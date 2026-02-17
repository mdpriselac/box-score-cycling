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

    # Training options
    train_time_gap: bool = True
    ranking_method: Literal['expected_bucket', 'time_gap', 'ensemble'] = 'expected_bucket'

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
            min_races_career=self.config.min_races_career
        ))

        self.bucket_predictor: Optional[OrdinalBucketPredictor] = None
        self.time_gap_predictor: Optional[TimeGapPredictor] = None
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

        # Create race ranking predictor
        race_ranker = RaceRankingPredictor(
            bucket_predictor=bucket_model,
            time_gap_predictor=time_gap_model,
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
            n_sample_races=100
        )

        if self.config.verbose:
            print_evaluation_report(evaluation)

        # Save models (optional)
        if self.config.model_save_dir:
            self._save_models(bucket_model, time_gap_model, evaluation)

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

        if best_params:
            training_info['tuned_params'] = best_params

        return {
            'bucket_predictor': bucket_model,
            'time_gap_predictor': time_gap_model,
            'race_ranker': race_ranker,
            'evaluation': evaluation,
            'training_info': training_info,
        }

    def _save_models(
        self,
        bucket_model: OrdinalBucketPredictor,
        time_gap_model: Optional[TimeGapPredictor],
        evaluation: Dict
    ):
        """Save trained models and metadata."""
        if self.config.verbose:
            print(f"\nSaving models to {self.config.model_save_dir}...")

        os.makedirs(self.config.model_save_dir, exist_ok=True)

        # Save bucket model
        bucket_path = os.path.join(self.config.model_save_dir, 'bucket_model.txt')
        bucket_model.save(bucket_path)

        # Save time gap model
        if time_gap_model:
            time_gap_path = os.path.join(self.config.model_save_dir, 'time_gap_model.txt')
            time_gap_model.save(time_gap_path)

        # Save metadata
        metadata = {
            'evaluation': evaluation,
            'timestamp': datetime.now().isoformat(),
            'config': self.config.__dict__,
        }

        # Convert non-serializable items
        metadata_clean = json.loads(
            json.dumps(metadata, default=str)
        )

        metadata_path = os.path.join(self.config.model_save_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata_clean, f, indent=2)

        if self.config.verbose:
            print(f"Models saved successfully")


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
