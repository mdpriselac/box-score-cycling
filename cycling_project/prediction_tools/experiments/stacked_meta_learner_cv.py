"""
Stacked meta-learner CV — augmented contender with OOF time-gap + LambdaRank features.

Builds a "contender++" by adding two OOF features to the existing
multiclass contender (top-15, LR=0.01, OOF, 5-class, gradient features):

- `oof_time_gap_pred`: predicted seconds behind winner from a TimeGapPredictor
- `oof_lambdarank_win_p`: per-race calibrated softmax win probability from a
  full-field LambdaRankProbabilityPredictor

Each new feature is generated via 5-fold temporal CV on the training data
to avoid leakage. At val/test inference, main models trained on train
(with val for early stopping) supply the predictions.

Tests whether the orthogonal signal in time-gap and LambdaRank (within-race
Spearman ~0.58 vs multiclass per the linear-blend experiment) gives the
contender additional discrimination that simple linear blending couldn't
extract.

Compares baseline contender (no new features) to meta contender on the
same 3-fold CV protocol used by ExperimentRunner / multiclass_start_date_cv:

    train→2021 / val→2022 / test→2023+
    train→2022 / val→2023 / test→2024+
    train→2023 / val→2024 / test→2025+

Test is uncapped (everything after val_end_date), matching ExperimentRunner.
This makes the baseline numbers directly comparable to the historic
production baseline (~24.31% / 44.36% / 1.78 from experiment_log.md).

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.stacked_meta_learner_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline, DataConfig
from cycling_project.prediction_tools.evaluation import Top4ProbabilityEvaluator
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)
from cycling_project.prediction_tools.time_gap_predictor import (
    TimeGapPredictor,
    TimeGapPredictorConfig,
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
N_OOF_FOLDS = 5

# Contender-stage config (production-aligned, matches multiclass_start_date_cv)
CONTENDER_CONFIG = {
    'n_estimators': 500,
    'early_stopping': 50,
    'contender_top_n': 15,
    'contender_learning_rate': 0.01,
    'contender_use_oof': True,
    'contender_n_classes': 5,
    'include_gradient_features': True,
}

# OOF base-model configs (smaller than main to keep runtime bounded)
TIME_GAP_OOF_CONFIG = {'n_estimators': 300, 'early_stopping_rounds': 30}
LAMBDARANK_OOF_CONFIG = {
    'n_estimators': 500,
    'early_stopping_rounds': 100,
    'learning_rate': 0.05,
}

# Main base-model configs (used for val/test inference)
TIME_GAP_MAIN_CONFIG = {'n_estimators': 500, 'early_stopping_rounds': 50}
LAMBDARANK_MAIN_CONFIG = {
    'n_estimators': 2000,
    'early_stopping_rounds': 300,
    'learning_rate': 0.05,
}

META_FEATURE_COLS = ['oof_time_gap_pred', 'oof_lambdarank_win_p']


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
    """ExperimentRunner-style slicing: test is uncapped (everything after val_end)."""
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])

    train = df[df['competition_date'] <= train_end].copy()
    val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
    test = df[df['competition_date'] > val_end].copy()
    return train, val, test


# ---------------------------------------------------------------------------
# OOF generators
# ---------------------------------------------------------------------------

def _temporal_fold_mask(dates: pd.Series, fold_idx: int, n_folds: int) -> pd.Series:
    quantiles = [dates.quantile(i / n_folds) for i in range(1, n_folds)]
    if fold_idx == 0:
        return dates <= quantiles[0]
    if fold_idx == n_folds - 1:
        return dates > quantiles[-1]
    return (dates > quantiles[fold_idx - 1]) & (dates <= quantiles[fold_idx])


def _generate_oof_time_gap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    n_folds: int = N_OOF_FOLDS,
) -> np.ndarray:
    """5-fold temporal OOF on train_df. Returns predicted seconds, aligned to row order."""
    dates = pd.to_datetime(train_df['competition_date'])
    oof = np.full(len(train_df), np.nan)

    for k in range(n_folds):
        mask = _temporal_fold_mask(dates, k, n_folds)
        fold_train = train_df[~mask]
        fold_predict = train_df[mask]
        if len(fold_predict) == 0:
            continue

        cfg = TimeGapPredictorConfig(**TIME_GAP_OOF_CONFIG)
        model = TimeGapPredictor(cfg)
        model.train(fold_train, val_df, verbose=False)
        preds = model.predict(fold_predict)
        oof[mask.values] = preds
        print(
            f"      tg OOF fold {k + 1}/{n_folds}: "
            f"trained on {len(fold_train):,}, predicted {len(fold_predict):,}",
            flush=True,
        )

    nan_n = int(np.isnan(oof).sum())
    if nan_n:
        print(f"      [warn] {nan_n} time_gap OOF rows missing; filling with median", flush=True)
        oof[np.isnan(oof)] = float(np.nanmedian(oof))
    return oof


def _generate_oof_lambdarank_winp(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    n_folds: int = N_OOF_FOLDS,
) -> np.ndarray:
    """5-fold temporal OOF on train_df. Returns calibrated softmax win_p."""
    dates = pd.to_datetime(train_df['competition_date'])
    oof = np.full(len(train_df), np.nan)

    for k in range(n_folds):
        mask = _temporal_fold_mask(dates, k, n_folds)
        fold_train = train_df[~mask]
        fold_predict = train_df[mask]
        if len(fold_predict) == 0:
            continue

        cfg = LambdaRankPredictorConfig(
            n_estimators=LAMBDARANK_OOF_CONFIG['n_estimators'],
            early_stopping_rounds=LAMBDARANK_OOF_CONFIG['early_stopping_rounds'],
        )
        cfg.lgb_params['learning_rate'] = LAMBDARANK_OOF_CONFIG['learning_rate']

        model = LambdaRankProbabilityPredictor(cfg)
        model.train(fold_train, val_df, verbose=False)
        T = model.calibrate_temperature(val_df)
        win_p = model.predict_win_probabilities(fold_predict).values
        oof[mask.values] = win_p
        print(
            f"      lr OOF fold {k + 1}/{n_folds}: trained on {len(fold_train):,}, "
            f"predicted {len(fold_predict):,}, T={T:.3f}",
            flush=True,
        )

    nan_n = int(np.isnan(oof).sum())
    if nan_n:
        print(f"      [warn] {nan_n} LR OOF rows missing; filling with mean", flush=True)
        oof[np.isnan(oof)] = float(np.nanmean(oof))
    return oof


# ---------------------------------------------------------------------------
# Main base models (for val + test inference)
# ---------------------------------------------------------------------------

def _train_main_time_gap(
    train_df: pd.DataFrame, val_df: pd.DataFrame
) -> TimeGapPredictor:
    cfg = TimeGapPredictorConfig(**TIME_GAP_MAIN_CONFIG)
    model = TimeGapPredictor(cfg)
    model.train(train_df, val_df, verbose=False)
    return model


def _train_main_lambdarank(
    train_df: pd.DataFrame, val_df: pd.DataFrame
) -> LambdaRankProbabilityPredictor:
    cfg = LambdaRankPredictorConfig(
        n_estimators=LAMBDARANK_MAIN_CONFIG['n_estimators'],
        early_stopping_rounds=LAMBDARANK_MAIN_CONFIG['early_stopping_rounds'],
    )
    cfg.lgb_params['learning_rate'] = LAMBDARANK_MAIN_CONFIG['learning_rate']
    model = LambdaRankProbabilityPredictor(cfg)
    model.train(train_df, val_df, verbose=False)
    model.calibrate_temperature(val_df)
    return model


# ---------------------------------------------------------------------------
# Contender training + eval
# ---------------------------------------------------------------------------

def _train_bucket_and_contender(
    train_df: pd.DataFrame, val_df: pd.DataFrame, fold_label: str
) -> Tuple[Any, Any, Dict[str, Any]]:
    cfg = TrainingConfig(
        start_date=START_DATE,
        train_end_date=train_df['competition_date'].max().strftime('%Y-%m-%d'),
        val_end_date=val_df['competition_date'].max().strftime('%Y-%m-%d'),
        bucket_n_estimators=CONTENDER_CONFIG['n_estimators'],
        bucket_early_stopping=CONTENDER_CONFIG['early_stopping'],
        probability_n_estimators=CONTENDER_CONFIG['n_estimators'],
        probability_early_stopping=CONTENDER_CONFIG['early_stopping'],
        time_gap_n_estimators=CONTENDER_CONFIG['n_estimators'],
        time_gap_early_stopping=CONTENDER_CONFIG['early_stopping'],
        contender_top_n=CONTENDER_CONFIG['contender_top_n'],
        contender_learning_rate=CONTENDER_CONFIG['contender_learning_rate'],
        contender_use_oof=CONTENDER_CONFIG['contender_use_oof'],
        contender_n_classes=CONTENDER_CONFIG['contender_n_classes'],
        include_gradient_features=CONTENDER_CONFIG['include_gradient_features'],
        fold_label=fold_label,
        train_time_gap=False,
        train_probability=False,
        train_calibrated_probability=False,
        train_contender_probability=True,
        verbose=False,
    )
    trainer = ModelTrainer(cfg)
    bucket_pred, bucket_info = trainer.train_bucket_predictor(train_df, val_df)
    contender_pred, contender_info = trainer.train_contender_predictor(
        train_df, val_df, bucket_pred
    )
    info = {
        'bucket_best_iteration': bucket_info.get('best_iteration'),
        'contender_best_iteration': contender_info.get('best_iteration'),
    }
    return bucket_pred, contender_pred, info


def _evaluate_on_test(
    test_df: pd.DataFrame, bucket_pred, contender_pred, top_n: int = 15
) -> Tuple[Dict[str, float], int]:
    """Mirror ExperimentRunner's `probability_contender_top4` evaluation."""
    expected = bucket_pred.predict_continuous(test_df)
    df = test_df.copy()
    df['classifier_expected_bucket'] = expected
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
    cont_df = df[df['_rank'] <= top_n].drop(columns=['_rank'])

    if len(cont_df) == 0:
        return {}, 0

    y_proba = contender_pred.predict_proba(cont_df)
    y_true = cont_df['place_bucket'].values

    n_classes = contender_pred.config.lgb_params.get('num_class', 8)
    if n_classes < 8:
        y_true = np.clip(y_true, 0, n_classes - 1)

    metrics = Top4ProbabilityEvaluator.evaluate(
        y_true, y_proba, competition_ids=cont_df['competition_id'].values
    )
    return metrics, len(cont_df)


def _capture_feature_importance(contender_pred) -> Dict[str, float]:
    try:
        imp_df = contender_pred.get_feature_importance(importance_type='gain')
        return dict(zip(imp_df['feature'], imp_df['importance'].astype(float)))
    except Exception as exc:  # pragma: no cover
        print(f"    [warn] feature importance unavailable: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(df: pd.DataFrame, fold: Dict[str, str]) -> Dict[str, Any]:
    train, val, test = _slice_fold(df, fold)

    print(
        f"  Train: {len(train):,} rows ({train['competition_id'].nunique():,} races, "
        f"{train['competition_date'].min().date()} to {train['competition_date'].max().date()})",
        flush=True,
    )
    print(
        f"  Val:   {len(val):,} rows ({val['competition_id'].nunique():,} races)",
        flush=True,
    )
    print(
        f"  Test:  {len(test):,} rows ({test['competition_id'].nunique():,} races, "
        f"{test['competition_date'].min().date()}+)",
        flush=True,
    )

    if len(test) == 0:
        return {'fold_label': fold['label'], 'skipped': True}

    # ---------------------------------------------------------------
    # Step 1: OOF features on train
    # ---------------------------------------------------------------
    print("  Generating OOF time_gap predictions on train (5 sub-folds)...", flush=True)
    oof_tg = _generate_oof_time_gap(train, val, N_OOF_FOLDS)

    print("  Generating OOF LambdaRank predictions on train (5 sub-folds)...", flush=True)
    oof_lr = _generate_oof_lambdarank_winp(train, val, N_OOF_FOLDS)

    # ---------------------------------------------------------------
    # Step 2: Main base models (for val + test inference)
    # ---------------------------------------------------------------
    print("  Training main time_gap predictor...", flush=True)
    main_tg = _train_main_time_gap(train, val)

    print("  Training main LambdaRank predictor + calibrating temperature...", flush=True)
    main_lr = _train_main_lambdarank(train, val)
    print(f"    LR temperature: {main_lr.config.temperature:.3f}", flush=True)

    # ---------------------------------------------------------------
    # Step 3: Build augmented frames
    # ---------------------------------------------------------------
    train_meta = train.copy()
    val_meta = val.copy()
    test_meta = test.copy()

    train_meta['oof_time_gap_pred'] = oof_tg
    train_meta['oof_lambdarank_win_p'] = oof_lr

    val_meta['oof_time_gap_pred'] = main_tg.predict(val_meta)
    val_meta['oof_lambdarank_win_p'] = main_lr.predict_win_probabilities(val_meta).values

    test_meta['oof_time_gap_pred'] = main_tg.predict(test_meta)
    test_meta['oof_lambdarank_win_p'] = main_lr.predict_win_probabilities(test_meta).values

    print(
        f"    train_meta tg pred: mean={oof_tg.mean():.1f}s std={oof_tg.std():.1f}s  "
        f"lr_p: mean={oof_lr.mean():.5f} std={oof_lr.std():.5f}",
        flush=True,
    )

    # ---------------------------------------------------------------
    # Step 4: Train baseline contender (no meta features)
    # ---------------------------------------------------------------
    print("  Training BASELINE contender (126 features)...", flush=True)
    bucket_b, cont_b, info_b = _train_bucket_and_contender(train, val, fold['label'])
    metrics_b, n_cont_b = _evaluate_on_test(test, bucket_b, cont_b, top_n=15)
    fi_b = _capture_feature_importance(cont_b)
    print(
        f"    baseline winner={metrics_b.get('race_winner_capture_rate', float('nan')):.4f}  "
        f"podium={metrics_b.get('race_podium_capture_rate', float('nan')):.4f}  "
        f"log_loss={metrics_b.get('top4_log_loss', float('nan')):.4f}",
        flush=True,
    )

    # ---------------------------------------------------------------
    # Step 5: Train meta contender (128 features)
    # ---------------------------------------------------------------
    print("  Training META contender (128 features = 126 + tg_pred + lr_winp)...", flush=True)
    bucket_m, cont_m, info_m = _train_bucket_and_contender(train_meta, val_meta, fold['label'])
    metrics_m, n_cont_m = _evaluate_on_test(test_meta, bucket_m, cont_m, top_n=15)
    fi_m = _capture_feature_importance(cont_m)
    print(
        f"    meta     winner={metrics_m.get('race_winner_capture_rate', float('nan')):.4f}  "
        f"podium={metrics_m.get('race_podium_capture_rate', float('nan')):.4f}  "
        f"log_loss={metrics_m.get('top4_log_loss', float('nan')):.4f}",
        flush=True,
    )

    # Print delta + meta-feature ranks
    delta_winner = metrics_m.get('race_winner_capture_rate', np.nan) - metrics_b.get(
        'race_winner_capture_rate', np.nan
    )
    delta_podium = metrics_m.get('race_podium_capture_rate', np.nan) - metrics_b.get(
        'race_podium_capture_rate', np.nan
    )
    delta_log = metrics_m.get('top4_log_loss', np.nan) - metrics_b.get(
        'top4_log_loss', np.nan
    )
    print(
        f"    Δ meta-baseline: winner={delta_winner:+.4f}  "
        f"podium={delta_podium:+.4f}  log_loss={delta_log:+.4f}",
        flush=True,
    )

    if fi_m:
        sorted_fi = sorted(fi_m.items(), key=lambda x: x[1], reverse=True)
        rank_tg = next(
            (i for i, (k, _) in enumerate(sorted_fi) if k == 'oof_time_gap_pred'), None
        )
        rank_lr = next(
            (i for i, (k, _) in enumerate(sorted_fi) if k == 'oof_lambdarank_win_p'), None
        )
        n_total = len(sorted_fi)
        print(
            f"    Meta feature ranks: oof_time_gap_pred=#{(rank_tg or 0) + 1 if rank_tg is not None else '—'}  "
            f"oof_lambdarank_win_p=#{(rank_lr or 0) + 1 if rank_lr is not None else '—'} "
            f"(of {n_total} features)",
            flush=True,
        )

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'main_lr_temperature': float(main_lr.config.temperature),
        'baseline': {
            'metrics': metrics_b,
            'n_contenders_eval': n_cont_b,
            'training_info': info_b,
            'feature_importance': fi_b,
        },
        'meta': {
            'metrics': metrics_m,
            'n_contenders_eval': n_cont_m,
            'training_info': info_m,
            'feature_importance': fi_m,
        },
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

PRIMARY_METRICS = [
    'race_winner_capture_rate',
    'race_podium_capture_rate',
    'top4_log_loss',
    'top4_brier',
    'win_cal_ratio',
    'podium_cal_ratio',
]


def aggregate(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [fr for fr in fold_results if not fr.get('skipped')]

    out: Dict[str, Any] = {'baseline': {}, 'meta': {}, 'delta': {}}
    for variant in ('baseline', 'meta'):
        for k in PRIMARY_METRICS:
            vals = [
                fr[variant]['metrics'].get(k)
                for fr in usable
                if k in fr[variant].get('metrics', {})
            ]
            vals = [
                v for v in vals
                if v is not None and not (isinstance(v, float) and np.isnan(v))
            ]
            if not vals:
                continue
            out[variant][k] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
                'per_fold': [float(v) for v in vals],
            }

    for k in PRIMARY_METRICS:
        if k in out['baseline'] and k in out['meta']:
            paired_deltas = [
                fr['meta']['metrics'][k] - fr['baseline']['metrics'][k]
                for fr in usable
                if k in fr['meta']['metrics'] and k in fr['baseline']['metrics']
            ]
            if paired_deltas:
                out['delta'][k] = {
                    'mean': float(np.mean(paired_deltas)),
                    'std': float(np.std(paired_deltas)),
                    'per_fold': [float(d) for d in paired_deltas],
                }
    return out


def aggregate_meta_feature_importance(
    fold_results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, float]]:
    """Average rank + gain of meta features across folds."""
    out: Dict[str, Dict[str, float]] = {}
    for feat in META_FEATURE_COLS:
        ranks: List[int] = []
        gains: List[float] = []
        n_features_seen: List[int] = []
        for fr in fold_results:
            if fr.get('skipped'):
                continue
            fi = fr['meta'].get('feature_importance') or {}
            if feat not in fi:
                continue
            sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)
            rank = next(i for i, (k, _) in enumerate(sorted_fi) if k == feat)
            ranks.append(rank + 1)
            gains.append(float(fi[feat]))
            n_features_seen.append(len(sorted_fi))
        if ranks:
            out[feat] = {
                'mean_rank': float(np.mean(ranks)),
                'mean_gain': float(np.mean(gains)),
                'min_rank': int(min(ranks)),
                'max_rank': int(max(ranks)),
                'mean_n_features': float(np.mean(n_features_seen)),
            }
    return out


def print_summary(agg: Dict[str, Any], feat_summary: Dict[str, Dict[str, float]]):
    print("\n" + "=" * 90)
    print("SUMMARY — meta-learner vs baseline contender (mean ± std across folds)")
    print("=" * 90)
    print(
        f"\n  {'Metric':<32s}  {'Baseline':>16s}  {'Meta':>16s}  {'Δ (meta-base)':>17s}"
    )
    print("  " + "-" * 86)
    for k in PRIMARY_METRICS:
        b = agg['baseline'].get(k)
        m = agg['meta'].get(k)
        d = agg['delta'].get(k)
        if not (b and m and d):
            continue
        print(
            f"  {k:<32s}  "
            f"{b['mean']:>7.4f}±{b['std']:>6.4f}  "
            f"{m['mean']:>7.4f}±{m['std']:>6.4f}  "
            f"{d['mean']:>+8.4f}±{d['std']:>6.4f}"
        )

    print("\n  PER-FOLD DELTAS:")
    for k in PRIMARY_METRICS:
        d = agg['delta'].get(k)
        if not d:
            continue
        per = '  '.join(f"{v:+.4f}" for v in d['per_fold'])
        print(f"    {k:<32s}  {per}")

    print("\n  META FEATURE IMPORTANCE (across folds):")
    if feat_summary:
        for feat, info in feat_summary.items():
            print(
                f"    {feat:<28s}  rank #{info['mean_rank']:>5.1f} "
                f"(min #{info['min_rank']}, max #{info['max_rank']})  "
                f"gain={info['mean_gain']:>8.0f}  / {info['mean_n_features']:.0f} features"
            )
    else:
        print("    (not available)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70, flush=True)
    print("STACKED META-LEARNER CV — augmented contender (+ time_gap OOF + LR OOF)")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df = _load_full_df()
    print(
        f"\nLoaded {len(df):,} samples, {df['competition_id'].nunique():,} competitions, "
        f"{df['competition_date'].min().date()} to {df['competition_date'].max().date()}",
        flush=True,
    )

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)", flush=True)
        print(f"{'─' * 60}", flush=True)
        fold_results.append(run_fold(df, fold))

    agg = aggregate(fold_results)
    feat_summary = aggregate_meta_feature_importance(fold_results)
    print_summary(agg, feat_summary)

    ended = datetime.now()
    duration = (ended - started).total_seconds()

    out: Dict[str, Any] = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': duration,
        'config': {
            'start_date': START_DATE,
            'folds': FOLDS,
            'n_oof_folds': N_OOF_FOLDS,
            'contender': CONTENDER_CONFIG,
            'time_gap_oof': TIME_GAP_OOF_CONFIG,
            'lambdarank_oof': LAMBDARANK_OOF_CONFIG,
            'time_gap_main': TIME_GAP_MAIN_CONFIG,
            'lambdarank_main': LAMBDARANK_MAIN_CONFIG,
            'meta_feature_cols': META_FEATURE_COLS,
        },
        'data_stats': {
            'total_rows': int(len(df)),
            'total_competitions': int(df['competition_id'].nunique()),
            'date_min': str(df['competition_date'].min().date()),
            'date_max': str(df['competition_date'].max().date()),
        },
        'fold_results': fold_results,
        'aggregated': agg,
        'meta_feature_importance_summary': feat_summary,
    }

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"stacked_meta_learner_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)", flush=True)


if __name__ == '__main__':
    main()
