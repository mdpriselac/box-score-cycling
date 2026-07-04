"""
Form feature sweep — additive gate for form-feature-lab blocks.

Round 1 (2026-06): v1/v2/v3/v4 blocks vs the pre-trajectory production set —
v2v3 passed and shipped to production (form_team_features twins, 2026-06-10).

Round 2 (2026-07, GT-aware form): v5 (contested-rows-only EMA) and v6
(comp-type-scoped EMA) vs the CURRENT production set (which already carries
the v2/v3 twins natively). Targets the grand-tour coasting dilution
established by the step-0 GT-recency backtest
(experiments/gt_recency_backtest_20260703.json).

Per config x 5 expanding folds (2016 start, production contender config):
  - bucket + contender + LambdaRank trained per fold
  - standard metrics (uncapped test, Top4 evaluator) for comparability
  - market probability metrics (MarketProbabilityEvaluator, top-15 pool)
  - HONEST-FRAME market metrics (startlist pool incl. DNF'd starters,
    P(market|finish) x P(finish) via a fold-safe DNF head) — the PRIMARY
    gate metric per the 2026-06-11 probability-gate policy. DNF'd-starter
    rows get real lab features via FormFeatureLab.features_for_targets.
  - GT-recency calibration tables (gt_recency_backtest.gt_band_tables) on
    the pooled label-year records — the bias diagnostic this round exists
    for. Success shape: GT <=45d band cal -> 1.0 (esp. GC targets) WITHOUT
    pushing the no-GT band further above its baseline.
  - age-bias indicators retained (regression check on the v2v3 fix)

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.form_feature_sweep [--smoke] [configs...]
    default configs: baseline v5 v6 v5v6
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import cycling_project.prediction_tools.experiments.age_bias_backtest as abb
from cycling_project.prediction_tools.experiments.age_bias_backtest import (
    FOLDS,
    TOP_N,
    _collect_records,
    _load_full_df,
    _slice_fold,
    _standard_metrics_uncapped,
    _train_bucket_and_contender,
    _train_lambdarank,
    analyze,
)
from cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv import (
    SUBSETS as HONEST_SUBSETS,
    adjust_markets,
    build_dnf_pipeline_rows,
    market_metrics,
    proba_to_markets,
)
from cycling_project.prediction_tools.experiments.form_feature_lab import (
    ALL_LAB_COLS,
    MERGEABLE_LAB_COLS,
    V1_COLS,
    V4_COLS,
    V5_COLS,
    V6_COLS,
    FormFeatureLab,
)
from cycling_project.prediction_tools.experiments.gt_recency_backtest import (
    attach_gt_recency,
    gt_band_tables,
    load_gt_participations,
)
from cycling_project.prediction_tools.dnf_predictor import (
    DNFPredictor,
    _DB_PATH,
    add_asof_dates,
    build_feature_frame,
    evaluate_dnf,
    load_labels,
    load_snapshot_table,
)
from cycling_project.prediction_tools.evaluation import MarketProbabilityEvaluator
from cycling_project.webscrape_tools.logging_config import get_logger


logger = get_logger(__name__)


# NOTE: v2/v3 lab blocks are NOT registerable any more — they were
# productionized 2026-06-10 under identical column names, so the production
# frame already carries them (merging the lab copies would collide).
CONFIG_REGISTRY: Dict[str, List[str]] = {
    'baseline': [],
    'v1': V1_COLS,
    'v4': V4_COLS,
    'v5': V5_COLS,
    'v6': V6_COLS,
    'v5v6': V5_COLS + V6_COLS,
    # One-day-scoped variants (see ONEDAY_NAN_COLS): the GT-aware form
    # features are NaN'd on one_day TARGET rows (train + eval + honest pool),
    # so they act only on gc/stage racing — the grand-tour-adjacent context
    # where the coasting dilution lives.
    'v5scoped': V5_COLS,
    'v6scoped': V6_COLS,
    'v5v6scoped': V5_COLS + V6_COLS,
    'v5v6mixed': V5_COLS + V6_COLS,  # v5 scoped off one-days, v6 left on
}

# Per-config subset of lab cols to NaN on one_day target rows. Round-2
# finding: v5 (contested-rows EMA) fixes the GT-recency bias and improves
# gc/stage market LL but consistently REGRESSES one-day market LL (v2 all-row
# EMA already suffices there — v5 adds variance). v6 (scoped EMA) is neutral
# on one-days. Scoping mirrors the shipped one-day-scoped signature features.
ONEDAY_NAN_COLS: Dict[str, List[str]] = {
    'v5scoped': V5_COLS,
    'v6scoped': V6_COLS,
    'v5v6scoped': V5_COLS + V6_COLS,
    'v5v6mixed': V5_COLS,  # only v5 is scoped; v6 stays active on one-days
}

DEFAULT_CONFIGS = ['baseline', 'v5', 'v6', 'v5v6']

STANDARD_KEYS = [
    'race_winner_capture_rate',
    'race_podium_capture_rate',
    'top4_log_loss',
    'top4_brier',
    'win_cal_ratio',
]
MARKET_KEYS = [
    'market_avg_log_loss', 'win_log_loss', 'podium_log_loss',
    'top5_log_loss', 'top15_log_loss', 'market_avg_brier', 'win_cal_ratio',
]
HONEST_KEYS = ['market_avg_log_loss', 'win_log_loss', 'top15_log_loss', 'win_cal_ratio']


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


def _market_metrics_uncapped(
    test_df: pd.DataFrame, bucket_pred, contender_pred
) -> Dict[str, float]:
    """MarketProbabilityEvaluator on the uncapped-test top-15 contender pool."""
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
    return MarketProbabilityEvaluator.evaluate(
        y_true, y_proba, competition_ids=cont_df['competition_id'].values
    )


# ---------------------------------------------------------------------------
# Honest-frame evaluation (startlist pool, DNF-adjusted) — primary gate
# ---------------------------------------------------------------------------

def _honest_eval(
    test_df: pd.DataFrame,
    dnf_rows_cfg: pd.DataFrame,
    bucket_pred,
    contender_pred,
    p_map: Dict,
    parity: bool = False,
) -> Dict[str, Any]:
    """dnf_market_adjustment_cv's views on the config's startlist pool.

    Reported views: standard (finisher top-15, raw), honest_unadjusted and
    honest_adjusted (pool top-15, x P(finish) with win book preserved).
    """
    pool = pd.concat(
        [test_df.assign(is_dnf_row=0), dnf_rows_cfg.assign(is_dnf_row=1)],
        ignore_index=True,
    )
    pool['classifier_expected_bucket'] = bucket_pred.predict_continuous(pool)
    fin_mask = pool['is_dnf_row'] == 0
    pool['_rank_fin'] = (
        pool[fin_mask].groupby('competition_id')['classifier_expected_bucket'].rank()
    )
    pool['_rank_pool'] = pool.groupby('competition_id')['classifier_expected_bucket'].rank()
    sel_std = fin_mask & (pool['_rank_fin'] <= TOP_N)
    sel_hon = pool['_rank_pool'] <= TOP_N
    need = sel_std | sel_hon

    cd = pool[need].copy()
    proba = contender_pred.predict_proba(cd)
    n_classes = contender_pred.config.lgb_params.get('num_class', 8)
    y_bucket = np.clip(cd['place_bucket'].values.astype(int), 0, n_classes - 1)
    is_dnf = cd['is_dnf_row'].values.astype(bool)

    keys = list(zip(cd['competition_id'].values, cd['rider_id'].values))
    p_dnf = np.array([p_map.get(k, 0.0) for k in keys])
    head_missing = int(np.sum([k not in p_map for k in keys]))
    p_finish = 1.0 - p_dnf

    raw = proba_to_markets(proba)
    comp_ids = cd['competition_id'].values
    in_std = sel_std.values[need.values]
    in_hon = sel_hon.values[need.values]
    ctype = cd['competition_type'].values

    def eval_view(rows: np.ndarray, adjusted: bool) -> Dict[str, float]:
        mp = {m: raw[m][rows] for m in raw}
        if adjusted:
            mp = adjust_markets(mp, p_finish[rows], comp_ids[rows])
        return market_metrics(mp, y_bucket[rows], is_dnf[rows])

    out: Dict[str, Any] = {'head_pred_missing_rows': head_missing, 'subsets': {}}
    for subset in HONEST_SUBSETS:
        smask = np.ones(len(cd), dtype=bool) if subset == 'all' else (ctype == subset)
        rows_s = in_std & smask
        rows_h = in_hon & smask
        if rows_s.sum() == 0:
            continue
        m_s = eval_view(rows_s, adjusted=False)
        if parity and subset == 'all':
            ref = MarketProbabilityEvaluator.evaluate(y_bucket[rows_s], proba[rows_s])
            assert abs(ref['market_avg_log_loss'] - m_s['market_avg_log_loss']) < 1e-9, (
                'inline market evaluator drifted from MarketProbabilityEvaluator'
            )
        out['subsets'][subset] = {
            'n_rows_standard': int(rows_s.sum()),
            'n_rows_honest': int(rows_h.sum()),
            'n_dnf_rows_in_honest_pool': int((rows_h & is_dnf).sum()),
            'standard': m_s,
            'honest_adjusted': eval_view(rows_h, adjusted=True),
            'honest_unadjusted': eval_view(rows_h, adjusted=False),
        }
    return out


# ---------------------------------------------------------------------------
# Per-fold context shared across configs (DNF head, DNF'd starter rows)
# ---------------------------------------------------------------------------

def build_fold_ctx(
    fold: Dict[str, str],
    df_base: pd.DataFrame,
    lab: FormFeatureLab,
    labels: pd.DataFrame,
    snaps: pd.DataFrame,
    head_frame: pd.DataFrame,
) -> Dict[str, Any]:
    train_end = pd.to_datetime(fold['train_end'])
    val_end = pd.to_datetime(fold['val_end'])
    _, _, _, test_uncapped = _slice_fold(df_base, fold)

    h_train = head_frame[head_frame['competition_date'] <= train_end]
    h_val = head_frame[
        (head_frame['competition_date'] > train_end)
        & (head_frame['competition_date'] <= val_end)
    ]
    h_test = head_frame[head_frame['competition_date'] > val_end]
    print(f"  [{fold['label']}] training DNF head on {len(h_train):,} starter rows...", flush=True)
    head = DNFPredictor()
    head_info = head.train(h_train, h_val)
    p_test = head.predict_dnf_proba(h_test)
    head_metrics = evaluate_dnf(h_test['dnf'].values, p_test)
    print(
        f"    head: best_iter={head_info['best_iteration']}  "
        f"AUC={head_metrics['auc']:.4f}  LL={head_metrics['log_loss']:.4f}  "
        f"cal={head_metrics['cal_ratio']:.3f}",
        flush=True,
    )
    p_map = dict(
        zip(zip(h_test['competition_id'].values, h_test['rider_id'].values), p_test)
    )

    dnf_rows, excl = build_dnf_pipeline_rows(
        test_uncapped, labels, snaps, str(_DB_PATH), test_period_start=val_end
    )
    print(f"    DNF'd starters scored: {len(dnf_rows):,}  exclusions: {excl}", flush=True)

    if len(dnf_rows):
        dnf_lab = lab.features_for_targets(dnf_rows[['rider_id', 'competition_id']])
        cov = dnf_lab[MERGEABLE_LAB_COLS[0]].notna().mean() if len(dnf_lab) else 0.0
        print(f"    lab features for DNF rows: {len(dnf_lab):,} (v1 coverage {cov:.1%})", flush=True)
    else:
        dnf_lab = pd.DataFrame(columns=['rider_id', 'competition_id'] + ALL_LAB_COLS)

    return {
        'p_map': p_map,
        'dnf_rows_base': dnf_rows,
        'dnf_lab': dnf_lab,
        'head_summary': {
            'best_iteration': head_info['best_iteration'],
            'test_metrics': {
                k: head_metrics[k]
                for k in ('n', 'base_rate', 'mean_pred', 'auc', 'log_loss', 'brier', 'cal_ratio')
                if k in head_metrics
            },
            'n_dnf_rows_scored': int(len(dnf_rows)),
            'exclusions': excl,
        },
    }


# ---------------------------------------------------------------------------
# Per-config run
# ---------------------------------------------------------------------------

def run_config(
    name: str,
    lab_cols: List[str],
    master: pd.DataFrame,
    folds: List[Dict[str, str]],
    fold_ctxs: Dict[str, Dict[str, Any]],
    gt_parts: pd.DataFrame,
    db_path,
) -> Dict[str, Any]:
    """Run all folds for one feature config."""
    drop_cols = [c for c in MERGEABLE_LAB_COLS if c not in lab_cols]
    df = master.drop(columns=drop_cols)
    nan_cols = [c for c in ONEDAY_NAN_COLS.get(name, []) if c in lab_cols]
    if nan_cols:
        df = df.copy()
        df.loc[df['competition_type'] == 'one_day', nan_cols] = np.nan

    fold_outputs = []
    all_records = []

    for i, fold in enumerate(folds):
        train, val, test_year, test_uncapped = _slice_fold(df, fold)
        print(
            f"  [{name}] fold {i + 1}/{len(folds)} (test {fold['label']}): "
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
        market = _market_metrics_uncapped(test_uncapped, bucket_pred, contender_pred)
        market = {k: float(v) for k, v in market.items() if np.isfinite(v)}

        # Honest frame: pool = config's test rows + DNF'd starters carrying
        # this config's lab columns (computed via features_for_targets).
        ctx = fold_ctxs[fold['label']]
        dnf_rows_cfg = ctx['dnf_rows_base']
        if len(dnf_rows_cfg) and lab_cols:
            dnf_rows_cfg = dnf_rows_cfg.merge(
                ctx['dnf_lab'][['rider_id', 'competition_id'] + lab_cols],
                on=['rider_id', 'competition_id'],
                how='left',
            )
            if nan_cols:
                dnf_rows_cfg.loc[
                    dnf_rows_cfg['competition_type'] == 'one_day', nan_cols
                ] = np.nan
        dnf_rows_cfg = dnf_rows_cfg.reindex(columns=list(test_uncapped.columns))
        honest = _honest_eval(
            test_uncapped, dnf_rows_cfg, bucket_pred, contender_pred,
            ctx['p_map'], parity=(name == 'baseline' and i == 0),
        )

        fold_outputs.append({
            'fold_label': fold['label'],
            'training_info': info,
            'lr_temperature': float(lr_pred.config.temperature),
            'standard_metrics_uncapped': std,
            'market_metrics_uncapped': market,
            'honest': honest,
            'lab_ranks_contender': _lab_feature_ranks(contender_pred, lab_cols),
            'lab_ranks_bucket': _lab_feature_ranks(bucket_pred, lab_cols),
        })
        h_all = honest['subsets'].get('all', {})
        h_adj = h_all.get('honest_adjusted', {}).get('market_avg_log_loss', float('nan'))
        print(
            f"    winner={std.get('race_winner_capture_rate', float('nan')):.4f}  "
            f"mkt_avg_ll={market.get('market_avg_log_loss', float('nan')):.4f}  "
            f"honest_adj_ll={h_adj:.4f}  "
            f"log_loss={std.get('top4_log_loss', float('nan')):.4f}",
            flush=True,
        )

    records = pd.concat(all_records, ignore_index=True)
    analysis = analyze(records)
    rec_gt = attach_gt_recency(records.copy(), db_path=db_path, gt=gt_parts)
    gt_tables = gt_band_tables(rec_gt, verbose=False)

    return {
        'config': name,
        'lab_cols': lab_cols,
        'fold_outputs': fold_outputs,
        'age_bias_analysis': analysis,
        'age_bias_indicators': _age_bias_indicators(analysis),
        'gt_recency': gt_tables,
        '_records': records,
    }


# ---------------------------------------------------------------------------
# Aggregation + printing
# ---------------------------------------------------------------------------

def _aggregate(fold_outputs: List[Dict], keys: List[str], getter) -> Dict[str, Dict[str, float]]:
    out = {}
    for k in keys:
        vals = []
        for fo in fold_outputs:
            v = getter(fo).get(k)
            if v is not None and np.isfinite(v):
                vals.append(v)
        if vals:
            out[k] = {
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals)),
                'per_fold': [float(v) for v in vals],
            }
    return out


def _aggregate_standard(fold_outputs: List[Dict]) -> Dict[str, Dict[str, float]]:
    return _aggregate(fold_outputs, STANDARD_KEYS, lambda fo: fo['standard_metrics_uncapped'])


def _aggregate_market(fold_outputs: List[Dict]) -> Dict[str, Dict[str, float]]:
    return _aggregate(fold_outputs, MARKET_KEYS, lambda fo: fo['market_metrics_uncapped'])


def _aggregate_honest(fold_outputs: List[Dict], subset: str, view: str) -> Dict[str, Dict[str, float]]:
    return _aggregate(
        fold_outputs, HONEST_KEYS,
        lambda fo: fo['honest']['subsets'].get(subset, {}).get(view, {}),
    )


def _delta_str(cfg: Dict[str, Dict], base: Dict[str, Dict], k: str) -> str:
    if k not in cfg or k not in base:
        return ''
    n = min(len(cfg[k]['per_fold']), len(base[k]['per_fold']))
    deltas = [cfg[k]['per_fold'][j] - base[k]['per_fold'][j] for j in range(n)]
    pos = sum(1 for d in deltas if d > 0)
    return f"(Δ{np.mean(deltas):+.4f}±{np.std(deltas):.4f}, {pos}/{n} folds +)"


def print_comparison(results: Dict[str, Dict[str, Any]]):
    base = results['baseline']
    base_std = _aggregate_standard(base['fold_outputs'])
    base_mkt = _aggregate_market(base['fold_outputs'])

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
                if name != 'baseline':
                    parts.append(_delta_str(std, base_std, k))
        print("  ".join(parts))

    print("\n" + "=" * 100)
    print("MARKET METRICS (top-15 pool, uncapped test; PRIMARY-adjacent; Δ paired per fold)")
    print("=" * 100)
    for name, res in results.items():
        mkt = _aggregate_market(res['fold_outputs'])
        parts = [f"  {name:<10s}"]
        for k in ('market_avg_log_loss', 'win_log_loss', 'win_cal_ratio'):
            if k in mkt:
                m = mkt[k]
                parts.append(f"{k}={m['mean']:.4f}±{m['std']:.4f}")
                if name != 'baseline':
                    parts.append(_delta_str(mkt, base_mkt, k))
        print("  ".join(parts))

    print("\n" + "=" * 100)
    print("HONEST FRAME (startlist pool, DNF-adjusted) — PRIMARY GATE: market_avg_log_loss")
    print("=" * 100)
    for subset in HONEST_SUBSETS:
        base_h = _aggregate_honest(base['fold_outputs'], subset, 'honest_adjusted')
        if 'market_avg_log_loss' not in base_h:
            continue
        for name, res in results.items():
            h = _aggregate_honest(res['fold_outputs'], subset, 'honest_adjusted')
            if 'market_avg_log_loss' not in h:
                continue
            m = h['market_avg_log_loss']
            line = (f"  {subset:<8s} {name:<10s} "
                    f"honest_adj_mkt_avg_ll={m['mean']:.4f}±{m['std']:.4f}")
            if name != 'baseline':
                line += "  " + _delta_str(h, base_h, 'market_avg_log_loss')
                wc = _delta_str(h, base_h, 'win_cal_ratio')
                if wc:
                    line += f"  win_cal {wc}"
            print(line)
        print()

    print("=" * 100)
    print("GT-RECENCY CALIBRATION (LambdaRank win cal; <1 = underpriced; target: <=45d -> 1.0)")
    print("=" * 100)
    for view, key in (('ALL rows', ('headline', 'all_rows')),
                      ('GC targets', ('subsets', 'gc_targets')),
                      ('Stage targets', ('subsets', 'stage_targets'))):
        print(f"\n  {view}:")
        hdr = f"    {'band':<20s}" + "".join(f"{n:>14s}" for n in results)
        print(hdr)
        bands = list(base['gt_recency'][key[0]][key[1]].keys())
        for b in bands:
            row = f"    {b:<20s}"
            for name in results:
                r = results[name]['gt_recency'][key[0]][key[1]].get(b)
                if r:
                    row += f"{r['cal']:>9.3f} {r['folds_under']}/{r['folds']}"
                else:
                    row += f"{'—':>14s}"
            print(row)
    print("\n  Contender head (top-15 rows):")
    hdr = f"    {'band':<20s}" + "".join(f"{n:>10s}" for n in results)
    print(hdr)
    for b in list(base['gt_recency']['subsets']['contender_head'].keys()):
        row = f"    {b:<20s}"
        for name in results:
            r = results[name]['gt_recency']['subsets']['contender_head'].get(b)
            row += f"{r['cal']:>10.3f}" if r else f"{'—':>10s}"
        print(row)

    print("\n" + "=" * 100)
    print("AGE-BIAS INDICATORS (pooled test years; cal >1 = overestimates band)")
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = [a for a in sys.argv[1:]]
    smoke = '--smoke' in args
    names = [a for a in args if not a.startswith('--')]
    if not names:
        names = ['baseline', 'v5v6'] if smoke else DEFAULT_CONFIGS
    if 'baseline' not in names:
        names = ['baseline'] + names
    unknown = [n for n in names if n not in CONFIG_REGISTRY]
    if unknown:
        raise SystemExit(f"Unknown configs: {unknown}. Known: {list(CONFIG_REGISTRY)}")
    configs = {n: CONFIG_REGISTRY[n] for n in names}
    folds = list(FOLDS)
    start_date = abb.START_DATE

    if smoke:
        print("*** SMOKE MODE: 1 fold, 2022+ data, small estimator budgets ***", flush=True)
        folds = [FOLDS[-1]]
        start_date = '2022-01-01'
        abb.CONTENDER_CONFIG['n_estimators'] = 120
        abb.CONTENDER_CONFIG['early_stopping'] = 30
        abb.LAMBDARANK_MAIN_CONFIG['n_estimators'] = 200
        abb.LAMBDARANK_MAIN_CONFIG['early_stopping_rounds'] = 50

    print("=" * 70, flush=True)
    print("FORM FEATURE SWEEP — round 2: GT-aware form (v5 contested / v6 scoped)")
    print(f"Configs: {list(configs)}   folds: {[f['label'] for f in folds]}")
    print("=" * 70, flush=True)
    started = datetime.now()
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    df = _load_full_df()
    if smoke:
        df = df[df['competition_date'] >= start_date].copy()
    print(f"Loaded {len(df):,} training rows", flush=True)

    lab = FormFeatureLab()
    feats = lab.build_or_load()
    merge_cols = ['rider_id', 'competition_id'] + MERGEABLE_LAB_COLS
    print(f"Lab features: {len(feats):,} rows; merging {len(MERGEABLE_LAB_COLS)} cols "
          f"(v2/v3 excluded — already in production frame)", flush=True)

    master = df.merge(feats[merge_cols], on=['rider_id', 'competition_id'], how='left')
    matched = master['v1_form_n5'].notna()
    print(f"Merge coverage: {matched.mean():.1%} of training rows", flush=True)

    # ---- DNF head inputs (fold-independent) ----
    print("Loading DNF labels + building head feature frame...", flush=True)
    labels = load_labels()
    labels = labels[labels['competition_date'].notna() & labels['rider_id'].notna()].copy()
    labels['rider_id'] = labels['rider_id'].astype('int64')
    labels = add_asof_dates(labels)
    snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=labels, snaps=snaps, start_date=start_date)
    head_frame['competition_date'] = pd.to_datetime(head_frame['competition_date'])
    print(f"  head frame: {len(head_frame):,} rows, DNF rate {head_frame['dnf'].mean():.4f}", flush=True)

    # ---- per-fold shared context (DNF head + DNF'd starter rows + lab feats) ----
    print("\nBuilding per-fold context (shared across configs)...", flush=True)
    df_base = df  # production frame, no lab cols
    fold_ctxs = {
        fold['label']: build_fold_ctx(fold, df_base, lab, labels, snaps, head_frame)
        for fold in folds
    }

    gt_parts = load_gt_participations(Path(lab.db_path))
    print(f"GT participations (diagnostic): {len(gt_parts):,}", flush=True)

    results: Dict[str, Dict[str, Any]] = {}
    for name, cols in configs.items():
        print(f"\n{'─' * 60}", flush=True)
        print(f"CONFIG: {name} (+{len(cols)} lab cols)", flush=True)
        print(f"{'─' * 60}", flush=True)
        results[name] = run_config(
            name, cols, master, folds, fold_ctxs, gt_parts, Path(lab.db_path)
        )

    print_comparison(results)

    ended = datetime.now()
    timestamp = ended.strftime('%Y%m%d_%H%M%S')
    tag = 'smoke_' if smoke else ''
    out_dir = Path('experiments')
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, res in results.items():
        rec_path = out_dir / f"form_sweep_{tag}records_{name}_{timestamp}.csv.gz"
        res.pop('_records').to_csv(rec_path, index=False, compression='gzip')
        res['records_file'] = str(rec_path)

    out = {
        'started_at': started.isoformat(),
        'ended_at': ended.isoformat(),
        'duration_seconds': (ended - started).total_seconds(),
        'smoke': smoke,
        'folds': folds,
        'dnf_head_per_fold': {
            label: ctx['head_summary'] for label, ctx in fold_ctxs.items()
        },
        'configs': {k: v for k, v in configs.items()},
        'results': results,
    }
    out_path = out_dir / f"form_feature_sweep_{tag}{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nResults saved to {out_path}", flush=True)
    print(f"Total runtime: {(ended - started).total_seconds() / 60:.1f} min", flush=True)


if __name__ == '__main__':
    main()
