"""Idempotency and migration coverage for the production prediction log."""

import sqlite3

import pytest

from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    PredictionRunIdentity,
    SCHEMA_SQL,
    ensure_schema,
    log_predictions,
)


def _row(*, model="model-a", win=0.1):
    return PredictionLogRow(
        fc_race_id="17",
        year=2026,
        stage_number=9,
        rider_id=101,
        rider_name="Rider One",
        reference_comp_ids=[30, 10],
        model_version=model,
        state_through_stage=8,
        multiclass_win_p=win,
    )


@pytest.mark.unit
def test_fresh_db_exact_rerun_updates_in_place():
    conn = sqlite3.connect(":memory:")

    assert log_predictions(conn, [_row(win=0.1)]) == 1
    assert log_predictions(conn, [_row(win=0.25)]) == 1

    stored = conn.execute(
        "SELECT run_key, multiclass_win_p FROM prediction_log"
    ).fetchall()
    assert len(stored) == 1
    assert stored[0][0].startswith("prediction-run-v1:")
    assert stored[0][1] == pytest.approx(0.25)


@pytest.mark.unit
def test_run_key_is_deterministic_and_reference_order_independent():
    first = PredictionRunIdentity(
        fc_race_id="17", year=2026, stage_number=9,
        model_version="model-a", reference_comp_ids=[30, 10, 10],
        scenario_key="mountain", input_fingerprint="startlist-sha",
    )
    reordered = PredictionRunIdentity(
        fc_race_id="17", year=2026, stage_number=9,
        model_version="model-a", reference_comp_ids=[10, 30],
        scenario_key="mountain", input_fingerprint="startlist-sha",
    )
    assert first.run_key == reordered.run_key


@pytest.mark.unit
@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    [("scenario_key", "steep-finish"), ("model_version", "model-b")],
)
def test_changed_scenario_or_model_creates_distinct_run(
    changed_field, changed_value
):
    conn = sqlite3.connect(":memory:")
    base_args = dict(
        fc_race_id="17", year=2026, stage_number=9,
        model_version="model-a", reference_comp_ids=[10, 30],
        state_through_stage=8, scenario_key="mountain",
    )
    first = PredictionRunIdentity(**base_args)
    changed_args = {**base_args, changed_field: changed_value}
    second = PredictionRunIdentity(**changed_args)
    second_row = _row(model=second.model_version)

    log_predictions(conn, [_row()], run_identity=first)
    log_predictions(conn, [second_row], run_identity=second)

    assert conn.execute("SELECT COUNT(*) FROM prediction_log").fetchone()[0] == 2


@pytest.mark.unit
def test_explicit_input_fingerprint_controls_replacement_boundary():
    conn = sqlite3.connect(":memory:")
    common = dict(
        fc_race_id="17", year=2026, stage_number=9,
        model_version="model-a", reference_comp_ids=[10, 30],
        state_through_stage=8, scenario_key="mountain",
    )
    startlist_a = PredictionRunIdentity(**common, input_fingerprint="sha-a")
    startlist_b = PredictionRunIdentity(**common, input_fingerprint="sha-b")

    log_predictions(conn, [_row(win=0.1)], run_identity=startlist_a)
    log_predictions(conn, [_row(win=0.2)], run_identity=startlist_a)
    log_predictions(conn, [_row(win=0.3)], run_identity=startlist_b)

    values = conn.execute(
        "SELECT multiclass_win_p FROM prediction_log ORDER BY multiclass_win_p"
    ).fetchall()
    assert values == [(0.2,), (0.3,)]


@pytest.mark.unit
def test_migration_preserves_unkeyed_history_and_keys_new_writes():
    conn = sqlite3.connect(":memory:")
    old_schema = SCHEMA_SQL.replace("    run_key TEXT,\n", "")
    conn.execute(old_schema)
    conn.execute(
        """
        INSERT INTO prediction_log
            (fc_race_id, year, stage_number, rider_id, model_version)
        VALUES ('17', 2026, 9, 101, 'model-a')
        """
    )
    conn.commit()

    ensure_schema(conn)
    assert "run_key" in {
        item[1] for item in conn.execute("PRAGMA table_info(prediction_log)")
    }
    assert conn.execute(
        "SELECT run_key FROM prediction_log WHERE id = 1"
    ).fetchone() == (None,)

    log_predictions(conn, [_row(win=0.1)])
    log_predictions(conn, [_row(win=0.2)])
    rows = conn.execute(
        "SELECT run_key, multiclass_win_p FROM prediction_log ORDER BY id"
    ).fetchall()
    assert rows[0] == (None, None)
    assert len(rows) == 2
    assert rows[1][1] == pytest.approx(0.2)


@pytest.mark.unit
def test_ignore_keeps_first_opinion_and_error_exposes_duplicate():
    conn = sqlite3.connect(":memory:")
    log_predictions(conn, [_row(win=0.1)])

    assert log_predictions(conn, [_row(win=0.2)], on_conflict="ignore") == 0
    assert conn.execute(
        "SELECT multiclass_win_p FROM prediction_log"
    ).fetchone()[0] == pytest.approx(0.1)
    with pytest.raises(sqlite3.IntegrityError):
        log_predictions(conn, [_row(win=0.3)], on_conflict="error")


@pytest.mark.unit
def test_explicit_identity_rejects_mixed_race_batch():
    conn = sqlite3.connect(":memory:")
    identity = PredictionRunIdentity(fc_race_id="17", year=2026, stage_number=9)
    wrong_race = _row()
    wrong_race.fc_race_id = "99"

    with pytest.raises(ValueError, match="race/year/stage"):
        log_predictions(conn, [wrong_race], run_identity=identity)
