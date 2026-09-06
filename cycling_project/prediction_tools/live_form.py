"""
Live form recomputation for future-race inference.

Future-race predictions assemble rider features from each rider's most
recent `rider_competition_snapshots` row, which means every form feature is
"as-of their last race": the EMA isn't decayed to race day,
days_since_last_race is frozen, and in early season the snapshot's "current
season" is actually last season. This module recomputes the time-sensitive
form features as-of a given date, using the same production classes that
build snapshots (engineering_tools/form_team_features.RiderFormHistory), so
the recomputed values match what the precompute would have written had a
competition existed on that date.

Covers both form families:
  - the original six (form_recent_avg_bucket .. days_since_last_race)
  - the 15 trajectory/EMA features (v2_*/v3_*, CV-validated 2026-06)

Career-average inputs for form_delta use the mean bucket of all results
since 2010, matching the precompute's running-state career average.

Mid-race caveat: for predictions made while a stage race is underway, any
already-raced stages of that same race are excluded only if (a) their
results are already migrated into rider_results AND (b) the caller passes
exclude_race (db race_id, year). Pre-race predictions — the dominant use —
need neither.
"""

import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from cycling_project.engineering_tools.form_team_features import (
    FORM_FEATURE_COLUMNS,
    TRAJECTORY_FORM_COLUMNS,
    RiderFormHistory,
)
from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.db_path import default_db_path


logger = get_logger(__name__)

_DEFAULT_DB = default_db_path()

HISTORY_START = '2010-01-01'

LIVE_FORM_COLUMNS = FORM_FEATURE_COLUMNS + TRAJECTORY_FORM_COLUMNS


def _career_avg_from_type_sums(type_sums: Dict[str, List[float]]) -> float:
    """
    Career average exactly as the precompute computes it for form_delta:
    per-type (stage/one_day/gc) averages ROUNDED to 2dp in the snapshot,
    then recombined weighted by counts (FeaturePrecomputer._compute_career_avg
    over RiderRunningState.get_snapshot values). The rounding matters —
    using the raw mean shifts form_delta's own 2dp rounding on ~20% of rows.
    """
    weighted = 0.0
    total = 0
    for s, c in type_sums.values():
        if c > 0:
            weighted += round(s / c, 2) * c
            total += c
    return (weighted / total) if total else 4.0


def _load_histories(
    rider_ids: List[int],
    asof_date: str,
    db_path: str,
    asof_comp_id: Optional[int] = None,
) -> Tuple[Dict[int, RiderFormHistory], Dict[int, float]]:
    """
    Build a RiderFormHistory per rider from results strictly before asof_date.

    Returns (histories, career_avg_bucket per rider). Mirrors the precompute:
    chronological (date, id) add_race with percentile/category, profile from
    competition_field_features.race_dominant_profile, career averages from
    rounded per-type snapshot averages.

    asof_comp_id: validation hook. The precompute processes competitions in
    (date, id) order, so a snapshot's career state includes SAME-DAY comps
    with a lower id. Passing the target competition id replicates that cut
    when replaying a past competition. Live future-race calls leave it None
    (strictly before the day) — a future race has no same-day priors.
    """
    placeholders = ','.join('?' * len(rider_ids))
    same_day_clause = (
        "OR (c.date = ? AND c.id < ?)" if asof_comp_id is not None else ""
    )
    params = [*rider_ids, HISTORY_START, asof_date]
    if asof_comp_id is not None:
        params += [asof_date, asof_comp_id]

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"""
            SELECT
                rr.rider_id,
                c.date,
                rr.place_bucket,
                c.race_id,
                r.year,
                c.competition_type,
                COALESCE(cff.race_dominant_profile, 'unknown'),
                rr.percentile,
                r.category
            FROM rider_results rr
            JOIN competitions c ON c.id = rr.competition_id
            JOIN races r ON r.id = c.race_id
            LEFT JOIN competition_field_features cff
                ON cff.competition_id = rr.competition_id
            WHERE rr.rider_id IN ({placeholders})
              AND c.date IS NOT NULL
              AND c.date >= ?
              AND (c.date < ? {same_day_clause})
              AND rr.place_bucket IS NOT NULL
              AND rr.place_bucket != 7
            ORDER BY c.date, c.id
        """, params).fetchall()

    histories: Dict[int, RiderFormHistory] = {}
    type_sums: Dict[int, Dict[str, List[float]]] = {}

    for (rider_id, comp_date, bucket, race_id, race_year,
         comp_type, profile, percentile, category) in rows:
        hist = histories.get(rider_id)
        if hist is None:
            hist = histories[rider_id] = RiderFormHistory(rider_id=rider_id)
            type_sums[rider_id] = {
                'stage': [0.0, 0], 'one_day': [0.0, 0], 'gc': [0.0, 0],
            }
        hist.add_race(
            date=comp_date,
            bucket=bucket,
            race_id=race_id,
            race_year=race_year,
            comp_type=comp_type,
            profile=profile,
            percentile=percentile,
            race_category=category,
        )
        agg = type_sums[rider_id].get(comp_type)
        if agg is not None:
            agg[0] += bucket
            agg[1] += 1

    career_avgs = {
        rid: _career_avg_from_type_sums(sums)
        for rid, sums in type_sums.items()
    }
    return histories, career_avgs


def compute_form_features_asof(
    rider_ids: List[int],
    asof_date: Optional[str] = None,
    comp_type: str = 'one_day',
    race_dominant_profile: str = 'unknown',
    exclude_race: Optional[Tuple[int, int]] = None,
    race_start_date: Optional[str] = None,
    db_path: Optional[str] = None,
    asof_comp_id: Optional[int] = None,
) -> pd.DataFrame:
    """
    Recompute all 21 form features for riders as-of a date.

    Args:
        rider_ids: Riders to compute for
        asof_date: YYYY-MM-DD; defaults to today. Only results strictly
            before this date count (same rule as snapshot computation).
        comp_type: Competition type of the target race ('one_day', 'stage',
            'gc') — affects GC effective-date handling only when
            race_start_date is given.
        race_dominant_profile: Dominant profile of the target race, for
            form_profile_recent_avg. 'unknown' yields the training-consistent
            default for unknown-profile races.
        exclude_race: Optional (db race_id, year) of the target race, for
            mid-race GC predictions where same-race stages may already be
            migrated. Harmless for pre-race predictions (no results exist).
        race_start_date: For GC targets mid-race, the race start date.
        db_path: Database path override.

    Returns:
        DataFrame with rider_id + the 21 form columns. Riders with no
        history get the original-six defaults and NULL trajectory features,
        exactly like a debut snapshot row.
    """
    if not rider_ids:
        return pd.DataFrame(columns=['rider_id'] + LIVE_FORM_COLUMNS)

    asof_date = asof_date or date.today().isoformat()
    db_path = str(db_path or _DEFAULT_DB)
    target_year = int(asof_date[:4])
    excl_race_id, excl_year = exclude_race if exclude_race else (-1, -1)

    histories, career_avgs = _load_histories(
        rider_ids, asof_date, db_path, asof_comp_id=asof_comp_id
    )

    records = []
    for rid in rider_ids:
        hist = histories.get(rid)
        if hist is None:
            hist = RiderFormHistory(rider_id=rid)
        form = hist.get_form_features(
            target_date=asof_date,
            target_year=target_year,
            target_race_id=excl_race_id,
            target_comp_type=comp_type,
            target_profile=race_dominant_profile,
            race_start_date=race_start_date if comp_type == 'gc' else None,
            career_avg_bucket=career_avgs.get(rid, 4.0),
        )
        traj = hist.get_trajectory_form_features(
            target_date=asof_date,
            target_year=target_year,
            target_race_id=excl_race_id,
            target_comp_type=comp_type,
            race_start_date=race_start_date if comp_type == 'gc' else None,
        )
        rec = {'rider_id': rid}
        rec.update(form)
        rec.update(traj)
        records.append(rec)

    df = pd.DataFrame(records)
    logger.info(
        f"Recomputed live form for {len(df)} riders as of {asof_date} "
        f"({len(histories)} with history)"
    )
    return df[['rider_id'] + LIVE_FORM_COLUMNS]
