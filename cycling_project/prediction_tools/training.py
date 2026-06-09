"""
Training Module for Cycling Race Predictions

Orchestrates training of the complete prediction system:
1. Load and split data
2. Train bucket predictor (with optional hyperparameter tuning)
3. Train time gap predictor
4. Create race ranking predictor
5. Evaluate on test set
6. Save models
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, Literal
from datetime import datetime
import os
import json
import numpy as np

from .data_pipeline import CyclingDataPipeline, DataConfig
from .bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from .time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig
from .probability_predictor import ProbabilityPredictor, ProbabilityPredictorConfig
from .race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig
from .evaluation import (
    evaluate_full_system,
    print_evaluation_report,
    BucketEvaluator,
    TimeGapEvaluator
)


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    # Data settings
    start_date: str = '2018-01-01'
    train_end_date: str = '2022-12-31'
    val_end_date: str = '2023-06-30'
    min_races_career: int = 10

    # Model settings
    bucket_n_estimators: int = 500
    bucket_early_stopping: int = 50
    time_gap_n_estimators: int = 500
    time_gap_early_stopping: int = 50

    # Probability model settings
    probability_n_estimators: int = 500
    probability_early_stopping: int = 50

    # Training options
    train_time_gap: bool = True
    train_probability: bool = True
    train_calibrated_probability: bool = True
    train_contender_probability: bool = True
    contender_top_n: int = 15
    ranking_method: Literal['expected_bucket', 'time_gap', 'ensemble'] = 'expected_bucket'

    # Contender model tuning
    contender_learning_rate: Optional[float] = 0.01  # Lower LR for longer training (~380+ iterations)
    contender_use_oof: bool = True  # Use out-of-fold bucket predictions for filtering
    contender_oof_folds: int = 5
    contender_n_classes: Optional[int] = 5  # Merge buckets 4-6 into class 4
    contender_use_soft_weights: bool = False  # Soft weighting instead of hard filtering
    contender_soft_weight_power: float = 2.0  # Exponent for soft weighting

    # Stage 0: expose raw gradient / null-marker / race-shape columns to
    # LightGBM. Off by default so production paths are unchanged.
    include_gradient_features: bool = False

    # Stage 1: expose one-day race cluster memberships from
    # race_cluster_v1_scores. Clusters populate only on one-day rows;
    # stage / gc rows are imputed to zero. fold_label is required when
    # clusters are on (set by ExperimentRunner per fold). cluster_variant
    # picks which GMM fit to read ('race_only' or 'joint').
    include_race_clusters: bool = False
    cluster_variant: str = 'joint'
    fold_label: Optional[str] = None

    # Stage-race state: expose within-race state features from
    # rider_race_state (stage rows only; see stage_race_dynamics_plan.md).
    # Off by default so production paths are unchanged.
    include_race_state: bool = False

    # Hyperparameter tuning (optional)
    tune_hyperparameters: bool = False
    n_tuning_trials: int = 50

    # Output
    model_save_dir: Optional[str] = 'models/prediction_system'
    verbose: bool = True


class ModelTrainer:
    """
    Orchestrates training of the complete prediction system.

    Example usage:
        trainer = ModelTrainer()
        results = trainer.train_full_system()
        print_evaluation_report(results['evaluation'])
    """

    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()

        self.data_pipeline = CyclingDataPipeline(DataConfig(
            start_date=self.config.start_date,
            min_races_career=self.config.min_races_career,
            include_gradient_features=self.config.include_gradient_features,
            include_race_clusters=self.config.include_race_clusters,
            cluster_variant=self.config.cluster_variant,
            current_fold_label=self.config.fold_label,
            include_race_state=self.config.include_race_state,
        ))

        self.bucket_predictor: Optional[OrdinalBucketPredictor] = None
        self.time_gap_predictor: Optional[TimeGapPredictor] = None
        self.probability_predictor: Optional[ProbabilityPredictor] = None
        self.calibrated_predictor: Optional[ProbabilityPredictor] = None
        self.contender_predictor: Optional[ProbabilityPredictor] = None
        self.race_ranker: Optional[RaceRankingPredictor] = None

    def load_and_split_data(self):
        """Load data and create temporal splits."""
        if self.config.verbose:
            print("Loading training data...")

        df = self.data_pipeline.load_training_data()

        if self.config.verbose:
            print(f"Total samples: {len(df):,}")

        train, val, test = self.data_pipeline.get_temporal_split(
            df,
            train_end=self.config.train_end_date,
            val_end=self.config.val_end_date
        )

        if self.config.verbose:
            print(f"Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

        return train, val, test

    def train_bucket_predictor(
        self,
        train_df,
        val_df,
        best_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[OrdinalBucketPredictor, Dict[str, Any]]:
        """Train bucket prediction model."""
        if self.config.verbose:
            print("\n--- Training Bucket Predictor ---")

        config = BucketPredictorConfig(
            n_estimators=self.config.bucket_n_estimators,
            early_stopping_rounds=self.config.bucket_early_stopping
        )

        if best_params:
            config.lgb_params.update(best_params)

        model = OrdinalBucketPredictor(config)
        info = model.train(train_df, val_df, verbose=self.config.verbose)

        self.bucket_predictor = model

        return model, info

    def train_time_gap_predictor(
        self,
        train_df,
        val_df
    ) -> Tuple[TimeGapPredictor, Dict[str, Any]]:
        """Train time gap prediction model."""
        if self.config.verbose:
            print("\n--- Training Time Gap Predictor ---")

        config = TimeGapPredictorConfig(
            n_estimators=self.config.time_gap_n_estimators,
            early_stopping_rounds=self.config.time_gap_early_stopping
        )

        model = TimeGapPredictor(config)
        info = model.train(train_df, val_df, verbose=self.config.verbose)

        self.time_gap_predictor = model

        return model, info

    def train_probability_predictor(
        self,
        train_df,
        val_df
    ) -> Tuple[ProbabilityPredictor, Dict[str, Any]]:
        """Train probability prediction model."""
        if self.config.verbose:
            print("\n--- Training Probability Predictor ---")

        config = ProbabilityPredictorConfig(
            n_estimators=self.config.probability_n_estimators,
            early_stopping_rounds=self.config.probability_early_stopping
        )

        model = ProbabilityPredictor(config)
        info = model.train(train_df, val_df, verbose=self.config.verbose)

        # Calibrate temperature on validation set
        if val_df is not None:
            temp = model.calibrate_temperature(val_df)
            if self.config.verbose:
                print(f"  Calibrated temperature: {temp:.3f}")

        self.probability_predictor = model

        return model, info

    def train_calibrated_predictor(
        self,
        train_df,
        val_df
    ) -> Tuple[ProbabilityPredictor, Dict[str, Any]]:
        """Train calibrated (unweighted) probability prediction model."""
        if self.config.verbose:
            print("\n--- Training Calibrated Probability Predictor (no sample weights) ---")

        config = ProbabilityPredictorConfig(
            n_estimators=self.config.probability_n_estimators,
            early_stopping_rounds=self.config.probability_early_stopping,
            use_sample_weights=False,
        )

        model = ProbabilityPredictor(config)
        info = model.train(train_df, val_df, verbose=self.config.verbose)

        # Calibrate temperature on validation set
        if val_df is not None:
            temp = model.calibrate_temperature(val_df)
            if self.config.verbose:
                print(f"  Calibrated temperature: {temp:.3f}")

        self.calibrated_predictor = model

        return model, info

    def train_contender_predictor(
        self,
        train_df,
        val_df,
        bucket_predictor: OrdinalBucketPredictor
    ) -> Tuple[ProbabilityPredictor, Dict[str, Any]]:
        """
        Train contender probability model on filtered data with classifier feature.

        Supports multiple modes via TrainingConfig:
        - Hard filtering: top N riders per race (default)
        - Soft weighting: all riders, weighted by predicted bucket
        - OOF predictions: out-of-fold bucket predictions for filtering
        - Class reduction: merge lower buckets into fewer classes
        - Separate learning rate for the contender model
        """
        import pandas as pd

        if self.config.verbose:
            print("\n--- Training Contender Probability Predictor ---")

        top_n = self.config.contender_top_n
        use_soft = self.config.contender_use_soft_weights
        use_oof = self.config.contender_use_oof
        n_classes = self.config.contender_n_classes

        # Step 1: Get classifier predictions (OOF or direct)
        if use_oof:
            if self.config.verbose:
                print("  Using out-of-fold bucket predictions...")
            oof_predictions = self._generate_oof_bucket_predictions(
                train_df, val_df, bucket_predictor
            )
            train_with_cls = train_df.copy()
            train_with_cls['classifier_expected_bucket'] = oof_predictions
        else:
            train_with_cls = train_df.copy()
            train_with_cls['classifier_expected_bucket'] = (
                bucket_predictor.predict_continuous(train_df)
            )

        # Step 2: Filter or weight
        external_weights = None
        if use_soft:
            # Soft weighting: all riders, weighted by predicted bucket
            power = self.config.contender_soft_weight_power
            expected = train_with_cls['classifier_expected_bucket'].values
            # Exponential decay: exp(-power * expected_bucket)
            # power=2: bucket 0 → 1.0, bucket 1 → 0.14, bucket 3 → 0.002, bucket 6 → 0.000006
            external_weights = np.exp(-power * expected)
            # Normalize to mean 1
            external_weights = external_weights / external_weights.mean()

            train_filtered = train_with_cls
            if self.config.verbose:
                print(f"  Soft weighting (power={power}): all {len(train_filtered):,} samples")
                print(f"    Weight range: {external_weights.min():.6f} to {external_weights.max():.4f}")
                print(f"    Effective samples (sum weights): {external_weights.sum():.0f}")
        else:
            # Hard filtering to top N per race
            train_with_cls['_rank'] = train_with_cls.groupby(
                'competition_id'
            )['classifier_expected_bucket'].rank()
            train_filtered = train_with_cls[
                train_with_cls['_rank'] <= top_n
            ].drop(columns=['_rank'])

            if self.config.verbose:
                print(f"  Hard filter top-{top_n}: {len(train_filtered):,} from "
                      f"{len(train_with_cls):,} ({len(train_filtered)/len(train_with_cls):.1%})")

        # Step 3: Class reduction (merge lower buckets)
        if n_classes is not None and n_classes < 8:
            max_bucket = n_classes - 1
            original_dist = train_filtered['place_bucket'].value_counts().sort_index()
            train_filtered = train_filtered.copy()
            train_filtered['place_bucket'] = train_filtered['place_bucket'].clip(upper=max_bucket)
            if self.config.verbose:
                print(f"  Class reduction: 8 → {n_classes} classes (merge buckets {max_bucket}+)")

        # Show class distribution
        if self.config.verbose:
            dist = train_filtered['place_bucket'].value_counts().sort_index()
            for bucket, count in dist.items():
                print(f"    Bucket {bucket}: {count:,} ({count/len(train_filtered):.1%})")

        # Step 4: Prepare validation data (always hard-filter val for clean evaluation)
        val_filtered = None
        if val_df is not None:
            val_filtered = self._filter_to_contenders(val_df, bucket_predictor, top_n)
            if n_classes is not None and n_classes < 8:
                val_filtered = val_filtered.copy()
                val_filtered['place_bucket'] = val_filtered['place_bucket'].clip(
                    upper=n_classes - 1
                )
            if self.config.verbose:
                print(f"  Filtered val: {len(val_filtered):,} from {len(val_df):,}")

        # Step 5: Build model config with optional separate learning rate
        lr = self.config.contender_learning_rate or self.config.probability_n_estimators
        # Fix: use the probability LR from the lgb_params default if no override
        contender_lr = self.config.contender_learning_rate

        config = ProbabilityPredictorConfig(
            n_estimators=self.config.probability_n_estimators,
            early_stopping_rounds=self.config.probability_early_stopping,
            use_sample_weights=False,  # We handle weights externally
        )

        if contender_lr is not None:
            config.lgb_params['learning_rate'] = contender_lr

        if n_classes is not None:
            config.lgb_params['num_class'] = n_classes

        model = ProbabilityPredictor(config)
        info = model.train(
            train_filtered, val_filtered,
            verbose=self.config.verbose,
            external_weights=external_weights,
        )

        # Calibrate temperature on filtered validation set
        if val_filtered is not None:
            temp = model.calibrate_temperature(val_filtered)
            if self.config.verbose:
                print(f"  Calibrated temperature: {temp:.3f}")

        self.contender_predictor = model

        return model, info

    def _generate_oof_bucket_predictions(
        self, train_df, val_df, bucket_predictor: OrdinalBucketPredictor
    ) -> np.ndarray:
        """Generate out-of-fold bucket predictions to avoid leakage in contender filtering."""
        import pandas as pd

        n_folds = self.config.contender_oof_folds
        train_df = train_df.copy()

        # Sort by date for temporal folds
        if 'competition_date' not in train_df.columns:
            # Fall back to direct predictions if no date column
            return bucket_predictor.predict_continuous(train_df)

        dates = pd.to_datetime(train_df['competition_date'])
        train_df['_oof_date'] = dates

        # Create temporal fold boundaries
        date_quantiles = [dates.quantile(i / n_folds) for i in range(1, n_folds)]

        oof_predictions = np.full(len(train_df), np.nan)

        for fold_idx in range(n_folds):
            # Define fold boundaries
            if fold_idx == 0:
                fold_mask = train_df['_oof_date'] <= date_quantiles[0]
            elif fold_idx == n_folds - 1:
                fold_mask = train_df['_oof_date'] > date_quantiles[-1]
            else:
                fold_mask = (
                    (train_df['_oof_date'] > date_quantiles[fold_idx - 1]) &
                    (train_df['_oof_date'] <= date_quantiles[fold_idx])
                )

            fold_train = train_df[~fold_mask]
            fold_predict = train_df[fold_mask]

            if len(fold_predict) == 0:
                continue

            # Train a temporary bucket predictor on the non-fold data
            temp_config = BucketPredictorConfig(
                n_estimators=self.config.bucket_n_estimators,
                early_stopping_rounds=self.config.bucket_early_stopping,
            )
            temp_model = OrdinalBucketPredictor(temp_config)
            temp_model.train(fold_train, val_df, verbose=False)

            # Predict on the held-out fold
            fold_preds = temp_model.predict_continuous(fold_predict)
            oof_predictions[fold_mask.values] = fold_preds

            if self.config.verbose:
                print(f"    OOF fold {fold_idx + 1}/{n_folds}: "
                      f"trained on {len(fold_train):,}, predicted {len(fold_predict):,}")

        train_df.drop(columns=['_oof_date'], inplace=True)

        # Fill any remaining NaN with direct predictions (shouldn't happen)
        nan_mask = np.isnan(oof_predictions)
        if nan_mask.any():
            oof_predictions[nan_mask] = bucket_predictor.predict_continuous(
                train_df[nan_mask]
            )

        return oof_predictions

    @staticmethod
    def _filter_to_contenders(
        df, bucket_predictor: OrdinalBucketPredictor, top_n: int
    ):
        """Filter DataFrame to top N riders per race, adding classifier prediction as feature."""
        import pandas as pd

        df = df.copy()
        expected = bucket_predictor.predict_continuous(df)
        df['classifier_expected_bucket'] = expected

        # Keep top N per race (lowest expected_bucket = best predicted)
        df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
        filtered = df[df['_rank'] <= top_n].drop(columns=['_rank'])

        return filtered

    def tune_bucket_hyperparameters(
        self,
        train_df,
        val_df
    ) -> Dict[str, Any]:
        """
        Hyperparameter tuning for bucket predictor using Optuna.

        Returns best parameters found.
        """
        try:
            import optuna
        except ImportError:
            print("Optuna not installed. Skipping hyperparameter tuning.")
            return {}

        if self.config.verbose:
            print("\n--- Tuning Bucket Predictor Hyperparameters ---")

        def objective(trial):
            params = {
                'num_leaves': trial.suggest_int('num_leaves', 31, 127),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
                'feature_fraction': trial.suggest_float('feature_fraction', 0.6, 1.0),
                'bagging_fraction': trial.suggest_float('bagging_fraction', 0.6, 1.0),
                'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),
            }

            config = BucketPredictorConfig(
                n_estimators=200,  # Reduced for tuning
                early_stopping_rounds=30
            )
            config.lgb_params.update(params)

            model = OrdinalBucketPredictor(config)
            model.train(train_df, val_df, verbose=False)

            # Evaluate on validation
            metrics = model.evaluate(val_df)
            return metrics['mae']

        study = optuna.create_study(direction='minimize')
        study.optimize(
            objective,
            n_trials=self.config.n_tuning_trials,
            show_progress_bar=self.config.verbose
        )

        if self.config.verbose:
            print(f"Best MAE: {study.best_value:.3f}")
            print(f"Best params: {study.best_params}")

        return study.best_params

    def train_full_system(self) -> Dict[str, Any]:
        """
        Train the complete prediction system.

        Returns:
            Dictionary containing:
            - bucket_predictor: Trained OrdinalBucketPredictor
            - time_gap_predictor: Trained TimeGapPredictor (if enabled)
            - race_ranker: Configured RaceRankingPredictor
            - evaluation: Dict of test set metrics
            - training_info: Training metadata
        """
        # Load data
        train, val, test = self.load_and_split_data()

        # Hyperparameter tuning (optional)
        best_params = None
        if self.config.tune_hyperparameters:
            best_params = self.tune_bucket_hyperparameters(train, val)

        # Train bucket predictor
        bucket_model, bucket_info = self.train_bucket_predictor(
            train, val, best_params
        )

        # Train time gap predictor (optional)
        time_gap_model = None
        time_gap_info = None
        if self.config.train_time_gap:
            time_gap_model, time_gap_info = self.train_time_gap_predictor(
                train, val
            )

        # Train probability predictor (optional) — weighted
        probability_model = None
        probability_info = None
        if self.config.train_probability:
            probability_model, probability_info = self.train_probability_predictor(
                train, val
            )

        # Train calibrated probability predictor (optional) — unweighted
        calibrated_model = None
        calibrated_info = None
        if self.config.train_calibrated_probability:
            calibrated_model, calibrated_info = self.train_calibrated_predictor(
                train, val
            )

        # Train contender probability predictor (optional) — filtered + classifier feature
        contender_model = None
        contender_info = None
        if self.config.train_contender_probability:
            contender_model, contender_info = self.train_contender_predictor(
                train, val, bucket_model
            )

        # Create race ranking predictor
        race_ranker = RaceRankingPredictor(
            bucket_predictor=bucket_model,
            time_gap_predictor=time_gap_model,
            probability_predictor=probability_model,
            calibrated_predictor=calibrated_model,
            contender_predictor=contender_model,
            config=RaceRankingConfig(ranking_method=self.config.ranking_method)
        )
        self.race_ranker = race_ranker

        # Evaluate on test set
        if self.config.verbose:
            print("\n--- Evaluating on Test Set ---")

        evaluation = evaluate_full_system(
            bucket_model,
            time_gap_model,
            race_ranker,
            test,
            n_sample_races=100,
            probability_predictor=probability_model,
            calibrated_predictor=calibrated_model,
            contender_predictor=contender_model,
            contender_top_n=self.config.contender_top_n,
        )

        if self.config.verbose:
            print_evaluation_report(evaluation)

        # Save models (optional)
        if self.config.model_save_dir:
            self._save_models(
                bucket_model, time_gap_model, probability_model,
                calibrated_model, contender_model, evaluation
            )

        # Training metadata
        training_info = {
            'train_samples': len(train),
            'val_samples': len(val),
            'test_samples': len(test),
            'bucket_best_iteration': bucket_info['best_iteration'],
            'bucket_n_features': bucket_info['n_features'],
            'config': {
                'start_date': self.config.start_date,
                'train_end_date': self.config.train_end_date,
                'val_end_date': self.config.val_end_date,
                'min_races_career': self.config.min_races_career,
            },
            'timestamp': datetime.now().isoformat(),
        }

        if time_gap_info:
            training_info['time_gap_best_iteration'] = time_gap_info['best_iteration']
            training_info['time_gap_train_samples'] = time_gap_info['train_samples']

        if probability_info:
            training_info['probability_best_iteration'] = probability_info['best_iteration']

        if calibrated_info:
            training_info['calibrated_best_iteration'] = calibrated_info['best_iteration']

        if contender_info:
            training_info['contender_best_iteration'] = contender_info['best_iteration']

        if best_params:
            training_info['tuned_params'] = best_params

        return {
            'bucket_predictor': bucket_model,
            'time_gap_predictor': time_gap_model,
            'probability_predictor': probability_model,
            'calibrated_predictor': calibrated_model,
            'contender_predictor': contender_model,
            'race_ranker': race_ranker,
            'evaluation': evaluation,
            'training_info': training_info,
        }

    def _save_models(
        self,
        bucket_model: OrdinalBucketPredictor,
        time_gap_model: Optional[TimeGapPredictor],
        probability_model: Optional[ProbabilityPredictor],
        calibrated_model: Optional[ProbabilityPredictor],
        contender_model: Optional[ProbabilityPredictor],
        evaluation: Dict
    ):
        """Save trained models and metadata."""
        from .model_registry import ModelRegistry

        if self.config.verbose:
            print(f"\nSaving models to {self.config.model_save_dir}...")

        registry = ModelRegistry(self.config.model_save_dir)
        registry.save(
            bucket_predictor=bucket_model,
            time_gap_predictor=time_gap_model,
            probability_predictor=probability_model,
            calibrated_predictor=calibrated_model,
            contender_predictor=contender_model,
            evaluation=evaluation,
        )


def train_prediction_system(
    config: Optional[TrainingConfig] = None,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Convenience function to train the full prediction system.

    Args:
        config: Training configuration
        verbose: Print training progress

    Returns:
        Dictionary with trained models and evaluation results
    """
    if config is None:
        config = TrainingConfig(verbose=verbose)

    trainer = ModelTrainer(config)
    return trainer.train_full_system()


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    print("=" * 60)
    print("CYCLING RACE PREDICTION SYSTEM - TRAINING")
    print("=" * 60)

    # Quick training for testing
    config = TrainingConfig(
        bucket_n_estimators=200,
        bucket_early_stopping=30,
        time_gap_n_estimators=200,
        time_gap_early_stopping=30,
        tune_hyperparameters=False,
        model_save_dir=None,  # Don't save for test
        verbose=True
    )

    results = train_prediction_system(config)

    print("\n--- Training Complete ---")
    print(f"Bucket MAE: {results['evaluation']['bucket']['mae']:.3f}")
    print(f"Time Gap MAE: {results['evaluation']['time_gap']['mae']:.1f} seconds")
    print(f"Ranking Kendall τ: {results['evaluation']['ranking']['mean_kendall_tau']:.3f}")
