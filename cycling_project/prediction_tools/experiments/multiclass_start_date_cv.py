"""
Full multiclass-stack start-date CV sweep.

Companion experiment to `lambdarank_start_date_cv.py`. Runs the existing
`ExperimentRunner` (bucket + time_gap + multiclass probability +
calibrated + contender cascade) across four training start dates to
test whether extending the training window backwards helps the
multiclass contender cascade (the high-water-mark model on winner/podium
capture per Stage 0).

Uses production-matching contender config: top-15 filter, LR=0.01, OOF,
5-class reduction, Stage 0 gradients. Caps n_estimators at 500 (vs
production's 2000) to keep runtime reasonable — the comparison across
start_dates is apples-to-apples even at this lower cap.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.multiclass_start_date_cv
"""

import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from cycling_project.prediction_tools.experiment_runner import (
    ExperimentConfig, ExperimentRunner, PRIMARY_METRICS, SECONDARY_METRICS
)


START_DATES = ['2018-01-01', '2017-01-01', '2016-01-01', '2015-01-01']

# Reference: per-fold metric keys we care about
HEADLINE_METRICS = [
    ('probability_contender_top4', 'race_winner_capture_rate'),
    ('probability_contender_top4', 'race_podium_capture_rate'),
    ('probability_contender_top4', 'top4_log_loss'),
    ('probability_contender_top4', 'win_cal_ratio'),
    ('probability_contender_top4', 'podium_cal_ratio'),
    ('probability_contender_top4', 'top4_brier'),
    ('bucket', 'mae'),
]


def build_config(start_date: str, n_estimators: int = 500) -> ExperimentConfig:
    return ExperimentConfig(
        name=f"multiclass_start_{start_date[:4]}",
        description=(
            f"Full multiclass stack with start_date={start_date}, "
            "production contender config."
        ),
        start_date=start_date,
        n_estimators=n_estimators,
        early_stopping=50,
        contender_top_n=15,
        contender_learning_rate=0.01,
        contender_use_oof=True,
        contender_n_classes=5,
        include_gradient_features=True,
        ranking_method='expected_bucket',
        train_time_gap=True,
        train_probability=True,
        train_calibrated=True,
        train_contender=True,
        verbose=False,
        results_dir='experiments/',
    )


def summarize(results_by_start: Dict[str, Any]) -> Dict[str, Any]:
    """Collapse ExperimentResults objects into a compact summary."""
    summary: Dict[str, Any] = {}
    for sd, res in results_by_start.items():
        primary = {}
        for group, key in HEADLINE_METRICS:
            label = f"{group}.{key}"
            if label in res.primary_metrics:
                primary[label] = res.primary_metrics[label]
        summary[sd] = {
            'primary_metrics': primary,
            'per_fold': [
                {
                    'fold_label': fr['fold_config']['label'],
                    'train_samples': fr['training_info'].get('train_samples'),
                    'winner_capture': fr['evaluation'].get('probability_contender_top4', {}).get(
                        'race_winner_capture_rate'
                    ),
                    'podium_capture': fr['evaluation'].get('probability_contender_top4', {}).get(
                        'race_podium_capture_rate'
                    ),
                    'log_loss': fr['evaluation'].get('probability_contender_top4', {}).get(
                        'top4_log_loss'
                    ),
                }
                for fr in res.fold_results
            ],
        }
    return summary


def _fmt(metric: Dict[str, float], decimals: int = 4) -> str:
    if not metric:
        return 'N/A'
    return f"{metric['mean']:.{decimals}f} ± {metric['std']:.{decimals}f}"


def print_comparison(summary: Dict[str, Any]):
    print(f"\n{'=' * 100}")
    print("MULTICLASS STACK — SIDE-BY-SIDE COMPARISON ACROSS START DATES")
    print(f"{'=' * 100}")

    headers = list(summary.keys())
    rows = [
        ('probability_contender_top4.race_winner_capture_rate', 'higher'),
        ('probability_contender_top4.race_podium_capture_rate', 'higher'),
        ('probability_contender_top4.top4_log_loss', 'lower'),
        ('probability_contender_top4.win_cal_ratio', 'cal'),
        ('probability_contender_top4.podium_cal_ratio', 'cal'),
        ('probability_contender_top4.top4_brier', 'lower'),
        ('bucket.mae', 'lower'),
    ]

    col_w = 22
    header = f"  {'Metric':<42s}" + "".join(f"{h:>{col_w}s}" for h in headers)
    print(header)
    print("  " + "-" * (42 + col_w * len(headers)))

    baseline_key = '2018-01-01'
    baseline_primary = summary[baseline_key]['primary_metrics']

    for key, direction in rows:
        row_cells = []
        for h in headers:
            m = summary[h]['primary_metrics'].get(key)
            if not m:
                row_cells.append('N/A')
                continue
            cell = _fmt(m, decimals=4)
            if h != baseline_key and key in baseline_primary:
                b = baseline_primary[key]['mean']
                v = m['mean']
                better = (
                    (direction == 'higher' and v > b) or
                    (direction == 'lower' and v < b) or
                    (direction == 'cal' and abs(v - 1.0) < abs(b - 1.0))
                )
                cell = f"{'↑' if better else '↓'} {cell}"
            row_cells.append(cell)
        short_key = key.split('.')[-1]
        row = f"  {short_key:<42s}" + "".join(f"{c:>{col_w}s}" for c in row_cells)
        print(row)

    print("\n  Per-fold winner capture:")
    for h in headers:
        folds = summary[h]['per_fold']
        line = f"    {h}:"
        for fr in folds:
            wc = fr.get('winner_capture')
            lbl = fr.get('fold_label')
            if wc is not None:
                line += f"  {lbl}={wc:.4f}"
        print(line)


def main():
    print("=" * 70)
    print("MULTICLASS STACK — START-DATE CV SWEEP")
    print("=" * 70)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Start dates: {', '.join(START_DATES)}")

    results_by_start: Dict[str, Any] = {}
    for sd in START_DATES:
        print(f"\n{'#' * 70}")
        print(f"# START DATE: {sd}")
        print(f"{'#' * 70}")
        config = build_config(sd)
        runner = ExperimentRunner(config)
        results_by_start[sd] = runner.run()

    summary = summarize(results_by_start)
    print_comparison(summary)

    ended = datetime.now()
    duration_s = (ended - started).total_seconds()
    print(f"\nCompleted in {duration_s:.1f}s ({duration_s/60:.1f} min)")

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"multiclass_start_date_cv_{timestamp}.json"

    # The full ExperimentResults are already saved individually by the
    # runner; here we just persist the cross-start-date summary.
    with open(out_path, 'w') as f:
        json.dump({
            'started_at': started.isoformat(),
            'ended_at': ended.isoformat(),
            'duration_seconds': duration_s,
            'start_dates': START_DATES,
            'summary': summary,
        }, f, indent=2, default=str)
    print(f"Summary saved to {out_path}")


if __name__ == '__main__':
    main()
