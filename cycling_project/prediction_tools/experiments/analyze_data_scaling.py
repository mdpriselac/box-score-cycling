"""
Cross-cutting analysis: how does model performance scale with training
data size?

Combines the two start-date sweep experiments (LambdaRank and
multiclass) and reshapes the 24 runs into a data-scaling view:

- For each test year (2023 / 2024 / 2025), holds the target population
  constant and plots performance across the 4 start_date configs (which
  vary training size by ~1.9x).
- Fits a simple linear regression `metric = a + b * train_rows` within
  each test year to get a "marginal return" slope.

The question this answers: within the 270K–520K training-rows range our
CV explores, are we on the rising part of the learning curve or flat?

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.analyze_data_scaling
"""

import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


EXPERIMENTS_DIR = Path('experiments')


def _latest(pattern: str) -> Optional[Path]:
    paths = sorted(EXPERIMENTS_DIR.glob(pattern))
    return paths[-1] if paths else None


def load_lambdarank_runs() -> List[Dict[str, Any]]:
    path = _latest('lambdarank_start_date_cv_*.json')
    if not path:
        return []
    with open(path) as f:
        data = json.load(f)

    runs = []
    for sd, sd_result in data['results_by_start_date'].items():
        for fr in sd_result['fold_results']:
            if fr.get('skipped'):
                continue
            tm = fr['test_metrics']
            runs.append({
                'head': 'lambdarank',
                'start_date': sd,
                'test_year': int(fr['fold_label']),
                'train_rows': int(fr['n_train_rows']),
                'train_groups': int(fr['n_train_groups']),
                'winner': float(tm['winner_capture']),
                'podium': float(tm['podium_capture']),
                'log_loss': float(tm['win_log_loss']),
                'discrimination_ratio': float(tm.get('discrimination_ratio', float('nan'))),
                'cal_ratio': float(tm.get('win_cal_ratio', float('nan'))),
                'ece': float(tm.get('win_ece', float('nan'))),
                'best_iter': int(fr.get('best_iteration', 0)),
            })
    return runs


def load_multiclass_runs() -> List[Dict[str, Any]]:
    """
    Multiclass sweep saves:
    - experiments/multiclass_start_2018_<ts>.json  (per-start-date full ExperimentResults)
    - experiments/multiclass_start_date_cv_<ts>.json  (summary)

    We want the per-fold details from the ExperimentResults. Walk the
    latest multiclass_start_<year>_*.json files.
    """
    runs = []
    for year in (2018, 2017, 2016, 2015):
        paths = sorted(EXPERIMENTS_DIR.glob(f'multiclass_start_{year}_*.json'))
        if not paths:
            continue
        with open(paths[-1]) as f:
            data = json.load(f)
        for fr in data['fold_results']:
            eval_data = fr['evaluation']
            prob = eval_data.get('probability_contender_top4', {})
            bucket = eval_data.get('bucket', {})
            runs.append({
                'head': 'multiclass',
                'start_date': f'{year}-01-01',
                'test_year': int(fr['fold_config']['label']),
                'train_rows': int(fr['training_info'].get('train_samples', 0)),
                'winner': float(prob.get('race_winner_capture_rate', float('nan'))),
                'podium': float(prob.get('race_podium_capture_rate', float('nan'))),
                'log_loss': float(prob.get('top4_log_loss', float('nan'))),
                'brier': float(prob.get('top4_brier', float('nan'))),
                'cal_ratio': float(prob.get('win_cal_ratio', float('nan'))),
                'bucket_mae': float(bucket.get('mae', float('nan'))),
            })
    return runs


def _slope(x: List[float], y: List[float]) -> Tuple[float, float, float]:
    """Simple linear regression; returns (slope, intercept, r)."""
    xs = np.asarray(x, dtype=float)
    ys = np.asarray(y, dtype=float)
    if len(xs) < 2:
        return float('nan'), float('nan'), float('nan')
    x_mean = xs.mean()
    y_mean = ys.mean()
    cov = np.mean((xs - x_mean) * (ys - y_mean))
    var_x = np.mean((xs - x_mean) ** 2)
    var_y = np.mean((ys - y_mean) ** 2)
    if var_x == 0 or var_y == 0:
        return float('nan'), float('nan'), float('nan')
    slope = cov / var_x
    intercept = y_mean - slope * x_mean
    r = cov / np.sqrt(var_x * var_y)
    return float(slope), float(intercept), float(r)


def print_by_year(head_name: str, runs: List[Dict[str, Any]], metrics: List[Tuple[str, str]]):
    print(f"\n{'=' * 90}")
    print(f"{head_name.upper()} — PER TEST YEAR, ORDERED BY TRAIN SIZE")
    print(f"{'=' * 90}")

    test_years = sorted({r['test_year'] for r in runs})
    for ty in test_years:
        subset = sorted(
            [r for r in runs if r['test_year'] == ty],
            key=lambda r: r['train_rows'],
        )
        if len(subset) < 2:
            continue

        print(f"\n  Test year {ty}:")
        print(
            f"    {'start_date':>11s}  {'train_rows':>11s}"
            + "".join(f"  {nm:>11s}" for nm, _ in metrics)
        )
        for r in subset:
            cells = [f"{r['start_date']:>11s}", f"{r['train_rows']:>11,d}"]
            for _, key in metrics:
                v = r.get(key)
                if v is None or (isinstance(v, float) and np.isnan(v)):
                    cells.append(f"{'N/A':>11s}")
                else:
                    cells.append(f"{v:>11.4f}")
            print("    " + "  ".join(cells))

        xs = [r['train_rows'] for r in subset]
        for nm, key in metrics:
            ys = [r[key] for r in subset]
            if any(isinstance(y, float) and np.isnan(y) for y in ys):
                continue
            slope, _, r_val = _slope(xs, ys)
            # Report slope per 100K rows for readability.
            per_100k = slope * 100_000
            direction = "+" if per_100k >= 0 else ""
            print(f"    → slope of {nm} per 100K rows: {direction}{per_100k:.4f}  (r={r_val:+.3f})")


def _aggregate_by_start(runs: List[Dict[str, Any]], metric: str) -> Dict[str, float]:
    out = {}
    by_sd: Dict[str, List[float]] = {}
    for r in runs:
        v = r.get(metric)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        by_sd.setdefault(r['start_date'], []).append(v)
    for sd, vs in by_sd.items():
        out[sd] = float(np.mean(vs))
    return out


def main():
    lr_runs = load_lambdarank_runs()
    mc_runs = load_multiclass_runs()

    print(f"Loaded {len(lr_runs)} LambdaRank runs, {len(mc_runs)} multiclass runs.")

    if lr_runs:
        print_by_year(
            "lambdarank",
            lr_runs,
            [('winner', 'winner'), ('podium', 'podium'), ('log_loss', 'log_loss')],
        )

    if mc_runs:
        print_by_year(
            "multiclass",
            mc_runs,
            [('winner', 'winner'), ('podium', 'podium'), ('log_loss', 'log_loss')],
        )

    # Cross-cutting summary: average metric per start_date across all folds
    print(f"\n{'=' * 90}")
    print("AVERAGE METRIC PER START DATE (across 3 folds)")
    print(f"{'=' * 90}")
    for head_name, runs in [('lambdarank', lr_runs), ('multiclass', mc_runs)]:
        if not runs:
            continue
        print(f"\n  {head_name}:")
        avg_winner = _aggregate_by_start(runs, 'winner')
        avg_podium = _aggregate_by_start(runs, 'podium')
        avg_log = _aggregate_by_start(runs, 'log_loss')
        print(f"    {'start_date':>11s}  {'winner':>9s}  {'podium':>9s}  {'log_loss':>9s}")
        for sd in sorted(avg_winner.keys()):
            print(
                f"    {sd:>11s}  {avg_winner[sd]:>9.4f}  "
                f"{avg_podium.get(sd, float('nan')):>9.4f}  "
                f"{avg_log.get(sd, float('nan')):>9.4f}"
            )


if __name__ == '__main__':
    main()
