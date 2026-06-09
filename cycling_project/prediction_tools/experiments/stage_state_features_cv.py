"""
Stage-race state features CV — Phase 1 of the stage-race dynamics plan.

Tests whether within-race state features (reconstructed GC standings,
in-race stage form, fatigue/progress, tactical-freedom flags from
``rider_race_state``) improve stage-day prediction. See
stage_race_dynamics_plan.md.

Baseline: production contender stack (top-15, LR=0.01, OOF, 5-class,
gradient features). Variant: identical stack + 23 state columns (22
features + race_state_missing flag), joined onto competition_type='stage'
rows only; gc/one-day rows keep pre-race behavior in this phase.

Evaluation is stratified by stage sequence position. The state join is
NULL for stage-1 rows by construction, so the 'stage_1', 'one_day' and
'gc' strata are controls: deltas there should be ~0 (anything systematic
indicates leakage or training interference). The hypothesis lives in
'stage_2_3', 'stage_4_9' and 'stage_10_plus' (late Grand Tour stages,
where fatigue/GC context should matter most).

5-fold expanding-window CV at production start_date='2016-01-01':

    train→2019 / val→2020 / test→2021+
    ...
    train→2023 / val→2024 / test→2025+

Prerequisites: rider_race_state built (uv run python -m
cycling_project.engineering_tools.stage_race_state) on a deduped DB.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.stage_state_features_cv
    uv run python -m cycling_project.prediction_tools.experiments.stage_state_features_cv --state-nan

--state-nan leaves missing state as NaN instead of imputing neutral
defaults (tests LightGBM-native missing routing as the fix for the
stage-1 control regression seen in the 2026-06-09 baseline run).
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import (
    CyclingDataPipeline,
    DataConfig,
)
from cycling_project.prediction_tools.evaluation import Top4ProbabilityEvaluator
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

# Production-aligned contender config (matches stacked_meta_learner_cv_5fold /
# multiclass_start_date_cv for cross-experiment comparability)
CONTENDER_CONFIG = {
    'n_estimators': 500,
    'early_stopping': 50,
    'contender_top_n': 15,
    'contender_learning_rate': 0.01,
    'contender_use_oof': True,
    'contender_n_classes': 5,
    'include_gradient_features': True,
}

STATE_COLS = CyclingDataPipeline.RACE_STATE_FEATURE_COLS + ['race_state_missing']

PRIMARY_METRICS = [
    'race_winner_capture_rate',
    'race_podium_capture_rate',
    'top4_log_loss',
    'top4_brier',
    'win_cal_ratio',
    'podium_cal_ratio',
]

# Strata: 'all' is the production headline; stage_1 / one_day / gc are
# controls (no state by construction); stage_2_3 / stage_4_9 / stage_10_plus
# carry the hypothesis.
STRATA = [
    'all', 'stage_all', 'stage_1', 'stage_2_3', 'stage_4_9',
    'stage_10_plus', 'one_day', 'gc',
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _db_path() -> Path:
    return (
        Path(__file__).parent.parent.parent
        / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    )


def _load_full_df() -> pd.DataFrame:
    cfg = DataConfig(
        db_path=str(_db_path()),
        start_date=START_DATE,
        min_races_career=10,
        include_gradient_features=True,
        include_race_state=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data()
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def _load_stage_seq_map() -> Dict[int, int]:
    """competition_id -> stage sequence position (stage rows only)."""
    conn = sqlite3.connect(str(_db_path()))
    try:
        rows = conn.execute(
            """
            SELECT c.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY c.race_id ORDER BY c.date, c.stage_number
                   ) AS stage_seq
            FROM competitions c
            WHERE c.competition_type = 'stage'
            """
        ).fetchall()
    finally:
        conn.close()
    return {comp_id: seq for comp_id, seq in rows}


def _stratum_mask(
    df: pd.DataFrame, stratum: str, seq_map: Dict[int, int]
) -> pd.Series:
    if stratum == 'all':
        return pd.Series(True, index=df.index)
    if stratum == 'one_day':
        return df['competition_type'] == 'one_day'
    if stratum == 'gc':
        return df['competition_type'] == 'gc'
    seq = df['competition_id'].map(seq_map)
    is_stage = df['competition_type'] == 'stage'
    if stratum == 'stage_all':
        return is_stage
    if stratum == 'stage_1':
        return is_stage & (seq == 1)
    if stratum == 'stage_2_3':
        return is_stage & seq.isin([2, 3])
    if stratum == 'stage_4_9':
        return is_stage & (seq >= 4) & (seq <= 9)
    if stratum == 'stage_10_plus':
        return is_stage & (seq >= 10)
    raise ValueError(f'unknown stratum {stratum!r}')


def _slice_fold(
    df: pd.DataFrame, fold: Dict[str, str]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """ExperimentRunner-style slicing: test is uncapped (after val_end)."""
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])
    train = df[df['competition_date'] <= train_end].copy()
    val = df[
        (df['competition_date'] > train_end)
        & (df['competition_date'] <= val_end)
    ].copy()
    test = df[df['competition_date'] > val_end].copy()
    return train, val, test


# ---------------------------------------------------------------------------
# Training + evaluation (mirrors stacked_meta_learner_cv_5fold)
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


def _evaluate_subset(
    test_df: pd.DataFrame, bucket_pred, contender_pred, top_n: int = 15
) -> Tuple[Dict[str, float], int, int]:
    """Contender-cascade evaluation on a test subset (whole competitions)."""
    if len(test_df) == 0:
        return {}, 0, 0
    expected = bucket_pred.predict_continuous(test_df)
    df = test_df.copy()
    df['classifier_expected_bucket'] = expected
    df['_rank'] = df.groupby('competition_id')['classifier_expected_bucket'].rank()
    cont_df = df[df['_rank'] <= top_n].drop(columns=['_rank'])
    if len(cont_df) == 0:
        return {}, 0, 0

    y_proba = contender_pred.predict_proba(cont_df)
    y_true = cont_df['place_bucket'].values
    n_classes = contender_pred.config.lgb_params.get('num_class', 8)
    if n_classes < 8:
        y_true = np.clip(y_true, 0, n_classes - 1)

    metrics = Top4ProbabilityEvaluator.evaluate(
        y_true, y_proba, competition_ids=cont_df['competition_id'].values
    )
    return metrics, len(cont_df), int(cont_df['competition_id'].nunique())


def _evaluate_all_strata(
    test_df: pd.DataFrame, bucket_pred, contender_pred, seq_map: Dict[int, int]
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for stratum in STRATA:
        subset = test_df[_stratum_mask(test_df, stratum, seq_map)]
        metrics, n_rows, n_comps = _evaluate_subset(
            subset, bucket_pred, contender_pred
        )
        out[stratum] = {
            'metrics': metrics,
            'n_rows_eval': n_rows,
            'n_competitions': n_comps,
        }
    return out


def _state_feature_ranks(contender_pred) -> Dict[str, Any]:
    """Importance ranks of state features in the state-variant contender."""
    try:
        imp_df = contender_pred.get_feature_importance(importance_type='gain')
    except Exception as exc:  # pragma: no cover
        print(f"    [warn] feature importance unavailable: {exc}", flush=True)
        return {}
    fi = dict(zip(imp_df['feature'], imp_df['importance'].astype(float)))
    sorted_feats = sorted(fi.items(), key=lambda x: x[1], reverse=True)
    ranks = {
        feat: i + 1
        for i, (feat, _) in enumerate(sorted_feats)
        if feat in STATE_COLS
    }
    return {
        'n_features_total': len(sorted_feats),
        'state_feature_ranks': ranks,
        'best_state_rank': min(ranks.values()) if ranks else None,
        'state_in_top20': sum(1 for r in ranks.values() if r <= 20),
    }


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(
    df_state: pd.DataFrame,
    df_base: pd.DataFrame,
    fold: Dict[str, str],
    seq_map: Dict[int, int],
) -> Dict[str, Any]:
    train_b, val_b, test_b = _slice_fold(df_base, fold)
    train_s, val_s, test_s = _slice_fold(df_state, fold)

    print(
        f"  Train: {len(train_b):,} rows ({train_b['competition_id'].nunique():,} comps, "
        f"to {train_b['competition_date'].max().date()})  "
        f"Val: {len(val_b):,}  Test: {len(test_b):,}",
        flush=True,
    )
    if len(test_b) == 0:
        return {'fold_label': fold['label'], 'skipped': True}

    print("  Training BASELINE stack...", flush=True)
    bucket_b, cont_b, info_b = _train_bucket_and_contender(
        train_b, val_b, fold['label']
    )
    strata_b = _evaluate_all_strata(test_b, bucket_b, cont_b, seq_map)

    print("  Training STATE stack (+23 state columns)...", flush=True)
    bucket_s, cont_s, info_s = _train_bucket_and_contender(
        train_s, val_s, fold['label']
    )
    strata_s = _evaluate_all_strata(test_s, bucket_s, cont_s, seq_map)
    feat_ranks = _state_feature_ranks(cont_s)

    for stratum in ('all', 'stage_all', 'stage_4_9', 'stage_10_plus'):
        mb = strata_b[stratum]['metrics']
        ms = strata_s[stratum]['metrics']
        if not mb or not ms:
            continue
        print(
            f"    {stratum:<14s} winner {mb.get('race_winner_capture_rate', np.nan):.4f}"
            f" -> {ms.get('race_winner_capture_rate', np.nan):.4f}"
            f"  podium {mb.get('race_podium_capture_rate', np.nan):.4f}"
            f" -> {ms.get('race_podium_capture_rate', np.nan):.4f}"
            f"  log_loss {mb.get('top4_log_loss', np.nan):.4f}"
            f" -> {ms.get('top4_log_loss', np.nan):.4f}",
            flush=True,
        )
    if feat_ranks.get('state_feature_ranks'):
        top5 = sorted(
            feat_ranks['state_feature_ranks'].items(), key=lambda x: x[1]
        )[:5]
        print(
            "    Top state features: "
            + ", ".join(f"{f}#{r}" for f, r in top5)
            + f"  ({feat_ranks['state_in_top20']} in top 20 of "
            f"{feat_ranks['n_features_total']})",
            flush=True,
        )

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'baseline': {'strata': strata_b, 'training_info': info_b},
        'state': {'strata': strata_s, 'training_info': info_s},
        'state_feature_ranks': feat_ranks,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [fr for fr in fold_results if not fr.get('skipped')]
    out: Dict[str, Any] = {}
    for stratum in STRATA:
        s_out: Dict[str, Any] = {'baseline': {}, 'state': {}, 'delta': {}}
        for metric in PRIMARY_METRICS:
            b_vals, s_vals, deltas = [], [], []
            for fr in usable:
                mb = fr['baseline']['strata'][stratum]['metrics']
                ms = fr['state']['strata'][stratum]['metrics']
                vb, vs = mb.get(metric), ms.get(metric)
                if vb is None or vs is None:
                    continue
                if np.isnan(vb) or np.isnan(vs):
                    continue
                b_vals.append(vb)
                s_vals.append(vs)
                deltas.append(vs - vb)
            if not deltas:
                continue
            s_out['baseline'][metric] = {
                'mean': float(np.mean(b_vals)), 'std': float(np.std(b_vals)),
            }
            s_out['state'][metric] = {
                'mean': float(np.mean(s_vals)), 'std': float(np.std(s_vals)),
            }
            s_out['delta'][metric] = {
                'mean': float(np.mean(deltas)), 'std': float(np.std(deltas)),
                'per_fold': [float(d) for d in deltas],
            }
        s_out['n_competitions_per_fold'] = [
            fr['baseline']['strata'][stratum]['n_competitions'] for fr in usable
        ]
        out[stratum] = s_out
    return out


def print_summary(agg: Dict[str, Any]):
    print("\n" + "=" * 100)
    print("SUMMARY — stage-race state features vs baseline (mean ± std across folds)")
    print("=" * 100)
    for stratum in STRATA:
        s = agg.get(stratum, {})
        if not s.get('delta'):
            continue
        n_comps = s.get('n_competitions_per_fold', [])
        print(f"\n  [{stratum}]  (competitions per fold: {n_comps})")
        print(
            f"    {'Metric':<30s}  {'Baseline':>16s}  {'State':>16s}  {'Δ (state-base)':>18s}"
        )
        for metric in PRIMARY_METRICS:
            b = s['baseline'].get(metric)
            v = s['state'].get(metric)
            d = s['delta'].get(metric)
            if not (b and v and d):
                continue
            print(
                f"    {metric:<30s}  "
                f"{b['mean']:>7.4f}±{b['std']:>6.4f}  "
                f"{v['mean']:>7.4f}±{v['std']:>6.4f}  "
                f"{d['mean']:>+8.4f}±{d['std']:>6.4f}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--state-nan', action='store_true',
        help='leave missing state as NaN (skip neutral-default imputation)',
    )
    args = parser.parse_args()

    state_imputation = 'nan' if args.state_nan else 'neutral_defaults'
    if args.state_nan:
        from cycling_project.prediction_tools import feature_engineering
        feature_engineering.IMPUTE_RACE_STATE_DEFAULTS = False

    print("=" * 70, flush=True)
    print("STAGE-RACE STATE FEATURES CV — Phase 1 (stage_race_dynamics_plan.md)")
    print(f"State imputation mode: {state_imputation}")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df_state = _load_full_df()
    seq_map = _load_stage_seq_map()

    stage_rows = df_state['competition_type'] == 'stage'
    state_present = stage_rows & (df_state['race_state_missing'] == 0)
    print(
        f"\nLoaded {len(df_state):,} rows, {df_state['competition_id'].nunique():,} comps, "
        f"{df_state['competition_date'].min().date()} to "
        f"{df_state['competition_date'].max().date()}",
        flush=True,
    )
    coverage = state_present.sum() / max(stage_rows.sum(), 1)
    print(
        f"State coverage on stage rows: {state_present.sum():,}/{stage_rows.sum():,} "
        f"({coverage:.1%}; remainder = stage-1 rows, coverage gaps, suspect races)",
        flush=True,
    )
    if coverage < 0.4:
        raise RuntimeError(
            "State coverage is implausibly low — is rider_race_state built? "
            "Run: uv run python -m cycling_project.engineering_tools.stage_race_state"
        )

    df_base = df_state.drop(columns=[c for c in STATE_COLS if c in df_state.columns])

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)", flush=True)
        print(f"{'─' * 60}", flush=True)
        fold_results.append(run_fold(df_state, df_base, fold, seq_map))

    agg = aggregate(fold_results)
    print_summary(agg)

    ended = datetime.now()
    duration = (ended - started).total_seconds()
    out = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': duration,
        'config': {
            'start_date': START_DATE,
            'folds': FOLDS,
            'contender': CONTENDER_CONFIG,
            'state_cols': STATE_COLS,
            'strata': STRATA,
            'state_imputation': state_imputation,
        },
        'data_stats': {
            'total_rows': int(len(df_state)),
            'stage_rows': int(stage_rows.sum()),
            'stage_rows_with_state': int(state_present.sum()),
        },
        'fold_results': fold_results,
        'aggregated': agg,
    }

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    suffix = '_nan' if args.state_nan else ''
    out_path = out_dir / f"stage_state_features_cv{suffix}_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)", flush=True)


if __name__ == '__main__':
    main()
