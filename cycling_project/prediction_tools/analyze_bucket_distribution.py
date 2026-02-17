"""
Analyze bucket prediction quality vs. naive baselines.

Key questions:
1. What's the class distribution? Are we just predicting the majority class?
2. How do we compare to naive baselines (always predict mode, predict by prior)?
3. What does the confusion matrix look like?
4. Are we actually predicting top finishers or just defaulting to mid-pack?
"""

import sys
sys.path.insert(0, '..')

import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig


def main():
    print("=" * 70)
    print("BUCKET PREDICTION QUALITY ANALYSIS")
    print("=" * 70)

    # Load data
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)

    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    # Splits
    train = df[df['competition_date'] < '2023-01-01'].copy()
    val = df[(df['competition_date'] >= '2023-01-01') & (df['competition_date'] < '2023-07-01')].copy()
    test = df[df['competition_date'] >= '2023-07-01'].copy()

    print(f"\nTrain: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    # =========================================================================
    # CLASS DISTRIBUTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("CLASS DISTRIBUTION")
    print("=" * 70)

    print("\n--- Training Set Distribution ---")
    train_dist = train['place_bucket'].value_counts().sort_index()
    train_pct = train['place_bucket'].value_counts(normalize=True).sort_index() * 100

    print(f"{'Bucket':<10} {'Count':>12} {'Percent':>12} {'Cumulative':>12}")
    print("-" * 50)
    cumulative = 0
    for bucket in range(8):
        count = train_dist.get(bucket, 0)
        pct = train_pct.get(bucket, 0)
        cumulative += pct
        print(f"{bucket:<10} {count:>12,} {pct:>11.1f}% {cumulative:>11.1f}%")

    print("\n--- Test Set Distribution ---")
    test_dist = test['place_bucket'].value_counts().sort_index()
    test_pct = test['place_bucket'].value_counts(normalize=True).sort_index() * 100

    print(f"{'Bucket':<10} {'Count':>12} {'Percent':>12}")
    print("-" * 40)
    for bucket in range(8):
        count = test_dist.get(bucket, 0)
        pct = test_pct.get(bucket, 0)
        print(f"{bucket:<10} {count:>12,} {pct:>11.1f}%")

    # =========================================================================
    # TRAIN MODEL
    # =========================================================================
    print("\n" + "=" * 70)
    print("TRAINING MODEL")
    print("=" * 70)

    bucket_config = BucketPredictorConfig(
        n_estimators=500,
        early_stopping_rounds=50,
        use_sample_weights=True
    )
    model = OrdinalBucketPredictor(bucket_config)
    model.train(train, val, verbose=True)

    # Get predictions
    y_true = test['place_bucket'].values
    y_pred = model.predict(test)
    y_pred_continuous = model.predict_continuous(test)

    # =========================================================================
    # NAIVE BASELINES
    # =========================================================================
    print("\n" + "=" * 70)
    print("BASELINE COMPARISONS")
    print("=" * 70)

    # Baseline 1: Always predict mode (most common bucket)
    mode_bucket = train['place_bucket'].mode()[0]
    baseline_mode = np.full_like(y_true, mode_bucket)
    mae_mode = np.mean(np.abs(y_true - baseline_mode))
    acc_mode = np.mean(y_true == baseline_mode)
    within1_mode = np.mean(np.abs(y_true - baseline_mode) <= 1)

    print(f"\nBaseline 1: Always predict mode (bucket {mode_bucket})")
    print(f"  MAE:      {mae_mode:.3f}")
    print(f"  Accuracy: {acc_mode:.1%}")
    print(f"  Within-1: {within1_mode:.1%}")

    # Baseline 2: Always predict mean
    mean_bucket = train['place_bucket'].mean()
    baseline_mean = np.full_like(y_true, round(mean_bucket))
    mae_mean = np.mean(np.abs(y_true - baseline_mean))
    acc_mean = np.mean(y_true == baseline_mean)
    within1_mean = np.mean(np.abs(y_true - baseline_mean) <= 1)

    print(f"\nBaseline 2: Always predict mean (bucket {mean_bucket:.1f} -> {round(mean_bucket)})")
    print(f"  MAE:      {mae_mean:.3f}")
    print(f"  Accuracy: {acc_mean:.1%}")
    print(f"  Within-1: {within1_mean:.1%}")

    # Baseline 3: Random sample from training distribution
    np.random.seed(42)
    baseline_random = np.random.choice(train['place_bucket'].values, size=len(y_true))
    mae_random = np.mean(np.abs(y_true - baseline_random))
    acc_random = np.mean(y_true == baseline_random)
    within1_random = np.mean(np.abs(y_true - baseline_random) <= 1)

    print(f"\nBaseline 3: Random sample from training distribution")
    print(f"  MAE:      {mae_random:.3f}")
    print(f"  Accuracy: {acc_random:.1%}")
    print(f"  Within-1: {within1_random:.1%}")

    # Our model
    mae_model = np.mean(np.abs(y_true - y_pred))
    acc_model = np.mean(y_true == y_pred)
    within1_model = np.mean(np.abs(y_true - y_pred) <= 1)

    print(f"\n--- OUR MODEL ---")
    print(f"  MAE:      {mae_model:.3f}")
    print(f"  Accuracy: {acc_model:.1%}")
    print(f"  Within-1: {within1_model:.1%}")

    print(f"\n--- IMPROVEMENT OVER BASELINES ---")
    print(f"  vs Mode:   MAE {mae_mode - mae_model:+.3f} | Acc {acc_model - acc_mode:+.1%} | Within-1 {within1_model - within1_mode:+.1%}")
    print(f"  vs Mean:   MAE {mae_mean - mae_model:+.3f} | Acc {acc_model - acc_mean:+.1%} | Within-1 {within1_model - within1_mean:+.1%}")
    print(f"  vs Random: MAE {mae_random - mae_model:+.3f} | Acc {acc_model - acc_random:+.1%} | Within-1 {within1_model - within1_random:+.1%}")

    # =========================================================================
    # PREDICTION DISTRIBUTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("PREDICTION DISTRIBUTION")
    print("=" * 70)

    pred_dist = pd.Series(y_pred).value_counts().sort_index()
    pred_pct = pd.Series(y_pred).value_counts(normalize=True).sort_index() * 100

    print(f"\n{'Bucket':<10} {'Actual':>12} {'Predicted':>12} {'Actual %':>12} {'Pred %':>12}")
    print("-" * 60)
    for bucket in range(8):
        actual_count = test_dist.get(bucket, 0)
        pred_count = pred_dist.get(bucket, 0)
        actual_pct = test_pct.get(bucket, 0)
        pred_pct_val = pred_pct.get(bucket, 0)
        print(f"{bucket:<10} {actual_count:>12,} {pred_count:>12,} {actual_pct:>11.1f}% {pred_pct_val:>11.1f}%")

    # =========================================================================
    # CONFUSION MATRIX
    # =========================================================================
    print("\n" + "=" * 70)
    print("CONFUSION MATRIX (rows=actual, cols=predicted)")
    print("=" * 70)

    # Build confusion matrix
    cm = np.zeros((8, 8), dtype=int)
    for true_b, pred_b in zip(y_true, y_pred):
        cm[int(true_b), int(pred_b)] += 1

    print("\n" + " " * 8, end="")
    for i in range(8):
        print(f"  P={i:>5}", end="")
    print()
    print("-" * 65)

    for i in range(8):
        print(f"A={i}  |", end="")
        for j in range(8):
            if cm[i, j] > 0:
                print(f"  {cm[i, j]:>5}", end="")
            else:
                print(f"      -", end="")
        # Show row total and accuracy
        row_total = cm[i, :].sum()
        if row_total > 0:
            row_acc = cm[i, i] / row_total
            print(f"  | {row_total:>6} ({row_acc:>5.1%})")
        else:
            print(f"  | {row_total:>6}")

    # =========================================================================
    # CONFUSION MATRIX AS PERCENTAGES (within each row)
    # =========================================================================
    print("\n" + "=" * 70)
    print("CONFUSION MATRIX (% of each actual bucket)")
    print("=" * 70)

    print("\n" + " " * 8, end="")
    for i in range(8):
        print(f"  P={i:>5}", end="")
    print()
    print("-" * 65)

    for i in range(8):
        row_total = cm[i, :].sum()
        print(f"A={i}  |", end="")
        for j in range(8):
            if row_total > 0:
                pct = cm[i, j] / row_total * 100
                if pct >= 1:
                    print(f"  {pct:>5.1f}", end="")
                else:
                    print(f"      -", end="")
            else:
                print(f"      -", end="")
        print()

    # =========================================================================
    # PER-BUCKET ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PER-BUCKET PERFORMANCE ANALYSIS")
    print("=" * 70)

    print(f"\n{'Bucket':<8} {'N':>8} {'Correct':>10} {'Within-1':>10} {'Within-2':>10} {'Mean Pred':>10} {'Bias':>8}")
    print("-" * 70)

    for bucket in range(8):
        mask = y_true == bucket
        n = mask.sum()
        if n > 0:
            correct = (y_pred[mask] == bucket).mean()
            within1 = (np.abs(y_pred[mask] - bucket) <= 1).mean()
            within2 = (np.abs(y_pred[mask] - bucket) <= 2).mean()
            mean_pred = y_pred[mask].mean()
            bias = mean_pred - bucket
            print(f"{bucket:<8} {n:>8,} {correct:>9.1%} {within1:>9.1%} {within2:>9.1%} {mean_pred:>10.2f} {bias:>+7.2f}")
        else:
            print(f"{bucket:<8} {n:>8,} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>8}")

    # =========================================================================
    # TOP FINISHER ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("TOP FINISHER PREDICTION QUALITY")
    print("=" * 70)

    print("\n--- When we predict bucket 0-2 (top 5), how often are they actually top finishers? ---")

    for pred_bucket in range(3):
        pred_mask = y_pred == pred_bucket
        n_predicted = pred_mask.sum()
        if n_predicted > 0:
            actual_buckets = y_true[pred_mask]
            exact = (actual_buckets == pred_bucket).mean()
            within1 = (np.abs(actual_buckets - pred_bucket) <= 1).mean()
            top5 = (actual_buckets <= 2).mean()
            top15 = (actual_buckets <= 3).mean()

            print(f"\nPredicted bucket {pred_bucket} (n={n_predicted:,}):")
            print(f"  Actually bucket {pred_bucket}: {exact:.1%}")
            print(f"  Within 1 bucket: {within1:.1%}")
            print(f"  Actually top 5 (bucket 0-2): {top5:.1%}")
            print(f"  Actually top 15 (bucket 0-3): {top15:.1%}")

    print("\n--- When actual is bucket 0-2 (top 5), what do we predict? ---")

    for actual_bucket in range(3):
        actual_mask = y_true == actual_bucket
        n_actual = actual_mask.sum()
        if n_actual > 0:
            preds = y_pred[actual_mask]
            pred_dist_local = Counter(preds)

            print(f"\nActual bucket {actual_bucket} (n={n_actual:,}):")
            print(f"  Prediction distribution: ", end="")
            for b in range(8):
                if pred_dist_local[b] > 0:
                    print(f"{b}:{pred_dist_local[b]/n_actual:.1%} ", end="")
            print()
            print(f"  Mean prediction: {preds.mean():.2f} (bias: {preds.mean() - actual_bucket:+.2f})")

    # =========================================================================
    # CONTINUOUS PREDICTION ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("CONTINUOUS PREDICTION ANALYSIS")
    print("=" * 70)

    print(f"\nContinuous prediction range: {y_pred_continuous.min():.2f} to {y_pred_continuous.max():.2f}")
    print(f"Mean: {y_pred_continuous.mean():.2f} | Std: {y_pred_continuous.std():.2f}")

    print("\n--- Continuous prediction by actual bucket ---")
    print(f"{'Actual':<10} {'Mean Pred':>12} {'Std':>10} {'Min':>10} {'Max':>10}")
    print("-" * 55)
    for bucket in range(8):
        mask = y_true == bucket
        if mask.sum() > 0:
            preds = y_pred_continuous[mask]
            print(f"{bucket:<10} {preds.mean():>12.2f} {preds.std():>10.2f} {preds.min():>10.2f} {preds.max():>10.2f}")


if __name__ == '__main__':
    main()
