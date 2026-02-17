"""
Practical Success Bucket Predictor

Traditional loss: MAE on bucket (penalizes all errors equally)
Practical loss: Rewards bold predictions that are met, penalizes over-promising

The key insight:
- Predicting bucket 2 (top 5) and rider finishes top 5 = SUCCESS + BOLDNESS BONUS
- Predicting bucket 5 (top 50) and rider finishes top 50 = SUCCESS but no bonus
- Predicting bucket 2 (top 5) and rider finishes 20th = FAILURE (over-promised)

We implement several approaches:
1. Asymmetric Loss: Penalize over-prediction more than under-prediction
2. Threshold Classification: Binary classifiers for each threshold
3. Custom Reward Function: Reward boldness when correct
"""

import sys
sys.path.insert(0, '..')

import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from typing import Tuple, Dict
from dataclasses import dataclass

from prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from prediction_tools.feature_engineering import FeatureEngineer


@dataclass
class PracticalPredictorConfig:
    """Configuration for practical success predictor."""
    n_estimators: int = 500
    early_stopping_rounds: int = 50
    # Asymmetry: how much more to penalize over-prediction vs under-prediction
    # > 1 means penalize over-prediction more (be conservative)
    # < 1 means penalize under-prediction more (be bold)
    asymmetry_ratio: float = 3.0  # Over-prediction costs 3x more


class PracticalBucketPredictor:
    """
    Bucket predictor optimized for practical success.

    Uses asymmetric loss to penalize over-prediction (saying they'll do
    better than they actually do) more heavily than under-prediction.
    """

    def __init__(self, config: PracticalPredictorConfig = None):
        self.config = config or PracticalPredictorConfig()
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def _asymmetric_objective(self, y_pred: np.ndarray, train_data: lgb.Dataset) -> Tuple[np.ndarray, np.ndarray]:
        """
        Custom asymmetric objective function for LightGBM.

        Over-prediction (predicted < actual) is penalized more heavily.
        This encourages the model to be appropriately conservative.

        Returns gradient and hessian.
        """
        y_true = train_data.get_label()
        residual = y_pred - y_true

        # Gradient - derivative of loss
        # For over-prediction (residual < 0, meaning we said bucket 2 but actual is bucket 4)
        # We want higher penalty, so gradient is amplified
        grad = np.where(
            residual < 0,  # Over-predicted (said they'd do better)
            self.config.asymmetry_ratio * residual,  # Higher penalty
            residual  # Normal penalty for under-prediction
        )

        # Hessian (second derivative) - constant for linear loss
        hess = np.where(
            residual < 0,
            self.config.asymmetry_ratio * np.ones_like(residual),
            np.ones_like(residual)
        )

        return grad, hess

    def _asymmetric_eval(self, y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[str, float, bool]:
        """Evaluation metric matching the asymmetric loss."""
        residual = y_pred - y_true

        loss = np.where(
            residual < 0,
            self.config.asymmetry_ratio * np.abs(residual),
            np.abs(residual)
        )

        return 'asymmetric_mae', float(np.mean(loss)), False

    def _practical_success_eval(self, y_true: np.ndarray, y_pred: np.ndarray) -> Tuple[str, float, bool]:
        """Practical success rate as evaluation metric."""
        # Round predictions to nearest bucket
        y_pred_bucket = np.clip(np.round(y_pred), 0, 7).astype(int)
        # Success = actual <= predicted (they met or exceeded our prediction)
        success_rate = np.mean(y_true <= y_pred_bucket)
        # Return negative because LightGBM minimizes
        return 'practical_success', float(success_rate), True

    def prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """Prepare features for training/prediction."""
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract feature matrix from dataframe."""
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in df.columns:
                X[col] = df[col]
            else:
                X[col] = 0.0
        return X

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame, verbose: bool = True) -> Dict:
        """Train the model with asymmetric loss."""
        # Prepare features
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)

        X_train = self.get_feature_matrix(train_df)
        y_train = train_df['place_bucket'].values

        X_val = self.get_feature_matrix(val_df)
        y_val = val_df['place_bucket'].values

        # Create datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Parameters - use custom objective via params
        params = {
            'objective': self._asymmetric_objective,
            'metric': 'None',  # Use custom metric
            'num_leaves': 63,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'min_child_samples': 50,
            'verbose': -1,
        }

        # Train with custom objective
        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=[train_data, val_data],
            valid_names=['train', 'val'],
            feval=lambda y_pred, data: [
                self._asymmetric_eval(data.get_label(), y_pred),
                self._practical_success_eval(data.get_label(), y_pred),
            ],
            callbacks=[
                lgb.early_stopping(self.config.early_stopping_rounds, verbose=verbose),
                lgb.log_evaluation(50 if verbose else 0),
            ],
        )

        return {
            'best_iteration': self.model.best_iteration,
            'n_features': len(self.feature_columns),
        }

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Predict bucket (rounded to integer)."""
        continuous = self.predict_continuous(df)
        return np.clip(np.round(continuous), 0, 7).astype(int)

    def predict_continuous(self, df: pd.DataFrame) -> np.ndarray:
        """Predict continuous bucket value."""
        df = self.prepare_features(df, fit=False)
        X = self.get_feature_matrix(df)
        return self.model.predict(X)


class ThresholdPredictor:
    """
    Predicts thresholds (will they finish top-K?) instead of exact buckets.

    Trains separate binary classifiers for each threshold:
    - Will they finish top 1? (winner)
    - Will they finish top 3? (podium)
    - Will they finish top 5?
    - Will they finish top 15?
    - Will they finish top 30?
    - Will they finish top 50?

    The predicted bucket is the narrowest threshold with confidence above threshold.
    """

    THRESHOLDS = [1, 3, 5, 15, 30, 50]  # Place thresholds
    BUCKET_MAP = {1: 0, 3: 1, 5: 2, 15: 3, 30: 4, 50: 5}  # threshold -> bucket

    def __init__(self, n_estimators: int = 300, confidence_threshold: float = 0.5):
        self.n_estimators = n_estimators
        self.confidence_threshold = confidence_threshold
        self.models = {}
        self.feature_engineer = FeatureEngineer()
        self.feature_columns = None

    def prepare_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """Prepare features."""
        if fit:
            df = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.feature_columns
        else:
            df = self.feature_engineer.transform(df)
        return df

    def get_feature_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract feature matrix."""
        X = pd.DataFrame(index=df.index)
        for col in self.feature_columns:
            if col in df.columns:
                X[col] = df[col]
            else:
                X[col] = 0.0
        return X

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame, verbose: bool = True):
        """Train threshold classifiers."""
        train_df = self.prepare_features(train_df, fit=True)
        val_df = self.prepare_features(val_df, fit=False)

        X_train = self.get_feature_matrix(train_df)
        X_val = self.get_feature_matrix(val_df)

        for threshold in self.THRESHOLDS:
            if verbose:
                print(f"\nTraining threshold classifier: Top {threshold}")

            # Binary target: did they finish at or above this threshold?
            # bucket 0 = 1st, bucket 1 = 2-3, etc.
            # We need to map bucket to whether they beat the threshold
            bucket_threshold = self.BUCKET_MAP[threshold]

            y_train = (train_df['place_bucket'] <= bucket_threshold).astype(int)
            y_val = (val_df['place_bucket'] <= bucket_threshold).astype(int)

            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            params = {
                'objective': 'binary',
                'metric': 'auc',
                'num_leaves': 31,
                'learning_rate': 0.05,
                'feature_fraction': 0.8,
                'verbose': -1,
            }

            model = lgb.train(
                params,
                train_data,
                num_boost_round=self.n_estimators,
                valid_sets=[val_data],
                callbacks=[
                    lgb.early_stopping(30, verbose=False),
                    lgb.log_evaluation(0),
                ],
            )

            self.models[threshold] = model

            if verbose:
                # Evaluate
                y_pred_proba = model.predict(X_val)
                from sklearn.metrics import roc_auc_score
                auc = roc_auc_score(y_val, y_pred_proba)
                print(f"  AUC: {auc:.3f} | Positive rate: {y_train.mean():.1%}")

    def predict_thresholds(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict probability of meeting each threshold."""
        df = self.prepare_features(df, fit=False)
        X = self.get_feature_matrix(df)

        results = pd.DataFrame(index=df.index)
        for threshold in self.THRESHOLDS:
            results[f'prob_top_{threshold}'] = self.models[threshold].predict(X)

        return results

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict bucket based on thresholds.

        Find the narrowest threshold where probability exceeds confidence_threshold.
        """
        probs = self.predict_thresholds(df)

        buckets = np.full(len(df), 6)  # Default to bucket 6 (finisher)

        # Go from broadest to narrowest, updating bucket when confident
        for threshold in reversed(self.THRESHOLDS):
            prob_col = f'prob_top_{threshold}'
            bucket = self.BUCKET_MAP[threshold]

            confident = probs[prob_col] >= self.confidence_threshold
            buckets[confident] = bucket

        return buckets


def main():
    print("=" * 70)
    print("PRACTICAL LOSS BUCKET PREDICTOR COMPARISON")
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

    # =========================================================================
    # MODEL 1: Standard Regression (baseline)
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODEL 1: Standard Regression (MAE Loss)")
    print("=" * 70)

    from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig

    standard_config = BucketPredictorConfig(n_estimators=300, early_stopping_rounds=50)
    standard_model = OrdinalBucketPredictor(standard_config)
    standard_model.train(train, val, verbose=True)

    y_true = test['place_bucket'].values
    y_standard = standard_model.predict(test)

    # =========================================================================
    # MODEL 2: Asymmetric Loss (penalize over-prediction more)
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODEL 2: Asymmetric Loss (3x penalty for over-prediction)")
    print("=" * 70)

    asym_config = PracticalPredictorConfig(
        n_estimators=300,
        early_stopping_rounds=50,
        asymmetry_ratio=3.0
    )
    asym_model = PracticalBucketPredictor(asym_config)
    asym_model.train(train, val, verbose=True)

    y_asym = asym_model.predict(test)

    # =========================================================================
    # MODEL 3: Threshold Predictor
    # =========================================================================
    print("\n" + "=" * 70)
    print("MODEL 3: Threshold Predictor (Binary classifiers)")
    print("=" * 70)

    threshold_model = ThresholdPredictor(n_estimators=200, confidence_threshold=0.5)
    threshold_model.train(train, val, verbose=True)

    y_threshold = threshold_model.predict(test)

    # =========================================================================
    # COMPARISON
    # =========================================================================
    print("\n" + "=" * 70)
    print("RESULTS COMPARISON")
    print("=" * 70)

    def evaluate(y_true, y_pred, name):
        mae = np.mean(np.abs(y_true - y_pred))
        accuracy = np.mean(y_true == y_pred)
        within1 = np.mean(np.abs(y_true - y_pred) <= 1)
        practical_success = np.mean(y_true <= y_pred)
        over_predict = np.mean(y_pred < y_true)
        under_predict = np.mean(y_pred > y_true)

        return {
            'name': name,
            'mae': mae,
            'accuracy': accuracy,
            'within1': within1,
            'practical_success': practical_success,
            'over_predict': over_predict,
            'under_predict': under_predict,
        }

    results = [
        evaluate(y_true, y_standard, 'Standard (MAE)'),
        evaluate(y_true, y_asym, 'Asymmetric (3x)'),
        evaluate(y_true, y_threshold, 'Threshold'),
    ]

    print(f"\n{'Model':<20} {'MAE':>8} {'Exact':>8} {'Within1':>8} {'Practical':>10} {'Over%':>8} {'Under%':>8}")
    print("-" * 80)
    for r in results:
        print(f"{r['name']:<20} {r['mae']:>8.3f} {r['accuracy']:>7.1%} {r['within1']:>7.1%} {r['practical_success']:>9.1%} {r['over_predict']:>7.1%} {r['under_predict']:>7.1%}")

    # =========================================================================
    # PREDICTION DISTRIBUTION
    # =========================================================================
    print("\n" + "=" * 70)
    print("PREDICTION DISTRIBUTION")
    print("=" * 70)

    print(f"\n{'Bucket':<10} {'Actual':>10} {'Standard':>10} {'Asymmetric':>10} {'Threshold':>10}")
    print("-" * 55)

    for bucket in range(7):
        actual_pct = (y_true == bucket).mean() * 100
        std_pct = (y_standard == bucket).mean() * 100
        asym_pct = (y_asym == bucket).mean() * 100
        thresh_pct = (y_threshold == bucket).mean() * 100
        print(f"{bucket:<10} {actual_pct:>9.1f}% {std_pct:>9.1f}% {asym_pct:>9.1f}% {thresh_pct:>9.1f}%")

    # =========================================================================
    # PER-BUCKET PRACTICAL SUCCESS
    # =========================================================================
    print("\n" + "=" * 70)
    print("PRACTICAL SUCCESS BY PREDICTED BUCKET")
    print("=" * 70)
    print("(What % of predictions for each bucket were 'met or exceeded'?)\n")

    print(f"{'Predicted':<15} {'Standard':>12} {'Asymmetric':>12} {'Threshold':>12}")
    print("-" * 55)

    for bucket in range(7):
        std_mask = y_standard == bucket
        asym_mask = y_asym == bucket
        thresh_mask = y_threshold == bucket

        std_success = (y_true[std_mask] <= bucket).mean() if std_mask.sum() > 0 else 0
        asym_success = (y_true[asym_mask] <= bucket).mean() if asym_mask.sum() > 0 else 0
        thresh_success = (y_true[thresh_mask] <= bucket).mean() if thresh_mask.sum() > 0 else 0

        print(f"Bucket {bucket:<8} {std_success:>11.1%} {asym_success:>11.1%} {thresh_success:>11.1%}")


if __name__ == '__main__':
    main()
