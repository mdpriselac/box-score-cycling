"""
Time Gap Predictor for Cycling Race Predictions

Predicts time gap behind winner (in seconds) using gradient boosting regression.

Key features:
1. Only trained on finishers (excludes DNF/bucket 7)
2. Uses log-transformed target for better distribution
3. Optionally excludes winners (time_gap=0)
4. Caps extreme values to handle outliers
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
class TimeGapPredictorConfig:
    """Configuration for time gap prediction model."""
    model_type: Literal['lightgbm', 'xgboost'] = 'lightgbm'

    # LightGBM parameters for regression
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

    # Target transformation
    log_transform_target: bool = True  # Use log1p(time_gap)

    # Filtering
    exclude_winners: bool = True  # Exclude time_gap=0 from training
    exclude_dnf: bool = True  # Exclude DNF (bucket 7)
    max_time_gap: float = 3600.0  # Cap at 1 hour for outlier handling


class TimeGapPredictor:
    """
    Gradient Boosting model for predicting time gap behind winner.

    Only trained on finishers (excludes DNF).
    Uses log-transformed target for better distribution of the
    highly skewed time gap values.

    Example usage:
        predictor = TimeGapPredictor()
        predictor.train(train_df, val_df)
        gaps = predictor.predict(test_df)
    """

    def __init__(self, config: Optional[TimeGapPredictorConfig] = None):
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required. Install with: pip install lightgbm")

        self.config = config or TimeGapPredictorConfig()
        self.model: Optional[lgb.Booster] = None
        self.feature_engineer = FeatureEngineer()
        self.feature_columns: Optional[List[str]] = None
        self._fitted = False

    def filter_for_training(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter data for time gap prediction.

        - Exclude DNF (bucket 7)
        - Exclude rows with null time_gap
        - Optionally exclude winners (time_gap = 0)
        - Cap extreme values

        Args:
            df: Raw data

        Returns:
            Filtered DataFrame
        """
        df = df.copy()

        # Exclude DNF
        if self.config.exclude_dnf and 'place_bucket' in df.columns:
            df = df[df['place_bucket'] != 7]

        # Exclude missing time_gap
        if 'time_gap' in df.columns:
            df = df[df['time_gap'].notna()]

            # Exclude winners (optional)
            if self.config.exclude_winners:
                df = df[df['time_gap'] > 0]

            # Cap extreme values
            df['time_gap'] = df['time_gap'].clip(upper=self.config.max_time_gap)

        return df

    def prepare_features(
        self,
        df: pd.DataFrame,
        fit: bool = True
    ) -> Tuple[pd.DataFrame, Optional[np.ndarray]]:
        """
        Prepare features for training/inference.

        Args:
            df: Raw data (already filtered)
            fit: If True, fit the feature engineer

        Returns:
            (X, y) tuple where y is the transformed target
        """
        if fit:
            df_transformed = self.feature_engineer.fit_transform(df)
            self.feature_columns = self.feature_engineer.get_feature_columns()
        else:
            df_transformed = self.feature_engineer.transform(df)

        X, _ = self.feature_engineer.get_feature_matrix(df_transformed)

        y = None
        if 'time_gap' in df.columns:
            y = df['time_gap'].values

            # Apply log transform
            if self.config.log_transform_target:
                y = np.log1p(y)

        return X, y

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: Optional[pd.DataFrame] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Train the time gap prediction model.

        Args:
            train_df: Training data with features and time_gap
            val_df: Validation data for early stopping
            verbose: Print training progress

        Returns:
            Training history/metrics dict
        """
        # Filter training data
        train_filtered = self.filter_for_training(train_df)

        if len(train_filtered) == 0:
            raise ValueError("No valid training samples after filtering")

        # Prepare features
        X_train, y_train = self.prepare_features(train_filtered, fit=True)

        if y_train is None:
            raise ValueError("Training data must contain 'time_gap' column")

        # Create LightGBM datasets
        train_data = lgb.Dataset(
            X_train, y_train,
            feature_name=self.feature_columns
        )

        valid_sets = [train_data]
        valid_names = ['train']

        if val_df is not None:
            val_filtered = self.filter_for_training(val_df)
            if len(val_filtered) > 0:
                X_val, y_val = self.prepare_features(val_filtered, fit=False)
                val_data = lgb.Dataset(
                    X_val, y_val,
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
            'train_samples': len(train_filtered),
        }

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict time gap in seconds.

        Note: Does NOT filter the input - returns predictions for all rows.
        For DNF riders, predictions may not be meaningful.

        Args:
            df: Data to predict on

        Returns:
            Array of time gap predictions (in seconds)
        """
        if not self._fitted:
            raise ValueError("Model must be trained before prediction")

        X, _ = self.prepare_features(df, fit=False)
        predictions = self.model.predict(X)

        # Inverse log transform
        if self.config.log_transform_target:
            predictions = np.expm1(predictions)

        # Ensure non-negative
        predictions = np.maximum(predictions, 0)

        return predictions

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
        filter_data: bool = True,
        return_predictions: bool = False
    ) -> Dict[str, float]:
        """
        Evaluate model on a dataset.

        Args:
            df: Data with time_gap for evaluation
            filter_data: If True, filter out DNF and winners
            return_predictions: If True, include predictions in output

        Returns:
            Dictionary of evaluation metrics
        """
        if 'time_gap' not in df.columns:
            raise ValueError("Data must contain 'time_gap' for evaluation")

        if filter_data:
            df_eval = self.filter_for_training(df)
        else:
            df_eval = df[df['time_gap'].notna()].copy()

        y_true = df_eval['time_gap'].values
        y_pred = self.predict(df_eval)

        # Compute metrics
        errors = y_true - y_pred
        abs_errors = np.abs(errors)

        metrics = {
            'mae': np.mean(abs_errors),
            'rmse': np.sqrt(np.mean(errors ** 2)),
            'median_ae': np.median(abs_errors),
            'n_samples': len(y_true),
        }

        # MAPE (exclude zeros)
        nonzero_mask = y_true > 0
        if nonzero_mask.sum() > 0:
            mape = np.mean(abs_errors[nonzero_mask] / y_true[nonzero_mask])
            metrics['mape'] = mape

        # R-squared
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        if ss_tot > 0:
            metrics['r2'] = 1 - (ss_res / ss_tot)

        # Metrics by bucket (if available)
        if 'place_bucket' in df_eval.columns:
            for bucket in range(7):  # Exclude bucket 7 (DNF)
                mask = df_eval['place_bucket'].values == bucket
                if mask.sum() > 0:
                    metrics[f'bucket_{bucket}_mae'] = np.mean(abs_errors[mask])
                    metrics[f'bucket_{bucket}_count'] = int(mask.sum())

        if return_predictions:
            metrics['predictions'] = y_pred
            metrics['y_true'] = y_true

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


def train_time_gap_predictor(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    config: Optional[TimeGapPredictorConfig] = None,
    verbose: bool = True
) -> Tuple[TimeGapPredictor, Dict[str, Any]]:
    """
    Convenience function to train a time gap predictor.

    Args:
        train_df: Training data
        val_df: Validation data (optional)
        config: Model configuration
        verbose: Print training progress

    Returns:
        (predictor, training_info) tuple
    """
    predictor = TimeGapPredictor(config)
    info = predictor.train(train_df, val_df, verbose)
    return predictor, info


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    from prediction_tools.data_pipeline import CyclingDataPipeline

    print("Testing TimeGapPredictor...")

    # Load and split data
    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    train, val, test = pipeline.get_temporal_split(df)

    print(f"Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    # Train model
    print("\nTraining time gap predictor...")
    predictor = TimeGapPredictor()
    info = predictor.train(train, val, verbose=True)

    print(f"\nBest iteration: {info['best_iteration']}")
    print(f"Training samples: {info['train_samples']:,}")

    # Feature importance
    importance = info['feature_importance']
    print("\nTop 10 features:")
    print(importance.head(10).to_string(index=False))

    # Evaluate
    print("\nEvaluating on test set...")
    metrics = predictor.evaluate(test)

    print(f"\nTest metrics:")
    print(f"  MAE: {metrics['mae']:.1f} seconds")
    print(f"  RMSE: {metrics['rmse']:.1f} seconds")
    print(f"  Median AE: {metrics['median_ae']:.1f} seconds")
    if 'r2' in metrics:
        print(f"  R²: {metrics['r2']:.3f}")
