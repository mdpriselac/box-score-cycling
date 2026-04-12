"""
Experiment Runner for Cycling Race Predictions

Provides a standardized framework for comparing model approaches
using expanding-window temporal cross-validation.

Usage:
    from cycling_project.prediction_tools.experiment_runner import (
        ExperimentRunner, ExperimentConfig
    )

    config = ExperimentConfig(name="baseline")
    runner = ExperimentRunner(config)
    results = runner.run()

    # Compare two experiments:
    ExperimentRunner.compare(baseline_results, new_results)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

import numpy as np

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)


# Default 3-fold expanding window (full-year val/test to avoid seasonal bias)
DEFAULT_FOLDS = [
    {'train_end': '2021-12-31', 'val_end': '2022-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'val_end': '2023-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'val_end': '2024-12-31', 'label': '2025'},
]

# Primary metrics we track for comparison (metric_group, metric_key)
PRIMARY_METRICS = [
    ('probability_contender_top4', 'race_winner_capture_rate'),
    ('probability_contender_top4', 'top4_log_loss'),
    ('probability_contender_top4', 'race_podium_capture_rate'),
]

# Secondary metrics for diagnostics
SECONDARY_METRICS = [
    ('probability_contender_top4', 'win_cal_ratio'),
    ('probability_contender_top4', 'podium_cal_ratio'),
    ('probability_contender_top4', 'top4_brier'),
    ('bucket', 'mae'),
    ('ranking', 'mean_winner_correct'),
    ('ranking', 'mean_kendall_tau'),
]


@dataclass
class ExperimentConfig:
    """Configuration for a single experiment."""
    name: str
    description: str = ""

    # Fold configuration
    folds: List[Dict[str, str]] = field(default_factory=lambda: list(DEFAULT_FOLDS))
    start_date: str = '2018-01-01'

    # Model config (forwarded to TrainingConfig)
    n_estimators: int = 500
    early_stopping: int = 50
    contender_top_n: int = 25
    ranking_method: str = 'expected_bucket'

    # What to train
    train_time_gap: bool = True
    train_probability: bool = True
    train_calibrated: bool = True
    train_contender: bool = True

    # Contender model tuning
    contender_learning_rate: Optional[float] = None
    contender_use_oof: bool = False
    contender_n_classes: Optional[int] = None
    contender_use_soft_weights: bool = False
    contender_soft_weight_power: float = 2.0

    # Stage 0: expose raw gradient / null-marker / race-shape columns.
    include_gradient_features: bool = False

    # Stage 1: expose one-day race cluster memberships. Only meaningful in
    # additive mode alongside include_gradient_features=True. cluster_variant
    # selects which GMM fit in race_cluster_v1_scores to read from.
    include_race_clusters: bool = False
    cluster_variant: str = 'joint'  # 'race_only' or 'joint'

    # Output
    results_dir: str = 'experiments/'
    verbose: bool = True
    n_sample_races: int = 200


@dataclass
class ExperimentResults:
    """Results from a completed experiment."""
    name: str
    description: str
    fold_results: List[Dict[str, Any]]
    aggregated: Dict[str, Dict[str, Dict[str, float]]]
    primary_metrics: Dict[str, Dict[str, float]]
    timestamp: str
    config_summary: Dict[str, Any]

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'description': self.description,
            'timestamp': self.timestamp,
            'config_summary': self.config_summary,
            'primary_metrics': self.primary_metrics,
            'aggregated': self.aggregated,
            'fold_results': self.fold_results,
        }


class ExperimentRunner:
    """
    Runs expanding-window temporal CV experiments for model comparison.

    Trains the full model system (bucket + time gap + probability models)
    on each fold, evaluates on held-out test data, and aggregates metrics.
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.fold_results: List[Dict[str, Any]] = []

    def run(self) -> ExperimentResults:
        """Run all folds and return aggregated results."""
        print(f"\n{'=' * 70}")
        print(f"EXPERIMENT: {self.config.name}")
        if self.config.description:
            print(f"  {self.config.description}")
        print(f"  Folds: {len(self.config.folds)}")
        print(f"  n_estimators: {self.config.n_estimators}")
        print(f"  contender_top_n: {self.config.contender_top_n}")
        print(f"{'=' * 70}")

        self.fold_results = []

        for i, fold_config in enumerate(self.config.folds):
            label = fold_config.get('label', f'fold_{i}')
            print(f"\n{'─' * 50}")
            print(f"FOLD {i + 1}/{len(self.config.folds)}: test={label}")
            print(f"  Train: {self.config.start_date} to {fold_config['train_end']}")
            print(f"  Val:   {fold_config['train_end']} to {fold_config['val_end']}")
            print(f"  Test:  after {fold_config['val_end']}")
            print(f"{'─' * 50}")

            fold_result = self._run_fold(i, fold_config)
            self.fold_results.append(fold_result)

            # Print fold primary metrics
            self._print_fold_primary(fold_result, label)

        results = self._build_results()
        self._save_results(results)
        self._print_summary(results)
        self._print_feature_importance(top_n=20)

        return results

    def _run_fold(self, fold_idx: int, fold_config: Dict[str, str]) -> Dict[str, Any]:
        """Train and evaluate on a single fold."""
        from .training import ModelTrainer, TrainingConfig

        training_config = TrainingConfig(
            start_date=self.config.start_date,
            train_end_date=fold_config['train_end'],
            val_end_date=fold_config['val_end'],
            bucket_n_estimators=self.config.n_estimators,
            bucket_early_stopping=self.config.early_stopping,
            time_gap_n_estimators=self.config.n_estimators,
            time_gap_early_stopping=self.config.early_stopping,
            probability_n_estimators=self.config.n_estimators,
            probability_early_stopping=self.config.early_stopping,
            train_time_gap=self.config.train_time_gap,
            train_probability=self.config.train_probability,
            train_calibrated_probability=self.config.train_calibrated,
            train_contender_probability=self.config.train_contender,
            contender_top_n=self.config.contender_top_n,
            ranking_method=self.config.ranking_method,
            # Contender tuning params
            contender_learning_rate=self.config.contender_learning_rate,
            contender_use_oof=self.config.contender_use_oof,
            contender_n_classes=self.config.contender_n_classes,
            contender_use_soft_weights=self.config.contender_use_soft_weights,
            contender_soft_weight_power=self.config.contender_soft_weight_power,
            include_gradient_features=self.config.include_gradient_features,
            include_race_clusters=self.config.include_race_clusters,
            cluster_variant=self.config.cluster_variant,
            fold_label=fold_config['label'],
            model_save_dir=None,  # Don't save models during experiments
            verbose=self.config.verbose,
        )

        trainer = ModelTrainer(training_config)
        system_results = trainer.train_full_system()

        # Capture feature importance from bucket predictor
        importance_dict = {}
        bucket_model = system_results.get('bucket_predictor')
        if bucket_model is not None:
            try:
                imp_df = bucket_model.get_feature_importance(importance_type='gain')
                importance_dict = dict(zip(imp_df['feature'], imp_df['importance']))
            except Exception:
                pass

        fold_result = {
            'fold_idx': fold_idx,
            'fold_config': fold_config,
            'evaluation': system_results['evaluation'],
            'training_info': system_results['training_info'],
            'feature_importance': importance_dict,
        }

        return fold_result

    def _build_results(self) -> ExperimentResults:
        """Aggregate fold results into ExperimentResults."""
        aggregated = self._aggregate_metrics()
        primary = self._extract_primary_metrics(aggregated)

        return ExperimentResults(
            name=self.config.name,
            description=self.config.description,
            fold_results=self.fold_results,
            aggregated=aggregated,
            primary_metrics=primary,
            timestamp=datetime.now().isoformat(),
            config_summary={
                'n_estimators': self.config.n_estimators,
                'early_stopping': self.config.early_stopping,
                'contender_top_n': self.config.contender_top_n,
                'ranking_method': self.config.ranking_method,
                'n_folds': len(self.config.folds),
                'start_date': self.config.start_date,
                'train_time_gap': self.config.train_time_gap,
                'train_probability': self.config.train_probability,
                'train_calibrated': self.config.train_calibrated,
                'train_contender': self.config.train_contender,
            },
        )

    def _aggregate_metrics(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Compute mean +/- std for all metrics across folds."""
        # Collect all metric groups and keys across folds
        all_groups = set()
        for fr in self.fold_results:
            all_groups.update(fr['evaluation'].keys())

        aggregated = {}

        for group in all_groups:
            # Skip non-dict entries (e.g., time_gap_by_bucket is a list)
            group_values = []
            for fr in self.fold_results:
                val = fr['evaluation'].get(group)
                if isinstance(val, dict):
                    group_values.append(val)

            if not group_values:
                continue

            # Collect all numeric keys
            all_keys = set()
            for gv in group_values:
                for k, v in gv.items():
                    if isinstance(v, (int, float)) and not np.isnan(v) and not np.isinf(v):
                        all_keys.add(k)

            group_agg = {}
            for key in sorted(all_keys):
                values = []
                for gv in group_values:
                    v = gv.get(key)
                    if v is not None and isinstance(v, (int, float)) and not np.isnan(v) and not np.isinf(v):
                        values.append(float(v))

                if values:
                    group_agg[key] = {
                        'mean': float(np.mean(values)),
                        'std': float(np.std(values)),
                        'min': float(np.min(values)),
                        'max': float(np.max(values)),
                        'n_folds': len(values),
                    }

            aggregated[group] = group_agg

        return aggregated

    def _extract_primary_metrics(
        self, aggregated: Dict
    ) -> Dict[str, Dict[str, float]]:
        """Extract primary and secondary metrics for quick access."""
        primary = {}

        for group, key in PRIMARY_METRICS:
            label = f"{group}.{key}"
            if group in aggregated and key in aggregated[group]:
                primary[label] = aggregated[group][key]

        for group, key in SECONDARY_METRICS:
            label = f"{group}.{key}"
            if group in aggregated and key in aggregated[group]:
                primary[label] = aggregated[group][key]

        return primary

    def _print_fold_primary(self, fold_result: Dict, label: str):
        """Print primary metrics for a single fold."""
        eval_data = fold_result['evaluation']
        info = fold_result['training_info']

        print(f"\n  Fold {label} results:")
        print(f"    Samples — train: {info['train_samples']:,}, "
              f"val: {info['val_samples']:,}, test: {info['test_samples']:,}")

        for group, key in PRIMARY_METRICS:
            if group in eval_data and key in eval_data[group]:
                val = eval_data[group][key]
                higher_better = key != 'top4_log_loss'
                print(f"    {key}: {val:.4f}")

    def _save_results(self, results: ExperimentResults):
        """Save results to JSON file."""
        results_dir = Path(self.config.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{results.name}_{timestamp}.json"
        filepath = results_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results.to_dict(), f, indent=2, default=str)

        print(f"\nResults saved to {filepath}")

    def _print_summary(self, results: ExperimentResults):
        """Print aggregated summary across all folds."""
        print(f"\n{'=' * 70}")
        print(f"EXPERIMENT SUMMARY: {results.name}")
        print(f"{'=' * 70}")

        # Primary metrics
        print("\n  PRIMARY METRICS (mean ± std across folds):")
        for group, key in PRIMARY_METRICS:
            label = f"{group}.{key}"
            if label in results.primary_metrics:
                m = results.primary_metrics[label]
                direction = "↑" if key != 'top4_log_loss' else "↓"
                print(f"    {direction} {key}: {m['mean']:.4f} ± {m['std']:.4f}")

        # Secondary metrics
        print("\n  SECONDARY METRICS:")
        for group, key in SECONDARY_METRICS:
            label = f"{group}.{key}"
            if label in results.primary_metrics:
                m = results.primary_metrics[label]
                print(f"    {key}: {m['mean']:.4f} ± {m['std']:.4f}")

        # Per-fold breakdown
        print("\n  PER-FOLD BREAKDOWN:")
        header_parts = ["Fold"]
        for _, key in PRIMARY_METRICS:
            short = key.replace('race_', '').replace('_capture_rate', '')
            header_parts.append(f"{short:>12s}")
        print(f"    {'  '.join(header_parts)}")

        for fr in results.fold_results:
            label = fr['fold_config'].get('label', f"fold_{fr['fold_idx']}")
            parts = [f"{label:>6s}"]
            for group, key in PRIMARY_METRICS:
                eval_data = fr['evaluation']
                if group in eval_data and key in eval_data[group]:
                    parts.append(f"{eval_data[group][key]:>12.4f}")
                else:
                    parts.append(f"{'N/A':>12s}")
            print(f"    {'  '.join(parts)}")

        print()

    def _print_feature_importance(self, top_n: int = 20):
        """Print average feature importance across folds."""
        # Collect all feature importance dicts
        all_importances = [
            fr['feature_importance']
            for fr in self.fold_results
            if fr.get('feature_importance')
        ]

        if not all_importances:
            return

        # Average across folds
        all_features = set()
        for imp in all_importances:
            all_features.update(imp.keys())

        avg_importance = {}
        for feat in all_features:
            values = [imp.get(feat, 0) for imp in all_importances]
            avg_importance[feat] = float(np.mean(values))

        # Sort and print top N
        sorted_features = sorted(avg_importance.items(), key=lambda x: x[1], reverse=True)
        total = sum(v for _, v in sorted_features)

        print(f"\n  TOP {top_n} FEATURE IMPORTANCE (avg gain across folds):")
        for i, (feat, imp) in enumerate(sorted_features[:top_n]):
            pct = imp / total * 100 if total > 0 else 0
            bar = "█" * int(pct)
            print(f"    {i+1:>2d}. {feat:<40s} {imp:>10.0f}  ({pct:>5.1f}%) {bar}")

        print()

    @staticmethod
    def compare(
        baseline: ExperimentResults,
        experiment: ExperimentResults,
    ):
        """Print side-by-side comparison of two experiments."""
        print(f"\n{'=' * 70}")
        print(f"COMPARISON: {baseline.name} vs {experiment.name}")
        print(f"{'=' * 70}")

        print(f"\n  {'Metric':<35s} {'Baseline':>12s} {'Experiment':>12s} {'Delta':>10s} {'%':>8s}")
        print(f"  {'─' * 77}")

        for group, key in PRIMARY_METRICS + SECONDARY_METRICS:
            label = f"{group}.{key}"
            b_metrics = baseline.primary_metrics.get(label)
            e_metrics = experiment.primary_metrics.get(label)

            if b_metrics is None or e_metrics is None:
                continue

            b_val = b_metrics['mean']
            e_val = e_metrics['mean']
            delta = e_val - b_val
            pct = (delta / abs(b_val) * 100) if b_val != 0 else 0

            # Determine if higher or lower is better
            higher_better = key != 'top4_log_loss' and key != 'mae'
            if key in ('win_cal_ratio', 'podium_cal_ratio'):
                # For calibration ratio, closer to 1.0 is better
                improvement = abs(e_val - 1.0) < abs(b_val - 1.0)
            else:
                improvement = (delta > 0) == higher_better

            marker = "✓" if improvement else "✗"

            is_primary = (group, key) in PRIMARY_METRICS
            prefix = "★" if is_primary else " "

            print(f"  {prefix}{key:<34s} {b_val:>12.4f} {e_val:>12.4f} "
                  f"{delta:>+10.4f} {pct:>+7.1f}% {marker}")

        print()

    @staticmethod
    def load_results(filepath: str) -> ExperimentResults:
        """Load ExperimentResults from a JSON file."""
        with open(filepath) as f:
            data = json.load(f)

        return ExperimentResults(
            name=data['name'],
            description=data.get('description', ''),
            fold_results=data['fold_results'],
            aggregated=data['aggregated'],
            primary_metrics=data['primary_metrics'],
            timestamp=data['timestamp'],
            config_summary=data.get('config_summary', {}),
        )
