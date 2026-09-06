"""Integration test: full LambdaRank train → registry round-trip → inference.

Uses real data from the DB (small slice) to train a minimal LambdaRank
model, saves it via ModelRegistry.add_lambdarank, reloads it, and verifies
that predictions are bit-identical across the round-trip. Also verifies
that per-race softmax probabilities sum to 1.

Skipped if the production DB or bucket model is absent.
"""

import json
import shutil
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry


DB_PATH = (
    Path(__file__).parent.parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
PROD_MODEL_DIR = (
    Path(__file__).parent.parent.parent.parent / "models" / "production"
)


@pytest.fixture
def small_training_df():
    """Load ~50 recent competitions from the DB for a fast train."""
    if not DB_PATH.exists():
        pytest.skip(f"DB not found at {DB_PATH}")

    config = DataConfig(
        db_path=str(DB_PATH),
        start_date='2024-01-01',
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(config)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    # Keep the most recent 50 competitions for a fast CV-free training run.
    recent = (
        df.groupby('competition_id')['competition_date'].first()
        .sort_values().tail(50).index
    )
    df = df[df['competition_id'].isin(recent)].copy()
    return df


@pytest.mark.integration
@pytest.mark.slow
def test_full_field_softmax_sums_to_one(small_training_df):
    """Per-race softmax should normalize to 1 within each competition group."""
    df = small_training_df

    # Minimal LambdaRank config for speed (50 iterations).
    cfg = LambdaRankPredictorConfig(
        n_estimators=50, early_stopping_rounds=20,
    )
    cfg.lgb_params.update({'learning_rate': 0.1, 'num_leaves': 15})

    predictor = LambdaRankProbabilityPredictor(cfg)
    predictor.train(df, df, verbose=False)

    win_probs = predictor.predict_win_probabilities(df)
    per_race_sums = (
        pd.DataFrame({'p': win_probs, 'g': df['competition_id']})
        .groupby('g')['p'].sum()
    )
    np.testing.assert_allclose(per_race_sums.values, 1.0, atol=1e-6)


@pytest.mark.integration
@pytest.mark.slow
def test_temperature_calibration_changes_probs_not_ranking(small_training_df):
    df = small_training_df
    cfg = LambdaRankPredictorConfig(n_estimators=30, early_stopping_rounds=20)
    cfg.lgb_params.update({'learning_rate': 0.1, 'num_leaves': 15})

    predictor = LambdaRankProbabilityPredictor(cfg)
    predictor.train(df, df, verbose=False)

    probs_T1 = predictor.predict_win_probabilities(df)
    # Re-run with a different temperature — ranking order must not change.
    predictor.config.temperature = 2.5
    probs_T25 = predictor.predict_win_probabilities(df)

    # Rankings within each race should be identical.
    for comp_id, g in df.groupby('competition_id'):
        r1 = probs_T1.loc[g.index].rank(ascending=False, method='first')
        r2 = probs_T25.loc[g.index].rank(ascending=False, method='first')
        np.testing.assert_array_equal(r1.values, r2.values)


@pytest.mark.integration
@pytest.mark.slow
def test_registry_round_trip_preserves_predictions(tmp_path, small_training_df):
    """Save via ModelRegistry.add_lambdarank, reload, verify identical outputs."""
    df = small_training_df

    # Stage a minimal registry: clone the production bucket model + metadata
    # so add_lambdarank has something to append to. Skip if prod absent.
    if not (PROD_MODEL_DIR / 'metadata.json').exists():
        pytest.skip("Production model dir missing; skipping registry round-trip.")

    test_registry_dir = tmp_path / 'prediction_system'
    shutil.copytree(PROD_MODEL_DIR, test_registry_dir)

    # Train a tiny LambdaRank and append it to the copied registry.
    cfg = LambdaRankPredictorConfig(n_estimators=30, early_stopping_rounds=20)
    cfg.lgb_params.update({'learning_rate': 0.1, 'num_leaves': 15})
    predictor = LambdaRankProbabilityPredictor(cfg)
    predictor.train(df, df, verbose=False)
    predictor.calibrate_temperature(df)
    expected_probs = predictor.predict_win_probabilities(df).values

    # A standalone replacement is only valid after the full suite has
    # recorded the schema its downstream heads were trained against.
    metadata_path = test_registry_dir / 'metadata.json'
    metadata = json.loads(metadata_path.read_text())
    metadata['lambdarank_feature_contract'] = predictor.feature_contract_metadata()
    metadata_path.write_text(json.dumps(metadata, indent=2))

    registry = ModelRegistry(str(test_registry_dir))
    registry.add_lambdarank(predictor, training_info={'test': True})

    # Reload from scratch via the registry.
    (
        _bucket, _time_gap, _weighted, _cal, _contender, loaded_lambdarank,
    ) = registry.load()

    assert loaded_lambdarank is not None, "LambdaRank predictor did not load"
    # Temperature should round-trip.
    assert loaded_lambdarank.config.temperature == pytest.approx(
        predictor.config.temperature
    )
    # Predictions must be identical (no retraining, no temperature drift).
    loaded_probs = loaded_lambdarank.predict_win_probabilities(df).values
    np.testing.assert_allclose(loaded_probs, expected_probs, rtol=1e-10, atol=1e-12)
