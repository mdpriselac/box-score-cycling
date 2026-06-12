"""
3-fold CV: linear blend of multiclass contender win_p with LambdaRank win_p.

Tests whether a per-rider probability blend
    blend_p = w * mc_p + (1-w) * lr_p
beats either head alone on winner capture, podium capture, log loss, and
calibration. Sweeps w from 0.0 (pure LambdaRank) to 1.0 (pure multiclass,
renormalized on full field).

mc_p is the multiclass contender's prob_win, padded over the full field
with 0 for non-contenders, then renormalized per race so it sums to 1.
lr_p is the LambdaRank softmax win_p over the full field with calibrated
temperature.

Folds match Step A / lambdarank_cv.py:
    train→2021 / val→2022 / test→2023
    train→2022 / val→2023 / test→2024
    train→2023 / val→2024 / test→2025

Test set is calendar-year-capped to match the LambdaRank CV protocol.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.blend_multiclass_lambdarank_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)
from cycling_project.prediction_tools.training import ModelTrainer, TrainingConfig
from cycling_project.webscrape_tools.logging_config import get_logger


logger = get_logger(__name__)


FOLDS = [
    {'train_end': '2021-12-31', 'val_end': '2022-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'val_end': '2023-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'val_end': '2024-12-31', 'label': '2025'},
]

START_DATE = '2018-01-01'
CONTENDER_TOP_N = 15

# Production-aligned multiclass cascade hyperparameters
MULTICLASS_CONFIG = {
    'n_estimators': 500,
    'early_stopping': 50,
    'contender_top_n': CONTENDER_TOP_N,
    'contender_learning_rate': 0.01,
    'contender_use_oof': True,
    'contender_n_classes': 5,
    'include_gradient_features': True,
}

# LambdaRank head config (production LR)
LAMBDARANK_CONFIG = {
    'learning_rate': 0.05,
    'n_estimators': 2000,
    'early_stopping_rounds': 300,
}

# Blend weights to sweep
W_GRID = [round(float(x), 2) for x in np.linspace(0.0, 1.0, 11)]


# ---------------------------------------------------------------------------
# Data loading + slicing
# ---------------------------------------------------------------------------

def _load_full_df() -> pd.DataFrame:
    db_path = (
        Path(__file__).parent.parent.parent
        / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    )
    cfg = DataConfig(
        db_path=str(db_path),
        start_date=START_DATE,
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def _slice_fold(
    df: pd.DataFrame, fold: Dict[str, str]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Mirror lambdarank_cv.py: train→train_end, val→val_end, test→year matching label."""
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])

    train = df[df['competition_date'] <= train_end].copy()
    val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
    test = df[df['competition_date'] > val_end].copy()

    test_year = int(fold['label'])
    test = test[test['competition_date'].dt.year == test_year].copy()

    return train, val, test


# ---------------------------------------------------------------------------
# Model training (per fold)
# ---------------------------------------------------------------------------

def _train_multiclass(
    train: pd.DataFrame,
    val: pd.DataFrame,
    fold_label: str,
):
    """Train bucket + contender (skip time_gap / weighted / calibrated)."""
    cfg = TrainingConfig(
        start_date=START_DATE,
        train_end_date=train['competition_date'].max().strftime('%Y-%m-%d'),
        val_end_date=val['competition_date'].max().strftime('%Y-%m-%d'),
        bucket_n_estimators=MULTICLASS_CONFIG['n_estimators'],
        bucket_early_stopping=MULTICLASS_CONFIG['early_stopping'],
        time_gap_n_estimators=MULTICLASS_CONFIG['n_estimators'],
        time_gap_early_stopping=MULTICLASS_CONFIG['early_stopping'],
        probability_n_estimators=MULTICLASS_CONFIG['n_estimators'],
        probability_early_stopping=MULTICLASS_CONFIG['early_stopping'],
        contender_top_n=MULTICLASS_CONFIG['contender_top_n'],
        contender_learning_rate=MULTICLASS_CONFIG['contender_learning_rate'],
        contender_use_oof=MULTICLASS_CONFIG['contender_use_oof'],
        contender_n_classes=MULTICLASS_CONFIG['contender_n_classes'],
        include_gradient_features=MULTICLASS_CONFIG['include_gradient_features'],
        fold_label=fold_label,
        train_time_gap=False,
        train_probability=False,
        train_calibrated_probability=False,
        train_contender_probability=True,
        verbose=False,
    )
    trainer = ModelTrainer(cfg)
    bucket_pred, bucket_info = trainer.train_bucket_predictor(train, val)
    contender_pred, contender_info = trainer.train_contender_predictor(
        train, val, bucket_pred
    )
    return bucket_pred, contender_pred, {
        'bucket_best_iteration': bucket_info.get('best_iteration'),
        'contender_best_iteration': contender_info.get('best_iteration'),
    }


def _train_lambdarank(
    train: pd.DataFrame, val: pd.DataFrame
) -> Tuple[LambdaRankProbabilityPredictor, Dict[str, Any]]:
    cfg = LambdaRankPredictorConfig(
        n_estimators=LAMBDARANK_CONFIG['n_estimators'],
        early_stopping_rounds=LAMBDARANK_CONFIG['early_stopping_rounds'],
    )
    cfg.lgb_params['learning_rate'] = LAMBDARANK_CONFIG['learning_rate']
    pred = LambdaRankProbabilityPredictor(cfg)
    info = pred.train(train, val, verbose=False)
    T = pred.calibrate_temperature(val)
    info['calibrated_temperature'] = T
    return pred, info


# ---------------------------------------------------------------------------
# Test predictions
# ---------------------------------------------------------------------------

def _multiclass_win_p_full(
    test: pd.DataFrame, bucket_pred, contender_pred, top_n: int = CONTENDER_TOP_N
) -> np.ndarray:
    """Multiclass win prob over the full test field.

    Non-contenders (outside top-N by predicted bucket) get prob = 0; the
    resulting per-race vector is then renormalized so it sums to 1.

    Returns array aligned to test row order.
    """
    expected = bucket_pred.predict_continuous(test)
    df = test.copy()
    df['classifier_expected_bucket'] = expected
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
    df['_is_contender'] = df['_rank'] <= top_n

    cont_df = df[df['_is_contender']].copy()
    if len(cont_df) == 0:
        return np.zeros(len(df))

    proba = contender_pred.predict_proba(cont_df)
    win_p_cont = proba[:, 0]

    win_p_full = np.zeros(len(df))
    is_cont = df['_is_contender'].values
    win_p_full[is_cont] = win_p_cont

    # Renormalize per race
    df['_mc_win_p'] = win_p_full
    sum_per_race = df.groupby('competition_id')['_mc_win_p'].transform('sum').values
    sum_per_race = np.where(sum_per_race > 0, sum_per_race, 1.0)
    return win_p_full / sum_per_race


def _lambdarank_win_p(test: pd.DataFrame, lr_pred) -> np.ndarray:
    return lr_pred.predict_win_probabilities(test).values


# ---------------------------------------------------------------------------
# Metric computation (mirrors LambdaRankProbabilityPredictor.evaluate)
# ---------------------------------------------------------------------------

def _compute_metrics(test: pd.DataFrame, win_p: np.ndarray) -> Dict[str, float]:
    """Winner capture, podium capture (top-3 by win_p), winner NLL, cal ratio, ECE."""
    df = pd.DataFrame({
        'comp_id': test['competition_id'].values,
        'p': win_p,
        'place_bucket': test['place_bucket'].values,
    })
    df['is_winner'] = (df['place_bucket'] == 0).astype(float)
    df['is_podium'] = (df['place_bucket'] <= 1).astype(float)

    winner_hits = 0
    podium_overlap_sum = 0.0
    n_races = 0
    winner_ps: List[float] = []

    for _, g in df.groupby('comp_id', sort=False):
        if (g['place_bucket'] == 0).sum() == 0:
            continue
        n_races += 1

        idx_max = g['p'].idxmax()
        if g.loc[idx_max, 'place_bucket'] == 0:
            winner_hits += 1

        top3 = g.nlargest(3, 'p')
        actual_podium_count = int((g['place_bucket'] <= 1).sum())
        podium_in_top3 = int((top3['place_bucket'] <= 1).sum())
        if actual_podium_count > 0:
            podium_overlap_sum += podium_in_top3 / min(3, actual_podium_count)

        actual_winner = g[g['place_bucket'] == 0].iloc[0]
        winner_ps.append(float(actual_winner['p']))

    winner_capture = winner_hits / max(n_races, 1)
    podium_capture = podium_overlap_sum / max(n_races, 1)

    win_log_loss = (
        float(-np.mean(np.log(np.asarray(winner_ps) + 1e-12)))
        if winner_ps else float('nan')
    )

    mean_predicted = float(df['p'].mean())
    actual_freq = float(df['is_winner'].mean())
    win_cal_ratio = (
        mean_predicted / actual_freq if actual_freq > 0 else float('nan')
    )

    n_bins = 10
    bin_edges = np.linspace(0, 1, n_bins + 1)
    p = df['p'].values
    y = df['is_winner'].values
    ece = 0.0
    n = len(p)
    for i in range(n_bins):
        mask = (p > bin_edges[i]) & (p <= bin_edges[i + 1])
        if mask.sum() >= 10:
            ece += (mask.sum() / n) * abs(p[mask].mean() - y[mask].mean())

    return {
        'winner_capture': float(winner_capture),
        'podium_capture': float(podium_capture),
        'win_log_loss': win_log_loss,
        'win_cal_ratio': float(win_cal_ratio),
        'win_ece': float(ece),
        'n_races': int(n_races),
    }


def _correlation_diagnostics(
    test: pd.DataFrame, mc_p: np.ndarray, lr_p: np.ndarray
) -> Dict[str, float]:
    """Correlation between heads — pooled across all rider rows and within-race."""
    pearson_pooled, _ = pearsonr(mc_p, lr_p)
    spearman_pooled, _ = spearmanr(mc_p, lr_p)

    # Within-race rank correlation: for each race, Spearman between mc and lr.
    df = pd.DataFrame({
        'comp_id': test['competition_id'].values,
        'mc': mc_p,
        'lr': lr_p,
    })
    rho_per_race: List[float] = []
    for _, g in df.groupby('comp_id', sort=False):
        if len(g) >= 5:
            rho, _ = spearmanr(g['mc'].values, g['lr'].values)
            if rho is not None and not np.isnan(rho):
                rho_per_race.append(float(rho))

    return {
        'pearson_pooled': float(pearson_pooled),
        'spearman_pooled': float(spearman_pooled),
        'spearman_within_race_mean': (
            float(np.mean(rho_per_race)) if rho_per_race else float('nan')
        ),
        'spearman_within_race_std': (
            float(np.std(rho_per_race)) if rho_per_race else float('nan')
        ),
        'n_races_for_within': len(rho_per_race),
    }


def _coverage_diagnostics(
    test: pd.DataFrame,
    bucket_pred,
    top_n: int = CONTENDER_TOP_N,
) -> Dict[str, float]:
    """% of races where the actual winner is in the bucket-regression top-N filter.

    This is the upper bound for multiclass winner capture — if the winner is
    filtered out, multiclass cannot recover them.
    """
    expected = bucket_pred.predict_continuous(test)
    df = test.copy()
    df['classifier_expected_bucket'] = expected
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()

    n_races = 0
    winner_in_topN = 0
    for _, g in df.groupby('competition_id', sort=False):
        if (g['place_bucket'] == 0).sum() == 0:
            continue
        n_races += 1
        winner_row = g[g['place_bucket'] == 0].iloc[0]
        if winner_row['_rank'] <= top_n:
            winner_in_topN += 1

    return {
        'bucket_topN_winner_coverage': (
            winner_in_topN / n_races if n_races else float('nan')
        ),
        'top_n': top_n,
        'n_races': n_races,
    }


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(df: pd.DataFrame, fold: Dict[str, str]) -> Dict[str, Any]:
    train, val, test = _slice_fold(df, fold)
    print(
        f"  Train: {len(train):,} rows ({train['competition_id'].nunique():,} races, "
        f"{train['competition_date'].min().date()} to {train['competition_date'].max().date()})"
    )
    print(f"  Val:   {len(val):,} rows ({val['competition_id'].nunique():,} races)")
    print(
        f"  Test:  {len(test):,} rows ({test['competition_id'].nunique():,} races, "
        f"year {fold['label']})"
    )

    if len(test) == 0:
        return {'fold_label': fold['label'], 'skipped': True}

    print("  Training multiclass cascade (bucket + OOF + contender)...")
    bucket_pred, contender_pred, mc_info = _train_multiclass(train, val, fold['label'])

    print("  Training LambdaRank head + calibrating temperature...")
    lr_pred, lr_info = _train_lambdarank(train, val)

    print("  Computing test predictions...")
    mc_p = _multiclass_win_p_full(test, bucket_pred, contender_pred)
    lr_p = _lambdarank_win_p(test, lr_pred)

    print("  Diagnostics...")
    cor = _correlation_diagnostics(test, mc_p, lr_p)
    cov = _coverage_diagnostics(test, bucket_pred)
    print(
        f"    Bucket top-15 winner coverage: {cov['bucket_topN_winner_coverage']:.4f} "
        f"(ceiling for multiclass winner capture)"
    )
    print(
        f"    mc vs lr Spearman (pooled): {cor['spearman_pooled']:.4f}  "
        f"within-race: {cor['spearman_within_race_mean']:.4f} ± {cor['spearman_within_race_std']:.4f}"
    )

    print("  Sweeping blend weights...")
    sweep: List[Dict[str, Any]] = []
    for w in W_GRID:
        blended = w * mc_p + (1.0 - w) * lr_p
        m = _compute_metrics(test, blended)
        m['w'] = w
        sweep.append(m)

    print(f"\n  Fold {fold['label']} per-w results:")
    print(
        f"    {'w':>5s}  {'winner':>8s}  {'podium':>8s}  {'log_loss':>9s}  "
        f"{'cal':>7s}  {'ECE':>8s}"
    )
    for s in sweep:
        print(
            f"    {s['w']:>5.1f}  {s['winner_capture']:>8.4f}  "
            f"{s['podium_capture']:>8.4f}  {s['win_log_loss']:>9.4f}  "
            f"{s['win_cal_ratio']:>7.4f}  {s['win_ece']:>8.4f}"
        )

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'multiclass_info': mc_info,
        'lambdarank_info': {
            'best_iteration': lr_info.get('best_iteration'),
            'calibrated_temperature': float(lr_info.get('calibrated_temperature', np.nan)),
        },
        'mc_win_p_stats': {
            'mean': float(mc_p.mean()),
            'std': float(mc_p.std()),
            'nonzero_frac': float((mc_p > 0).mean()),
        },
        'lr_win_p_stats': {
            'mean': float(lr_p.mean()),
            'std': float(lr_p.std()),
        },
        'correlation': cor,
        'coverage': cov,
        'sweep': sweep,
    }


# ---------------------------------------------------------------------------
# Aggregation + reporting
# ---------------------------------------------------------------------------

def aggregate_sweeps(fold_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    usable = [fr for fr in fold_results if not fr.get('skipped')]
    keys = ('winner_capture', 'podium_capture', 'win_log_loss', 'win_cal_ratio', 'win_ece')

    agg: Dict[str, Dict[str, Any]] = {}
    for w_idx, w_val in enumerate(W_GRID):
        per_fold = [fr['sweep'][w_idx] for fr in usable]
        per_w: Dict[str, Any] = {'w': w_val}
        for k in keys:
            vals = [m[k] for m in per_fold]
            per_w[k] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
                'per_fold': [float(v) for v in vals],
            }
        agg[f'w={w_val:.1f}'] = per_w
    return agg


def find_best_w(agg: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    metrics = [
        ('winner_capture', 'higher'),
        ('podium_capture', 'higher'),
        ('win_log_loss', 'lower'),
        ('win_ece', 'lower'),
    ]
    best: Dict[str, Dict[str, Any]] = {}
    cal_target = 1.0  # win_cal_ratio: closest to 1.0 is best
    for metric, direction in metrics:
        candidates = [
            (agg[k]['w'], agg[k][metric]['mean'])
            for k in agg
        ]
        if direction == 'higher':
            best_w, best_val = max(candidates, key=lambda x: x[1])
        else:
            best_w, best_val = min(candidates, key=lambda x: x[1])
        best[metric] = {'best_w': float(best_w), 'best_value': float(best_val)}

    cal_candidates = [
        (agg[k]['w'], agg[k]['win_cal_ratio']['mean'])
        for k in agg
    ]
    best_w_cal, best_cal_val = min(
        cal_candidates, key=lambda x: abs(x[1] - cal_target)
    )
    best['win_cal_ratio'] = {
        'best_w': float(best_w_cal),
        'best_value': float(best_cal_val),
        'distance_to_1': float(abs(best_cal_val - 1.0)),
    }
    return best


def print_summary(
    agg: Dict[str, Dict[str, Any]],
    best: Dict[str, Dict[str, Any]],
):
    print("\n" + "=" * 100)
    print("SUMMARY — blend sweep (mean ± std across 3 folds)")
    print("=" * 100)
    print(
        f"\n  {'w':>5s}  {'winner_capt':>15s}  {'podium_capt':>15s}  "
        f"{'log_loss':>15s}  {'cal_ratio':>15s}  {'ECE':>15s}"
    )
    print("  " + "-" * 95)
    for w_val in W_GRID:
        key = f'w={w_val:.1f}'
        m = agg[key]
        print(
            f"  {w_val:>5.1f}  "
            f"{m['winner_capture']['mean']:>7.4f}±{m['winner_capture']['std']:>6.4f}  "
            f"{m['podium_capture']['mean']:>7.4f}±{m['podium_capture']['std']:>6.4f}  "
            f"{m['win_log_loss']['mean']:>7.4f}±{m['win_log_loss']['std']:>6.4f}  "
            f"{m['win_cal_ratio']['mean']:>7.4f}±{m['win_cal_ratio']['std']:>6.4f}  "
            f"{m['win_ece']['mean']:>7.4f}±{m['win_ece']['std']:>6.4f}"
        )

    print("\n  ENDPOINTS (sanity check):")
    p0 = agg['w=0.0']
    p1 = agg['w=1.0']
    print(
        f"    w=0.0 (pure LambdaRank): winner={p0['winner_capture']['mean']:.4f}  "
        f"podium={p0['podium_capture']['mean']:.4f}  log_loss={p0['win_log_loss']['mean']:.4f}  "
        f"cal={p0['win_cal_ratio']['mean']:.4f}  ECE={p0['win_ece']['mean']:.4f}"
    )
    print(
        f"    w=1.0 (pure multiclass): winner={p1['winner_capture']['mean']:.4f}  "
        f"podium={p1['podium_capture']['mean']:.4f}  log_loss={p1['win_log_loss']['mean']:.4f}  "
        f"cal={p1['win_cal_ratio']['mean']:.4f}  ECE={p1['win_ece']['mean']:.4f}"
    )

    print("\n  BEST w PER METRIC:")
    for metric, info in best.items():
        if metric == 'win_cal_ratio':
            print(
                f"    {metric:<18s}  best_w={info['best_w']:.1f}  "
                f"value={info['best_value']:.4f}  |Δ from 1.0|={info['distance_to_1']:.4f}"
            )
        else:
            print(
                f"    {metric:<18s}  best_w={info['best_w']:.1f}  "
                f"value={info['best_value']:.4f}"
            )

    print("\n  ΔS vs endpoints at the best winner-capture w:")
    bw = best['winner_capture']['best_w']
    bw_key = f'w={bw:.1f}'
    bm = agg[bw_key]
    for metric in ('winner_capture', 'podium_capture', 'win_log_loss', 'win_cal_ratio', 'win_ece'):
        v0 = agg['w=0.0'][metric]['mean']
        v1 = agg['w=1.0'][metric]['mean']
        vb = bm[metric]['mean']
        d_lr = vb - v0
        d_mc = vb - v1
        print(
            f"    {metric:<18s}  blend({bw:.1f})={vb:.4f}  "
            f"vs LR={v0:.4f} (Δ={d_lr:+.4f})  "
            f"vs MC={v1:.4f} (Δ={d_mc:+.4f})"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("BLEND CV — multiclass × LambdaRank")
    print("=" * 70)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}")

    df = _load_full_df()
    print(
        f"\nLoaded {len(df):,} samples, {df['competition_id'].nunique():,} competitions, "
        f"{df['competition_date'].min().date()} to {df['competition_date'].max().date()}"
    )

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}")
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']})")
        print(f"{'─' * 60}")
        fold_results.append(run_fold(df, fold))

    agg = aggregate_sweeps(fold_results)
    best = find_best_w(agg)

    print_summary(agg, best)

    ended = datetime.now()
    duration = (ended - started).total_seconds()
    out: Dict[str, Any] = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': duration,
        'config': {
            'start_date': START_DATE,
            'folds': FOLDS,
            'multiclass': MULTICLASS_CONFIG,
            'lambdarank': LAMBDARANK_CONFIG,
            'w_grid': W_GRID,
        },
        'data_stats': {
            'total_rows': int(len(df)),
            'total_competitions': int(df['competition_id'].nunique()),
            'date_min': str(df['competition_date'].min().date()),
            'date_max': str(df['competition_date'].max().date()),
        },
        'fold_results': fold_results,
        'aggregated': agg,
        'best_w_per_metric': best,
    }

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"blend_multiclass_lambdarank_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}")
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)")


if __name__ == '__main__':
    main()
