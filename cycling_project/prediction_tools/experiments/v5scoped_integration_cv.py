"""
v5scoped full-stack integration gate — is the contested-rows GT-form fix
additive on top of the SHIPPED arm-C stack? (2026-07-03)

The GT-aware form sweep (experiment_log 2026-07-03) picked v5scoped
(contested-rows-only EMA, NaN'd on one-day targets) as the bias fix. But the
production stack already carries contested Elo, which is itself partly
GT-aware. This gate tests v5scoped against the FULL stack, not the plain
baseline, on both the primary market gate and the GT-recency bias diagnostic.

Arms (per fold, paired; FOLDS shared with the stack gates):
  A baseline  — plain production stack (no meta-OOF / sigs / Elo / v5).
  C full      — the shipped arm-C stack: meta-OOF (oof_time_gap_pred,
                oof_lambdarank_win_p) + one-day B4 signatures + contested-Elo.
  D full+v5   — C + the 4 v5 contested-form columns, NaN'd on one_day TARGET
                rows (the v5scoped design).

Each arm trains bucket + contender + a LambdaRank head ON THAT ARM'S FRAME
(so the GT-recency win-cal table reflects the arm's own calibration). OOF
meta features + main tg/LR are generated once per fold and reused for C, D.

Reported per fold, aggregated across 5:
  - MarketProbabilityEvaluator (top-15 pool) per subset all/one_day/stage/gc,
    paired deltas D-C (key), C-A, D-A. Honest DNF-adjusted frame for A/C/D
    (startlist pool, P(market|finish)xP(finish)); D's pool re-derives every
    arm feature incl. v5 on the DNF-inclusive rows.
  - GT-recency LambdaRank win-cal tables per arm (gt_recency_backtest), pooled
    over label-year records — does v5scoped move the GT ≤45d band toward 1.0
    ON TOP of the stack, without worsening no-GT?
  - v5 feature-importance ranks in arm D; absolute one-day win_cal per arm.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.v5scoped_integration_cv [--smoke]
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold as sml
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
from cycling_project.prediction_tools.evaluation import MarketProbabilityEvaluator
from cycling_project.prediction_tools.experiments.age_bias_backtest import _collect_records
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    ARCH,
    attach,
    load_signature_table,
    oneday_b4,
)
from cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv import (
    SUBSETS as HONEST_SUBSETS,
    build_dnf_pipeline_rows,
)
from cycling_project.prediction_tools.experiments.form_feature_lab import (
    V5_COLS,
    FormFeatureLab,
)
from cycling_project.prediction_tools.experiments.full_stack_integration_cv import (
    TOP_N,
    _stat,
    contender_pool,
    eval_arm,
    honest_eval,
)
from cycling_project.prediction_tools.experiments.gt_recency_backtest import (
    attach_gt_recency,
    gt_band_tables,
    load_gt_participations,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
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
ARMS = ("A", "C", "D")
ARM_DESC = {
    "A": "plain baseline (no stack)",
    "C": "shipped arm-C stack (meta-OOF + one-day sigs + Elo)",
    "D": "C + v5scoped (contested-form, NaN on one-days)",
}
EVAL_SUBSETS = ("all", "one_day", "stage", "gc")
PAIRS = [("D_minus_C", "D", "C"), ("C_minus_A", "C", "A"), ("D_minus_A", "D", "A")]
DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "podium_cal_ratio",
    "race_winner_capture_rate", "race_podium_capture_rate",
]
CAL_METRICS = ["win_cal_ratio", "podium_cal_ratio"]
HONEST_DELTA_METRICS = ["market_avg_log_loss", "win_log_loss", "top15_log_loss", "win_cal_ratio"]


# ---------------------------------------------------------------------------
# v5scoped attachment (merge from lab cache; DNF rows via features_for_targets)
# ---------------------------------------------------------------------------

def attach_v5scoped(
    frame: pd.DataFrame, cache: pd.DataFrame, lab: FormFeatureLab
) -> pd.DataFrame:
    """Attach the 4 v5 columns, then NaN them on one_day rows (the v5scoped
    design). Finisher rows come from the lab cache; any rows not covered
    (DNF'd starters in the honest pool) are computed as-of-then directly."""
    keys = ["rider_id", "competition_id"]
    out = frame.merge(cache[keys + V5_COLS], on=keys, how="left", indicator=True)
    not_covered = out["_merge"] == "left_only"
    if "is_dnf_row" in out.columns:
        not_covered &= out["is_dnf_row"] == 1
    out = out.drop(columns="_merge")
    if not_covered.any():
        extra = lab.features_for_targets(out.loc[not_covered, keys])
        out = out.merge(
            extra[keys + V5_COLS], on=keys, how="left", suffixes=("", "_x")
        )
        for c in V5_COLS:
            out[c] = out[c].where(out[c].notna(), out[f"{c}_x"])
            out = out.drop(columns=f"{c}_x")
    out.loc[out["competition_type"] == "one_day", V5_COLS] = np.nan
    return out


def v5_feature_ranks(cont) -> Optional[Dict[str, Any]]:
    try:
        imp_df = cont.get_feature_importance(importance_type="gain")
    except Exception:
        return None
    order = sorted(
        zip(imp_df["feature"], imp_df["importance"].astype(float)),
        key=lambda kv: kv[1], reverse=True,
    )
    pos = {k: i + 1 for i, (k, _) in enumerate(order)}
    return {"n_features": len(order), **{f: pos.get(f) for f in V5_COLS}}


def _test_year(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    return frame[frame["competition_date"].dt.year == int(label)].copy()


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(
    i: int,
    fold: Dict[str, str],
    df: pd.DataFrame,
    df_rated: pd.DataFrame,
    cache: pd.DataFrame,
    lab: FormFeatureLab,
    od_feats: pd.DataFrame,
    field_shares: pd.DataFrame,
    rating_snaps: pd.DataFrame,
    labels: pd.DataFrame,
    dnf_snaps: pd.DataFrame,
    head_frame: pd.DataFrame,
) -> Dict[str, Any]:
    label = fold["label"]
    train, val, test = _slice_fold(df, fold)
    train_r, val_r, test_r = _slice_fold(df_rated, fold)
    if len(test) == 0:
        return {"fold_label": label, "skipped": True}
    print(f"  train {len(train):,} | val {len(val):,} | test {len(test):,} rows "
          f"({test['competition_id'].nunique():,} comps)", flush=True)

    # ---- OOF meta + main base models (once; reused C, D) ----
    print("  OOF time_gap + LambdaRank (5 sub-folds each)...", flush=True)
    oof_tg = _generate_oof_time_gap(train, val)
    oof_lr = _generate_oof_lambdarank_winp(train, val)
    main_tg = _train_main_time_gap(train, val)
    main_lr = _train_main_lambdarank(train, val)   # arm A's LR head
    print(f"    main LR temperature: {main_lr.config.temperature:.3f}", flush=True)

    # ---- Arm C frames: sigs + meta-OOF + Elo ----
    train_c = attach(train, od_feats, field_shares)
    val_c = attach(val, od_feats, field_shares)
    test_c = attach(test, od_feats, field_shares)
    train_c["oof_time_gap_pred"] = oof_tg
    train_c["oof_lambdarank_win_p"] = oof_lr
    for f, m in ((val_c, val), (test_c, test)):
        f["oof_time_gap_pred"] = main_tg.predict(f)
        f["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(f))
    for cf, rf in ((train_c, train_r), (val_c, val_r), (test_c, test_r)):
        assert (cf["competition_id"].to_numpy() == rf["competition_id"].to_numpy()).all()
        assert (cf["rider_id"].to_numpy() == rf["rider_id"].to_numpy()).all()
        for col in RATING_FEATURE_COLS:
            cf[col] = rf[col].to_numpy()

    # ---- Arm D frames: C + v5scoped ----
    train_d = attach_v5scoped(train_c, cache, lab)
    val_d = attach_v5scoped(val_c, cache, lab)
    test_d = attach_v5scoped(test_c, cache, lab)
    v5_cov = 1 - test_d.loc[test_d["competition_type"] != "one_day", "v5_cont_ema_pct_h60"].isna().mean()
    print(f"    v5 coverage on non-one-day test rows: {v5_cov:.1%}", flush=True)

    # ---- Train + eval the three arms (+ per-arm LR for GT tables) ----
    records = {}
    res, ranks_d = {}, None
    frames = {"A": (train, val, test, main_lr),
              "C": (train_c, val_c, test_c, None),
              "D": (train_d, val_d, test_d, None)}
    buckets, conts = {}, {}
    for arm in ARMS:
        tr, vl, te, lr = frames[arm]
        print(f"  Training ARM {arm} — {ARM_DESC[arm]}...", flush=True)
        bucket, cont, _ = _train_bucket_and_contender(tr, vl, label)
        if lr is None:
            lr = _train_main_lambdarank(tr, vl)
        buckets[arm], conts[arm] = bucket, cont
        res[arm], _ = eval_arm(te, bucket, cont, lr_model=None)
        records[arm] = _collect_records(_test_year(te, label), bucket, cont, lr, label)
        if arm == "D":
            ranks_d = v5_feature_ranks(cont)

    # ---- DNF head (fold-safe) + honest pools A/C/D ----
    train_end = pd.to_datetime(fold["train_end"])
    val_end = pd.to_datetime(fold["val_end"])
    h_tr = head_frame[head_frame["competition_date"] <= train_end]
    h_vl = head_frame[(head_frame["competition_date"] > train_end)
                      & (head_frame["competition_date"] <= val_end)]
    h_te = head_frame[head_frame["competition_date"] > val_end]
    print(f"  Training DNF head on {len(h_tr):,} starter rows...", flush=True)
    head = DNFPredictor()
    head_info = head.train(h_tr, h_vl)
    p_te = head.predict_dnf_proba(h_te)
    head_metrics = evaluate_dnf(h_te["dnf"].values, p_te)
    print(f"    head: AUC={head_metrics['auc']:.4f} LL={head_metrics['log_loss']:.4f} "
          f"cal={head_metrics['cal_ratio']:.3f}", flush=True)
    p_map = dict(zip(zip(h_te["competition_id"].values, h_te["rider_id"].values), p_te))

    dnf_rows, excl = build_dnf_pipeline_rows(
        test, labels, dnf_snaps, str(DEFAULT_DB_PATH), test_period_start=val_end)
    print(f"  DNF'd starters scored: {len(dnf_rows):,}  exclusions: {excl}", flush=True)
    pool_plain = pd.concat(
        [test.assign(is_dnf_row=0), dnf_rows.assign(is_dnf_row=1)], ignore_index=True)

    print("  Honest-pool eval A...", flush=True)
    honest = {"A": honest_eval(pool_plain, buckets["A"], conts["A"], p_map, parity=(i == 0))}

    print("  Honest-pool eval C...", flush=True)
    pool_rated = attach_rating_features(pool_plain, rating_snaps, db_path=DEFAULT_DB_PATH)
    pool_c = attach(pool_rated, od_feats, field_shares)
    pool_c["oof_time_gap_pred"] = main_tg.predict(pool_c)
    pool_c["oof_lambdarank_win_p"] = np.asarray(main_lr.predict_win_probabilities(pool_c))
    honest["C"] = honest_eval(pool_c, buckets["C"], conts["C"], p_map)

    print("  Honest-pool eval D...", flush=True)
    pool_d = attach_v5scoped(pool_c, cache, lab)
    honest["D"] = honest_eval(pool_d, buckets["D"], conts["D"], p_map)

    # ---- per-fold summary line ----
    a, c, d = res["A"]["all"], res["C"]["all"], res["D"]["all"]
    print(f"  FOLD {label}: mkt_avg_ll A={a['market_avg_log_loss']:.4f} "
          f"C={c['market_avg_log_loss']:.4f} D={d['market_avg_log_loss']:.4f} | "
          f"D-C={d['market_avg_log_loss']-c['market_avg_log_loss']:+.4f} "
          f"C-A={c['market_avg_log_loss']-a['market_avg_log_loss']:+.4f} | "
          f"wcap D-C={d['race_winner_capture_rate']-c['race_winner_capture_rate']:+.4f}", flush=True)
    hc = honest["C"]["subsets"].get("all", {})
    hd = honest["D"]["subsets"].get("all", {})
    if hc and hd:
        print(f"    honest_adj mkt_avg: C={hc['honest_adjusted']['market_avg_log_loss']:.4f} "
              f"D={hd['honest_adjusted']['market_avg_log_loss']:.4f} "
              f"(D-C={hd['honest_adjusted']['market_avg_log_loss']-hc['honest_adjusted']['market_avg_log_loss']:+.4f})", flush=True)
    if ranks_d:
        shown = [f for f in V5_COLS if ranks_d.get(f)]
        print("    D v5 ranks: " + "  ".join(f"{f}=#{ranks_d[f]}" for f in shown)
              + f" (of {ranks_d['n_features']})", flush=True)

    return {
        "fold_label": label,
        "skipped": False,
        "v5_coverage_nonoentday_test": round(float(v5_cov), 4),
        "main_lr_temperature": float(main_lr.config.temperature),
        "arms": res,
        "honest": {arm: honest[arm]["subsets"] for arm in ARMS},
        "gt_records": {arm: records[arm] for arm in ARMS},   # dropped before JSON dump
        "dnf_head": {
            "best_iteration": head_info["best_iteration"],
            "test_metrics": {k: head_metrics[k] for k in
                             ("auc", "log_loss", "brier", "cal_ratio") if k in head_metrics},
        },
        "v5_feature_ranks_D": ranks_d,
    }


# ---------------------------------------------------------------------------
# Aggregation + printing
# ---------------------------------------------------------------------------

def build_aggregates(usable: List[Dict[str, Any]], gt_parts, db_path) -> Dict[str, Any]:
    agg: Dict[str, Any] = {"paired_deltas": {}, "absolute_calibration": {},
                           "levels_market_avg_log_loss": {}, "honest": {}, "gt_recency": {}}
    for subset in EVAL_SUBSETS:
        agg["paired_deltas"][subset] = {}
        for pair_name, hi, lo in PAIRS:
            block = {}
            for k in DELTA_METRICS:
                ds = [fr["arms"][hi][subset][k] - fr["arms"][lo][subset][k]
                      for fr in usable
                      if subset in fr["arms"][hi] and subset in fr["arms"][lo]
                      and k in fr["arms"][hi][subset] and k in fr["arms"][lo][subset]]
                if ds:
                    block[k] = _stat(ds)
            agg["paired_deltas"][subset][pair_name] = block
        agg["absolute_calibration"][subset] = {}
        agg["levels_market_avg_log_loss"][subset] = {}
        for arm in ARMS:
            cal = {k: _stat([fr["arms"][arm][subset][k] for fr in usable
                             if subset in fr["arms"][arm] and k in fr["arms"][arm][subset]])
                   for k in CAL_METRICS
                   if any(subset in fr["arms"][arm] for fr in usable)}
            agg["absolute_calibration"][subset][arm] = cal
            lv = [fr["arms"][arm][subset]["market_avg_log_loss"] for fr in usable
                  if subset in fr["arms"][arm]]
            if lv:
                agg["levels_market_avg_log_loss"][subset][arm] = _stat(lv)

    # Honest frame
    for subset in HONEST_SUBSETS:
        entry = {}
        for arm in ARMS:
            folds_with = [fr for fr in usable if subset in fr["honest"][arm]]
            if not folds_with:
                continue
            entry[arm] = {
                "level_honest_adjusted_market_avg_log_loss": _stat(
                    [fr["honest"][arm][subset]["honest_adjusted"]["market_avg_log_loss"]
                     for fr in folds_with]),
                "honest_adjusted_minus_unadjusted__market_avg_log_loss": _stat(
                    [fr["honest"][arm][subset]["honest_adjusted"]["market_avg_log_loss"]
                     - fr["honest"][arm][subset]["honest_unadjusted"]["market_avg_log_loss"]
                     for fr in folds_with]),
            }
        for pair_name, hi, lo in PAIRS:
            both = [fr for fr in usable
                    if subset in fr["honest"][hi] and subset in fr["honest"][lo]]
            if both:
                entry[f"{pair_name}__honest_adjusted"] = {
                    k: _stat([fr["honest"][hi][subset]["honest_adjusted"][k]
                              - fr["honest"][lo][subset]["honest_adjusted"][k] for fr in both])
                    for k in HONEST_DELTA_METRICS}
        if entry:
            agg["honest"][subset] = entry

    # GT-recency: pool label-year records per arm, cal tables
    for arm in ARMS:
        recs = pd.concat([fr["gt_records"][arm] for fr in usable], ignore_index=True)
        recs = attach_gt_recency(recs, db_path=db_path, gt=gt_parts)
        agg["gt_recency"][arm] = gt_band_tables(recs, verbose=False)
    return agg


def print_blocks(agg: Dict[str, Any]):
    print("\n" + "=" * 92)
    print("PAIRED MARKET DELTAS (mean ± std; per-fold in brackets) — D_minus_C is the key row")
    print("=" * 92)
    for subset in EVAL_SUBSETS:
        for pair_name, _, _ in PAIRS:
            d = agg["paired_deltas"][subset].get(pair_name, {}).get("market_avg_log_loss")
            if d:
                per = " ".join(f"{v:+.4f}" for v in d["per_fold"])
                pos = sum(1 for v in d["per_fold"] if v < 0)
                print(f"  {subset:<8s} {pair_name:<10s} market_avg_log_loss "
                      f"{d['mean']:+.4f}±{d['std']:.4f}  ({pos}/{len(d['per_fold'])} better)  [{per}]")
        print()

    print("=" * 92)
    print("HONEST FRAME (DNF-adjusted startlist pool) — level + D_minus_C")
    print("=" * 92)
    for subset in HONEST_SUBSETS:
        e = agg["honest"].get(subset, {})
        for arm in ARMS:
            if arm in e:
                lv = e[arm]["level_honest_adjusted_market_avg_log_loss"]
                print(f"  {subset:<8s} arm {arm}: honest_adj mkt_avg_ll={lv['mean']:.4f}±{lv['std']:.4f}")
        dc = e.get("D_minus_C__honest_adjusted", {}).get("market_avg_log_loss")
        if dc:
            per = " ".join(f"{v:+.4f}" for v in dc["per_fold"])
            pos = sum(1 for v in dc["per_fold"] if v < 0)
            print(f"  {subset:<8s} D-C honest_adj: {dc['mean']:+.4f}±{dc['std']:.4f} "
                  f"({pos}/{len(dc['per_fold'])} better)  [{per}]")
        print()

    print("=" * 92)
    print("GT-RECENCY LR win cal (bias diagnostic; ≤45d → 1.0, no-GT should not overshoot)")
    print("=" * 92)
    for view, k1, k2 in (("ALL rows", "headline", "all_rows"),
                         ("GC targets", "subsets", "gc_targets"),
                         ("Stage targets", "subsets", "stage_targets")):
        print(f"\n  {view}:")
        bands = list(agg["gt_recency"]["A"][k1][k2].keys())
        print(f"    {'band':<22s}" + "".join(f"{a:>14s}" for a in ARMS))
        for b in bands:
            row = f"    {b:<22s}"
            for arm in ARMS:
                r = agg["gt_recency"][arm][k1][k2].get(b)
                row += f"{r['cal']:>9.3f} {r['folds_under']}/{r['folds']}" if r else f"{'—':>14s}"
            print(row)
    print("\n  Contender head (top-15 rows):")
    print(f"    {'band':<22s}" + "".join(f"{a:>10s}" for a in ARMS))
    for b in list(agg["gt_recency"]["A"]["subsets"]["contender_head"].keys()):
        row = f"    {b:<22s}"
        for arm in ARMS:
            r = agg["gt_recency"][arm]["subsets"]["contender_head"].get(b)
            row += f"{r['cal']:>10.3f}" if r else f"{'—':>10s}"
        print(row)

    print("\n" + "=" * 92)
    print("ABSOLUTE win_cal_ratio by arm (watch item: one_day)")
    print("=" * 92)
    for subset in EVAL_SUBSETS:
        parts = []
        for arm in ARMS:
            dd = agg["absolute_calibration"][subset].get(arm, {}).get("win_cal_ratio")
            if dd:
                parts.append(f"{arm}={dd['mean']:.3f}")
        if parts:
            print(f"  {subset:<8s} win_cal  " + "  ".join(parts))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    smoke = "--smoke" in sys.argv[1:]
    folds = list(FOLDS)
    if smoke:
        print("*** SMOKE: 1 fold, reduced estimator budgets ***", flush=True)
        folds = [FOLDS[-1]]
        sml.CONTENDER_CONFIG["n_estimators"] = 120
        sml.CONTENDER_CONFIG["early_stopping"] = 30
        sml.TIME_GAP_OOF_CONFIG["n_estimators"] = 80
        sml.LAMBDARANK_OOF_CONFIG["n_estimators"] = 150
        sml.TIME_GAP_MAIN_CONFIG["n_estimators"] = 120
        sml.LAMBDARANK_MAIN_CONFIG["n_estimators"] = 200

    started = datetime.now()
    print("=" * 70, flush=True)
    print("v5scoped INTEGRATION GATE — A plain vs C shipped-stack vs D stack+v5scoped", flush=True)
    print(f"Folds: {[f['label'] for f in folds]}   started {started:%Y-%m-%d %H:%M:%S}", flush=True)
    print("=" * 70, flush=True)

    sig = load_signature_table()
    od_feats = oneday_b4(sig)
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    print(f"Signatures: {len(sig):,} comps; one-day B4 rows {len(od_feats):,}", flush=True)

    if DEFAULT_SNAPSHOT_PATH.exists():
        rating_snaps = load_snapshots(DEFAULT_SNAPSHOT_PATH)
    else:
        rating_snaps = build_and_save()
    print(f"Rating snapshots: {len(rating_snaps):,}", flush=True)

    df = _load_full_df()
    df_rated = attach_rating_features(df, rating_snaps, db_path=DEFAULT_DB_PATH)
    assert (df_rated["competition_id"].to_numpy() == df["competition_id"].to_numpy()).all()
    print(f"Frame: {len(df):,} rows; rating coverage {df_rated['contested_rating'].notna().mean():.1%}", flush=True)

    lab = FormFeatureLab()
    cache = lab.build_or_load()
    print(f"v5 lab cache: {len(cache):,} rows", flush=True)

    print("Loading DNF labels + head frame...", flush=True)
    labels = load_labels()
    labels = labels[labels["competition_date"].notna() & labels["rider_id"].notna()].copy()
    labels["rider_id"] = labels["rider_id"].astype("int64")
    labels = add_asof_dates(labels)
    dnf_snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=labels, snaps=dnf_snaps, start_date=START_DATE)
    head_frame["competition_date"] = pd.to_datetime(head_frame["competition_date"])
    print(f"  head frame: {len(head_frame):,} rows, DNF rate {head_frame['dnf'].mean():.4f}", flush=True)

    gt_parts = load_gt_participations(Path(str(DEFAULT_DB_PATH)))

    partial = OUT_DIR / "v5scoped_integration_cv_partial.json"
    fold_results = []
    for i, fold in enumerate(folds):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(folds)} (test={fold['label']}+)\n{'─'*60}", flush=True)
        fr = run_fold(i, fold, df, df_rated, cache, lab, od_feats, field_shares,
                      rating_snaps, labels, dnf_snaps, head_frame)
        fold_results.append(fr)
        # persist partial without the bulky record frames
        slim = [{k: v for k, v in f.items() if k != "gt_records"} for f in fold_results]
        partial.write_text(json.dumps({"folds_done": i + 1, "fold_results": slim},
                                      indent=2, default=str))

    usable = [fr for fr in fold_results if not fr.get("skipped")]
    agg = build_aggregates(usable, gt_parts, Path(str(DEFAULT_DB_PATH)))
    print_blocks(agg)

    for fr in fold_results:
        fr.pop("gt_records", None)
    ended = datetime.now()
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "smoke": smoke, "folds": folds, "arms": ARM_DESC,
        "v5_cols": list(V5_COLS), "fold_results": fold_results, "aggregated": agg,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tag = "smoke_" if smoke else ""
    path = OUT_DIR / f"v5scoped_integration_cv_{tag}{ended:%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    if partial.exists():
        partial.unlink()
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
