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


class ProbabilityEvaluator:
    """
    Evaluation metrics for probability predictions (calibration quality).

    Metrics:
    - log_loss: Multi-class negative log-likelihood
    - brier_score: Mean squared error of probability estimates
    - mean_calibration_error: Mean |predicted prob - actual frequency| per bucket
    - ece: Expected Calibration Error (binned confidence vs accuracy)
    - sharpness: Mean of max per-sample probability (higher = more confident)
    - top1_accuracy: How often the most-probable bucket is correct
    """

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10
    ) -> Dict[str, float]:
        """
        Comprehensive evaluation for probability predictions.

        Args:
            y_true: True bucket values (0-7), shape (n_samples,)
            y_proba: Predicted probabilities, shape (n_samples, 8)
            n_bins: Number of bins for ECE calculation

        Returns:
            Dictionary of evaluation metrics
        """
        y_true = np.asarray(y_true, dtype=int)
        y_proba = np.asarray(y_proba)

        n_samples = len(y_true)
        n_buckets = y_proba.shape[1]

        # One-hot encode true labels
        one_hot = np.zeros((n_samples, n_buckets))
        one_hot[np.arange(n_samples), y_true] = 1.0

        # Log loss (negative log-likelihood)
        log_probs = np.log(y_proba[np.arange(n_samples), y_true] + 1e-12)
        log_loss = float(-np.mean(log_probs))

        # Brier score (multiclass)
        brier = float(np.mean(np.sum((one_hot - y_proba) ** 2, axis=1)))

        # Top-1 accuracy
        y_pred = np.argmax(y_proba, axis=1)
        accuracy = float(np.mean(y_pred == y_true))

        # Sharpness (mean max probability)
        sharpness = float(np.mean(np.max(y_proba, axis=1)))

        # Per-bucket calibration error
        calibration_errors = []
        for bucket in range(n_buckets):
            actual_freq = np.mean(y_true == bucket)
            predicted_prob = np.mean(y_proba[:, bucket])
            cal_error = abs(predicted_prob - actual_freq)
            calibration_errors.append(cal_error)

        mean_cal_error = float(np.mean(calibration_errors))

        # Expected Calibration Error (ECE)
        max_probs = np.max(y_proba, axis=1)
        correct = (y_pred == y_true).astype(float)
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            mask = (max_probs > bin_boundaries[i]) & (max_probs <= bin_boundaries[i + 1])
            if mask.sum() > 0:
                bin_acc = correct[mask].mean()
                bin_conf = max_probs[mask].mean()
                ece += mask.sum() / n_samples * abs(bin_acc - bin_conf)

        metrics = {
            'log_loss': log_loss,
            'brier_score': brier,
            'accuracy': accuracy,
            'sharpness': sharpness,
            'mean_calibration_error': mean_cal_error,
            'ece': float(ece),
            'n_samples': n_samples,
        }

        # Per-bucket details
        for bucket in range(n_buckets):
            mask = y_true == bucket
            metrics[f'bucket_{bucket}_cal_error'] = calibration_errors[bucket]
            metrics[f'bucket_{bucket}_count'] = int(mask.sum())
            if mask.sum() > 0:
                metrics[f'bucket_{bucket}_mean_prob'] = float(np.mean(y_proba[mask, bucket]))

        return metrics


class Top4ProbabilityEvaluator:
    """
    Evaluation metrics focused on top-4 buckets (0-3: Winner, Podium, Top 5, Top 15).

    Metrics:
    - Top-4 filtered: log loss, accuracy, Brier on samples where actual bucket ∈ {0,1,2,3}
    - Cumulative calibration: predicted vs actual frequency for Win, Podium, Top 5, Top 15
    - Top-K precision: among top K riders by predicted prob, what fraction achieved threshold
    - Race-level: winner/podium capture rates per race
    """

    CUMULATIVE_CATS = {
        'win': [0],
        'podium': [0, 1],
        'top5': [0, 1, 2],
        'top15': [0, 1, 2, 3],
    }

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_proba: np.ndarray,
        competition_ids: Optional[np.ndarray] = None,
        n_bins: int = 10
    ) -> Dict[str, float]:
        """
        Top-4 focused probability evaluation.

        Args:
            y_true: True bucket values (0-7)
            y_proba: Predicted probabilities, shape (n_samples, n_buckets)
            competition_ids: Optional race IDs for race-level evaluation
            n_bins: Number of bins for calibration analysis

        Returns:
            Dictionary of top-4 focused metrics
        """
        y_true = np.asarray(y_true, dtype=int)
        y_proba = np.asarray(y_proba)
        metrics: Dict[str, float] = {}

        # --- 1. Top-4 filtered metrics ---
        top4_mask = y_true <= 3
        if top4_mask.sum() > 0:
            top4_true = y_true[top4_mask]
            top4_proba = y_proba[top4_mask]
            top4_pred = np.argmax(top4_proba, axis=1)

            # Log loss on top-4 samples
            log_probs = np.log(top4_proba[np.arange(len(top4_true)), top4_true] + 1e-12)
            metrics['top4_log_loss'] = float(-np.mean(log_probs))

            # Accuracy on top-4 samples
            metrics['top4_accuracy'] = float(np.mean(top4_pred == top4_true))

            # Brier on top-4 samples
            n_buckets = top4_proba.shape[1]
            one_hot = np.zeros((len(top4_true), n_buckets))
            one_hot[np.arange(len(top4_true)), top4_true] = 1.0
            metrics['top4_brier'] = float(np.mean(np.sum((one_hot - top4_proba) ** 2, axis=1)))

            metrics['top4_n_samples'] = int(top4_mask.sum())

        # --- 2. Cumulative calibration ---
        for cat_name, cat_buckets in Top4ProbabilityEvaluator.CUMULATIVE_CATS.items():
            cum_prob = y_proba[:, cat_buckets].sum(axis=1)
            actual = np.isin(y_true, cat_buckets).astype(float)

            # Binned calibration error
            bin_boundaries = np.linspace(0, 1, n_bins + 1)
            cal_errors = []
            for i in range(n_bins):
                mask = (cum_prob > bin_boundaries[i]) & (cum_prob <= bin_boundaries[i + 1])
                if mask.sum() >= 10:
                    pred_mean = cum_prob[mask].mean()
                    actual_mean = actual[mask].mean()
                    cal_errors.append(abs(pred_mean - actual_mean))

            if cal_errors:
                metrics[f'{cat_name}_cumulative_cal_error'] = float(np.mean(cal_errors))

            # Overall calibration
            metrics[f'{cat_name}_mean_predicted'] = float(cum_prob.mean())
            metrics[f'{cat_name}_actual_frequency'] = float(actual.mean())
            actual_freq = actual.mean()
            metrics[f'{cat_name}_cal_ratio'] = (
                float(cum_prob.mean() / actual_freq) if actual_freq > 0 else float('inf')
            )

        # --- 3. Top-K precision ---
        for cat_name, cat_buckets in Top4ProbabilityEvaluator.CUMULATIVE_CATS.items():
            cum_prob = y_proba[:, cat_buckets].sum(axis=1)
            actual = np.isin(y_true, cat_buckets)
            sorted_idx = np.argsort(-cum_prob)

            for k in [5, 10, 20, 50]:
                if len(sorted_idx) >= k:
                    top_k_idx = sorted_idx[:k]
                    precision = float(actual[top_k_idx].mean())
                    metrics[f'{cat_name}_precision_at_{k}'] = precision

        # --- 4. Race-level evaluation ---
        if competition_ids is not None:
            competition_ids = np.asarray(competition_ids)
            unique_races = np.unique(competition_ids)

            win_prob = y_proba[:, 0]
            podium_prob = y_proba[:, [0, 1]].sum(axis=1)

            winner_captured = []
            podium_captured = []

            for race_id in unique_races:
                race_mask = competition_ids == race_id
                if race_mask.sum() < 5:
                    continue

                race_true = y_true[race_mask]
                race_win_prob = win_prob[race_mask]
                race_podium_prob = podium_prob[race_mask]

                # Best predicted winner: did they actually win?
                best_win_idx = np.argmax(race_win_prob)
                winner_captured.append(1.0 if race_true[best_win_idx] == 0 else 0.0)

                # Top 3 by podium prob: how many actual podium finishers captured?
                top3_idx = np.argsort(-race_podium_prob)[:3]
                actual_podium_in_top3 = np.isin(race_true[top3_idx], [0, 1]).sum()
                actual_podium_count = np.sum(np.isin(race_true, [0, 1]))
                if actual_podium_count > 0:
                    podium_captured.append(
                        float(actual_podium_in_top3) / min(3, actual_podium_count)
                    )

            if winner_captured:
                metrics['race_winner_capture_rate'] = float(np.mean(winner_captured))
                metrics['race_winner_n_races'] = len(winner_captured)
            if podium_captured:
                metrics['race_podium_capture_rate'] = float(np.mean(podium_captured))

        return metrics


class MarketProbabilityEvaluator:
    """
    Market-aligned probability evaluation (the probability gate, 2026-06-11).

    Scores EVERY evaluated rider against each cumulative market as a binary
    outcome — unlike Top4ProbabilityEvaluator's top4_log_loss, which
    conditions on the outcome (only riders who finished top-15) and therefore
    under-penalizes overconfidence on riders who finished poorly.

    Markets are the bucket-boundary cumulative events the suite prices:
    win, podium, top5, top15. Per market: binary log loss, Brier,
    calibration ratio (sum of predicted / count of actual). Headline:
    market_avg_log_loss (equal-weight mean over the four markets).
    """

    MARKETS = {
        'win': [0],
        'podium': [0, 1],
        'top5': [0, 1, 2],
        'top15': [0, 1, 2, 3],
    }

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_proba: np.ndarray,
        competition_ids: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Args:
            y_true: True bucket values (already class-clipped is fine — only
                membership in classes 0..3 is used)
            y_proba: Predicted probabilities, shape (n_samples, n_classes)
            competition_ids: Unused; accepted for call-site symmetry

        Returns:
            {<market>_log_loss, <market>_brier, <market>_cal_ratio, ...,
             market_avg_log_loss, market_avg_brier, n_evaluated}
        """
        y_true = np.asarray(y_true, dtype=int)
        y_proba = np.asarray(y_proba)
        eps = 1e-12
        metrics: Dict[str, float] = {'n_evaluated': int(len(y_true))}

        log_losses, briers = [], []
        for market, classes in MarketProbabilityEvaluator.MARKETS.items():
            p = np.clip(y_proba[:, classes].sum(axis=1), eps, 1 - eps)
            y = np.isin(y_true, classes).astype(float)
            ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
            br = float(np.mean((p - y) ** 2))
            metrics[f'{market}_log_loss'] = ll
            metrics[f'{market}_brier'] = br
            metrics[f'{market}_cal_ratio'] = float(p.sum() / max(y.sum(), 1.0))
            log_losses.append(ll)
            briers.append(br)

        metrics['market_avg_log_loss'] = float(np.mean(log_losses))
        metrics['market_avg_brier'] = float(np.mean(briers))
        return metrics


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
    n_sample_races: int = 100,
    probability_predictor=None,
    calibrated_predictor=None,
    contender_predictor=None,
    contender_top_n: int = 25,
) -> Dict[str, Dict[str, float]]:
    """
    Comprehensive evaluation of the full prediction system.

    Args:
        bucket_predictor: Trained OrdinalBucketPredictor
        time_gap_predictor: Trained TimeGapPredictor
        race_ranker: Configured RaceRankingPredictor
        test_df: Test data with all features and targets
        n_sample_races: Number of races to sample for ranking evaluation
        probability_predictor: Optional weighted ProbabilityPredictor
        calibrated_predictor: Optional calibrated (unweighted) ProbabilityPredictor
        contender_predictor: Optional contender (filtered + classifier feature) ProbabilityPredictor
        contender_top_n: Top N riders per race for contender evaluation

    Returns:
        Dictionary with evaluation results keyed by model/metric type
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

    comp_ids = test_df['competition_id'].values if 'competition_id' in test_df.columns else None

    # Weighted probability evaluation
    if probability_predictor is not None:
        y_proba = probability_predictor.predict_proba(test_df)
        results['probability'] = ProbabilityEvaluator.evaluate(y_true_bucket, y_proba)
        results['probability_weighted'] = results['probability']
        results['probability_weighted_top4'] = Top4ProbabilityEvaluator.evaluate(
            y_true_bucket, y_proba, competition_ids=comp_ids
        )

    # Calibrated probability evaluation
    if calibrated_predictor is not None:
        y_proba_cal = calibrated_predictor.predict_proba(test_df)
        results['probability_calibrated'] = ProbabilityEvaluator.evaluate(y_true_bucket, y_proba_cal)
        results['probability_calibrated_top4'] = Top4ProbabilityEvaluator.evaluate(
            y_true_bucket, y_proba_cal, competition_ids=comp_ids
        )

    # Contender probability evaluation (filtered to top N per race)
    if contender_predictor is not None and comp_ids is not None:
        expected_buckets = bucket_predictor.predict_continuous(test_df)
        test_df_with_cls = test_df.copy()
        test_df_with_cls['classifier_expected_bucket'] = expected_buckets

        # Filter to top N per race
        test_df_with_cls['_rank'] = test_df_with_cls.groupby('competition_id')['classifier_expected_bucket'].rank()
        contender_mask = test_df_with_cls['_rank'] <= contender_top_n
        contender_df = test_df_with_cls[contender_mask]

        if len(contender_df) > 0:
            y_proba_cont = contender_predictor.predict_proba(contender_df)
            y_true_cont = contender_df['place_bucket'].values
            comp_ids_cont = contender_df['competition_id'].values

            # Handle reduced-class contender models: clip true values to match
            n_model_classes = contender_predictor.config.lgb_params.get('num_class', 8)
            if n_model_classes < 8:
                y_true_cont = np.clip(y_true_cont, 0, n_model_classes - 1)

            results['probability_contender'] = ProbabilityEvaluator.evaluate(y_true_cont, y_proba_cont)
            results['probability_contender_top4'] = Top4ProbabilityEvaluator.evaluate(
                y_true_cont, y_proba_cont, competition_ids=comp_ids_cont
            )

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

    # Probability models: print all available
    for model_label, base_key in [
        ('Weighted', 'probability_weighted'),
        ('Calibrated', 'probability_calibrated'),
        ('Contender', 'probability_contender'),
    ]:
        if base_key in results:
            print(f"\n--- {model_label} Probability ---")
            prob = results[base_key]
            print(f"  Log loss:       {prob['log_loss']:.4f}")
            print(f"  Brier score:    {prob['brier_score']:.4f}")
            print(f"  Accuracy:       {prob['accuracy']:.1%}")
            print(f"  Sharpness:      {prob['sharpness']:.3f}")
            print(f"  Mean cal error: {prob['mean_calibration_error']:.4f}")
            print(f"  ECE:            {prob['ece']:.4f}")
            print(f"  Samples:        {prob['n_samples']:,}")

        top4_key = f'{base_key}_top4'
        if top4_key in results:
            t4 = results[top4_key]
            print(f"\n  Top-4 Focus ({model_label}):")
            if 'top4_log_loss' in t4:
                print(f"    Log loss:     {t4['top4_log_loss']:.4f}")
                print(f"    Accuracy:     {t4['top4_accuracy']:.1%}")
                print(f"    Brier:        {t4['top4_brier']:.4f}")
                print(f"    Samples:      {t4['top4_n_samples']:,}")

            print(f"  Calibration ratios ({model_label}):")
            for cat in ['win', 'podium', 'top5', 'top15']:
                ratio_key = f'{cat}_cal_ratio'
                if ratio_key in t4:
                    print(f"    {cat.title():10s} {t4[ratio_key]:.2f}x "
                          f"(pred {t4[f'{cat}_mean_predicted']:.4f} vs actual {t4[f'{cat}_actual_frequency']:.4f})")

            if 'race_winner_capture_rate' in t4:
                print(f"  Race winner capture: {t4['race_winner_capture_rate']:.1%} "
                      f"({t4['race_winner_n_races']} races)")
            if 'race_podium_capture_rate' in t4:
                print(f"  Race podium capture: {t4['race_podium_capture_rate']:.1%}")

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
