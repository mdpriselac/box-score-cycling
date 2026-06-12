"""
Ordinal Bucket Predictor for Cycling Race Predictions

Predicts finish bucket (0-7) using gradient boosting with ordinal regression.

The model treats buckets as continuous values (0-7) which naturally respects
the ordinal nature - predicting bucket 3 when the true value is 2 has lower
error than predicting bucket 6.

Bucket scale:
    0 = Winner (1st place)
    1 = Podium (2nd-3rd)
    2 = Top 5 (4th-5th)
    3 = Top 15 (6th-15th)
    4 = Top 30 (16th-30th)
    5 = Top 50 (31st-50th)
    6 = Finisher (51st+)
    7 = DNF/DNS/OTL
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List, Literal
import numpy as np
import pandas as pd
import warnings

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    warnings.warn("LightGBM not installed. Install with: pip install lightgbm")

from .feature_engineering import FeatureEngineer, FeatureConfig


@dataclass
class BucketPredictorConfig:
    """Configuration for bucket prediction model."""
    model_type: Literal['lightgbm', 'xgboost'] = 'lightgbm'

    # LightGBM parameters for ordinal regression (using regression objective)
    lgb_params: Dict[str, Any] = field(default_factory=lambda: {
        'objective': 'regression',
        'metric': 'mae',
        'boosting_type': 'gbdt',
        'num_leaves': 63,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'min_child_samples': 20,
        'verbose': -1,
        'seed': 42,
    })

    # Training parameters
    n_estimators: int = 500
    early_stopping_rounds: int = 50

    # Whether to use sample weights for class imbalance
    use_sample_weights: bool = True

    # Clamp predictions to valid range
    min_bucket: float = 0.0
    max_bucket: float = 7.0


class OrdinalBucketPredictor:
    """
    Gradient Boosting model for predicting finish bucket (0-7).

    Uses LightGBM with regression objective to respect ordinal nature.
    Predictions can be:
    - Continuous (for ranking): predict_continuous()
    - Discrete classes (for classification): predict()
    - Probability distribution (for uncertainty): predict_proba()

    Example usage:
        predictor = OrdinalBucketPredictor()
        predictor.train(train_df, val_df)
        buckets = predictor.predict(test_df)
        continuous = predictor.predict_continuous(test_df)
    """

    def __init__(self, config: Optional[BucketPredictorConfig] = None):
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required. Install with: pip install lightgbm")

        self.config = config or BucketPredictorConfig()
        self.model: Optional[lgb.Booster] = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns: Optional[List[str]] = None
        self._fitted = False

    def prepare_features(
        self,
        df: pd.DataFrame,
        fit: bool = True
    ) -> Tuple[pd.DataFrame, Optional[np.ndarray]]:
        """
        Prepare features for training/inference.

        Args:
            df: Raw data from data_pipeline
            fit: If True, fit the feature engineer (for training)

        Returns:
            (X, y) tuple where y is None if 'place_bucket' not in df
        """
        if fit:
            df_transformed = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.get_feature_columns()
        else:
            df_transformed = self.feature_engineer.transform(df)

        X, y = self.feature_engineer.get_feature_matrix(
            df_transformed, include_target=True
        )

        if y is not None:
            y = y.values

        return X, y

    def compute_sample_weights(self, y: np.ndarray) -> np.ndarray:
        """
        Compute sample weights for imbalanced bucket distribution.

        Uses inverse frequency weighting to give more importance to rare buckets.
        """
        unique, counts = np.unique(y, return_counts=True)
        total = len(y)

        # Inverse frequency weighting
        weights_map = {
            bucket: total / (len(unique) * count)
            for bucket, count in zip(unique, counts)
        }

        weights = np.array([weights_map.get(yi, 1.0) for yi in y])

        # Normalize to mean 1
        weights = weights / weights.mean()

        return weights

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
        verbose: bool = True,
        external_weights: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Train the bucket prediction model.

        Args:
            train_df: Training data with features and place_bucket
            val_df: Validation data for early stopping
            verbose: Print training progress
            external_weights: Optional per-row weights aligned to train_df row
                order (e.g. placement-informativeness weights). Multiplied
                with class-balance weights when both are enabled.

        Returns:
            Training history/metrics dict
        """
        # Prepare features
        X_train, y_train = self.prepare_features(train_df, fit=True)

        if y_train is None:
            raise ValueError("Training data must contain 'place_bucket' column")

        # Compute sample weights
        sample_weights = None
        if self.config.use_sample_weights:
            sample_weights = self.compute_sample_weights(y_train)
        if external_weights is not None:
            ext = np.asarray(external_weights, dtype=float)
            if len(ext) != len(y_train):
                raise ValueError(
                    f"external_weights length {len(ext)} != train rows {len(y_train)}"
                )
            sample_weights = ext if sample_weights is None else sample_weights * ext

        # Create LightGBM datasets
        train_data = lgb.Dataset(
            X_train, y_train,
            weight=sample_weights,
            feature_name=self.feature_columns
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if val_df is not None:
            X_val, y_val = self.prepare_features(val_df, fit=False)
            val_weights = None
            if self.config.use_sample_weights:
                val_weights = self.compute_sample_weights(y_val)

            val_data = lgb.Dataset(
                X_val, y_val,
                weight=val_weights,
                reference=train_data
            )
            valid_sets.append(val_data)
            valid_names.append('val')

        # Training callbacks
        callbacks = []
        if verbose:
            callbacks.append(lgb.log_evaluation(period=50))
        if self.config.early_stopping_rounds:
            callbacks.append(
                lgb.early_stopping(
                    stopping_rounds=self.config.early_stopping_rounds,
                    verbose=verbose
                )
            )

        # Train model
        self.model = lgb.train(
            self.config.lgb_params,
            train_data,
            num_boost_round=self.config.n_estimators,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks
        )

        self._fitted = True

        return {
            'feature_importance': self.get_feature_importance(),
            'best_iteration': self.model.best_iteration,
            'n_features': len(self.feature_columns),
        }

    def predict_continuous(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict continuous bucket value (0-7 range).

        Use this for ranking - lower values indicate better expected finish.

        Args:
            df: Data to predict on

        Returns:
            Array of continuous predictions (clamped to [0, 7])
        """
        if not self._fitted:
            raise ValueError("Model must be trained before prediction")

        X, _ = self.prepare_features(df, fit=False)
        predictions = self.model.predict(X)

        # Clamp to valid range
        predictions = np.clip(
            predictions,
            self.config.min_bucket,
            self.config.max_bucket
        )

        return predictions

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict bucket class (0-7 integer).

        Rounds continuous predictions to nearest integer bucket.

        Args:
            df: Data to predict on

        Returns:
            Array of integer bucket predictions
        """
        continuous = self.predict_continuous(df)
        return np.round(continuous).astype(int)

    def predict_proba(self, df: pd.DataFrame, std_estimate: float = 1.2) -> np.ndarray:
        """
        Estimate probability distribution over buckets.

        Since we use regression, we estimate probabilities using a
        Gaussian distribution centered on the predicted value.

        Args:
            df: Data to predict on
            std_estimate: Standard deviation for probability estimation

        Returns:
            Array of shape (n_samples, 8) with bucket probabilities
        """
        continuous = self.predict_continuous(df)
        n_samples = len(continuous)
        n_buckets = 8

        # Compute probability for each bucket using Gaussian CDF
        proba = np.zeros((n_samples, n_buckets))

        for bucket in range(n_buckets):
            # Use bucket boundaries for probability calculation
            if bucket == 0:
                lower, upper = -np.inf, 0.5
            elif bucket == 7:
                lower, upper = 6.5, np.inf
            else:
                lower, upper = bucket - 0.5, bucket + 0.5

            from scipy import stats
            proba[:, bucket] = (
                stats.norm.cdf(upper, loc=continuous, scale=std_estimate) -
                stats.norm.cdf(lower, loc=continuous, scale=std_estimate)
            )

        # Normalize to sum to 1
        proba = proba / proba.sum(axis=1, keepdims=True)

        return proba

    def get_feature_importance(self, importance_type: str = 'gain') -> pd.DataFrame:
        """
        Get feature importance from trained model.

        Args:
            importance_type: Type of importance ('gain', 'split')

        Returns:
            DataFrame with feature names and importance scores
        """
        if not self._fitted:
            raise ValueError("Model must be trained before getting importance")

        importance = self.model.feature_importance(importance_type=importance_type)

        return pd.DataFrame({
            'feature': self.feature_columns,
            'importance': importance
        }).sort_values('importance', ascending=False)

    def evaluate(
        self,
        df: pd.DataFrame,
        return_predictions: bool = False
    ) -> Dict[str, float]:
        """
        Evaluate model on a dataset.

        Args:
            df: Data with place_bucket for evaluation
            return_predictions: If True, include predictions in output

        Returns:
            Dictionary of evaluation metrics
        """
        if 'place_bucket' not in df.columns:
            raise ValueError("Data must contain 'place_bucket' for evaluation")

        y_true = df['place_bucket'].values
        y_pred_continuous = self.predict_continuous(df)
        y_pred = self.predict(df)

        # Compute metrics
        diff = np.abs(y_true - y_pred)

        metrics = {
            'mae': np.mean(np.abs(y_true - y_pred_continuous)),
            'mae_rounded': np.mean(diff),
            'accuracy': np.mean(y_true == y_pred),
            'within_1': np.mean(diff <= 1),
            'within_2': np.mean(diff <= 2),
        }

        # Per-bucket accuracy
        for bucket in range(8):
            mask = y_true == bucket
            if mask.sum() > 0:
                metrics[f'bucket_{bucket}_accuracy'] = np.mean(y_pred[mask] == bucket)
                metrics[f'bucket_{bucket}_count'] = int(mask.sum())

        if return_predictions:
            metrics['predictions'] = y_pred
            metrics['predictions_continuous'] = y_pred_continuous

        return metrics

    def save(self, path: str):
        """Save model to file."""
        if not self._fitted:
            raise ValueError("Model must be trained before saving")
        self.model.save_model(path)

    def load(self, path: str):
        """Load model from file."""
        self.model = lgb.Booster(model_file=path)
        self._fitted = True


def train_bucket_predictor(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    config: Optional[BucketPredictorConfig] = None,
    verbose: bool = True
) -> Tuple[OrdinalBucketPredictor, Dict[str, Any]]:
    """
    Convenience function to train a bucket predictor.

    Args:
        train_df: Training data
        val_df: Validation data (optional)
        config: Model configuration
        verbose: Print training progress

    Returns:
        (predictor, training_info) tuple
    """
    predictor = OrdinalBucketPredictor(config)
    info = predictor.train(train_df, val_df, verbose)
    return predictor, info


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    from prediction_tools.data_pipeline import CyclingDataPipeline

    print("Testing OrdinalBucketPredictor...")

    # Load and split data
    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    train, val, test = pipeline.get_temporal_split(df)

    print(f"Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    # Train model
    print("\nTraining bucket predictor...")
    predictor = OrdinalBucketPredictor()
    info = predictor.train(train, val, verbose=True)

    print(f"\nBest iteration: {info['best_iteration']}")
    print(f"N features: {info['n_features']}")

    # Feature importance
    importance = info['feature_importance']
    print("\nTop 10 features:")
    print(importance.head(10).to_string(index=False))

    # Evaluate
    print("\nEvaluating on test set...")
    metrics = predictor.evaluate(test)

    print(f"\nTest metrics:")
    print(f"  MAE: {metrics['mae']:.3f}")
    print(f"  Accuracy: {metrics['accuracy']:.3f}")
    print(f"  Within-1: {metrics['within_1']:.3f}")
    print(f"  Within-2: {metrics['within_2']:.3f}")
