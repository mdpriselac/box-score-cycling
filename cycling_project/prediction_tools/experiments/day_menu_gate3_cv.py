"""
Day-type menu step-3 gate — rider-side kernel ladders on top of the day fill.

Adds four as-of-then rider features answering "how does this rider fare on
days LIKE TODAY" — the mechanism half the step-2 oracle showed was missing
(day fill alone: composition +0.021 5/5, winner rank -0.5..-0.7 in 20/20
fold-arms, but pool entry only ~+1pp against a 49.5% baseline miss rate).

Kernel design (day_type_menu_plan.md step 3, session decisions 2026-08-08):
  For a target stage row with assigned menu item m (canonical signature S_m,
  fold-honest train-member canonicals), each history row h of the rider in a
  signature-covered comp (stage OR one-day — one-day history transfers into
  stage days through the kernel; that is the point) gets weight
      w_h = cos(s_h, S_m)^GAMMA * exp(-lambda * (t - t_h))
  with s_h the comp's REALIZED top-15 6-archetype shares (past outcomes,
  as-of-then clean), GAMMA=8, half-life 730 d. Kernel target is the item
  CANONICAL, never the target race's own realized signature (leak rule).

  dtm_k_expos      decayed total similar-day exposure (sum of w)
  dtm_k_attend     weighted top-15 rate on similar days      (attendance)
  dtm_k_top3       weighted top-3 rate on similar days       (kick)
  dtm_k_perf_place weighted mean finishing place over the rider's top-15
                   rows on similar days                       (standing)
  attend/top3/perf NaN when dtm_k_expos < 3 effective rows; all four NaN on
  one_day / gc / unlabeled rows (namespace isolation, od stack untouched).

Arms: base (production) / menu8sep (step-2 reference day fill, k=8, dtm_*)
/ menu8kern (= menu8sep + the four kernel cols). Day fills IDENTICAL in the
two menu arms (bunch item included) so menu8kern - menu8sep is purely the
rider-side increment; dropping the bunch fill is a separate later ablation.

PRE-REGISTERED RULE (registered before the run; residual slice, C - base,
paired by fold). Change from step 2, agreed with the user: the continuous
winner_model_rank replaces the binary pool metric as primary-1 (the binary
bar stays reported as the headline aspiration, not gated):
  PASS iff  winner_model_rank pooled delta <= -1.00 with >= 4/5 folds < 0
        AND board_front_cosine pooled delta >= +0.010 with >= 4/5 folds >= 0
  guardrails: all.top4_log_loss <= +0.010, all.winner_capture >= -0.005,
              |one_day.winner_capture| <= 0.005.
  Tracked headline: winner_in_pool15 (aspiration +0.020 from step 2).

ITERATION 2 (2026-08-08, registered BEFORE the run): run 1's menu8kern
cleared both primaries decisively (winner_rank -2.09, negative 5/5 folds;
cosine +0.0277 5/5; pool15 +2.38pp meeting the retired binary bar; global
winner +0.81pp with kern >= base 5/5) but tripped the od band at -0.85pp
(mixed 3/5-negative, od ll +0.009 — weaker than run-1-of-step-2's systematic
collision but not clean). Cause: od rows traverse dtm_k_* splits via the
NaN-default path. Fix arm menu8kernod: od rows get REAL kernel features,
keyed to the nearest menu canonical (by cosine) of their OWN as-of-then B4
signature — same feature semantics ("record on days like today"), day key =
menu canonical for stages / quantized B4 for one-days. AMENDED GUARDRAIL
for menu8kernod only, since its od features differ from base BY DESIGN: od
winner capture >= -0.5pp (one-sided, degradation-only) AND od top4_log_loss
<= +0.010. menu8kern keeps the original two-sided band. All other
thresholds unchanged.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.day_menu_gate3_cv [--smoke]
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
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    attach,
    load_signature_table,
    oneday_b4,
)
from cycling_project.prediction_tools.experiments.day_menu_gate_cv import (
    ARCH,
    DB_PATH,
    POOL_N,
    attach_menu,
    build_labels,
    slice_deltas,
    stage_menu_feats,
    surfacing_records,
)
from cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold import (
    FOLDS,
    START_DATE,
    _capture_feature_importance,
    _evaluate_on_test,
    _load_full_df,
    _slice_fold,
    _train_bucket_and_contender,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path("experiments")
K_MENU = 8
GAMMA = 8.0
HALF_LIFE_DAYS = 730.0
LAM = np.log(2.0) / HALF_LIFE_DAYS
EPOCH = pd.Timestamp("2010-01-01")
MIN_EFF_N = 3.0
S6 = [f"top15_{a}" for a in ARCH]
SIGC = [f"sig_{a}" for a in ARCH]
KERNEL_COLS = ["dtm_k_expos", "dtm_k_attend", "dtm_k_top3", "dtm_k_perf_place"]
CUM_KINDS = ["expos", "att", "top3", "perf"]

THRESHOLDS = {
    "winner_model_rank_delta_max": -1.00,
    "winner_rank_fold_consistency_min": 4,
    "board_front_cosine_delta": 0.010,
    "cosine_fold_consistency_min": 4,
    "headline_winner_in_pool15_aspiration": 0.020,
    "guard_top4_log_loss_max": 0.010,
    "guard_winner_capture_min": -0.005,
    "guard_oneday_winner_abs": 0.005,
}


def unit(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, float)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1
    return m / n


def extend_item_map_oneday(item_map: pd.Series, od_feats: pd.DataFrame,
                           canon: pd.DataFrame) -> pd.Series:
    """One-day comps -> nearest menu canonical to their as-of-then B4 signature."""
    odv = od_feats.dropna(subset=SIGC)
    U = unit(odv[SIGC].values)
    C = unit(canon[SIGC].values)
    best = (U @ C.T).argmax(1)
    om = pd.Series(canon.index.values[best], index=odv.comp_id.values)
    return pd.concat([item_map, om])


def build_rider_history(sig: pd.DataFrame) -> pd.DataFrame:
    """Every finisher row in a signature-covered comp, with realized shares."""
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TEMP TABLE sc(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO sc VALUES (?)",
                    [(int(i),) for i in sig.comp_id])
    rr = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN sc ON sc.id = r.competition_id""", con)
    con.close()
    rr["place_n"] = pd.to_numeric(rr.place, errors="coerce")
    rr = rr[rr.place_n.notna()]
    hist = rr.merge(sig[["comp_id", "date"] + S6],
                    left_on="competition_id", right_on="comp_id")
    hist["date"] = pd.to_datetime(hist["date"])
    hist["top15"] = (hist.place_n <= 15).astype(float)
    hist["top3"] = (hist.place_n <= 3).astype(float)
    logger.info("rider history: %d rows, %d riders, %d comps",
                len(hist), hist.rider_id.nunique(), hist.comp_id.nunique())
    return hist


def kernel_cumulants(hist: pd.DataFrame, canon: pd.DataFrame) -> tuple:
    """Per-rider date-sorted cumulative kernel sums for every menu item.

    Decay factorization: sum_h w_h * exp(-lam*(t - t_h)) =
    exp(-lam*t) * sum_h w_h * exp(lam*t_h), so cumulants store the growth-
    weighted sums and the target divides by exp(lam*t) (ratios cancel it).
    """
    items = list(canon.index)
    S = unit(hist[S6].values)
    C = unit(canon[SIGC].values)
    W = np.clip(S @ C.T, 0, None) ** GAMMA        # n_hist x n_items
    growth = np.exp(LAM * (hist.date - EPOCH).dt.days.to_numpy())
    W = W * growth[:, None]

    cum = hist[["rider_id", "date"]].copy()
    top15 = hist.top15.to_numpy()
    top3 = hist.top3.to_numpy()
    place = hist.place_n.to_numpy()
    for j, item in enumerate(items):
        cum[f"expos__{item}"] = W[:, j]
        cum[f"att__{item}"] = W[:, j] * top15
        cum[f"top3__{item}"] = W[:, j] * top3
        cum[f"perf__{item}"] = W[:, j] * top15 * place
    cum = cum.sort_values(["date", "rider_id"], kind="mergesort")
    val_cols = [c for c in cum.columns if "__" in c]
    cum[val_cols] = cum.groupby("rider_id")[val_cols].cumsum()
    return cum, items


def attach_kernels(df: pd.DataFrame, cum: pd.DataFrame, items: List[str],
                   item_map: pd.Series) -> pd.DataFrame:
    """Attach the four dtm_k_* features (stage rows with a menu item only)."""
    out = df.copy()
    out["_item"] = out["competition_id"].map(item_map)
    out["_date"] = pd.to_datetime(out["competition_date"])
    order = np.argsort(out["_date"].values, kind="mergesort")
    t = out.iloc[order][["rider_id", "_date"]].reset_index()
    merged = pd.merge_asof(
        t, cum.rename(columns={"date": "_date"}),
        on="_date", by="rider_id", direction="backward",
        allow_exact_matches=False)
    merged = merged.set_index("index").reindex(out.index)

    item_pos = {it: i for i, it in enumerate(items)}
    pos = out["_item"].map(item_pos)
    has = pos.notna().to_numpy()
    pos_i = pos.fillna(0).astype(int).to_numpy()
    rows = np.arange(len(out))
    mats = {kind: merged[[f"{kind}__{it}" for it in items]].to_numpy(dtype=float)
            for kind in CUM_KINDS}
    sel = {kind: np.where(has, mats[kind][rows, pos_i], np.nan)
           for kind in CUM_KINDS}
    decay = np.exp(LAM * (out["_date"] - EPOCH).dt.days.to_numpy())
    expos = sel["expos"] / decay
    with np.errstate(invalid="ignore", divide="ignore"):
        attend = np.where(sel["expos"] > 0, sel["att"] / sel["expos"], np.nan)
        top3 = np.where(sel["expos"] > 0, sel["top3"] / sel["expos"], np.nan)
        perf = np.where(sel["att"] > 0, sel["perf"] / sel["att"], np.nan)
    thin = ~(expos >= MIN_EFF_N)
    attend[thin] = np.nan
    top3[thin] = np.nan
    perf[thin] = np.nan
    out["dtm_k_expos"] = expos
    out["dtm_k_attend"] = attend
    out["dtm_k_top3"] = top3
    out["dtm_k_perf_place"] = perf
    out.drop(columns=["_item", "_date"], inplace=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    started = datetime.now()
    folds = FOLDS
    if args.smoke:
        folds = FOLDS[-1:]
        H.CONTENDER_CONFIG["n_estimators"] = 60
        H.CONTENDER_CONFIG["early_stopping"] = 10
        print("[SMOKE MODE] 1 fold, 60 trees", flush=True)

    print("=" * 70, flush=True)
    print("DAY-MENU STEP-3 GATE — base vs menu8sep vs menu8kern", flush=True)
    print("=" * 70, flush=True)

    sig = load_signature_table()
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    od_feats = oneday_b4(sig)
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

    df = _load_full_df()
    df["rider_id"] = df["rider_id"].astype(np.int64)
    print(f"Loaded {len(df):,} rows, {df['competition_id'].nunique():,} comps", flush=True)

    all_records: List[Dict[str, Any]] = []
    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(folds):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(folds)} (test={fold['label']}+)\n{'─'*60}",
              flush=True)
        train, val, test = _slice_fold(df, fold)
        if len(test) == 0:
            continue
        feats, item_map, canon = stage_menu_feats(labels, fold["train_end"], K_MENU)
        cum, items = kernel_cumulants(hist, canon)

        base_tr = attach(train, od_feats, field_shares)
        base_va = attach(val, od_feats, field_shares)
        base_te = attach(test, od_feats, field_shares)
        menu_tr = attach_menu(base_tr, feats, field_shares)
        menu_va = attach_menu(base_va, feats, field_shares)
        menu_te = attach_menu(base_te, feats, field_shares)

        item_map_ext = extend_item_map_oneday(item_map, od_feats, canon)
        frames = {
            "base": (base_tr, base_va, base_te),
            "menu8kern": (attach_kernels(menu_tr, cum, items, item_map),
                          attach_kernels(menu_va, cum, items, item_map),
                          attach_kernels(menu_te, cum, items, item_map)),
            "menu8kernod": (attach_kernels(menu_tr, cum, items, item_map_ext),
                            attach_kernels(menu_va, cum, items, item_map_ext),
                            attach_kernels(menu_te, cum, items, item_map_ext)),
        }
        te_od = frames["menu8kernod"][2]
        od_rows = te_od[te_od.competition_type == "one_day"]
        st_rows = te_od[te_od.competition_type == "stage"]
        print(f"  kernel coverage: stage rows "
              f"{1 - st_rows['dtm_k_attend'].isna().mean():.1%}, "
              f"one_day rows (kernod arm) "
              f"{1 - od_rows['dtm_k_attend'].isna().mean():.1%}", flush=True)

        fr: Dict[str, Any] = {"fold_label": fold["label"]}
        for arm, (tr, va, te) in frames.items():
            print(f"  Training {arm.upper()}...", flush=True)
            bucket, cont, _ = _train_bucket_and_contender(tr, va, fold["label"])
            subsets = {"all": te,
                       "one_day": te[te.competition_type == "one_day"],
                       "stage": te[te.competition_type == "stage"]}
            fr[arm] = {name: dict(zip(("metrics", "n"),
                                      _evaluate_on_test(sub, bucket, cont, top_n=POOL_N)))
                       for name, sub in subsets.items() if len(sub)}
            recs = surfacing_records(te, bucket, labels, place_map, arm,
                                     fold["label"],
                                     item_map if arm != "base" else None)
            all_records.extend(recs)
            if arm.startswith("menu8kern"):
                fr[f"{arm}_importance"] = {
                    c: float(v) for c, v in _capture_feature_importance(cont).items()
                    if c.startswith("dtm_")}
            w = fr[arm]["all"]["metrics"].get("race_winner_capture_rate", np.nan)
            print(f"    {arm}: winner_capture={w:.4f}", flush=True)
        fold_results.append(fr)

    rec_df = pd.DataFrame(all_records)
    agg: Dict[str, Any] = {}
    arms_eval = ("menu8kern", "menu8kernod")
    for arm in arms_eval:
        agg[arm] = {"residual": slice_deltas(rec_df, arm, "residual"),
                    "gc_day": slice_deltas(rec_df, arm, "gc_day"),
                    "bunch": slice_deltas(rec_df, arm, "bunch")}
        guards = {}
        for metric, subset in [("top4_log_loss", "all"),
                               ("race_winner_capture_rate", "all"),
                               ("race_winner_capture_rate", "one_day"),
                               ("top4_log_loss", "one_day")]:
            ds = [fr[arm][subset]["metrics"][metric]
                  - fr["base"][subset]["metrics"][metric]
                  for fr in fold_results]
            guards[f"{subset}.{metric}"] = {
                "mean": float(np.mean(ds)), "per_fold": [float(d) for d in ds]}
        agg[arm]["guardrails"] = guards
        r = agg[arm]["residual"]
        t = THRESHOLDS
        n_run = len(fold_results)
        wr = r["winner_model_rank"]
        folds_neg = sum(1 for v in wr["per_fold"].values() if v < 0)
        od_w = guards["one_day.race_winner_capture_rate"]["mean"]
        if arm == "menu8kernod":
            od_ok = (od_w >= -t["guard_oneday_winner_abs"]
                     and guards["one_day.top4_log_loss"]["mean"] <= 0.010)
        else:
            od_ok = abs(od_w) <= t["guard_oneday_winner_abs"]
        agg[arm]["PASS"] = bool(
            wr["pooled_delta"] <= t["winner_model_rank_delta_max"]
            and folds_neg >= min(t["winner_rank_fold_consistency_min"], n_run)
            and r["board_front_cosine"]["pooled_delta"] >= t["board_front_cosine_delta"]
            and r["board_front_cosine"]["folds_nonneg"]
                >= min(t["cosine_fold_consistency_min"], n_run)
            and guards["all.top4_log_loss"]["mean"] <= t["guard_top4_log_loss_max"]
            and guards["all.race_winner_capture_rate"]["mean"]
                >= t["guard_winner_capture_min"]
            and od_ok)

    print("\n" + "=" * 88, flush=True)
    for arm in arms_eval:
        r = agg[arm]["residual"]
        print(f"{arm}: RESIDUAL (n={r['n_comps']})  "
              f"winner_rank {r['winner_model_rank']['pooled_delta']:+.3f}  "
              f"cosine {r['board_front_cosine']['pooled_delta']:+.4f} "
              f"({r['board_front_cosine']['folds_nonneg']}/{len(fold_results)})  "
              f"pool15 {r['winner_in_pool15']['pooled_delta']:+.4f}  "
              f"front_recall {r['front_recall15']['pooled_delta']:+.4f}  "
              f"PASS={agg[arm]['PASS']}", flush=True)
        print(f"   guardrails: "
              f"{json.dumps({k: round(v['mean'], 5) for k, v in agg[arm]['guardrails'].items()})}",
              flush=True)

    ended = datetime.now()
    ts = ended.strftime("%Y%m%d_%H%M%S")
    tag = "smoke_" if args.smoke else ""
    rec_path = OUT_DIR / f"day_menu_gate3_records_{tag}{ts}.csv.gz"
    rec_df.to_csv(rec_path, index=False, compression="gzip")
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": folds, "start_date": START_DATE, "k_menu": K_MENU,
                   "gamma": GAMMA, "half_life_days": HALF_LIFE_DAYS,
                   "min_eff_n": MIN_EFF_N, "thresholds": THRESHOLDS,
                   "smoke": args.smoke},
        "fold_results": fold_results,
        "aggregated": agg,
        "records_csv": rec_path.name,
    }
    path = OUT_DIR / f"day_menu_gate3_cv_{tag}{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
