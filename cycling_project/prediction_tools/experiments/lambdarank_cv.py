"""
3-fold CV for the full-field LambdaRank probability head.

Mirrors the fold configuration used in Step A of the ranking experiment
(train through end-of-year N, validate on year N+1, test on year N+2) so
the numbers are directly comparable to experiment_log.md.

Compares two learning-rate configs side by side:
- LR=0.05 (production default at the time of this experiment)
- LR=0.01 (candidate, matches the production contender tuning)

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.lambdarank_cv
"""

import json
from dataclasses import dataclass, field
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


# Same folds used in ExperimentRunner — aligns with Step A numbers in
# experiment_log.md (train→end-of-year N, val on N+1, test on N+2).
FOLDS = [
    {'train_end': '2021-12-31', 'val_end': '2022-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'val_end': '2023-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'val_end': '2024-12-31', 'label': '2025'},
]


@dataclass
class LambdaRankCVConfig:
    name: str
    learning_rate: float
    n_estimators: int = 2000
    early_stopping_rounds: int = 300
    num_leaves: int = 63
    feature_fraction: float = 0.8
    bagging_fraction: float = 0.8
    bagging_freq: int = 5
    min_child_samples: int = 50


def _load_full_df() -> pd.DataFrame:
    db_path = Path(__file__).parent.parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    cfg = DataConfig(
        db_path=str(db_path),
        start_date='2018-01-01',
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def run_fold(
    df: pd.DataFrame,
    fold: Dict[str, str],
    cv_config: LambdaRankCVConfig,
) -> Dict[str, Any]:
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])

    train = df[df['competition_date'] <= train_end].copy()
    val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
    test = df[df['competition_date'] > val_end].copy()

    # Cap test to the *calendar year* matching the label so we don't pull
    # in later years (important for the 2023 fold since we have 2024-2026 data).
    test_year = int(fold['label'])
    test = test[test['competition_date'].dt.year == test_year].copy()

    print(f"  Train: {len(train):,} rows, {train['competition_id'].nunique():,} races "
          f"({train['competition_date'].min().date()} to {train['competition_date'].max().date()})")
    print(f"  Val:   {len(val):,} rows, {val['competition_id'].nunique():,} races")
    print(f"  Test:  {len(test):,} rows, {test['competition_id'].nunique():,} races "
          f"(year {test_year})")

    if len(test) == 0:
        print("  [skip] no test rows")
        return {'fold_label': fold['label'], 'skipped': True}

    predictor_cfg = LambdaRankPredictorConfig(
        n_estimators=cv_config.n_estimators,
        early_stopping_rounds=cv_config.early_stopping_rounds,
    )
    predictor_cfg.lgb_params.update({
        'learning_rate': cv_config.learning_rate,
        'num_leaves': cv_config.num_leaves,
        'feature_fraction': cv_config.feature_fraction,
        'bagging_fraction': cv_config.bagging_fraction,
        'bagging_freq': cv_config.bagging_freq,
        'min_child_samples': cv_config.min_child_samples,
    })

    predictor = LambdaRankProbabilityPredictor(predictor_cfg)
    info = predictor.train(train, val, verbose=False)

    T = predictor.calibrate_temperature(val)
    test_metrics = predictor.evaluate(test)

    # Also report the pre-temperature metric suite so we can see what
    # calibration actually fixed.
    predictor.config.temperature = 1.0
    test_metrics_raw = predictor.evaluate(test)
    predictor.config.temperature = T  # restore

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'best_iteration': info['best_iteration'],
        'n_features': info['n_features'],
        'n_train_rows': info['n_train_rows'],
        'n_train_groups': info['n_train_groups'],
        'calibrated_temperature': T,
        'test_metrics': test_metrics,
        'test_metrics_T1': test_metrics_raw,
    }


def run_config(df: pd.DataFrame, cfg: LambdaRankCVConfig) -> Dict[str, Any]:
    print(f"\n{'=' * 70}")
    print(f"CONFIG: {cfg.name}")
    print(f"  learning_rate: {cfg.learning_rate}")
    print(f"  n_estimators:  {cfg.n_estimators}")
    print(f"  early_stop:    {cfg.early_stopping_rounds}")
    print(f"{'=' * 70}")

    fold_results = []
    for i, fold in enumerate(FOLDS):
        print(f"\n--- Fold {i + 1}/{len(FOLDS)} (test={fold['label']}) ---")
        fold_results.append(run_fold(df, fold, cfg))

    agg = _aggregate(fold_results)
    return {
        'config': cfg.__dict__,
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
    # Also aggregate best_iteration and temperature
    for key in ('best_iteration', 'calibrated_temperature'):
        vals = [fr[key] for fr in usable if key in fr]
        if vals:
            agg[key] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
            }
    return agg


def _print_summary(name: str, result: Dict[str, Any]):
    print(f"\n{'=' * 70}")
    print(f"SUMMARY — {name}")
    print(f"{'=' * 70}")
    agg = result['aggregated']
    headline = [
        'winner_capture', 'podium_capture', 'win_log_loss',
        'discrimination_ratio', 'win_cal_ratio', 'win_ece',
        'best_iteration', 'calibrated_temperature',
    ]
    for k in headline:
        if k in agg:
            m = agg[k]
            print(f"  {k:<28s} {m['mean']:>8.4f} ± {m['std']:.4f}")

    print("\n  Per-fold winner capture:")
    for fr in result['fold_results']:
        if fr.get('skipped'):
            continue
        tm = fr['test_metrics']
        print(f"    {fr['fold_label']}: winner={tm['winner_capture']:.4f}  "
              f"podium={tm['podium_capture']:.4f}  T={fr['calibrated_temperature']:.3f}  "
              f"best_iter={fr['best_iteration']}")


def main():
    print("=" * 70)
    print("LAMBDARANK HEAD — 3-FOLD CV (LR sweep)")
    print("=" * 70)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")

    df = _load_full_df()
    print(f"\nLoaded {len(df):,} samples, {df['competition_id'].nunique():,} competitions, "
          f"{df['competition_date'].min().date()} to {df['competition_date'].max().date()}")

    configs = [
        LambdaRankCVConfig(name='lr_0.05', learning_rate=0.05),
        LambdaRankCVConfig(name='lr_0.01', learning_rate=0.01),
    ]

    all_results: Dict[str, Any] = {
        'started_at': started.isoformat(),
        'folds': FOLDS,
        'data_stats': {
            'total_rows': int(len(df)),
            'total_competitions': int(df['competition_id'].nunique()),
            'date_min': str(df['competition_date'].min().date()),
            'date_max': str(df['competition_date'].max().date()),
        },
        'configs': {},
    }

    for cfg in configs:
        all_results['configs'][cfg.name] = run_config(df, cfg)
        _print_summary(cfg.name, all_results['configs'][cfg.name])

    # Side-by-side comparison
    print(f"\n{'=' * 70}")
    print("SIDE-BY-SIDE COMPARISON")
    print(f"{'=' * 70}")

    rows = [
        ('winner_capture', 'higher'),
        ('podium_capture', 'higher'),
        ('win_log_loss', 'lower'),
        ('discrimination_ratio', 'higher'),
        ('win_ece', 'lower'),
        ('best_iteration', 'info'),
        ('calibrated_temperature', 'info'),
    ]
    print(f"\n  {'Metric':<28s} {'LR=0.05':>18s} {'LR=0.01':>18s} {'Δ (0.01−0.05)':>16s}")
    print(f"  {'-' * 82}")
    a = all_results['configs']['lr_0.05']['aggregated']
    b = all_results['configs']['lr_0.01']['aggregated']
    for key, direction in rows:
        if key not in a or key not in b:
            continue
        am, astd = a[key]['mean'], a[key].get('std', 0.0)
        bm, bstd = b[key]['mean'], b[key].get('std', 0.0)
        delta = bm - am
        marker = ''
        if direction == 'higher':
            marker = '↑ b' if delta > 0 else '↓ b'
        elif direction == 'lower':
            marker = '↓ b (better)' if delta < 0 else '↑ b (worse)'
        else:
            marker = ''
        print(f"  {key:<28s} {am:>10.4f}±{astd:>5.4f} "
              f"{bm:>10.4f}±{bstd:>5.4f} {delta:>+10.4f} {marker}")

    ended = datetime.now()
    all_results['ended_at'] = ended.isoformat()
    duration_s = (ended - started).total_seconds()
    all_results['duration_seconds'] = duration_s
    print(f"\nCompleted in {duration_s:.1f}s ({duration_s/60:.1f} min)")

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"lambdarank_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Results saved to {out_path}")


if __name__ == '__main__':
    main()
