"""
Full-stack production-integration gate — additivity test for the three
candidates that passed the probability gate separately on 2026-06-11.

Arms (per fold, paired; 5 folds from the shared FOLDS):
  A baseline — production stack as-is.
  B combined — meta-OOF features (oof_time_gap_pred, oof_lambdarank_win_p)
               + one-day-scoped signature features (11 cols, stage rows NaN).
               Replicates probability_gate_combined_cv's passing arm.
  C full     — B + the 4 contested-Elo columns (contested_rating,
               contested_rating_n, contested_rating_delta90,
               contested_rating_vs_field), as-of-then from
               experiments/contested_rating_snapshots.parquet.

OOF features are generated ONCE per fold and reused for B and C. Every arm
is evaluated with MarketProbabilityEvaluator (top-15 contender pool) on
subsets all / one_day / stage, with winner/podium capture as diagnostics.

Extras:
  - Win-market blend overlay (w=0.2 mc x calibrated LambdaRank, per-race
    book-sum preserved) for arms A and C.
  - Honest-pool DNF-adjusted evaluation for arms A and C: DNF head trained
    per fold on train years (val = early stop), P(market|finish) x P(finish)
    on the DNF-inclusive pool, exactly as dnf_market_adjustment_cv.
    Arm C's honest pool re-derives all C features on the pooled frame
    (finishers + DNF'd starters), which mirrors serving (startlist-level
    LR softmax / field means).
  - CALIBRATION WATCH-ITEM: absolute win/podium cal-ratio levels per arm
    per subset, plus a scalar win-book temperature refit for arm C
    (p^(1/T) renormalized to sum 1 per race, T fit on each fold's VAL
    win market by NLL; test win_log_loss + win_cal_ratio before/after).
    Reported for every fold; flagged "triggered" when arm C's one_day
    win_cal_ratio < 0.95.

Outputs experiments/full_stack_integration_cv_<ts>.json with per-fold and
aggregated paired deltas (B-A, C-B, C-A).

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.full_stack_integration_cv
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from cycling_project.prediction_tools.contested_rating import (
    DEFAULT_DB_PATH,
    DEFAULT_SNAPSHOT_PATH,
    RATING_FEATURE_COLS,
    attach_rating_features,
    build_and_save,
    load_snapshots,
)
from cycling_project.prediction_tools.dnf_predictor import (
    DNFPredictor,
    add_asof_dates,
    build_feature_frame,
    evaluate_dnf,
    load_labels,
    load_snapshot_table,
)
from cycling_project.prediction_tools.evaluation import (
    MarketProbabilityEvaluator,
    Top4ProbabilityEvaluator,
)
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    ARCH,
    attach,
    load_signature_table,
    oneday_b4,
)
from cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv import (
    SUBSETS as HONEST_SUBSETS,
    TOP_N,
    adjust_markets,
    build_dnf_pipeline_rows,
    market_metrics,
    proba_to_markets,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    META_FEATURE_COLS,
    START_DATE,
    _generate_oof_lambdarank_winp,
    _generate_oof_time_gap,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
    _train_main_lambdarank,
    _train_main_time_gap,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
BLEND_W = 0.2
CAL_TRIGGER = 0.95          # one_day win_cal_ratio threshold for the watch item
TEMP_BOUNDS = (0.25, 4.0)

ARMS = ("A", "B", "C")
ARM_DESC = {
    "A": "baseline (production stack)",
    "B": "meta-OOF + one-day signatures",
    "C": "B + contested-Elo (4 cols)",
}
EVAL_SUBSETS = ("all", "one_day", "stage")
PAIRS = [("B_minus_A", "B", "A"), ("C_minus_B", "C", "B"), ("C_minus_A", "C", "A")]
DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "podium_cal_ratio",
    "race_winner_capture_rate", "race_podium_capture_rate",
    "blend_win_log_loss",
]
CAL_METRICS = ["win_cal_ratio", "podium_cal_ratio"]
HONEST_DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "top15_log_loss", "win_cal_ratio",
]
TRACKED_FEATURES = list(META_FEATURE_COLS) + list(RATING_FEATURE_COLS) + [
    "rider_contest_fit", "sig_wg_prop", "rider_sig_share",
]


# ---------------------------------------------------------------------------
# Pool construction + per-arm market evaluation
# ---------------------------------------------------------------------------

def contender_pool(df: pd.DataFrame, bucket) -> pd.DataFrame:
    d = df.copy()
    d["classifier_expected_bucket"] = bucket.predict_continuous(d)
    d["_rank"] = d.groupby("competition_id")["classifier_expected_bucket"].rank()
    return d[d["_rank"] <= TOP_N].drop(columns=["_rank"])


def eval_arm(
    test_df: pd.DataFrame, bucket, cont, lr_model=None
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, np.ndarray]]]:
    """Market metrics + capture per subset.

    Returns (metrics_by_subset, win_pools); win_pools holds the win-market
    vectors per subset for the temperature refit. When lr_model is given,
    the w=0.2 blend overlay (per-race mc book sum preserved) is added.
    """
    out: Dict[str, Any] = {}
    pools: Dict[str, Dict[str, np.ndarray]] = {}
    for name in EVAL_SUBSETS:
        sub = test_df if name == "all" else test_df[test_df["competition_type"] == name]
        if len(sub) == 0:
            continue
        cd = contender_pool(sub, bucket)
        proba = cont.predict_proba(cd)
        n_classes = cont.config.lgb_params.get("num_class", 8)
        y = cd["place_bucket"].values
        if n_classes < 8:
            y = np.clip(y, 0, n_classes - 1)
        m = MarketProbabilityEvaluator.evaluate(y, proba)
        t4 = Top4ProbabilityEvaluator.evaluate(
            y, proba, competition_ids=cd["competition_id"].values
        )
        for k in ("race_winner_capture_rate", "race_podium_capture_rate"):
            if k in t4:
                m[k] = t4[k]

        comp_ids = cd["competition_id"].to_numpy()
        win_p = proba[:, 0]
        y_win = (y == 0).astype(float)
        pools[name] = {"win_p": win_p, "y_win": y_win, "comp_ids": comp_ids}

        if lr_model is not None:
            lr_p = np.asarray(lr_model.predict_win_probabilities(cd))
            bl = BLEND_W * win_p + (1 - BLEND_W) * lr_p
            s = pd.Series(bl, index=cd.index)
            s = s / s.groupby(cd["competition_id"]).transform("sum") * \
                pd.Series(win_p, index=cd.index).groupby(cd["competition_id"]).transform("sum")
            p = np.clip(s.to_numpy(), 1e-12, 1 - 1e-12)
            m["blend_win_log_loss"] = float(
                -np.mean(y_win * np.log(p) + (1 - y_win) * np.log(1 - p))
            )
            m["blend_win_cal_ratio"] = float(p.sum() / max(y_win.sum(), 1.0))
        out[name] = m
    return out, pools


# ---------------------------------------------------------------------------
# Win-book temperature refit (watch item)
# ---------------------------------------------------------------------------

def _apply_win_temperature(p: np.ndarray, comp_ids: np.ndarray, T: float) -> np.ndarray:
    q = np.clip(p, 1e-12, 1.0) ** (1.0 / T)
    qs = pd.Series(q).groupby(pd.Series(comp_ids)).transform("sum").to_numpy()
    return np.clip(q / np.maximum(qs, 1e-12), 1e-12, 1 - 1e-12)


def _win_metrics(p: np.ndarray, y_win: np.ndarray) -> Dict[str, float]:
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return {
        "win_log_loss": float(-np.mean(y_win * np.log(p) + (1 - y_win) * np.log(1 - p))),
        "win_cal_ratio": float(p.sum() / max(y_win.sum(), 1.0)),
    }


def fit_win_temperature(
    p: np.ndarray, y_win: np.ndarray, comp_ids: np.ndarray
) -> Tuple[float, float]:
    def nll(T: float) -> float:
        q = _apply_win_temperature(p, comp_ids, T)
        return float(-np.mean(y_win * np.log(q) + (1 - y_win) * np.log(1 - q)))

    res = minimize_scalar(nll, bounds=TEMP_BOUNDS, method="bounded")
    return float(res.x), float(nll(float(res.x)))


def temperature_refit_block(
    val_pools: Dict[str, Dict[str, np.ndarray]],
    test_pools: Dict[str, Dict[str, np.ndarray]],
) -> Dict[str, Any]:
    """Fit T on the VAL win book per subset; report test before/after."""
    out: Dict[str, Any] = {}
    for subset in EVAL_SUBSETS:
        if subset not in val_pools or subset not in test_pools:
            continue
        v, t = val_pools[subset], test_pools[subset]
        T, val_nll = fit_win_temperature(v["win_p"], v["y_win"], v["comp_ids"])
        before = _win_metrics(t["win_p"], t["y_win"])
        after = _win_metrics(
            _apply_win_temperature(t["win_p"], t["comp_ids"], T), t["y_win"]
        )
        out[subset] = {"T": T, "val_nll_at_T": val_nll, "before": before, "after": after}
    return out


# ---------------------------------------------------------------------------
# Honest-pool DNF-adjusted evaluation (arms A and C)
# ---------------------------------------------------------------------------

def honest_eval(pool_df: pd.DataFrame, bucket, cont, p_map, parity: bool = False) -> Dict[str, Any]:
    """dnf_market_adjustment_cv's four views, on a prebuilt arm pool frame.

    pool_df = test rows (is_dnf_row=0) + DNF'd-starter rows (is_dnf_row=1),
    already carrying every feature column the arm's models expect.
    """
    pool = pool_df.copy()
    pool["classifier_expected_bucket"] = bucket.predict_continuous(pool)
    fin_mask = pool["is_dnf_row"] == 0
    pool["_rank_fin"] = (
        pool[fin_mask].groupby("competition_id")["classifier_expected_bucket"].rank()
    )
    pool["_rank_pool"] = pool.groupby("competition_id")["classifier_expected_bucket"].rank()
    sel_std = fin_mask & (pool["_rank_fin"] <= TOP_N)
    sel_hon = pool["_rank_pool"] <= TOP_N
    need = sel_std | sel_hon

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
    in_std = sel_std.values[need.values]
    in_hon = sel_hon.values[need.values]
    ctype = cd["competition_type"].values

    def eval_view(rows: np.ndarray, adjusted: bool) -> Dict[str, float]:
        mp = {m: raw[m][rows] for m in raw}
        if adjusted:
            mp = adjust_markets(mp, p_finish[rows], comp_ids[rows])
        return market_metrics(mp, y_bucket[rows], is_dnf[rows])

    out: Dict[str, Any] = {"head_pred_missing_rows": head_missing, "subsets": {}}
    for subset in HONEST_SUBSETS:
        smask = np.ones(len(cd), dtype=bool) if subset == "all" else (ctype == subset)
        rows_s = in_std & smask
        rows_h = in_hon & smask
        if rows_s.sum() == 0:
            continue
        m_s = eval_view(rows_s, adjusted=False)
        if parity and subset == "all":
            ref = MarketProbabilityEvaluator.evaluate(y_bucket[rows_s], proba[rows_s])
            assert abs(ref["market_avg_log_loss"] - m_s["market_avg_log_loss"]) < 1e-9, (
                "inline market evaluator drifted from MarketProbabilityEvaluator"
            )
        out["subsets"][subset] = {
            "n_rows_standard": int(rows_s.sum()),
            "n_rows_honest": int(rows_h.sum()),
            "n_dnf_rows_in_honest_pool": int((rows_h & is_dnf).sum()),
            "standard": m_s,
            "same_rows_adjusted": eval_view(rows_s, adjusted=True),
            "honest_adjusted": eval_view(rows_h, adjusted=True),
            "honest_unadjusted": eval_view(rows_h, adjusted=False),
        }
    return out


# ---------------------------------------------------------------------------
# Feature-importance ranks for the tracked candidate features (arm C)
# ---------------------------------------------------------------------------

def tracked_feature_ranks(cont) -> Optional[Dict[str, Any]]:
    try:
        imp_df = cont.get_feature_importance(importance_type="gain")
    except Exception as exc:  # pragma: no cover
        print(f"    [warn] feature importance unavailable: {exc}", flush=True)
        return None
    imp = dict(zip(imp_df["feature"], imp_df["importance"].astype(float)))
    order = sorted(imp.items(), key=lambda kv: kv[1], reverse=True)
    pos = {k: i + 1 for i, (k, _) in enumerate(order)}
    ranks: Dict[str, Any] = {"n_features": len(order)}
    for f in TRACKED_FEATURES:
        ranks[f] = {"rank": pos.get(f), "gain": imp.get(f)}
    return ranks


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(
    i: int,
    fold: Dict[str, str],
    df: pd.DataFrame,
    df_rated: pd.DataFrame,
    od_feats: pd.DataFrame,
    field_shares: pd.DataFrame,
    rating_snaps: pd.DataFrame,
    labels: pd.DataFrame,
    dnf_snaps: pd.DataFrame,
    head_frame: pd.DataFrame,
) -> Dict[str, Any]:
    train, val, test = _slice_fold(df, fold)
    train_r, val_r, test_r = _slice_fold(df_rated, fold)
    if len(test) == 0:
        return {"fold_label": fold["label"], "skipped": True}
    print(
        f"  train {len(train):,} | val {len(val):,} | test {len(test):,} rows "
        f"({test['competition_id'].nunique():,} comps; test rating coverage "
        f"{test_r['contested_rating'].notna().mean():.1%})",
        flush=True,
    )

    # ---- OOF features + main base models (generated ONCE, reused B + C) ----
    print("  OOF time_gap (5 sub-folds)...", flush=True)
    oof_tg = _generate_oof_time_gap(train, val)
    print("  OOF LambdaRank (5 sub-folds)...", flush=True)
    oof_lr = _generate_oof_lambdarank_winp(train, val)
    print("  Main time-gap + LambdaRank base models...", flush=True)
    main_tg = _train_main_time_gap(train, val)
    main_lr = _train_main_lambdarank(train, val)
    print(f"    LR temperature: {main_lr.config.temperature:.3f}", flush=True)

    # ---- Arm B frames: one-day sigs + meta-OOF ----
    train_b = attach(train, od_feats, field_shares)
    val_b = attach(val, od_feats, field_shares)
    test_b = attach(test, od_feats, field_shares)
    train_b["oof_time_gap_pred"] = oof_tg
    train_b["oof_lambdarank_win_p"] = oof_lr
    val_b["oof_time_gap_pred"] = main_tg.predict(val_b)
    val_b["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(val_b))
    test_b["oof_time_gap_pred"] = main_tg.predict(test_b)
    test_b["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(test_b))

    # ---- Arm C frames: B + 4 contested-Elo columns ----
    for bf, rf in ((train_b, train_r), (val_b, val_r), (test_b, test_r)):
        assert len(bf) == len(rf)
        assert (bf["competition_id"].to_numpy() == rf["competition_id"].to_numpy()).all()
        assert (bf["rider_id"].to_numpy() == rf["rider_id"].to_numpy()).all()
    train_c, val_c, test_c = train_b.copy(), val_b.copy(), test_b.copy()
    for col in RATING_FEATURE_COLS:
        train_c[col] = train_r[col].to_numpy()
        val_c[col] = val_r[col].to_numpy()
        test_c[col] = test_r[col].to_numpy()

    sig_cov = 1 - test_b["sig_sprint"].isna().mean()
    print(f"    sig coverage on test rows: {sig_cov:.1%}", flush=True)

    # ---- Train + evaluate the three arms ----
    print(f"  Training ARM A — {ARM_DESC['A']}...", flush=True)
    bucket_a, cont_a, _ = _train_bucket_and_contender(train, val, fold["label"])
    res_a, _ = eval_arm(test, bucket_a, cont_a, lr_model=main_lr)

    print(f"  Training ARM B — {ARM_DESC['B']}...", flush=True)
    bucket_b, cont_b, _ = _train_bucket_and_contender(train_b, val_b, fold["label"])
    res_b, _ = eval_arm(test_b, bucket_b, cont_b, lr_model=None)

    print(f"  Training ARM C — {ARM_DESC['C']}...", flush=True)
    bucket_c, cont_c, _ = _train_bucket_and_contender(train_c, val_c, fold["label"])
    res_c, pools_c = eval_arm(test_c, bucket_c, cont_c, lr_model=main_lr)
    ranks_c = tracked_feature_ranks(cont_c)

    # ---- Temperature refit for arm C (fit on VAL win book) ----
    _, val_pools_c = eval_arm(val_c, bucket_c, cont_c, lr_model=None)
    refit = temperature_refit_block(val_pools_c, pools_c)
    od_cal_c = res_c.get("one_day", {}).get("win_cal_ratio")
    refit["one_day_win_cal_ratio_C"] = od_cal_c
    refit["triggered"] = bool(od_cal_c is not None and od_cal_c < CAL_TRIGGER)

    # ---- DNF head (fold-safe) + honest pools for arms A and C ----
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
    p_test_dnf = head.predict_dnf_proba(h_test)
    head_metrics = evaluate_dnf(h_test["dnf"].values, p_test_dnf)
    print(
        f"    head: best_iter={head_info['best_iteration']}  "
        f"test AUC={head_metrics['auc']:.4f}  LL={head_metrics['log_loss']:.4f}",
        flush=True,
    )
    p_map = dict(
        zip(
            zip(h_test["competition_id"].values, h_test["rider_id"].values),
            p_test_dnf,
        )
    )

    dnf_rows, excl = build_dnf_pipeline_rows(
        test, labels, dnf_snaps, str(DEFAULT_DB_PATH), test_period_start=val_end
    )
    print(f"  DNF'd starters scored: {len(dnf_rows):,}  exclusions: {excl}", flush=True)

    pool_plain = pd.concat(
        [test.assign(is_dnf_row=0), dnf_rows.assign(is_dnf_row=1)], ignore_index=True
    )
    print("  Honest-pool evaluation, ARM A...", flush=True)
    honest_a = honest_eval(pool_plain, bucket_a, cont_a, p_map, parity=(i == 0))

    # Arm C honest pool: re-derive C features on the pooled frame (serving-like:
    # startlist-level LR softmax + field means; honest view is never differenced
    # against the standard view, so the slight finisher-row feature drift vs
    # test_c is by design).
    print("  Honest-pool evaluation, ARM C...", flush=True)
    pool_rated = attach_rating_features(pool_plain, rating_snaps, db_path=DEFAULT_DB_PATH)
    pool_c = attach(pool_rated, od_feats, field_shares)
    pool_c["oof_time_gap_pred"] = main_tg.predict(pool_c)
    pool_c["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(pool_c))
    honest_c = honest_eval(pool_c, bucket_c, cont_c, p_map, parity=False)

    # ---- Per-fold summary lines ----
    a, b, c = res_a["all"], res_b["all"], res_c["all"]
    print(
        f"  FOLD {fold['label']}: mkt_avg_ll A={a['market_avg_log_loss']:.4f} "
        f"B={b['market_avg_log_loss']:.4f} C={c['market_avg_log_loss']:.4f} | "
        f"C-B={c['market_avg_log_loss'] - b['market_avg_log_loss']:+.4f} "
        f"C-A={c['market_avg_log_loss'] - a['market_avg_log_loss']:+.4f} | "
        f"wcap C-B={c['race_winner_capture_rate'] - b['race_winner_capture_rate']:+.4f} "
        f"C-A={c['race_winner_capture_rate'] - a['race_winner_capture_rate']:+.4f}",
        flush=True,
    )
    ha = honest_a["subsets"].get("all", {})
    hc = honest_c["subsets"].get("all", {})
    if ha and hc:
        print(
            f"    honest_adj mkt_avg: A={ha['honest_adjusted']['market_avg_log_loss']:.4f} "
            f"C={hc['honest_adjusted']['market_avg_log_loss']:.4f} "
            f"(C-A={hc['honest_adjusted']['market_avg_log_loss'] - ha['honest_adjusted']['market_avg_log_loss']:+.4f})  "
            f"adj-unadj: A={ha['honest_adjusted']['market_avg_log_loss'] - ha['honest_unadjusted']['market_avg_log_loss']:+.4f} "
            f"C={hc['honest_adjusted']['market_avg_log_loss'] - hc['honest_unadjusted']['market_avg_log_loss']:+.4f}",
            flush=True,
        )
    od_line = []
    for arm, r in (("A", res_a), ("B", res_b), ("C", res_c)):
        if "one_day" in r:
            od_line.append(f"{arm}={r['one_day']['win_cal_ratio']:.3f}")
    rf_od = refit.get("one_day")
    if rf_od:
        od_line.append(
            f"refit(T={rf_od['T']:.3f}): cal {rf_od['before']['win_cal_ratio']:.3f}"
            f"->{rf_od['after']['win_cal_ratio']:.3f} "
            f"ll {rf_od['before']['win_log_loss']:.4f}->{rf_od['after']['win_log_loss']:.4f}"
        )
    print(
        f"    one_day win_cal: {'  '.join(od_line)}  "
        f"[watch-item triggered: {refit['triggered']}]",
        flush=True,
    )
    if ranks_c:
        shown = [f for f in TRACKED_FEATURES if ranks_c.get(f, {}).get("rank")]
        print(
            "    C feature ranks: "
            + "  ".join(f"{f}=#{ranks_c[f]['rank']}" for f in shown)
            + f" (of {ranks_c['n_features']})",
            flush=True,
        )

    head_metrics_small = {
        k: head_metrics[k]
        for k in ("n", "base_rate", "mean_pred", "auc", "log_loss", "brier", "cal_ratio")
    }
    return {
        "fold_label": fold["label"],
        "skipped": False,
        "sig_coverage_test": round(float(sig_cov), 4),
        "test_rating_coverage": round(float(test_r["contested_rating"].notna().mean()), 4),
        "main_lr_temperature": float(main_lr.config.temperature),
        "arms": {"A": res_a, "B": res_b, "C": res_c},
        "honest": {
            "A": honest_a["subsets"],
            "C": honest_c["subsets"],
            "head_pred_missing_rows": {
                "A": honest_a["head_pred_missing_rows"],
                "C": honest_c["head_pred_missing_rows"],
            },
        },
        "dnf_head": {
            "best_iteration": head_info["best_iteration"],
            "test_metrics": head_metrics_small,
            "n_dnf_rows_scored": int(len(dnf_rows)),
            "exclusions": excl,
        },
        "temperature_refit_C": refit,
        "tracked_feature_ranks_C": ranks_c,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _stat(vals: List[float]) -> Dict[str, Any]:
    return {
        "mean": float(np.mean(vals)),
        "std": float(np.std(vals)),
        "per_fold": [float(v) for v in vals],
    }


def build_aggregates(usable: List[Dict[str, Any]]) -> Dict[str, Any]:
    agg: Dict[str, Any] = {
        "paired_deltas": {},
        "absolute_calibration": {},
        "levels_market_avg_log_loss": {},
        "honest": {},
        "temperature_refit_C": {},
    }

    # Paired deltas + absolute levels per subset
    for subset in EVAL_SUBSETS:
        agg["paired_deltas"][subset] = {}
        for pair_name, hi, lo in PAIRS:
            agg["paired_deltas"][subset][pair_name] = {}
            for k in DELTA_METRICS:
                ds = []
                for fr in usable:
                    a = fr["arms"][hi].get(subset, {}).get(k)
                    b = fr["arms"][lo].get(subset, {}).get(k)
                    if a is not None and b is not None and not (np.isnan(a) or np.isnan(b)):
                        ds.append(a - b)
                if ds:
                    agg["paired_deltas"][subset][pair_name][k] = _stat(ds)

        agg["absolute_calibration"][subset] = {}
        agg["levels_market_avg_log_loss"][subset] = {}
        for arm in ARMS:
            cal_entry = {}
            for k in CAL_METRICS + ["blend_win_cal_ratio"]:
                vals = [
                    fr["arms"][arm][subset][k]
                    for fr in usable
                    if k in fr["arms"][arm].get(subset, {})
                ]
                if vals:
                    cal_entry[k] = _stat(vals)
            agg["absolute_calibration"][subset][arm] = cal_entry
            lv = [
                fr["arms"][arm][subset]["market_avg_log_loss"]
                for fr in usable
                if subset in fr["arms"][arm]
            ]
            if lv:
                agg["levels_market_avg_log_loss"][subset][arm] = _stat(lv)

    # Honest frame
    for subset in HONEST_SUBSETS:
        entry: Dict[str, Any] = {}
        for arm in ("A", "C"):
            folds_with = [fr for fr in usable if subset in fr["honest"][arm]]
            if not folds_with:
                continue
            arm_entry: Dict[str, Any] = {}
            arm_entry["level_honest_adjusted_market_avg_log_loss"] = _stat(
                [fr["honest"][arm][subset]["honest_adjusted"]["market_avg_log_loss"]
                 for fr in folds_with]
            )
            for k in HONEST_DELTA_METRICS:
                arm_entry[f"honest_adjusted_minus_unadjusted__{k}"] = _stat(
                    [fr["honest"][arm][subset]["honest_adjusted"][k]
                     - fr["honest"][arm][subset]["honest_unadjusted"][k]
                     for fr in folds_with]
                )
            arm_entry["same_rows_adjusted_minus_standard__market_avg_log_loss"] = _stat(
                [fr["honest"][arm][subset]["same_rows_adjusted"]["market_avg_log_loss"]
                 - fr["honest"][arm][subset]["standard"]["market_avg_log_loss"]
                 for fr in folds_with]
            )
            entry[arm] = arm_entry
        # C - A on the honest-adjusted view (system-level comparison)
        both = [
            fr for fr in usable
            if subset in fr["honest"]["A"] and subset in fr["honest"]["C"]
        ]
        if both:
            entry["C_minus_A__honest_adjusted"] = {
                k: _stat(
                    [fr["honest"]["C"][subset]["honest_adjusted"][k]
                     - fr["honest"]["A"][subset]["honest_adjusted"][k]
                     for fr in both]
                )
                for k in HONEST_DELTA_METRICS
            }
            entry["C_minus_A__honest_unadjusted_market_avg_log_loss"] = _stat(
                [fr["honest"]["C"][subset]["honest_unadjusted"]["market_avg_log_loss"]
                 - fr["honest"]["A"][subset]["honest_unadjusted"]["market_avg_log_loss"]
                 for fr in both]
            )
        if entry:
            agg["honest"][subset] = entry

    # Temperature refit
    for subset in EVAL_SUBSETS:
        folds_with = [fr for fr in usable if subset in fr["temperature_refit_C"]]
        if not folds_with:
            continue
        agg["temperature_refit_C"][subset] = {
            "T": _stat([fr["temperature_refit_C"][subset]["T"] for fr in folds_with]),
            "before_win_log_loss": _stat(
                [fr["temperature_refit_C"][subset]["before"]["win_log_loss"] for fr in folds_with]
            ),
            "after_win_log_loss": _stat(
                [fr["temperature_refit_C"][subset]["after"]["win_log_loss"] for fr in folds_with]
            ),
            "before_win_cal_ratio": _stat(
                [fr["temperature_refit_C"][subset]["before"]["win_cal_ratio"] for fr in folds_with]
            ),
            "after_win_cal_ratio": _stat(
                [fr["temperature_refit_C"][subset]["after"]["win_cal_ratio"] for fr in folds_with]
            ),
        }
    agg["temperature_refit_C"]["n_folds_triggered"] = int(
        sum(1 for fr in usable if fr["temperature_refit_C"].get("triggered"))
    )
    return agg


def print_final_blocks(agg: Dict[str, Any]):
    print("\n" + "=" * 88, flush=True)
    print("PAIRED DELTAS (mean ± std across folds; per-fold in brackets)", flush=True)
    print("=" * 88, flush=True)
    for subset in EVAL_SUBSETS:
        for pair_name, _, _ in PAIRS:
            block = agg["paired_deltas"][subset].get(pair_name, {})
            for k in DELTA_METRICS:
                d = block.get(k)
                if d:
                    per = " ".join(f"{v:+.4f}" for v in d["per_fold"])
                    print(
                        f"  {subset:<8s} {pair_name:<10s} {k:<28s} "
                        f"{d['mean']:+.4f}±{d['std']:.4f}   [{per}]",
                        flush=True,
                    )
            print("", flush=True)

    print("=" * 88, flush=True)
    print("ABSOLUTE CALIBRATION LEVELS (mean ± std across folds)", flush=True)
    print("=" * 88, flush=True)
    for subset in EVAL_SUBSETS:
        for k in CAL_METRICS:
            parts = []
            for arm in ARMS:
                d = agg["absolute_calibration"][subset].get(arm, {}).get(k)
                if d:
                    parts.append(f"{arm}={d['mean']:.3f}±{d['std']:.3f}")
            if parts:
                print(f"  {subset:<8s} {k:<18s} {'  '.join(parts)}", flush=True)

    print("\n" + "=" * 88, flush=True)
    print("HONEST FRAME (DNF-adjusted, startlist pool)", flush=True)
    print("=" * 88, flush=True)
    for subset in HONEST_SUBSETS:
        e = agg["honest"].get(subset)
        if not e:
            continue
        for arm in ("A", "C"):
            if arm in e:
                lvl = e[arm]["level_honest_adjusted_market_avg_log_loss"]
                d = e[arm]["honest_adjusted_minus_unadjusted__market_avg_log_loss"]
                print(
                    f"  {subset:<8s} arm {arm}: honest_adj mkt_avg_ll={lvl['mean']:.4f}±{lvl['std']:.4f}  "
                    f"adj-unadj={d['mean']:+.4f}±{d['std']:.4f} "
                    f"[{' '.join(f'{v:+.4f}' for v in d['per_fold'])}]",
                    flush=True,
                )
        ca = e.get("C_minus_A__honest_adjusted", {}).get("market_avg_log_loss")
        if ca:
            print(
                f"  {subset:<8s} C-A honest_adjusted mkt_avg_ll: {ca['mean']:+.4f}±{ca['std']:.4f} "
                f"[{' '.join(f'{v:+.4f}' for v in ca['per_fold'])}]",
                flush=True,
            )

    print("\n" + "=" * 88, flush=True)
    print(
        f"TEMPERATURE REFIT (arm C win book; folds triggered "
        f"(one_day win_cal<{CAL_TRIGGER}): {agg['temperature_refit_C']['n_folds_triggered']})",
        flush=True,
    )
    print("=" * 88, flush=True)
    for subset in EVAL_SUBSETS:
        d = agg["temperature_refit_C"].get(subset)
        if not d:
            continue
        print(
            f"  {subset:<8s} T={d['T']['mean']:.3f}±{d['T']['std']:.3f}  "
            f"win_ll {d['before_win_log_loss']['mean']:.4f}->{d['after_win_log_loss']['mean']:.4f}  "
            f"win_cal {d['before_win_cal_ratio']['mean']:.3f}->{d['after_win_cal_ratio']['mean']:.3f}",
            flush=True,
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    started = datetime.now()
    print("=" * 70, flush=True)
    print("FULL-STACK INTEGRATION GATE — A baseline vs B combined vs C full", flush=True)
    print("=" * 70, flush=True)
    print(f"Started: {started.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    # ---- Signatures (one-day B4, fold-independent) ----
    sig = load_signature_table()
    od_feats = oneday_b4(sig)
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    assert od_feats["comp_id"].is_unique and field_shares["comp_id"].is_unique
    print(f"Signature table: {len(sig):,} comps; one-day B4 rows: {len(od_feats):,}", flush=True)

    # ---- Contested-Elo snapshots ----
    if DEFAULT_SNAPSHOT_PATH.exists():
        rating_snaps = load_snapshots(DEFAULT_SNAPSHOT_PATH)
        print(f"Loaded {len(rating_snaps):,} rating snapshots from {DEFAULT_SNAPSHOT_PATH}", flush=True)
    else:
        print("Rating snapshot parquet missing — building from DB...", flush=True)
        rating_snaps = build_and_save()

    # ---- Production frame + rated twin ----
    df = _load_full_df()
    print(f"Loaded {len(df):,} training rows, {df['competition_id'].nunique():,} comps", flush=True)
    df_rated = attach_rating_features(df, rating_snaps, db_path=DEFAULT_DB_PATH)
    assert len(df_rated) == len(df)
    assert (df_rated["competition_id"].to_numpy() == df["competition_id"].to_numpy()).all()
    assert (df_rated["rider_id"].to_numpy() == df["rider_id"].to_numpy()).all()
    print(f"Rating coverage on frame: {df_rated['contested_rating'].notna().mean():.1%}", flush=True)

    # ---- DNF labels + head feature frame ----
    print("Loading DNF labels + building head feature frame...", flush=True)
    labels = load_labels()
    labels = labels[labels["competition_date"].notna() & labels["rider_id"].notna()].copy()
    labels["rider_id"] = labels["rider_id"].astype("int64")
    labels = add_asof_dates(labels)
    dnf_snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=labels, snaps=dnf_snaps, start_date=START_DATE)
    head_frame["competition_date"] = pd.to_datetime(head_frame["competition_date"])
    print(
        f"  head frame: {len(head_frame):,} rows, DNF rate {head_frame['dnf'].mean():.4f}",
        flush=True,
    )

    partial_path = OUT_DIR / "full_stack_integration_cv_partial.json"
    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(FOLDS):
        print(f"\n{'─' * 60}\nFOLD {i + 1}/{len(FOLDS)} (test={fold['label']}+)\n{'─' * 60}", flush=True)
        fold_results.append(
            run_fold(i, fold, df, df_rated, od_feats, field_shares,
                     rating_snaps, labels, dnf_snaps, head_frame)
        )
        partial_path.write_text(
            json.dumps({"folds_done": i + 1, "fold_results": fold_results},
                       indent=2, default=str)
        )

    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg = build_aggregates(usable)
    print_final_blocks(agg)

    ended = datetime.now()
    out = {
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {
            "folds": FOLDS,
            "start_date": START_DATE,
            "blend_w": BLEND_W,
            "cal_trigger": CAL_TRIGGER,
            "temp_bounds": TEMP_BOUNDS,
            "arms": ARM_DESC,
            "rating_feature_cols": list(RATING_FEATURE_COLS),
            "meta_feature_cols": list(META_FEATURE_COLS),
            "rating_snapshot_path": str(DEFAULT_SNAPSHOT_PATH),
            "n_rating_snapshot_rows": int(len(rating_snaps)),
            "notes": (
                "OOF generated once per fold, shared by B and C. Blend overlay and "
                "honest DNF frame computed for arms A and C only. Arm C honest pool "
                "re-derives C features on the pooled (startlist-like) frame. "
                "Temperature refit: win book p^(1/T) renormalized to sum 1 per race, "
                "T fit on VAL by NLL."
            ),
        },
        "fold_results": fold_results,
        "aggregated": agg,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = ended.strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"full_stack_integration_cv_{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    if partial_path.exists():
        partial_path.unlink()
    print(f"\nSaved {path}  ({(ended - started).total_seconds() / 60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
