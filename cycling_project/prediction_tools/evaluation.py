"""
Evaluation Module for Cycling Race Predictions

Provides comprehensive evaluation metrics for:
1. Bucket predictions (ordinal classification)
2. Time gap predictions (regression)
3. Race ranking predictions

All evaluators follow a consistent interface with evaluate() methods
returning dictionaries of metrics.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class BucketEvaluator:
    """
    Evaluation metrics for bucket prediction (ordinal classification).

    Metrics:
    - mae: Mean Absolute Error
    - accuracy: Exact match rate
    - within_1: Predictions within 1 bucket
    - within_2: Predictions within 2 buckets
    - quadratic_kappa: Cohen's Kappa with quadratic weights (ordinal)
    """

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        sample_weights: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Comprehensive evaluation for bucket predictions.

        Args:
            y_true: True bucket values (0-7)
            y_pred: Predicted bucket values
            sample_weights: Optional weights for samples

        Returns:
            Dictionary of evaluation metrics
        """
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)

        diff = np.abs(y_true - y_pred)

        # Basic metrics
        if sample_weights is not None:
            mae = np.average(diff, weights=sample_weights)
            accuracy = np.average(y_true == y_pred, weights=sample_weights)
            within_1 = np.average(diff <= 1, weights=sample_weights)
            within_2 = np.average(diff <= 2, weights=sample_weights)
        else:
            mae = np.mean(diff)
            accuracy = np.mean(y_true == y_pred)
            within_1 = np.mean(diff <= 1)
            within_2 = np.mean(diff <= 2)

        # Quadratic weighted kappa
        kappa = BucketEvaluator._quadratic_kappa(y_true, y_pred)

        metrics = {
            'mae': float(mae),
            'accuracy': float(accuracy),
            'within_1': float(within_1),
            'within_2': float(within_2),
            'quadratic_kappa': float(kappa),
            'n_samples': len(y_true),
        }

        # Per-bucket metrics
        for bucket in range(8):
            mask = y_true == bucket
            if mask.sum() > 0:
                bucket_acc = np.mean(y_pred[mask] == bucket)
                bucket_mae = np.mean(np.abs(y_pred[mask] - bucket))
                metrics[f'bucket_{bucket}_accuracy'] = float(bucket_acc)
                metrics[f'bucket_{bucket}_mae'] = float(bucket_mae)
                metrics[f'bucket_{bucket}_count'] = int(mask.sum())

        return metrics

    @staticmethod
    def _quadratic_kappa(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """Compute quadratic weighted Cohen's Kappa."""
        n_classes = max(y_true.max(), y_pred.max()) + 1
        n_classes = max(n_classes, 8)  # At least 8 buckets

        # Create weight matrix
        weights = np.zeros((n_classes, n_classes))
        for i in range(n_classes):
            for j in range(n_classes):
                weights[i, j] = (i - j) ** 2 / (n_classes - 1) ** 2

        # Create confusion matrix
        conf_matrix = np.zeros((n_classes, n_classes))
        for t, p in zip(y_true, y_pred):
            conf_matrix[int(t), int(p)] += 1

        # Expected matrix
        hist_true = np.bincount(y_true.astype(int), minlength=n_classes)
        hist_pred = np.bincount(y_pred.astype(int), minlength=n_classes)
        expected = np.outer(hist_true, hist_pred) / len(y_true)

        # Kappa
        observed = np.sum(weights * conf_matrix) / len(y_true)
        expected_score = np.sum(weights * expected) / len(y_true)

        if expected_score == 0:
            return 1.0

        return 1 - observed / expected_score

    @staticmethod
    def confusion_matrix(
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> pd.DataFrame:
        """Generate confusion matrix as DataFrame."""
        n_classes = 8
        cm = np.zeros((n_classes, n_classes), dtype=int)

        for t, p in zip(y_true, y_pred):
            if 0 <= t < n_classes and 0 <= p < n_classes:
                cm[int(t), int(p)] += 1

        return pd.DataFrame(
            cm,
            index=[f'actual_{i}' for i in range(n_classes)],
            columns=[f'pred_{i}' for i in range(n_classes)]
        )


class TimeGapEvaluator:
    """
    Evaluation metrics for time gap prediction (regression).

    Metrics:
    - mae: Mean Absolute Error (seconds)
    - rmse: Root Mean Squared Error
    - mape: Mean Absolute Percentage Error
    - median_ae: Median Absolute Error
    - r2: Coefficient of determination
    """

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """
        Comprehensive evaluation for time gap predictions.

        Args:
            y_true: True time gaps (seconds)
            y_pred: Predicted time gaps

        Returns:
            Dictionary of evaluation metrics
        """
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)

        errors = y_true - y_pred
        abs_errors = np.abs(errors)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        median_ae = float(np.median(abs_errors))

        # R-squared
        ss_res = np.sum(errors ** 2)
        ss_tot = np.sum((y_true - y_true.mean()) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        metrics = {
            'mae': mae,
            'rmse': rmse,
            'median_ae': median_ae,
            'r2': float(r2),
            'n_samples': len(y_true),
        }

        # MAPE (exclude zeros)
        nonzero_mask = y_true > 0
        if nonzero_mask.sum() > 0:
            mape = np.mean(abs_errors[nonzero_mask] / y_true[nonzero_mask])
            metrics['mape'] = float(mape)

        return metrics

    @staticmethod
    def evaluate_by_bucket(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        buckets: np.ndarray
    ) -> pd.DataFrame:
        """
        Evaluate time gap prediction accuracy per bucket.

        Args:
            y_true: True time gaps
            y_pred: Predicted time gaps
            buckets: Bucket values for each sample

        Returns:
            DataFrame with per-bucket metrics
        """
        results = []
        for bucket in range(7):  # Exclude bucket 7 (DNF)
            mask = buckets == bucket
            if mask.sum() > 0:
                bucket_metrics = TimeGapEvaluator.evaluate(
                    y_true[mask], y_pred[mask]
                )
                bucket_metrics['bucket'] = bucket
                results.append(bucket_metrics)

        return pd.DataFrame(results)


class RankingEvaluator:
    """
    Evaluation metrics for race ranking prediction.

    Metrics:
    - kendall_tau: Rank correlation (-1 to 1)
    - spearman_rho: Rank correlation
    - top_k_precision: Precision at various K values
    - mrr_winner: Mean Reciprocal Rank of winner
    """

    @staticmethod
    def evaluate(
        predicted_ranks: np.ndarray,
        actual_ranks: np.ndarray,
        field_size: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Comprehensive evaluation for ranking predictions.

        Args:
            predicted_ranks: Predicted ranking (1 = winner)
            actual_ranks: Actual ranking or bucket values
            field_size: Total field size (for normalization)

        Returns:
            Dictionary of evaluation metrics
        """
        from scipy.stats import kendalltau, spearmanr

        predicted_ranks = np.asarray(predicted_ranks)
        actual_ranks = np.asarray(actual_ranks)

        if field_size is None:
            field_size = len(predicted_ranks)

        # Rank correlations
        tau, _ = kendalltau(predicted_ranks, actual_ranks)
        rho, _ = spearmanr(predicted_ranks, actual_ranks)

        # Get indices for top-K comparison
        actual_sorted_idx = np.argsort(actual_ranks)
        pred_sorted_idx = np.argsort(predicted_ranks)

        def top_k_overlap(k):
            actual_top = set(actual_sorted_idx[:k])
            pred_top = set(pred_sorted_idx[:k])
            return len(actual_top & pred_top) / k

        # Mean Reciprocal Rank of actual winner
        actual_winner_idx = actual_sorted_idx[0]
        winner_pred_rank = np.where(pred_sorted_idx == actual_winner_idx)[0][0] + 1
        mrr = 1.0 / winner_pred_rank

        metrics = {
            'kendall_tau': float(tau),
            'spearman_rho': float(rho),
            'top1_accuracy': float(top_k_overlap(1)),
            'top3_precision': float(top_k_overlap(3)),
            'top5_precision': float(top_k_overlap(5)),
            'mrr_winner': float(mrr),
            'field_size': field_size,
        }

        if field_size >= 10:
            metrics['top10_precision'] = float(top_k_overlap(10))

        return metrics

    @staticmethod
    def evaluate_races(
        race_results: List[Tuple[np.ndarray, np.ndarray]]
    ) -> Dict[str, float]:
        """
        Aggregate evaluation across multiple races.

        Args:
            race_results: List of (predicted_ranks, actual_ranks) tuples

        Returns:
            Aggregated metrics
        """
        all_metrics = []
        for pred, actual in race_results:
            if len(pred) >= 10:  # Minimum field size
                metrics = RankingEvaluator.evaluate(pred, actual)
                all_metrics.append(metrics)

        if not all_metrics:
            return {}

        # Aggregate
        agg = {}
        for key in all_metrics[0].keys():
            if key != 'field_size':
                values = [m[key] for m in all_metrics if key in m]
                agg[f'mean_{key}'] = float(np.mean(values))
                agg[f'std_{key}'] = float(np.std(values))

        agg['n_races'] = len(all_metrics)

        return agg


def evaluate_full_system(
    bucket_predictor,
    time_gap_predictor,
    race_ranker,
    test_df: pd.DataFrame,
    n_sample_races: int = 100
) -> Dict[str, Dict[str, float]]:
    """
    Comprehensive evaluation of the full prediction system.

    Args:
        bucket_predictor: Trained OrdinalBucketPredictor
        time_gap_predictor: Trained TimeGapPredictor
        race_ranker: Configured RaceRankingPredictor
        test_df: Test data with all features and targets
        n_sample_races: Number of races to sample for ranking evaluation

    Returns:
        Dictionary with 'bucket', 'time_gap', and 'ranking' metrics
    """
    results = {}

    # Bucket evaluation
    y_pred_bucket = bucket_predictor.predict(test_df)
    y_true_bucket = test_df['place_bucket'].values
    results['bucket'] = BucketEvaluator.evaluate(y_true_bucket, y_pred_bucket)

    # Time gap evaluation (filtered)
    test_time_gap = time_gap_predictor.filter_for_training(test_df)
    if len(test_time_gap) > 0:
        y_pred_time = time_gap_predictor.predict(test_time_gap)
        y_true_time = test_time_gap['time_gap'].values
        results['time_gap'] = TimeGapEvaluator.evaluate(y_true_time, y_pred_time)

        # Time gap by bucket
        results['time_gap_by_bucket'] = TimeGapEvaluator.evaluate_by_bucket(
            y_true_time, y_pred_time, test_time_gap['place_bucket'].values
        ).to_dict('records')

    # Race ranking evaluation
    if 'competition_id' in test_df.columns:
        race_ids = test_df['competition_id'].unique()
        if len(race_ids) > n_sample_races:
            np.random.seed(42)
            race_ids = np.random.choice(race_ids, n_sample_races, replace=False)

        eval_results = race_ranker.evaluate_races(
            test_df, competition_ids=race_ids
        )

        if len(eval_results) > 0:
            results['ranking'] = {
                'mean_kendall_tau': float(eval_results['kendall_tau'].mean()),
                'mean_winner_correct': float(eval_results['winner_correct'].mean()),
                'mean_podium_accuracy': float(eval_results['podium_accuracy'].mean()),
                'mean_top5_accuracy': float(eval_results['top5_accuracy'].mean()),
                'mean_top10_accuracy': float(eval_results['top10_accuracy'].mean()),
                'n_races': len(eval_results),
            }

    return results


def print_evaluation_report(results: Dict[str, Dict[str, float]]):
    """Print a formatted evaluation report."""
    print("\n" + "=" * 60)
    print("EVALUATION REPORT")
    print("=" * 60)

    if 'bucket' in results:
        print("\n--- Bucket Prediction ---")
        bucket = results['bucket']
        print(f"  MAE:            {bucket['mae']:.3f}")
        print(f"  Accuracy:       {bucket['accuracy']:.1%}")
        print(f"  Within-1:       {bucket['within_1']:.1%}")
        print(f"  Within-2:       {bucket['within_2']:.1%}")
        print(f"  Quadratic κ:    {bucket['quadratic_kappa']:.3f}")
        print(f"  Samples:        {bucket['n_samples']:,}")

    if 'time_gap' in results:
        print("\n--- Time Gap Prediction ---")
        tg = results['time_gap']
        print(f"  MAE:            {tg['mae']:.1f} seconds")
        print(f"  RMSE:           {tg['rmse']:.1f} seconds")
        print(f"  Median AE:      {tg['median_ae']:.1f} seconds")
        print(f"  R²:             {tg['r2']:.3f}")
        print(f"  Samples:        {tg['n_samples']:,}")

    if 'ranking' in results:
        print("\n--- Race Ranking ---")
        rank = results['ranking']
        print(f"  Kendall's τ:    {rank['mean_kendall_tau']:.3f}")
        print(f"  Winner correct: {rank['mean_winner_correct']:.1%}")
        print(f"  Podium acc:     {rank['mean_podium_accuracy']:.1%}")
        print(f"  Top-5 acc:      {rank['mean_top5_accuracy']:.1%}")
        print(f"  Top-10 acc:     {rank['mean_top10_accuracy']:.1%}")
        print(f"  Races:          {rank['n_races']}")

    print("\n" + "=" * 60)


if __name__ == '__main__':
    # Test evaluators with synthetic data
    print("Testing evaluation metrics...")

    # Bucket evaluation
    y_true = np.array([0, 1, 2, 3, 4, 5, 6, 3, 4, 5])
    y_pred = np.array([1, 1, 2, 4, 4, 4, 6, 3, 5, 5])

    bucket_metrics = BucketEvaluator.evaluate(y_true, y_pred)
    print("\nBucket metrics:")
    for k, v in bucket_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    # Time gap evaluation
    y_true_time = np.array([0, 30, 60, 120, 300, 600])
    y_pred_time = np.array([10, 45, 50, 100, 350, 580])

    time_metrics = TimeGapEvaluator.evaluate(y_true_time, y_pred_time)
    print("\nTime gap metrics:")
    for k, v in time_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    # Ranking evaluation
    pred_ranks = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    actual_ranks = np.array([2, 1, 4, 3, 5, 7, 6, 9, 8, 10])

    rank_metrics = RankingEvaluator.evaluate(pred_ranks, actual_ranks)
    print("\nRanking metrics:")
    for k, v in rank_metrics.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")
