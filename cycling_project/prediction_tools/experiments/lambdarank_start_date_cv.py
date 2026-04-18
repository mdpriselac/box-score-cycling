"""
Start-date sweep for the LambdaRank probability head.

Question: does extending the training window backwards in time help?
Adding older races gives more labels but noisier rider histories
(shorter feature rollups on the earliest training races).

Method: run the shipped production LambdaRank config across four
training start dates — 2018 (baseline), 2017, 2016, 2015 — on the same
3-fold CV folds used in `lambdarank_cv.py`. Only `start_date` varies;
everything else matches production.

Reports primary (winner/podium/log-loss) and calibration metrics per
start_date, aggregated across the 3 folds.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.lambdarank_start_date_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)


# Same folds as lambdarank_cv.py / ExperimentRunner defaults.
FOLDS = [
    {'train_end': '2021-12-31', 'val_end': '2022-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'val_end': '2023-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'val_end': '2024-12-31', 'label': '2025'},
]

START_DATES = ['2018-01-01', '2017-01-01', '2016-01-01', '2015-01-01']


def _load_full_df(start_date: str) -> pd.DataFrame:
    db_path = (
        Path(__file__).parent.parent.parent
        / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    )
    cfg = DataConfig(
        db_path=str(db_path),
        start_date=start_date,
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def run_fold(df: pd.DataFrame, fold: Dict[str, str]) -> Dict[str, Any]:
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])

    train = df[df['competition_date'] <= train_end].copy()
    val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
    test = df[df['competition_date'] > val_end].copy()
    test_year = int(fold['label'])
    test = test[test['competition_date'].dt.year == test_year].copy()

    print(
        f"    Train: {len(train):>8,} rows / {train['competition_id'].nunique():>5,} races  "
        f"({train['competition_date'].min().date()} → {train['competition_date'].max().date()})"
    )
    print(
        f"    Val:   {len(val):>8,} rows / {val['competition_id'].nunique():>5,} races"
    )
    print(
        f"    Test:  {len(test):>8,} rows / {test['competition_id'].nunique():>5,} races "
        f"(year {test_year})"
    )
    if len(test) == 0:
        return {'fold_label': fold['label'], 'skipped': True}

    # Use production defaults — no overrides.
    predictor = LambdaRankProbabilityPredictor(LambdaRankPredictorConfig())
    info = predictor.train(train, val, verbose=False)

    T = predictor.calibrate_temperature(val)
    metrics = predictor.evaluate(test)

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'best_iteration': info['best_iteration'],
        'n_train_rows': info['n_train_rows'],
        'n_train_groups': info['n_train_groups'],
        'calibrated_temperature': T,
        'test_metrics': metrics,
    }


def run_start_date(start_date: str) -> Dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(f"START DATE: {start_date}")
    print(f"{'=' * 70}")

    df = _load_full_df(start_date)
    print(
        f"  Loaded {len(df):,} rows / {df['competition_id'].nunique():,} competitions  "
        f"({df['competition_date'].min().date()} → {df['competition_date'].max().date()})"
    )

    fold_results = []
    for i, fold in enumerate(FOLDS):
        print(f"\n  --- Fold {i + 1}/{len(FOLDS)} (test={fold['label']}) ---")
        fold_results.append(run_fold(df, fold))

    agg = _aggregate(fold_results)
    return {
        'start_date': start_date,
        'data_stats': {
            'total_rows': int(len(df)),
            'total_competitions': int(df['competition_id'].nunique()),
            'date_min': str(df['competition_date'].min().date()),
            'date_max': str(df['competition_date'].max().date()),
        },
        'fold_results': fold_results,
        'aggregated': agg,
    }


def _aggregate(fold_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    usable = [fr for fr in fold_results if not fr.get('skipped')]
    keys = set()
    for fr in usable:
        keys.update(fr['test_metrics'].keys())

    agg: Dict[str, Dict[str, float]] = {}
    for key in sorted(keys):
        vals = [fr['test_metrics'][key] for fr in usable if key in fr['test_metrics']]
        vals = [v for v in vals if v is not None and not (isinstance(v, float) and np.isnan(v))]
        if not vals:
            continue
        agg[key] = {
            'mean': float(np.mean(vals)),
            'std': float(np.std(vals)),
            'min': float(np.min(vals)),
            'max': float(np.max(vals)),
            'n_folds': len(vals),
        }
    for key in ('best_iteration', 'calibrated_temperature', 'n_train_rows', 'n_train_groups'):
        vals = [fr[key] for fr in usable if key in fr]
        if vals:
            agg[key] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
            }
    return agg


def _print_config_summary(sd_result: Dict[str, Any]):
    agg = sd_result['aggregated']
    print(f"\n  Summary for start_date={sd_result['start_date']}:")
    headline = [
        'winner_capture', 'podium_capture', 'win_log_loss',
        'discrimination_ratio', 'win_cal_ratio', 'win_ece',
        'best_iteration', 'calibrated_temperature', 'n_train_rows',
    ]
    for k in headline:
        if k in agg:
            m = agg[k]
            std_str = f" ± {m['std']:.4f}" if 'std' in m else ""
            print(f"    {k:<28s} {m['mean']:>10.4f}{std_str}")

    print("\n    Per-fold winner capture:")
    for fr in sd_result['fold_results']:
        if fr.get('skipped'):
            continue
        tm = fr['test_metrics']
        print(
            f"      {fr['fold_label']}: winner={tm['winner_capture']:.4f}  "
            f"podium={tm['podium_capture']:.4f}  T={fr['calibrated_temperature']:.3f}  "
            f"best_iter={fr['best_iteration']}"
        )


def _print_comparison(results_by_start: Dict[str, Dict[str, Any]]):
    print(f"\n{'=' * 90}")
    print("SIDE-BY-SIDE COMPARISON ACROSS START DATES")
    print(f"{'=' * 90}")

    headers = list(results_by_start.keys())
    metric_rows = [
        ('winner_capture', 'higher'),
        ('podium_capture', 'higher'),
        ('win_log_loss', 'lower'),
        ('discrimination_ratio', 'higher'),
        ('win_cal_ratio', 'info'),
        ('win_ece', 'lower'),
        ('best_iteration', 'info'),
        ('calibrated_temperature', 'info'),
        ('n_train_rows', 'info'),
    ]

    col_w = 18
    header = f"  {'Metric':<26s}" + "".join(f"{h:>{col_w}s}" for h in headers)
    print(header)
    print("  " + "-" * (26 + col_w * len(headers)))

    # Reference values from the 2018 baseline to flag improvements
    baseline_key = '2018-01-01'
    baseline_agg = results_by_start[baseline_key]['aggregated']

    for key, direction in metric_rows:
        row = f"  {key:<26s}"
        for h in headers:
            agg = results_by_start[h]['aggregated']
            if key not in agg:
                row += f"{'N/A':>{col_w}s}"
                continue
            mean = agg[key]['mean']
            std = agg[key].get('std')
            if std is not None and direction != 'info':
                cell = f"{mean:.4f}±{std:.3f}"
            elif std is not None:
                cell = f"{mean:.3f}±{std:.3f}"
            else:
                cell = f"{mean:.4f}"
            # Mark improvement vs baseline
            if h != baseline_key and key in baseline_agg and direction != 'info':
                b = baseline_agg[key]['mean']
                better = (
                    (direction == 'higher' and mean > b) or
                    (direction == 'lower' and mean < b)
                )
                marker = '↑' if better else '↓'
                cell = f"{marker} {cell}"
            row += f"{cell:>{col_w}s}"
        print(row)


def main():
    print("=" * 70)
    print("LAMBDARANK START-DATE CV SWEEP")
    print("=" * 70)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Production LambdaRank config. Varying only `start_date`.")
    print(f"Start dates: {', '.join(START_DATES)}")
    print(f"Folds: {[f['label'] for f in FOLDS]}")

    results_by_start: Dict[str, Dict[str, Any]] = {}
    for sd in START_DATES:
        sd_result = run_start_date(sd)
        results_by_start[sd] = sd_result
        _print_config_summary(sd_result)

    _print_comparison(results_by_start)

    ended = datetime.now()
    duration_s = (ended - started).total_seconds()
    print(f"\nCompleted in {duration_s:.1f}s ({duration_s/60:.1f} min)")

    output = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': duration_s,
        'folds': FOLDS,
        'start_dates': START_DATES,
        'results_by_start_date': results_by_start,
    }

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"lambdarank_start_date_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"Results saved to {out_path}")


if __name__ == '__main__':
    main()
