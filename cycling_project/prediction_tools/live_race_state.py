"""
Live stage-race state for inference.

Computes the within-race state block (the rider_race_state feature columns)
for an ONGOING stage race at prediction time, from the stages completed so
far. Training-side state rows are built by
``engineering_tools.stage_race_state`` from migrated results; this module
feeds the SAME ``compute_race_state`` function, so a model trained with
``include_race_state`` sees identical feature semantics live.

Completed-stage data is loaded LOCAL-FIRST, per stage:

1. the main DB (``competitions`` + ``rider_results`` for this edition —
   stages the weekly pipeline already migrated),
2. ``cached_race_results`` (stages fetched by a previous app session),
3. a live scrape (``future_race_loader.scrape_or_load_results``) only for
   stages not available locally.

The stage list itself is likewise assembled from the edition's DB
competitions + cache rows, enriched (not gated) by the live race page.
Scrape failures are NON-FATAL: state is built from whatever contiguous
prefix of stages is available, and the returned ``info`` dict says exactly
which stages are missing and why (``missing_stages``, ``scrape_failed``,
``db_horizon``, per-source breakdown in ``sources``) so the UI can attach
state honestly instead of silently falling back to pre-race features.
Before 2026-06 this module required a live page fetch to enumerate stages,
so a Cloudflare block produced "no stage list found" even with every
completed stage already migrated in the DB.

Used by web/app.py Step 3: real state is attached only when the prediction
target is stage 2+ of a stage race — matching training, where only
competition_type='stage' rows carry state. Every other target (stage 1,
one-day, races without completed results yet) gets the state columns
as NaN, which feature_engineering imputes to the same neutral defaults
used for missing state in training. GC targets of in-progress stage races
get state too — it feeds the separate GC outlook head, not the main models.

``enumerate_edition_stages`` reuses the same local stage inventory for the
web app's Step-4 "compare with actual results" dropdown, so that selector
also works without a live page fetch.

Known v1 limitation: stage dates aren't available from the live results
path, so ``is_post_rest_day`` is always 0 for live state (it is populated
correctly in training data).
"""

import re
import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.engineering_tools.stage_race_state import (
    STATE_FEATURE_COLUMNS,
    compute_race_state,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

# Sentinel competition_id for the "after the last completed stage"
# checkpoint produced by compute_race_state.
_VIRTUAL_GC_ID = -1

# Dropdown entries that are classification tabs, not stages.
_NON_STAGE_RE = re.compile(
    r'\b(gc|general|points|mountain|youth|teams?)\b', re.IGNORECASE
)


def _parse_stage_number(name: str, value: str, position: int) -> int:
    """Best-effort stage number from a FirstCycling stage-dropdown entry."""
    for candidate in (value, name):
        if not candidate:
            continue
        if re.fullmatch(r'\s*prologue\s*', str(candidate), re.IGNORECASE):
            return 0
        m = re.search(r'(\d+)', str(candidate))
        if m:
            return int(m.group(1))
    return position


def list_race_stages(fc_race_id: int, year: int) -> List[Dict]:
    """
    Enumerate the current edition's stages from the live race page.

    Returns [{'stage_number': int, 'name': str, 'url_param': str}, ...] in
    page order, or [] for one-day races / fetch failures.
    """
    from cycling_project.prediction_tools.future_race_loader import (
        detect_race_stages,
    )
    is_stage_race, raw = detect_race_stages(fc_race_id, year)
    if not is_stage_race or not raw:
        return []
    stages = []
    position = 0
    for entry in raw:
        name = (entry.get('name') or '').strip()
        value = entry.get('url_param')
        if not value or _NON_STAGE_RE.search(name):
            continue
        position += 1
        stages.append({
            'stage_number': _parse_stage_number(name, value, position),
            'name': name,
            'url_param': str(value),
        })
    return stages


# ---------------------------------------------------------------------------
# Local (DB + cache) edition inventory — no network
# ---------------------------------------------------------------------------

_STAGE_URL_PARAM_RE = re.compile(r'[?&]e=([^&]+)')


def _resolve_db_path(db_path: Optional[str]) -> str:
    from cycling_project.prediction_tools.future_race_loader import _DEFAULT_DB
    return db_path or str(_DEFAULT_DB)


def _db_edition_stages(
    fc_race_id: int, year: int, db_path: str
) -> Dict[int, Dict]:
    """
    Stage competitions of THIS edition already migrated into the main DB.

    Returns {stage_number: {'competition_id', 'winning_time', 'url_param',
    'n_results'}} for stages that have results. ``url_param`` is mined from
    the stored competition URL (…&e=N) when present.
    """
    query = """
    SELECT c.id, c.stage_number, c.winning_time, c.url, COUNT(rr.id) AS n_res
    FROM races r
    JOIN competitions c ON c.race_id = r.id AND c.competition_type = 'stage'
    LEFT JOIN rider_results rr ON rr.competition_id = c.id
    WHERE r.fc_race_id = ? AND r.year = ? AND c.stage_number IS NOT NULL
    GROUP BY c.id
    ORDER BY c.stage_number, n_res DESC
    """
    out: Dict[int, Dict] = {}
    with sqlite3.connect(db_path) as conn:
        for comp_id, stage_num, wt, url, n_res in conn.execute(
            query, (str(fc_race_id), int(year))
        ):
            stage_num = int(stage_num)
            if n_res <= 0 or stage_num in out:
                continue
            m = _STAGE_URL_PARAM_RE.search(url or '')
            out[stage_num] = {
                'competition_id': int(comp_id),
                'winning_time': wt,
                'url_param': m.group(1) if m else None,
                'n_results': int(n_res),
            }
    return out


def _cached_edition_stage_ids(
    fc_race_id: int, year: int, db_path: str
) -> Dict[int, str]:
    """{stage_number: cached stage_id} from cached_race_results."""
    out: Dict[int, str] = {}
    with sqlite3.connect(db_path) as conn:
        try:
            rows = conn.execute(
                "SELECT DISTINCT stage_id FROM cached_race_results "
                "WHERE fc_race_id = ? AND year = ? AND stage_id IS NOT NULL",
                (str(fc_race_id), int(year)),
            ).fetchall()
        except sqlite3.OperationalError:  # cache table not created yet
            return out
    for (stage_id,) in rows:
        num = _parse_stage_number('', str(stage_id), -1)
        if num >= 0 and num not in out:
            out[num] = str(stage_id)
    return out


def _db_edition_has_gc(fc_race_id: int, year: int, db_path: str) -> bool:
    """True when this edition has a migrated GC competition with results."""
    query = """
    SELECT 1 FROM races r
    JOIN competitions c ON c.race_id = r.id AND c.competition_type = 'gc'
    JOIN rider_results rr ON rr.competition_id = c.id
    WHERE r.fc_race_id = ? AND r.year = ?
    LIMIT 1
    """
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(query, (str(fc_race_id), int(year))).fetchone()
    return row is not None


def _db_is_stage_race(fc_race_id: int, db_path: str) -> Optional[bool]:
    """races.is_stage_race of the most recent edition; None when unknown."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT is_stage_race FROM races "
            "WHERE fc_race_id = ? ORDER BY year DESC LIMIT 1",
            (str(fc_race_id),),
        ).fetchone()
    return None if row is None else bool(row[0])


# The live race page's stage selector names its GC tab like this (its url
# value is '0' — see tests/fixtures race_detail.html).
_GC_NAME_RE = re.compile(
    r'^\s*(gc|general(\s+classification)?)\s*$', re.IGNORECASE
)


def _annotate_live_stage_entries(raw: List[Dict]) -> List[Dict]:
    """Step-4 entry dicts from raw ``detect_race_stages`` output.

    ``competition_type``/``stage_number`` are set only when unambiguous (a
    plain numeric url value, or a GC-named entry) so the main-DB
    short-circuit in ``scrape_or_load_results`` can never serve the wrong
    competition; everything else keeps None and loads cache-first, then
    scrapes, exactly as before.
    """
    entries: List[Dict] = []
    for entry in raw:
        name = (entry.get('name') or '').strip()
        value = entry.get('url_param')
        if value is None:
            continue
        value = str(value)
        if _GC_NAME_RE.match(name):
            comp_type, stage_num = 'gc', None
        elif _NON_STAGE_RE.search(name):
            comp_type, stage_num = None, None  # points/youth/teams tabs
        elif value.isdigit():
            comp_type, stage_num = 'stage', int(value)
        else:
            comp_type, stage_num = None, None  # split stages ('7a') etc.
        entries.append({
            'stage_number': stage_num,
            'name': name,
            'url_param': value,
            'competition_type': comp_type,
            'source': 'live',
        })
    return entries


def enumerate_edition_stages(
    fc_race_id: int,
    year: int,
    db_path: Optional[str] = None,
    prefer_live: bool = False,
) -> Tuple[bool, List[Dict]]:
    """
    Stage-selector entries for one edition, local-first (web/app.py Step 4).

    The edition's migrated stage competitions and ``cached_race_results``
    rows are merged into dropdown entries without touching the network; the
    live race page is fetched only when the edition has no local stage data
    (or ``prefer_live`` asks for a refresh), so an unreachable FirstCycling
    still yields a stage selector for races already in the DB. Known
    one-day races (``races.is_stage_race`` = 0) skip the fetch entirely.

    Returns ``(is_stage_race, entries)``; each entry carries
    ``stage_number``, ``name``, ``url_param``, ``competition_type`` and
    ``source`` ('db' | 'cache' | 'live'). A 'GC' entry is included when the
    edition's GC standings are migrated, or cached under the live page's
    GC url value '0' — mirroring the live selector. When a live fetch
    fails but local data exists, the local list is returned.
    """
    db_path = _resolve_db_path(db_path)

    db_stages = _db_edition_stages(fc_race_id, year, db_path)
    cached_ids = _cached_edition_stage_ids(fc_race_id, year, db_path)

    entries: List[Dict] = []
    # A cached stage_id of '0' is the live selector's GC tab, not a
    # prologue — unless the DB knows a stage-0 competition for the edition.
    stage_nums = set(db_stages) | {
        n for n in cached_ids if n > 0 or n in db_stages
    }
    for num in sorted(stage_nums):
        db_entry = db_stages.get(num)
        cache_id = cached_ids.get(num)
        url_param = (
            (db_entry or {}).get('url_param')
            or (str(cache_id) if cache_id is not None else None)
            or str(num)
        )
        entries.append({
            'stage_number': num,
            'name': 'Prologue' if num == 0 else f'Stage {num}',
            'url_param': url_param,
            'competition_type': 'stage',
            'source': 'db' if db_entry else 'cache',
        })
    if _db_edition_has_gc(fc_race_id, year, db_path):
        entries.append({
            'stage_number': None,
            'name': 'GC',
            'url_param': '0',
            'competition_type': 'gc',
            'source': 'db',
        })
    elif 0 in cached_ids and 0 not in db_stages:
        entries.append({
            'stage_number': None,
            'name': 'GC',
            'url_param': str(cached_ids[0]),
            'competition_type': 'gc',
            'source': 'cache',
        })

    if entries and not prefer_live:
        return True, entries
    if (
        not entries
        and not prefer_live
        and _db_is_stage_race(fc_race_id, db_path) is False
    ):
        return False, []

    from cycling_project.prediction_tools.future_race_loader import (
        detect_race_stages,
    )
    is_live_stage_race, raw = detect_race_stages(fc_race_id, year)
    if is_live_stage_race and raw:
        return True, _annotate_live_stage_entries(raw)
    return bool(entries), entries


def _prior_edition_stage_count(
    fc_race_id: int, year: int, db_path: str
) -> Optional[int]:
    """Stage count of the most recent earlier edition (total_stages proxy)."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(c.id) FROM races r
            JOIN competitions c ON c.race_id = r.id
                AND c.competition_type = 'stage'
            WHERE r.fc_race_id = ? AND r.year = (
                SELECT MAX(r2.year) FROM races r2
                JOIN competitions c2 ON c2.race_id = r2.id
                    AND c2.competition_type = 'stage'
                WHERE r2.fc_race_id = ? AND r2.year < ?
            )
            """,
            (str(fc_race_id), str(fc_race_id), int(year)),
        ).fetchone()
    return int(row[0]) if row and row[0] else None


def _db_data_horizon(db_path: str) -> Optional[str]:
    """Latest competition date in the DB — 'data current through' marker."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT MAX(date) FROM competitions").fetchone()
    return row[0] if row and row[0] else None


def _load_db_stage_results(
    competition_id: int, db_path: str
) -> Optional[pd.DataFrame]:
    """Migrated stage results in build_live_state's input shape."""
    query = """
    SELECT rr.rider_id,
           rd.fc_rider_id AS rider_fc_id,
           rd.name AS rider_name,
           t.name AS team_name,
           rr.place, rr.time_gap, rr.place_bucket, rr.percentile
    FROM rider_results rr
    JOIN riders rd ON rr.rider_id = rd.id
    LEFT JOIN teams t ON rr.team_id = t.id
    WHERE rr.competition_id = ?
    ORDER BY rr.place
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(int(competition_id),))
    return df if not df.empty else None


def build_live_state(
    completed: List[Dict],
    total_stages: int,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """
    Build the state block from already-fetched stage results.

    Args:
        completed: [{'seq': int, 'winning_time': float|None,
                     'results': DataFrame[rider_fc_id, rider_id, rider_name,
                                          team_name, place, time_gap,
                                          place_bucket]}]
            in racing order. 'rider_id' is the DB id (NaN for riders not
            matched to the DB — they still count toward standings).
        total_stages: scheduled stage count (pct_race_complete denominator).

    Returns:
        (state_df, info) where state_df has rider_id (DB id) +
        STATE_FEATURE_COLUMNS for riders matched to the DB, or None when no
        usable state exists.
    """
    info: Dict = {
        'available': False,
        'stages_completed': 0,
        'total_stages': total_stages,
        'riders_in_standings': 0,
        'leader_name': None,
        'reason': None,
    }
    completed = [
        c for c in completed
        if c.get('results') is not None and len(c['results']) > 0
    ]
    if not completed:
        info['reason'] = 'no completed stage results'
        return None, info

    # Key standings by rider_fc_id so unmatched riders still occupy GC
    # positions; map back to DB rider_id at the end.
    fc_to_key: Dict[str, int] = {}
    key_to_db: Dict[int, Optional[int]] = {}
    key_to_name: Dict[int, str] = {}

    def _key_for(fc_id, db_id, name) -> int:
        fc = str(fc_id)
        if fc not in fc_to_key:
            fc_to_key[fc] = len(fc_to_key) + 1
            key_to_db[fc_to_key[fc]] = (
                int(db_id) if pd.notna(db_id) else None
            )
            key_to_name[fc_to_key[fc]] = name
        return fc_to_key[fc]

    stage_rows = []
    result_rows = []
    team_codes: Dict[str, int] = {}
    for c in completed:
        seq = int(c['seq'])
        stage_rows.append({
            'competition_id': seq,
            'stage_number': seq,
            'date': None,
            'winning_time': c.get('winning_time'),
        })
        res = c['results']
        n_finishers = len(res)
        for _, r in res.iterrows():
            place = r.get('place')
            if pd.isna(place):
                continue
            place = int(place)
            team_name = r.get('team_name') or None
            if team_name and team_name not in team_codes:
                team_codes[team_name] = len(team_codes) + 1
            bucket = r.get('place_bucket')
            if pd.isna(bucket):
                bucket = _place_bucket(place)
            # DB-sourced rows carry the migration-time percentile (what
            # training saw); cache/scrape rows don't have one, so compute
            # the same formula over the rows with a place.
            pctile = r.get('percentile')
            if pd.isna(pctile):
                pctile = 100.0 * (n_finishers - place + 1) / n_finishers
            result_rows.append({
                'competition_id': seq,
                'rider_id': _key_for(
                    r.get('rider_fc_id'), r.get('rider_id'),
                    r.get('rider_name'),
                ),
                'team_id': team_codes.get(team_name),
                'place': place,
                'time_gap': r.get('time_gap'),
                'place_bucket': bucket,
                'percentile': float(pctile),
            })

    state, quality = compute_race_state(
        pd.DataFrame(stage_rows),
        pd.DataFrame(result_rows),
        gc_competition_id=_VIRTUAL_GC_ID,
        total_stages=total_stages,
    )
    if quality.get('truncated_at_seq') is not None:
        info['reason'] = (
            f"state truncated at stage {quality['truncated_at_seq']} "
            "(missing winning time or results)"
        )
        return None, info

    current = state[state['competition_id'] == _VIRTUAL_GC_ID]
    if current.empty:
        info['reason'] = 'no riders with complete stage coverage'
        return None, info

    info['stages_completed'] = int(current['stages_completed'].iloc[0])
    info['riders_in_standings'] = len(current)
    leader = current.loc[current['is_race_leader'] == 1, 'rider_id']
    if not leader.empty:
        info['leader_name'] = key_to_name.get(int(leader.iloc[0]))

    out = current[['rider_id'] + STATE_FEATURE_COLUMNS].copy()
    out['rider_id'] = out['rider_id'].map(key_to_db)
    out = out.dropna(subset=['rider_id'])
    out['rider_id'] = out['rider_id'].astype(int)
    info['available'] = True
    return out.reset_index(drop=True), info


def _plain_numeral_params(stages_by_num: Dict[int, Dict]) -> bool:
    """True when every known stage identifier is just its stage number.

    Guards url_param guessing for stages we have no identifier for: if any
    known param deviates (prologue, split stages), guessing str(n) could
    fetch the WRONG stage's results, so we don't.
    """
    for num, entry in stages_by_num.items():
        for key in ('url_param', 'cache_stage_id'):
            value = entry.get(key)
            if value is not None and str(value).strip() != str(num):
                return False
    return True


def fetch_live_race_state(
    fc_race_id: int,
    year: int,
    target_stage_number: Optional[int] = None,
    force_refresh: bool = False,
    db_path: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """
    Load completed-stage results for an ongoing race and compute state.

    Local-first: per stage, the main DB (migrated results) is checked, then
    cached_race_results, then a live scrape — so state attaches even when
    scraping is unavailable, as long as completed stages are in the DB.
    Stages feed the state in racing order and must be contiguous from the
    first; the first unavailable stage stops the reconstruction (a gap would
    corrupt cumulative GC time) and is reported in ``info``.

    Args:
        target_stage_number: the stage being predicted; only stages with a
            lower number feed the state (strictly-before leakage rule).
            None means "use everything completed" (GC targets — state feeds
            the GC outlook head; the main models stay pre-race on gc rows).
        force_refresh: re-scrape stages instead of using cached_race_results
            (e.g. a stage finished since the cache row was written mid-race).
            Stages migrated into the main DB are final and are not re-scraped.

    Returns (state_df or None, info). info keys beyond the build stats:
        sources: {'db': [...], 'cache': [...], 'scraped': [...]} stage numbers
        missing_stages: candidate stages that could not be loaded
        scrape_failed: a live fetch was attempted and raised
        total_stages_estimated: total came from a prior edition / floor,
            not the live race page
        db_horizon: latest competition date in the DB (data-current-through)
    """
    from cycling_project.prediction_tools.future_race_loader import (
        get_cached_results,
        scrape_or_load_results,
    )

    db_path = _resolve_db_path(db_path)
    info: Dict = {
        'available': False,
        'stages_completed': 0,
        'total_stages': 0,
        'riders_in_standings': 0,
        'leader_name': None,
        'reason': None,
        'sources': {'db': [], 'cache': [], 'scraped': []},
        'missing_stages': [],
        'scrape_failed': False,
        'total_stages_estimated': False,
        'db_horizon': _db_data_horizon(db_path),
    }

    # ── stage inventory: local DB + cache first, live page as enrichment ──
    stages_by_num: Dict[int, Dict] = {}
    for num, entry in _db_edition_stages(fc_race_id, year, db_path).items():
        stages_by_num[num] = dict(entry)
    for num, stage_id in _cached_edition_stage_ids(
        fc_race_id, year, db_path
    ).items():
        stages_by_num.setdefault(num, {})['cache_stage_id'] = stage_id

    live_stages = list_race_stages(fc_race_id, year)  # [] on fetch failure
    for s in live_stages:
        entry = stages_by_num.setdefault(s['stage_number'], {})
        entry.setdefault('url_param', s['url_param'])

    # ── scheduled total (pct_race_complete denominator) ──
    if live_stages:
        total_stages = len(live_stages)
    else:
        info['total_stages_estimated'] = True
        total_stages = max(
            _prior_edition_stage_count(fc_race_id, year, db_path) or 0,
            max(stages_by_num) if stages_by_num else 0,
            len(stages_by_num),  # covers prologue numbering (stage 0)
            target_stage_number or 0,
        )
    info['total_stages'] = total_stages

    if not stages_by_num:
        info['reason'] = (
            'no stage data for this edition — not in the local DB and the '
            'live race page could not be fetched'
        )
        return None, info

    # ── candidate stage numbers, strictly before the target ──
    if target_stage_number is not None:
        upper = int(target_stage_number) - 1
    else:
        upper = total_stages
    # Fill gaps up to the bound so locally-unknown completed stages can be
    # scraped (e.g. DB has 1-5, target is stage 7 -> try stage 6 too). Only
    # when stage identifiers are plain numerals — see _plain_numeral_params.
    if _plain_numeral_params(stages_by_num):
        for num in range(min(stages_by_num), upper + 1):
            stages_by_num.setdefault(num, {})
    candidate_nums = sorted(n for n in stages_by_num if n <= upper)

    # ── load each candidate: DB -> cache -> scrape; stop at the first gap ──
    completed: List[Dict] = []
    loaded_nums: List[int] = []
    for num in candidate_nums:
        entry = stages_by_num.get(num, {})
        results = None
        winning_time = None
        source = None

        # 1. Main DB: migrated results are final — force_refresh never
        #    re-scrapes them.
        if entry.get('competition_id') is not None:
            results = _load_db_stage_results(entry['competition_id'], db_path)
            if results is not None:
                winning_time = entry.get('winning_time')
                source = 'db'

        # 2. Cache (skipped on force_refresh — re-scrape instead).
        cache_id = entry.get('cache_stage_id')
        if results is None and cache_id is not None and not force_refresh:
            cached = get_cached_results(fc_race_id, year, cache_id, db_path)
            if cached is not None and len(cached):
                results = cached
                wt = cached['winning_time'].dropna()
                winning_time = float(wt.iloc[0]) if len(wt) else None
                source = 'cache'

        # 3. Live scrape (also the force_refresh path for cached stages).
        if results is None:
            url_param = entry.get('url_param') or cache_id or str(num)
            try:
                results, winning_time = scrape_or_load_results(
                    fc_race_id,
                    year,
                    stage_id=str(url_param),
                    stage_url_param=str(url_param),
                    force_refresh=force_refresh,
                    db_path=db_path,
                    raise_fetch_errors=True,
                )
                if results is not None and len(results):
                    source = 'scraped'
            except Exception as exc:
                info['scrape_failed'] = True
                logger.warning(
                    "Live state: fetch failed for stage %s of race %s/%s: %s",
                    num, fc_race_id, year, exc,
                )
                results = None
                # force_refresh asked to bypass the cache, but a failed
                # scrape beats no data — fall back and say so via sources.
                if cache_id is not None and force_refresh:
                    cached = get_cached_results(
                        fc_race_id, year, cache_id, db_path
                    )
                    if cached is not None and len(cached):
                        results = cached
                        wt = cached['winning_time'].dropna()
                        winning_time = (
                            float(wt.iloc[0]) if len(wt) else None
                        )
                        source = 'cache'

        if results is None or len(results) == 0 or winning_time is None:
            # Contiguity break: without this stage every later cumulative
            # GC sum is wrong, so stop here (stages already loaded still
            # produce valid — possibly stale — state).
            break
        completed.append({
            'seq': len(completed) + 1,
            'winning_time': winning_time,
            'results': results,
        })
        loaded_nums.append(num)
        info['sources'][source].append(num)

    info['missing_stages'] = [
        n for n in candidate_nums if n not in loaded_nums
    ]

    if not completed:
        info['reason'] = 'no completed stage results yet'
        if info['scrape_failed']:
            info['reason'] += (
                ' (live fetch failed; no local results for this edition)'
            )
        return None, info

    state, build_info = build_live_state(completed, total_stages=total_stages)
    info.update(build_info)
    info['total_stages'] = total_stages
    return state, info


def attach_race_state(
    pred_df: pd.DataFrame,
    state_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Attach the state block to a model-ready prediction frame.

    Always materializes all state columns: rows without state (or when
    state_df is None — one-day races, stage 1, GC targets, no results yet)
    get NaN + race_state_missing=1, which feature_engineering imputes to
    the training-time neutral defaults. NEVER leave the columns absent on a
    frame fed to a state-trained model: get_feature_matrix fills absent
    columns with zeros, and a 0s gap means "race leader".
    """
    df = pred_df.copy()
    if state_df is None or state_df.empty:
        for col in STATE_FEATURE_COLUMNS:
            df[col] = np.nan
        df['race_state_missing'] = 1
        return df

    merged = df.merge(
        state_df[['rider_id'] + STATE_FEATURE_COLUMNS],
        on='rider_id',
        how='left',
    )
    merged['race_state_missing'] = (
        merged[STATE_FEATURE_COLUMNS[0]].isna().astype(int)
    )
    return merged


def _place_bucket(place: int) -> int:
    """Mirror place_handling.place_bucketer's bracket scheme."""
    if place == 1:
        return 0
    if place <= 3:
        return 1
    if place <= 5:
        return 2
    if place <= 15:
        return 3
    if place <= 30:
        return 4
    if place <= 50:
        return 5
    return 6
