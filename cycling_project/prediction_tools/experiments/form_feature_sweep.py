"""
Form feature sweep — steps 1-3 of the form-features work.

Tests the form-feature-lab blocks additively against a paired baseline on
the standard 5-fold expanding window (start 2016, production contender
config), measuring both the standard primary metrics and the age-bias
indicators from the step-0 backtest.

Configs (round 1):
    baseline   — production 126-feature set, no lab columns
    v1         — + fixed-window form (cross-year 90d window, NaN defaults)
    v2         — + EMA percentile form (h30/h60, quality-weighted)
    v3         — + multi-season trajectory (season deltas, slope, peak)
    v2v3v4     — + the full new-form stack (EMA + trajectory + volatility)

Each config trains bucket + contender + LambdaRank per fold. Standard
metrics use the uncapped test (comparable to prior experiment JSONs);
age-bias analysis pools each fold's label-calendar-year test rows
(every row counted once) via age_bias_backtest.analyze.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.form_feature_sweep
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.experiments.age_bias_backtest import (
    FOLDS,
    _collect_records,
    _load_full_df,
    _slice_fold,
    _standard_metrics_uncapped,
    _train_bucket_and_contender,
    _train_lambdarank,
    analyze,
)
from cycling_project.prediction_tools.experiments.form_feature_lab import (
    ALL_LAB_COLS,
    V1_COLS,
    V2_COLS,
    V3_COLS,
    V4_COLS,
    FormFeatureLab,
)
from cycling_project.webscrape_tools.logging_config import get_logger


logger = get_logger(__name__)


CONFIG_REGISTRY: Dict[str, List[str]] = {
    'baseline': [],
    'v1': V1_COLS,
    'v2': V2_COLS,
    'v3': V3_COLS,
    'v4': V4_COLS,
    'v2v3': V2_COLS + V3_COLS,
    'v3v4': V3_COLS + V4_COLS,
    'v2v3v4': V2_COLS + V3_COLS + V4_COLS,
}

# Round 1 default; override with CLI args, e.g.:
#   ... form_feature_sweep baseline v2v3 v3v4
DEFAULT_CONFIGS = ['baseline', 'v1', 'v2', 'v3', 'v2v3v4']

STANDARD_KEYS = [
    'race_winner_capture_rate',
    'race_podium_capture_rate',
    'top4_log_loss',
    'top4_brier',
    'win_cal_ratio',
]


def _age_bias_indicators(analysis: Dict[str, Any]) -> Dict[str, float]:
    """Flatten the headline veteran-bias numbers from an analyze() result."""
    out: Dict[str, float] = {}
    bt = analysis.get('band_table', {})
    for band in ('30-33', '34-36', '37+'):
        r = bt.get(band)
        if r:
            out[f'lr_win_cal_{band}'] = r['lr_win_cal']
            out[f'c_win_cal_{band}'] = r['c_win_cal']
            out[f'optimism_top15_{band}'] = r['bucket_optimism_top15']
    slopes = analysis.get('residual_slopes', {})
    out.update({f'slope_{k}': v for k, v in slopes.items()})
    poor = analysis.get('form_slices', {}).get(
        'poor_recent_form (form_delta >= +0.5)', {}
    )
    r = poor.get('34+')
    if r:
        out['poorform_34p_lr_win_cal'] = r['lr_win_cal']
        out['poorform_34p_c_win_cal'] = r['c_win_cal']
        out['poorform_34p_optimism_top15'] = r['bucket_optimism_top15']
    return out


def _lab_feature_ranks(predictor, lab_cols: List[str]) -> Dict[str, Any]:
    """Importance rank of each lab column in a trained predictor."""
    try:
        imp_df = predictor.get_feature_importance(importance_type='gain')
    except Exception:
        return {}
    imp = sorted(
        zip(imp_df['feature'], imp_df['importance'].astype(float)),
        key=lambda x: x[1], reverse=True,
    )
    total = sum(v for _, v in imp) or 1.0
    ranks = {}
    for i, (feat, gain) in enumerate(imp):
        if feat in lab_cols:
            ranks[feat] = {'rank': i + 1, 'gain_pct': 100.0 * gain / total}
    return ranks


def run_config(
    name: str,
    lab_cols: List[str],
    master: pd.DataFrame,
) -> Dict[str, Any]:
    """Run all folds for one feature config."""
    drop_cols = [c for c in ALL_LAB_COLS if c not in lab_cols]
    df = master.drop(columns=drop_cols)

    fold_outputs = []
    all_records = []

    for i, fold in enumerate(FOLDS):
        train, val, test_year, test_uncapped = _slice_fold(df, fold)
        print(
            f"  [{name}] fold {i + 1}/{len(FOLDS)} (test {fold['label']}): "
            f"train {len(train):,} / test {len(test_year):,}",
            flush=True,
        )

        bucket_pred, contender_pred, info = _train_bucket_and_contender(
            train, val, fold['label']
        )
        lr_pred = _train_lambdarank(train, val)

        rec = _collect_records(test_year, bucket_pred, contender_pred, lr_pred, fold['label'])
        all_records.append(rec)

        std = _standard_metrics_uncapped(test_uncapped, bucket_pred, contender_pred)
        std = {k: float(v) for k, v in std.items()
               if isinstance(v, (int, float)) and np.isfinite(v)}

        fold_outputs.append({
            'fold_label': fold['label'],
            'training_info': info,
            'lr_temperature': float(lr_pred.config.temperature),
            'standard_metrics_uncapped': std,
            'lab_ranks_contender': _lab_feature_ranks(contender_pred, lab_cols),
            'lab_ranks_bucket': _lab_feature_ranks(bucket_pred, lab_cols),
        })
        print(
            f"    winner={std.get('race_winner_capture_rate', float('nan')):.4f}  "
            f"podium={std.get('race_podium_capture_rate', float('nan')):.4f}  "
            f"log_loss={std.get('top4_log_loss', float('nan')):.4f}",
            flush=True,
        )

    records = pd.concat(all_records, ignore_index=True)
    analysis = analyze(records)

    return {
        'config': name,
        'lab_cols': lab_cols,
        'fold_outputs': fold_outputs,
        'age_bias_analysis': analysis,
        'age_bias_indicators': _age_bias_indicators(analysis),
        '_records': records,
    }


def _aggregate_standard(fold_outputs: List[Dict]) -> Dict[str, Dict[str, float]]:
    out = {}
    for k in STANDARD_KEYS:
        vals = [
            fo['standard_metrics_uncapped'].get(k)
            for fo in fold_outputs
            if k in fo.get('standard_metrics_uncapped', {})
        ]
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        if vals:
            out[k] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
                'per_fold': [float(v) for v in vals],
            }
    return out


def print_comparison(results: Dict[str, Dict[str, Any]]):
    base = results['baseline']
    base_std = _aggregate_standard(base['fold_outputs'])

    print("\n" + "=" * 100)
    print("SWEEP SUMMARY — standard metrics (uncapped test, mean ± std; Δ vs baseline paired per fold)")
    print("=" * 100)
    for name, res in results.items():
        std = _aggregate_standard(res['fold_outputs'])
        parts = [f"  {name:<10s}"]
        for k in ('race_winner_capture_rate', 'race_podium_capture_rate', 'top4_log_loss'):
            if k in std:
                m = std[k]
                parts.append(f"{k.split('race_')[-1].split('top4_')[-1]}={m['mean']:.4f}±{m['std']:.4f}")
                if name != 'baseline' and k in base_std:
                    deltas = [
                        e - b for e, b in zip(std[k]['per_fold'], base_std[k]['per_fold'])
                    ]
                    parts.append(f"(Δ{np.mean(deltas):+.4f}±{np.std(deltas):.4f})")
        print("  ".join(parts))

    print("\n" + "=" * 100)
    print("AGE-BIAS INDICATORS (pooled 2021-2025 test years; cal >1 = overestimates band)")
    print("=" * 100)
    keys = sorted({k for res in results.values() for k in res['age_bias_indicators']})
    hdr = f"  {'indicator':<36s}" + "".join(f"{n:>12s}" for n in results)
    print(hdr)
    for k in keys:
        row = f"  {k:<36s}"
        for name in results:
            v = results[name]['age_bias_indicators'].get(k)
            row += f"{v:>12.3f}" if v is not None and np.isfinite(v) else f"{'—':>12s}"
        print(row)

    print("\nLAB FEATURE RANKS (contender, mean across folds)")
    for name, res in results.items():
        if name == 'baseline':
            continue
        rank_acc: Dict[str, List[float]] = {}
        for fo in res['fold_outputs']:
            for feat, r in fo['lab_ranks_contender'].items():
                rank_acc.setdefault(feat, []).append(r['rank'])
        if rank_acc:
            print(f"  {name}:")
            for feat, ranks in sorted(rank_acc.items(), key=lambda x: np.mean(x[1])):
                print(f"    {feat:<28s} mean rank {np.mean(ranks):>6.1f}  "
                      f"(best {int(min(ranks))}, worst {int(max(ranks))})")


def main():
    import sys

    names = sys.argv[1:] or DEFAULT_CONFIGS
    unknown = [n for n in names if n not in CONFIG_REGISTRY]
    if unknown:
        raise SystemExit(f"Unknown configs: {unknown}. Known: {list(CONFIG_REGISTRY)}")
    configs = {n: CONFIG_REGISTRY[n] for n in names}

    print("=" * 70, flush=True)
    print("FORM FEATURE SWEEP — steps 1-3 (v1 window fix / v2 EMA / v3 trajectory)")
    print(f"Configs: {list(configs)}")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df = _load_full_df()
    print(f"Loaded {len(df):,} training rows", flush=True)

    lab = FormFeatureLab()
    feats = lab.build_or_load()
    print(f"Lab features: {len(feats):,} rows x {len(ALL_LAB_COLS)} cols", flush=True)

    master = df.merge(feats, on=['rider_id', 'competition_id'], how='left')
    matched = master[ALL_LAB_COLS[0]].notna() | (master['v1_form_n5'].notna())
    print(f"Merge coverage: {matched.mean():.1%} of training rows", flush=True)

    results: Dict[str, Dict[str, Any]] = {}
    for name, cols in configs.items():
        print(f"\n{'─' * 60}", flush=True)
        print(f"CONFIG: {name} (+{len(cols)} lab cols)", flush=True)
        print(f"{'─' * 60}", flush=True)
        results[name] = run_config(name, cols, master)

    print_comparison(results)

    ended = datetime.now()
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, res in results.items():
        rec_path = out_dir / f"form_sweep_records_{name}_{timestamp}.csv.gz"
        res.pop('_records').to_csv(rec_path, index=False, compression='gzip')
        res['records_file'] = str(rec_path)

    out = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': (ended - started).total_seconds(),
        'configs': {k: v for k, v in configs.items()},
        'results': results,
    }
    out_path = out_dir / f"form_feature_sweep_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {(ended - started).total_seconds() / 60:.1f} min", flush=True)


if __name__ == '__main__':
    main()
