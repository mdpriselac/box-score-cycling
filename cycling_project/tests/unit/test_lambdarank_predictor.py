"""Unit tests for the LambdaRank probability predictor helpers and
prediction_log schema.

These avoid touching the real DB or LightGBM — they exercise the pure
functions that encode behavior we care about: relevance mapping,
per-group softmax normalization, and log-row serialization.
"""

import json
import sqlite3

import numpy as np
import pandas as pd
import pytest

from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    _relevance_from_bucket,
    _softmax_by_group,
)
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    ensure_schema,
    log_predictions,
    resolve_competition_id,
)


@pytest.mark.unit
class TestRelevanceMapping:
    def test_winner_has_max_relevance(self):
        rel = _relevance_from_bucket(np.array([0]))
        assert rel[0] == 6

    def test_finisher_is_zero(self):
        rel = _relevance_from_bucket(np.array([6]))
        assert rel[0] == 0

    def test_dnf_is_zero(self):
        rel = _relevance_from_bucket(np.array([7]))
        assert rel[0] == 0

    def test_full_ladder(self):
        rel = _relevance_from_bucket(np.array([0, 1, 2, 3, 4, 5, 6, 7]))
        assert rel.tolist() == [6, 5, 4, 3, 2, 1, 0, 0]

    def test_clips_out_of_range(self):
        # Defensive: negative or absurdly large buckets shouldn't break.
        rel = _relevance_from_bucket(np.array([-1, 99]))
        assert rel[0] == 6  # -1 clipped to 0 → winner relevance
        assert rel[1] == 0  # 99 clipped to 7 → DNF → zero


@pytest.mark.unit
class TestSoftmaxByGroup:
    def test_single_group_sums_to_one(self):
        probs = _softmax_by_group(
            np.array([1.0, 2.0, 3.0]),
            np.array([1, 1, 1]),
        )
        assert probs.sum() == pytest.approx(1.0)

    def test_multi_group_each_sums_to_one(self):
        probs = _softmax_by_group(
            np.array([1.0, 2.0, 3.0, 1.0, 1.0]),
            np.array([1, 1, 1, 2, 2]),
        )
        assert probs[:3].sum() == pytest.approx(1.0)
        assert probs[3:].sum() == pytest.approx(1.0)

    def test_higher_score_higher_prob(self):
        probs = _softmax_by_group(
            np.array([1.0, 2.0, 3.0]),
            np.array([1, 1, 1]),
        )
        assert probs[2] > probs[1] > probs[0]

    def test_temperature_sharpens(self):
        scores = np.array([1.0, 2.0, 3.0])
        groups = np.array([1, 1, 1])
        soft = _softmax_by_group(scores, groups, temperature=1.0)
        sharp = _softmax_by_group(scores, groups, temperature=0.1)
        # Lower temperature should concentrate probability on the max.
        assert sharp[2] > soft[2]

    def test_scale_invariance(self):
        """Adding a constant to all scores within a group should not
        change the softmax output (numerical stability guarantee)."""
        g = np.array([1, 1, 1, 1])
        a = _softmax_by_group(np.array([0.0, 1.0, 2.0, 3.0]), g)
        b = _softmax_by_group(np.array([100.0, 101.0, 102.0, 103.0]), g)
        np.testing.assert_allclose(a, b, rtol=1e-10)


@pytest.mark.unit
class TestPredictionLogRow:
    def test_as_row_serializes_reference_ids_as_json(self):
        row = PredictionLogRow(
            fc_race_id='56', year=2026, rider_id=42,
            reference_comp_ids=[1, 2, 3],
        )
        payload = row.as_row()
        assert json.loads(payload['reference_comp_ids']) == [1, 2, 3]

    def test_as_row_coerces_nan_to_none(self):
        row = PredictionLogRow(
            fc_race_id='1', year=2026, rider_id=1,
            multiclass_win_p=float('nan'),
        )
        payload = row.as_row()
        assert payload['multiclass_win_p'] is None

    def test_as_row_coerces_types(self):
        row = PredictionLogRow(
            fc_race_id=56, year='2026', rider_id=42.0,  # deliberately wrong types
            multiclass_win_p=0.5,
        )
        payload = row.as_row()
        assert payload['fc_race_id'] == '56'
        assert payload['year'] == 2026
        assert payload['rider_id'] == 42
        assert payload['multiclass_win_p'] == 0.5


@pytest.mark.unit
class TestPredictionLogSchema:
    def _fresh_conn(self):
        conn = sqlite3.connect(':memory:')
        # Create the minimum referenced tables so our inserts don't fail
        # (FK constraints aren't enforced unless we turn them on, so schema
        # alone is enough for insert-side tests).
        conn.execute("""
            CREATE TABLE competitions (
                id INTEGER PRIMARY KEY,
                race_id INTEGER,
                stage_number INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE races (
                id INTEGER PRIMARY KEY,
                fc_race_id TEXT,
                year INTEGER,
                category TEXT
            )
        """)
        conn.execute("CREATE TABLE riders (id INTEGER PRIMARY KEY)")
        return conn

    def test_ensure_schema_creates_table(self):
        conn = self._fresh_conn()
        ensure_schema(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='prediction_log'"
        )
        assert cur.fetchone() is not None

    def test_log_predictions_inserts_all_columns(self):
        conn = self._fresh_conn()
        rows = [
            PredictionLogRow(
                fc_race_id='9', year=2026, rider_id=1,
                multiclass_win_p=0.15, multiclass_podium_p=0.40,
                lambdarank_win_p=0.12, lambdarank_podium_p=0.37,
                lambdarank_temperature=1.5,
                reference_comp_ids=[100, 200],
                model_version='2026-04-18T10:00:00',
            ),
            PredictionLogRow(
                fc_race_id='9', year=2026, rider_id=2,
                multiclass_win_p=0.05, lambdarank_win_p=0.03,
            ),
        ]
        n = log_predictions(conn, rows)
        assert n == 2

        cur = conn.execute(
            "SELECT rider_id, multiclass_win_p, lambdarank_win_p, reference_comp_ids "
            "FROM prediction_log ORDER BY rider_id"
        )
        records = cur.fetchall()
        assert records[0][0] == 1
        assert records[0][1] == pytest.approx(0.15)
        assert records[0][2] == pytest.approx(0.12)
        assert json.loads(records[0][3]) == [100, 200]

    def test_resolve_competition_id_returns_none_when_missing(self):
        conn = self._fresh_conn()
        ensure_schema(conn)
        assert resolve_competition_id(conn, '999', 2030, None) is None

    def test_resolve_competition_id_finds_matching_one_day_race(self):
        conn = self._fresh_conn()
        ensure_schema(conn)
        conn.execute("INSERT INTO races (id, fc_race_id, year) VALUES (1, '56', 2026)")
        conn.execute(
            "INSERT INTO competitions (id, race_id, stage_number) VALUES (100, 1, NULL)"
        )
        conn.commit()
        assert resolve_competition_id(conn, '56', 2026, None) == 100

    def test_resolve_competition_id_picks_correct_stage(self):
        conn = self._fresh_conn()
        ensure_schema(conn)
        conn.execute("INSERT INTO races (id, fc_race_id, year) VALUES (1, '123', 2025)")
        conn.executemany(
            "INSERT INTO competitions (id, race_id, stage_number) VALUES (?, 1, ?)",
            [(200, 1), (201, 2), (202, 3)],
        )
        conn.commit()
        # Stage 2 should resolve to comp 201, not 200 or 202.
        assert resolve_competition_id(conn, '123', 2025, 2) == 201
