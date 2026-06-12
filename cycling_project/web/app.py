"""
Cycling Race Prediction Web App

Run with: uv run streamlit run cycling_project/web/app.py
"""

import sys
from pathlib import Path

# Ensure the project root is on the path so cycling_project is importable
_PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# Load .env before any scraping so the startlist fetch picks up the browser
# backend (SCRAPER_USE_BROWSER) — FirstCycling's Cloudflare challenge 403s
# cloudscraper, so future-race predictions need the headed-Chrome path.
try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

import streamlit as st
import pandas as pd

from cycling_project.prediction_tools.future_race_loader import (
    parse_firstcycling_url,
    get_race_name,
    scrape_or_load_startlist,
    match_riders_to_db,
    get_latest_rider_snapshots,
    compute_field_features,
    get_reference_race_profile,
    average_race_profiles,
    assemble_prediction_df,
    attach_stack_features,
    load_production_rating_snapshots,
    search_historical_races,
    get_selected_race_details,
    scrape_or_load_results,
    compute_characteristics_from_results,
    compare_race_characteristics,
    evaluate_predictions_against_actual,
    evaluate_probability_heads_against_actual,
    get_race_finishing_characteristics,
    compute_profile_scores_from_results,
    detect_stage_race_from_db,
    get_available_stages,
    get_default_references,
)
from cycling_project.prediction_tools.contest_signature_features import (
    build_serving_signature_context,
)
from cycling_project.prediction_tools.dnf_predictor import (
    load_production_dnf_head,
)
from cycling_project.prediction_tools.gc_outlook import GCOutlookHead
from cycling_project.prediction_tools.pricing_layer import (
    BLEND_W,
    apply_pricing_layer,
)
from cycling_project.prediction_tools.live_race_state import (
    attach_race_state,
    enumerate_edition_stages,
    fetch_live_race_state,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    ensure_schema as _ensure_prediction_log_schema,
    log_predictions,
)
from cycling_project.prediction_tools.win_calibration import (
    load_corrector as load_win_corrector,
)


MODEL_DIR = str(Path(__file__).parent.parent.parent / "models" / "production")
DB_PATH = str(
    Path(__file__).parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)

# Absolute-percentage-point gap above which we flag a win-probability
# disagreement between the multiclass and LambdaRank heads in the UI.
DISAGREEMENT_THRESHOLD_PP = 2.0


def _decimal_to_american(d: float) -> str:
    """Convert decimal odds to American moneyline format."""
    if d >= 2.0:
        return f"+{round((d - 1) * 100)}"
    if d > 1.0:
        return f"-{round(100 / (d - 1))}"
    return "—"


def _decimal_to_fractional(d: float) -> str:
    """Convert decimal odds to fractional (British) format."""
    from fractions import Fraction
    profit = d - 1
    if profit >= 10:
        # Long shots: round to X/1
        return f"{round(profit)}/1"
    if profit <= 0:
        return "—"
    frac = Fraction(profit).limit_denominator(10)
    return str(frac)


def _fmt_stage_nums(nums) -> str:
    """Compact '1-4' / '1-3, 5' rendering of a stage-number list."""
    nums = sorted({int(n) for n in nums})
    if not nums:
        return ''
    runs = []
    start = prev = nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append((start, prev))
        start = prev = n
    runs.append((start, prev))
    return ', '.join(
        f"{a}" if a == b else f"{a}-{b}" for a, b in runs
    )


def _race_state_status(info: dict, feeds_gc_outlook: bool) -> tuple:
    """(level, message) describing the live race-state attachment outcome.

    Levels: 'ok' (quiet caption), 'info' (note — e.g. next stage simply not
    raced yet), 'warn' (loud — state missing or stale because data that
    should exist could not be loaded).
    """
    if not info.get('available'):
        return 'warn', (
            f"NOT attached — {info.get('reason') or 'unavailable'}. "
            "Predictions use pre-race features."
        )

    k = info.get('stages_completed')
    total = info.get('total_stages')
    total_txt = (
        f"{total} (est.)" if info.get('total_stages_estimated') else f"{total}"
    )
    parts = [f"attached through stage {k} of {total_txt}"]
    if info.get('leader_name'):
        parts.append(f"leader: {info['leader_name']}")
    parts.append(f"{info.get('riders_in_standings')} riders in standings")
    sources = info.get('sources') or {}
    src_bits = [
        f"{label} {_fmt_stage_nums(stage_nums)}"
        for label, stage_nums in (
            ('DB', sources.get('db')),
            ('cache', sources.get('cache')),
            ('scraped', sources.get('scraped')),
        )
        if stage_nums
    ]
    if src_bits:
        parts.append("from " + ", ".join(src_bits))
    if feeds_gc_outlook:
        parts.append(
            "feeds the GC outlook head (main GC prediction stays "
            "pre-race, mirroring training)"
        )
    msg = "; ".join(parts)

    missing = info.get('missing_stages') or []
    if not missing:
        return 'ok', msg
    horizon = info.get('db_horizon') or 'unknown'
    if info.get('scrape_failed'):
        return 'warn', (
            f"{msg}. STALE: stage(s) {_fmt_stage_nums(missing)} missing — "
            f"DB data through {horizon}, live fetch failed (scrape "
            f"pending). State reflects the race only through stage {k}."
        )
    return 'info', (
        f"{msg}. Stage(s) {_fmt_stage_nums(missing)} have no results yet "
        f"(not yet raced or published) — state is current through stage {k}."
    )


def _render_provenance_panel(prov: dict) -> None:
    """Compact always-visible status panel: one line per feature family /
    head, with its live status for THIS prediction run. Absence is loud
    (warning icon + bold), presence is quiet."""
    if not prov:
        return

    target = prov.get('target') or {}
    comp_type = target.get('comp_type') or 'one_day'
    if comp_type == 'stage' and target.get('stage_num'):
        target_txt = f"stage {target['stage_num']} target"
    elif comp_type == 'gc':
        target_txt = "GC target"
    else:
        target_txt = "one-day target"

    rows = []  # (is_warn, family, detail)

    rs = prov.get('race_state') or {}
    rows.append((
        rs.get('level') == 'warn', 'Race state', rs.get('msg', 'unknown')
    ))

    gco = prov.get('gc_outlook') or {}
    if gco.get('applicable'):
        if gco.get('engaged'):
            rows.append((
                False, 'GC outlook',
                'engaged — state-aware final-GC head '
                f"({gco.get('n_riders', '?')} riders)",
            ))
        else:
            rows.append((
                True, 'GC outlook',
                f"not engaged — {gco.get('note') or 'unavailable'}",
            ))
    else:
        rows.append((False, 'GC outlook', 'n/a (not a GC target)'))

    sig = prov.get('sig') or {}
    if not sig.get('applicable'):
        rows.append((
            False, 'Signatures',
            'n/a by design (one-day scope; stage/GC rows stay NaN)',
        ))
    elif sig.get('error'):
        rows.append((
            True, 'Signatures',
            f"unavailable (NaN fallback): {sig['error']}",
        ))
    elif (sig.get('coverage') or 0) > 0:
        detail = f"on — coverage {sig['coverage']:.0%}"
        if sig.get('n_refs') is not None:
            detail += f", {sig['n_refs']} reference comps"
        rows.append((False, 'Signatures', detail))
    else:
        rows.append((
            True, 'Signatures', 'all NaN (no reference signatures found)'
        ))

    elo = prov.get('elo') or {}
    if not elo.get('loaded'):
        rows.append((
            True, 'Contested Elo',
            'snapshots artifact missing — features NaN '
            '(run pipeline step elo-snapshots)',
        ))
    else:
        cov = elo.get('coverage') or 0.0
        rows.append((
            cov < 0.5, 'Contested Elo', f"rating coverage {cov:.0%} of field"
        ))

    meta = prov.get('meta_oof') or {}
    if meta.get('time_gap') and meta.get('lambdarank'):
        rows.append((
            False, 'Meta-OOF', 'time-gap + LambdaRank features attached'
        ))
    else:
        absent = [
            label for label, key in
            (('time-gap', 'time_gap'), ('LambdaRank', 'lambdarank'))
            if not meta.get(key)
        ]
        rows.append((True, 'Meta-OOF', f"missing: {', '.join(absent)}"))

    wc = prov.get('win_corrector') or {}
    if wc.get('loaded'):
        method = wc.get('method') or 'identity'
        if method == 'identity':
            detail = 'identity (no correction fitted)'
        elif wc.get('param') is not None:
            detail = f"applied — {method} (param {wc['param']:.4f})"
        else:
            detail = f"applied — {method}"
        rows.append((False, 'Win corrector', detail))
    else:
        rows.append((
            True, 'Win corrector',
            'artifact missing — uncorrected win probabilities',
        ))

    dnf = prov.get('dnf') or {}
    if dnf.get('loaded'):
        if dnf.get('mean_p') is not None:
            rows.append((
                False, 'DNF head',
                f"loaded — mean P(DNF) {dnf['mean_p']:.1%}",
            ))
        else:
            rows.append((True, 'DNF head', 'loaded but produced no output'))
    else:
        rows.append((
            True, 'DNF head',
            'absent — honest (DNF-adjusted) prices unavailable',
        ))

    bl = prov.get('blend') or {}
    if bl.get('available'):
        rows.append((
            False, 'Blend win',
            f"on (w={bl.get('w', 0.2):g} multiclass, book-preserving)",
        ))
    else:
        rows.append((
            True, 'Blend win', 'unavailable (LambdaRank head absent)'
        ))

    lf = prov.get('live_form') or {}
    if lf.get('mode') == 'live':
        rows.append((
            False, 'Live form re-aging', f"on (as-of {lf.get('asof_date')})"
        ))
    else:
        err = lf.get('error')
        rows.append((
            True, 'Live form re-aging',
            'FAILED — using stale snapshot form'
            + (f" ({err})" if err else ''),
        ))

    refs = prov.get('references') or []
    refs_detail = (
        f"{len(refs)} comps: " + '; '.join(refs) if refs else 'none selected'
    )
    rows.append((len(refs) == 0, 'References', refs_detail))

    def _line(is_warn: bool, family: str, detail: str) -> str:
        if is_warn:
            return f"⚠️ **{family} — {detail}**"
        return f"✓ {family} — {detail}"

    with st.container(border=True):
        st.markdown(f"**Prediction provenance** — {target_txt}")
        lines = [_line(*row) for row in rows]
        mid = (len(lines) + 1) // 2
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("  \n".join(lines[:mid]))
        with col2:
            st.markdown("  \n".join(lines[mid:]))


st.set_page_config(page_title="Cycling Race Predictor", layout="wide")
st.title("Cycling Race Predictor")

# Initialize session state for selected references
if 'selected_refs' not in st.session_state:
    st.session_state['selected_refs'] = {}  # {comp_id: row_dict}
if 'search_counter' not in st.session_state:
    st.session_state['search_counter'] = 0


# ── Step 1: Scrape Start List ─────────────────────────────────────────────

st.header("1. Enter Race URL")
url = st.text_input(
    "FirstCycling race URL",
    placeholder="https://firstcycling.com/race.php?r=9&y=2026",
)
force_refresh_startlist = st.checkbox("Force refresh start list", value=False)

if st.button("Get Start List") and url:
    try:
        race_id, year, stage_hint = parse_firstcycling_url(url)
        with st.spinner(f"Loading start list for race {race_id}, year {year}..."):
            teams, from_cache = scrape_or_load_startlist(race_id, year, force_refresh=force_refresh_startlist)
            matched, unmatched = match_riders_to_db(teams)
            if not matched.empty:
                rider_ids = matched['rider_id'].tolist()
                snapshots = get_latest_rider_snapshots(rider_ids)
                field_features = compute_field_features(snapshots)
            else:
                snapshots = pd.DataFrame()
                field_features = {}

        st.session_state['teams'] = teams
        st.session_state['matched'] = matched
        st.session_state['unmatched'] = unmatched
        st.session_state['snapshots'] = snapshots
        st.session_state['field_features'] = field_features
        st.session_state['url'] = url
        st.session_state['fc_race_id'] = race_id
        st.session_state['race_name'] = get_race_name(race_id)
        st.session_state['race_year'] = year
        st.session_state['startlist_from_cache'] = from_cache
        st.session_state['is_stage_race'] = detect_stage_race_from_db(race_id)
        st.session_state['stage_hint'] = stage_hint
        # Clear old selections, predictions, and results when new start list is loaded
        st.session_state['selected_refs'] = {}
        st.session_state['removed_rider_ids'] = set()
        st.session_state.pop('defaults_loaded', None)
        st.session_state.pop('all_predictions', None)
        st.session_state.pop('actual_results', None)
        st.session_state.pop('race_stages', None)
        st.session_state.pop('_predictions_removed_set', None)
        st.session_state.pop('provenance', None)
    except Exception as e:
        st.error(f"Error: {e}")

# Show start list results
if 'matched' in st.session_state and not st.session_state['matched'].empty:
    if 'race_name' in st.session_state:
        st.subheader(f"{st.session_state['race_name']} {st.session_state['race_year']}")
        if st.session_state.get('startlist_from_cache'):
            st.caption("Start list loaded from cache")

    matched = st.session_state['matched']
    unmatched = st.session_state['unmatched']

    # ── Edit Start List (remove DNS riders) ──
    rider_options = {
        row['rider_id']: f"{row['rider_name']} ({row['team_name']})"
        for _, row in matched.iterrows()
    }
    current_removed = st.session_state.get('removed_rider_ids', set())

    removed_ids = st.multiselect(
        "Remove riders (DNS / late withdrawals)",
        options=list(rider_options.keys()),
        default=[rid for rid in current_removed if rid in rider_options],
        format_func=lambda rid: rider_options[rid],
        placeholder="Search and select riders to remove...",
    )
    st.session_state['removed_rider_ids'] = set(removed_ids)

    # Derive active (filtered) data
    removed = st.session_state['removed_rider_ids']
    full_snapshots = st.session_state['snapshots']

    if removed:
        active_matched = matched[~matched['rider_id'].isin(removed)]
        active_snapshots = full_snapshots[~full_snapshots['rider_id'].isin(removed)]
        active_field_features = compute_field_features(active_snapshots)
    else:
        active_matched = matched
        active_snapshots = full_snapshots
        active_field_features = st.session_state['field_features']

    st.session_state['active_matched'] = active_matched
    st.session_state['active_snapshots'] = active_snapshots
    st.session_state['active_field_features'] = active_field_features

    col1, col2 = st.columns(2)
    with col1:
        if removed:
            st.success(f"{len(active_matched)} riders in prediction field ({len(removed)} removed)")
        else:
            st.success(f"Matched {len(matched)} riders in database")
        st.dataframe(
            active_matched[['rider_name', 'team_name', 'bib_number']].rename(
                columns={'rider_name': 'Rider', 'team_name': 'Team', 'bib_number': 'Bib'}
            ),
            hide_index=True,
            width='stretch',
        )
    with col2:
        if unmatched:
            st.warning(f"{len(unmatched)} riders not found in database")
            unmatched_df = pd.DataFrame(unmatched)[['rider_name', 'team_name', 'bib_number']].rename(
                columns={'rider_name': 'Rider', 'team_name': 'Team', 'bib_number': 'Bib'}
            )
            st.dataframe(unmatched_df, hide_index=True, width='stretch')
        else:
            st.success("All riders found in database")


# ── Step 2: Select Reference Races ────────────────────────────────────────

if 'matched' in st.session_state and not st.session_state['matched'].empty:
    st.header("2. Select Reference Races")

    fc_race_id = st.session_state['fc_race_id']
    is_stage_race = st.session_state.get('is_stage_race', False)

    # ── 2a. Stage/GC selector and auto-populate defaults ──
    selected_comp_type = 'one_day'
    selected_stage_num = None

    if is_stage_race:
        available_stages = get_available_stages(fc_race_id)
        if available_stages:
            stage_labels = [s['label'] for s in available_stages]
            stage_hint = st.session_state.get('stage_hint')

            default_idx = 0
            if stage_hint is not None:
                for i, s in enumerate(available_stages):
                    if s['stage_number'] == stage_hint:
                        default_idx = i
                        break

            selected_label = st.selectbox(
                "Competition to predict",
                stage_labels,
                index=default_idx,
                key="stage_selector",
            )
            selected_stage_info = next(s for s in available_stages if s['label'] == selected_label)
            selected_comp_type = selected_stage_info['competition_type']
            selected_stage_num = selected_stage_info['stage_number']
        else:
            st.warning("No historical stage data found for this race.")

    # Detect stage selector change and reset defaults
    prev_comp_type = st.session_state.get('_prev_comp_type')
    prev_stage_num = st.session_state.get('_prev_stage_num')
    if prev_comp_type is not None and (
        selected_comp_type != prev_comp_type or selected_stage_num != prev_stage_num
    ):
        st.session_state['selected_refs'] = {}
        st.session_state.pop('defaults_loaded', None)
    st.session_state['_prev_comp_type'] = selected_comp_type
    st.session_state['_prev_stage_num'] = selected_stage_num

    # Auto-populate defaults (runs once per stage selection)
    if not st.session_state.get('defaults_loaded'):
        defaults = get_default_references(
            fc_race_id=fc_race_id,
            competition_type=selected_comp_type,
            stage_number=selected_stage_num,
            exclude_year=st.session_state['race_year'],
            max_results=5,
        )
        if not defaults.empty:
            for _, row in defaults.iterrows():
                comp_id = int(row['competition_id'])
                st.session_state['selected_refs'][comp_id] = row.to_dict()
            n = len(defaults)
            if n < 5:
                st.info(
                    f"Auto-selected {n} historical edition{'s' if n != 1 else ''} "
                    f"(only {n} available with profile data)"
                )
            else:
                st.success("Auto-selected 5 most recent editions")
        else:
            st.warning(
                "No historical editions found with profile data. "
                "Search manually below."
            )
        st.session_state['defaults_loaded'] = True

    # ── 2b. Currently selected races (always visible at top) ──
    selected_refs = st.session_state['selected_refs']

    if selected_refs:
        st.subheader(f"Selected ({len(selected_refs)}/5)")

        # Get enriched details for selected races
        comp_ids = list(selected_refs.keys())
        details_df = get_selected_race_details(comp_ids)
        st.session_state['reference_details'] = details_df

        # Main profile table
        sel_rows = list(selected_refs.values())
        sel_df = pd.DataFrame(sel_rows)[[
            'competition_id', 'display_name', 'competition_date',
            'competition_type', 'race_dominant_profile',
            'race_sprint_score', 'race_mountain_score', 'race_hilly_score',
            'race_rolling_score', 'race_breakaway_score', 'race_time_trial_score',
        ]].copy()
        sel_df.columns = ['ID', 'Name', 'Date', 'Type', 'Profile',
                          'Sprint', 'Mtn', 'Hilly', 'Rolling', 'Breakaway', 'TT']
        score_cols = ['Sprint', 'Mtn', 'Hilly', 'Rolling', 'Breakaway', 'TT']
        for col in score_cols:
            sel_df[col] = sel_df[col].apply(lambda v: float(v) if v is not None else 0.0)
        score_col_config = {
            col: st.column_config.ProgressColumn(
                min_value=0, max_value=1, format="%.2f"
            ) for col in score_cols
        }
        st.dataframe(sel_df, hide_index=True, width='stretch',
                      column_config=score_col_config)

        # Understanding Race Profiles expander
        with st.expander("Understanding Race Profiles"):
            st.markdown("""
Race profiles are derived from how finishing time distributions change as you look
deeper into the results — from the top 10% of finishers down to the full field.
This captures the *outcome* of a race, not the course terrain. Each race gets a
score (0-1) for each profile type, and the six scores sum to 1.0.

We track four statistical gradients across finishing percentiles:

- **Breakdown percentile**: The point at which finishing times lose enough variance
  to compute statistics — a 50% breakdown means the top 50% all recorded essentially
  the same time. No breakdown means gaps exist throughout.
- **Variance slope**: How quickly the spread of finishing times grows as you include
  lower-placed finishers. Steep = gaps widen rapidly. Flat = times stay tight.
- **Clumpiness slope**: Whether riders increasingly form distinct finishing groups
  as you look deeper. Positive = more clustering into packs.
- **Biggest group slope**: How the largest finishing group changes in relative size.
  Negative = the main group fragments as you include more finishers.

---

**Sprint** — *Bunch sprint finish. Flat stages controlled by sprint teams.*
97% of sprint-classified races have a breakdown point, typically 55-90% — meaning
the top 55-90% of finishers all recorded the same time. Near-zero variance slope:
time gaps barely grow because so many riders are in the same bunch.
Hallmark: massive group finishing together + flat variance growth.

**Mountain** — *Selective summit finish. Alpine/Pyrenean summit finishes.*
100% have no breakdown point — there's variance in finishing times at every
percentile, even the top 10%. Highest variance slope of all types (~3.3e-05, 6x
rolling) — gaps widen steeply the deeper you look.
Hallmark: no bunch at any level + the steepest variance growth.

**Hilly** — *Moderately selective. Ardennes classics, punchy finishes.*
100% have a breakdown point, typically 25-50% — the top quarter to half finishes
together, then gaps appear. Highest clumpiness slope of all types (0.007, 2-3x
others) — riders cluster into distinct groups below the bunch.
Hallmark: mid-range bunching + strong group formation.

**Rolling** — *Gradual, steady selection. Wind-affected stages, medium terrain.*
99% have no breakdown point — like mountain stages, there's variance throughout.
But variance slope is moderate (~5.7e-06, about 1/6th of mountain). Gaps grow
steadily, not steeply. This is the most common profile (52% of all races).
Hallmark: no big bunch + moderate, consistent gap growth.

**Breakaway** — *Early selection with fragmentation.*
99% have a breakdown in the 10-20% range — only a small group at the very top
finishes together. Most negative biggest group slope of all types (-0.008, 2x
others) — the largest group gets progressively smaller.
Hallmark: small initial bunch + the most aggressive group fragmentation.

**TT** — *Individual or team time trial.*
Identified by winning time < 70 minutes rather than gradient patterns. Each rider
races alone, so 99% have no breakdown point — variance exists throughout.
""")

        # Finishing Time Distributions expander
        if not details_df.empty and 'biggest_group_metric' in details_df.columns:
            with st.expander("Finishing Time Distributions"):
                st.caption(
                    "Raw statistical characteristics measured at the 50th percentile "
                    "(top half of finishers). These feed into the profile scoring model. "
                    "Biggest Group: size/position influence of the largest finishing group (0-1). "
                    "Evenness: how uniformly spaced time gaps are (1=even, 0=bunchy). "
                    "Clumpiness: degree of group clustering (higher=more groups). "
                    "Selection: how selective the race was (spread + gap progression). "
                    "Gini: inequality in time gaps (0=equal, 1=max inequality)."
                )
                char_cols = {
                    'display_name': 'Race',
                    'biggest_group_metric': 'Biggest Group',
                    'time_gap_evenness_metric': 'Evenness',
                    'clumpiness_score': 'Clumpiness',
                    'selection_metric': 'Selection',
                    'total_race_duration': 'Duration (s)',
                    'variance_normalized': 'Variance',
                    'skewness_normalized': 'Skewness',
                    'gini_coefficient': 'Gini',
                    'total_finishers': 'Finishers',
                    'abandon_ratio': 'Abandon %',
                    'largest_group_size': 'Largest Group',
                    'proportion_in_groups': 'In Groups %',
                }
                available = [c for c in char_cols if c in details_df.columns]
                char_df = details_df[available].copy()
                char_df = char_df.rename(columns=char_cols)
                # Format numeric columns
                for col in char_df.columns:
                    if col not in ['Race', 'Finishers', 'Largest Group', 'Duration (s)']:
                        char_df[col] = char_df[col].apply(
                            lambda v: f"{v:.3f}" if pd.notna(v) else ""
                        )
                st.dataframe(char_df, hide_index=True, width='stretch')

        # Field Composition expander
        if not details_df.empty and 'field_size' in details_df.columns:
            with st.expander("Field Composition"):
                field_cols = {
                    'display_name': 'Race',
                    'field_size': 'Field Size',
                    'experience_mean': 'Avg Experience',
                    'bucket_mean': 'Avg Bucket',
                    'sprinter_count': 'Sprinters',
                    'climber_count': 'Climbers',
                    'hilly_specialist_count': 'Hilly',
                    'rolling_specialist_count': 'Rolling',
                    'breakaway_specialist_count': 'Breakaway',
                    'time_trialist_count': 'TT',
                }
                available = [c for c in field_cols if c in details_df.columns]
                field_df = details_df[available].copy()
                field_df = field_df.rename(columns=field_cols)
                for col in ['Avg Experience', 'Avg Bucket']:
                    if col in field_df.columns:
                        field_df[col] = field_df[col].apply(
                            lambda v: f"{v:.1f}" if pd.notna(v) else ""
                        )
                st.dataframe(field_df, hide_index=True, width='stretch')

        # Remove buttons
        cols = st.columns(min(len(selected_refs), 5))
        for i, (comp_id, ref) in enumerate(list(selected_refs.items())):
            with cols[i % len(cols)]:
                if st.button(f"Remove {ref['display_name'][:30]}...", key=f"rm_{comp_id}"):
                    del st.session_state['selected_refs'][comp_id]
                    st.rerun()

        if st.button("Clear all selections"):
            st.session_state['selected_refs'] = {}
            st.rerun()
    else:
        st.info("No reference races selected yet. Search below and add up to 5.")

    st.divider()

    # ── 2c. Search for races to add ──
    with st.expander("Search Historical Races", expanded=not bool(selected_refs)):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            name_q = st.text_input("Race name", placeholder="Tour de France")
        with col2:
            year_q = st.number_input("Year", min_value=2010, max_value=2025, value=2024, step=1)
        with col3:
            cat_q = st.selectbox("Category", ["All", "wt", "pro", "d1"])
        with col4:
            type_q = st.selectbox("Type", ["All", "stage", "one_day", "gc"])

        if st.button("Search"):
            results = search_historical_races(
                name_filter=name_q if name_q else None,
                year_filter=int(year_q) if year_q else None,
                category_filter=cat_q if cat_q != "All" else None,
                type_filter=type_q if type_q != "All" else None,
                limit=200,
            )
            st.session_state['search_results'] = results
            st.session_state['search_counter'] += 1

        if 'search_results' in st.session_state and not st.session_state['search_results'].empty:
            results = st.session_state['search_results']

            # Show results with add checkboxes
            st.caption(f"{len(results)} results found")

            # Multi-select from search results
            already_selected = set(st.session_state['selected_refs'].keys())
            available = results[~results['competition_id'].isin(already_selected)].reset_index(drop=True)

            if available.empty:
                st.info("All search results are already selected.")
            else:
                display_df = available[[
                    'competition_id', 'display_name', 'competition_date',
                    'competition_type', 'race_category', 'field_size',
                    'race_dominant_profile',
                ]].copy()
                display_df.columns = ['ID', 'Name', 'Date', 'Type', 'Category', 'Field Size', 'Profile']
                event = st.dataframe(
                    display_df,
                    hide_index=True,
                    width='stretch',
                    on_select="rerun",
                    selection_mode="multi-row",
                    key=f"search_results_table_{st.session_state['search_counter']}",
                )

                # ── Click-to-add from dataframe selection ──
                selected_rows = event.selection.rows
                if selected_rows:
                    spots_left = 5 - len(st.session_state['selected_refs'])
                    if spots_left <= 0:
                        st.warning("5/5 reference races selected. Remove one to add more.")
                    else:
                        rows_to_add = selected_rows[:spots_left]
                        n_selected = len(selected_rows)
                        label = f"Add {len(rows_to_add)} selected race{'s' if len(rows_to_add) != 1 else ''}"
                        if n_selected > spots_left:
                            label += f" (only {spots_left} spot{'s' if spots_left != 1 else ''} left)"
                        if st.button(label, key="add_from_dataframe"):
                            for row_idx in rows_to_add:
                                comp_id = int(available.iloc[row_idx]['competition_id'])
                                if comp_id not in st.session_state['selected_refs']:
                                    row = results[results['competition_id'] == comp_id]
                                    if not row.empty:
                                        st.session_state['selected_refs'][comp_id] = row.iloc[0].to_dict()
                            st.rerun()

                st.divider()

                # Add by ID input
                spots_left = 5 - len(st.session_state['selected_refs'])
                if spots_left > 0:
                    add_input = st.text_input(
                        f"Enter competition ID(s) to add (comma-separated, {spots_left} spot{'s' if spots_left != 1 else ''} left)",
                        placeholder="e.g. 141, 142, 10",
                        key="add_ids",
                    )
                    if st.button("Add to selection"):
                        if add_input:
                            try:
                                ids_to_add = [int(x.strip()) for x in add_input.split(',') if x.strip()]
                                added = 0
                                for cid in ids_to_add:
                                    if added >= spots_left:
                                        break
                                    if cid in st.session_state['selected_refs']:
                                        continue
                                    row = results[results['competition_id'] == cid]
                                    if not row.empty:
                                        st.session_state['selected_refs'][cid] = row.iloc[0].to_dict()
                                        added += 1
                                    else:
                                        st.warning(f"ID {cid} not in current search results")
                                if added:
                                    st.rerun()
                            except ValueError:
                                st.error("Enter valid comma-separated numbers")
                else:
                    st.warning("5/5 reference races selected. Remove one to add more.")


# ── Step 3: Run Predictions ───────────────────────────────────────────────

if (
    st.session_state.get('selected_refs')
    and 'active_snapshots' in st.session_state
    and not st.session_state['active_snapshots'].empty
):
    st.header("3. Predictions")

    with st.expander("How these predictions work", expanded=False):
        st.markdown("""
Every prediction run produces three kinds of output per rider. They're
derived from different models and answer slightly different questions.

**Rank order (the default sort)** — produced by the *bucket + time-gap
ensemble*. The bucket predictor is a LightGBM ordinal regression that
estimates each rider's finishing bucket (0 = winner, 1 = podium, …,
6 = finisher). The time-gap predictor estimates seconds behind the
winner. Combined as an ensemble, they produce the `Predicted Rank`
column — treat this as "most likely to least likely to do well."

**Win % / Podium % / Top 5 % / Top 15 %** — produced by the *multiclass
contender cascade*. The bucket predictor first narrows to the top 15
contenders; then a softmax classifier (5-class reduction: winner,
podium, top-5, top-15, rest) assigns probabilities to each. This is
the strongest model we have for *discrimination* — i.e. picking which
rider from a field will win. Historically it captures ~24% of winners
in a 130-rider field (vs ~0.8% random baseline).

**LR Win % / LR Podium %** — produced by the *full-field LambdaRank
probability head*. A single LightGBM model trained with a ranking loss
(LambdaRank/NDCG); its scores are softmaxed across the entire field
to produce probabilities. Slightly weaker on discrimination than the
contender cascade but **near-perfectly calibrated** (mean predicted
probability ≈ actual frequency). These are the numbers to compare
against sportsbook-implied odds.

**Δ Win pp** — the absolute gap between the two heads' win
probabilities. Rows highlighted yellow mean the two heads disagree by
≥ 2pp on win probability for that rider. Disagreement is interesting:
one head sees the rider as a stronger or weaker favorite than the
other. Every prediction run is logged to the `prediction_log` table so
we can later analyze *which head is right* when they disagree.

**Odds** — simply the reciprocal of each probability, rendered in
decimal / American / fractional formats. Uses the multiclass
probabilities by default (the more discriminative head).

**Arm-C stack (2026-06-11)** — the bucket + contender models now consume
17 extra features (meta-OOF time-gap & LambdaRank predictions, one-day
contest signatures, contested-comparison Elo), the combination that
passed the probability gate. Three pricing additions on top:

- *Win %* carries a scalar **calibration corrector** fit at train time
  (the stack's raw win book ran slightly under-confident on one-days).
- **Blend Win %** — 0.2 × multiclass + 0.8 × LambdaRank win probability,
  renormalized to preserve the multiclass book (small but consistent
  log-loss winner in CV).
- **DNF %** and the *DNF-adjusted (honest) prices* expander — the
  multiclass heads are trained on finishers only, so their probabilities
  are implicitly conditioned on finishing. P(market | finish) × P(finish)
  from the DNF head is the price an actual bet pays on.
""")

    # Warn if startlist changed since last prediction run
    if 'all_predictions' in st.session_state:
        current_removed = st.session_state.get('removed_rider_ids', set())
        prev_removed = st.session_state.get('_predictions_removed_set', set())
        if current_removed != prev_removed:
            st.warning("Start list has changed since predictions were run. Re-run predictions to update.")

    # Within-race state applies when predicting stage 2+ of a stage race
    # (state features feed the main models, mirroring training) or the GC
    # of an in-progress stage race (state feeds the separate GC outlook
    # head; the main GC prediction stays pre-race, also mirroring training).
    _state_target_is_stage = (
        st.session_state.get('_prev_comp_type') == 'stage'
        and (st.session_state.get('_prev_stage_num') or 0) >= 2
    )
    _state_target_is_gc = (
        st.session_state.get('_prev_comp_type') == 'gc'
        and st.session_state.get('is_stage_race', False)
    )
    force_refresh_state = False
    if _state_target_is_stage or _state_target_is_gc:
        force_refresh_state = st.checkbox(
            "Force refresh completed stages (race state)",
            value=False,
            help=(
                "Re-scrape this edition's completed stage results instead of "
                "using the cache. Use after a new stage has finished."
            ),
        )

    if st.button("Run Predictions", type="primary"):
        selected_refs = st.session_state['selected_refs']
        snapshots = st.session_state['active_snapshots']
        matched = st.session_state['active_matched']
        field_features = st.session_state['active_field_features']

        with st.spinner("Loading model and running predictions..."):
            try:
                # Load model (ensemble gives both bucket + time gap,
                # plus the optional full-field LambdaRank probability head)
                registry = ModelRegistry(MODEL_DIR)
                (
                    bucket_pred,
                    time_gap_pred,
                    race_ranker,
                    lambdarank_pred,
                ) = registry.load_with_ranker(ranking_method='ensemble')
                registry_metadata = registry.get_metadata()
                model_version = registry_metadata.get('saved_at', '')

                # ── Arm-C stack inputs (all optional; features stay NaN
                # and pricing degrades gracefully when artifacts are absent)
                win_corrector = load_win_corrector(MODEL_DIR)
                dnf_bundle = load_production_dnf_head(Path(MODEL_DIR))
                rating_snaps = load_production_rating_snapshots()

                # Build name/team lookup
                name_map = matched.set_index('rider_id')[['rider_name', 'team_name']].to_dict('index')

                all_predictions = {}
                reference_profiles = []
                log_rows: list = []

                fc_race_id = str(st.session_state.get('fc_race_id', ''))
                race_year = st.session_state.get('race_year')
                target_comp_type = st.session_state.get('_prev_comp_type', 'one_day')
                target_stage_num = st.session_state.get('_prev_stage_num')
                reference_ids = [int(c) for c in selected_refs.keys()]

                # Log stage_number = the SELECTED prediction target (NULL for
                # one-day and GC), so state_through_stage pairs coherently.
                logged_stage_num = (
                    int(target_stage_num)
                    if target_comp_type == 'stage' and target_stage_num
                    else None
                )

                # ── Within-race state ──
                # Stage 2+ targets: state feeds the MAIN models (mirrors
                # training). GC targets of stage races: state feeds only
                # the separate GC outlook head; the main GC prediction
                # stays pre-race (gc training rows carry no state).
                fetch_for_stage = (
                    target_comp_type == 'stage'
                    and target_stage_num
                    and int(target_stage_num) >= 2
                )
                fetch_for_gc = (
                    target_comp_type == 'gc'
                    and st.session_state.get('is_stage_race', False)
                )
                race_state_df = None
                race_state_info = None
                if fetch_for_stage or fetch_for_gc:
                    race_state_df, race_state_info = fetch_live_race_state(
                        int(fc_race_id),
                        int(race_year),
                        target_stage_number=(
                            int(target_stage_num) if fetch_for_stage else None
                        ),
                        force_refresh=force_refresh_state,
                        db_path=DB_PATH,
                    )
                # State for the main per-reference/averaged predictions —
                # only stage targets; everything else gets NaN -> defaults.
                main_state_df = race_state_df if fetch_for_stage else None
                state_through = (
                    int(race_state_info['stages_completed'])
                    if race_state_info and race_state_info.get('available')
                    else None
                )
                # Honest state status: through which stage, from which
                # sources, and exactly what is missing when data is stale
                # (mid-race edition with the scrape on hold).
                if race_state_info is not None:
                    rs_level, rs_msg = _race_state_status(
                        race_state_info, feeds_gc_outlook=bool(fetch_for_gc)
                    )
                    {
                        'ok': st.caption,
                        'info': st.info,
                        'warn': st.warning,
                    }[rs_level](f"Race state: {rs_msg}")
                else:
                    rs_level = 'ok'
                    if target_comp_type == 'one_day':
                        rs_msg = 'n/a (one-day race)'
                    elif target_comp_type == 'stage':
                        rs_msg = 'n/a (stage 1 — no prior stages)'
                    else:
                        rs_msg = 'n/a (not an in-progress stage-race target)'

                def _attach_lambdarank(result_df: pd.DataFrame, pred_df: pd.DataFrame):
                    """Merge LambdaRank win/podium probabilities onto result_df.

                    Both columns are aligned on rider_id; silently no-ops
                    if the LambdaRank head isn't installed in the registry.
                    """
                    if lambdarank_pred is None:
                        return None
                    # LambdaRank requires competition_id to form the softmax
                    # denominator. pred_df already has competition_id=0 set
                    # by assemble_prediction_df, so the whole field forms
                    # one group (what we want for full-field softmax).
                    win_p = lambdarank_pred.predict_win_probabilities(pred_df)
                    podium_p = lambdarank_pred.predict_topk_probabilities(
                        pred_df, k=3, n_samples=2000
                    )
                    lr_df = pd.DataFrame({
                        'rider_id': pred_df['rider_id'].values,
                        'lambdarank_win_p': win_p.values,
                        'lambdarank_podium_p': podium_p.values,
                    })
                    result_df['lambdarank_win_p'] = result_df['rider_id'].map(
                        lr_df.set_index('rider_id')['lambdarank_win_p']
                    )
                    result_df['lambdarank_podium_p'] = result_df['rider_id'].map(
                        lr_df.set_index('rider_id')['lambdarank_podium_p']
                    )
                    return float(lambdarank_pred.config.temperature)

                # ── Arm-C signature context: one-day targets only.
                # Stage / gc targets keep all signature columns NaN — the
                # models' trained out-of-scope state (ref-keyed stage serving
                # was shown to cost +0.078 log loss).
                sig_context = None
                sig_error = None
                if target_comp_type == 'one_day':
                    try:
                        sig_context = build_serving_signature_context(
                            reference_ids, field_features, DB_PATH,
                        )
                    except Exception as sig_exc:
                        sig_error = str(sig_exc)
                        st.warning(
                            f"Signature features unavailable (NaN fallback): {sig_exc}"
                        )

                _pricing_warned = set()

                def _apply_pricing_layer(result_df: pd.DataFrame, pred_df: pd.DataFrame,
                                         profile: dict):
                    """Shared pricing layer (prediction_tools.pricing_layer):
                    win corrector + blend win market + DNF-adjusted prices."""
                    priced, pricing_warnings = apply_pricing_layer(
                        result_df, pred_df, profile,
                        win_corrector=win_corrector,
                        dnf_bundle=dnf_bundle,
                        stage_number=(
                            int(target_stage_num)
                            if target_comp_type == 'stage' and target_stage_num
                            else None
                        ),
                        db_path=DB_PATH,
                    )
                    for w in pricing_warnings:
                        if w not in _pricing_warned:
                            _pricing_warned.add(w)
                            st.warning(w)
                    return priced

                def _append_log_rows(label: str, result_df: pd.DataFrame, lr_temp):
                    for _, row in result_df.iterrows():
                        log_rows.append(PredictionLogRow(
                            fc_race_id=fc_race_id,
                            year=int(race_year) if race_year else 0,
                            stage_number=logged_stage_num,
                            rider_id=int(row['rider_id']),
                            rider_name=row.get('rider_name'),
                            reference_comp_ids=reference_ids,
                            model_version=model_version,
                            multiclass_win_p=row.get('prob_win'),
                            multiclass_podium_p=row.get('prob_podium'),
                            multiclass_top5_p=row.get('prob_top5'),
                            multiclass_top15_p=row.get('prob_top15'),
                            lambdarank_win_p=row.get('lambdarank_win_p'),
                            lambdarank_podium_p=row.get('lambdarank_podium_p'),
                            lambdarank_temperature=lr_temp,
                            state_through_stage=state_through,
                            dnf_p=row.get('dnf_p'),
                            dnf_adj_win_p=row.get('dnf_adj_win_p'),
                            dnf_adj_podium_p=row.get('dnf_adj_podium_p'),
                            dnf_adj_top5_p=row.get('dnf_adj_top5_p'),
                            dnf_adj_top15_p=row.get('dnf_adj_top15_p'),
                            blend_win_p=row.get('blend_win_p'),
                        ))

                # Live-form recompute status, written by assemble_prediction_df
                # (shared across all assembles this run — same inputs).
                form_status: dict = {}

                for comp_id in selected_refs:
                    profile = get_reference_race_profile(comp_id)
                    reference_profiles.append(profile)

                    pred_df = assemble_prediction_df(
                        snapshots, matched, field_features, profile,
                        form_status=form_status,
                    )
                    pred_df = attach_race_state(pred_df, main_state_df)
                    pred_df = attach_stack_features(
                        pred_df, time_gap_pred, lambdarank_pred,
                        rating_snapshots=rating_snaps,
                        signature_context=sig_context,
                    )
                    result = race_ranker.predict_race(pred_df, return_details=True)
                    result['team'] = result['rider_id'].map(
                        lambda rid: name_map.get(rid, {}).get('team_name', '')
                    )
                    lr_temp = _attach_lambdarank(result, pred_df)
                    result = _apply_pricing_layer(result, pred_df, profile)

                    label = f"{profile['competition_name']} ({profile['competition_date']})"
                    all_predictions[label] = result
                    _append_log_rows(label, result, lr_temp)

                # Average prediction (always, even for 1 race)
                avg_profile = average_race_profiles(reference_profiles)
                pred_df = assemble_prediction_df(
                    snapshots, matched, field_features, avg_profile,
                    form_status=form_status,
                )
                pred_df = attach_race_state(pred_df, main_state_df)
                pred_df = attach_stack_features(
                    pred_df, time_gap_pred, lambdarank_pred,
                    rating_snapshots=rating_snaps,
                    signature_context=sig_context,
                )
                result = race_ranker.predict_race(pred_df, return_details=True)
                result['team'] = result['rider_id'].map(
                    lambda rid: name_map.get(rid, {}).get('team_name', '')
                )
                lr_temp = _attach_lambdarank(result, pred_df)
                result = _apply_pricing_layer(result, pred_df, avg_profile)
                all_predictions['Averaged Reference Races'] = result
                _append_log_rows('Averaged Reference Races', result, lr_temp)

                # ── GC outlook head (state-aware final-GC prediction) ──
                gc_outlook_df = None
                gc_outlook_note = None
                if fetch_for_gc and race_state_df is None:
                    gc_outlook_note = (
                        "no race state — "
                        + (
                            (race_state_info or {}).get('reason')
                            or 'unavailable'
                        )
                    )
                if fetch_for_gc and race_state_df is not None:
                    gc_outlook_head = GCOutlookHead.load(MODEL_DIR)
                    if gc_outlook_head is None:
                        gc_outlook_note = "head not installed"
                        st.info(
                            "GC outlook head not installed — train it with "
                            "`uv run python -m cycling_project.update_pipeline "
                            "--only train-gc-outlook`."
                        )
                    else:
                        outlook_frame = assemble_prediction_df(
                            snapshots, matched, field_features, avg_profile,
                            form_status=form_status,
                        )
                        outlook_frame = attach_race_state(
                            outlook_frame, race_state_df
                        )
                        gc_outlook_df = gc_outlook_head.predict(outlook_frame)
                        if gc_outlook_df.empty:
                            gc_outlook_note = (
                                "head produced no rows (no riders in "
                                "reconstructed standings)"
                            )
                        if not gc_outlook_df.empty:
                            gc_outlook_df['team'] = gc_outlook_df['rider_id'].map(
                                lambda rid: name_map.get(rid, {}).get('team_name', '')
                            )
                            # Outlook is run-level (averaged profile): merge
                            # its probabilities onto every log row by rider.
                            outlook_by_rider = gc_outlook_df.set_index('rider_id')
                            for r in log_rows:
                                if r.rider_id in outlook_by_rider.index:
                                    o = outlook_by_rider.loc[r.rider_id]
                                    r.gc_outlook_win_p = o.get('gc_outlook_win_p')
                                    r.gc_outlook_podium_p = o.get('gc_outlook_podium_p')
                                    r.gc_outlook_top5_p = o.get('gc_outlook_top5_p')
                                    r.gc_outlook_top15_p = o.get('gc_outlook_top15_p')
                st.session_state['gc_outlook'] = gc_outlook_df
                st.session_state['gc_outlook_state_info'] = race_state_info

                # ── Prediction provenance (persistent status panel) ──
                # Computed from the averaged-reference frame/result (in scope
                # from the run above) — representative of every tab.
                _sig_cov = (
                    float(pred_df['sig_sprint'].notna().mean())
                    if 'sig_sprint' in pred_df.columns else 0.0
                )
                _sig_n_refs_series = (
                    pred_df['sig_n_refs'].dropna()
                    if 'sig_n_refs' in pred_df.columns else pd.Series(dtype=float)
                )
                _dnf_series = (
                    result['dnf_p'].dropna()
                    if 'dnf_p' in result.columns else pd.Series(dtype=float)
                )
                st.session_state['provenance'] = {
                    'target': {
                        'comp_type': target_comp_type,
                        'stage_num': (
                            int(target_stage_num) if target_stage_num else None
                        ),
                    },
                    'race_state': {'level': rs_level, 'msg': rs_msg},
                    'gc_outlook': {
                        'applicable': bool(fetch_for_gc),
                        'engaged': (
                            gc_outlook_df is not None
                            and not gc_outlook_df.empty
                        ),
                        'note': gc_outlook_note,
                        'n_riders': (
                            int(len(gc_outlook_df))
                            if gc_outlook_df is not None else 0
                        ),
                    },
                    'sig': {
                        'applicable': target_comp_type == 'one_day',
                        'coverage': _sig_cov,
                        'n_refs': (
                            int(_sig_n_refs_series.iloc[0])
                            if len(_sig_n_refs_series) else None
                        ),
                        'error': sig_error,
                    },
                    'elo': {
                        'loaded': rating_snaps is not None,
                        'coverage': (
                            float(pred_df['contested_rating'].notna().mean())
                            if 'contested_rating' in pred_df.columns else 0.0
                        ),
                    },
                    'meta_oof': {
                        'time_gap': bool(
                            'oof_time_gap_pred' in pred_df.columns
                            and pred_df['oof_time_gap_pred'].notna().any()
                        ),
                        'lambdarank': bool(
                            'oof_lambdarank_win_p' in pred_df.columns
                            and pred_df['oof_lambdarank_win_p'].notna().any()
                        ),
                    },
                    'win_corrector': {
                        'loaded': bool(win_corrector),
                        'method': (
                            win_corrector.get('method')
                            if win_corrector else None
                        ),
                        'param': (
                            win_corrector.get('param')
                            if win_corrector else None
                        ),
                    },
                    'dnf': {
                        'loaded': dnf_bundle is not None,
                        'mean_p': (
                            float(_dnf_series.mean())
                            if len(_dnf_series) else None
                        ),
                    },
                    'blend': {
                        'available': bool(
                            'blend_win_p' in result.columns
                            and result['blend_win_p'].notna().any()
                        ),
                        'w': BLEND_W,
                    },
                    'live_form': dict(form_status),
                    'references': [
                        f"{p.get('competition_name')} "
                        f"({p.get('competition_date')})"
                        for p in reference_profiles
                    ],
                }

                # Persist to prediction_log (best-effort — never blocks the UI)
                if log_rows and fc_race_id:
                    try:
                        import sqlite3
                        from cycling_project.prediction_tools.prediction_log import (
                            resolve_competition_id,
                        )
                        with sqlite3.connect(DB_PATH) as conn:
                            _ensure_prediction_log_schema(conn)
                            # Fill competition_id for the *target* race if it exists
                            target_comp_id = resolve_competition_id(
                                conn,
                                fc_race_id,
                                int(race_year) if race_year else 0,
                                logged_stage_num,
                            )
                            for r in log_rows:
                                r.competition_id = target_comp_id
                            log_predictions(conn, log_rows)
                    except Exception as log_exc:
                        st.warning(f"Prediction log write failed (non-fatal): {log_exc}")

                st.session_state['all_predictions'] = all_predictions
                st.session_state['reference_profiles'] = reference_profiles
                st.session_state['_predictions_removed_set'] = set(
                    st.session_state.get('removed_rider_ids', set())
                )
                st.session_state['lambdarank_available'] = lambdarank_pred is not None
                # Clear old actual results when new predictions are run
                st.session_state.pop('actual_results', None)
                st.session_state.pop('eval_results', None)
                st.session_state.pop('prob_head_eval', None)

            except Exception as e:
                st.error(f"Prediction error: {e}")
                import traceback
                st.code(traceback.format_exc())

    # Display predictions
    if 'all_predictions' in st.session_state:
        predictions = st.session_state['all_predictions']

        # Always-visible provenance: what actually fed THIS prediction run
        # (race state, stack features, pricing heads), warts and all.
        _render_provenance_panel(st.session_state.get('provenance'))

        tabs = st.tabs(list(predictions.keys()))
        for tab, (label, result) in zip(tabs, predictions.items()):
            with tab:
                cols_to_show = ['predicted_rank', 'rider_name', 'team',
                                'expected_bucket', 'ranking_derived_bucket']
                col_rename = {
                    'predicted_rank': 'Rank',
                    'rider_name': 'Rider',
                    'team': 'Team',
                    'expected_bucket': 'Expected Bucket',
                    'ranking_derived_bucket': 'Predicted Bucket',
                }

                if 'is_contender' in result.columns:
                    cols_to_show.append('is_contender')
                    col_rename['is_contender'] = 'Contender'

                if 'predicted_time_gap' in result.columns:
                    cols_to_show.append('predicted_time_gap')
                    col_rename['predicted_time_gap'] = 'Time Gap (s)'

                # Add cumulative probability columns if available
                has_probs = 'prob_win' in result.columns
                has_lambdarank = 'lambdarank_win_p' in result.columns
                has_blend = (
                    'blend_win_p' in result.columns
                    and result['blend_win_p'].notna().any()
                )
                has_dnf = 'dnf_p' in result.columns and result['dnf_p'].notna().any()

                if has_probs:
                    cols_to_show.extend(['prob_win', 'prob_podium', 'prob_top5', 'prob_top15'])
                    col_rename.update({
                        'prob_win': 'Win %',
                        'prob_podium': 'Podium %',
                        'prob_top5': 'Top 5 %',
                        'prob_top15': 'Top 15 %',
                    })
                if has_lambdarank:
                    cols_to_show.extend(['lambdarank_win_p', 'lambdarank_podium_p'])
                    col_rename.update({
                        'lambdarank_win_p': 'LR Win %',
                        'lambdarank_podium_p': 'LR Podium %',
                    })
                if has_blend:
                    cols_to_show.append('blend_win_p')
                    col_rename['blend_win_p'] = 'Blend Win %'
                if has_dnf:
                    cols_to_show.append('dnf_p')
                    col_rename['dnf_p'] = 'DNF %'

                display = result[cols_to_show].copy().rename(columns=col_rename)
                display['Expected Bucket'] = display['Expected Bucket'].round(2)
                if 'Contender' in display.columns:
                    display['Contender'] = display['Contender'].map({True: 'Yes', False: ''})
                if 'Time Gap (s)' in display.columns:
                    display['Time Gap (s)'] = display['Time Gap (s)'].round(0).astype(int)
                if has_probs:
                    display['Win %'] = (result['prob_win'] * 100).round(1)
                    display['Podium %'] = (result['prob_podium'] * 100).round(1)
                    display['Top 5 %'] = (result['prob_top5'] * 100).round(1)
                    display['Top 15 %'] = (result['prob_top15'] * 100).round(1)
                if has_lambdarank:
                    display['LR Win %'] = (result['lambdarank_win_p'] * 100).round(1)
                    display['LR Podium %'] = (result['lambdarank_podium_p'] * 100).round(1)
                    # Add disagreement marker column (only shown if both heads present)
                    win_gap_pp = (
                        (result['prob_win'] - result['lambdarank_win_p']).abs() * 100
                    )
                    display['Δ Win pp'] = win_gap_pp.round(1)
                if has_blend:
                    display['Blend Win %'] = (
                        result['blend_win_p'].astype(float) * 100
                    ).round(1)
                if has_dnf:
                    display['DNF %'] = (result['dnf_p'].astype(float) * 100).round(1)

                if has_probs and has_lambdarank:
                    # Highlight rows where the two heads disagree materially on win probability.
                    def _highlight_disagreement(row):
                        gap = row.get('Δ Win pp', 0)
                        if isinstance(gap, (int, float)) and gap >= DISAGREEMENT_THRESHOLD_PP:
                            return ['background-color: #fff3cd'] * len(row)
                        return [''] * len(row)
                    styled = display.style.apply(_highlight_disagreement, axis=1)
                    st.caption(
                        f"Rows highlighted where |multiclass Win % − LambdaRank Win %| ≥ "
                        f"{DISAGREEMENT_THRESHOLD_PP}pp."
                    )
                    st.dataframe(styled, hide_index=True, width='stretch')
                else:
                    if has_probs and not has_lambdarank:
                        st.caption(
                            "LambdaRank probability head not installed. "
                            "Run `uv run python -m cycling_project.update_pipeline --only train-lambdarank` to add it."
                        )
                    st.dataframe(display, hide_index=True, width='stretch')

                # DNF-adjusted (honest) prices: the multiclass heads emit
                # P(market | finished); multiplying by P(finish) is the
                # price an actual bet pays on (gate: honest frame
                # market_avg_log_loss -0.0019 all / -0.0076 one-day, 5/5).
                if has_dnf and has_probs:
                    with st.expander("DNF-adjusted (honest) prices"):
                        st.caption(
                            "P(market | finish) × P(finish) from the DNF head. "
                            "Podium/Top 5/Top 15 are multiplied directly, so "
                            "adjusted ≤ unadjusted; the Win market is "
                            "renormalized within the race to preserve the "
                            "total win book, so low-DNF riders can gain."
                        )
                        adj_display = result[
                            ['predicted_rank', 'rider_name', 'team', 'dnf_p',
                             'dnf_adj_win_p', 'dnf_adj_podium_p',
                             'dnf_adj_top5_p', 'dnf_adj_top15_p']
                        ].copy().rename(columns={
                            'predicted_rank': 'Rank',
                            'rider_name': 'Rider',
                            'team': 'Team',
                            'dnf_p': 'DNF %',
                            'dnf_adj_win_p': 'Win % (adj)',
                            'dnf_adj_podium_p': 'Podium % (adj)',
                            'dnf_adj_top5_p': 'Top 5 % (adj)',
                            'dnf_adj_top15_p': 'Top 15 % (adj)',
                        })
                        for c in ('DNF %', 'Win % (adj)', 'Podium % (adj)',
                                  'Top 5 % (adj)', 'Top 15 % (adj)'):
                            adj_display[c] = (
                                adj_display[c].astype(float) * 100
                            ).round(1)
                        st.dataframe(adj_display, hide_index=True, width='stretch')

                # Odds view in expander
                if has_probs:
                    with st.expander("Odds"):
                        odds_format = st.radio(
                            "Format",
                            ["Decimal", "American", "Fractional"],
                            horizontal=True,
                            key=f"odds_fmt_{label}",
                        )

                        id_cols = ['predicted_rank', 'rider_name', 'team']
                        id_rename = {
                            'predicted_rank': 'Rank',
                            'rider_name': 'Rider',
                            'team': 'Team',
                        }
                        if 'is_contender' in result.columns:
                            id_cols.append('is_contender')
                            id_rename['is_contender'] = 'Contender'

                        decimal_cols = ['odds_win', 'odds_podium', 'odds_top5',
                                        'odds_top15', 'odds_top30']
                        market_names = {
                            'odds_win': 'Win',
                            'odds_podium': 'Podium',
                            'odds_top5': 'Top 5',
                            'odds_top15': 'Top 15',
                            'odds_top30': 'Top 30',
                        }

                        available_id = [c for c in id_cols if c in result.columns]
                        available_dec = [c for c in decimal_cols if c in result.columns]
                        odds_display = result[available_id + available_dec].copy()
                        odds_display = odds_display.rename(columns=id_rename)

                        if 'Contender' in odds_display.columns:
                            odds_display['Contender'] = odds_display['Contender'].map({True: 'Yes', False: ''})

                        if odds_format == "Decimal":
                            odds_display = odds_display.rename(columns=market_names)

                        elif odds_format == "American":
                            for col, name in market_names.items():
                                if col in odds_display.columns:
                                    odds_display[name] = odds_display[col].apply(_decimal_to_american)
                                    odds_display = odds_display.drop(columns=[col])

                        elif odds_format == "Fractional":
                            for col, name in market_names.items():
                                if col in odds_display.columns:
                                    odds_display[name] = odds_display[col].apply(_decimal_to_fractional)
                                    odds_display = odds_display.drop(columns=[col])

                        st.dataframe(
                            odds_display,
                            hide_index=True,
                            width='stretch',
                        )

# ── GC Outlook (state-aware final-GC prediction) ─────────────────────────

if (
    'all_predictions' in st.session_state
    and st.session_state.get('gc_outlook') is not None
    and not st.session_state['gc_outlook'].empty
):
    outlook = st.session_state['gc_outlook']
    state_info = st.session_state.get('gc_outlook_state_info') or {}

    k = state_info.get('stages_completed')
    total = state_info.get('total_stages')
    total_txt = (
        f"{total} (est.)"
        if state_info.get('total_stages_estimated') else f"{total}"
    )
    st.subheader(
        f"GC Outlook — after stage {k} of {total_txt}"
        if k else "GC Outlook"
    )
    st.caption(
        "Final-GC probabilities conditioned on the race so far "
        "(reconstructed standings, in-race form, fatigue). The main "
        "prediction tabs above remain pre-race for GC targets. "
        f"{state_info.get('riders_in_standings', '?')} riders in standings"
        + (
            f" — current leader: {state_info['leader_name']}"
            if state_info.get('leader_name') else ""
        )
    )
    if state_info.get('missing_stages') and state_info.get('scrape_failed'):
        st.warning(
            f"Outlook is computed from the first {k} completed stage(s) "
            f"only — stage(s) "
            f"{_fmt_stage_nums(state_info['missing_stages'])} missing "
            f"(DB data through {state_info.get('db_horizon') or 'unknown'}; "
            "scrape pending)."
        )

    def _fmt_gap(seconds):
        if pd.isna(seconds):
            return ''
        s = int(seconds)
        if s >= 3600:
            return f"+{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
        return f"+{s // 60}:{s % 60:02d}"

    display = outlook.head(25).copy()
    display['Gap'] = display['gc_gap_to_leader_s'].apply(_fmt_gap)
    for col in ('gc_outlook_win_p', 'gc_outlook_podium_p',
                'gc_outlook_top5_p', 'gc_outlook_top15_p'):
        display[col] = (display[col] * 100).round(1)
    display = display[[
        'outlook_rank', 'rider_name', 'team', 'gc_rank_current', 'Gap',
        'gc_outlook_win_p', 'gc_outlook_podium_p',
        'gc_outlook_top5_p', 'gc_outlook_top15_p',
    ]].rename(columns={
        'outlook_rank': 'Outlook Rank',
        'rider_name': 'Rider',
        'team': 'Team',
        'gc_rank_current': 'Current GC',
        'gc_outlook_win_p': 'Win %',
        'gc_outlook_podium_p': 'Podium %',
        'gc_outlook_top5_p': 'Top 5 %',
        'gc_outlook_top15_p': 'Top 15 %',
    })
    st.dataframe(display, hide_index=True, width='stretch')


# ── Step 4: Compare with Actual Results ──────────────────────────────────

if 'all_predictions' in st.session_state and 'fc_race_id' in st.session_state:
    st.header("4. Compare with Actual Results")

    fc_race_id = st.session_state['fc_race_id']
    race_year = st.session_state['race_year']

    # ── 4a. Stage detection & selection (local DB/cache first; the live
    #        race page is fetched only when the edition has no local stages) ──
    if 'race_stages' not in st.session_state:
        with st.spinner("Checking for stages..."):
            is_stage_race, stages = enumerate_edition_stages(fc_race_id, race_year)
        st.session_state['race_stages'] = (is_stage_race, stages)
    else:
        is_stage_race, stages = st.session_state['race_stages']

    selected_stage_id = None
    selected_stage_param = None
    selected_stage_number = None
    selected_comp_type = None

    if is_stage_race and stages:
        stage_names = [s['name'] for s in stages]
        selected_stage_name = st.selectbox("Select stage to compare", stage_names)
        selected_stage = next(s for s in stages if s['name'] == selected_stage_name)
        selected_stage_id = selected_stage['url_param']
        selected_stage_param = selected_stage['url_param']
        selected_stage_number = selected_stage.get('stage_number')
        selected_comp_type = selected_stage.get('competition_type')

        if any(s.get('source') in ('db', 'cache') for s in stages):
            cap_col, refresh_col = st.columns([3, 1])
            with cap_col:
                st.caption(
                    "Stage list from local data (DB / results cache) — "
                    "no live fetch."
                )
            with refresh_col:
                if st.button("Refresh from FirstCycling"):
                    with st.spinner("Fetching live stage list..."):
                        live_ok, live_stages = enumerate_edition_stages(
                            fc_race_id, race_year, prefer_live=True
                        )
                    if live_stages and any(
                        s.get('source') == 'live' for s in live_stages
                    ):
                        st.session_state['race_stages'] = (live_ok, live_stages)
                        st.rerun()
                    else:
                        st.warning(
                            "Live stage list unavailable — keeping local list."
                        )

    # ── 4b. Fetch results ──
    col1, col2 = st.columns([3, 1])
    with col1:
        force_refresh_results = st.checkbox("Force re-scrape results", value=False)
    with col2:
        get_results_btn = st.button("Get Actual Results", type="primary")

    if get_results_btn:
        with st.spinner("Loading actual results..."):
            actual_df, winning_time = scrape_or_load_results(
                fc_race_id, race_year,
                stage_id=selected_stage_id,
                stage_url_param=selected_stage_param,
                force_refresh=force_refresh_results,
                stage_number=selected_stage_number,
                competition_type=selected_comp_type,
            )
        if actual_df is not None and not actual_df.empty:
            st.session_state['actual_results'] = actual_df
            st.session_state['winning_time'] = winning_time
            # Clear old eval results
            st.session_state.pop('eval_results', None)
            st.session_state.pop('prob_head_eval', None)
        else:
            st.warning("No results found. The race may not have been completed yet.")

    if 'actual_results' in st.session_state:
        actual_df = st.session_state['actual_results']

        # ── 4c. Actual results display ──
        st.subheader("Actual Race Results")
        actual_display_cols = ['place', 'rider_name']
        actual_rename = {'place': 'Place', 'rider_name': 'Rider'}
        if 'team_name' in actual_df.columns:
            actual_display_cols.append('team_name')
            actual_rename['team_name'] = 'Team'
        if 'time_gap' in actual_df.columns:
            actual_display_cols.append('time_gap')
            actual_rename['time_gap'] = 'Time Gap (s)'
        if 'place_bucket' in actual_df.columns:
            actual_display_cols.append('place_bucket')
            actual_rename['place_bucket'] = 'Bucket'

        available_cols = [c for c in actual_display_cols if c in actual_df.columns]
        actual_show = actual_df[available_cols].copy().rename(
            columns={k: v for k, v in actual_rename.items() if k in available_cols}
        )
        st.dataframe(actual_show, hide_index=True, width='stretch')

        # ── 4d. Side-by-side comparison ──
        predictions = st.session_state['all_predictions']
        st.subheader("Predicted vs Actual")

        pred_tabs = st.tabs(list(predictions.keys()))
        for tab, (label, pred_result) in zip(pred_tabs, predictions.items()):
            with tab:
                if 'rider_id' in pred_result.columns and 'rider_id' in actual_df.columns:
                    merged = pred_result.merge(
                        actual_df[['rider_id', 'place', 'time_gap', 'place_bucket']].dropna(subset=['rider_id']).rename(
                            columns={
                                'place': 'actual_place',
                                'time_gap': 'actual_gap',
                                'place_bucket': 'actual_bucket',
                            }
                        ),
                        on='rider_id',
                        how='inner',
                    ).sort_values('predicted_rank')

                    if not merged.empty:
                        compare_cols = ['predicted_rank', 'rider_name', 'team',
                                        'ranking_derived_bucket', 'actual_place',
                                        'actual_bucket']
                        compare_rename = {
                            'predicted_rank': 'Pred Rank',
                            'rider_name': 'Rider',
                            'team': 'Team',
                            'ranking_derived_bucket': 'Pred Bucket',
                            'actual_place': 'Actual Place',
                            'actual_bucket': 'Actual Bucket',
                        }
                        if 'predicted_time_gap' in merged.columns:
                            compare_cols.append('predicted_time_gap')
                            compare_rename['predicted_time_gap'] = 'Pred Gap (s)'
                        if 'actual_gap' in merged.columns:
                            compare_cols.append('actual_gap')
                            compare_rename['actual_gap'] = 'Actual Gap (s)'

                        avail = [c for c in compare_cols if c in merged.columns]
                        compare_display = merged[avail].copy().rename(
                            columns={k: v for k, v in compare_rename.items() if k in avail}
                        )
                        for col in ['Pred Bucket', 'Actual Bucket']:
                            if col in compare_display.columns:
                                compare_display[col] = compare_display[col].apply(
                                    lambda v: int(v) if pd.notna(v) else ''
                                )
                        if 'Pred Gap (s)' in compare_display.columns:
                            compare_display['Pred Gap (s)'] = compare_display['Pred Gap (s)'].apply(
                                lambda v: f"{v:.0f}" if pd.notna(v) else ''
                            )
                        if 'Actual Gap (s)' in compare_display.columns:
                            compare_display['Actual Gap (s)'] = compare_display['Actual Gap (s)'].apply(
                                lambda v: f"{v:.0f}" if pd.notna(v) and isinstance(v, (int, float)) else str(v) if pd.notna(v) else ''
                            )
                        st.dataframe(compare_display, hide_index=True, width='stretch')
                    else:
                        st.info("No riders matched between predictions and actual results.")
                else:
                    st.info("Cannot compare — missing rider IDs.")

        # ── 4e. Prediction accuracy metrics ──
        st.subheader("Prediction Accuracy")

        if 'eval_results' not in st.session_state:
            eval_results = evaluate_predictions_against_actual(
                predictions, actual_df
            )
            st.session_state['eval_results'] = eval_results

        eval_results = st.session_state['eval_results']

        if eval_results:
            # Summary table
            summary_rows = []
            for label, metrics in eval_results.items():
                row = {'Prediction': label, 'Riders Matched': metrics.get('n_matched', 0)}
                if 'ranking' in metrics:
                    row['Kendall Tau'] = f"{metrics['ranking']['kendall_tau']:.3f}"
                    row['Top-3 Precision'] = f"{metrics['ranking']['top3_precision']:.1%}"
                    row['Top-5 Precision'] = f"{metrics['ranking']['top5_precision']:.1%}"
                if 'bucket' in metrics:
                    row['Bucket MAE'] = f"{metrics['bucket']['mae']:.2f}"
                    row['Bucket Accuracy'] = f"{metrics['bucket']['accuracy']:.1%}"
                    row['Within-1'] = f"{metrics['bucket']['within_1']:.1%}"
                if 'time_gap' in metrics:
                    row['TG MAE (s)'] = f"{metrics['time_gap']['mae']:.0f}"
                # Mark best predictions
                best_for = metrics.get('best_for', [])
                if best_for:
                    row['Best For'] = ', '.join(best_for)
                summary_rows.append(row)

            if summary_rows:
                summary_df = pd.DataFrame(summary_rows)
                st.dataframe(summary_df, hide_index=True, width='stretch')

            # Detailed metrics per prediction
            with st.expander("Detailed Metrics"):
                for label, metrics in eval_results.items():
                    st.markdown(f"**{label}**")
                    detail_cols = st.columns(3)
                    with detail_cols[0]:
                        if 'bucket' in metrics:
                            st.caption("Bucket Metrics")
                            for k, v in metrics['bucket'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.3f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    with detail_cols[1]:
                        if 'ranking' in metrics:
                            st.caption("Ranking Metrics")
                            for k, v in metrics['ranking'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.3f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    with detail_cols[2]:
                        if 'time_gap' in metrics:
                            st.caption("Time Gap Metrics")
                            for k, v in metrics['time_gap'].items():
                                if isinstance(v, float):
                                    st.text(f"  {k}: {v:.1f}")
                                else:
                                    st.text(f"  {k}: {v}")
                    st.divider()

        # ── 4e-bis. Probability head comparison ──
        # Per-prediction, score both probability heads (multiclass cascade
        # vs LambdaRank) against the actual results. Answers the question
        # "which probability head was more accurate on THIS race?"
        st.subheader("Probability Head Comparison")
        st.caption(
            "Compares the multiclass cascade's probabilities (Win %, Podium %) "
            "against the full-field LambdaRank head (LR Win %, LR Podium %) on "
            "this specific race. Lower log loss and Brier = better; winner "
            "predicted rank = where the actual winner fell on each head's "
            "sorted list of riders."
        )

        if 'prob_head_eval' not in st.session_state:
            st.session_state['prob_head_eval'] = (
                evaluate_probability_heads_against_actual(predictions, actual_df)
            )
        prob_head_eval = st.session_state['prob_head_eval']

        if not prob_head_eval:
            st.info(
                "No probability head metrics available. Either predictions "
                "don't include both heads, or no riders matched the actual results."
            )
        else:
            # Flat summary table: one row per (prediction, head) with key metrics.
            rows = []
            for label, heads in prob_head_eval.items():
                for head_name, head in heads.items():
                    if head is None:
                        continue
                    pretty_head = {
                        'multiclass': 'Multiclass cascade',
                        'lambdarank': 'LambdaRank softmax',
                    }.get(head_name, head_name)
                    rows.append({
                        'Prediction': label,
                        'Head': pretty_head,
                        'Winner log loss': f"{head['winner_log_loss']:.3f}"
                            if pd.notna(head['winner_log_loss']) else '—',
                        'Winner Brier': f"{head['winner_brier']:.4f}",
                        'Winner rank': (
                            f"#{head['winner_predicted_rank']}"
                            if head['winner_predicted_rank'] is not None else '—'
                        ),
                        'Winner p %': (
                            f"{head['winner_predicted_p'] * 100:.1f}%"
                            if pd.notna(head['winner_predicted_p']) else '—'
                        ),
                        'Podium log loss': f"{head['podium_log_loss']:.3f}"
                            if pd.notna(head['podium_log_loss']) else '—',
                        'Podium Brier': f"{head['podium_brier']:.4f}",
                        'Top-3 overlap': f"{head['top3_overlap']}/3",
                    })
            if rows:
                head_summary_df = pd.DataFrame(rows)
                st.dataframe(head_summary_df, hide_index=True, width='stretch')

                # Surface who wins the head-to-head on the averaged prediction,
                # since that's the single-number summary most users look at.
                avg_label = 'Averaged Reference Races'
                if avg_label in prob_head_eval:
                    avg = prob_head_eval[avg_label]
                    mc = avg.get('multiclass')
                    lr = avg.get('lambdarank')
                    if mc and lr:
                        winner_rank_mc = mc['winner_predicted_rank']
                        winner_rank_lr = lr['winner_predicted_rank']
                        winner_p_mc = mc['winner_predicted_p'] * 100
                        winner_p_lr = lr['winner_predicted_p'] * 100

                        # Pick a narrative based on whichever rank was better.
                        if winner_rank_mc is not None and winner_rank_lr is not None:
                            if winner_rank_mc < winner_rank_lr:
                                verdict = (
                                    f"On the averaged prediction, the **multiclass cascade** "
                                    f"was more confident on the actual winner "
                                    f"(ranked #{winner_rank_mc} at {winner_p_mc:.1f}% "
                                    f"vs LambdaRank #{winner_rank_lr} at {winner_p_lr:.1f}%)."
                                )
                            elif winner_rank_lr < winner_rank_mc:
                                verdict = (
                                    f"On the averaged prediction, the **LambdaRank head** "
                                    f"was more confident on the actual winner "
                                    f"(ranked #{winner_rank_lr} at {winner_p_lr:.1f}% "
                                    f"vs multiclass #{winner_rank_mc} at {winner_p_mc:.1f}%)."
                                )
                            else:
                                verdict = (
                                    f"Both heads ranked the actual winner at "
                                    f"#{winner_rank_mc} on the averaged prediction "
                                    f"(multiclass: {winner_p_mc:.1f}%, LambdaRank: {winner_p_lr:.1f}%)."
                                )
                            st.info(verdict)

                with st.expander("What do these numbers mean?"):
                    st.markdown("""
- **Winner log loss**: `-log(p)` where `p` is the probability that head
  assigned to the actual winner. Lower is better. A perfectly confident
  head (`p = 1.0`) scores 0; a head that gave the winner a 10% chance
  scores 2.30; 5% scores 3.00.
- **Winner Brier**: mean squared error between the binary winner
  indicator and the probability assigned to each rider. Lower is
  better. A head that assigned 1.0 to the winner and 0.0 to everyone
  else would score 0.
- **Winner rank**: where the actual winner finished on each head's
  sorted list of riders (sorted by predicted win probability, highest
  first). #1 means the head correctly identified the winner.
- **Winner p %**: the head's predicted win probability for the actual
  winner. Useful for spotting cases where the model was right about
  *who* would win but unsure (low p) vs confidently right (high p).
- **Podium log loss / Brier**: same idea but for the three actual
  podium finishers and each head's podium probability column.
- **Top-3 overlap**: how many of each head's top-3-by-win-prob were
  in the actual top 3. 0/3 means no overlap; 3/3 means a clean sweep.
                    """)
            else:
                st.info("No comparable probability output on these predictions.")

        # ── 4f. Race characteristics comparison ──
        winning_time = st.session_state.get('winning_time')
        if winning_time and actual_df is not None:
            actual_chars = compute_characteristics_from_results(actual_df, winning_time)

            if actual_chars:
                st.subheader("Race Characteristics Comparison")

                # Compute profile scores for actual race
                actual_profile = compute_profile_scores_from_results(actual_df, winning_time)

                # Get reference characteristics + profile scores
                ref_chars_list = []
                selected_refs = st.session_state.get('selected_refs', {})
                for comp_id, ref_info in selected_refs.items():
                    chars = get_race_finishing_characteristics(comp_id)
                    if chars:
                        chars['label'] = ref_info.get('display_name', str(comp_id))
                        # Attach profile scores from selected_refs
                        for pkey in ['race_sprint_score', 'race_mountain_score',
                                     'race_hilly_score', 'race_rolling_score',
                                     'race_breakaway_score', 'race_time_trial_score',
                                     'race_dominant_profile']:
                            chars[pkey] = ref_info.get(pkey)
                        ref_chars_list.append(chars)

                # Add averaged profile characteristics if available
                if len(ref_chars_list) > 1:
                    avg_chars = {}
                    for key in actual_chars:
                        vals = [c[key] for c in ref_chars_list if c.get(key) is not None]
                        avg_chars[key] = sum(vals) / len(vals) if vals else 0
                    # Average profile scores too
                    for pkey in ['race_sprint_score', 'race_mountain_score',
                                 'race_hilly_score', 'race_rolling_score',
                                 'race_breakaway_score', 'race_time_trial_score']:
                        vals = [c[pkey] for c in ref_chars_list
                                if c.get(pkey) is not None]
                        avg_chars[pkey] = sum(vals) / len(vals) if vals else 0
                    avg_chars['label'] = 'Averaged Reference Races'
                    ref_chars_list.append(avg_chars)

                if ref_chars_list:
                    comparison_df = compare_race_characteristics(actual_chars, ref_chars_list)

                    if not comparison_df.empty:
                        # Highlight most similar
                        most_similar_row = comparison_df[comparison_df['most_similar']].iloc[0]
                        st.success(
                            f"Most similar reference race: **{most_similar_row['label']}** "
                            f"(similarity: {most_similar_row['similarity']:.3f})"
                        )

                        # Best prediction callout
                        if eval_results:
                            best_ranking_labels = [
                                l for l, m in eval_results.items()
                                if 'ranking' in (m.get('best_for') or [])
                            ]
                            if best_ranking_labels:
                                st.info(f"Best ranking prediction: **{best_ranking_labels[0]}**")

                        # Comparison table
                        with st.expander("Characteristic Details"):
                            # Build a comparison table: actual vs each reference
                            display_metrics = [
                                'biggest_group_metric', 'time_gap_evenness_metric',
                                'clumpiness_score', 'selection_metric',
                                'total_race_duration', 'gini_coefficient',
                            ]
                            comp_rows = [{'Metric': m, 'Actual': f"{actual_chars.get(m, 0):.3f}"}
                                         for m in display_metrics]
                            for ref in ref_chars_list:
                                label = ref.get('label', '')[:25]
                                for i, m in enumerate(display_metrics):
                                    comp_rows[i][label] = f"{ref.get(m, 0):.3f}" if ref.get(m) is not None else ''

                            # Add profile scores section
                            profile_keys = [
                                ('race_sprint_score', 'Sprint'),
                                ('race_mountain_score', 'Mountain'),
                                ('race_hilly_score', 'Hilly'),
                                ('race_rolling_score', 'Rolling'),
                                ('race_breakaway_score', 'Breakaway'),
                                ('race_time_trial_score', 'TT'),
                            ]
                            for pkey, plabel in profile_keys:
                                row = {'Metric': plabel}
                                if actual_profile:
                                    # Map race_sprint_score -> sprint
                                    score_key = pkey.replace('race_', '').replace('_score', '')
                                    row['Actual'] = f"{actual_profile.get(score_key, 0):.3f}"
                                else:
                                    row['Actual'] = ''
                                for ref in ref_chars_list:
                                    label = ref.get('label', '')[:25]
                                    val = ref.get(pkey)
                                    row[label] = f"{val:.3f}" if val is not None else ''
                                comp_rows.append(row)

                            # Add dominant profile row
                            dom_row = {'Metric': 'Dominant Profile'}
                            dom_row['Actual'] = actual_profile.get('dominant_profile', '') if actual_profile else ''
                            for ref in ref_chars_list:
                                label = ref.get('label', '')[:25]
                                dom_row[label] = ref.get('race_dominant_profile', '')
                            comp_rows.append(dom_row)

                            comp_table = pd.DataFrame(comp_rows)
                            st.dataframe(comp_table, hide_index=True, width='stretch')

                            # Similarity scores table
                            sim_display = comparison_df[['label', 'similarity', 'distance']].copy()
                            sim_display.columns = ['Reference Race', 'Similarity', 'Distance']
                            sim_display['Similarity'] = sim_display['Similarity'].apply(lambda v: f"{v:.3f}")
                            sim_display['Distance'] = sim_display['Distance'].apply(lambda v: f"{v:.3f}")
                            st.dataframe(sim_display, hide_index=True, width='stretch')
