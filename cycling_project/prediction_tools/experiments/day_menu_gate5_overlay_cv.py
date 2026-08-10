"""
Day-menu step-4b — OVERLAY (home-turf) gate: A vs korc, day-class-sliced
pricing (2026-08-09, follows the step-4 review discussion).

The user's framing: the system is operated the way the TdF 2026 was run —
judgment in the loop, a day key supplied per read — not as an unattended
engine. Step-4 established that feature-attachment fails GLOBALLY even at
oracle tier (korc−A honest market LL +0.0100, 0/5 folds): wiring the
columns into the shared heads damages pricing on every race, keys known or
not. The live question for the scenario-layer product is therefore local:
**when the key is known, does the conditional model price BETTER ON ITS
HOME TURF — the labeled hard days?** korc bounds the judgment-keyed
product from above; step-4's kmix bounds it from below.

Arms (per fold, paired): A = shipped arm-C stack; korc = stack +
menu8kernod with ORACLE keys at train/val/test (training identical to
step-4's shared K model). No selector, no mixing.

Metrics: market metrics sliced by DAY CLASS (residual / gc_day / bunch /
itt / stage_unlabeled / one_day) on the standard test frame AND the honest
DNF-adjusted frame; per-comp market-loss contributions persisted per arm
(any further slice computable offline); surfacing recap per slice.

PRE-REGISTERED READING (registered before the run; korc − A, residual
slice, honest-adjusted market_avg_log_loss, paired by fold):
  home-turf WIN  iff pooled mean <= 0.0000 and >= 4/5 folds <= 0
  home-turf HARM iff pooled mean >= +0.0020 and >= 4/5 folds >= 0
  otherwise INCONCLUSIVE. win_log_loss reported alongside (the board most
  read in practice). Consequence mapping: WIN -> the scenario layer may
  serve conditional BOARDS (judgment-keyed); HARM or INCONCLUSIVE -> the
  scenario layer serves RETRIEVAL (pool/shortlist guidance) only and
  production prices stand.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.day_menu_gate5_overlay_cv [--smoke]
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

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
    key_attach,
    pool_records,
)
from cycling_project.prediction_tools.experiments.dnf_market_adjustment_cv import (
    TOP_N,
    adjust_markets,
    build_dnf_pipeline_rows,
    market_metrics,
    proba_to_markets,
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
ARMS = ("A", "korc")
SLICES = ("residual", "gc_day", "bunch", "itt", "stage_unlabeled", "one_day", "all")

READING = {
    "win_mean_max": 0.0000, "win_folds_nonpos_min": 4,
    "harm_mean_min": 0.0020, "harm_folds_nonneg_min": 4,
}


def comp_class_map(labels: pd.DataFrame, frame: pd.DataFrame) -> pd.Series:
    """comp_id -> day-class slice name for every comp in frame."""
    m = labels.set_index("comp_id")["day_class"]
    comps = frame[["competition_id", "competition_type"]].drop_duplicates("competition_id")
    cls = comps.competition_id.map(m)
    cls = cls.where(cls.notna(),
                    np.where(comps.competition_type.values == "one_day",
                             "one_day", "stage_unlabeled"))
    return pd.Series(cls.values, index=comps.competition_id.values)


def sliced_market_eval(
    pool_rows: pd.DataFrame, proba: np.ndarray, n_classes: int,
    cls_map: pd.Series, p_finish: np.ndarray = None,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Market metrics per day-class slice + per-comp contributions.

    pool_rows: the already-selected top-15 rows (per comp), with
    place_bucket / competition_id / (is_dnf_row when honest).
    p_finish: when given, markets are DNF-adjusted per comp (honest frame).
    """
    y = np.clip(pool_rows["place_bucket"].to_numpy().astype(int), 0, n_classes - 1)
    is_dnf = (pool_rows["is_dnf_row"].to_numpy().astype(bool)
              if "is_dnf_row" in pool_rows.columns
              else np.zeros(len(pool_rows), dtype=bool))
    comp_ids = pool_rows["competition_id"].to_numpy()
    mp = proba_to_markets(proba)
    if p_finish is not None:
        mp = adjust_markets(mp, p_finish, comp_ids)
    cls = pd.Series(comp_ids).map(cls_map).fillna("stage_unlabeled").to_numpy()

    out: Dict[str, Any] = {}
    for s in SLICES:
        rows = np.ones(len(y), bool) if s == "all" else (cls == s)
        if rows.sum() == 0:
            continue
        m = market_metrics({k: v[rows] for k, v in mp.items()}, y[rows], is_dnf[rows])
        m["n_rows"] = int(rows.sum())
        m["n_comps"] = int(pd.unique(comp_ids[rows]).size)
        out[s] = m

    recs = []
    order = pd.Series(np.arange(len(comp_ids)))
    for comp, idx in order.groupby(pd.Series(comp_ids)):
        rows = idx.to_numpy()
        m = market_metrics({k: v[rows] for k, v in mp.items()}, y[rows], is_dnf[rows])
        recs.append({
            "comp_id": int(comp), "day_class": cls[rows[0]],
            "n_rows": int(len(rows)),
            "market_avg_ll": m.get("market_avg_log_loss"),
            "win_ll": m.get("win_log_loss"),
            "winner_in_pool": bool((y[rows] == 0).any()),
        })
    return out, pd.DataFrame(recs)


def std_pool(frame: pd.DataFrame, expected: np.ndarray) -> np.ndarray:
    r = (pd.Series(expected, index=frame.index)
         .groupby(frame["competition_id"]).rank())
    return (r <= TOP_N).to_numpy()


def honest_pool_mask(pool: pd.DataFrame, expected: np.ndarray) -> np.ndarray:
    r = (pd.Series(expected, index=pool.index)
         .groupby(pool["competition_id"]).rank())
    return (r <= TOP_N).to_numpy()


def run_fold(i, fold, df, df_rated, od_feats, field_shares, rating_snaps,
             labels, hist, place_map, dnf_labels, dnf_snaps, head_frame):
    label = fold["label"]
    train, val, test = _slice_fold(df, fold)
    train_r, val_r, test_r = _slice_fold(df_rated, fold)
    if len(test) == 0:
        return {"fold_label": label, "skipped": True}, [], []
    print(f"  train {len(train):,} | test {len(test):,} rows "
          f"({test['competition_id'].nunique():,} comps)", flush=True)

    feats, item_map, canon = stage_menu_feats(labels, fold["train_end"], K_MENU)
    cum, items = kernel_cumulants(hist, canon)
    oracle_ext = extend_item_map_oneday(item_map, od_feats, canon)
    stage_comps = set(labels.comp_id)
    kw = dict(canon=canon, cum=cum, items=items,
              field_shares=field_shares, stage_comps=stage_comps)

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
    test_k = key_attach(test_a, oracle_ext, **kw)

    print("  Training ARM A...", flush=True)
    bucket_a, cont_a, _ = _train_bucket_and_contender(train_a, val_a, label)
    print("  Training ARM korc...", flush=True)
    bucket_k, cont_k, _ = _train_bucket_and_contender(train_k, val_k, label)
    n_classes = cont_a.config.lgb_params.get("num_class", 8)

    cls_map = comp_class_map(labels, test)

    std_res, price_recs, surf_recs = {}, [], []
    for arm, (fr, bucket, cont) in (("A", (test_a, bucket_a, cont_a)),
                                    ("korc", (test_k, bucket_k, cont_k))):
        e = np.asarray(bucket.predict_continuous(fr), dtype=float)
        sel = std_pool(fr, e)
        pr = cont.predict_proba(fr[sel])
        std_res[arm], recs = sliced_market_eval(fr[sel], pr, n_classes, cls_map)
        recs["arm"], recs["fold"], recs["frame"] = arm, label, "standard"
        price_recs.append(recs)
        surf_recs += pool_records(fr, e, labels, place_map, arm, label,
                                  item_map, None, None)

    # ---- honest DNF-adjusted frame ----
    train_end = pd.to_datetime(fold["train_end"])
    val_end = pd.to_datetime(fold["val_end"])
    h_tr = head_frame[head_frame["competition_date"] <= train_end]
    h_vl = head_frame[(head_frame["competition_date"] > train_end)
                      & (head_frame["competition_date"] <= val_end)]
    h_te = head_frame[head_frame["competition_date"] > val_end]
    print(f"  DNF head ({len(h_tr):,} rows)...", flush=True)
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
    print(f"  Honest pool {len(pool_plain):,} rows (head AUC={auc:.3f})", flush=True)

    pool_rated = attach_rating_features(pool_plain, rating_snaps,
                                        db_path=DEFAULT_DB_PATH)
    pool_a = attach(pool_rated, od_feats, field_shares)
    pool_a["oof_time_gap_pred"] = main_tg.predict(pool_a)
    pool_a["oof_lambdarank_win_p"] = np.asarray(
        main_lr.predict_win_probabilities(pool_a))
    pool_k = key_attach(pool_a, oracle_ext, **kw)

    hon_res = {}
    for arm, (fr, bucket, cont) in (("A", (pool_a, bucket_a, cont_a)),
                                    ("korc", (pool_k, bucket_k, cont_k))):
        e = np.asarray(bucket.predict_continuous(fr), dtype=float)
        sel = honest_pool_mask(fr, e)
        sub = fr[sel]
        pr = cont.predict_proba(sub)
        keys = list(zip(sub["competition_id"].to_numpy(),
                        sub["rider_id"].to_numpy()))
        p_fin = 1.0 - np.array([p_map.get(k, 0.0) for k in keys])
        hon_res[arm], recs = sliced_market_eval(sub, pr, n_classes, cls_map,
                                                p_finish=p_fin)
        recs["arm"], recs["fold"], recs["frame"] = arm, label, "honest"
        price_recs.append(recs)

    for s in ("residual", "gc_day", "all"):
        a = hon_res["A"].get(s, {}).get("market_avg_log_loss", np.nan)
        k = hon_res["korc"].get(s, {}).get("market_avg_log_loss", np.nan)
        print(f"    honest {s:<9s} A={a:.4f} korc={k:.4f} (d={k-a:+.4f})", flush=True)

    return ({"fold_label": label, "skipped": False,
             "standard": std_res, "honest": hon_res, "dnf_head_auc": float(auc)},
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
    print("DAY-MENU OVERLAY GATE — A vs korc, day-class-sliced pricing", flush=True)
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
                              rating_snaps, labels, hist, place_map,
                              dnf_labels, dnf_snaps, head_frame)
        fold_results.append(fr)
        price_all += pr
        surf_all += sr

    usable = [f for f in fold_results if not f.get("skipped")]
    agg: Dict[str, Any] = {"deltas": {}}
    for frame_name in ("standard", "honest"):
        agg["deltas"][frame_name] = {}
        for s in SLICES:
            block = {}
            for metric in ("market_avg_log_loss", "win_log_loss"):
                ds = [f[frame_name]["korc"][s][metric] - f[frame_name]["A"][s][metric]
                      for f in usable
                      if s in f[frame_name]["korc"] and s in f[frame_name]["A"]]
                if ds:
                    block[metric] = {
                        "mean": float(np.mean(ds)),
                        "per_fold": [float(d) for d in ds],
                        "folds_nonpos": int(sum(1 for d in ds if d <= 0))}
            if block:
                agg["deltas"][frame_name][s] = block

    r = agg["deltas"].get("honest", {}).get("residual", {}).get("market_avg_log_loss")
    n = len(usable)
    verdict = "INCONCLUSIVE"
    if r:
        if (r["mean"] <= READING["win_mean_max"]
                and r["folds_nonpos"] >= min(READING["win_folds_nonpos_min"], n)):
            verdict = "HOME_TURF_WIN"
        elif (r["mean"] >= READING["harm_mean_min"]
              and (n - r["folds_nonpos"]) >= min(READING["harm_folds_nonneg_min"], n)):
            verdict = "HOME_TURF_HARM"
    agg["residual_honest_reading"] = verdict

    print("\n" + "=" * 92, flush=True)
    print("KORC − A market_avg_log_loss by slice (honest frame first)", flush=True)
    for frame_name in ("honest", "standard"):
        for s in SLICES:
            d = agg["deltas"][frame_name].get(s, {}).get("market_avg_log_loss")
            if d:
                per = " ".join(f"{v:+.4f}" for v in d["per_fold"])
                print(f"  {frame_name:<9s} {s:<16s} {d['mean']:+.4f} "
                      f"({d['folds_nonpos']}/{len(d['per_fold'])} <=0)  [{per}]",
                      flush=True)
        print("", flush=True)
    print(f"RESIDUAL HONEST READING: {verdict}", flush=True)

    ended = datetime.now()
    ts = ended.strftime("%Y%m%d_%H%M%S")
    tag = "smoke_" if args.smoke else ""
    price_df = pd.concat(price_all, ignore_index=True)
    surf_df = pd.DataFrame(surf_all)
    price_path = OUT_DIR / f"day_menu_gate5_pricing_{tag}{ts}.csv.gz"
    surf_path = OUT_DIR / f"day_menu_gate5_surfacing_{tag}{ts}.csv.gz"
    price_df.to_csv(price_path, index=False, compression="gzip")
    surf_df.to_csv(surf_path, index=False, compression="gzip")
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": folds, "reading": READING, "k_menu": K_MENU,
                   "smoke": args.smoke},
        "fold_results": fold_results, "aggregated": agg,
        "pricing_csv": price_path.name, "surfacing_csv": surf_path.name,
    }
    path = OUT_DIR / f"day_menu_gate5_overlay_cv_{tag}{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
