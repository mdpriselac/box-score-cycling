"""Unit tests for stage-race state computation (rider_race_state)."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from cycling_project.engineering_tools.stage_race_state import (
    METADATA_COLUMNS,
    STATE_FEATURE_COLUMNS,
    StageRaceStateBuilder,
    compute_race_state,
    validate_reconstruction,
)
from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline
from cycling_project.prediction_tools.feature_engineering import FeatureEngineer


# ---------------------------------------------------------------------------
# Fixture race: 3 stages, 8 riders
#   riders 1,2 team 1; riders 3,4 team 2; riders 5,6 team 3
#   rider 7: abandons after stage 1 (no stage 2/3 results)
#   rider 8: coverage gap (missing stage 1, appears from stage 2)
#   rider 5: loses 700s on stage 2 (big time loss)
#   rest day between stage 2 (06-02) and stage 3 (06-04)
# ---------------------------------------------------------------------------

STAGES = pd.DataFrame({
    'competition_id': [101, 102, 103],
    'stage_number': [1, 2, 3],
    'date': ['2024-06-01', '2024-06-02', '2024-06-04'],
    'winning_time': [10000.0, 11000.0, 12000.0],
})

GC_COMP_ID = 104


def _results() -> pd.DataFrame:
    rows = []

    def add(comp, rider, team, place, gap, bucket, pctile):
        rows.append({
            'competition_id': comp, 'rider_id': rider, 'team_id': team,
            'place': place, 'time_gap': gap, 'place_bucket': bucket,
            'percentile': pctile,
        })

    # Stage 1: riders 1-7
    add(101, 1, 1, 1, 0.0, 0, 100.0)
    add(101, 2, 1, 2, 10.0, 1, 90.0)
    add(101, 3, 2, 3, 20.0, 1, 80.0)
    add(101, 4, 2, 4, 30.0, 2, 70.0)
    add(101, 5, 3, 5, 40.0, 2, 60.0)
    add(101, 6, 3, 6, 50.0, 3, 50.0)
    add(101, 7, None, 7, 60.0, 3, 40.0)
    # Stage 2: rider 7 gone, rider 8 appears (coverage gap), rider 5 loses 700s
    add(102, 2, 1, 1, 0.0, 0, 100.0)
    add(102, 1, 1, 2, 5.0, 1, 90.0)
    add(102, 3, 2, 3, 15.0, 1, 80.0)
    add(102, 6, 3, 4, 20.0, 2, 70.0)
    add(102, 8, None, 5, 25.0, 2, 60.0)
    add(102, 4, 2, 6, 30.0, 3, 50.0)
    add(102, 5, 3, 7, 700.0, 6, 40.0)
    # Stage 3: riders 1-6 + 8
    add(103, 1, 1, 1, 0.0, 0, 100.0)
    add(103, 2, 1, 2, 8.0, 1, 90.0)
    add(103, 3, 2, 3, 12.0, 1, 80.0)
    add(103, 4, 2, 4, 25.0, 2, 70.0)
    add(103, 5, 3, 5, 30.0, 2, 60.0)
    add(103, 6, 3, 6, 40.0, 3, 50.0)
    add(103, 8, None, 7, 45.0, 3, 40.0)

    return pd.DataFrame(rows)


# Final cumulative times for riders with full coverage (1-6):
#   r1: 10000+0 + 11000+5 + 12000+0  = 33005
#   r2: 10010 + 11000 + 12008        = 33018
#   r3: 10020 + 11015 + 12012        = 33047
#   r4: 10030 + 11030 + 12025        = 33085
#   r5: 10040 + 11700 + 12030        = 33770
#   r6: 10050 + 11020 + 12040        = 33110
FINAL_GC = pd.DataFrame({
    'rider_id': [1, 2, 3, 4, 6, 5],
    'place': [1, 2, 3, 4, 5, 6],
    'time_gap': [0.0, 13.0, 42.0, 80.0, 105.0, 765.0],
})


@pytest.fixture
def state_and_quality():
    return compute_race_state(
        STAGES, _results(), gc_competition_id=GC_COMP_ID, race_id=1
    )


def _row(state_df, comp_id, rider_id):
    rows = state_df[
        (state_df['competition_id'] == comp_id)
        & (state_df['rider_id'] == rider_id)
    ]
    assert len(rows) == 1, f"expected 1 state row for comp {comp_id} rider {rider_id}"
    return rows.iloc[0]


@pytest.mark.unit
class TestComputeRaceState:

    def test_no_state_for_stage_one(self, state_and_quality):
        state, _ = state_and_quality
        assert (state['competition_id'] == 101).sum() == 0

    def test_stage_two_standings_after_stage_one(self, state_and_quality):
        state, _ = state_and_quality
        r1 = _row(state, 102, 1)
        assert r1['gc_rank_current'] == 1
        assert r1['is_race_leader'] == 1
        assert r1['gc_gap_to_leader_s'] == 0.0
        assert r1['stages_completed'] == 1
        assert r1['pct_race_complete'] == pytest.approx(1 / 3)
        assert r1['cum_time_raced_s'] == pytest.approx(10000.0)
        assert r1['last_stage_bucket'] == 0
        assert r1['stage_top10_count_so_far'] == 1

        r3 = _row(state, 102, 3)
        assert r3['gc_rank_current'] == 3
        assert r3['gc_gap_to_leader_s'] == pytest.approx(20.0)
        # podium time after stage 1 is rider 3's own time -> gap 0
        assert r3['gc_gap_to_podium_s'] == pytest.approx(0.0)

        # 7 riders in standings, fewer than 10 -> rank-10 gap undefined
        assert pd.isna(r1['gc_gap_to_rank10_s'])
        # all 7 stage-1 starters still present
        assert r1['field_attrition'] == pytest.approx(1.0)

    def test_stage_three_cumulative_state(self, state_and_quality):
        state, _ = state_and_quality
        # After stage 2: r1=21005, r2=21010, r3=21035, r4=21060, r6=21070, r5=21740
        r2 = _row(state, 103, 2)
        assert r2['gc_rank_current'] == 2
        assert r2['gc_gap_to_leader_s'] == pytest.approx(5.0)
        assert r2['last_stage_bucket'] == 0  # won stage 2
        assert r2['best_stage_bucket_so_far'] == 0
        assert r2['mean_stage_pctile_so_far'] == pytest.approx(95.0)

        r5 = _row(state, 103, 5)
        assert r5['gc_rank_current'] == 6
        assert r5['gc_gap_to_leader_s'] == pytest.approx(735.0)
        assert r5['gc_gap_gt_10min'] == 1
        assert r5['lost_big_time_last_stage'] == 1

        # abandoned rider 7 and coverage-gap rider 8 are out of the standings
        assert (state[state['competition_id'] == 103]['rider_id'] == 7).sum() == 0
        assert (state[state['competition_id'] == 103]['rider_id'] == 8).sum() == 0
        assert r5['field_attrition'] == pytest.approx(6 / 7)

    def test_rest_day_flag(self, state_and_quality):
        state, _ = state_and_quality
        # stage 2 follows stage 1 by one day: not post-rest
        assert _row(state, 102, 1)['is_post_rest_day'] == 0
        # stage 3 follows stage 2 by two days: post-rest
        assert _row(state, 103, 1)['is_post_rest_day'] == 1

    def test_team_features(self, state_and_quality):
        state, _ = state_and_quality
        # After stage 1: team 1 holds ranks 1 (r1) and 2 (r2)
        r1 = _row(state, 102, 1)
        r2 = _row(state, 102, 2)
        assert r1['team_best_gc_rank'] == 1
        assert r1['is_team_gc_leader'] == 1
        assert r2['is_team_gc_leader'] == 0
        assert r1['teammates_top10_count'] == 1  # excludes self
        assert r2['team_has_gc_top5'] == 1
        # rider 7 has no team: neutral team state
        r7 = _row(state, 102, 7)
        assert pd.isna(r7['team_best_gc_rank'])
        assert r7['is_team_gc_leader'] == 0

    def test_gc_row_holds_state_after_final_stage(self, state_and_quality):
        state, _ = state_and_quality
        gc1 = _row(state, GC_COMP_ID, 1)
        assert gc1['stages_completed'] == 3
        assert gc1['pct_race_complete'] == pytest.approx(1.0)
        assert gc1['cum_time_raced_s'] == pytest.approx(33005.0)
        assert gc1['gc_rank_current'] == 1
        gc6 = _row(state, GC_COMP_ID, 6)
        assert gc6['gc_rank_current'] == 5
        assert gc6['gc_gap_to_leader_s'] == pytest.approx(105.0)

    def test_tied_times_break_by_countback(self):
        results = _results()
        # Tie rider 4 to rider 3 on stage 1 (same cumulative time); rider 3
        # has the better stage place so countback puts them ahead.
        results.loc[
            (results['competition_id'] == 101) & (results['rider_id'] == 4),
            'time_gap',
        ] = 20.0
        state, _ = compute_race_state(
            STAGES, results, gc_competition_id=GC_COMP_ID, race_id=1
        )
        r3 = _row(state, 102, 3)
        r4 = _row(state, 102, 4)
        assert r3['gc_rank_current'] == 3
        assert r4['gc_rank_current'] == 4
        assert r3['gc_gap_to_leader_s'] == pytest.approx(20.0)
        assert r4['gc_gap_to_leader_s'] == pytest.approx(20.0)
        # Strict ranking: exactly one race leader per competition
        for comp in (102, 103, GC_COMP_ID):
            leaders = state[state['competition_id'] == comp]['is_race_leader']
            assert leaders.sum() == 1

    def test_null_winning_time_truncates_later_stages(self):
        stages = STAGES.copy()
        stages.loc[stages['competition_id'] == 102, 'winning_time'] = np.nan
        state, quality = compute_race_state(
            stages, _results(), gc_competition_id=GC_COMP_ID, race_id=1
        )
        # state after stage 1 still exists (keyed to stage 2)...
        assert (state['competition_id'] == 102).sum() > 0
        # ...but nothing after the broken stage
        assert (state['competition_id'] == 103).sum() == 0
        assert (state['competition_id'] == GC_COMP_ID).sum() == 0
        assert quality['truncated_at_seq'] == 2

    def test_empty_inputs(self):
        state, quality = compute_race_state(
            STAGES.iloc[:0], pd.DataFrame(), gc_competition_id=None
        )
        assert state.empty
        assert quality['n_state_rows'] == 0


@pytest.mark.unit
class TestValidateReconstruction:

    def test_consistent_gc_validates_clean(self, state_and_quality):
        state, _ = state_and_quality
        v = validate_reconstruction(state, FINAL_GC, GC_COMP_ID)
        assert v['gc_validated'] == 1
        assert v['is_suspect'] == 0
        assert v['gc_winner_match'] == 1
        assert v['top10_mean_abs_err_s'] == pytest.approx(0.0)
        assert v['n_matched_top10'] == 6

    def test_corrupt_gc_is_suspect(self, state_and_quality):
        state, _ = state_and_quality
        corrupt = FINAL_GC.copy()
        corrupt['time_gap'] = corrupt['time_gap'] + 5000.0
        corrupt.loc[corrupt['place'] == 1, 'time_gap'] = 0.0
        v = validate_reconstruction(state, corrupt, GC_COMP_ID)
        assert v['gc_validated'] == 1
        assert v['is_suspect'] == 1

    def test_too_few_matches_is_unvalidated(self, state_and_quality):
        state, _ = state_and_quality
        v = validate_reconstruction(state, FINAL_GC.head(3), GC_COMP_ID)
        assert v['gc_validated'] == 0
        assert v['is_suspect'] == 0


@pytest.mark.unit
class TestTrainingIntegration:

    def test_column_lists_in_sync(self):
        assert STATE_FEATURE_COLUMNS == CyclingDataPipeline.RACE_STATE_FEATURE_COLS

    def test_imputation_fills_all_state_columns(self):
        df = pd.DataFrame(
            {c: [np.nan, 1.0] for c in STATE_FEATURE_COLUMNS}
        )
        df['race_state_missing'] = [1, 0]
        out = FeatureEngineer().apply_imputation(df)
        for c in STATE_FEATURE_COLUMNS:
            assert out[c].notna().all(), f"{c} still has NaN after imputation"
        # meaningful values untouched
        assert out.loc[1, 'gc_rank_current'] == 1.0
        # missing-state defaults are not the race-leader signature
        assert out.loc[0, 'gc_gap_to_leader_s'] > 0
        assert out.loc[0, 'is_race_leader'] == 0


@pytest.mark.unit
class TestBuilder:

    @pytest.fixture
    def db_path(self, tmp_path):
        path = tmp_path / "test.db"
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE races (
                id INTEGER PRIMARY KEY, fc_race_id TEXT, name TEXT,
                year INTEGER, date DATE, category TEXT, is_stage_race BOOLEAN
            );
            CREATE TABLE competitions (
                id INTEGER PRIMARY KEY, race_id INTEGER, name TEXT,
                stage_number INTEGER, competition_type TEXT, date DATE,
                winning_time REAL
            );
            CREATE TABLE rider_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition_id INTEGER, rider_id INTEGER, team_id INTEGER,
                place INTEGER, time_gap REAL, place_bucket INTEGER,
                percentile REAL
            );
        """)
        conn.execute(
            "INSERT INTO races VALUES (1, '9', 'Test Tour', 2024, '2024-06-01', 'wt', 1)"
        )
        for _, s in STAGES.iterrows():
            conn.execute(
                "INSERT INTO competitions VALUES (?, 1, ?, ?, 'stage', ?, ?)",
                (int(s['competition_id']), f"Stage: {s['stage_number']:02d}",
                 int(s['stage_number']), s['date'], s['winning_time']),
            )
        conn.execute(
            "INSERT INTO competitions VALUES (?, 1, 'GC', NULL, 'gc', '2024-06-04', NULL)",
            (GC_COMP_ID,),
        )
        for _, r in _results().iterrows():
            conn.execute(
                "INSERT INTO rider_results "
                "(competition_id, rider_id, team_id, place, time_gap, place_bucket, percentile) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (int(r['competition_id']), int(r['rider_id']),
                 None if pd.isna(r['team_id']) else int(r['team_id']),
                 int(r['place']), r['time_gap'], int(r['place_bucket']),
                 r['percentile']),
            )
        for _, g in FINAL_GC.iterrows():
            conn.execute(
                "INSERT INTO rider_results "
                "(competition_id, rider_id, team_id, place, time_gap, place_bucket, percentile) "
                "VALUES (?, ?, NULL, ?, ?, 0, 50.0)",
                (GC_COMP_ID, int(g['rider_id']), int(g['place']), g['time_gap']),
            )
        conn.commit()
        conn.close()
        return str(path)

    def test_build_write_and_incremental_skip(self, db_path):
        builder = StageRaceStateBuilder(db_path=db_path)
        summary = builder.run()
        assert summary['races_processed'] == 1
        assert summary['suspect_races'] == 0
        assert summary['state_rows'] > 0

        conn = sqlite3.connect(db_path)
        n_rows = conn.execute(
            "SELECT COUNT(*) FROM rider_race_state"
        ).fetchone()[0]
        # stage 2: 7 riders, stage 3: 6, gc: 6
        assert n_rows == 19
        quality = conn.execute(
            "SELECT gc_validated, is_suspect, gc_winner_match FROM race_state_quality "
            "WHERE race_id = 1"
        ).fetchone()
        assert quality == (1, 0, 1)

        # Incremental rerun: nothing changed, nothing reprocessed
        assert builder.run()['races_processed'] == 0

        # A new stage appearing (in-progress race) triggers reprocessing
        conn.execute(
            "INSERT INTO competitions VALUES (105, 1, 'Stage: 04', 4, 'stage', "
            "'2024-06-05', 13000.0)"
        )
        for rid, gap in [(1, 0.0), (2, 4.0), (3, 9.0), (4, 14.0), (5, 19.0), (6, 24.0)]:
            conn.execute(
                "INSERT INTO rider_results "
                "(competition_id, rider_id, team_id, place, time_gap, place_bucket, percentile) "
                "VALUES (105, ?, NULL, 1, ?, 1, 50.0)",
                (rid, gap),
            )
        conn.commit()
        conn.close()
        assert builder.run()['races_processed'] == 1

    def test_suspect_race_writes_no_rows(self, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE rider_results SET time_gap = time_gap + 5000 "
            "WHERE competition_id = ? AND place > 1",
            (GC_COMP_ID,),
        )
        conn.commit()
        conn.close()

        builder = StageRaceStateBuilder(db_path=db_path)
        summary = builder.run()
        assert summary['suspect_races'] == 1
        assert summary['state_rows'] == 0

        conn = sqlite3.connect(db_path)
        assert conn.execute(
            "SELECT COUNT(*) FROM rider_race_state"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT is_suspect FROM race_state_quality WHERE race_id = 1"
        ).fetchone()[0] == 1
        conn.close()
