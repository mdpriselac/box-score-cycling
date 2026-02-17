"""
Race Ranking Predictor for Cycling Race Predictions

Predicts complete race rankings from a start list using individual models.

Ranking methods:
1. expected_bucket: Sort by predicted bucket (lower = better)
2. time_gap: Sort by predicted time gap (lower = better)
3. ensemble: Weighted combination of both

The predicted ranking can then be converted to buckets using place_bucketer.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Literal
import numpy as np
import pandas as pd

from .bucket_predictor import OrdinalBucketPredictor
from .time_gap_predictor import TimeGapPredictor

try:
    from ..engineering_tools.place_handling import place_bucketer
except (ImportError, ValueError):
    # Fallback implementation
    def place_bucketer(place: int) -> int:
        """Convert place to bucket."""
        if place is None:
            return None
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


@dataclass
class RaceRankingConfig:
    """Configuration for race ranking prediction."""
    # Method for ranking riders
    ranking_method: Literal['expected_bucket', 'time_gap', 'ensemble'] = 'expected_bucket'

    # Weights for ensemble method (bucket_weight, time_gap_weight)
    ensemble_weights: tuple = (0.7, 0.3)


class RaceRankingPredictor:
    """
    Predicts complete race rankings from a start list.

    Uses individual bucket and/or time gap predictors to score riders,
    then sorts to produce a ranking.

    Example usage:
        ranker = RaceRankingPredictor(bucket_predictor, time_gap_predictor)
        results = ranker.predict_race(race_df)
    """

    def __init__(
        self,
        bucket_predictor: OrdinalBucketPredictor,
        time_gap_predictor: Optional[TimeGapPredictor] = None,
        config: Optional[RaceRankingConfig] = None
    ):
        self.bucket_predictor = bucket_predictor
        self.time_gap_predictor = time_gap_predictor
        self.config = config or RaceRankingConfig()

        # Validate config
        if self.config.ranking_method in ('time_gap', 'ensemble'):
            if self.time_gap_predictor is None:
                raise ValueError(
                    f"TimeGapPredictor required for ranking_method='{self.config.ranking_method}'"
                )

    def predict_race(
        self,
        race_df: pd.DataFrame,
        return_details: bool = False
    ) -> pd.DataFrame:
        """
        Predict complete race ranking.

        Args:
            race_df: DataFrame with all riders in the race
            return_details: If True, include predicted bucket, time_gap, probabilities

        Returns:
            DataFrame sorted by predicted finishing order with columns:
            - rider_id, rider_name (if available)
            - predicted_rank (1 = winner)
            - predicted_bucket (bucket from ranking position)
            - expected_bucket (from individual model)
            - ranking_score (the score used for sorting)
            - Additional columns if return_details=True
        """
        # Ensure we have required columns
        if 'rider_id' not in race_df.columns:
            raise ValueError("race_df must contain 'rider_id' column")

        # Start with basic info
        results = race_df[['rider_id']].copy()
        if 'rider_name' in race_df.columns:
            results['rider_name'] = race_df['rider_name']
        if 'competition_id' in race_df.columns:
            results['competition_id'] = race_df['competition_id']

        # Get expected bucket predictions (continuous) - used for ranking
        expected_buckets = self.bucket_predictor.predict_continuous(race_df)
        results['expected_bucket'] = expected_buckets

        # Get discrete bucket predictions from model (tends to compress to middle)
        bucket_preds = self.bucket_predictor.predict(race_df)
        results['model_predicted_bucket'] = bucket_preds

        # Determine ranking score based on method
        if self.config.ranking_method == 'expected_bucket':
            results['ranking_score'] = expected_buckets

        elif self.config.ranking_method == 'time_gap':
            time_gaps = self.time_gap_predictor.predict(race_df)
            results['predicted_time_gap'] = time_gaps
            results['ranking_score'] = time_gaps

        elif self.config.ranking_method == 'ensemble':
            time_gaps = self.time_gap_predictor.predict(race_df)
            results['predicted_time_gap'] = time_gaps

            # Normalize both to 0-1 scale for combination
            bucket_min, bucket_max = expected_buckets.min(), expected_buckets.max()
            gap_min, gap_max = time_gaps.min(), time_gaps.max()

            bucket_norm = (expected_buckets - bucket_min) / (bucket_max - bucket_min + 1e-10)
            gap_norm = (time_gaps - gap_min) / (gap_max - gap_min + 1e-10)

            w_bucket, w_gap = self.config.ensemble_weights
            results['ranking_score'] = w_bucket * bucket_norm + w_gap * gap_norm

        # Sort by ranking score (lower is better)
        results = results.sort_values('ranking_score').reset_index(drop=True)

        # Assign predicted rank (1-indexed)
        results['predicted_rank'] = range(1, len(results) + 1)

        # Convert predicted rank to bucket (ranking-derived bucket)
        # This uses the race position to assign buckets, avoiding the compression issue
        results['ranking_derived_bucket'] = results['predicted_rank'].apply(place_bucketer)

        # Add probability distribution if requested
        if return_details:
            proba = self.bucket_predictor.predict_proba(race_df)
            # Re-sort probabilities to match the ranking order
            proba_sorted = proba[results.index]
            for i in range(8):
                results[f'prob_bucket_{i}'] = proba_sorted[:, i]

        # Reorder columns for clarity
        cols = ['rider_id']
        if 'rider_name' in results.columns:
            cols.append('rider_name')
        cols.extend(['predicted_rank', 'ranking_derived_bucket', 'model_predicted_bucket', 'expected_bucket'])
        if 'predicted_time_gap' in results.columns:
            cols.append('predicted_time_gap')
        cols.append('ranking_score')
        if 'competition_id' in results.columns:
            cols.append('competition_id')
        if return_details:
            cols.extend([f'prob_bucket_{i}' for i in range(8)])

        return results[[c for c in cols if c in results.columns]]

    def evaluate_race(
        self,
        race_df: pd.DataFrame,
        actual_results: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        Evaluate race prediction against actual results.

        Args:
            race_df: Race data (with place_bucket if actual_results not provided)
            actual_results: Optional separate actual results DataFrame

        Returns:
            Dictionary of evaluation metrics:
            - kendall_tau: Rank correlation
            - winner_correct: 1 if winner predicted correctly
            - podium_overlap: Number of correct podium finishers (0-3)
            - top5_overlap: Number of correct top 5 finishers
            - top10_overlap: Number of correct top 10 finishers
        """
        predictions = self.predict_race(race_df, return_details=False)

        # Get actual results
        if actual_results is not None:
            actual = actual_results[['rider_id', 'place_bucket']].copy()
        elif 'place_bucket' in race_df.columns:
            actual = race_df[['rider_id', 'place_bucket']].copy()
        else:
            raise ValueError("Actual results required for evaluation")

        # Merge predictions with actual
        merged = predictions.merge(actual, on='rider_id', suffixes=('', '_actual'))

        # Sort by actual place bucket for comparison
        actual_sorted = merged.sort_values('place_bucket').reset_index(drop=True)
        actual_sorted['actual_rank'] = range(1, len(actual_sorted) + 1)

        # Get predicted ranking
        pred_sorted = merged.sort_values('predicted_rank').reset_index(drop=True)

        # Compute Kendall's Tau
        from scipy.stats import kendalltau
        tau, _ = kendalltau(
            merged['predicted_rank'].values,
            merged['place_bucket'].values
        )

        # Top-K accuracy
        actual_top1 = set(actual_sorted.iloc[:1]['rider_id'])
        actual_top3 = set(actual_sorted.iloc[:3]['rider_id'])
        actual_top5 = set(actual_sorted.iloc[:5]['rider_id'])
        actual_top10 = set(actual_sorted.iloc[:min(10, len(actual_sorted))]['rider_id'])

        pred_top1 = set(pred_sorted.iloc[:1]['rider_id'])
        pred_top3 = set(pred_sorted.iloc[:3]['rider_id'])
        pred_top5 = set(pred_sorted.iloc[:5]['rider_id'])
        pred_top10 = set(pred_sorted.iloc[:min(10, len(pred_sorted))]['rider_id'])

        metrics = {
            'kendall_tau': tau,
            'winner_correct': int(pred_top1 == actual_top1),
            'podium_overlap': len(pred_top3 & actual_top3),
            'top5_overlap': len(pred_top5 & actual_top5),
            'top10_overlap': len(pred_top10 & actual_top10),
            'podium_accuracy': len(pred_top3 & actual_top3) / 3,
            'top5_accuracy': len(pred_top5 & actual_top5) / 5,
            'top10_accuracy': len(pred_top10 & actual_top10) / min(10, len(actual_sorted)),
            'field_size': len(merged),
        }

        return metrics

    def evaluate_races(
        self,
        races_df: pd.DataFrame,
        competition_ids: Optional[List[int]] = None,
        min_field_size: int = 20
    ) -> pd.DataFrame:
        """
        Evaluate predictions across multiple races.

        Args:
            races_df: DataFrame containing multiple races (with competition_id)
            competition_ids: Specific competitions to evaluate (None = all)
            min_field_size: Minimum field size to include in evaluation

        Returns:
            DataFrame with per-race metrics
        """
        if 'competition_id' not in races_df.columns:
            raise ValueError("races_df must contain 'competition_id' column")

        if competition_ids is None:
            competition_ids = races_df['competition_id'].unique()

        results = []
        for comp_id in competition_ids:
            race = races_df[races_df['competition_id'] == comp_id]

            if len(race) < min_field_size:
                continue

            try:
                metrics = self.evaluate_race(race)
                metrics['competition_id'] = comp_id
                results.append(metrics)
            except Exception as e:
                # Skip problematic races
                continue

        if not results:
            return pd.DataFrame()

        return pd.DataFrame(results)


def create_race_ranker(
    bucket_predictor: OrdinalBucketPredictor,
    time_gap_predictor: Optional[TimeGapPredictor] = None,
    ranking_method: str = 'expected_bucket'
) -> RaceRankingPredictor:
    """
    Convenience function to create a race ranking predictor.

    Args:
        bucket_predictor: Trained bucket prediction model
        time_gap_predictor: Optional trained time gap model
        ranking_method: Method for ranking ('expected_bucket', 'time_gap', 'ensemble')

    Returns:
        Configured RaceRankingPredictor
    """
    config = RaceRankingConfig(ranking_method=ranking_method)
    return RaceRankingPredictor(bucket_predictor, time_gap_predictor, config)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '..')

    from prediction_tools.data_pipeline import CyclingDataPipeline
    from prediction_tools.bucket_predictor import OrdinalBucketPredictor, BucketPredictorConfig
    from prediction_tools.time_gap_predictor import TimeGapPredictor, TimeGapPredictorConfig

    print("Testing RaceRankingPredictor...")

    # Load and split data
    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    train, val, test = pipeline.get_temporal_split(df)

    print(f"Train: {len(train):,} | Val: {len(val):,} | Test: {len(test):,}")

    # Train bucket predictor (quick)
    print("\nTraining bucket predictor...")
    bucket_config = BucketPredictorConfig(n_estimators=100, early_stopping_rounds=20)
    bucket_pred = OrdinalBucketPredictor(bucket_config)
    bucket_pred.train(train, val, verbose=False)

    # Create race ranker
    ranker = RaceRankingPredictor(bucket_pred)

    # Evaluate on sample races from test set
    print("\nEvaluating on test set races...")
    test_comp_ids = test['competition_id'].unique()[:50]  # First 50 races
    eval_results = ranker.evaluate_races(test, competition_ids=test_comp_ids)

    print(f"\nEvaluated {len(eval_results)} races")
    print(f"\nAggregate metrics:")
    print(f"  Mean Kendall's Tau: {eval_results['kendall_tau'].mean():.3f}")
    print(f"  Winner correct rate: {eval_results['winner_correct'].mean():.3f}")
    print(f"  Mean podium accuracy: {eval_results['podium_accuracy'].mean():.3f}")
    print(f"  Mean top-5 accuracy: {eval_results['top5_accuracy'].mean():.3f}")
    print(f"  Mean top-10 accuracy: {eval_results['top10_accuracy'].mean():.3f}")

    # Show single race prediction
    print("\n--- Example Race Prediction ---")
    sample_race = test[test['competition_id'] == test_comp_ids[0]]
    prediction = ranker.predict_race(sample_race, return_details=False)
    print(prediction.head(10).to_string(index=False))
