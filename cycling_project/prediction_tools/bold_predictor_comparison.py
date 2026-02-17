"""
Bold Predictor Comparison

We want models that:
1. Make BOLD predictions (identify winners, podium, top 10)
2. Are rewarded MORE for getting narrow predictions right
3. Work well when converted to rankings → ranking-derived buckets

Value hierarchy:
- Correctly predicting winner (bucket 0) = most valuable
- Correctly predicting podium (bucket 1) = very valuable
- Correctly predicting top 5 (bucket 2) = valuable
- Correctly predicting top 15 (bucket 3) = useful
- Correctly predicting top 30+ = less interesting

We test:
1. Standard MAE (baseline)
2. Bold asymmetry (penalize under-prediction MORE - being too conservative)
3. Value-weighted loss (reward narrow correct predictions)
"""

import sys
sys.path.insert(0, '..')

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from typing import Tuple, Dict, List
from dataclasses import dataclass

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.feature_engineering import FeatureEngineer
from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from prediction_tools.race_ranking_predictor import RaceRankingPredictor


# Value weights for each bucket - higher = more valuable to predict correctly
BUCKET_VALUES = {
    0: 10.0,  # Winner - extremely valuable
    1: 7.0,   # Podium - very valuable
    2: 5.0,   # Top 5 - valuable
    3: 3.0,   # Top 15 - useful
    4: 1.5,   # Top 30 - moderate
    5: 1.0,   # Top 50 - baseline
    6: 0.5,   # Finisher - least valuable
}


class BoldBucketPredictor:
    """
    Bucket predictor with configurable asymmetry.

    asymmetry_ratio < 1.0 = BOLD (penalize under-prediction more)
    asymmetry_ratio > 1.0 = CONSERVATIVE (penalize over-prediction more)
    """

    def __init__(self, asymmetry_ratio: float = 0.5, n_estimators: int = 300):
        self.asymmetry_ratio = asymmetry_ratio
        self.n_estimators = n_estimators
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def _asymmetric_objective(self, y_pred: np.ndarray, train_data: lgb.Dataset) -> Tuple[np.ndarray, np.ndarray]:
        """Custom objective with configurable asymmetry."""
        y_true = train_data.get_label()
        residual = y_pred - y_true

        # residual < 0 means over-prediction (predicted better than actual)
        # residual > 0 means under-prediction (predicted worse than actual)

        grad = np.where(
            residual < 0,
            self.asymmetry_ratio * residual,  # Over-prediction penalty
            residual  # Under-prediction penalty (this is the baseline)
        )

        hess = np.where(
            residual < 0,
            self.asymmetry_ratio * np.ones_like(residual),
            np.ones_like(residual)
        )

        return grad, hess

    def prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in df.columns:
                X[col] = df[col]
            else:
                X[col] = 0.0
        return X

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame, verbose: bool = False):
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)

        X_train = self.get_feature_matrix(train_df)
        y_train = train_df['place_bucket'].values
        X_val = self.get_feature_matrix(val_df)
        y_val = val_df['place_bucket'].values

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            'objective': self._asymmetric_objective,
            'metric': 'None',
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_child_samples': 50,
            'verbose': -1,
        }

        def mae_eval(y_pred, data):
            y_true = data.get_label()
            return 'mae', float(np.mean(np.abs(y_true - y_pred))), False

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.n_estimators,
            valid_sets=[val_data],
            feval=mae_eval,
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(0),
            ],
        )

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.clip(np.round(self.predict_continuous(df)), 0, 7).astype(int)

    def predict_continuous(self, df: pd.DataFrame) -> np.ndarray:
        df = self.prepare_features(df, fit=False)
        X = self.get_feature_matrix(df)
        return self.model.predict(X)


class ValueWeightedPredictor:
    """
    Predictor that weights errors by the VALUE of getting each bucket right.

    Errors on bucket 0 (winners) are penalized heavily.
    Errors on bucket 6 (finishers) are penalized lightly.
    """

    def __init__(self, n_estimators: int = 300):
        self.n_estimators = n_estimators
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def _value_weighted_objective(self, y_pred: np.ndarray, train_data: lgb.Dataset) -> Tuple[np.ndarray, np.ndarray]:
        """Weight errors by the value of the true bucket."""
        y_true = train_data.get_label()
        residual = y_pred - y_true

        # Weight by the value of the TRUE bucket
        # Missing a winner hurts more than missing a mid-pack rider
        weights = np.array([BUCKET_VALUES.get(int(y), 1.0) for y in y_true])

        grad = weights * residual
        hess = weights

        return grad, hess

    def prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in df.columns:
                X[col] = df[col]
            else:
                X[col] = 0.0
        return X

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame, verbose: bool = False):
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)

        X_train = self.get_feature_matrix(train_df)
        y_train = train_df['place_bucket'].values
        X_val = self.get_feature_matrix(val_df)
        y_val = val_df['place_bucket'].values

        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        params = {
            'objective': self._value_weighted_objective,
            'metric': 'None',
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_child_samples': 50,
            'verbose': -1,
        }

        def mae_eval(y_pred, data):
            y_true = data.get_label()
            return 'mae', float(np.mean(np.abs(y_true - y_pred))), False

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.n_estimators,
            valid_sets=[val_data],
            feval=mae_eval,
            callbacks=[
                lgb.early_stopping(50, verbose=False),
                lgb.log_evaluation(0),
            ],
        )

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.clip(np.round(self.predict_continuous(df)), 0, 7).astype(int)

    def predict_continuous(self, df: pd.DataFrame) -> np.ndarray:
        df = self.prepare_features(df, fit=False)
        X = self.get_feature_matrix(df)
        return self.model.predict(X)


def place_bucketer(place: int) -> int:
    """Convert place to bucket."""
    if place == 1:
        return 0
    elif place <= 3:
        return 1
    elif place <= 5:
        return 2
    elif place <= 15:
        return 3
    elif place <= 30:
        return 4
    elif place <= 50:
        return 5
    else:
        return 6


def get_ranking_derived_buckets(continuous_preds: np.ndarray, competition_ids: np.ndarray) -> np.ndarray:
    """Convert continuous predictions to rankings, then to buckets."""
    df = pd.DataFrame({
        'continuous': continuous_preds,
        'competition_id': competition_ids,
    })

    # Rank within each competition (lower continuous = better predicted finish)
    df['rank'] = df.groupby('competition_id')['continuous'].rank(method='first')

    # Convert rank to bucket
    df['ranking_bucket'] = df['rank'].apply(place_bucketer)

    return df['ranking_bucket'].values


def evaluate_comprehensive(y_true, y_model_bucket, y_ranking_bucket, name):
    """Comprehensive evaluation of both model and ranking-derived buckets."""
    results = {'name': name}

    # Model bucket metrics
    results['model_mae'] = np.mean(np.abs(y_true - y_model_bucket))
    results['model_exact'] = np.mean(y_true == y_model_bucket)
    results['model_within1'] = np.mean(np.abs(y_true - y_model_bucket) <= 1)
    results['model_practical'] = np.mean(y_true <= y_model_bucket)

    # Ranking-derived bucket metrics
    results['rank_mae'] = np.mean(np.abs(y_true - y_ranking_bucket))
    results['rank_exact'] = np.mean(y_true == y_ranking_bucket)
    results['rank_within1'] = np.mean(np.abs(y_true - y_ranking_bucket) <= 1)
    results['rank_practical'] = np.mean(y_true <= y_ranking_bucket)

    # Value-weighted accuracy (how well do we do on valuable predictions?)
    model_value_score = 0
    rank_value_score = 0
    total_value = 0

    for bucket in range(7):
        mask = y_true == bucket
        n = mask.sum()
        if n > 0:
            value = BUCKET_VALUES[bucket]
            total_value += n * value

            # Credit for exact or practical success
            model_value_score += value * np.sum((y_model_bucket[mask] >= bucket))
            rank_value_score += value * np.sum((y_ranking_bucket[mask] >= bucket))

    results['model_value_score'] = model_value_score / total_value
    results['rank_value_score'] = rank_value_score / total_value

    return results


def main():
    print("=" * 80)
    print("BOLD PREDICTOR COMPARISON WITH RANKING-DERIVED BUCKETS")
    print("=" * 80)

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

    y_true = test['place_bucket'].values
    comp_ids = test['competition_id'].values

    # =========================================================================
    # TRAIN MODELS
    # =========================================================================

    models = {}

    # 1. Standard (baseline)
    print("\n[1/6] Training Standard MAE model...")
    standard = OrdinalBucketPredictor(BucketPredictorConfig(n_estimators=300, early_stopping_rounds=50))
    standard.train(train, val, verbose=False)
    models['Standard MAE'] = standard

    # 2. Conservative (asymmetry 3.0)
    print("[2/6] Training Conservative (3x) model...")
    conservative = BoldBucketPredictor(asymmetry_ratio=3.0, n_estimators=300)
    conservative.train(train, val)
    models['Conservative 3x'] = conservative

    # 3. Slightly Bold (asymmetry 0.7)
    print("[3/6] Training Slightly Bold (0.7x) model...")
    slightly_bold = BoldBucketPredictor(asymmetry_ratio=0.7, n_estimators=300)
    slightly_bold.train(train, val)
    models['Slightly Bold 0.7x'] = slightly_bold

    # 4. Bold (asymmetry 0.5)
    print("[4/6] Training Bold (0.5x) model...")
    bold = BoldBucketPredictor(asymmetry_ratio=0.5, n_estimators=300)
    bold.train(train, val)
    models['Bold 0.5x'] = bold

    # 5. Very Bold (asymmetry 0.3)
    print("[5/6] Training Very Bold (0.3x) model...")
    very_bold = BoldBucketPredictor(asymmetry_ratio=0.3, n_estimators=300)
    very_bold.train(train, val)
    models['Very Bold 0.3x'] = very_bold

    # 6. Value-Weighted
    print("[6/6] Training Value-Weighted model...")
    value_weighted = ValueWeightedPredictor(n_estimators=300)
    value_weighted.train(train, val)
    models['Value-Weighted'] = value_weighted

    # =========================================================================
    # EVALUATE ALL MODELS
    # =========================================================================
    print("\n" + "=" * 80)
    print("COMPREHENSIVE EVALUATION")
    print("=" * 80)

    all_results = []

    for name, model in models.items():
        y_model = model.predict(test)
        y_continuous = model.predict_continuous(test)
        y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

        results = evaluate_comprehensive(y_true, y_model, y_ranking, name)
        all_results.append(results)

    # =========================================================================
    # DISPLAY RESULTS
    # =========================================================================

    print("\n--- MODEL-PREDICTED BUCKET PERFORMANCE ---")
    print(f"{'Model':<22} {'MAE':>7} {'Exact':>8} {'Within1':>8} {'Practical':>10} {'ValueScore':>11}")
    print("-" * 75)
    for r in all_results:
        print(f"{r['name']:<22} {r['model_mae']:>7.3f} {r['model_exact']:>7.1%} {r['model_within1']:>7.1%} {r['model_practical']:>9.1%} {r['model_value_score']:>10.1%}")

    print("\n--- RANKING-DERIVED BUCKET PERFORMANCE ---")
    print(f"{'Model':<22} {'MAE':>7} {'Exact':>8} {'Within1':>8} {'Practical':>10} {'ValueScore':>11}")
    print("-" * 75)
    for r in all_results:
        print(f"{r['name']:<22} {r['rank_mae']:>7.3f} {r['rank_exact']:>7.1%} {r['rank_within1']:>7.1%} {r['rank_practical']:>9.1%} {r['rank_value_score']:>10.1%}")

    # =========================================================================
    # PREDICTION DISTRIBUTION
    # =========================================================================
    print("\n" + "=" * 80)
    print("MODEL BUCKET PREDICTION DISTRIBUTION")
    print("=" * 80)

    print(f"\n{'Bucket':<8} {'Actual':>8}", end="")
    for name in models.keys():
        print(f" {name[:12]:>12}", end="")
    print()
    print("-" * (20 + 13 * len(models)))

    for bucket in range(7):
        actual_pct = (y_true == bucket).mean() * 100
        print(f"{bucket:<8} {actual_pct:>7.1f}%", end="")
        for name, model in models.items():
            pred_pct = (model.predict(test) == bucket).mean() * 100
            print(f" {pred_pct:>11.1f}%", end="")
        print()

    # =========================================================================
    # TOP FINISHER IDENTIFICATION
    # =========================================================================
    print("\n" + "=" * 80)
    print("TOP FINISHER IDENTIFICATION (Using Ranking-Derived Buckets)")
    print("=" * 80)

    for threshold_name, bucket_threshold in [("Winners (bucket 0)", 0), ("Podium (bucket 0-1)", 1), ("Top 5 (bucket 0-2)", 2), ("Top 15 (bucket 0-3)", 3)]:
        print(f"\n--- {threshold_name} ---")
        actual_contenders = y_true <= bucket_threshold
        n_actual = actual_contenders.sum()

        print(f"Actual count: {n_actual:,}")
        print(f"{'Model':<22} {'Predicted':>10} {'Precision':>10} {'Recall':>10}")
        print("-" * 55)

        for name, model in models.items():
            y_continuous = model.predict_continuous(test)
            y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

            pred_contenders = y_ranking <= bucket_threshold
            n_pred = pred_contenders.sum()

            if n_pred > 0:
                precision = (y_true[pred_contenders] <= bucket_threshold).mean()
            else:
                precision = 0

            recall = (y_ranking[actual_contenders] <= bucket_threshold).mean()

            print(f"{name:<22} {n_pred:>10,} {precision:>9.1%} {recall:>9.1%}")

    # =========================================================================
    # PRACTICAL SUCCESS BY PREDICTED BUCKET (Ranking-Derived)
    # =========================================================================
    print("\n" + "=" * 80)
    print("PRACTICAL SUCCESS BY RANKING-DERIVED BUCKET")
    print("=" * 80)
    print("(When we rank someone at position X, how often do they finish at or above that threshold?)\n")

    print(f"{'Bucket':<12}", end="")
    for name in models.keys():
        print(f" {name[:12]:>12}", end="")
    print()
    print("-" * (12 + 13 * len(models)))

    for bucket in range(7):
        print(f"{bucket:<12}", end="")
        for name, model in models.items():
            y_continuous = model.predict_continuous(test)
            y_ranking = get_ranking_derived_buckets(y_continuous, comp_ids)

            mask = y_ranking == bucket
            if mask.sum() > 0:
                success = (y_true[mask] <= bucket).mean()
                print(f" {success:>11.1%}", end="")
            else:
                print(f" {'N/A':>11}", end="")
        print()


if __name__ == '__main__':
    main()
