"""
Train the production LambdaRank probability head.

This trains a full-field LambdaRank scorer on the same data window as the
main production suite, then appends it to the existing `models/production`
registry (without disturbing the other models).

Runs as a separate pipeline step so the LambdaRank head can be re-tuned
or re-calibrated without a full retrain.

Start-date matches the main trainer (2016-01-01) so LambdaRank features
are built from the same training pool, even though CV showed the
LambdaRank head itself is insensitive to window size.

Usage:
    uv run python -m cycling_project.prediction_tools.train_lambdarank_production
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)
from cycling_project.prediction_tools.lambdarank_feature_contract import (
    build_lambdarank_feature_view,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry


def main():
    print("=" * 70)
    print("LAMBDARANK PROBABILITY HEAD — PRODUCTION TRAINING")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # --- Load Data (same window as main production trainer) ---
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(
        db_path=str(db_path),
        start_date='2016-01-01',
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(config)
    df = pipeline.load_training_data()
    df = build_lambdarank_feature_view(df)
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    print(f"Total samples: {len(df):,}")
    print(f"Date range: {df['competition_date'].min().date()} to {df['competition_date'].max().date()}")
    print(f"Competitions: {df['competition_id'].nunique():,}")

    # --- Split: same 95/5 chronological split used by main trainer ---
    comp_dates = df.groupby('competition_id')['competition_date'].first().sort_values()
    cutoff_idx = int(len(comp_dates) * 0.95)
    cutoff_date = comp_dates.iloc[cutoff_idx]

    train = df[df['competition_date'] < cutoff_date].copy()
    early_stop = df[df['competition_date'] >= cutoff_date].copy()

    print(f"\nTrain:       {len(train):>8,} samples, {train['competition_id'].nunique():,} competitions")
    print(f"Early-stop:  {len(early_stop):>8,} samples, {early_stop['competition_id'].nunique():,} competitions")

    # --- Train LambdaRank (full-field, no contender filter) ---
    print("\n" + "=" * 70)
    print("TRAINING LAMBDARANK HEAD (full field)")
    print("=" * 70)

    # Defaults on LambdaRankPredictorConfig are the production config —
    # see PRODUCTION_LGB_PARAMS in lambdarank_probability_predictor.py.
    lr_config = LambdaRankPredictorConfig()

    predictor = LambdaRankProbabilityPredictor(lr_config)
    info = predictor.train(train, early_stop, verbose=True)
    print(f"Best iteration: {info['best_iteration']}")
    print(f"Features: {info['n_features']}")
    print(f"Training groups (races): {info['n_train_groups']:,}")

    # --- Calibrate softmax temperature on early-stop set ---
    print("\nCalibrating softmax temperature on early-stop set...")
    T = predictor.calibrate_temperature(early_stop)
    print(f"Calibrated temperature: {T:.3f}")

    # --- Reference metrics on early-stop set ---
    print("\n" + "=" * 70)
    print("EARLY-STOP METRICS (reference only)")
    print("=" * 70)
    metrics = predictor.evaluate(early_stop)
    print(f"Winner capture:        {metrics['winner_capture']:.4f}")
    print(f"Podium capture:        {metrics['podium_capture']:.4f}")
    print(f"Winner log-loss:       {metrics['win_log_loss']:.4f}")
    print(f"Discrimination ratio:  {metrics['discrimination_ratio']:.4f}  (1.0 = no skill)")
    print(f"Win cal ratio:         {metrics['win_cal_ratio']:.4f}  (1.0 = calibrated)")
    print(f"Win ECE:               {metrics['win_ece']:.4f}  (0.0 = calibrated)")
    print(f"N races evaluated:     {metrics['n_races']}")

    # --- Append to production registry ---
    print("\n" + "=" * 70)
    print("APPENDING LAMBDARANK HEAD TO PRODUCTION REGISTRY")
    print("=" * 70)
    model_dir = Path(__file__).parent.parent.parent / "models" / "production"
    registry = ModelRegistry(str(model_dir))

    training_info = {
        'lambdarank_best_iteration': info['best_iteration'],
        'lambdarank_n_features': info['n_features'],
        'lambdarank_n_train_groups': info['n_train_groups'],
        'lambdarank_temperature': T,
        'lambdarank_early_stop_winner_capture': metrics['winner_capture'],
        'lambdarank_early_stop_podium_capture': metrics['podium_capture'],
        'lambdarank_early_stop_win_log_loss': metrics['win_log_loss'],
        'lambdarank_early_stop_discrimination_ratio': metrics['discrimination_ratio'],
        'lambdarank_early_stop_win_cal_ratio': metrics['win_cal_ratio'],
        'lambdarank_early_stop_win_ece': metrics['win_ece'],
        'lambdarank_trained_at': datetime.now().isoformat(),
        'lambdarank_feature_contract': predictor.feature_contract_metadata(),
    }

    registry.add_lambdarank(predictor, training_info=training_info)

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
