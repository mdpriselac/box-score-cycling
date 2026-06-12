"""
DNF market adjustment CV — does multiplying the production heads' market
probabilities by P(finish) from the DNF head improve market probability
quality? (probability gate, 2026-06-11 policy)

The production stack emits P(market | finished): rider_results holds only
finishers, so DNF'd starters never appear at train or eval time and every
market probability is silently conditioned on finishing. Honest market
probability = P(market | finish) * P(finish).

Per fold (FOLDS from stacked_meta_learner_cv_5fold):
  1. Train baseline bucket + contender on train/val (production config).
  2. Train the DNF head on that fold's train years only (val = early stop) —
     OOF-safe w.r.t. test.
  3. Evaluate test in four views (subsets: all / one_day / stage / gc):
       (a) standard          finisher-only top-15 pool, raw conditional
                             probabilities (exactly today's eval).
       (b) same-rows adj.    same rows as (a); markets multiplied by
                             p_finish, win renormalized within race to
                             preserve the race's win-probability book.
       (c) honest adjusted   DNF-inclusive pool: finishers + DNF'd starters
                             scored through the same pipeline (prior
                             snapshot, races_career >= 10 parity filter),
                             ranked together, top-15; adjusted markets; DNF
                             rows lose every market.
       (d) honest unadjusted same rows as (c), raw conditional markets —
                             the paired control for (c).

  (a) vs (b) share rows/labels -> directly comparable.
  (c) vs (d) share rows/labels -> directly comparable.
  (a)/(b) vs (c)/(d) are DIFFERENT row sets — labeled, never differenced.

DNF'd rider feature rows: competition-level columns copied from a finisher
row of the same competition (constant within competition); rider columns
from the rider's latest snapshot STRICTLY before the competition (race start
date for gc comps); age recomputed from riders.birth_year; place_bucket set
to a sentinel 6 purely so the predictors' prepare_features (astype(int))
accepts the rows — predictions never read the target. Exclusions counted.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.data_pipeline import CyclingDataPipeline
from cycling_project.prediction_tools.dnf_predictor import (
    DNFPredictor,
    add_asof_dates,
    attach_prior_snapshots,
    build_feature_frame,
    load_labels,
    load_snapshot_table,
    evaluate_dnf,
    _DB_PATH,
)
from cycling_project.prediction_tools.evaluation import MarketProbabilityEvaluator
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    START_DATE,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
TOP_N = 15
MIN_RACES_CAREER = 10  # pipeline parity filter for DNF'd starters

MARKETS = MarketProbabilityEvaluator.MARKETS  # {'win': [0], 'podium': [0,1], ...}
SUBSETS = ("all", "one_day", "stage", "gc")


# ---------------------------------------------------------------------------
# Inline market evaluator (DNF-aware)
# ---------------------------------------------------------------------------

def market_metrics(
    market_p: Dict[str, np.ndarray],
    y_bucket: np.ndarray,
    is_dnf: np.ndarray,
) -> Dict[str, float]:
    """MarketProbabilityEvaluator semantics, with explicit market vectors and
    DNF rows losing every market."""
    eps = 1e-12
    out: Dict[str, float] = {"n_evaluated": int(len(y_bucket))}
    lls, brs = [], []
    for market, classes in MARKETS.items():
        p = np.clip(market_p[market], eps, 1 - eps)
        y = (np.isin(y_bucket, classes) & ~is_dnf).astype(float)
        ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        br = float(np.mean((p - y) ** 2))
        out[f"{market}_log_loss"] = ll
        out[f"{market}_brier"] = br
        out[f"{market}_cal_ratio"] = float(p.sum() / max(y.sum(), 1.0))
        lls.append(ll)
        brs.append(br)
    out["market_avg_log_loss"] = float(np.mean(lls))
    out["market_avg_brier"] = float(np.mean(brs))
    return out


def proba_to_markets(proba: np.ndarray) -> Dict[str, np.ndarray]:
    return {m: proba[:, cls].sum(axis=1) for m, cls in MARKETS.items()}


def adjust_markets(
    market_p: Dict[str, np.ndarray],
    p_finish: np.ndarray,
    comp_ids: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Multiply every market by p_finish; renormalize the win market within
    each race so the race's total win probability is preserved."""
    adj = {m: market_p[m] * p_finish for m in market_p}
    s = pd.Series(market_p["win"]).groupby(pd.Series(comp_ids)).transform("sum")
    s_adj = pd.Series(adj["win"]).groupby(pd.Series(comp_ids)).transform("sum")
    adj["win"] = adj["win"] * (s.values / np.maximum(s_adj.values, 1e-12))
    return adj


# ---------------------------------------------------------------------------
# DNF'd-starter pipeline rows
# ---------------------------------------------------------------------------

def build_dnf_pipeline_rows(
    test_df: pd.DataFrame,
    labels: pd.DataFrame,
    snaps: pd.DataFrame,
    db_path: str,
    test_period_start: pd.Timestamp,
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """DNF'd starters of test competitions as pipeline-compatible rows."""
    rider_cols = list(CyclingDataPipeline.RIDER_FEATURE_COLS)
    target_cols = ["place_bucket", "time_gap"]
    comp_cols = [
        c for c in test_df.columns
        if c not in rider_cols + target_cols + ["competition_id"]
    ]

    excl = {
        "comp_not_in_test_df": 0, "already_finisher_row": 0,
        "no_prior_snapshot": 0, "career_lt_10": 0,
    }

    test_comps = set(test_df["competition_id"].unique())
    cand = labels[
        (labels["started"] == 1) & (labels["dnf"] == 1) & labels["rider_id"].notna()
        & (pd.to_datetime(labels["competition_date"]) > test_period_start)
    ].copy()
    cand["rider_id"] = cand["rider_id"].astype("int64")
    in_test = cand["competition_id"].isin(test_comps)
    excl["comp_not_in_test_df"] = int((~in_test).sum())
    cand = cand[in_test]

    seen = set(zip(test_df["competition_id"].values, test_df["rider_id"].values))
    dup = [
        (c, r) in seen
        for c, r in zip(cand["competition_id"].values, cand["rider_id"].values)
    ]
    excl["already_finisher_row"] = int(np.sum(dup))
    cand = cand[~np.array(dup, dtype=bool)] if len(cand) else cand

    if len(cand) == 0:
        return pd.DataFrame(columns=list(test_df.columns)), excl

    # latest snapshot strictly before the (race-start anchored) date
    cand = attach_prior_snapshots(cand, snaps, "asof_date", columns=None)
    no_snap = cand["races_career"].isna()
    excl["no_prior_snapshot"] = int(no_snap.sum())
    cand = cand[~no_snap]
    lt10 = cand["races_career"] < MIN_RACES_CAREER
    excl["career_lt_10"] = int(lt10.sum())
    cand = cand[~lt10]
    if len(cand) == 0:
        return pd.DataFrame(columns=list(test_df.columns)), excl

    # recompute age at the target competition
    with sqlite3.connect(db_path) as conn:
        birth = pd.read_sql_query("SELECT id AS rider_id, birth_year FROM riders", conn)
    cand = cand.merge(birth, on="rider_id", how="left")
    comp_year = pd.to_datetime(cand["competition_date"]).dt.year
    cand["age"] = np.where(
        cand["birth_year"].notna(), comp_year - cand["birth_year"], cand["age"]
    )

    # competition-level template from finisher rows (constant within comp)
    template = test_df.groupby("competition_id")[comp_cols].first()
    out = cand[["competition_id"]].join(template, on="competition_id")
    for c in rider_cols:
        out[c] = cand[c].values
    out["place_bucket"] = 6      # sentinel; predictors' astype(int) — never read
    out["time_gap"] = np.nan
    out = out.reindex(columns=list(test_df.columns))
    return out.reset_index(drop=True), excl


# ---------------------------------------------------------------------------
# Per-fold evaluation
# ---------------------------------------------------------------------------

def run_fold(
    fold: Dict[str, str],
    df: pd.DataFrame,
    head_frame: pd.DataFrame,
    labels: pd.DataFrame,
    snaps: pd.DataFrame,
    parity_check: bool,
) -> Dict[str, Any]:
    train, val, test = _slice_fold(df, fold)
    if len(test) == 0:
        return {"fold_label": fold["label"], "skipped": True}
    print(
        f"  train {len(train):,} | val {len(val):,} | test {len(test):,} rows "
        f"({test['competition_id'].nunique():,} comps)",
        flush=True,
    )

    # ---- production stack ----
    print("  Training baseline bucket + contender...", flush=True)
    bucket, cont, _ = _train_bucket_and_contender(train, val, fold["label"])

    # ---- DNF head (fold-safe) ----
    train_end = pd.to_datetime(fold["train_end"])
    val_end = pd.to_datetime(fold["val_end"])
    h_train = head_frame[head_frame["competition_date"] <= train_end]
    h_val = head_frame[
        (head_frame["competition_date"] > train_end)
        & (head_frame["competition_date"] <= val_end)
    ]
    h_test = head_frame[head_frame["competition_date"] > val_end]
    print(f"  Training DNF head on {len(h_train):,} starter rows...", flush=True)
    head = DNFPredictor()
    head_info = head.train(h_train, h_val)
    head_test_metrics = evaluate_dnf(
        h_test["dnf"].values, head.predict_dnf_proba(h_test)
    )
    print(
        f"    head: best_iter={head_info['best_iteration']}  "
        f"test AUC={head_test_metrics['auc']:.4f}  LL={head_test_metrics['log_loss']:.4f}",
        flush=True,
    )

    # p_dnf for every started (comp, rider) of the test period
    p_map = dict(
        zip(
            zip(h_test["competition_id"].values, h_test["rider_id"].values),
            head.predict_dnf_proba(h_test),
        )
    )

    # ---- DNF'd starters as pipeline rows ----
    dnf_rows, excl = build_dnf_pipeline_rows(
        test, labels, snaps, str(_DB_PATH), test_period_start=val_end
    )
    print(
        f"  DNF'd starters scored: {len(dnf_rows):,}  exclusions: {excl}",
        flush=True,
    )

    pool = pd.concat(
        [test.assign(is_dnf_row=0), dnf_rows.assign(is_dnf_row=1)],
        ignore_index=True,
    )

    # ---- predictions ----
    print("  Bucket + contender predictions on pool...", flush=True)
    pool["classifier_expected_bucket"] = bucket.predict_continuous(pool)
    fin_mask = pool["is_dnf_row"] == 0
    pool["_rank_fin"] = (
        pool[fin_mask]
        .groupby("competition_id")["classifier_expected_bucket"]
        .rank()
    )
    pool["_rank_pool"] = pool.groupby("competition_id")[
        "classifier_expected_bucket"
    ].rank()
    sel_a = fin_mask & (pool["_rank_fin"] <= TOP_N)
    sel_c = pool["_rank_pool"] <= TOP_N
    need = sel_a | sel_c

    cd = pool[need].copy()
    proba = cont.predict_proba(cd)
    n_classes = cont.config.lgb_params.get("num_class", 8)
    y_bucket = np.clip(cd["place_bucket"].values.astype(int), 0, n_classes - 1)
    is_dnf = cd["is_dnf_row"].values.astype(bool)

    keys = list(zip(cd["competition_id"].values, cd["rider_id"].values))
    p_dnf = np.array([p_map.get(k, 0.0) for k in keys])
    head_missing = int(np.sum([k not in p_map for k in keys]))
    p_finish = 1.0 - p_dnf

    raw = proba_to_markets(proba)
    comp_ids = cd["competition_id"].values
    in_a = sel_a.values[need.values]
    in_c = sel_c.values[need.values]

    # one adjusted book per view, renormalized within its own row set
    def eval_view(rows: np.ndarray, adjusted: bool) -> Dict[str, float]:
        mp = {m: raw[m][rows] for m in raw}
        if adjusted:
            mp = adjust_markets(mp, p_finish[rows], comp_ids[rows])
        return market_metrics(mp, y_bucket[rows], is_dnf[rows])

    result: Dict[str, Any] = {
        "fold_label": fold["label"],
        "skipped": False,
        "head": {
            "best_iteration": head_info["best_iteration"],
            "test_auc": head_test_metrics["auc"],
            "test_log_loss": head_test_metrics["log_loss"],
            "test_cal_ratio": head_test_metrics["cal_ratio"],
        },
        "exclusions": {**excl, "head_pred_missing_rows": head_missing},
        "subsets": {},
    }

    ctype = cd["competition_type"].values
    for subset in SUBSETS:
        smask = np.ones(len(cd), dtype=bool) if subset == "all" else (ctype == subset)
        rows_a = in_a & smask
        rows_c = in_c & smask
        if rows_a.sum() == 0:
            continue

        m_a = eval_view(rows_a, adjusted=False)
        if parity_check and subset == "all":
            ref = MarketProbabilityEvaluator.evaluate(y_bucket[rows_a], proba[rows_a])
            assert abs(ref["market_avg_log_loss"] - m_a["market_avg_log_loss"]) < 1e-9, (
                "inline market evaluator drifted from MarketProbabilityEvaluator"
            )
        result["subsets"][subset] = {
            "n_rows_standard": int(rows_a.sum()),
            "n_rows_honest": int(rows_c.sum()),
            "n_dnf_rows_in_honest_pool": int((rows_c & is_dnf).sum()),
            "standard": m_a,
            "same_rows_adjusted": eval_view(rows_a, adjusted=True),
            "honest_adjusted": eval_view(rows_c, adjusted=True),
            "honest_unadjusted": eval_view(rows_c, adjusted=False),
        }

    s = result["subsets"]["all"]
    print(
        f"  all: std={s['standard']['market_avg_log_loss']:.4f}  "
        f"adj(same rows)={s['same_rows_adjusted']['market_avg_log_loss']:.4f} "
        f"(Δ{s['same_rows_adjusted']['market_avg_log_loss'] - s['standard']['market_avg_log_loss']:+.4f})  |  "
        f"honest: unadj={s['honest_unadjusted']['market_avg_log_loss']:.4f}  "
        f"adj={s['honest_adjusted']['market_avg_log_loss']:.4f} "
        f"(Δ{s['honest_adjusted']['market_avg_log_loss'] - s['honest_unadjusted']['market_avg_log_loss']:+.4f})  "
        f"[honest pool: {s['n_rows_honest']:,} rows, {s['n_dnf_rows_in_honest_pool']:,} DNF]",
        flush=True,
    )
    return result


# ---------------------------------------------------------------------------
# Aggregation + main
# ---------------------------------------------------------------------------

DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "top15_cal_ratio",
]


def aggregate(fold_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg: Dict[str, Any] = {}
    pairs = [
        ("same_rows_adjusted_minus_standard", "same_rows_adjusted", "standard"),
        ("honest_adjusted_minus_unadjusted", "honest_adjusted", "honest_unadjusted"),
    ]
    for subset in SUBSETS:
        agg[subset] = {}
        for name, a_key, b_key in pairs:
            agg[subset][name] = {}
            for k in DELTA_METRICS:
                deltas = [
                    fr["subsets"][subset][a_key][k] - fr["subsets"][subset][b_key][k]
                    for fr in usable
                    if subset in fr["subsets"]
                ]
                if deltas:
                    agg[subset][name][k] = {
                        "mean": float(np.mean(deltas)),
                        "std": float(np.std(deltas)),
                        "per_fold": [float(d) for d in deltas],
                    }
        # absolute levels for the honest view (not comparable to standard)
        for key in ("standard", "same_rows_adjusted", "honest_unadjusted", "honest_adjusted"):
            vals = [
                fr["subsets"][subset][key]["market_avg_log_loss"]
                for fr in usable
                if subset in fr["subsets"]
            ]
            if vals:
                agg[subset][f"level_{key}_market_avg_log_loss"] = {
                    "mean": float(np.mean(vals)),
                    "std": float(np.std(vals)),
                }
    return agg


def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("DNF MARKET ADJUSTMENT CV — P(market|finish) x P(finish) vs status quo", flush=True)
    print("=" * 70, flush=True)

    print("Loading production training frame...", flush=True)
    df = _load_full_df()
    print(f"  {len(df):,} rows", flush=True)

    print("Loading DNF labels + building head feature frame...", flush=True)
    labels = load_labels()
    labels = labels[labels["competition_date"].notna() & labels["rider_id"].notna()].copy()
    labels["rider_id"] = labels["rider_id"].astype("int64")
    labels = add_asof_dates(labels)
    snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=labels, snaps=snaps, start_date=START_DATE)
    head_frame["competition_date"] = pd.to_datetime(head_frame["competition_date"])
    print(
        f"  head frame: {len(head_frame):,} rows, DNF rate {head_frame['dnf'].mean():.4f}",
        flush=True,
    )

    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}\nFOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)\n{'─' * 60}", flush=True)
        fold_results.append(
            run_fold(fold, df, head_frame, labels, snaps, parity_check=(i == 0))
        )

    agg = aggregate(fold_results)
    print("\n" + "=" * 70, flush=True)
    print("PAIRED DELTAS (mean±std over folds)", flush=True)
    print("=" * 70, flush=True)
    for subset in SUBSETS:
        for name in ("same_rows_adjusted_minus_standard", "honest_adjusted_minus_unadjusted"):
            d = agg[subset].get(name, {}).get("market_avg_log_loss")
            if d:
                print(
                    f"  {subset:<8s} {name:<38s} {d['mean']:+.4f}±{d['std']:.4f}  "
                    f"per-fold: {' '.join(f'{x:+.4f}' for x in d['per_fold'])}",
                    flush=True,
                )

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {
            "folds": FOLDS, "start_date": START_DATE, "top_n": TOP_N,
            "min_races_career_dnf_rows": MIN_RACES_CAREER,
            "win_renormalized": True,
            "notes": (
                "standard vs same_rows_adjusted share rows; honest_* share rows; "
                "standard and honest_* are different row sets and never differenced"
            ),
        },
        "fold_results": fold_results,
        "aggregated": agg,
    }
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"dnf_market_adjustment_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended - started).total_seconds() / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
