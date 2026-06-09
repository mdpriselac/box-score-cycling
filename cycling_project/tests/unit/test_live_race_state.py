"""Unit tests for live (inference-time) stage-race state."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from cycling_project.engineering_tools.stage_race_state import (
    STATE_FEATURE_COLUMNS,
    compute_race_state,
)
from cycling_project.prediction_tools.feature_engineering import FeatureEngineer
from cycling_project.prediction_tools.live_race_state import (
    _parse_stage_number,
    attach_race_state,
    build_live_state,
)
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    ensure_schema,
    log_predictions,
)


def _stage_results(rows):
    return pd.DataFrame(
        rows,
        columns=[
            'rider_fc_id', 'rider_id', 'rider_name', 'team_name',
            'place', 'time_gap', 'place_bucket',
        ],
    )


@pytest.fixture
def completed_two_stages():
    """Two completed stages; rider fc=400 is NOT matched to the DB."""
    s1 = _stage_results([
        ('100', 1, 'Alpha', 'Team A', 1, 0.0, 0),
        ('200', 2, 'Bravo', 'Team A', 2, 10.0, 1),
        ('400', np.nan, 'Delta', 'Team B', 3, 20.0, 1),
        ('300', 3, 'Charlie', 'Team B', 4, 30.0, 2),
    ])
    s2 = _stage_results([
        ('400', np.nan, 'Delta', 'Team B', 1, 0.0, 0),
        ('100', 1, 'Alpha', 'Team A', 2, 5.0, 1),
        ('200', 2, 'Bravo', 'Team A', 3, 8.0, 1),
        ('300', 3, 'Charlie', 'Team B', 4, 12.0, 1),
    ])
    return [
        {'seq': 1, 'winning_time': 10000.0, 'results': s1},
        {'seq': 2, 'winning_time': 11000.0, 'results': s2},
    ]


@pytest.mark.unit
class TestBuildLiveState:

    def test_state_after_completed_stages(self, completed_two_stages):
        state, info = build_live_state(completed_two_stages, total_stages=8)
        assert info['available']
        assert info['stages_completed'] == 2
        assert info['riders_in_standings'] == 4

        # Cumulative: Alpha 21005, Bravo 21018, Delta 21020, Charlie 21042
        assert info['leader_name'] == 'Alpha'

        # Only DB-matched riders come back (unmatched Delta influenced
        # standings but has no rider_id to merge onto a prediction frame)
        assert set(state['rider_id']) == {1, 2, 3}

        alpha = state[state['rider_id'] == 1].iloc[0]
        assert alpha['gc_rank_current'] == 1
        assert alpha['is_race_leader'] == 1
        assert alpha['stages_completed'] == 2
        # mid-race denominator comes from the SCHEDULED count
        assert alpha['pct_race_complete'] == pytest.approx(2 / 8)

        # Charlie sits BEHIND unmatched Delta: rank 4, not 3
        charlie = state[state['rider_id'] == 3].iloc[0]
        assert charlie['gc_rank_current'] == 4
        assert charlie['gc_gap_to_leader_s'] == pytest.approx(37.0)

    def test_team_features_use_scraped_team_names(self, completed_two_stages):
        state, _ = build_live_state(completed_two_stages, total_stages=8)
        bravo = state[state['rider_id'] == 2].iloc[0]
        # Team A holds ranks 1 (Alpha) and 2 (Bravo)
        assert bravo['team_best_gc_rank'] == 1
        assert bravo['is_team_gc_leader'] == 0
        assert bravo['teammates_top10_count'] == 1

    def test_empty_input_returns_none(self):
        state, info = build_live_state([], total_stages=8)
        assert state is None
        assert not info['available']
        assert info['reason']

    def test_missing_winning_time_truncates(self, completed_two_stages):
        completed_two_stages[0]['winning_time'] = None
        state, info = build_live_state(completed_two_stages, total_stages=8)
        assert state is None
        assert 'truncated' in info['reason']


@pytest.mark.unit
class TestAttachRaceState:

    def _pred_df(self):
        return pd.DataFrame({
            'rider_id': [1, 2, 99],
            'some_feature': [0.1, 0.2, 0.3],
        })

    def test_attach_none_state_yields_nan_and_missing_flag(self):
        out = attach_race_state(self._pred_df(), None)
        assert (out['race_state_missing'] == 1).all()
        for col in STATE_FEATURE_COLUMNS:
            assert out[col].isna().all()

    def test_attach_merges_by_rider(self, completed_two_stages):
        state, _ = build_live_state(completed_two_stages, total_stages=8)
        out = attach_race_state(self._pred_df(), state)
        assert len(out) == 3
        r1 = out[out['rider_id'] == 1].iloc[0]
        assert r1['race_state_missing'] == 0
        assert r1['gc_rank_current'] == 1
        # rider 99 wasn't in the race results: missing state
        r99 = out[out['rider_id'] == 99].iloc[0]
        assert r99['race_state_missing'] == 1
        assert pd.isna(r99['gc_rank_current'])


@pytest.mark.unit
class TestStageNumberParsing:

    def test_parse_variants(self):
        assert _parse_stage_number('Stage 5 | Foo - Bar', '05', 9) == 5
        assert _parse_stage_number('Prologue', None, 1) == 0
        assert _parse_stage_number('', '12', 3) == 12
        assert _parse_stage_number('Something odd', None, 7) == 7


@pytest.mark.unit
class TestFeatureMatrixFallback:
    """A state-trained model must see neutral defaults — not zeros — when a
    prediction frame lacks the state columns entirely."""

    def _training_frame(self, with_state: bool) -> pd.DataFrame:
        n = 6
        data = {}
        for col in FeatureEngineer.RIDER_NUMERIC_FEATURES:
            data[col] = np.linspace(1, 3, n)
        for col in FeatureEngineer.FIELD_NUMERIC_FEATURES:
            data[col] = np.linspace(2, 4, n)
        for col in FeatureEngineer.RACE_PROFILE_FEATURES:
            data[col] = np.full(n, 0.2)
        data.update({
            'rider_id': range(n), 'rider_name': ['x'] * n,
            'competition_id': [1] * n, 'competition_name': ['c'] * n,
            'competition_date': ['2024-01-01'] * n,
            'competition_type': ['stage'] * n, 'race_category': ['wt'] * n,
            'best_profile': ['sprint'] * n,
            'race_dominant_profile': ['sprint'] * n,
            'place_bucket': [0, 1, 2, 3, 4, 5],
        })
        if with_state:
            for col in STATE_FEATURE_COLUMNS:
                data[col] = np.full(n, 1.0)
            data['race_state_missing'] = np.zeros(n)
        return pd.DataFrame(data)

    def test_missing_state_columns_fill_with_defaults_not_zeros(self):
        eng = FeatureEngineer()
        eng.fit_transform(self._training_frame(with_state=True))
        assert 'gc_gap_to_leader_s' in eng.get_feature_columns()

        # Inference frame WITHOUT state columns (e.g. a caller that didn't
        # go through attach_race_state)
        inference = eng.transform(self._training_frame(with_state=False))
        X, _ = eng.get_feature_matrix(inference)
        assert X['gc_gap_to_leader_s'].iloc[0] == pytest.approx(
            FeatureEngineer.RACE_STATE_DEFAULTS['gc_gap_to_leader_s']
        )
        assert X['is_race_leader'].iloc[0] == 0.0
        assert X['race_state_missing'].iloc[0] == 1.0
        # non-state columns keep the zero fallback
        assert X['gc_gap_to_leader_s'].iloc[0] != 0.0


@pytest.mark.unit
class TestPredictionLogMigration:

    def test_old_schema_gains_state_column_and_roundtrips(self, tmp_path):
        db = tmp_path / "log.db"
        conn = sqlite3.connect(db)
        # Simulate the pre-existing table WITHOUT state_through_stage
        conn.execute("""
            CREATE TABLE prediction_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                predicted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                fc_race_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                stage_number INTEGER,
                competition_id INTEGER,
                rider_id INTEGER NOT NULL,
                rider_name TEXT,
                reference_comp_ids TEXT,
                model_version TEXT,
                multiclass_win_p REAL,
                multiclass_podium_p REAL,
                multiclass_top5_p REAL,
                multiclass_top15_p REAL,
                lambdarank_win_p REAL,
                lambdarank_podium_p REAL,
                lambdarank_temperature REAL
            );
        """)
        conn.commit()

        ensure_schema(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(prediction_log)")}
        assert 'state_through_stage' in cols

        n = log_predictions(conn, [
            PredictionLogRow(
                fc_race_id='17', year=2026, rider_id=1,
                stage_number=5, state_through_stage=4,
            ),
            PredictionLogRow(fc_race_id='17', year=2026, rider_id=2),
        ])
        assert n == 2
        rows = conn.execute(
            "SELECT rider_id, state_through_stage FROM prediction_log ORDER BY rider_id"
        ).fetchall()
        assert rows == [(1, 4), (2, None)]
        conn.close()


@pytest.mark.unit
def test_total_stages_param_on_compute_race_state():
    stages = pd.DataFrame({
        'competition_id': [11, 12],
        'stage_number': [1, 2],
        'date': ['2026-06-07', '2026-06-08'],
        'winning_time': [10000.0, 11000.0],
    })
    results = pd.DataFrame({
        'competition_id': [11, 11, 12, 12],
        'rider_id': [1, 2, 1, 2],
        'team_id': [1, 1, 1, 1],
        'place': [1, 2, 1, 2],
        'time_gap': [0.0, 5.0, 0.0, 3.0],
        'place_bucket': [0, 1, 0, 1],
        'percentile': [100.0, 50.0, 100.0, 50.0],
    })
    state, _ = compute_race_state(
        stages, results, gc_competition_id=-1, total_stages=8
    )
    virtual = state[state['competition_id'] == -1]
    assert np.allclose(virtual['pct_race_complete'], 2 / 8)
    # without the override, the denominator is the provided stage count
    state2, _ = compute_race_state(stages, results, gc_competition_id=-1)
    virtual2 = state2[state2['competition_id'] == -1]
    assert np.allclose(virtual2['pct_race_complete'], 1.0)
