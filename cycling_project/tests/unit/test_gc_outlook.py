"""Unit tests for the GC outlook head (state-aware final-GC prediction)."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from cycling_project.prediction_tools.gc_outlook import (
    GROUP_FACTOR,
    GCOutlookHead,
    build_checkpoint_frame,
)
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    ensure_schema,
    log_predictions,
)


class StubBucket:
    """predict_continuous returns the frame's stub_score column."""

    def predict_continuous(self, df):
        return df['stub_score'].values.astype(float)


class StubContender:
    """Fixed padded-to-8 probability rows: 0.4/0.3/0.2/0.05/0.05."""

    def predict_proba(self, df):
        proba = np.zeros((len(df), 8))
        proba[:, 0] = 0.40
        proba[:, 1] = 0.30
        proba[:, 2] = 0.20
        proba[:, 3] = 0.05
        proba[:, 4] = 0.05
        return proba


def _frame(n=20, n_missing=3):
    df = pd.DataFrame({
        'rider_id': np.arange(1, n + 1),
        'rider_name': [f'r{i}' for i in range(1, n + 1)],
        'stub_score': np.linspace(0.5, 5.5, n),  # lower = better
        'race_state_missing': [0] * (n - n_missing) + [1] * n_missing,
        'gc_rank_current': np.arange(1, n + 1, dtype=float),
        'gc_gap_to_leader_s': np.arange(0, n * 10, 10, dtype=float),
        'stages_completed': 4,
    })
    return df


@pytest.mark.unit
class TestGCOutlookPredict:

    def test_filters_missing_state_riders(self):
        head = GCOutlookHead(StubBucket(), StubContender())
        out = head.predict(_frame(n=20, n_missing=3))
        assert len(out) == 17
        assert set(out['rider_id']) == set(range(1, 18))

    def test_cumulative_probabilities_for_contenders_only(self):
        head = GCOutlookHead(StubBucket(), StubContender())
        out = head.predict(_frame(n=20, n_missing=0), top_n=15)
        contenders = out[out['is_contender']]
        rest = out[~out['is_contender']]
        assert len(contenders) == 15
        assert len(rest) == 5
        assert np.allclose(contenders['gc_outlook_win_p'], 0.40)
        assert np.allclose(contenders['gc_outlook_podium_p'], 0.70)
        assert np.allclose(contenders['gc_outlook_top5_p'], 0.90)
        assert np.allclose(contenders['gc_outlook_top15_p'], 0.95)
        assert rest['gc_outlook_win_p'].isna().all()

    def test_ranking_and_passthrough(self):
        head = GCOutlookHead(StubBucket(), StubContender())
        out = head.predict(_frame(n=10, n_missing=0))
        # stub_score ascends with rider_id, so outlook order == rider order
        assert out['outlook_rank'].tolist() == list(range(1, 11))
        assert out['rider_id'].tolist() == list(range(1, 11))
        assert out['gc_rank_current'].iloc[0] == 1.0
        assert out['gc_gap_to_leader_s'].iloc[2] == 20.0
        assert (out['stages_completed'] == 4).all()

    def test_empty_when_no_state(self):
        head = GCOutlookHead(StubBucket(), StubContender())
        out = head.predict(_frame(n=5, n_missing=5))
        assert out.empty


@pytest.mark.unit
class TestCheckpointFrameAssembly:

    def test_synthetic_groups_and_state_flag(self):
        gc_base = pd.DataFrame({
            'rider_id': [1, 2],
            'competition_id': [500, 500],
            'competition_date': pd.to_datetime(['2024-06-10'] * 2),
            'place_bucket': [0, 3],
            'some_feature': [1.0, 2.0],
        })
        states = pd.DataFrame({
            'rider_id': [1, 1, 2, 2],
            'gc_competition_id': [500] * 4,
            'stages_completed': [1, 2, 1, 2],
            'gc_rank_current': [1.0, 1.0, 2.0, 2.0],
            'pct_race_complete': [0.33, 0.67, 0.33, 0.67],
        })
        frame = build_checkpoint_frame(gc_base, states)
        assert len(frame) == 4
        assert set(frame['competition_id']) == {
            500 * GROUP_FACTOR + 1, 500 * GROUP_FACTOR + 2
        }
        assert (frame['race_state_missing'] == 0).all()
        assert 'gc_competition_id' not in frame.columns
        # target replicated per checkpoint
        r1 = frame[frame['rider_id'] == 1]
        assert (r1['place_bucket'] == 0).all()


@pytest.mark.unit
def test_prediction_log_gc_outlook_columns(tmp_path):
    conn = sqlite3.connect(tmp_path / "log.db")
    ensure_schema(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(prediction_log)")}
    for c in ('gc_outlook_win_p', 'gc_outlook_podium_p',
              'gc_outlook_top5_p', 'gc_outlook_top15_p'):
        assert c in cols
    log_predictions(conn, [
        PredictionLogRow(
            fc_race_id='15', year=2026, rider_id=1,
            state_through_stage=3, gc_outlook_win_p=0.41,
            gc_outlook_podium_p=0.7,
        ),
    ])
    row = conn.execute(
        "SELECT gc_outlook_win_p, gc_outlook_podium_p, gc_outlook_top5_p "
        "FROM prediction_log"
    ).fetchone()
    assert row == (0.41, 0.7, None)
    conn.close()
