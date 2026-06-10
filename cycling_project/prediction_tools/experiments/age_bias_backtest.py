"""
Age-band residual backtest — form-features work, step 0.

Quantifies the suspected veteran-overestimation bias before any form-feature
changes, so later steps have a target metric. Trains the production-config
heads on the standard 5-fold expanding window (start 2016) and measures
predicted-vs-actual residuals by rider age band on held-out test years.

Unlike capture-rate experiments, each fold's test set is restricted to its
label calendar year (2021..2025), so the pooled records cover every test row
exactly once, each predicted by a model trained through label-2. Standard
uncapped-test metrics are also computed per fold for comparability with
prior experiment baselines.

Measurements (pooled 2021-2025 + per fold):
  1. LambdaRank full-field win calibration by age band (sum win_p vs wins)
  2. Bucket-head optimism by age band (actual − expected bucket; + = model
     too optimistic), full field and predicted-top-15 subset
  3. Contender-cascade win/podium/top5/top15 calibration by age band
  4. Selection bias: share of predicted-top-15 slots vs share of actual
     top-15 finishes per band
  5. Form-conditional slices: riders with clearly-below-career recent form
     (form_delta >= +0.5, count >= 3) and clearly-above (<= -0.5), by age
  6. Continuous slopes: residual vs age (per year of age)

Outputs:
  experiments/age_bias_backtest_<ts>.json        — summary + tables
  experiments/age_bias_backtest_records_<ts>.csv.gz — per-rider records for
                                                    reuse in later form steps

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.age_bias_backtest
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
from cycling_project.prediction_tools.training import ModelTrainer, TrainingConfig
from cycling_project.webscrape_tools.logging_config import get_logger


logger = get_logger(__name__)


FOLDS = [
    {'train_end': '2019-12-31', 'val_end': '2020-12-31', 'label': '2021'},
    {'train_end': '2020-12-31', 'val_end': '2021-12-31', 'label': '2022'},
    {'train_end': '2021-12-31', 'val_end': '2022-12-31', 'label': '2023'},
    {'train_end': '2022-12-31', 'val_end': '2023-12-31', 'label': '2024'},
    {'train_end': '2023-12-31', 'val_end': '2024-12-31', 'label': '2025'},
]

START_DATE = '2016-01-01'
TOP_N = 15

# Production-aligned contender stage (matches stacked_meta_learner_cv_5fold)
CONTENDER_CONFIG = {
    'n_estimators': 500,
    'early_stopping': 50,
    'contender_top_n': TOP_N,
    'contender_learning_rate': 0.01,
    'contender_use_oof': True,
    'contender_n_classes': 5,
    'include_gradient_features': True,
}

LAMBDARANK_MAIN_CONFIG = {
    'n_estimators': 2000,
    'early_stopping_rounds': 300,
    'learning_rate': 0.05,
}

AGE_BINS = [0, 25, 30, 34, 37, 200]
AGE_LABELS = ['<25', '25-29', '30-33', '34-36', '37+']
COARSE_BINS = [0, 30, 34, 200]
COARSE_LABELS = ['<30', '30-33', '34+']


# ---------------------------------------------------------------------------
# Data + training (mirrors stacked_meta_learner_cv_5fold)
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
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns train, val, test_year (label calendar year), test_uncapped."""
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])
    label_year = int(fold['label'])

    train = df[df['competition_date'] <= train_end].copy()
    val = df[(df['competition_date'] > train_end) & (df['competition_date'] <= val_end)].copy()
    test_uncapped = df[df['competition_date'] > val_end].copy()
    test_year = test_uncapped[test_uncapped['competition_date'].dt.year == label_year].copy()
    return train, val, test_year, test_uncapped


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


def _train_lambdarank(
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
# Per-fold record collection
# ---------------------------------------------------------------------------

RECORD_ATTR_COLS = [
    'competition_id', 'rider_id', 'age', 'form_delta', 'form_recent_count',
    'form_recent_avg_bucket', 'form_recent_best_bucket', 'days_since_last_race',
    'place_bucket', 'race_category', 'competition_type',
]


def _collect_records(
    test_df: pd.DataFrame, bucket_pred, contender_pred, lr_pred, fold_label: str
) -> pd.DataFrame:
    """Per-rider predictions from all three heads on the fold's test year."""
    rec = test_df[RECORD_ATTR_COLS].copy()
    rec['fold_label'] = fold_label

    df = test_df.copy()
    df['classifier_expected_bucket'] = bucket_pred.predict_continuous(df)
    rec['expected_bucket'] = df['classifier_expected_bucket'].values

    rec['lr_win_p'] = lr_pred.predict_win_probabilities(df).values

    # Contender cascade on predicted top-15 per race
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
    top_mask = (df['_rank'] <= TOP_N).values
    rec['in_pred_top15'] = top_mask

    for col in ('c_win_p', 'c_podium_p', 'c_top5_p', 'c_top15_p'):
        rec[col] = np.nan

    cont_df = df[top_mask].drop(columns=['_rank'])
    if len(cont_df) > 0:
        proba = contender_pred.predict_proba(cont_df)
        rec.loc[top_mask, 'c_win_p'] = proba[:, 0]
        rec.loc[top_mask, 'c_podium_p'] = proba[:, :2].sum(axis=1)
        rec.loc[top_mask, 'c_top5_p'] = proba[:, :3].sum(axis=1)
        rec.loc[top_mask, 'c_top15_p'] = proba[:, :4].sum(axis=1)

    return rec


def _standard_metrics_uncapped(
    test_df: pd.DataFrame, bucket_pred, contender_pred
) -> Dict[str, float]:
    """Uncapped-test contender metrics, comparable to prior experiment JSONs."""
    df = test_df.copy()
    df['classifier_expected_bucket'] = bucket_pred.predict_continuous(df)
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
    cont_df = df[df['_rank'] <= TOP_N].drop(columns=['_rank'])
    if len(cont_df) == 0:
        return {}

    y_proba = contender_pred.predict_proba(cont_df)
    y_true = cont_df['place_bucket'].values
    n_classes = contender_pred.config.lgb_params.get('num_class', 8)
    if n_classes < 8:
        y_true = np.clip(y_true, 0, n_classes - 1)

    return Top4ProbabilityEvaluator.evaluate(
        y_true, y_proba, competition_ids=cont_df['competition_id'].values
    )


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def _add_bands(rec: pd.DataFrame) -> pd.DataFrame:
    rec = rec.copy()
    age = pd.to_numeric(rec['age'], errors='coerce')
    age = age.where(age > 0)
    rec['age_num'] = age
    rec['age_band'] = pd.cut(age, bins=AGE_BINS, labels=AGE_LABELS, right=False)
    rec['age_coarse'] = pd.cut(age, bins=COARSE_BINS, labels=COARSE_LABELS, right=False)
    rec['is_win'] = (rec['place_bucket'] == 0).astype(int)
    rec['is_podium'] = (rec['place_bucket'] <= 1).astype(int)
    rec['is_top5'] = (rec['place_bucket'] <= 2).astype(int)
    rec['is_top15'] = (rec['place_bucket'] <= 3).astype(int)
    # + = model predicted better (lower bucket) than reality = overestimation
    rec['bucket_optimism'] = rec['place_bucket'] - rec['expected_bucket']
    return rec


def _ratio(num: float, den: float) -> float:
    return float(num / den) if den > 0 else float('nan')


def _band_table(rec: pd.DataFrame, band_col: str = 'age_band') -> Dict[str, Dict]:
    """Core per-band calibration table across all three heads."""
    out = {}
    for band, g in rec.groupby(band_col, observed=True):
        cont = g[g['in_pred_top15']]
        row = {
            'n_rows': int(len(g)),
            'n_wins': int(g['is_win'].sum()),
            # LambdaRank: full-field expected wins vs actual
            'lr_expected_wins': float(g['lr_win_p'].sum()),
            'lr_win_cal': _ratio(g['lr_win_p'].sum(), g['is_win'].sum()),
            # Bucket head optimism
            'bucket_optimism_full': float(g['bucket_optimism'].mean()),
            'bucket_optimism_top15': float(cont['bucket_optimism'].mean()) if len(cont) else float('nan'),
            # Contender cascade (top-15 rows only)
            'n_top15_rows': int(len(cont)),
            'c_win_cal': _ratio(cont['c_win_p'].sum(), cont['is_win'].sum()),
            'c_podium_cal': _ratio(cont['c_podium_p'].sum(), cont['is_podium'].sum()),
            'c_top5_cal': _ratio(cont['c_top5_p'].sum(), cont['is_top5'].sum()),
            'c_top15_cal': _ratio(cont['c_top15_p'].sum(), cont['is_top15'].sum()),
        }
        out[str(band)] = row
    return out


def _selection_table(rec: pd.DataFrame) -> Dict[str, Dict]:
    """Predicted-top-15 slot share vs actual top-15 finish share, per band."""
    total_slots = rec['in_pred_top15'].sum()
    total_actual = rec['is_top15'].sum()
    out = {}
    for band, g in rec.groupby('age_band', observed=True):
        slot_share = _ratio(g['in_pred_top15'].sum(), total_slots)
        actual_share = _ratio(g['is_top15'].sum(), total_actual)
        out[str(band)] = {
            'pred_top15_slot_share': slot_share,
            'actual_top15_share': actual_share,
            'selection_ratio': _ratio(slot_share, actual_share),
        }
    return out


def _form_slice_tables(rec: pd.DataFrame) -> Dict[str, Dict]:
    """The clinical test: riders with clearly poor / clearly good recent form."""
    informative = rec[rec['form_recent_count'] >= 3]
    slices = {
        'poor_recent_form (form_delta >= +0.5)': informative[informative['form_delta'] >= 0.5],
        'good_recent_form (form_delta <= -0.5)': informative[informative['form_delta'] <= -0.5],
        'neutral_form (|form_delta| < 0.5)': informative[informative['form_delta'].abs() < 0.5],
    }
    out = {}
    for name, sl in slices.items():
        out[name] = _band_table(sl, band_col='age_coarse')
    return out


def _residual_slopes(rec: pd.DataFrame) -> Dict[str, float]:
    """Linear slope of residuals on age (per year of age)."""
    out = {}
    g = rec.dropna(subset=['age_num'])
    if len(g) > 100:
        out['bucket_optimism_per_year_full'] = float(
            np.polyfit(g['age_num'], g['bucket_optimism'], 1)[0]
        )
        out['lr_win_resid_per_year_full'] = float(
            np.polyfit(g['age_num'], g['lr_win_p'] - g['is_win'], 1)[0]
        )
        cont = g[g['in_pred_top15']]
        if len(cont) > 100:
            out['bucket_optimism_per_year_top15'] = float(
                np.polyfit(cont['age_num'], cont['bucket_optimism'], 1)[0]
            )
            out['c_win_resid_per_year_top15'] = float(
                np.polyfit(cont['age_num'], cont['c_win_p'] - cont['is_win'], 1)[0]
            )
    return out


def analyze(rec: pd.DataFrame) -> Dict[str, Any]:
    rec = _add_bands(rec)
    n_unknown_age = int(rec['age_num'].isna().sum())

    analysis = {
        'n_records': int(len(rec)),
        'n_unknown_age': n_unknown_age,
        'band_table': _band_table(rec),
        'selection_table': _selection_table(rec),
        'form_slices': _form_slice_tables(rec),
        'residual_slopes': _residual_slopes(rec),
        'per_fold_band_lr_win_cal': {},
    }

    # Per-fold stability of the headline number (LR win cal by band)
    for fold, g in rec.groupby('fold_label'):
        tbl = {}
        for band, gg in g.groupby('age_band', observed=True):
            tbl[str(band)] = {
                'lr_win_cal': _ratio(gg['lr_win_p'].sum(), gg['is_win'].sum()),
                'bucket_optimism_top15': (
                    float(gg.loc[gg['in_pred_top15'], 'bucket_optimism'].mean())
                    if gg['in_pred_top15'].any() else float('nan')
                ),
                'n_wins': int(gg['is_win'].sum()),
            }
        analysis['per_fold_band_lr_win_cal'][fold] = tbl

    return analysis


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

def print_analysis(analysis: Dict[str, Any]):
    print("\n" + "=" * 96)
    print("AGE-BAND RESIDUAL ANALYSIS — pooled test years 2021-2025")
    print("=" * 96)
    print(f"  records: {analysis['n_records']:,}  (unknown age: {analysis['n_unknown_age']:,})")
    print("  cal ratios = predicted / actual (>1 = model overestimates the band)")
    print("  bucket_optimism = actual − predicted bucket (+ = model too optimistic)")

    hdr = (f"  {'band':<7s} {'n':>8s} {'wins':>6s} {'LRwinCal':>9s} {'CwinCal':>8s} "
           f"{'CpodCal':>8s} {'Ctop15Cal':>9s} {'optimFull':>9s} {'optimT15':>9s}")
    print("\n  MAIN TABLE (all heads)")
    print(hdr)
    for band, r in analysis['band_table'].items():
        print(f"  {band:<7s} {r['n_rows']:>8,d} {r['n_wins']:>6d} "
              f"{r['lr_win_cal']:>9.3f} {r['c_win_cal']:>8.3f} "
              f"{r['c_podium_cal']:>8.3f} {r['c_top15_cal']:>9.3f} "
              f"{r['bucket_optimism_full']:>9.3f} {r['bucket_optimism_top15']:>9.3f}")

    print("\n  SELECTION (predicted top-15 slots vs actual top-15 finishes)")
    for band, r in analysis['selection_table'].items():
        print(f"  {band:<7s} slots {r['pred_top15_slot_share']:>6.1%}  "
              f"actual {r['actual_top15_share']:>6.1%}  ratio {r['selection_ratio']:>6.3f}")

    print("\n  FORM-CONDITIONAL SLICES (form_recent_count >= 3)")
    for slice_name, tbl in analysis['form_slices'].items():
        print(f"\n    {slice_name}")
        for band, r in tbl.items():
            print(f"    {band:<7s} n={r['n_rows']:>7,d} wins={r['n_wins']:>5d}  "
                  f"LRwinCal {r['lr_win_cal']:>7.3f}  CwinCal {r['c_win_cal']:>7.3f}  "
                  f"optimT15 {r['bucket_optimism_top15']:>7.3f}")

    print("\n  RESIDUAL SLOPES (per year of age)")
    for k, v in analysis['residual_slopes'].items():
        print(f"    {k:<38s} {v:>+10.5f}")

    print("\n  PER-FOLD LR WIN CAL (stability check)")
    bands = AGE_LABELS
    print(f"    {'fold':<6s}" + "".join(f"{b:>10s}" for b in bands))
    for fold, tbl in sorted(analysis['per_fold_band_lr_win_cal'].items()):
        vals = []
        for b in bands:
            r = tbl.get(b)
            vals.append(f"{r['lr_win_cal']:>10.3f}" if r else f"{'—':>10s}")
        print(f"    {fold:<6s}" + "".join(vals))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70, flush=True)
    print("AGE-BIAS BACKTEST — form-features step 0 (production-config heads)")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df = _load_full_df()
    print(
        f"\nLoaded {len(df):,} samples, {df['competition_id'].nunique():,} competitions, "
        f"{df['competition_date'].min().date()} to {df['competition_date'].max().date()}",
        flush=True,
    )

    all_records: List[pd.DataFrame] = []
    fold_summaries: List[Dict[str, Any]] = []

    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test year {fold['label']})", flush=True)
        print(f"{'─' * 60}", flush=True)

        train, val, test_year, test_uncapped = _slice_fold(df, fold)
        print(
            f"  Train: {len(train):,} rows  Val: {len(val):,} rows  "
            f"Test {fold['label']}: {len(test_year):,} rows "
            f"({test_year['competition_id'].nunique():,} races; uncapped {len(test_uncapped):,})",
            flush=True,
        )
        if len(test_year) == 0:
            fold_summaries.append({'fold_label': fold['label'], 'skipped': True})
            continue

        print("  Training bucket + contender (production config)...", flush=True)
        bucket_pred, contender_pred, info = _train_bucket_and_contender(
            train, val, fold['label']
        )
        print(f"    best iterations: {info}", flush=True)

        print("  Training LambdaRank + temperature calibration...", flush=True)
        lr_pred = _train_lambdarank(train, val)
        print(f"    LR temperature: {lr_pred.config.temperature:.3f}", flush=True)

        print("  Collecting per-rider records on test year...", flush=True)
        rec = _collect_records(test_year, bucket_pred, contender_pred, lr_pred, fold['label'])
        all_records.append(rec)

        std_metrics = _standard_metrics_uncapped(test_uncapped, bucket_pred, contender_pred)
        print(
            f"    sanity (uncapped test): winner={std_metrics.get('race_winner_capture_rate', float('nan')):.4f}  "
            f"podium={std_metrics.get('race_podium_capture_rate', float('nan')):.4f}  "
            f"log_loss={std_metrics.get('top4_log_loss', float('nan')):.4f}",
            flush=True,
        )

        fold_summaries.append({
            'fold_label': fold['label'],
            'skipped': False,
            'training_info': info,
            'lr_temperature': float(lr_pred.config.temperature),
            'n_test_rows': int(len(test_year)),
            'n_test_races': int(test_year['competition_id'].nunique()),
            'standard_metrics_uncapped': {
                k: float(v) for k, v in std_metrics.items()
                if isinstance(v, (int, float)) and not np.isnan(v)
            },
        })

    records = pd.concat(all_records, ignore_index=True)
    analysis = analyze(records)
    print_analysis(analysis)

    ended = datetime.now()
    duration = (ended - started).total_seconds()
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)

    records_path = out_dir / f"age_bias_backtest_records_{timestamp}.csv.gz"
    records.to_csv(records_path, index=False, compression='gzip')

    out = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': duration,
        'config': {
            'start_date': START_DATE,
            'folds': FOLDS,
            'contender': CONTENDER_CONFIG,
            'lambdarank_main': LAMBDARANK_MAIN_CONFIG,
            'top_n': TOP_N,
            'age_bins': AGE_BINS,
            'test_restriction': 'label calendar year (pooled rows unique)',
        },
        'fold_summaries': fold_summaries,
        'analysis': analysis,
        'records_file': str(records_path),
    }
    out_path = out_dir / f"age_bias_backtest_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)

    print(f"\nRecords saved to {records_path}", flush=True)
    print(f"Results saved to {out_path}", flush=True)
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)", flush=True)


if __name__ == '__main__':
    main()
