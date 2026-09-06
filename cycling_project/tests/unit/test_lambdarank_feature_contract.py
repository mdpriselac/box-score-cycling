import json

import numpy as np
import pandas as pd
import pytest

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline
from cycling_project.prediction_tools.lambdarank_feature_contract import (
    LAMBDARANK_EXCLUDED_COLUMNS,
    assert_lambdarank_contract_compatible,
    assert_stateless_feature_columns,
    build_lambdarank_feature_view,
    make_lambdarank_contract_metadata,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools import train_production_model


@pytest.mark.unit
def test_stateless_view_removes_every_race_state_field_without_mutating_source():
    source = pd.DataFrame({
        "competition_id": [1],
        "rider_id": [10],
        "base_feature": [3.5],
        **{column: [1.0] for column in LAMBDARANK_EXCLUDED_COLUMNS},
    })

    view = build_lambdarank_feature_view(source)

    assert "base_feature" in view
    assert not set(LAMBDARANK_EXCLUDED_COLUMNS).intersection(view.columns)
    assert set(LAMBDARANK_EXCLUDED_COLUMNS).issubset(source.columns)


@pytest.mark.unit
def test_contract_rejects_state_and_ordered_schema_changes():
    state_column = CyclingDataPipeline.RACE_STATE_FEATURE_COLS[0]
    with pytest.raises(ValueError, match="within-race state"):
        assert_stateless_feature_columns(["age", state_column])

    expected = make_lambdarank_contract_metadata(["age", "form"])
    reordered = make_lambdarank_contract_metadata(["form", "age"])
    with pytest.raises(ValueError, match="feature contract mismatch"):
        assert_lambdarank_contract_compatible(expected, reordered)


@pytest.mark.unit
def test_oof_lambdarank_always_receives_stateless_frames(monkeypatch):
    state_column = CyclingDataPipeline.RACE_STATE_FEATURE_COLS[0]
    frame = pd.DataFrame({
        "competition_id": np.repeat(np.arange(1, 6), 2),
        "competition_date": pd.date_range("2025-01-01", periods=10),
        "place_bucket": np.tile([0, 1], 5),
        state_column: np.arange(10),
        "race_state_missing": 0,
    })

    class FakeLambdaRank:
        def __init__(self, _config):
            pass

        def train(self, train, val, verbose=False):
            assert state_column not in train
            assert state_column not in val

        def calibrate_temperature(self, val):
            assert state_column not in val
            return 1.0

        def predict_win_probabilities(self, predict):
            assert state_column not in predict
            return pd.Series(np.full(len(predict), 0.5), index=predict.index)

    monkeypatch.setattr(
        train_production_model, "LambdaRankProbabilityPredictor", FakeLambdaRank
    )
    result = train_production_model.generate_oof_lambdarank_winp(
        frame, frame, n_folds=2
    )
    assert np.isfinite(result).all()


@pytest.mark.unit
def test_standalone_replacement_cannot_change_installed_schema(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "metadata.json").write_text(
        json.dumps({
            "has_lambdarank_model": True,
            "lambdarank_feature_contract": (
                make_lambdarank_contract_metadata(["age", "form"])
            ),
        })
    )

    class Replacement:
        def feature_contract_metadata(self):
            return make_lambdarank_contract_metadata(["age", "different"])

    registry = ModelRegistry(str(registry_dir))
    with pytest.raises(ValueError, match="Standalone LambdaRank replacement"):
        registry.add_lambdarank(Replacement())


@pytest.mark.unit
def test_legacy_registry_requires_full_suite_retrain_before_standalone(tmp_path):
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    (registry_dir / "metadata.json").write_text(
        json.dumps({"has_lambdarank_model": True})
    )

    class Replacement:
        def feature_contract_metadata(self):
            return make_lambdarank_contract_metadata(["age", "form"])

    registry = ModelRegistry(str(registry_dir))
    with pytest.raises(ValueError, match="full production-suite retrain"):
        registry.add_lambdarank(Replacement())
