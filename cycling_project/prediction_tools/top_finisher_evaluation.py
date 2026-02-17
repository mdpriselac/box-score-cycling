"""
Top Finisher Evaluation (Buckets 0-4 Only)

Focus exclusively on predicting top 30 finishers (buckets 0-4).
Bucket 5-6 predictions are excluded from evaluation.

Full metric suite:
- Traditional: MAE, Exact, Within-1, Within-2
- Practical: Success rate, directional error
- Value-weighted: Rewards narrow correct predictions
- Contender identification: Precision/Recall for each threshold
"""

import sys
sys.path.insert(0, '..')

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from typing import Tuple
from scipy.stats import kendalltau

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.feature_engineering import FeatureEngineer
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig


BUCKET_VALUES = {0: 10.0, 1: 7.0, 2: 5.0, 3: 3.0, 4: 1.5, 5: 1.0, 6: 0.5}


class AsymmetricPredictor:
    """Predictor with configurable asymmetry ratio."""

    def __init__(self, asymmetry_ratio: float, n_estimators: int = 300):
        self.asymmetry_ratio = asymmetry_ratio
        self.n_estimators = n_estimators
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def _objective(self, y_pred, train_data):
        y_true = train_data.get_label()
        residual = y_pred - y_true
        grad = np.where(residual < 0, self.asymmetry_ratio * residual, residual)
        hess = np.where(residual < 0, self.asymmetry_ratio, 1.0) * np.ones_like(residual)
        return grad, hess

    def prepare_features(self, df, fit=False):
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df):
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            X[col] = df[col] if col in df.columns else 0.0
        return X

    def train(self, train_df, val_df):
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)

        X_train, y_train = self.get_feature_matrix(train_df), train_df['place_bucket'].values
        X_val, y_val = self.get_feature_matrix(val_df), val_df['place_bucket'].values

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            'objective': self._objective, 'metric': 'None', 'num_leaves': 63,
            'learning_rate': 0.05, 'feature_fraction': 0.8, 'bagging_fraction': 0.8,
            'bagging_freq': 5, 'min_child_samples': 50, 'verbose': -1,
        }

        def mae_eval(y_pred, data):
            return 'mae', float(np.mean(np.abs(data.get_label() - y_pred))), False

        self.model = lgb.train(
            params, train_data, num_boost_round=self.n_estimators,
            valid_sets=[val_data], feval=mae_eval,
            callbacks=[lgb.early_stopping(50, verbose=False), lgb.log_evaluation(0)],
        )

    def predict(self, df):
        return np.clip(np.round(self.predict_continuous(df)), 0, 7).astype(int)

    def predict_continuous(self, df):
        df = self.prepare_features(df, fit=False)
        return self.model.predict(self.get_feature_matrix(df))


def place_bucketer(place):
    if place == 1: return 0
    elif place <= 3: return 1
    elif place <= 5: return 2
    elif place <= 15: return 3
    elif place <= 30: return 4
    elif place <= 50: return 5
    else: return 6


def get_ranking_derived_buckets(continuous_preds, competition_ids):
    df = pd.DataFrame({'continuous': continuous_preds, 'competition_id': competition_ids})
    df['rank'] = df.groupby('competition_id')['continuous'].rank(method='first')
    df['ranking_bucket'] = df['rank'].apply(place_bucketer)
    return df['ranking_bucket'].values


def full_evaluation(y_true, y_model, y_ranking, name, mask=None):
    """Full evaluation suite."""
    if mask is not None:
        y_true = y_true[mask]
        y_model = y_model[mask]
        y_ranking = y_ranking[mask]

    n = len(y_true)
    results = {'name': name, 'n': n}

    # === MODEL BUCKET METRICS ===
    results['m_mae'] = np.mean(np.abs(y_true - y_model))
    results['m_exact'] = np.mean(y_true == y_model)
    results['m_within1'] = np.mean(np.abs(y_true - y_model) <= 1)
    results['m_within2'] = np.mean(np.abs(y_true - y_model) <= 2)
    results['m_practical'] = np.mean(y_true <= y_model)
    results['m_over'] = np.mean(y_model < y_true)  # Over-predicted (too optimistic)
    results['m_under'] = np.mean(y_model > y_true)  # Under-predicted (too conservative)

    # === RANKING BUCKET METRICS ===
    results['r_mae'] = np.mean(np.abs(y_true - y_ranking))
    results['r_exact'] = np.mean(y_true == y_ranking)
    results['r_within1'] = np.mean(np.abs(y_true - y_ranking) <= 1)
    results['r_within2'] = np.mean(np.abs(y_true - y_ranking) <= 2)
    results['r_practical'] = np.mean(y_true <= y_ranking)
    results['r_over'] = np.mean(y_ranking < y_true)
    results['r_under'] = np.mean(y_ranking > y_true)

    # === VALUE-WEIGHTED SCORE ===
    m_value, r_value, total_value = 0, 0, 0
    for bucket in range(5):  # Only 0-4
        bucket_mask = y_true == bucket
        if bucket_mask.sum() > 0:
            value = BUCKET_VALUES[bucket]
            total_value += bucket_mask.sum() * value
            m_value += value * np.sum(y_model[bucket_mask] == bucket)
            r_value += value * np.sum(y_ranking[bucket_mask] == bucket)
    results['m_value'] = m_value / total_value if total_value > 0 else 0
    results['r_value'] = r_value / total_value if total_value > 0 else 0

    return results


def main():
    print("=" * 90)
    print("TOP FINISHER EVALUATION (BUCKETS 0-4 ONLY)")
    print("=" * 90)

    # Load data
    db_path = Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    config = DataConfig(db_path=str(db_path), start_date='2018-01-01', min_races_career=10)
    pipeline = CyclingDataPipeline(config)

    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])

    train = df[df['competition_date'] < '2023-01-01'].copy()
    val = df[(df['competition_date'] >= '2023-01-01') & (df['competition_date'] < '2023-07-01')].copy()
    test = df[df['competition_date'] >= '2023-07-01'].copy()

    print(f"\nData: Train {len(train):,} | Val {len(val):,} | Test {len(test):,}")

    y_true_all = test['place_bucket'].values
    comp_ids = test['competition_id'].values

    # Filter to buckets 0-4 only
    top_finisher_mask = y_true_all <= 4
    print(f"Top finishers (bucket 0-4): {top_finisher_mask.sum():,} ({top_finisher_mask.mean():.1%} of test set)")

    # Distribution of top finishers
    print("\nTop finisher distribution:")
    for b in range(5):
        n = (y_true_all == b).sum()
        print(f"  Bucket {b}: {n:,} ({n/len(y_true_all):.1%})")

    # =========================================================================
    # TRAIN MODELS
    # =========================================================================
    models = {}

    configs = [
        ("Standard MAE", None),
        ("Conservative 3x", 3.0),
        ("Balanced 1x", 1.0),
        ("Slightly Bold 0.7x", 0.7),
        ("Bold 0.5x", 0.5),
        ("Very Bold 0.3x", 0.3),
        ("Super Bold 0.1x", 0.1),
    ]

    print("\nTraining models...")
    for name, ratio in configs:
        print(f"  {name}...", end=" ", flush=True)
        if ratio is None:
            model = OrdinalBucketPredictor(BucketPredictorConfig(n_estimators=300, early_stopping_rounds=50))
            model.train(train, val, verbose=False)
        else:
            model = AsymmetricPredictor(asymmetry_ratio=ratio, n_estimators=300)
            model.train(train, val)
        models[name] = model
        print("done")

    # =========================================================================
    # FULL EVALUATION ON TOP FINISHERS
    # =========================================================================
    print("\n" + "=" * 90)
    print("FULL METRICS (BUCKETS 0-4 ONLY)")
    print("=" * 90)

    all_results = []
    for name, model in models.items():
        y_model = model.predict(test)
        y_continuous = model.predict_continuous(test)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)
        results = full_evaluation(y_true_all, y_model, y_ranking, name, mask=top_finisher_mask)
        all_results.append(results)

    # MODEL BUCKET TABLE
    print("\n--- MODEL-PREDICTED BUCKET (Buckets 0-4 only) ---")
    print(f"{'Model':<22} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'W/in2':>7} {'Prac%':>7} {'Over%':>7} {'Under%':>7} {'Value':>7}")
    print("-" * 90)
    for r in all_results:
        print(f"{r['name']:<22} {r['m_mae']:>7.3f} {r['m_exact']:>6.1%} {r['m_within1']:>6.1%} {r['m_within2']:>6.1%} "
              f"{r['m_practical']:>6.1%} {r['m_over']:>6.1%} {r['m_under']:>6.1%} {r['m_value']:>6.1%}")

    # RANKING BUCKET TABLE
    print("\n--- RANKING-DERIVED BUCKET (Buckets 0-4 only) ---")
    print(f"{'Model':<22} {'MAE':>7} {'Exact':>7} {'W/in1':>7} {'W/in2':>7} {'Prac%':>7} {'Over%':>7} {'Under%':>7} {'Value':>7}")
    print("-" * 90)
    for r in all_results:
        print(f"{r['name']:<22} {r['r_mae']:>7.3f} {r['r_exact']:>6.1%} {r['r_within1']:>6.1%} {r['r_within2']:>6.1%} "
              f"{r['r_practical']:>6.1%} {r['r_over']:>6.1%} {r['r_under']:>6.1%} {r['r_value']:>6.1%}")

    # =========================================================================
    # PER-BUCKET ANALYSIS
    # =========================================================================
    print("\n" + "=" * 90)
    print("PER-BUCKET EXACT ACCURACY (Model vs Ranking)")
    print("=" * 90)

    print(f"\n{'Model':<22}", end="")
    for b in range(5):
        print(f"  B{b} Model  B{b} Rank", end="")
    print()
    print("-" * 90)

    for name, model in models.items():
        y_model = model.predict(test)
        y_continuous = model.predict_continuous(test)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

        print(f"{name:<22}", end="")
        for bucket in range(5):
            mask = y_true_all == bucket
            m_acc = (y_model[mask] == bucket).mean() if mask.sum() > 0 else 0
            r_acc = (y_ranking[mask] == bucket).mean() if mask.sum() > 0 else 0
            print(f"  {m_acc:>6.1%}  {r_acc:>6.1%}", end="")
        print()

    # =========================================================================
    # PRACTICAL SUCCESS BY BUCKET
    # =========================================================================
    print("\n" + "=" * 90)
    print("PRACTICAL SUCCESS BY ACTUAL BUCKET (Ranking-Derived)")
    print("(Did we predict at least as good as they finished?)")
    print("=" * 90)

    print(f"\n{'Model':<22}  {'B0':>7}  {'B1':>7}  {'B2':>7}  {'B3':>7}  {'B4':>7}")
    print("-" * 60)

    for name, model in models.items():
        y_continuous = model.predict_continuous(test)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

        print(f"{name:<22}", end="")
        for bucket in range(5):
            mask = y_true_all == bucket
            if mask.sum() > 0:
                # Practical success = ranking prediction >= actual (didn't over-promise)
                prac = (y_ranking[mask] >= bucket).mean()
                print(f"  {prac:>6.1%}", end="")
            else:
                print(f"  {'N/A':>6}", end="")
        print()

    # =========================================================================
    # THRESHOLD IDENTIFICATION
    # =========================================================================
    print("\n" + "=" * 90)
    print("THRESHOLD IDENTIFICATION (Ranking-Derived)")
    print("=" * 90)

    thresholds = [
        ("Winners (B0)", 0),
        ("Podium (B0-1)", 1),
        ("Top 5 (B0-2)", 2),
        ("Top 15 (B0-3)", 3),
        ("Top 30 (B0-4)", 4),
    ]

    for thresh_name, bucket_thresh in thresholds:
        print(f"\n--- {thresh_name} ---")
        actual_in_thresh = y_true_all <= bucket_thresh
        n_actual = actual_in_thresh.sum()

        print(f"{'Model':<22} {'Predicted':>10} {'TP':>8} {'Precision':>10} {'Recall':>8} {'F1':>8}")
        print("-" * 70)

        for name, model in models.items():
            y_continuous = model.predict_continuous(test)
            y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

            pred_in_thresh = y_ranking <= bucket_thresh
            n_pred = pred_in_thresh.sum()

            tp = (actual_in_thresh & pred_in_thresh).sum()
            precision = tp / n_pred if n_pred > 0 else 0
            recall = tp / n_actual if n_actual > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            print(f"{name:<22} {n_pred:>10,} {tp:>8,} {precision:>9.1%} {recall:>7.1%} {f1:>7.3f}")

    # =========================================================================
    # PREDICTION DISTRIBUTION FOR TOP FINISHERS
    # =========================================================================
    print("\n" + "=" * 90)
    print("WHAT DO WE PREDICT FOR TOP FINISHERS? (Ranking-Derived)")
    print("=" * 90)

    for actual_bucket in range(5):
        mask = y_true_all == actual_bucket
        n = mask.sum()
        print(f"\n--- Actual Bucket {actual_bucket} (n={n:,}) ---")
        print(f"{'Model':<22}  {'→B0':>6}  {'→B1':>6}  {'→B2':>6}  {'→B3':>6}  {'→B4':>6}  {'→B5+':>6}  {'MeanPred':>9}")
        print("-" * 80)

        for name, model in models.items():
            y_continuous = model.predict_continuous(test)
            y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

            preds = y_ranking[mask]
            print(f"{name:<22}", end="")
            for b in range(5):
                pct = (preds == b).mean() * 100
                print(f"  {pct:>5.1f}%", end="")
            pct_5plus = (preds >= 5).mean() * 100
            print(f"  {pct_5plus:>5.1f}%", end="")
            print(f"  {preds.mean():>8.2f}")


if __name__ == '__main__':
    main()
