"""
Day-menu step-4c — RETRIEVAL-ONLY integration gate (2026-08-09).

The program's deciding experiment, per the step-4 review: the kernel family
is a TOP-15-GRADE signal (gate4 market decomposition: top15 LL ~neutral /
better 3-5 folds, ALL damage in win/podium/top5) and the program's goal was
always retrieval (invisible winners), not mass. So: the kernod-featured
model governs ONLY the contender-selection phase (pool membership + board
order); the UNTOUCHED production heads price whatever pool they are given.
A wrong day key can cost pool composition but can never corrupt prices.

Arms (per fold, paired; pricing model = arm-A cascade in ALL arms):
  A      shipped stack: bucket_a ranking + cont_a pricing (production).
  rorc   bucket_k ranking under ORACLE keys + cont_a pricing (ceiling).
  rmix   bucket_k ranking under top-5 selector-mixture keys + cont_a
         pricing (deployable automatic form; judgment replaces/overrides
         the key at serve when a read exists).

bucket_k = the step-3 menu8kernod feature set (dtm fills + kernels), oracle
keys at train/val (training conditions on the realized day, as settled).
cont_k is trained by the shared helper but NEVER used.

PRE-REGISTERED RULE (registered before the run; rmix vs A, paired by fold):
  P1 pricing-neutrality (the point of the design):
     honest_adjusted market_avg_log_loss delta mean <= +0.0010 with >= 4/5
     folds <= +0.0020, AND win_log_loss delta mean <= +0.0010 (top-of-book
     protected explicitly, per the 2026-08-09 market decomposition).
  P2 retrieval (residual slice):
     winner_in_pool15 pooled delta >= +0.015 with >= 4/5 folds >= 0, AND
     winner_model_rank pooled delta <= -1.00 with >= 4/5 folds < 0.
  Guardrails: all-subset winner capture >= -0.005; one_day winner capture
     >= -0.005.
  rorc reported as the ceiling (not gated). PASS = P1 AND P2 AND guards ->
  recommend production wiring of the ranking channel (with serve-time key
  = judgment override > od self-key > mixture fallback). FAIL on P1 ->
  the signal cannot even ride the ranking channel without leaking into
  prices via pool composition; program closes to scenario-layer only.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.day_menu_gate6_retrieval_cv [--smoke]
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

import cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold as H
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
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    ARCH,
    attach,
    load_signature_table,
    oneday_b4,
)
from cycling_project.prediction_tools.experiments.day_menu_gate_cv import (
    DB_PATH,
    build_labels,
    stage_menu_feats,
)
from cycling_project.prediction_tools.experiments.day_menu_gate3_cv import (
    K_MENU,
    build_rider_history,
    extend_item_map_oneday,
    kernel_cumulants,
)
from cycling_project.prediction_tools.experiments.day_menu_gate4_cv import (
    build_selector_features,
    fit_selector,
    key_attach,
    mix_weights,
    pool_records,
    selector_maps,
)
from cycling_project.prediction_tools.experiments.day_menu_gate5_overlay_cv import (
    comp_class_map,
    honest_pool_mask,
    sliced_market_eval,
    std_pool,
)
from cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv import (
    build_dnf_pipeline_rows,
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
ARMS = ("A", "rorc", "rmix")

THRESHOLDS = {
    "p1_honest_mkt_ll_mean_max": 0.0010,
    "p1_fold_ll_max": 0.0020,
    "p1_folds_within_min": 4,
    "p1_win_ll_mean_max": 0.0010,
    "p2_pool15_delta_min": 0.015,
    "p2_pool15_folds_nonneg_min": 4,
    "p2_winner_rank_delta_max": -1.00,
    "p2_winner_rank_folds_neg_min": 4,
    "guard_winner_capture_min": -0.005,
}


def mixed_expected(base_frame, bucket, fixed_map, weights, canon, cum,
                   items, field_shares, stage_comps) -> np.ndarray:
    """Mixture of per-item RANKING scores (expected bucket) only."""
    var_comps = weights.index.to_numpy()
    comp_ids = base_frame["competition_id"].to_numpy()
    w_rows = weights.reindex(comp_ids)
    is_var = w_rows.notna().all(axis=1).to_numpy()
    mixed = np.zeros(len(base_frame))
    done_fixed = False
    for m in items:
        w_col = (w_rows[m].to_numpy(dtype=float) if m in w_rows.columns
                 else np.zeros(len(w_rows)))
        w_m = np.where(is_var, w_col, 0.0)
        if not done_fixed:
            w_m = w_m + (~is_var).astype(float)
        if w_m.sum() == 0:
            continue
        key_m = pd.concat([fixed_map[~fixed_map.index.isin(var_comps)],
                           pd.Series(m, index=var_comps)])
        fr_m = key_attach(base_frame, key_m, canon=canon, cum=cum,
                          items=items, field_shares=field_shares,
                          stage_comps=stage_comps)
        mixed += w_m * np.asarray(bucket.predict_continuous(fr_m), dtype=float)
        done_fixed = True
    return mixed


def run_fold(i, fold, df, df_rated, od_feats, field_shares, rating_snaps,
             labels, hist, comp_selfeats, place_map, dnf_labels, dnf_snaps,
             head_frame, smoke):
    label = fold["label"]
    train, val, test = _slice_fold(df, fold)
    train_r, val_r, test_r = _slice_fold(df_rated, fold)
    if len(test) == 0:
        return {"fold_label": label, "skipped": True}, [], []
    print(f"  train {len(train):,} | test {len(test):,} rows", flush=True)

    feats, item_map, canon = stage_menu_feats(labels, fold["train_end"], K_MENU)
    cum, items = kernel_cumulants(hist, canon)
    oracle_ext = extend_item_map_oneday(item_map, od_feats, canon)
    stage_comps = set(labels.comp_id)
    kw = dict(canon=canon, cum=cum, items=items,
              field_shares=field_shares, stage_comps=stage_comps)

    sel = fit_selector(comp_selfeats, labels, item_map,
                       fold["train_end"], fold["val_end"], smoke=smoke)
    mech_map, sel_probs = selector_maps(sel, labels, oracle_ext)
    weights = mix_weights(sel_probs)
    fixed_map = mech_map[~mech_map.index.isin(set(weights.index))]
    print(f"  selector: top1={sel['diag']['test_top1']:.3f}", flush=True)

    print("  OOF + main base models...", flush=True)
    oof_tg = _generate_oof_time_gap(train, val)
    oof_lr = _generate_oof_lambdarank_winp(train, val)
    main_tg = _train_main_time_gap(train, val)
    main_lr = _train_main_lambdarank(train, val)

    def stackify(frame, rated, oof_vals=None):
        f = attach(frame, od_feats, field_shares)
        if oof_vals is not None:
            f["oof_time_gap_pred"], f["oof_lambdarank_win_p"] = oof_vals
        else:
            f["oof_time_gap_pred"] = main_tg.predict(f)
            f["oof_lambdarank_win_p"] = np.asarray(
                main_lr.predict_win_probabilities(f))
        assert (f["competition_id"].to_numpy()
                == rated["competition_id"].to_numpy()).all()
        for col in RATING_FEATURE_COLS:
            f[col] = rated[col].to_numpy()
        return f

    train_a = stackify(train, train_r, (oof_tg, oof_lr))
    val_a = stackify(val, val_r)
    test_a = stackify(test, test_r)
    train_k = key_attach(train_a, oracle_ext, **kw)
    val_k = key_attach(val_a, oracle_ext, **kw)

    print("  Training ARM A (bucket_a + cont_a — the only pricing model)...",
          flush=True)
    bucket_a, cont_a, _ = _train_bucket_and_contender(train_a, val_a, label)
    print("  Training bucket_k (ranking channel only; cont_k discarded)...",
          flush=True)
    bucket_k, _cont_unused, _ = _train_bucket_and_contender(train_k, val_k, label)
    n_classes = cont_a.config.lgb_params.get("num_class", 8)
    cls_map = comp_class_map(labels, test)

    # ---- ranking scores per arm (test frame) ----
    exp = {"A": np.asarray(bucket_a.predict_continuous(test_a), dtype=float)}
    test_korc = key_attach(test_a, oracle_ext, **kw)
    exp["rorc"] = np.asarray(bucket_k.predict_continuous(test_korc), dtype=float)
    exp["rmix"] = mixed_expected(test_a, bucket_k, fixed_map, weights, **kw)

    # ---- pricing: cont_a on each arm's pool (same feature frame test_a) ----
    std_res, price_recs, surf_recs = {}, [], []
    proba_cache: Dict[int, np.ndarray] = {}
    for arm in ARMS:
        sel_mask = std_pool(test_a, exp[arm])
        rows_key = tuple(np.flatnonzero(sel_mask)[:50])
        pr = cont_a.predict_proba(test_a[sel_mask])
        std_res[arm], recs = sliced_market_eval(
            test_a[sel_mask], pr, n_classes, cls_map)
        recs["arm"], recs["fold"], recs["frame"] = arm, label, "standard"
        price_recs.append(recs)
        surf_recs += pool_records(test_a, exp[arm], labels, place_map, arm,
                                  label, item_map,
                                  None if arm == "A" else mech_map, sel_probs)

    # ---- honest frame ----
    train_end = pd.to_datetime(fold["train_end"])
    val_end = pd.to_datetime(fold["val_end"])
    h_tr = head_frame[head_frame["competition_date"] <= train_end]
    h_vl = head_frame[(head_frame["competition_date"] > train_end)
                      & (head_frame["competition_date"] <= val_end)]
    h_te = head_frame[head_frame["competition_date"] > val_end]
    head = DNFPredictor()
    head.train(h_tr, h_vl)
    p_te = head.predict_dnf_proba(h_te)
    auc = evaluate_dnf(h_te["dnf"].values, p_te)["auc"]
    p_map = dict(zip(zip(h_te["competition_id"].values,
                         h_te["rider_id"].values), p_te))
    dnf_rows, _ = build_dnf_pipeline_rows(
        test, dnf_labels, dnf_snaps, str(DEFAULT_DB_PATH),
        test_period_start=val_end)
    pool_plain = pd.concat([test.assign(is_dnf_row=0),
                            dnf_rows.assign(is_dnf_row=1)], ignore_index=True)
    print(f"  Honest pool {len(pool_plain):,} rows (head AUC={auc:.3f})",
          flush=True)
    pool_rated = attach_rating_features(pool_plain, rating_snaps,
                                        db_path=DEFAULT_DB_PATH)
    pool_a = attach(pool_rated, od_feats, field_shares)
    pool_a["oof_time_gap_pred"] = main_tg.predict(pool_a)
    pool_a["oof_lambdarank_win_p"] = np.asarray(
        main_lr.predict_win_probabilities(pool_a))

    hexp = {"A": np.asarray(bucket_a.predict_continuous(pool_a), dtype=float)}
    pool_korc = key_attach(pool_a, oracle_ext, **kw)
    hexp["rorc"] = np.asarray(bucket_k.predict_continuous(pool_korc), dtype=float)
    hexp["rmix"] = mixed_expected(pool_a, bucket_k, fixed_map, weights, **kw)

    hon_res = {}
    for arm in ARMS:
        sel_mask = honest_pool_mask(pool_a, hexp[arm])
        sub = pool_a[sel_mask]
        pr = cont_a.predict_proba(sub)
        keys = list(zip(sub["competition_id"].to_numpy(),
                        sub["rider_id"].to_numpy()))
        p_fin = 1.0 - np.array([p_map.get(k, 0.0) for k in keys])
        hon_res[arm], recs = sliced_market_eval(sub, pr, n_classes, cls_map,
                                                p_finish=p_fin)
        recs["arm"], recs["fold"], recs["frame"] = arm, label, "honest"
        price_recs.append(recs)

    for arm in ARMS:
        a = hon_res[arm].get("all", {}).get("market_avg_log_loss", np.nan)
        r = hon_res[arm].get("residual", {}).get("market_avg_log_loss", np.nan)
        print(f"    {arm:<5s} honest all={a:.4f} residual={r:.4f}", flush=True)

    return ({"fold_label": label, "skipped": False,
             "selector": sel["diag"], "standard": std_res, "honest": hon_res,
             "dnf_head_auc": float(auc)},
            price_recs, surf_recs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    started = datetime.now()
    folds = list(FOLDS)
    if args.smoke:
        folds = FOLDS[-1:]
        H.CONTENDER_CONFIG["n_estimators"] = 120
        H.CONTENDER_CONFIG["early_stopping"] = 30
        H.TIME_GAP_OOF_CONFIG["n_estimators"] = 80
        H.LAMBDARANK_OOF_CONFIG["n_estimators"] = 150
        H.TIME_GAP_MAIN_CONFIG["n_estimators"] = 120
        H.LAMBDARANK_MAIN_CONFIG["n_estimators"] = 200
        print("*** SMOKE: 1 fold, reduced budgets ***", flush=True)

    print("=" * 74, flush=True)
    print("DAY-MENU RETRIEVAL-ONLY GATE — kernod ranks, clean heads price",
          flush=True)
    print("=" * 74, flush=True)

    sig = load_signature_table()
    od_feats = oneday_b4(sig)
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    labels = build_labels(sig)
    hist = build_rider_history(sig)

    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TEMP TABLE lc(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO lc VALUES (?)",
                    [(int(i),) for i in labels.comp_id])
    places = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN lc ON lc.id = r.competition_id""", con)
    con.close()
    places["place_n"] = pd.to_numeric(places.place, errors="coerce")
    place_map = places.set_index(["competition_id", "rider_id"]).place_n

    rating_snaps = (load_snapshots(DEFAULT_SNAPSHOT_PATH)
                    if DEFAULT_SNAPSHOT_PATH.exists() else build_and_save())
    df = _load_full_df()
    df["rider_id"] = df["rider_id"].astype(np.int64)
    df_rated = attach_rating_features(df, rating_snaps, db_path=DEFAULT_DB_PATH)
    assert (df_rated["competition_id"].to_numpy()
            == df["competition_id"].to_numpy()).all()
    print(f"Loaded {len(df):,} rows", flush=True)
    comp_selfeats = build_selector_features(df, sig)

    dnf_labels = load_labels()
    dnf_labels = dnf_labels[dnf_labels["competition_date"].notna()
                            & dnf_labels["rider_id"].notna()].copy()
    dnf_labels["rider_id"] = dnf_labels["rider_id"].astype("int64")
    dnf_labels = add_asof_dates(dnf_labels)
    dnf_snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=dnf_labels, snaps=dnf_snaps,
                                     start_date=START_DATE)
    head_frame["competition_date"] = pd.to_datetime(head_frame["competition_date"])

    fold_results, price_all, surf_all = [], [], []
    for i, fold in enumerate(folds):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(folds)} (test={fold['label']}+)\n{'─'*60}",
              flush=True)
        fr, pr, sr = run_fold(i, fold, df, df_rated, od_feats, field_shares,
                              rating_snaps, labels, hist, comp_selfeats,
                              place_map, dnf_labels, dnf_snaps, head_frame,
                              args.smoke)
        fold_results.append(fr)
        price_all += pr
        surf_all += sr

    usable = [f for f in fold_results if not f.get("skipped")]
    surf_df = pd.DataFrame(surf_all)

    agg: Dict[str, Any] = {"honest_deltas": {}, "standard_deltas": {},
                           "surfacing": {}}
    for arm in ("rorc", "rmix"):
        for frame_name, store in (("honest", "honest_deltas"),
                                  ("standard", "standard_deltas")):
            agg[store][arm] = {}
            for s in ("all", "residual", "gc_day", "bunch", "one_day"):
                block = {}
                for metric in ("market_avg_log_loss", "win_log_loss"):
                    ds = [f[frame_name][arm][s][metric] - f[frame_name]["A"][s][metric]
                          for f in usable
                          if s in f[frame_name][arm] and s in f[frame_name]["A"]]
                    if ds:
                        block[metric] = {
                            "mean": float(np.mean(ds)),
                            "per_fold": [float(d) for d in ds],
                            "folds_nonpos": int(sum(1 for d in ds if d <= 0))}
                if block:
                    agg[store][arm][s] = block

        base = surf_df[(surf_df.arm == "A")]
        t = surf_df[(surf_df.arm == arm)]
        sl = {}
        for dc in ("residual", "gc_day", "bunch"):
            b = base[base.day_class == dc]
            k = t[t.day_class == dc]
            m = b.merge(k, on=["fold", "comp_id"], suffixes=("_b", "_t"))
            entry = {"n_comps": int(m.comp_id.nunique())}
            for metric in ("winner_in_pool15", "winner_model_rank",
                           "front_recall15", "board_front_cosine"):
                pf = (m.groupby("fold").apply(
                    lambda g: g[f"{metric}_t"].mean() - g[f"{metric}_b"].mean(),
                    include_groups=False))
                entry[metric] = {
                    "pooled_delta": float(m[f"{metric}_t"].mean()
                                          - m[f"{metric}_b"].mean()),
                    "per_fold": {kk: float(v) for kk, v in pf.items()},
                    "folds_nonneg": int((pf >= 0).sum()),
                    "folds_neg": int((pf < 0).sum())}
            sl[dc] = entry
        agg["surfacing"][arm] = sl

    # capture guardrails from per-comp records (winner_in_pool ~ capture proxy
    # not used; compute from std slices instead)
    t = THRESHOLDS
    n = len(usable)
    g1 = agg["honest_deltas"]["rmix"].get("all", {}).get("market_avg_log_loss")
    g1w = agg["honest_deltas"]["rmix"].get("all", {}).get("win_log_loss")
    r = agg["surfacing"]["rmix"]["residual"]
    checks = {
        "p1_mkt": bool(g1 and g1["mean"] <= t["p1_honest_mkt_ll_mean_max"]
                       and sum(1 for v in g1["per_fold"]
                               if v <= t["p1_fold_ll_max"])
                       >= min(t["p1_folds_within_min"], n)),
        "p1_win": bool(g1w and g1w["mean"] <= t["p1_win_ll_mean_max"]),
        "p2_pool15": bool(
            r["winner_in_pool15"]["pooled_delta"] >= t["p2_pool15_delta_min"]
            and r["winner_in_pool15"]["folds_nonneg"]
            >= min(t["p2_pool15_folds_nonneg_min"], n)),
        "p2_rank": bool(
            r["winner_model_rank"]["pooled_delta"] <= t["p2_winner_rank_delta_max"]
            and r["winner_model_rank"]["folds_neg"]
            >= min(t["p2_winner_rank_folds_neg_min"], n)),
    }
    agg["pass_checks_rmix"] = checks
    agg["PASS_rmix"] = bool(all(checks.values()))

    print("\n" + "=" * 92, flush=True)
    for arm in ("rorc", "rmix"):
        h = agg["honest_deltas"][arm]
        s = agg["surfacing"][arm]["residual"]
        m = h.get("all", {}).get("market_avg_log_loss", {})
        w = h.get("all", {}).get("win_log_loss", {})
        print(f"{arm}: honest mkt_ll {m.get('mean', np.nan):+.4f} "
              f"[{' '.join(f'{v:+.4f}' for v in m.get('per_fold', []))}]  "
              f"win_ll {w.get('mean', np.nan):+.4f}", flush=True)
        print(f"   residual: pool15 {s['winner_in_pool15']['pooled_delta']:+.4f} "
              f"({s['winner_in_pool15']['folds_nonneg']}/{n})  "
              f"rank {s['winner_model_rank']['pooled_delta']:+.3f} "
              f"({s['winner_model_rank']['folds_neg']}/{n} neg)  "
              f"recall {s['front_recall15']['pooled_delta']:+.4f}", flush=True)
    print(f"\nPASS checks (rmix): {json.dumps(agg['pass_checks_rmix'])}", flush=True)
    print(f"PASS_rmix = {agg['PASS_rmix']}", flush=True)

    ended = datetime.now()
    ts = ended.strftime("%Y%m%d_%H%M%S")
    tag = "smoke_" if args.smoke else ""
    price_df = pd.concat(price_all, ignore_index=True)
    price_path = OUT_DIR / f"day_menu_gate6_pricing_{tag}{ts}.csv.gz"
    surf_path = OUT_DIR / f"day_menu_gate6_surfacing_{tag}{ts}.csv.gz"
    price_df.to_csv(price_path, index=False, compression="gzip")
    surf_df.to_csv(surf_path, index=False, compression="gzip")
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": folds, "thresholds": THRESHOLDS,
                   "k_menu": K_MENU, "smoke": args.smoke},
        "fold_results": fold_results, "aggregated": agg,
        "pricing_csv": price_path.name, "surfacing_csv": surf_path.name,
    }
    path = OUT_DIR / f"day_menu_gate6_retrieval_cv_{tag}{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)",
          flush=True)


if __name__ == "__main__":
    main()
