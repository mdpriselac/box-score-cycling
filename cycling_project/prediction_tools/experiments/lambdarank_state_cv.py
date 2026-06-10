"""
LambdaRank head + stage-race state features — 5-fold CV.

Follow-up to the Phase-1 stage-state experiment (2026-06-09): the contender
cascade shipped with state features using neutral-default imputation, and
the rejected NaN-imputation variant showed a log-loss-heavy profile
(stage-row log loss −0.040 vs −0.033, at the cost of winner capture).
That profile suits the LambdaRank head, whose job is calibrated
probabilities rather than argmax picks — so this run tests the production
LambdaRank config with state, in both imputation modes, against the
stateless baseline.

Variants (identical rows; state columns dropped for the baseline):
- baseline:        production LambdaRank, no state columns
- state_defaults:  + 23 state columns, neutral-default imputation
- state_nan:       + 23 state columns, missing state left NaN
                   (feature_engineering.IMPUTE_RACE_STATE_DEFAULTS=False)

Same 5 expanding-window folds as the Phase-1 experiment (test 2021-2025,
uncapped), start_date 2016. Metrics from the predictor's own evaluate()
(winner/podium capture, win log loss, calibration ratio, ECE), reported
overall and on stage-sequence strata.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.lambdarank_state_cv
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from cycling_project.prediction_tools import feature_engineering
from cycling_project.prediction_tools.data_pipeline import (
    CyclingDataPipeline,
    DataConfig,
)
from cycling_project.prediction_tools.lambdarank_probability_predictor import (
    LambdaRankPredictorConfig,
    LambdaRankProbabilityPredictor,
)
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

# Production LambdaRank config (LR=0.05 per the 2026-04-18 deployment)
LR_CONFIG = {
    'n_estimators': 2000,
    'early_stopping_rounds': 300,
    'learning_rate': 0.05,
}

STATE_COLS = CyclingDataPipeline.RACE_STATE_FEATURE_COLS + ['race_state_missing']

VARIANTS = ['baseline', 'state_defaults', 'state_nan']

STRATA = ['all', 'stage_all', 'stage_1', 'stage_2_3', 'stage_4_9', 'stage_10_plus']

HEADLINE_METRICS = [
    'winner_capture', 'podium_capture', 'win_log_loss',
    'win_cal_ratio', 'win_ece', 'discrimination_ratio',
]


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
    conn = sqlite3.connect(str(_db_path()))
    try:
        rows = conn.execute(
            """
            SELECT c.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY c.race_id ORDER BY c.date, c.stage_number
                   )
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
    raise ValueError(stratum)


def _slice(df: pd.DataFrame, fold: Dict[str, str]):
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])
    train = df[df['competition_date'] <= train_end].copy()
    val = df[
        (df['competition_date'] > train_end)
        & (df['competition_date'] <= val_end)
    ].copy()
    test = df[df['competition_date'] > val_end].copy()
    return train, val, test


def run_variant_fold(
    df: pd.DataFrame,
    fold: Dict[str, str],
    seq_map: Dict[int, int],
    impute_state_defaults: bool,
) -> Dict[str, Any]:
    train, val, test = _slice(df, fold)
    if len(test) == 0:
        return {'fold_label': fold['label'], 'skipped': True}

    prev = feature_engineering.IMPUTE_RACE_STATE_DEFAULTS
    feature_engineering.IMPUTE_RACE_STATE_DEFAULTS = impute_state_defaults
    try:
        cfg = LambdaRankPredictorConfig(
            n_estimators=LR_CONFIG['n_estimators'],
            early_stopping_rounds=LR_CONFIG['early_stopping_rounds'],
        )
        cfg.lgb_params['learning_rate'] = LR_CONFIG['learning_rate']
        predictor = LambdaRankProbabilityPredictor(cfg)
        info = predictor.train(train, val, verbose=False)
        temperature = predictor.calibrate_temperature(val)

        strata_metrics: Dict[str, Any] = {}
        for stratum in STRATA:
            subset = test[_stratum_mask(test, stratum, seq_map)]
            if len(subset) == 0:
                strata_metrics[stratum] = {}
                continue
            strata_metrics[stratum] = predictor.evaluate(subset)
    finally:
        feature_engineering.IMPUTE_RACE_STATE_DEFAULTS = prev

    return {
        'fold_label': fold['label'],
        'skipped': False,
        'best_iteration': info.get('best_iteration'),
        'n_features': info.get('n_features'),
        'calibrated_temperature': float(temperature),
        'strata': strata_metrics,
    }


def aggregate(variant_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for stratum in STRATA:
        s_out: Dict[str, Any] = {v: {} for v in VARIANTS}
        s_out['delta_vs_baseline'] = {v: {} for v in VARIANTS if v != 'baseline'}
        for metric in HEADLINE_METRICS:
            per_variant_per_fold: Dict[str, Dict[str, float]] = {}
            for variant in VARIANTS:
                vals = {}
                for fr in variant_results[variant]:
                    if fr.get('skipped'):
                        continue
                    v = fr['strata'].get(stratum, {}).get(metric)
                    if v is None or (isinstance(v, float) and np.isnan(v)):
                        continue
                    vals[fr['fold_label']] = float(v)
                if vals:
                    per_variant_per_fold[variant] = vals
                    s_out[variant][metric] = {
                        'mean': float(np.mean(list(vals.values()))),
                        'std': float(np.std(list(vals.values()))),
                        'per_fold': vals,
                    }
            base = per_variant_per_fold.get('baseline', {})
            for variant in ('state_defaults', 'state_nan'):
                vv = per_variant_per_fold.get(variant, {})
                deltas = [
                    vv[label] - base[label] for label in vv if label in base
                ]
                if deltas:
                    s_out['delta_vs_baseline'][variant][metric] = {
                        'mean': float(np.mean(deltas)),
                        'std': float(np.std(deltas)),
                        'per_fold': [float(d) for d in deltas],
                    }
        out[stratum] = s_out
    return out


def print_summary(agg: Dict[str, Any]):
    print("\n" + "=" * 100)
    print("SUMMARY — LambdaRank + state vs stateless baseline (mean ± std across folds)")
    print("=" * 100)
    for stratum in STRATA:
        s = agg.get(stratum, {})
        if not s.get('baseline'):
            continue
        print(f"\n  [{stratum}]")
        print(
            f"    {'Metric':<24s} {'baseline':>16s} {'state_defaults':>16s} "
            f"{'state_nan':>16s} {'Δ def':>9s} {'Δ nan':>9s}"
        )
        for metric in HEADLINE_METRICS:
            b = s['baseline'].get(metric)
            if not b:
                continue
            d = s['state_defaults'].get(metric)
            n = s['state_nan'].get(metric)
            dd = s['delta_vs_baseline']['state_defaults'].get(metric)
            dn = s['delta_vs_baseline']['state_nan'].get(metric)

            def cell(e):
                return (
                    f"{e['mean']:>8.4f}±{e['std']:<6.4f}" if e else '—'.center(15)
                )

            def dcell(e):
                return f"{e['mean']:>+8.4f}" if e else '—'.rjust(8)

            print(
                f"    {metric:<24s} {cell(b):>16s} {cell(d):>16s} "
                f"{cell(n):>16s} {dcell(dd):>9s} {dcell(dn):>9s}"
            )


def main():
    print("=" * 70, flush=True)
    print("LAMBDARANK + STATE — 5-FOLD CV (stage_race_dynamics_plan.md)")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df_state = _load_full_df()
    df_base = df_state.drop(
        columns=[c for c in STATE_COLS if c in df_state.columns]
    )
    seq_map = _load_stage_seq_map()
    print(
        f"\nLoaded {len(df_state):,} rows, "
        f"{df_state['competition_id'].nunique():,} comps",
        flush=True,
    )

    variant_specs = [
        ('baseline', df_base, True),
        ('state_defaults', df_state, True),
        ('state_nan', df_state, False),
    ]
    variant_results: Dict[str, List[Dict[str, Any]]] = {v: [] for v in VARIANTS}

    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)", flush=True)
        print(f"{'─' * 60}", flush=True)
        for name, frame, impute in variant_specs:
            result = run_variant_fold(frame, fold, seq_map, impute)
            variant_results[name].append(result)
            if not result.get('skipped'):
                m = result['strata'].get('all', {})
                print(
                    f"  {name:<16s} winner={m.get('winner_capture', np.nan):.4f}  "
                    f"podium={m.get('podium_capture', np.nan):.4f}  "
                    f"log_loss={m.get('win_log_loss', np.nan):.4f}  "
                    f"T={result['calibrated_temperature']:.3f}  "
                    f"iters={result['best_iteration']}",
                    flush=True,
                )

    agg = aggregate(variant_results)
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
            'lambdarank': LR_CONFIG,
            'variants': VARIANTS,
            'state_cols': STATE_COLS,
        },
        'variant_results': variant_results,
        'aggregated': agg,
    }
    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"lambdarank_state_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)", flush=True)


if __name__ == '__main__':
    main()
