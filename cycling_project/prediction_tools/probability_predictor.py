"""
Probability Predictor for Cycling Race Predictions

Predicts probability distribution over finish buckets (0-7) using
LightGBM multiclass classification with softmax output.

Unlike the OrdinalBucketPredictor (which uses regression for ranking),
this model is specifically trained to produce calibrated probabilities
for each bucket. It also derives cumulative probabilities that respect
the hierarchical bucket structure:

    Bucket 0: Winner (1st)
    Bucket 1: Podium (2nd-3rd)
    Bucket 2: Top 5 (4th-5th)
    Bucket 3: Top 15 (6th-15th)
    Bucket 4: Top 30 (16th-30th)
    Bucket 5: Top 50 (31st-50th)
    Bucket 6: Finisher (51st+)
    Bucket 7: DNF/DNS/OTL

Buckets 0-6 are cumulative (a winner is also podium, top 5, etc.).
Bucket 7 (DNF) is mutually exclusive with finishing.
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

# Cumulative bucket labels for display
CUMULATIVE_LABELS = {
    'win': [0],           # P(bucket 0)
    'podium': [0, 1],     # P(bucket 0 or 1) = P(top 3)
    'top5': [0, 1, 2],    # P(top 5)
    'top15': [0, 1, 2, 3],
    'top30': [0, 1, 2, 3, 4],
    'top50': [0, 1, 2, 3, 4, 5],
    'finish': [0, 1, 2, 3, 4, 5, 6],
    'dnf': [7],           # Standalone, not cumulative
}

MAX_ODDS = 999.0


@dataclass
class ProbabilityPredictorConfig:
    """Configuration for probability prediction model."""
    model_type: Literal['lightgbm', 'xgboost'] = 'lightgbm'

    # LightGBM parameters for multiclass classification
    lgb_params: Dict[str, Any] = field(default_factory=lambda: {
        'objective': 'multiclass',
        'num_class': 8,
        'metric': 'multi_logloss',
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

    # Temperature scaling for calibration (1.0 = no scaling)
    temperature: float = 1.0


class ProbabilityPredictor:
    """
    LightGBM multiclass model for predicting bucket probabilities.

    Produces native softmax probabilities for each of the 8 buckets,
    and derives cumulative probabilities for hierarchical categories
    (Win, Podium, Top 5, etc.) and decimal odds.

    Example usage:
        predictor = ProbabilityPredictor()
        predictor.train(train_df, val_df)

        proba = predictor.predict_proba(test_df)  # (n, 8) array
        cumulative = predictor.predict_cumulative_proba(test_df)  # DataFrame
        odds = predictor.predict_odds(test_df)  # DataFrame with decimal odds
    """

    def __init__(self, config: Optional[ProbabilityPredictorConfig] = None):
        if not HAS_LIGHTGBM:
            raise ImportError("LightGBM is required. Install with: pip install lightgbm")

        self.config = config or ProbabilityPredictorConfig()
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
            y = y.values.astype(int)

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
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Train the probability prediction model.

        Args:
            train_df: Training data with features and place_bucket
            val_df: Validation data for early stopping
            verbose: Print training progress

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

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict probability distribution over buckets.

        Returns native softmax probabilities from the multiclass model,
        with optional temperature scaling for calibration.

        Args:
            df: Data to predict on

        Returns:
            Array of shape (n_samples, 8) with bucket probabilities
        """
        if not self._fitted:
            raise ValueError("Model must be trained before prediction")

        X, _ = self.prepare_features(df, fit=False)

        if self.config.temperature != 1.0:
            # Get raw logits and apply temperature scaling
            raw_scores = self.model.predict(X, raw_score=True)
            scaled = raw_scores / self.config.temperature
            # Softmax
            exp_scaled = np.exp(scaled - scaled.max(axis=1, keepdims=True))
            proba = exp_scaled / exp_scaled.sum(axis=1, keepdims=True)
        else:
            # Standard softmax output from LightGBM
            proba = self.model.predict(X)

        return proba

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict most likely bucket class (0-7 integer).

        Args:
            df: Data to predict on

        Returns:
            Array of integer bucket predictions
        """
        proba = self.predict_proba(df)
        return np.argmax(proba, axis=1)

    def predict_cumulative_proba(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict cumulative probabilities respecting bucket hierarchy.

        Buckets 0-6 are cumulative (winner is also podium, top 5, etc.).
        DNF (bucket 7) is standalone.

        Args:
            df: Data to predict on

        Returns:
            DataFrame with columns: prob_win, prob_podium, prob_top5,
            prob_top15, prob_top30, prob_top50, prob_finish, prob_dnf
        """
        proba = self.predict_proba(df)

        result = {}
        for label, buckets in CUMULATIVE_LABELS.items():
            result[f'prob_{label}'] = proba[:, buckets].sum(axis=1)

        return pd.DataFrame(result)

    def predict_odds(
        self,
        df: pd.DataFrame,
        odds_format: str = 'decimal'
    ) -> pd.DataFrame:
        """
        Predict decimal odds from cumulative probabilities.

        Decimal odds = 1 / probability. Capped at MAX_ODDS (999.0) to
        avoid extreme values for very unlikely outcomes.

        Args:
            df: Data to predict on
            odds_format: 'decimal' (default). Only decimal supported currently.

        Returns:
            DataFrame with columns: odds_win, odds_podium, odds_top5,
            odds_top15, odds_top30, odds_top50, odds_finish, odds_dnf
        """
        cumulative = self.predict_cumulative_proba(df)

        result = {}
        for col in cumulative.columns:
            label = col.replace('prob_', '')
            prob = cumulative[col].values
            # Avoid division by zero, cap at MAX_ODDS
            odds = np.where(prob > 0, 1.0 / prob, MAX_ODDS)
            odds = np.minimum(odds, MAX_ODDS)
            result[f'odds_{label}'] = np.round(odds, 2)

        return pd.DataFrame(result)

    def calibrate_temperature(self, val_df: pd.DataFrame) -> float:
        """
        Fit temperature scaling on validation data to improve calibration.

        Temperature scaling adjusts confidence without changing predictions:
        - T < 1.0: sharper (more confident) probabilities
        - T > 1.0: smoother (less confident) probabilities

        Args:
            val_df: Validation data with place_bucket labels

        Returns:
            Optimal temperature value
        """
        from scipy.optimize import minimize_scalar

        X, y = self.prepare_features(val_df, fit=False)
        if y is None:
            raise ValueError("Validation data must contain 'place_bucket' column")

        # Get raw logits (pre-softmax)
        raw_scores = self.model.predict(X, raw_score=True)

        def nll_with_temp(T):
            scaled = raw_scores / T
            # Numerically stable softmax
            shifted = scaled - scaled.max(axis=1, keepdims=True)
            exp_scaled = np.exp(shifted)
            probs = exp_scaled / exp_scaled.sum(axis=1, keepdims=True)
            # Negative log-likelihood
            log_probs = np.log(probs[np.arange(len(y)), y] + 1e-12)
            return -np.mean(log_probs)

        result = minimize_scalar(nll_with_temp, bounds=(0.1, 10.0), method='bounded')
        self.config.temperature = result.x

        return self.config.temperature

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
        Evaluate probability model on a dataset.

        Args:
            df: Data with place_bucket for evaluation
            return_predictions: If True, include predictions in output

        Returns:
            Dictionary of evaluation metrics
        """
        if 'place_bucket' not in df.columns:
            raise ValueError("Data must contain 'place_bucket' for evaluation")

        y_true = df['place_bucket'].values.astype(int)
        proba = self.predict_proba(df)
        y_pred = np.argmax(proba, axis=1)

        n_samples = len(y_true)
        n_buckets = 8

        # Log loss
        one_hot = np.zeros((n_samples, n_buckets))
        one_hot[np.arange(n_samples), y_true] = 1.0
        log_probs = np.log(proba[np.arange(n_samples), y_true] + 1e-12)
        log_loss = -np.mean(log_probs)

        # Brier score (multiclass)
        brier = np.mean(np.sum((one_hot - proba) ** 2, axis=1))

        # Top-1 accuracy (argmax correct)
        accuracy = np.mean(y_pred == y_true)

        # Sharpness (mean max probability)
        sharpness = np.mean(np.max(proba, axis=1))

        # Within-1 accuracy
        diff = np.abs(y_true - y_pred)
        within_1 = np.mean(diff <= 1)

        metrics = {
            'log_loss': log_loss,
            'brier_score': brier,
            'accuracy': accuracy,
            'within_1': within_1,
            'sharpness': sharpness,
        }

        # Per-bucket calibration error
        calibration_errors = []
        for bucket in range(n_buckets):
            actual_freq = np.mean(y_true == bucket)
            predicted_prob = np.mean(proba[:, bucket])
            cal_error = abs(predicted_prob - actual_freq)
            calibration_errors.append(cal_error)
            metrics[f'bucket_{bucket}_cal_error'] = cal_error
            metrics[f'bucket_{bucket}_accuracy'] = (
                np.mean(y_pred[y_true == bucket] == bucket) if np.sum(y_true == bucket) > 0 else 0.0
            )
            metrics[f'bucket_{bucket}_count'] = int(np.sum(y_true == bucket))

        metrics['mean_calibration_error'] = np.mean(calibration_errors)

        # Expected Calibration Error (ECE) - binned by confidence
        max_probs = np.max(proba, axis=1)
        correct = (y_pred == y_true).astype(float)
        n_bins = 10
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            mask = (max_probs > bin_boundaries[i]) & (max_probs <= bin_boundaries[i + 1])
            if mask.sum() > 0:
                bin_acc = correct[mask].mean()
                bin_conf = max_probs[mask].mean()
                ece += mask.sum() / n_samples * abs(bin_acc - bin_conf)
        metrics['ece'] = ece

        if return_predictions:
            metrics['predictions'] = y_pred
            metrics['probabilities'] = proba

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


def train_probability_predictor(
    train_df: pd.DataFrame,
    val_df: Optional[pd.DataFrame] = None,
    config: Optional[ProbabilityPredictorConfig] = None,
    verbose: bool = True
) -> Tuple[ProbabilityPredictor, Dict[str, Any]]:
    """
    Convenience function to train a probability predictor.

    Args:
        train_df: Training data
        val_df: Validation data (optional)
        config: Model configuration
        verbose: Print training progress

    Returns:
        (predictor, training_info) tuple
    """
    predictor = ProbabilityPredictor(config)
    info = predictor.train(train_df, val_df, verbose)
    return predictor, info
