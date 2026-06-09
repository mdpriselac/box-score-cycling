"""
Live stage-race state for inference.

Computes the within-race state block (the rider_race_state feature columns)
for an ONGOING stage race at prediction time, from the stages completed so
far. Training-side state rows are built by
``engineering_tools.stage_race_state`` from migrated results; this module
feeds the SAME ``compute_race_state`` function from the web app's on-demand
results path (``future_race_loader.scrape_or_load_results``, which checks
the DB, then ``cached_race_results``, then scrapes), so a model trained
with ``include_race_state`` sees identical feature semantics live.

Used by web/app.py Step 3: real state is attached only when the prediction
target is stage 2+ of a stage race — matching training, where only
competition_type='stage' rows carry state. Every other target (stage 1,
one-day, GC, races without completed results yet) gets the state columns
as NaN, which feature_engineering imputes to the same neutral defaults
used for missing state in training.

Known v1 limitation: stage dates aren't available from the live results
path, so ``is_post_rest_day`` is always 0 for live state (it is populated
correctly in training data).
"""

import re
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
                'percentile': 100.0 * (n_finishers - place + 1) / n_finishers,
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


def fetch_live_race_state(
    fc_race_id: int,
    year: int,
    target_stage_number: Optional[int] = None,
    force_refresh: bool = False,
    db_path: Optional[str] = None,
) -> Tuple[Optional[pd.DataFrame], Dict]:
    """
    Fetch completed-stage results for an ongoing race and compute state.

    Args:
        target_stage_number: the stage being predicted; only stages with a
            lower number feed the state (strictly-before leakage rule).
            None means "use everything completed" (not used for GC targets
            in Phase 1 — the production model carries no state on gc rows).
        force_refresh: bypass cached_race_results (e.g. a stage finished
            since the cache row was written mid-race).

    Returns (state_df or None, info). Network access: one race-page fetch
    plus one fetch per completed stage not already cached (3s+ rate limit
    each, so a Grand Tour's first mid-race fetch can take a minute or two;
    subsequent runs hit the cache).
    """
    from cycling_project.prediction_tools.future_race_loader import (
        scrape_or_load_results,
    )

    stages = list_race_stages(fc_race_id, year)
    info: Dict = {
        'available': False,
        'stages_completed': 0,
        'total_stages': len(stages),
        'riders_in_standings': 0,
        'leader_name': None,
        'reason': None,
    }
    if not stages:
        info['reason'] = 'no stage list found for this edition'
        return None, info

    if target_stage_number is not None:
        candidates = [
            s for s in stages if s['stage_number'] < target_stage_number
        ]
    else:
        candidates = stages

    completed: List[Dict] = []
    for seq, stage in enumerate(candidates, start=1):
        try:
            results, winning_time = scrape_or_load_results(
                fc_race_id,
                year,
                stage_id=stage['url_param'],
                stage_url_param=stage['url_param'],
                force_refresh=force_refresh,
                db_path=db_path,
            )
        except Exception as exc:
            logger.warning(
                "Live state: failed to load stage %s of race %s/%s: %s",
                stage['url_param'], fc_race_id, year, exc,
            )
            break
        if results is None or len(results) == 0:
            break  # race hasn't reached this stage yet
        completed.append({
            'seq': seq,
            'winning_time': winning_time,
            'results': results,
        })

    if not completed:
        info['reason'] = 'no completed stage results yet'
        return None, info

    state, build_info = build_live_state(completed, total_stages=len(stages))
    build_info['total_stages'] = len(stages)
    return state, build_info


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
