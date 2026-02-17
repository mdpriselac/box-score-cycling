"""
Compare Model-Predicted Buckets vs Ranking-Derived Buckets

Shows the difference between:
1. model_predicted_bucket: Raw bucket prediction from model (compressed to middle)
2. ranking_derived_bucket: Bucket assigned based on predicted race position
"""

import sys
sys.path.insert(0, '..')

import pandas as pd
import numpy as np
from pathlib import Path

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from prediction_tools.race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig


def main():
    print("=" * 70)
    print("COMPARING BUCKET PREDICTION METHODS")
    print("=" * 70)

    # Load data
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)

    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    train = df[df['competition_date'] < '2023-01-01'].copy()
    val = df[(df['competition_date'] >= '2023-01-01') & (df['competition_date'] < '2023-07-01')].copy()
    test = df[df['competition_date'] >= '2023-07-01'].copy()

    print(f"\nTrain: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    # Train model
    print("\nTraining bucket predictor...")
    bucket_config = BucketPredictorConfig(n_estimators=300, early_stopping_rounds=50)
    model = OrdinalBucketPredictor(bucket_config)
    model.train(train, val, verbose=True)

    # Create race ranker
    ranker = RaceRankingPredictor(model)

    # =========================================================================
    # EVALUATE BOTH METHODS ON TEST RACES
    # =========================================================================
    print("\n" + "=" * 70)
    print("EVALUATING ON TEST SET RACES")
    print("=" * 70)

    test_comp_ids = test['competition_id'].unique()
    print(f"Evaluating {len(test_comp_ids)} races...")

    # Collect results
    all_results = []

    for comp_id in test_comp_ids:
        race = test[test['competition_id'] == comp_id].copy()
        if len(race) < 10:  # Skip tiny races
            continue

        try:
            predictions = ranker.predict_race(race)

            # Merge with actual buckets
            actual = race[['rider_id', 'place_bucket']].copy()
            merged = predictions.merge(actual, on='rider_id')

            all_results.append(merged)
        except Exception as e:
            continue

    combined = pd.concat(all_results, ignore_index=True)
    print(f"Total predictions: {len(combined):,}")

    # =========================================================================
    # OVERALL COMPARISON
    # =========================================================================
    print("\n" + "=" * 70)
    print("OVERALL ACCURACY COMPARISON")
    print("=" * 70)

    y_true = combined['place_bucket'].values
    y_model = combined['model_predicted_bucket'].values
    y_ranking = combined['ranking_derived_bucket'].values

    # Model-based metrics
    model_mae = np.mean(np.abs(y_true - y_model))
    model_acc = np.mean(y_true == y_model)
    model_within1 = np.mean(np.abs(y_true - y_model) <= 1)
    model_within2 = np.mean(np.abs(y_true - y_model) <= 2)

    # Ranking-derived metrics
    rank_mae = np.mean(np.abs(y_true - y_ranking))
    rank_acc = np.mean(y_true == y_ranking)
    rank_within1 = np.mean(np.abs(y_true - y_ranking) <= 1)
    rank_within2 = np.mean(np.abs(y_true - y_ranking) <= 2)

    print(f"\n{'Metric':<20} {'Model Bucket':>15} {'Ranking Bucket':>15} {'Improvement':>15}")
    print("-" * 70)
    print(f"{'MAE':<20} {model_mae:>15.3f} {rank_mae:>15.3f} {model_mae - rank_mae:>+15.3f}")
    print(f"{'Accuracy':<20} {model_acc:>14.1%} {rank_acc:>14.1%} {rank_acc - model_acc:>+14.1%}")
    print(f"{'Within-1':<20} {model_within1:>14.1%} {rank_within1:>14.1%} {rank_within1 - model_within1:>+14.1%}")
    print(f"{'Within-2':<20} {model_within2:>14.1%} {rank_within2:>14.1%} {rank_within2 - model_within2:>+14.1%}")

    # =========================================================================
    # PER-BUCKET COMPARISON
    # =========================================================================
    print("\n" + "=" * 70)
    print("PER-BUCKET ACCURACY COMPARISON")
    print("=" * 70)

    print(f"\n{'Actual':<8} {'N':>8} {'Model Acc':>12} {'Ranking Acc':>12} {'Improvement':>12}")
    print("-" * 60)

    for bucket in range(7):  # 0-6, skip 7 (DNF)
        mask = y_true == bucket
        n = mask.sum()
        if n > 0:
            model_bucket_acc = (y_model[mask] == bucket).mean()
            rank_bucket_acc = (y_ranking[mask] == bucket).mean()
            improvement = rank_bucket_acc - model_bucket_acc
            print(f"{bucket:<8} {n:>8,} {model_bucket_acc:>11.1%} {rank_bucket_acc:>11.1%} {improvement:>+11.1%}")

    # =========================================================================
    # DISTRIBUTION COMPARISON
    # =========================================================================
    print("\n" + "=" * 70)
    print("PREDICTION DISTRIBUTION COMPARISON")
    print("=" * 70)

    actual_dist = pd.Series(y_true).value_counts(normalize=True).sort_index() * 100
    model_dist = pd.Series(y_model).value_counts(normalize=True).sort_index() * 100
    rank_dist = pd.Series(y_ranking).value_counts(normalize=True).sort_index() * 100

    print(f"\n{'Bucket':<8} {'Actual %':>12} {'Model %':>12} {'Ranking %':>12}")
    print("-" * 50)

    for bucket in range(7):
        actual_pct = actual_dist.get(bucket, 0)
        model_pct = model_dist.get(bucket, 0)
        rank_pct = rank_dist.get(bucket, 0)
        print(f"{bucket:<8} {actual_pct:>11.1f}% {model_pct:>11.1f}% {rank_pct:>11.1f}%")

    # =========================================================================
    # WINNER/PODIUM ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("TOP FINISHER PREDICTION ANALYSIS")
    print("=" * 70)

    # How often do we correctly identify bucket 0 (winners)?
    actual_winners = y_true == 0
    model_pred_winners = y_model == 0
    rank_pred_winners = y_ranking == 0

    print(f"\n--- BUCKET 0 (WINNERS) ---")
    print(f"Actual winners: {actual_winners.sum():,}")
    print(f"Model predicts bucket 0: {model_pred_winners.sum():,} times")
    print(f"Ranking predicts bucket 0: {rank_pred_winners.sum():,} times")

    if model_pred_winners.sum() > 0:
        model_precision = (y_true[model_pred_winners] == 0).mean()
        print(f"Model precision (when predicting 0): {model_precision:.1%}")

    if rank_pred_winners.sum() > 0:
        rank_precision = (y_true[rank_pred_winners] == 0).mean()
        print(f"Ranking precision (when predicting 0): {rank_precision:.1%}")

    model_recall = (y_model[actual_winners] == 0).mean()
    rank_recall = (y_ranking[actual_winners] == 0).mean()
    print(f"Model recall (finding actual winners): {model_recall:.1%}")
    print(f"Ranking recall (finding actual winners): {rank_recall:.1%}")

    # Top 5 (buckets 0-2)
    print(f"\n--- BUCKETS 0-2 (TOP 5) ---")
    actual_top5 = y_true <= 2
    model_pred_top5 = y_model <= 2
    rank_pred_top5 = y_ranking <= 2

    print(f"Actual top-5 finishers: {actual_top5.sum():,}")
    print(f"Model predicts bucket 0-2: {model_pred_top5.sum():,} times")
    print(f"Ranking predicts bucket 0-2: {rank_pred_top5.sum():,} times")

    if model_pred_top5.sum() > 0:
        model_precision = (y_true[model_pred_top5] <= 2).mean()
        print(f"Model precision: {model_precision:.1%}")
    if rank_pred_top5.sum() > 0:
        rank_precision = (y_true[rank_pred_top5] <= 2).mean()
        print(f"Ranking precision: {rank_precision:.1%}")

    # =========================================================================
    # EXAMPLE RACE
    # =========================================================================
    print("\n" + "=" * 70)
    print("EXAMPLE RACE COMPARISON")
    print("=" * 70)

    sample_comp = test_comp_ids[0]
    sample_race = test[test['competition_id'] == sample_comp].copy()
    sample_pred = ranker.predict_race(sample_race)
    sample_actual = sample_race[['rider_id', 'place_bucket']].rename(columns={'place_bucket': 'actual_bucket'})
    sample = sample_pred.merge(sample_actual, on='rider_id')

    print(f"\nRace: Competition ID {sample_comp} (field size: {len(sample)})")
    print("\nTop 10 predicted vs actual:")

    display_cols = ['rider_id', 'predicted_rank', 'ranking_derived_bucket', 'model_predicted_bucket', 'actual_bucket']
    if 'rider_name' in sample.columns:
        display_cols.insert(1, 'rider_name')

    print(sample[display_cols].head(10).to_string(index=False))


if __name__ == '__main__':
    main()
