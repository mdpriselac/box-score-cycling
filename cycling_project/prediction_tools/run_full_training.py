"""
Full Training Run with Overfitting Analysis

Train: 2018-2022 (all pre-2023 data)
Val: 2023-H1 (for early stopping)
Test: 2023-H2
Holdout: 2024 (for overfitting analysis)
"""

import sys
sys.path.insert(0, '..')

import pandas as pd
import numpy as np
from datetime import datetime

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from prediction_tools.time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig
from prediction_tools.race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig
from prediction_tools.evaluation import (
    BucketEvaluator, TimeGapEvaluator, RankingEvaluator,
    evaluate_full_system, print_evaluation_report
)


def main():
    print("=" * 70)
    print("FULL TRAINING RUN WITH OVERFITTING ANALYSIS")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # =========================================================================
    # LOAD DATA
    # =========================================================================
    print("\n" + "=" * 70)
    print("LOADING DATA")
    print("=" * 70)

    # Use absolute path to database
    from pathlib import Path
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"

    config = DataConfig(
        db_path=str(db_path),
        start_date='2018-01-01',
        min_races_career=10
    )
    pipeline = CyclingDataPipeline(config)

    # Load all data
    df = pipeline.load_training_data()
    print(f"Total samples loaded: {len(df):,}")

    # Show date range
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    print(f"Date range: {df['competition_date'].min().date()} to {df['competition_date'].max().date()}")

    # =========================================================================
    # CREATE SPLITS
    # =========================================================================
    print("\n" + "=" * 70)
    print("CREATING TEMPORAL SPLITS")
    print("=" * 70)

    # Train: 2018-2022
    train = df[df['competition_date'] < '2023-01-01'].copy()

    # Validation: 2023-H1 (for early stopping)
    val = df[(df['competition_date'] >= '2023-01-01') &
             (df['competition_date'] < '2023-07-01')].copy()

    # Test: 2023-H2
    test_2023 = df[(df['competition_date'] >= '2023-07-01') &
                   (df['competition_date'] < '2024-01-01')].copy()

    # Holdout: 2024+
    holdout_2024 = df[df['competition_date'] >= '2024-01-01'].copy()

    print(f"Train (2018-2022):     {len(train):>8,} samples")
    print(f"Val (2023-H1):         {len(val):>8,} samples")
    print(f"Test (2023-H2):        {len(test_2023):>8,} samples")
    print(f"Holdout (2024+):       {len(holdout_2024):>8,} samples")

    # Competition counts
    print(f"\nCompetitions:")
    print(f"  Train:   {train['competition_id'].nunique():,}")
    print(f"  Val:     {val['competition_id'].nunique():,}")
    print(f"  Test:    {test_2023['competition_id'].nunique():,}")
    print(f"  Holdout: {holdout_2024['competition_id'].nunique():,}")

    # =========================================================================
    # TRAIN BUCKET PREDICTOR
    # =========================================================================
    print("\n" + "=" * 70)
    print("TRAINING BUCKET PREDICTOR")
    print("=" * 70)

    bucket_config = BucketPredictorConfig(
        n_estimators=1000,  # More iterations for full training
        early_stopping_rounds=100,
        use_sample_weights=True
    )
    bucket_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    bucket_predictor = OrdinalBucketPredictor(bucket_config)
    bucket_info = bucket_predictor.train(train, val, verbose=True)

    print(f"\nBucket model trained:")
    print(f"  Best iteration: {bucket_info['best_iteration']}")
    print(f"  Features: {bucket_info['n_features']}")

    # =========================================================================
    # TRAIN TIME GAP PREDICTOR
    # =========================================================================
    print("\n" + "=" * 70)
    print("TRAINING TIME GAP PREDICTOR")
    print("=" * 70)

    time_gap_config = TimeGapPredictorConfig(
        n_estimators=1000,
        early_stopping_rounds=100,
        log_transform_target=True,
        exclude_winners=True,
        max_time_gap=3600.0
    )
    time_gap_config.lgb_params.update({
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 50,
    })

    time_gap_predictor = TimeGapPredictor(time_gap_config)
    time_gap_info = time_gap_predictor.train(train, val, verbose=True)

    print(f"\nTime gap model trained:")
    print(f"  Best iteration: {time_gap_info['best_iteration']}")
    print(f"  Training samples: {time_gap_info['train_samples']:,}")

    # =========================================================================
    # CREATE RACE RANKER
    # =========================================================================
    race_ranker = RaceRankingPredictor(
        bucket_predictor=bucket_predictor,
        time_gap_predictor=time_gap_predictor,
        config=RaceRankingConfig(ranking_method='expected_bucket')
    )

    # =========================================================================
    # EVALUATE ON VALIDATION SET (2023-H1) - for reference
    # =========================================================================
    print("\n" + "=" * 70)
    print("VALIDATION SET EVALUATION (2023-H1) - Training Reference")
    print("=" * 70)

    val_eval = evaluate_full_system(
        bucket_predictor, time_gap_predictor, race_ranker, val,
        n_sample_races=min(100, val['competition_id'].nunique())
    )
    print_evaluation_report(val_eval)

    # =========================================================================
    # EVALUATE ON TEST SET (2023-H2)
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST SET EVALUATION (2023-H2)")
    print("=" * 70)

    test_eval = evaluate_full_system(
        bucket_predictor, time_gap_predictor, race_ranker, test_2023,
        n_sample_races=min(200, test_2023['competition_id'].nunique())
    )
    print_evaluation_report(test_eval)

    # =========================================================================
    # EVALUATE ON HOLDOUT SET (2024)
    # =========================================================================
    print("\n" + "=" * 70)
    print("HOLDOUT SET EVALUATION (2024) - Overfitting Check")
    print("=" * 70)

    holdout_eval = evaluate_full_system(
        bucket_predictor, time_gap_predictor, race_ranker, holdout_2024,
        n_sample_races=min(200, holdout_2024['competition_id'].nunique())
    )
    print_evaluation_report(holdout_eval)

    # =========================================================================
    # OVERFITTING ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("OVERFITTING ANALYSIS: 2023 vs 2024 Performance")
    print("=" * 70)

    print("\n--- Bucket Prediction ---")
    print(f"{'Metric':<20} {'2023-H2':>12} {'2024':>12} {'Delta':>12} {'Status':>15}")
    print("-" * 70)

    bucket_metrics = ['mae', 'accuracy', 'within_1', 'within_2', 'quadratic_kappa']
    for metric in bucket_metrics:
        v2023 = test_eval['bucket'][metric]
        v2024 = holdout_eval['bucket'][metric]
        delta = v2024 - v2023

        # For MAE, lower is better (negative delta is good)
        # For others, higher is better (positive delta is good)
        if metric == 'mae':
            status = "OK" if delta <= 0.05 else ("WARN" if delta <= 0.1 else "CONCERN")
        else:
            status = "OK" if delta >= -0.02 else ("WARN" if delta >= -0.05 else "CONCERN")

        if metric in ['accuracy', 'within_1', 'within_2']:
            print(f"{metric:<20} {v2023:>11.1%} {v2024:>11.1%} {delta:>+11.1%} {status:>15}")
        else:
            print(f"{metric:<20} {v2023:>12.3f} {v2024:>12.3f} {delta:>+12.3f} {status:>15}")

    print("\n--- Time Gap Prediction ---")
    print(f"{'Metric':<20} {'2023-H2':>12} {'2024':>12} {'Delta':>12} {'Status':>15}")
    print("-" * 70)

    time_gap_metrics = ['mae', 'rmse', 'r2']
    for metric in time_gap_metrics:
        v2023 = test_eval['time_gap'][metric]
        v2024 = holdout_eval['time_gap'][metric]
        delta = v2024 - v2023

        if metric in ['mae', 'rmse']:
            status = "OK" if delta <= 10 else ("WARN" if delta <= 30 else "CONCERN")
            print(f"{metric:<20} {v2023:>11.1f}s {v2024:>11.1f}s {delta:>+11.1f}s {status:>15}")
        else:
            status = "OK" if delta >= -0.03 else ("WARN" if delta >= -0.1 else "CONCERN")
            print(f"{metric:<20} {v2023:>12.3f} {v2024:>12.3f} {delta:>+12.3f} {status:>15}")

    print("\n--- Race Ranking ---")
    print(f"{'Metric':<20} {'2023-H2':>12} {'2024':>12} {'Delta':>12} {'Status':>15}")
    print("-" * 70)

    ranking_metrics = ['mean_kendall_tau', 'mean_winner_correct', 'mean_podium_accuracy',
                       'mean_top5_accuracy', 'mean_top10_accuracy']
    for metric in ranking_metrics:
        v2023 = test_eval['ranking'][metric]
        v2024 = holdout_eval['ranking'][metric]
        delta = v2024 - v2023

        status = "OK" if delta >= -0.02 else ("WARN" if delta >= -0.05 else "CONCERN")

        if metric in ['mean_winner_correct', 'mean_podium_accuracy', 'mean_top5_accuracy', 'mean_top10_accuracy']:
            print(f"{metric:<25} {v2023:>11.1%} {v2024:>11.1%} {delta:>+11.1%} {status:>12}")
        else:
            print(f"{metric:<25} {v2023:>12.3f} {v2024:>12.3f} {delta:>+12.3f} {status:>12}")

    # =========================================================================
    # FEATURE IMPORTANCE
    # =========================================================================
    print("\n" + "=" * 70)
    print("TOP 20 MOST IMPORTANT FEATURES")
    print("=" * 70)

    importance = bucket_predictor.get_feature_importance()
    print(importance.head(20).to_string(index=False))

    # =========================================================================
    # PER-BUCKET ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PER-BUCKET ACCURACY (2023-H2 vs 2024)")
    print("=" * 70)

    # 2023 per-bucket
    y_true_2023 = test_2023['place_bucket'].values
    y_pred_2023 = bucket_predictor.predict(test_2023)

    # 2024 per-bucket
    y_true_2024 = holdout_2024['place_bucket'].values
    y_pred_2024 = bucket_predictor.predict(holdout_2024)

    print(f"\n{'Bucket':<10} {'2023 Count':>12} {'2023 Acc':>12} {'2024 Count':>12} {'2024 Acc':>12} {'Delta':>10}")
    print("-" * 70)

    for bucket in range(8):
        mask_2023 = y_true_2023 == bucket
        mask_2024 = y_true_2024 == bucket

        count_2023 = mask_2023.sum()
        count_2024 = mask_2024.sum()

        if count_2023 > 0:
            acc_2023 = (y_pred_2023[mask_2023] == bucket).mean()
        else:
            acc_2023 = 0

        if count_2024 > 0:
            acc_2024 = (y_pred_2024[mask_2024] == bucket).mean()
        else:
            acc_2024 = 0

        delta = acc_2024 - acc_2023
        print(f"{bucket:<10} {count_2023:>12,} {acc_2023:>11.1%} {count_2024:>12,} {acc_2024:>11.1%} {delta:>+9.1%}")

    # =========================================================================
    # BY COMPETITION TYPE
    # =========================================================================
    print("\n" + "=" * 70)
    print("PERFORMANCE BY COMPETITION TYPE")
    print("=" * 70)

    for comp_type in ['stage', 'one_day', 'gc']:
        test_type = test_2023[test_2023['competition_type'] == comp_type]
        holdout_type = holdout_2024[holdout_2024['competition_type'] == comp_type]

        if len(test_type) > 0 and len(holdout_type) > 0:
            # Bucket MAE
            y_true_t = test_type['place_bucket'].values
            y_pred_t = bucket_predictor.predict(test_type)
            mae_2023 = np.mean(np.abs(y_true_t - y_pred_t))

            y_true_h = holdout_type['place_bucket'].values
            y_pred_h = bucket_predictor.predict(holdout_type)
            mae_2024 = np.mean(np.abs(y_true_h - y_pred_h))

            print(f"\n{comp_type.upper()}:")
            print(f"  Samples: {len(test_type):,} (2023) / {len(holdout_type):,} (2024)")
            print(f"  Bucket MAE: {mae_2023:.3f} (2023) / {mae_2024:.3f} (2024) | Delta: {mae_2024 - mae_2023:+.3f}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    # Calculate overall overfitting score
    bucket_mae_delta = holdout_eval['bucket']['mae'] - test_eval['bucket']['mae']
    within1_delta = holdout_eval['bucket']['within_1'] - test_eval['bucket']['within_1']
    kendall_delta = holdout_eval['ranking']['mean_kendall_tau'] - test_eval['ranking']['mean_kendall_tau']

    print(f"\nKey 2024 vs 2023 Deltas:")
    print(f"  Bucket MAE:    {bucket_mae_delta:+.3f} ({'OK' if bucket_mae_delta <= 0.05 else 'POTENTIAL OVERFIT'})")
    print(f"  Within-1:      {within1_delta:+.1%} ({'OK' if within1_delta >= -0.02 else 'POTENTIAL OVERFIT'})")
    print(f"  Kendall Tau:   {kendall_delta:+.3f} ({'OK' if kendall_delta >= -0.02 else 'POTENTIAL OVERFIT'})")

    overall_status = "GOOD GENERALIZATION"
    if bucket_mae_delta > 0.1 or within1_delta < -0.05 or kendall_delta < -0.05:
        overall_status = "POTENTIAL OVERFITTING"
    elif bucket_mae_delta > 0.05 or within1_delta < -0.02 or kendall_delta < -0.02:
        overall_status = "MINOR DEGRADATION"

    print(f"\nOverall Status: {overall_status}")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        'bucket_predictor': bucket_predictor,
        'time_gap_predictor': time_gap_predictor,
        'race_ranker': race_ranker,
        'val_eval': val_eval,
        'test_eval': test_eval,
        'holdout_eval': holdout_eval,
    }


if __name__ == '__main__':
    results = main()
