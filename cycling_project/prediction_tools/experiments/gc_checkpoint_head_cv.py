"""
Mid-race GC head CV — Phase 2 of the stage-race dynamics plan.

Trains a contender-cascade head that predicts the FINAL GC bucket from the
race state after k completed stages, and evaluates it against two baselines
on identical (gc race, checkpoint) groups:

- blind: the production-style GC prediction (pre-race features only,
  trained on one row per rider x gc competition) — what the system does
  for GC targets today.
- carry-forward: predicted final GC order = current GC order
  (gc_rank_current). Nearly unbeatable late in a race; the bar that
  matters early/mid race.

Training rows for the state head: (rider, gc competition, checkpoint k)
for k = 1..N-1. The state after k stages is already materialized in
rider_race_state as the row keyed to stage k+1's competition (the
"after the final stage" row keyed to the GC competition itself is the
degenerate k=N checkpoint and is excluded). Target: the rider's final GC
place_bucket. Evaluation groups are synthetic competitions
(gc_comp_id * 1000 + k) so the existing per-race machinery ranks within
each checkpoint; metrics are stratified by pct_race_complete
(early <=1/3 < mid <= 2/3 < late).

Caveats: checkpoint rows from the same race are correlated, so per-stratum
n overstates independent evidence — read paired per-fold deltas, as usual.
2025+ GC competitions currently have NULL dates and therefore no
snapshots/field features (known data bug, fix pending), so the 2025 test
fold contributes nothing here.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.gc_checkpoint_head_cv
"""

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
]

STRATA = ['all', 'early', 'mid', 'late']

# Synthetic group id = gc_comp_id * GROUP_FACTOR + checkpoint k. Real
# competition ids are < ~20K and checkpoints < 30, so groups never collide.
GROUP_FACTOR = 1000


# ---------------------------------------------------------------------------
# Data assembly
# ---------------------------------------------------------------------------

def _db_path() -> Path:
    return (
        Path(__file__).parent.parent.parent
        / "webscrape_tools" / "database" / "database" / "cycling_races.db"
    )


def load_gc_base() -> pd.DataFrame:
    """One row per (rider, gc competition): pre-race features + final bucket."""
    cfg = DataConfig(
        db_path=str(_db_path()),
        start_date=START_DATE,
        min_races_career=10,
        include_gradient_features=True,
    )
    pipeline = CyclingDataPipeline(cfg)
    df = pipeline.load_training_data(competition_types=['gc'])
    df['competition_date'] = pd.to_datetime(df['competition_date'])
    return df


def load_checkpoint_states() -> pd.DataFrame:
    """
    Checkpoint states joined to their race's GC competition.

    State keyed to stage seq k+1 holds the standings AFTER k stages, so
    stage-keyed rows are exactly checkpoints k = 1..N-1.
    """
    state_cols_sql = ', '.join(
        f'rrs.{c}' for c in CyclingDataPipeline.RACE_STATE_FEATURE_COLS
    )
    query = f"""
        SELECT rrs.rider_id, gc.id AS gc_competition_id, {state_cols_sql}
        FROM rider_race_state rrs
        JOIN competitions c
            ON c.id = rrs.competition_id AND c.competition_type = 'stage'
        JOIN competitions gc
            ON gc.race_id = rrs.race_id AND gc.competition_type = 'gc'
    """
    conn = sqlite3.connect(str(_db_path()))
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df


def build_checkpoint_frame(
    gc_base: pd.DataFrame, states: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[int, Dict[str, Any]]]:
    """
    Replicate each (rider, gc) row once per checkpoint and attach state.

    Returns (frame, group_meta) where frame uses synthetic competition ids
    and group_meta maps synthetic id -> {'gc_comp', 'k', 'pct'}.
    """
    merged = gc_base.merge(
        states,
        left_on=['rider_id', 'competition_id'],
        right_on=['rider_id', 'gc_competition_id'],
        how='inner',
    )
    merged['stages_completed'] = merged['stages_completed'].astype(int)
    merged['synth_id'] = (
        merged['gc_competition_id'] * GROUP_FACTOR + merged['stages_completed']
    )

    group_meta: Dict[int, Dict[str, Any]] = {}
    meta_src = merged.drop_duplicates('synth_id')[
        ['synth_id', 'gc_competition_id', 'stages_completed', 'pct_race_complete']
    ]
    for row in meta_src.itertuples(index=False):
        group_meta[int(row.synth_id)] = {
            'gc_comp': int(row.gc_competition_id),
            'k': int(row.stages_completed),
            'pct': float(row.pct_race_complete),
        }

    merged['competition_id'] = merged['synth_id']
    merged['race_state_missing'] = 0
    merged = merged.drop(columns=['gc_competition_id', 'synth_id'])
    return merged, group_meta


def _stratum_ids(
    group_meta: Dict[int, Dict[str, Any]], stratum: str
) -> set:
    if stratum == 'all':
        return set(group_meta)
    lo, hi = {
        'early': (0.0, 1 / 3),
        'mid': (1 / 3, 2 / 3),
        'late': (2 / 3, 1.01),
    }[stratum]
    return {
        gid for gid, m in group_meta.items() if lo < m['pct'] <= hi
    }


# ---------------------------------------------------------------------------
# Training + evaluation
# ---------------------------------------------------------------------------

def _train_stack(
    train_df: pd.DataFrame, val_df: pd.DataFrame, fold_label: str
) -> Tuple[Any, Any]:
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
    bucket_pred, _ = trainer.train_bucket_predictor(train_df, val_df)
    contender_pred, _ = trainer.train_contender_predictor(
        train_df, val_df, bucket_pred
    )
    return bucket_pred, contender_pred


def _evaluate_subset(
    test_df: pd.DataFrame, bucket_pred, contender_pred, top_n: int = 15
) -> Tuple[Dict[str, float], int]:
    if len(test_df) == 0:
        return {}, 0
    df = test_df.copy()
    df['classifier_expected_bucket'] = bucket_pred.predict_continuous(df)
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
    return metrics, int(cont_df['competition_id'].nunique())


def carry_forward_metrics(test_df: pd.DataFrame) -> Dict[str, float]:
    """
    Carry-forward baseline on the same groups, mirroring the evaluator's
    semantics: 'predicted winner' = current GC leader; 'predicted podium' =
    current GC top 3. Groups with fewer than 5 riders are skipped.
    """
    winner_captured: List[float] = []
    podium_captured: List[float] = []
    for _, g in test_df.groupby('competition_id'):
        if len(g) < 5:
            continue
        g = g.sort_values('gc_rank_current')
        winner_captured.append(1.0 if g['place_bucket'].iloc[0] == 0 else 0.0)
        top3_buckets = g['place_bucket'].head(3).values
        actual_podium_count = int(np.isin(g['place_bucket'].values, [0, 1]).sum())
        if actual_podium_count > 0:
            podium_captured.append(
                float(np.isin(top3_buckets, [0, 1]).sum())
                / min(3, actual_podium_count)
            )
    out: Dict[str, float] = {}
    if winner_captured:
        out['race_winner_capture_rate'] = float(np.mean(winner_captured))
    if podium_captured:
        out['race_podium_capture_rate'] = float(np.mean(podium_captured))
    return out


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

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


def run_fold(
    gc_base: pd.DataFrame,
    checkpoint_state: pd.DataFrame,
    checkpoint_blind: pd.DataFrame,
    group_meta: Dict[int, Dict[str, Any]],
    fold: Dict[str, str],
) -> Dict[str, Any]:
    # blind trains on UNIQUE gc rows (production-style); state trains on
    # checkpoint rows. Both evaluate on identical checkpoint test groups.
    btrain, bval, _ = _slice(gc_base, fold)
    strain, sval, stest = _slice(checkpoint_state, fold)
    _, _, btest = _slice(checkpoint_blind, fold)

    print(
        f"  blind train {len(btrain):,} rows ({btrain['competition_id'].nunique():,} gc comps)  "
        f"state train {len(strain):,} checkpoint rows  "
        f"test {len(stest):,} rows ({stest['competition_id'].nunique():,} checkpoint groups)",
        flush=True,
    )
    if len(stest) == 0 or len(strain) == 0 or len(sval) == 0:
        print("  [skip] empty window", flush=True)
        return {'fold_label': fold['label'], 'skipped': True}

    print("  Training BLIND stack (pre-race features, unique gc rows)...", flush=True)
    bucket_b, cont_b = _train_stack(btrain, bval, fold['label'])
    print("  Training STATE stack (checkpoint rows + state)...", flush=True)
    bucket_s, cont_s = _train_stack(strain, sval, fold['label'])

    out: Dict[str, Any] = {'fold_label': fold['label'], 'skipped': False, 'strata': {}}
    for stratum in STRATA:
        ids = _stratum_ids(group_meta, stratum)
        st_test = stest[stest['competition_id'].isin(ids)]
        bl_test = btest[btest['competition_id'].isin(ids)]
        m_blind, n_groups = _evaluate_subset(bl_test, bucket_b, cont_b)
        m_state, _ = _evaluate_subset(st_test, bucket_s, cont_s)
        m_cf = carry_forward_metrics(st_test)
        out['strata'][stratum] = {
            'n_groups': n_groups,
            'blind': m_blind,
            'state': m_state,
            'carry_forward': m_cf,
        }
        if m_state:
            print(
                f"    {stratum:<6s} winner: cf={m_cf.get('race_winner_capture_rate', np.nan):.3f} "
                f"blind={m_blind.get('race_winner_capture_rate', np.nan):.3f} "
                f"state={m_state.get('race_winner_capture_rate', np.nan):.3f}   "
                f"log_loss: blind={m_blind.get('top4_log_loss', np.nan):.3f} "
                f"state={m_state.get('top4_log_loss', np.nan):.3f}",
                flush=True,
            )
    return out


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [fr for fr in fold_results if not fr.get('skipped')]
    out: Dict[str, Any] = {}
    for stratum in STRATA:
        s_out: Dict[str, Any] = {
            'blind': {}, 'state': {}, 'carry_forward': {},
            'delta_state_blind': {}, 'delta_state_cf': {},
            'n_groups_per_fold': [
                fr['strata'][stratum]['n_groups'] for fr in usable
            ],
        }
        for metric in PRIMARY_METRICS:
            for variant in ('blind', 'state', 'carry_forward'):
                vals = [
                    fr['strata'][stratum][variant].get(metric)
                    for fr in usable
                ]
                vals = [
                    v for v in vals
                    if v is not None and not (isinstance(v, float) and np.isnan(v))
                ]
                if vals:
                    s_out[variant][metric] = {
                        'mean': float(np.mean(vals)),
                        'std': float(np.std(vals)),
                        'per_fold': [float(v) for v in vals],
                    }
            for delta_key, other in (
                ('delta_state_blind', 'blind'),
                ('delta_state_cf', 'carry_forward'),
            ):
                deltas = []
                for fr in usable:
                    sv = fr['strata'][stratum]['state'].get(metric)
                    ov = fr['strata'][stratum][other].get(metric)
                    if sv is None or ov is None:
                        continue
                    if np.isnan(sv) or np.isnan(ov):
                        continue
                    deltas.append(sv - ov)
                if deltas:
                    s_out[delta_key][metric] = {
                        'mean': float(np.mean(deltas)),
                        'std': float(np.std(deltas)),
                        'per_fold': [float(d) for d in deltas],
                    }
        out[stratum] = s_out
    return out


def _fmt(entry: Optional[Dict[str, Any]], signed: bool = False) -> str:
    if not entry:
        return '—'.rjust(10)
    spec = '{:>+10.4f}' if signed else '{:>10.4f}'
    return spec.format(entry['mean'])


def print_summary(agg: Dict[str, Any]):
    print("\n" + "=" * 100)
    print("SUMMARY — mid-race GC head vs blind (pre-race) vs carry-forward")
    print("=" * 100)
    for stratum in STRATA:
        s = agg.get(stratum, {})
        if not s.get('state'):
            continue
        print(f"\n  [{stratum}]  (checkpoint groups per fold: {s['n_groups_per_fold']})")
        print(
            f"    {'Metric':<28s} {'carry-fwd':>10s} {'blind':>10s} "
            f"{'state':>10s} {'Δ st-blind':>11s} {'Δ st-cf':>11s}"
        )
        for metric in PRIMARY_METRICS:
            stv = s['state'].get(metric)
            if not stv:
                continue
            print(
                f"    {metric:<28s} "
                f"{_fmt(s['carry_forward'].get(metric))} "
                f"{_fmt(s['blind'].get(metric))} "
                f"{_fmt(stv)} "
                f"{_fmt(s['delta_state_blind'].get(metric), signed=True):>11s} "
                f"{_fmt(s['delta_state_cf'].get(metric), signed=True):>11s}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70, flush=True)
    print("MID-RACE GC HEAD CV — Phase 2 (stage_race_dynamics_plan.md)")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    gc_base = load_gc_base()
    states = load_checkpoint_states()
    checkpoint_state, group_meta = build_checkpoint_frame(gc_base, states)
    checkpoint_blind = checkpoint_state.drop(
        columns=[c for c in STATE_COLS if c in checkpoint_state.columns]
    )

    print(
        f"\ngc rows: {len(gc_base):,} ({gc_base['competition_id'].nunique():,} gc comps, "
        f"{gc_base['competition_date'].min().date()} to {gc_base['competition_date'].max().date()})",
        flush=True,
    )
    print(
        f"checkpoint rows: {len(checkpoint_state):,} "
        f"({len(group_meta):,} checkpoint groups, "
        f"{checkpoint_state['competition_date'].nunique():,} dates)",
        flush=True,
    )
    if len(checkpoint_state) == 0:
        raise RuntimeError(
            "No checkpoint rows — is rider_race_state built? "
            "Run: uv run python -m cycling_project.engineering_tools.stage_race_state"
        )

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}", flush=True)
        print(f"FOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)", flush=True)
        print(f"{'─' * 60}", flush=True)
        fold_results.append(
            run_fold(gc_base, checkpoint_state, checkpoint_blind, group_meta, fold)
        )

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
            'strata': STRATA,
            'group_factor': GROUP_FACTOR,
        },
        'data_stats': {
            'gc_rows': int(len(gc_base)),
            'gc_comps': int(gc_base['competition_id'].nunique()),
            'checkpoint_rows': int(len(checkpoint_state)),
            'checkpoint_groups': len(group_meta),
        },
        'fold_results': fold_results,
        'aggregated': agg,
    }

    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_path = out_dir / f"gc_checkpoint_head_cv_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {duration:.1f}s ({duration / 60:.1f} min)", flush=True)


if __name__ == '__main__':
    main()
