"""
Model Registry for Cycling Race Predictions

Handles saving and loading of trained models with metadata.

Directory structure:
    models/prediction_system/
        bucket_model.txt         # LightGBM model
        time_gap_model.txt       # LightGBM model
        feature_columns.json     # Feature column names
        metadata.json            # Training metadata and evaluation
"""

import os
import json
import pickle
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import logging

logger = logging.getLogger(__name__)

from .bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
from .time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig
from .probability_predictor import ProbabilityPredictor, ProbabilityPredictorConfig
from .race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig
from .feature_engineering import FeatureEngineer


class ModelRegistry:
    """
    Handles saving and loading of trained models with metadata.

    Stores:
    - LightGBM model files
    - Feature column configurations
    - Training metadata and evaluation metrics
    - Feature engineer state

    Example usage:
        # Save
        registry = ModelRegistry('models/v1')
        registry.save(bucket_predictor, time_gap_predictor, probability_predictor,
                       calibrated_predictor, contender_predictor, evaluation)

        # Load
        bucket_pred, time_gap_pred, weighted, calibrated, contender = registry.load()
    """

    def __init__(self, base_dir: str = 'models/prediction_system'):
        self.base_dir = Path(base_dir)

    def _archive_existing(self) -> Optional[Path]:
        """Archive the current model directory before overwriting.

        Copies all files to models/history/<timestamp>_<label>/ where the
        label comes from existing metadata (date range, sample count).
        Returns the archive path, or None if nothing to archive.
        """
        metadata_path = self.base_dir / 'metadata.json'
        if not metadata_path.exists():
            return None

        # Build a descriptive label from existing metadata
        try:
            with open(metadata_path) as f:
                meta = json.load(f)
            saved_at = meta.get('saved_at', '')[:10]  # YYYY-MM-DD
            training_info = meta.get('training_info', {})
            date_range = training_info.get('date_range', '')
            # Use the end date of the training range as the label
            train_end = date_range.split(' to ')[-1] if ' to ' in date_range else saved_at
            label = train_end
        except Exception:
            label = 'unknown'

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_dir = self.base_dir.parent / 'history' / f"{timestamp}_{label}"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Copy all model files to the archive
        for item in self.base_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, archive_dir / item.name)

        logger.info(f"Archived previous model to {archive_dir}")
        print(f"Archived previous model to {archive_dir}")
        return archive_dir

    def save(
        self,
        bucket_predictor: OrdinalBucketPredictor,
        time_gap_predictor: Optional[TimeGapPredictor] = None,
        probability_predictor: Optional[ProbabilityPredictor] = None,
        calibrated_predictor: Optional[ProbabilityPredictor] = None,
        contender_predictor: Optional[ProbabilityPredictor] = None,
        evaluation: Optional[Dict[str, Any]] = None,
        training_info: Optional[Dict[str, Any]] = None
    ):
        """
        Save trained models and metadata.

        Args:
            bucket_predictor: Trained bucket prediction model
            time_gap_predictor: Optional trained time gap model
            probability_predictor: Optional weighted probability model
            calibrated_predictor: Optional calibrated (unweighted) probability model
            contender_predictor: Optional contender (filtered + classifier feature) probability model
            evaluation: Optional evaluation metrics
            training_info: Optional training metadata
        """
        # Archive existing models before overwriting
        self._archive_existing()

        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Save bucket model
        bucket_model_path = self.base_dir / 'bucket_model.txt'
        bucket_predictor.save(str(bucket_model_path))

        # Save bucket feature engineer
        bucket_fe_path = self.base_dir / 'bucket_feature_engineer.pkl'
        with open(bucket_fe_path, 'wb') as f:
            pickle.dump({
                'feature_columns': bucket_predictor.feature_columns,
                'feature_engineer': bucket_predictor.feature_engineer,
            }, f)

        # Save time gap model (optional)
        if time_gap_predictor is not None:
            time_gap_model_path = self.base_dir / 'time_gap_model.txt'
            time_gap_predictor.save(str(time_gap_model_path))

            time_gap_fe_path = self.base_dir / 'time_gap_feature_engineer.pkl'
            with open(time_gap_fe_path, 'wb') as f:
                pickle.dump({
                    'feature_columns': time_gap_predictor.feature_columns,
                    'feature_engineer': time_gap_predictor.feature_engineer,
                }, f)

        # Save probability models
        for predictor, suffix in [
            (probability_predictor, 'weighted'),
            (calibrated_predictor, 'calibrated'),
            (contender_predictor, 'contender'),
        ]:
            if predictor is not None:
                self._save_probability_model(predictor, suffix)

        # Save metadata
        metadata = {
            'has_time_gap_model': time_gap_predictor is not None,
            'has_probability_model': probability_predictor is not None,
            'has_calibrated_model': calibrated_predictor is not None,
            'has_contender_model': contender_predictor is not None,
            'bucket_feature_columns': bucket_predictor.feature_columns,
            'saved_at': datetime.now().isoformat(),
        }

        if evaluation:
            metadata['evaluation'] = self._make_json_safe(evaluation)

        if training_info:
            metadata['training_info'] = self._make_json_safe(training_info)

        metadata_path = self.base_dir / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"Models saved to {self.base_dir}")

    def _save_probability_model(self, predictor: ProbabilityPredictor, suffix: str):
        """Save a single probability model and its feature engineer."""
        model_path = self.base_dir / f'probability_model_{suffix}.txt'
        predictor.save(str(model_path))

        fe_path = self.base_dir / f'probability_feature_engineer_{suffix}.pkl'
        with open(fe_path, 'wb') as f:
            pickle.dump({
                'feature_columns': predictor.feature_columns,
                'feature_engineer': predictor.feature_engineer,
                'temperature': predictor.config.temperature,
            }, f)

    def _load_probability_model(
        self, model_filename: str, fe_filename: str
    ) -> Optional[ProbabilityPredictor]:
        """Load a single probability model and its feature engineer."""
        model_path = self.base_dir / model_filename
        if not model_path.exists():
            return None

        predictor = ProbabilityPredictor()
        predictor.load(str(model_path))

        fe_path = self.base_dir / fe_filename
        if fe_path.exists():
            with open(fe_path, 'rb') as f:
                fe_data = pickle.load(f)
                predictor.feature_columns = fe_data['feature_columns']
                predictor.feature_engineer = fe_data['feature_engineer']
                if 'temperature' in fe_data:
                    predictor.config.temperature = fe_data['temperature']

        return predictor

    def load(
        self,
        load_time_gap: bool = True,
        load_probability: bool = True
    ) -> Tuple[
        OrdinalBucketPredictor,
        Optional[TimeGapPredictor],
        Optional[ProbabilityPredictor],
        Optional[ProbabilityPredictor],
        Optional[ProbabilityPredictor],
    ]:
        """
        Load trained models from disk.

        Args:
            load_time_gap: If True, also load time gap model if available
            load_probability: If True, also load probability models if available

        Returns:
            (bucket_predictor, time_gap_predictor,
             weighted_prob, calibrated_prob, contender_prob) tuple
        """
        # Load metadata
        metadata_path = self.base_dir / 'metadata.json'
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found at {metadata_path}")

        with open(metadata_path, 'r') as f:
            metadata = json.load(f)

        # Load bucket model
        bucket_model_path = self.base_dir / 'bucket_model.txt'
        bucket_predictor = OrdinalBucketPredictor()
        bucket_predictor.load(str(bucket_model_path))

        # Load bucket feature engineer
        bucket_fe_path = self.base_dir / 'bucket_feature_engineer.pkl'
        if bucket_fe_path.exists():
            with open(bucket_fe_path, 'rb') as f:
                fe_data = pickle.load(f)
                bucket_predictor.feature_columns = fe_data['feature_columns']
                bucket_predictor.feature_engineer = fe_data['feature_engineer']

        # Load time gap model (optional)
        time_gap_predictor = None
        if load_time_gap and metadata.get('has_time_gap_model', False):
            time_gap_model_path = self.base_dir / 'time_gap_model.txt'
            if time_gap_model_path.exists():
                time_gap_predictor = TimeGapPredictor()
                time_gap_predictor.load(str(time_gap_model_path))

                time_gap_fe_path = self.base_dir / 'time_gap_feature_engineer.pkl'
                if time_gap_fe_path.exists():
                    with open(time_gap_fe_path, 'rb') as f:
                        fe_data = pickle.load(f)
                        time_gap_predictor.feature_columns = fe_data['feature_columns']
                        time_gap_predictor.feature_engineer = fe_data['feature_engineer']

        # Load probability models (optional)
        weighted_prob = None
        calibrated_prob = None
        contender_prob = None
        if load_probability:
            # New dual/triple-model format
            if metadata.get('has_probability_model', False):
                weighted_prob = self._load_probability_model(
                    'probability_model_weighted.txt',
                    'probability_feature_engineer_weighted.pkl'
                )
                # Backward compat: legacy single model -> treat as weighted
                if weighted_prob is None:
                    weighted_prob = self._load_probability_model(
                        'probability_model.txt',
                        'probability_feature_engineer.pkl'
                    )

            if metadata.get('has_calibrated_model', False):
                calibrated_prob = self._load_probability_model(
                    'probability_model_calibrated.txt',
                    'probability_feature_engineer_calibrated.pkl'
                )

            if metadata.get('has_contender_model', False):
                contender_prob = self._load_probability_model(
                    'probability_model_contender.txt',
                    'probability_feature_engineer_contender.pkl'
                )

        print(f"Models loaded from {self.base_dir}")

        return bucket_predictor, time_gap_predictor, weighted_prob, calibrated_prob, contender_prob

    def load_with_ranker(
        self,
        ranking_method: str = 'expected_bucket'
    ) -> Tuple[OrdinalBucketPredictor, Optional[TimeGapPredictor], RaceRankingPredictor]:
        """
        Load models and create race ranker.

        Args:
            ranking_method: Method for ranking ('expected_bucket', 'time_gap', 'ensemble')

        Returns:
            (bucket_predictor, time_gap_predictor, race_ranker) tuple
        """
        bucket_pred, time_gap_pred, weighted_prob, calibrated_prob, contender_prob = self.load()

        race_ranker = RaceRankingPredictor(
            bucket_predictor=bucket_pred,
            time_gap_predictor=time_gap_pred,
            probability_predictor=weighted_prob,
            calibrated_predictor=calibrated_prob,
            contender_predictor=contender_prob,
            config=RaceRankingConfig(ranking_method=ranking_method)
        )

        return bucket_pred, time_gap_pred, race_ranker

    def get_metadata(self) -> Dict[str, Any]:
        """Get saved metadata."""
        metadata_path = self.base_dir / 'metadata.json'
        if not metadata_path.exists():
            return {}

        with open(metadata_path, 'r') as f:
            return json.load(f)

    def get_evaluation(self) -> Optional[Dict[str, Any]]:
        """Get saved evaluation metrics."""
        metadata = self.get_metadata()
        return metadata.get('evaluation')

    def exists(self) -> bool:
        """Check if models exist at this path."""
        return (self.base_dir / 'bucket_model.txt').exists()

    def _make_json_safe(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_json_safe(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_safe(v) for v in obj]
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        else:
            return str(obj)


def save_models(
    bucket_predictor: OrdinalBucketPredictor,
    time_gap_predictor: Optional[TimeGapPredictor] = None,
    path: str = 'models/prediction_system',
    evaluation: Optional[Dict] = None
):
    """
    Convenience function to save models.

    Args:
        bucket_predictor: Trained bucket model
        time_gap_predictor: Optional trained time gap model
        path: Directory to save to
        evaluation: Optional evaluation metrics
    """
    registry = ModelRegistry(path)
    registry.save(bucket_predictor, time_gap_predictor, evaluation)


def load_models(
    path: str = 'models/prediction_system'
) -> Tuple[
    OrdinalBucketPredictor,
    Optional[TimeGapPredictor],
    Optional[ProbabilityPredictor],
    Optional[ProbabilityPredictor],
    Optional[ProbabilityPredictor],
]:
    """
    Convenience function to load models.

    Args:
        path: Directory to load from

    Returns:
        (bucket_predictor, time_gap_predictor,
         weighted_prob, calibrated_prob, contender_prob) tuple
    """
    registry = ModelRegistry(path)
    return registry.load()


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    print("Testing ModelRegistry...")

    # Quick training to test save/load
    from prediction_tools.data_pipeline import CyclingDataPipeline
    from prediction_tools.bucket_predictor import BucketPredictorConfig

    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    train, val, test = pipeline.get_temporal_split(df)

    # Train a small model
    config = BucketPredictorConfig(n_estimators=50, early_stopping_rounds=10)
    bucket_pred = OrdinalBucketPredictor(config)
    bucket_pred.train(train.head(10000), val.head(2000), verbose=False)

    # Test save
    registry = ModelRegistry('/tmp/test_model_registry')
    registry.save(bucket_pred, evaluation={'test': 'metrics'})

    # Test load
    loaded_pred, _, _, _, _ = registry.load()
    print(f"Loaded model with {len(loaded_pred.feature_columns)} features")

    # Test prediction
    sample = test.head(100)
    preds = loaded_pred.predict(sample)
    print(f"Sample predictions: {preds[:10]}")

    print("\nModelRegistry test complete!")
