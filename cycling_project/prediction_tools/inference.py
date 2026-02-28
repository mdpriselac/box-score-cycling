"""
Inference API for Cycling Race Predictions

Provides a simple, production-ready API for making predictions:
1. Predict individual rider bucket/time gap
2. Predict complete race rankings
3. Load pre-trained models

Example usage:
    api = RacePredictionAPI.load('models/prediction_system')

    # Predict a race
    results = api.predict_race(competition_id=12345)

    # Predict individual rider
    prediction = api.predict_rider(rider_id=1, competition_id=12345)
"""

from typing import Dict, List, Optional, Union, Any
import pandas as pd
import numpy as np

from .data_pipeline import CyclingDataPipeline, DataConfig
from .bucket_predictor import OrdinalBucketPredictor
from .time_gap_predictor import TimeGapPredictor
from .probability_predictor import ProbabilityPredictor, CUMULATIVE_LABELS, MAX_ODDS
from .race_ranking_predictor import RaceRankingPredictor, RaceRankingConfig
from .model_registry import ModelRegistry


class RacePredictionAPI:
    """
    Production inference API for race predictions.

    Provides simple methods for:
    - Predicting individual rider results
    - Predicting complete race rankings
    - Loading pre-trained models

    Example:
        api = RacePredictionAPI.load()
        results = api.predict_race(competition_id=12345)
        print(results.head())
    """

    def __init__(
        self,
        bucket_predictor: OrdinalBucketPredictor,
        time_gap_predictor: Optional[TimeGapPredictor] = None,
        probability_predictor: Optional[ProbabilityPredictor] = None,
        calibrated_predictor: Optional[ProbabilityPredictor] = None,
        contender_predictor: Optional[ProbabilityPredictor] = None,
        race_ranker: Optional[RaceRankingPredictor] = None,
        data_pipeline: Optional[CyclingDataPipeline] = None
    ):
        self.bucket_predictor = bucket_predictor
        self.time_gap_predictor = time_gap_predictor
        self.probability_predictor = probability_predictor
        self.calibrated_predictor = calibrated_predictor
        self.contender_predictor = contender_predictor

        self.race_ranker = race_ranker or RaceRankingPredictor(
            bucket_predictor=bucket_predictor,
            time_gap_predictor=time_gap_predictor,
            probability_predictor=probability_predictor,
            calibrated_predictor=calibrated_predictor,
            contender_predictor=contender_predictor,
        )

        self.data_pipeline = data_pipeline or CyclingDataPipeline()

    @classmethod
    def load(
        cls,
        model_dir: str = 'models/prediction_system',
        ranking_method: str = 'expected_bucket'
    ) -> 'RacePredictionAPI':
        """
        Load pre-trained models and create API.

        Args:
            model_dir: Directory containing saved models
            ranking_method: Method for race ranking

        Returns:
            Configured RacePredictionAPI instance
        """
        registry = ModelRegistry(model_dir)
        bucket_pred, time_gap_pred, race_ranker = registry.load_with_ranker(
            ranking_method=ranking_method
        )

        data_pipeline = CyclingDataPipeline()

        return cls(
            bucket_predictor=bucket_pred,
            time_gap_predictor=time_gap_pred,
            probability_predictor=race_ranker.probability_predictor,
            calibrated_predictor=race_ranker.calibrated_predictor,
            contender_predictor=race_ranker.contender_predictor,
            race_ranker=race_ranker,
            data_pipeline=data_pipeline
        )

    def predict_race(
        self,
        competition_id: int,
        return_details: bool = True
    ) -> pd.DataFrame:
        """
        Predict results for an existing race.

        Loads rider snapshots from database and generates predictions.

        Args:
            competition_id: ID of the competition to predict
            return_details: If True, include probability distributions

        Returns:
            DataFrame with predicted rankings:
            - rider_id, rider_name
            - predicted_rank (1 = winner)
            - predicted_bucket
            - expected_bucket
            - predicted_time_gap (if time gap model available)
        """
        race_df = self.data_pipeline.load_race_startlist(competition_id)

        if race_df.empty:
            raise ValueError(f"No data found for competition_id {competition_id}")

        return self.race_ranker.predict_race(race_df, return_details=return_details)

    def predict_rider(
        self,
        rider_id: int,
        competition_id: int
    ) -> Dict[str, Union[int, float, List[float]]]:
        """
        Predict single rider's result in a race.

        Args:
            rider_id: ID of the rider
            competition_id: ID of the competition

        Returns:
            Dictionary with predictions:
            - predicted_bucket: Integer bucket (0-7)
            - expected_bucket: Continuous prediction
            - bucket_probabilities: List of 8 probabilities
            - predicted_time_gap: Time gap in seconds (if model available)
            - confidence: Max bucket probability
        """
        race_df = self.data_pipeline.load_race_startlist(competition_id)
        rider_df = race_df[race_df['rider_id'] == rider_id]

        if rider_df.empty:
            raise ValueError(
                f"Rider {rider_id} not found in competition {competition_id}"
            )

        bucket_pred = self.bucket_predictor.predict(rider_df)[0]
        expected_bucket = self.bucket_predictor.predict_continuous(rider_df)[0]

        # Use best available probability model for display
        # (calibrated preferred for honest odds, contender not used here since
        # it requires full race context for filtering)
        display_predictor = self.calibrated_predictor or self.probability_predictor
        if display_predictor is not None:
            bucket_proba = display_predictor.predict_proba(rider_df)[0]
        else:
            bucket_proba = self.bucket_predictor.predict_proba(rider_df)[0]

        result = {
            'rider_id': int(rider_id),
            'competition_id': int(competition_id),
            'predicted_bucket': int(bucket_pred),
            'expected_bucket': float(expected_bucket),
            'bucket_probabilities': bucket_proba.tolist(),
            'confidence': float(np.max(bucket_proba)),
        }

        # Cumulative probabilities and odds
        cumulative = {}
        odds = {}
        for label, buckets in CUMULATIVE_LABELS.items():
            cum_prob = float(bucket_proba[buckets].sum())
            cumulative[label] = cum_prob
            odds[label] = float(min(round(1.0 / cum_prob, 2), MAX_ODDS)) if cum_prob > 0 else MAX_ODDS
        result['cumulative_probabilities'] = cumulative
        result['odds'] = odds

        if self.time_gap_predictor is not None:
            time_gap = self.time_gap_predictor.predict(rider_df)[0]
            result['predicted_time_gap'] = float(time_gap)

        return result

    def predict_startlist(
        self,
        rider_ids: List[int],
        competition_id: int
    ) -> pd.DataFrame:
        """
        Predict race results for a custom startlist.

        Uses race features from an existing competition but with
        custom rider selection.

        Args:
            rider_ids: List of rider IDs to include
            competition_id: Competition to get race features from

        Returns:
            DataFrame with predicted rankings
        """
        race_df = self.data_pipeline.load_race_startlist(competition_id)

        # Filter to specified riders
        filtered_df = race_df[race_df['rider_id'].isin(rider_ids)]

        if filtered_df.empty:
            raise ValueError("None of the specified riders found in competition")

        return self.race_ranker.predict_race(filtered_df, return_details=True)

    def evaluate_race(
        self,
        competition_id: int
    ) -> Dict[str, float]:
        """
        Evaluate prediction against actual results for a race.

        Args:
            competition_id: Competition to evaluate

        Returns:
            Dictionary with evaluation metrics
        """
        race_df = self.data_pipeline.load_race_startlist(
            competition_id, include_targets=True
        )

        if race_df.empty:
            raise ValueError(f"No data found for competition_id {competition_id}")

        return self.race_ranker.evaluate_race(race_df)

    def get_race_info(self, competition_id: int) -> Dict[str, Any]:
        """Get information about a race."""
        race_df = self.data_pipeline.load_race_startlist(competition_id)

        if race_df.empty:
            return {}

        first_row = race_df.iloc[0]
        return {
            'competition_id': int(competition_id),
            'competition_name': str(first_row.get('competition_name', '')),
            'competition_date': str(first_row.get('competition_date', '')),
            'competition_type': str(first_row.get('competition_type', '')),
            'race_category': str(first_row.get('race_category', '')),
            'field_size': len(race_df),
            'race_dominant_profile': str(first_row.get('race_dominant_profile', '')),
        }

    def list_available_races(
        self,
        start_date: str,
        end_date: str,
        min_field_size: int = 20
    ) -> pd.DataFrame:
        """
        List races available for prediction in a date range.

        Args:
            start_date: Start of date range (YYYY-MM-DD)
            end_date: End of date range (YYYY-MM-DD)
            min_field_size: Minimum field size to include

        Returns:
            DataFrame with race metadata
        """
        races = self.data_pipeline.load_races_in_range(start_date, end_date)
        return races[races['field_size'] >= min_field_size]


def quick_predict_race(
    competition_id: int,
    model_dir: str = 'models/prediction_system'
) -> pd.DataFrame:
    """
    Quick function to predict a race.

    Args:
        competition_id: Competition to predict
        model_dir: Directory with saved models

    Returns:
        DataFrame with predictions
    """
    api = RacePredictionAPI.load(model_dir)
    return api.predict_race(competition_id)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    print("Testing RacePredictionAPI...")

    # For testing, we'll train a quick model first
    from prediction_tools.data_pipeline import CyclingDataPipeline
    from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
    from prediction_tools.time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig

    # Load data
    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    train, val, test = pipeline.get_temporal_split(df)

    print(f"Train: {len(train):,} | Test: {len(test):,}")

    # Quick training
    print("\nTraining models for test...")
    bucket_config = BucketPredictorConfig(n_estimators=100, early_stopping_rounds=20)
    bucket_pred = OrdinalBucketPredictor(bucket_config)
    bucket_pred.train(train, val, verbose=False)

    time_gap_config = TimeGapPredictorConfig(n_estimators=100, early_stopping_rounds=20)
    time_gap_pred = TimeGapPredictor(time_gap_config)
    time_gap_pred.train(train, val, verbose=False)

    # Create API (without loading from disk)
    api = RacePredictionAPI(
        bucket_predictor=bucket_pred,
        time_gap_predictor=time_gap_pred,
        data_pipeline=pipeline
    )

    # Test race prediction
    print("\n--- Test Race Prediction ---")
    test_comp_id = test['competition_id'].iloc[0]
    race_info = api.get_race_info(test_comp_id)
    print(f"Race: {race_info['competition_name']}")
    print(f"Type: {race_info['competition_type']} | Category: {race_info['race_category']}")
    print(f"Field size: {race_info['field_size']}")

    predictions = api.predict_race(test_comp_id, return_details=False)
    print(f"\nTop 10 predictions:")
    print(predictions.head(10).to_string(index=False))

    # Test individual prediction
    print("\n--- Test Individual Prediction ---")
    test_rider_id = predictions.iloc[0]['rider_id']
    rider_pred = api.predict_rider(int(test_rider_id), test_comp_id)
    print(f"Rider {test_rider_id}:")
    print(f"  Predicted bucket: {rider_pred['predicted_bucket']}")
    print(f"  Expected bucket: {rider_pred['expected_bucket']:.2f}")
    print(f"  Confidence: {rider_pred['confidence']:.1%}")
    if 'predicted_time_gap' in rider_pred:
        print(f"  Time gap: {rider_pred['predicted_time_gap']:.0f} seconds")

    # Test evaluation
    print("\n--- Test Evaluation ---")
    metrics = api.evaluate_race(test_comp_id)
    print(f"Kendall's Tau: {metrics['kendall_tau']:.3f}")
    print(f"Winner correct: {metrics['winner_correct']}")
    print(f"Podium accuracy: {metrics['podium_accuracy']:.1%}")

    print("\nAPI test complete!")
