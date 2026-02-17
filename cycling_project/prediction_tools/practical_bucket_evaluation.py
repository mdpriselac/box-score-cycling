"""
Practical Bucket Evaluation

Traditional bucket evaluation penalizes predictions that are "right in spirit":
- Predict bucket 2 (top 5), actual bucket 0 (winner) = 2 bucket error
- But practically, we correctly identified a top contender!

This script adds practical metrics:
1. "At least as good as predicted": Did they finish at least as well as we predicted?
   - Predict top 15, finish 4th = SUCCESS (4th is in top 15)
   - Predict winner, finish 5th = FAILURE (5th is not 1st)

2. "Upper bound accuracy": For each bucket, did they finish within that threshold?
   - Predict bucket 2 (top 5) → Did they finish top 5? (places 1-5)
   - Predict bucket 3 (top 15) → Did they finish top 15? (places 1-15)

3. Directional error: Over-prediction (too optimistic) vs under-prediction (too pessimistic)
"""

import sys
sys.path.insert(0, '..')

import pandas as pd
import numpy as np
from pathlib import Path

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from prediction_tools.race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig


# Bucket upper bounds (inclusive place threshold)
BUCKET_UPPER_BOUNDS = {
    0: 1,    # Winner: place 1
    1: 3,    # Podium: places 1-3
    2: 5,    # Top 5: places 1-5
    3: 15,   # Top 15: places 1-15
    4: 30,   # Top 30: places 1-30
    5: 50,   # Top 50: places 1-50
    6: 999,  # Finisher: places 51+
}

# Bucket names for display
BUCKET_NAMES = {
    0: "Winner (1st)",
    1: "Podium (2-3)",
    2: "Top 5 (4-5)",
    3: "Top 15 (6-15)",
    4: "Top 30 (16-30)",
    5: "Top 50 (31-50)",
    6: "Finisher (51+)",
}


def practical_success(predicted_bucket, actual_bucket):
    """
    Did the rider finish at least as good as predicted?

    If we predict they'll be in the top 15 (bucket 3), and they finish
    in the top 5 (bucket 2), that's a practical success.

    Returns True if actual_bucket <= predicted_bucket
    """
    return actual_bucket <= predicted_bucket


def threshold_success(predicted_bucket, actual_bucket):
    """
    Did the rider finish within the predicted threshold?

    Same as practical_success, but framed as "did they meet the bar?"
    Bucket 3 (top 15) prediction is success if actual is 0, 1, 2, or 3.
    """
    return actual_bucket <= predicted_bucket


def main():
    print("=" * 70)
    print("PRACTICAL BUCKET EVALUATION")
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

    # Collect predictions
    print("\nGenerating predictions...")
    test_comp_ids = test['competition_id'].unique()
    all_results = []

    for comp_id in test_comp_ids:
        race = test[test['competition_id'] == comp_id].copy()
        if len(race) < 10:
            continue
        try:
            predictions = ranker.predict_race(race)
            actual = race[['rider_id', 'place_bucket']].copy()
            merged = predictions.merge(actual, on='rider_id')
            all_results.append(merged)
        except:
            continue

    combined = pd.concat(all_results, ignore_index=True)
    print(f"Total predictions: {len(combined):,}")

    y_true = combined['place_bucket'].values
    y_model = combined['model_predicted_bucket'].values
    y_ranking = combined['ranking_derived_bucket'].values

    # =========================================================================
    # TRADITIONAL METRICS (for reference)
    # =========================================================================
    print("\n" + "=" * 70)
    print("TRADITIONAL METRICS (Reference)")
    print("=" * 70)

    print(f"\n{'Metric':<25} {'Model':>15} {'Ranking':>15}")
    print("-" * 60)
    print(f"{'MAE':<25} {np.mean(np.abs(y_true - y_model)):>15.3f} {np.mean(np.abs(y_true - y_ranking)):>15.3f}")
    print(f"{'Exact Accuracy':<25} {np.mean(y_true == y_model):>14.1%} {np.mean(y_true == y_ranking):>14.1%}")
    print(f"{'Within-1 Bucket':<25} {np.mean(np.abs(y_true - y_model) <= 1):>14.1%} {np.mean(np.abs(y_true - y_ranking) <= 1):>14.1%}")

    # =========================================================================
    # PRACTICAL METRICS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PRACTICAL METRICS: 'At Least As Good As Predicted'")
    print("=" * 70)
    print("\nIf we predict 'top 15' and they finish 4th, that's a SUCCESS.")
    print("If we predict 'winner' and they finish 5th, that's a FAILURE.")

    # Practical success: actual <= predicted (they did at least as well as predicted)
    model_practical = np.mean(y_true <= y_model)
    ranking_practical = np.mean(y_true <= y_ranking)

    print(f"\n{'Metric':<35} {'Model':>15} {'Ranking':>15}")
    print("-" * 70)
    print(f"{'Practical Success Rate':<35} {model_practical:>14.1%} {ranking_practical:>14.1%}")
    print(f"{'(rider finished at least as good)':<35}")

    # =========================================================================
    # DIRECTIONAL ERROR ANALYSIS
    # =========================================================================
    print("\n" + "=" * 70)
    print("DIRECTIONAL ERROR ANALYSIS")
    print("=" * 70)

    # Over-prediction: we said they'd do better than they did (predicted < actual)
    # Under-prediction: we said they'd do worse than they did (predicted > actual)
    model_over = np.mean(y_model < y_true)  # Predicted better bucket (lower) than actual
    model_under = np.mean(y_model > y_true)  # Predicted worse bucket (higher) than actual
    model_exact = np.mean(y_model == y_true)

    ranking_over = np.mean(y_ranking < y_true)
    ranking_under = np.mean(y_ranking > y_true)
    ranking_exact = np.mean(y_ranking == y_true)

    print(f"\n{'Error Type':<25} {'Model':>15} {'Ranking':>15} {'Description'}")
    print("-" * 80)
    print(f"{'Over-predicted':<25} {model_over:>14.1%} {ranking_over:>14.1%} (too optimistic)")
    print(f"{'Exact':<25} {model_exact:>14.1%} {ranking_exact:>14.1%} (correct bucket)")
    print(f"{'Under-predicted':<25} {model_under:>14.1%} {ranking_under:>14.1%} (too pessimistic)")

    print(f"\nInterpretation:")
    print(f"  Over-prediction = we thought they'd do better than they did")
    print(f"  Under-prediction = we thought they'd do worse than they did (conservative)")

    # =========================================================================
    # THRESHOLD ACCURACY BY PREDICTED BUCKET
    # =========================================================================
    print("\n" + "=" * 70)
    print("THRESHOLD ACCURACY: 'Did they meet the predicted bar?'")
    print("=" * 70)
    print("\nFor each prediction, did the rider finish within that threshold?")
    print("e.g., If we predict 'top 15', did they actually finish top 15?\n")

    print(f"{'Predicted Bucket':<25} {'Model N':>10} {'Model %':>12} {'Ranking N':>10} {'Ranking %':>12}")
    print("-" * 75)

    for bucket in range(7):
        # Model
        model_mask = y_model == bucket
        model_n = model_mask.sum()
        if model_n > 0:
            model_threshold_met = (y_true[model_mask] <= bucket).mean()
        else:
            model_threshold_met = 0

        # Ranking
        ranking_mask = y_ranking == bucket
        ranking_n = ranking_mask.sum()
        if ranking_n > 0:
            ranking_threshold_met = (y_true[ranking_mask] <= bucket).mean()
        else:
            ranking_threshold_met = 0

        bucket_name = BUCKET_NAMES[bucket]
        print(f"{bucket_name:<25} {model_n:>10,} {model_threshold_met:>11.1%} {ranking_n:>10,} {ranking_threshold_met:>11.1%}")

    # =========================================================================
    # PRACTICAL ACCURACY BY ACTUAL BUCKET
    # =========================================================================
    print("\n" + "=" * 70)
    print("PRACTICAL ACCURACY: By Actual Performance")
    print("=" * 70)
    print("\nFor riders in each actual bucket, how often were we 'practically correct'?")
    print("(Predicted bucket >= actual bucket, i.e., we didn't over-estimate)\n")

    print(f"{'Actual Bucket':<25} {'N':>10} {'Model Prac%':>12} {'Rank Prac%':>12} {'Model Exact':>12} {'Rank Exact':>12}")
    print("-" * 90)

    for bucket in range(7):
        mask = y_true == bucket
        n = mask.sum()
        if n > 0:
            # Practical success: predicted >= actual (we didn't over-promise)
            model_prac = (y_model[mask] >= bucket).mean()
            ranking_prac = (y_ranking[mask] >= bucket).mean()

            # Exact accuracy for comparison
            model_exact_bucket = (y_model[mask] == bucket).mean()
            ranking_exact_bucket = (y_ranking[mask] == bucket).mean()

            bucket_name = BUCKET_NAMES[bucket]
            print(f"{bucket_name:<25} {n:>10,} {model_prac:>11.1%} {ranking_prac:>11.1%} {model_exact_bucket:>11.1%} {ranking_exact_bucket:>11.1%}")

    # =========================================================================
    # CONTENDER IDENTIFICATION
    # =========================================================================
    print("\n" + "=" * 70)
    print("CONTENDER IDENTIFICATION: Did we spot the top finishers?")
    print("=" * 70)

    thresholds = [
        ("Top 5 contenders", 2, 5),
        ("Top 15 contenders", 3, 15),
        ("Top 30 contenders", 4, 30),
    ]

    for name, bucket_threshold, place_threshold in thresholds:
        print(f"\n--- {name} (bucket 0-{bucket_threshold}, places 1-{place_threshold}) ---")

        # Actual contenders
        actual_contenders = y_true <= bucket_threshold
        n_actual = actual_contenders.sum()

        # Model predicted contenders
        model_pred_contenders = y_model <= bucket_threshold
        model_n_pred = model_pred_contenders.sum()

        # Ranking predicted contenders
        ranking_pred_contenders = y_ranking <= bucket_threshold
        ranking_n_pred = ranking_pred_contenders.sum()

        # Precision: of those we predicted as contenders, how many were?
        if model_n_pred > 0:
            model_precision = (y_true[model_pred_contenders] <= bucket_threshold).mean()
        else:
            model_precision = 0
        if ranking_n_pred > 0:
            ranking_precision = (y_true[ranking_pred_contenders] <= bucket_threshold).mean()
        else:
            ranking_precision = 0

        # Recall: of actual contenders, how many did we identify?
        model_recall = (y_model[actual_contenders] <= bucket_threshold).mean()
        ranking_recall = (y_ranking[actual_contenders] <= bucket_threshold).mean()

        print(f"  Actual {name.lower()}: {n_actual:,}")
        print(f"  Model predictions:   {model_n_pred:>6,} | Precision: {model_precision:>5.1%} | Recall: {model_recall:>5.1%}")
        print(f"  Ranking predictions: {ranking_n_pred:>6,} | Precision: {ranking_precision:>5.1%} | Recall: {ranking_recall:>5.1%}")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"""
Key Findings:

1. TRADITIONAL METRICS favor Ranking-Derived:
   - MAE: Model {np.mean(np.abs(y_true - y_model)):.3f} vs Ranking {np.mean(np.abs(y_true - y_ranking)):.3f}
   - Exact: Model {np.mean(y_true == y_model):.1%} vs Ranking {np.mean(y_true == y_ranking):.1%}

2. PRACTICAL SUCCESS (rider finished at least as good as predicted):
   - Model: {model_practical:.1%}
   - Ranking: {ranking_practical:.1%}

3. DIRECTIONAL TENDENCY:
   - Model over-predicts {model_over:.1%} (too optimistic) and under-predicts {model_under:.1%}
   - Ranking over-predicts {ranking_over:.1%} and under-predicts {ranking_under:.1%}

4. INTERPRETATION:
   - Model tends to push predictions toward middle buckets (3-5)
   - This means it often OVER-predicts poor finishers (says they'll do better)
   - And UNDER-predicts good finishers (says they'll do worse)

   - Ranking matches distribution, so over/under prediction is balanced
   - But for middle buckets, the "wrong" prediction could go either direction
""")


if __name__ == '__main__':
    main()
