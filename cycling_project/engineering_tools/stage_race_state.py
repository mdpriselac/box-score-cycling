"""
Stage-race state precomputation.

Builds the ``rider_race_state`` table: for every stage competition (sequence
position k >= 2) of a multi-stage race, one row per rider holding their
within-race state AFTER the previous stage — reconstructed GC standings,
in-race stage form, fatigue/progress, and tactical-freedom flags. The race's
GC competition gets a row holding the state after the final stage.

Rows are only written where state genuinely exists. Stage-1 rows, one-day
races, riders without complete prior-stage coverage, and races that fail the
reconstruction sanity check get NO row — the training-side LEFT JOIN surfaces
them as NULL and feature_engineering imputes neutral defaults plus a
``race_state_missing`` flag (same pattern as the Stage-0 gradient features).

GC standings are reconstructed as cumulative stage time:

    sum over completed stages of (stage winning_time + rider time_gap)

Validated against stored final GCs (2023-2025): median top-10 gap error ~10s
(bonus seconds, which FirstCycling's GC includes but raw stage sums don't),
~72s worst case over a Grand Tour. Races whose reconstruction disagrees with
the stored GC top-10 by more than ``SUSPECT_TOP10_ERR_S`` on average are
marked suspect in ``race_state_quality`` and get no state rows, so they fall
back to pre-race behavior.

The state computation (`compute_race_state`) is a pure function over result
frames so the identical code path can later serve live mid-race inference
from ``cached_race_results``.

Usage:
    uv run python -m cycling_project.engineering_tools.stage_race_state             # incremental
    uv run python -m cycling_project.engineering_tools.stage_race_state --rebuild   # drop + full rebuild
    uv run python -m cycling_project.engineering_tools.stage_race_state --race-id 42 --dry-run
"""

import argparse
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

logger = get_logger(__name__)

# A race is suspect when the reconstructed final GC disagrees with the stored
# GC by more than this (mean absolute seconds over matched top-10 riders).
# Bonus seconds legitimately accumulate to ~70s over a Grand Tour; genuine
# data corruption (e.g. Tour de Wallonie 2024) lands in the thousands.
SUSPECT_TOP10_ERR_S = 120.0

# Time gap (seconds) past which a rider is considered out of GC contention
# and tactically "free" (breakaway license), and past which a single stage
# counts as losing big time.
BIG_TIME_LOSS_S = 600.0

# Canonical feature column list. data_pipeline.RACE_STATE_FEATURE_COLS must
# stay in sync (unit-tested); it is duplicated there to keep prediction_tools
# free of engineering_tools imports, matching the gradient-feature pattern.
STATE_FEATURE_COLUMNS = [
    # GC standings (reconstructed cumulative time after the previous stage)
    'gc_rank_current',
    'gc_gap_to_leader_s',
    'gc_gap_to_podium_s',
    'gc_gap_to_rank10_s',
    'gc_rank_pctile',
    'is_race_leader',
    # Team GC situation
    'team_best_gc_rank',
    'is_team_gc_leader',
    'teammates_top10_count',
    'team_has_gc_top5',
    # In-race stage form
    'last_stage_bucket',
    'last_stage_pctile',
    'best_stage_bucket_so_far',
    'mean_stage_pctile_so_far',
    'stage_top10_count_so_far',
    # Fatigue / race progress
    'stages_completed',
    'pct_race_complete',
    'cum_time_raced_s',
    'is_post_rest_day',
    'field_attrition',
    # Tactical freedom
    'gc_gap_gt_10min',
    'lost_big_time_last_stage',
]

METADATA_COLUMNS = ['rider_id', 'competition_id', 'race_id', 'stage_seq']


# ---------------------------------------------------------------------------
# Pure state computation
# ---------------------------------------------------------------------------

def compute_race_state(
    stages: pd.DataFrame,
    results: pd.DataFrame,
    gc_competition_id: Optional[int] = None,
    race_id: Optional[int] = None,
    total_stages: Optional[int] = None,
) -> Tuple[pd.DataFrame, Dict]:
    """
    Compute within-race state rows for one stage race.

    Args:
        stages: one row per stage competition with columns
            [competition_id, stage_number, date, winning_time].
        results: stage results with columns
            [competition_id, rider_id, team_id, place, time_gap,
             place_bucket, percentile].
        gc_competition_id: competition id of the race's GC row, if any. Gets
            a state row holding the standings after the final stage.
        race_id: carried through to the output for bookkeeping.
        total_stages: scheduled number of stages, used as the
            pct_race_complete denominator. Defaults to len(stages) — correct
            for historical races; live mid-race callers pass only the
            COMPLETED stages in `stages`, so they must pass the full
            scheduled count here.

    Returns:
        (state_df, quality) where state_df has METADATA_COLUMNS +
        STATE_FEATURE_COLUMNS and quality describes how far the
        reconstruction could run (validation against the stored GC happens
        separately in `validate_reconstruction`).
    """
    stages = stages.copy()
    stages['date'] = pd.to_datetime(stages['date'], errors='coerce')
    stages = stages.sort_values(
        ['date', 'stage_number'], na_position='last'
    ).reset_index(drop=True)
    n_total = len(stages)
    pct_denominator = total_stages if total_stages else n_total

    quality: Dict = {
        'n_stages': n_total,
        'n_state_rows': 0,
        'truncated_at_seq': None,  # stage seq where reconstruction had to stop
    }

    if n_total == 0 or results.empty:
        return _empty_state_frame(), quality

    seq_of_comp = {
        comp_id: seq + 1 for seq, comp_id in enumerate(stages['competition_id'])
    }
    results = results.copy()
    results['stage_seq'] = results['competition_id'].map(seq_of_comp)
    results = results.dropna(subset=['stage_seq'])
    results['stage_seq'] = results['stage_seq'].astype(int)

    results_by_seq = {seq: g for seq, g in results.groupby('stage_seq')}
    stage1_starters = (
        results_by_seq[1]['rider_id'].nunique() if 1 in results_by_seq else 0
    )

    # Rider -> team mapping (constant within a race; first non-null wins)
    team_of_rider = (
        results.dropna(subset=['team_id'])
        .groupby('rider_id')['team_id']
        .first()
        .to_dict()
    )

    cum_time: Dict[int, float] = {}        # rider -> cumulative seconds
    history: Dict[int, List[Tuple]] = {}   # rider -> [(bucket, pctile, place)]
    last_stage_rows: Dict[int, Tuple] = {} # rider -> (bucket, pctile, time_gap)

    out_rows: List[Dict] = []

    # k is the sequence position the state applies to ("before stage k").
    # k == n_total + 1 is the virtual "after the final stage" checkpoint,
    # keyed to the GC competition when one exists.
    for k in range(2, n_total + 2):
        prev_seq = k - 1
        prev_stage = stages.iloc[prev_seq - 1]
        prev_results = results_by_seq.get(prev_seq)

        if (
            prev_results is None
            or prev_results.empty
            or pd.isna(prev_stage['winning_time'])
        ):
            # A resultless or timeless stage breaks every later cumulative
            # sum; stop producing state from here on.
            quality['truncated_at_seq'] = int(prev_seq)
            break

        winning_time = float(prev_stage['winning_time'])
        new_cum: Dict[int, float] = {}
        for row in prev_results.itertuples(index=False):
            if pd.isna(row.time_gap):
                continue  # broken timing for this rider: drop from standings
            if prev_seq == 1:
                new_cum[row.rider_id] = winning_time + float(row.time_gap)
            elif row.rider_id in cum_time:
                new_cum[row.rider_id] = (
                    cum_time[row.rider_id] + winning_time + float(row.time_gap)
                )
            # Riders with a coverage gap (no result in some earlier stage)
            # stay excluded: their cumulative time is not comparable.
            else:
                continue
            bucket = row.place_bucket if pd.notna(row.place_bucket) else np.nan
            pctile = row.percentile if pd.notna(row.percentile) else np.nan
            history.setdefault(row.rider_id, []).append(
                (bucket, pctile, row.place)
            )
            last_stage_rows[row.rider_id] = (bucket, pctile, float(row.time_gap))
        cum_time = new_cum

        if not cum_time:
            quality['truncated_at_seq'] = int(prev_seq)
            break

        # ----- standings after prev_seq -----
        # Raw cumulative time ties whole bunches together early in a race
        # (everyone on 0 gap after a sprint stage), so ranks are tie-broken
        # by countback — mean stage place so far — approximating real GC
        # tie-breaking. Ranks are therefore strict (exactly one leader).
        # Gap features stay raw cumulative time: a 0s gap inside a tied
        # bunch is true information.
        times = pd.Series(cum_time, dtype=float)
        countback = pd.Series({
            rider: float(np.mean(
                [h[2] for h in history.get(rider, []) if pd.notna(h[2])] or [999.0]
            ))
            for rider in times.index
        })
        order = (
            pd.DataFrame({'t': times, 'cb': countback})
            .sort_values(['t', 'cb'])
        )
        ranks = pd.Series(
            np.arange(1, len(order) + 1), index=order.index, dtype=float
        )
        n_remaining = len(times)
        leader_time = float(order['t'].iloc[0])
        podium_time = (
            float(order['t'].iloc[2]) if n_remaining >= 3 else np.nan
        )
        rank10_time = (
            float(order['t'].iloc[9]) if n_remaining >= 10 else np.nan
        )

        # Team aggregates over the current standings
        team_ranks: Dict = {}
        for rider, rank in ranks.items():
            team = team_of_rider.get(rider)
            if team is not None:
                team_ranks.setdefault(team, []).append((rider, rank))

        # ----- target competition this state applies to -----
        if k <= n_total:
            target_comp_id = int(stages.iloc[k - 1]['competition_id'])
            target_date = stages.iloc[k - 1]['date']
        else:
            if gc_competition_id is None:
                break
            target_comp_id = int(gc_competition_id)
            target_date = pd.NaT

        prev_date = prev_stage['date']
        if pd.notna(target_date) and pd.notna(prev_date):
            is_post_rest_day = int((target_date - prev_date).days > 1)
        else:
            is_post_rest_day = 0

        for rider, total in times.items():
            rank = float(ranks[rider])
            gap_leader = total - leader_time
            hist = history.get(rider, [])
            buckets = [h[0] for h in hist if pd.notna(h[0])]
            pctiles = [h[1] for h in hist if pd.notna(h[1])]
            places = [h[2] for h in hist if pd.notna(h[2])]
            last_bucket, last_pctile, last_gap = last_stage_rows.get(
                rider, (np.nan, np.nan, np.nan)
            )

            team = team_of_rider.get(rider)
            mates = team_ranks.get(team, []) if team is not None else []
            if mates:
                team_best = min(r for _, r in mates)
                teammates_top10 = sum(
                    1 for rid, r in mates if rid != rider and r <= 10
                )
                team_has_top5 = int(any(r <= 5 for _, r in mates))
                is_team_leader = int(rank == team_best)
            else:
                team_best = np.nan
                teammates_top10 = 0
                team_has_top5 = 0
                is_team_leader = 0

            out_rows.append({
                'rider_id': int(rider),
                'competition_id': target_comp_id,
                'race_id': race_id,
                'stage_seq': int(k) if k <= n_total else None,
                'gc_rank_current': rank,
                'gc_gap_to_leader_s': gap_leader,
                'gc_gap_to_podium_s': (
                    total - podium_time if pd.notna(podium_time) else np.nan
                ),
                'gc_gap_to_rank10_s': (
                    total - rank10_time if pd.notna(rank10_time) else np.nan
                ),
                'gc_rank_pctile': 100.0 * (n_remaining - rank + 1) / n_remaining,
                'is_race_leader': int(rank == 1.0),
                'team_best_gc_rank': team_best,
                'is_team_gc_leader': is_team_leader,
                'teammates_top10_count': teammates_top10,
                'team_has_gc_top5': team_has_top5,
                'last_stage_bucket': last_bucket,
                'last_stage_pctile': last_pctile,
                'best_stage_bucket_so_far': (
                    float(np.min(buckets)) if buckets else np.nan
                ),
                'mean_stage_pctile_so_far': (
                    float(np.mean(pctiles)) if pctiles else np.nan
                ),
                'stage_top10_count_so_far': int(
                    sum(1 for p in places if p <= 10)
                ),
                'stages_completed': int(prev_seq),
                'pct_race_complete': prev_seq / pct_denominator,
                'cum_time_raced_s': float(total),
                'is_post_rest_day': is_post_rest_day,
                'field_attrition': (
                    n_remaining / stage1_starters if stage1_starters else np.nan
                ),
                'gc_gap_gt_10min': int(gap_leader > BIG_TIME_LOSS_S),
                'lost_big_time_last_stage': int(
                    pd.notna(last_gap) and last_gap > BIG_TIME_LOSS_S
                ),
            })

    state_df = (
        pd.DataFrame(out_rows) if out_rows else _empty_state_frame()
    )
    quality['n_state_rows'] = len(state_df)
    return state_df, quality


def _empty_state_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=METADATA_COLUMNS + STATE_FEATURE_COLUMNS)


def validate_reconstruction(
    state_df: pd.DataFrame,
    gc_results: pd.DataFrame,
    gc_competition_id: int,
) -> Dict:
    """
    Compare the reconstructed final standings (the rows keyed to the GC
    competition) against the stored GC results.

    Args:
        state_df: output of compute_race_state.
        gc_results: stored GC rows with columns [rider_id, place, time_gap].

    Returns dict with gc_validated, top10_mean_abs_err_s, gc_winner_match,
    n_matched_top10, is_suspect.
    """
    out = {
        'gc_validated': 0,
        'top10_mean_abs_err_s': None,
        'gc_winner_match': None,
        'n_matched_top10': 0,
        'is_suspect': 0,
    }
    final_state = state_df[state_df['competition_id'] == gc_competition_id]
    if final_state.empty or gc_results.empty:
        return out

    merged = gc_results.merge(
        final_state[['rider_id', 'gc_gap_to_leader_s', 'gc_rank_current']],
        on='rider_id',
        how='inner',
    )
    top10 = merged[merged['place'] <= 10].dropna(
        subset=['time_gap', 'gc_gap_to_leader_s']
    )
    if len(top10) < 5:
        # Too few matched riders to judge; treat as unvalidated but usable.
        return out

    errs = (top10['gc_gap_to_leader_s'] - top10['time_gap']).abs()
    gc_winner = gc_results.loc[gc_results['place'] == 1, 'rider_id']
    recon_winner = final_state.loc[
        final_state['gc_rank_current'] == 1.0, 'rider_id'
    ]
    winner_match = int(
        not gc_winner.empty
        and not recon_winner.empty
        and gc_winner.iloc[0] in set(recon_winner)
    )

    out.update({
        'gc_validated': 1,
        'top10_mean_abs_err_s': float(errs.mean()),
        'gc_winner_match': winner_match,
        'n_matched_top10': int(len(top10)),
        'is_suspect': int(errs.mean() > SUSPECT_TOP10_ERR_S),
    })
    return out


# ---------------------------------------------------------------------------
# DB builder
# ---------------------------------------------------------------------------

class StageRaceStateBuilder:
    """Populates rider_race_state + race_state_quality from the SQLite DB."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or self._find_database()

    def _find_database(self) -> str:
        if HAS_DOTENV:
            load_dotenv()
            env_path = os.getenv('DB_PATH')
            if env_path and os.path.isfile(env_path):
                return env_path
        candidate = (
            Path(__file__).parent.parent
            / "webscrape_tools" / "database" / "database" / "cycling_races.db"
        )
        if candidate.exists():
            return str(candidate)
        raise FileNotFoundError("Database not found")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def create_tables(self, conn: sqlite3.Connection) -> None:
        feature_cols_sql = ',\n                '.join(
            f'{c} REAL' for c in STATE_FEATURE_COLUMNS
        )
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS rider_race_state (
                rider_id INTEGER NOT NULL,
                competition_id INTEGER NOT NULL,
                race_id INTEGER,
                stage_seq INTEGER,
                {feature_cols_sql},
                computed_at TEXT,
                PRIMARY KEY (rider_id, competition_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_rider_race_state_comp
            ON rider_race_state(competition_id)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS race_state_quality (
                race_id INTEGER PRIMARY KEY,
                race_name TEXT,
                race_year INTEGER,
                n_stages INTEGER,
                n_stage_results INTEGER,
                n_state_rows INTEGER,
                truncated_at_seq INTEGER,
                gc_validated INTEGER,
                top10_mean_abs_err_s REAL,
                gc_winner_match INTEGER,
                n_matched_top10 INTEGER,
                is_suspect INTEGER,
                computed_at TEXT
            )
        """)
        conn.commit()

    def races_to_process(
        self, conn: sqlite3.Connection, rebuild: bool = False
    ) -> pd.DataFrame:
        """
        Stage races needing (re)computation: never processed, or whose stage
        count / result count changed since (covers in-progress races gaining
        stages and late result backfills).
        """
        races = pd.read_sql_query(
            """
            SELECT r.id AS race_id, r.name AS race_name, r.year AS race_year,
                   COUNT(c.id) AS n_stages,
                   COALESCE(SUM(rc.n_res), 0) AS n_stage_results
            FROM races r
            JOIN competitions c ON c.race_id = r.id
                AND c.competition_type = 'stage'
            LEFT JOIN (
                SELECT competition_id, COUNT(*) AS n_res
                FROM rider_results GROUP BY competition_id
            ) rc ON rc.competition_id = c.id
            GROUP BY r.id
            """,
            conn,
        )
        if rebuild:
            return races
        try:
            done = pd.read_sql_query(
                "SELECT race_id, n_stages, n_stage_results FROM race_state_quality",
                conn,
            )
        except (pd.errors.DatabaseError, sqlite3.OperationalError):
            return races
        merged = races.merge(
            done, on='race_id', how='left', suffixes=('', '_done')
        )
        needs = merged[
            merged['n_stages_done'].isna()
            | (merged['n_stages'] != merged['n_stages_done'])
            | (merged['n_stage_results'] != merged['n_stage_results_done'])
        ]
        return needs[races.columns]

    def _load_race(
        self, conn: sqlite3.Connection, race_id: int
    ) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[int], pd.DataFrame]:
        stages = pd.read_sql_query(
            """
            SELECT id AS competition_id, stage_number, date, winning_time
            FROM competitions
            WHERE race_id = ? AND competition_type = 'stage'
            """,
            conn,
            params=(race_id,),
        )
        if stages.empty:
            return stages, pd.DataFrame(), None, pd.DataFrame()
        comp_ids = stages['competition_id'].tolist()
        placeholders = ','.join('?' * len(comp_ids))
        results = pd.read_sql_query(
            f"""
            SELECT competition_id, rider_id, team_id, place, time_gap,
                   place_bucket, percentile
            FROM rider_results
            WHERE competition_id IN ({placeholders})
            """,
            conn,
            params=comp_ids,
        )
        gc_row = conn.execute(
            "SELECT id FROM competitions WHERE race_id = ? AND competition_type = 'gc'",
            (race_id,),
        ).fetchone()
        gc_comp_id = gc_row[0] if gc_row else None
        gc_results = pd.DataFrame()
        if gc_comp_id is not None:
            gc_results = pd.read_sql_query(
                "SELECT rider_id, place, time_gap FROM rider_results "
                "WHERE competition_id = ?",
                conn,
                params=(gc_comp_id,),
            )
        return stages, results, gc_comp_id, gc_results

    def _write_race(
        self,
        conn: sqlite3.Connection,
        race_id: int,
        state_df: pd.DataFrame,
        quality_row: Dict,
    ) -> None:
        now = datetime.now().isoformat(timespec='seconds')
        conn.execute(
            "DELETE FROM rider_race_state WHERE race_id = ?", (race_id,)
        )
        if not state_df.empty:
            cols = METADATA_COLUMNS + STATE_FEATURE_COLUMNS
            payload = state_df[cols].astype(object).where(
                state_df[cols].notna(), None
            )
            payload['computed_at'] = now
            placeholders = ','.join('?' * (len(cols) + 1))
            conn.executemany(
                f"INSERT OR REPLACE INTO rider_race_state "
                f"({', '.join(cols)}, computed_at) VALUES ({placeholders})",
                payload.itertuples(index=False, name=None),
            )
        conn.execute(
            """
            INSERT OR REPLACE INTO race_state_quality
            (race_id, race_name, race_year, n_stages, n_stage_results,
             n_state_rows, truncated_at_seq, gc_validated,
             top10_mean_abs_err_s, gc_winner_match, n_matched_top10,
             is_suspect, computed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                race_id,
                quality_row.get('race_name'),
                quality_row.get('race_year'),
                quality_row.get('n_stages'),
                quality_row.get('n_stage_results'),
                quality_row.get('n_state_rows'),
                quality_row.get('truncated_at_seq'),
                quality_row.get('gc_validated'),
                quality_row.get('top10_mean_abs_err_s'),
                quality_row.get('gc_winner_match'),
                quality_row.get('n_matched_top10'),
                quality_row.get('is_suspect'),
                now,
            ),
        )

    def run(
        self,
        rebuild: bool = False,
        race_id: Optional[int] = None,
        dry_run: bool = False,
    ) -> Dict:
        """Build state rows. Returns summary counts."""
        conn = self._connect()
        try:
            self.create_tables(conn)
            if rebuild and not dry_run:
                logger.info("Rebuild: clearing rider_race_state + race_state_quality")
                conn.execute("DELETE FROM rider_race_state")
                conn.execute("DELETE FROM race_state_quality")
                conn.commit()

            todo = self.races_to_process(conn, rebuild=rebuild)
            if race_id is not None:
                todo = todo[todo['race_id'] == race_id]
            logger.info("Stage-race state: %d races to process", len(todo))

            n_rows = n_suspect = n_truncated = 0
            for i, race in enumerate(todo.itertuples(index=False), 1):
                stages, results, gc_comp_id, gc_results = self._load_race(
                    conn, race.race_id
                )
                state_df, quality = compute_race_state(
                    stages, results, gc_comp_id, race_id=race.race_id
                )
                validation = (
                    validate_reconstruction(state_df, gc_results, gc_comp_id)
                    if gc_comp_id is not None
                    else {
                        'gc_validated': 0, 'top10_mean_abs_err_s': None,
                        'gc_winner_match': None, 'n_matched_top10': 0,
                        'is_suspect': 0,
                    }
                )
                if validation['is_suspect']:
                    logger.warning(
                        "Suspect reconstruction for race %s (%s %s): "
                        "top-10 err %.0fs — writing no state rows",
                        race.race_id, race.race_name, race.race_year,
                        validation['top10_mean_abs_err_s'],
                    )
                    state_df = _empty_state_frame()
                    n_suspect += 1
                if quality.get('truncated_at_seq') is not None:
                    n_truncated += 1

                quality_row = {
                    'race_name': race.race_name,
                    'race_year': race.race_year,
                    'n_stage_results': race.n_stage_results,
                    **quality,
                    'n_state_rows': len(state_df),
                    **validation,
                }
                if not dry_run:
                    self._write_race(conn, race.race_id, state_df, quality_row)
                    if i % 50 == 0:
                        conn.commit()
                        logger.info("  %d/%d races done", i, len(todo))
                n_rows += len(state_df)

            if not dry_run:
                conn.commit()
            summary = {
                'races_processed': len(todo),
                'state_rows': n_rows,
                'suspect_races': n_suspect,
                'truncated_races': n_truncated,
            }
            logger.info("Stage-race state build complete: %s", summary)
            return summary
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument('--rebuild', action='store_true',
                        help='Drop and rebuild all state rows')
    parser.add_argument('--race-id', type=int, default=None,
                        help='Process a single race (debugging)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Compute and validate without writing')
    parser.add_argument('--db-path', type=str, default=None)
    args = parser.parse_args()

    builder = StageRaceStateBuilder(db_path=args.db_path)
    summary = builder.run(
        rebuild=args.rebuild, race_id=args.race_id, dry_run=args.dry_run
    )
    print(summary)


if __name__ == '__main__':
    main()
