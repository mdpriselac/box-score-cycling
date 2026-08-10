"""
Day-type menu ORACLE gate — step 2 of day_type_menu_plan.md (5-fold CV).

Tests whether filling the 11 stage-NULL contest-signature columns with
menu-item canonical values (hard own-assignment labels, borrowed canonical
values) improves CONTENDER SURFACING on the residual day class — the
program-scoped primary metric set (2026-07-11 gate amendment), with the
global metrics as no-degradation guardrails. This is the oracle-ceiling /
kill-switch test: labels at test time come from the day's own realized
front (accepted bounded leak, June quantification 49%/0.876); a shippable
form must later pass the serve-keyed + full-stack integration gates.

Day-class labeler (updated per 2026-08-08 session decisions):
  itt      winning_time < 4500 s (75 min covers ITT/TTT/prologue)
  bunch    mass_sprint, or bunch_sprint with wg_prop >= 0.20
  gc_day   winner OR front-5 median as-of-MORNING GC rank <= 10
           (rider_race_state.gc_rank_current; final-GC fallback where absent)
  residual everything else (includes low-wg_prop survivor gallops = res_wide)

Arms (per fold; one-day B4 features attached identically in all arms):
  base    stages NaN in all 11 sig cols (production semantics today)
  menu6   stage fill from k=6 GMM menu (residual) + bunch/gc/itt macro items
  menu8   same with k=8

Fold discipline: GMM + canonical values fit on train-period members only;
assignment of any-period comps is hard own-assignment (the oracle label).

PRE-REGISTERED DECISION RULE (residual slice, arm - base, paired by fold):
  PASS iff BOTH, on either menu arm, with guardrails intact:
    1. winner_in_pool15  pooled delta >= +0.020 and >= 4/5 folds >= 0
    2. board_front_cosine pooled delta >= +0.010 and >= 4/5 folds >= 0
  Guardrails: all-subset top4_log_loss delta <= +0.010,
              all-subset winner capture delta >= -0.005,
              one_day subset winner capture |delta| <= 0.005 (implementation
              sanity: od features are identical across arms).
  Diagnostics (reported, not gated): front_recall15, winner_model_rank.

ITERATION 2 (2026-08-08, same session): run 1 (arms menu6/menu8 filling the
SHARED sig_* columns) showed systematic one-day damage — od winner capture
-1.1pp/-1.0pp with od log loss worse in 5/5 / 4/5 folds — stage fills on the
shared columns cannibalize the one-day B4 signal (distribution collision).
Fix: stage fills move to a separate dtm_* namespace (dtm_sig_<arch> x6,
dtm_sig_wg_prop, dtm_rider_sig_share, dtm_rider_contest_fit,
dtm_rider_sig_vs_field); one-day rows keep sig_* exactly as production and
get dtm_* NaN. Thresholds unchanged from pre-registration.

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.day_menu_gate_cv [--smoke]
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

import cycling_project.prediction_tools.experiments.stacked_meta_learner_cv_5fold as H
from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    attach,
    load_signature_table,
    oneday_b4,
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
DB_PATH = (Path(__file__).parent.parent.parent
           / "webscrape_tools" / "database" / "database" / "cycling_races.db")
SEED = 42
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
ARCH7 = ARCH + ["unknown"]
SH15 = [f"top15_{a}" for a in ARCH]
SH15_7 = [f"top15_{a}" for a in ARCH7]
SIG = [f"sig_{a}" for a in ARCH]

GC_TOP = 10
ITT_SECONDS = 4500.0
WIDE_BS_PROP = 0.20
UNKNOWN_JUNK = 0.20   # rows with top15_unknown above this are excluded from GMM FIT
K_ARMS = {"menu6sep": 6, "menu8sep": 8}
POOL_N = 15
DTM_SIG = [f"dtm_sig_{a}" for a in ARCH]

THRESHOLDS = {
    "winner_in_pool15_delta": 0.020,
    "board_front_cosine_delta": 0.010,
    "fold_consistency_min": 4,
    "guard_top4_log_loss_max": 0.010,
    "guard_winner_capture_min": -0.005,
    "guard_oneday_winner_abs": 0.005,
}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def build_labels(sig: pd.DataFrame) -> pd.DataFrame:
    """Per stage comp: day_class + realized shares/shape (oracle labels)."""
    st = sig[sig["competition_type"] == "stage"].copy()
    con = sqlite3.connect(DB_PATH)
    comps = pd.read_sql(
        "SELECT id, race_id, competition_type, winning_time FROM competitions", con)
    gc_comps = comps[comps.competition_type == "gc"][["id", "race_id"]]
    need = set(st.comp_id) | set(gc_comps.id)
    con.execute("CREATE TEMP TABLE need(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO need VALUES (?)", [(int(i),) for i in need])
    rr = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN need n ON n.id = r.competition_id""", con)
    state = pd.read_sql(
        "SELECT competition_id, rider_id, gc_rank_current FROM rider_race_state", con)
    con.close()
    rr["place_n"] = pd.to_numeric(rr.place, errors="coerce")

    st = st.merge(comps[["id", "race_id", "winning_time"]],
                  left_on="comp_id", right_on="id", how="left").drop(columns=["id"])

    # final-GC lookup (fallback)
    gcr = rr.merge(gc_comps.rename(columns={"id": "gc_comp_id"}),
                   left_on="competition_id", right_on="gc_comp_id")
    final_gc = gcr.set_index(["race_id", "rider_id"]).place_n
    morning = state.set_index(["competition_id", "rider_id"]).gc_rank_current

    srr = rr[rr.competition_id.isin(set(st.comp_id))]
    winners = srr[srr.place_n == 1].groupby("competition_id").rider_id.first()
    top5 = srr[srr.place_n <= 5]

    def look(index_obj, key):
        try:
            return index_obj.loc[key]
        except KeyError:
            return np.nan

    st["winner_rider_id"] = st.comp_id.map(winners)
    w_morning, w_final, f5 = [], [], []
    top5_by_comp = {c: g.rider_id.tolist() for c, g in top5.groupby("competition_id")}
    for comp, race, w in zip(st.comp_id, st.race_id, st.winner_rider_id):
        w_morning.append(look(morning, (comp, w)) if pd.notna(w) else np.nan)
        w_final.append(look(final_gc, (race, w)) if pd.notna(w) else np.nan)
        ranks = [look(morning, (comp, r)) for r in top5_by_comp.get(comp, [])]
        ranks = [r for r in ranks if pd.notna(r)]
        if not ranks:  # fallback to final GC for the front
            ranks = [look(final_gc, (race, r)) for r in top5_by_comp.get(comp, [])]
            ranks = [r for r in ranks if pd.notna(r)]
        f5.append(np.median(ranks) if ranks else np.nan)
    st["winner_gc_m"] = w_morning
    st["winner_gc_f"] = w_final
    st["front5_gc_m"] = f5
    st["gc_eff"] = st.winner_gc_m.fillna(st.winner_gc_f)

    st["is_itt"] = st.winning_time < ITT_SECONDS
    st["is_bunch"] = (st.rule_type == "mass_sprint") | (
        (st.rule_type == "bunch_sprint") & (st.wg_prop >= WIDE_BS_PROP))
    st["is_gc_day"] = (st.gc_eff <= GC_TOP) | (st.front5_gc_m <= GC_TOP)
    st["day_class"] = np.select(
        [st.is_itt, st.is_bunch, st.is_gc_day],
        ["itt", "bunch", "gc_day"], default="residual")
    logger.info("labels: %s", st.day_class.value_counts().to_dict())
    return st


# ---------------------------------------------------------------------------
# Menu features per fold
# ---------------------------------------------------------------------------

def stage_menu_feats(labels: pd.DataFrame, train_end: str, k: int) -> pd.DataFrame:
    """comp_feats rows (sig_* fills) for ALL labeled stage comps, fold-honest."""
    lab = labels.copy()
    lab["date"] = pd.to_datetime(lab["date"])
    train = lab[lab.date <= pd.to_datetime(train_end)]

    res_tr = train[(train.day_class == "residual")
                   & (train.top15_unknown <= UNKNOWN_JUNK)]
    gm = GaussianMixture(k, covariance_type="full", n_init=5,
                         random_state=SEED, reg_covar=1e-5)
    gm.fit(res_tr[SH15].values)

    res_all = lab[lab.day_class == "residual"]
    assign = pd.Series(gm.predict(res_all[SH15].values), index=res_all.index)
    lab["item"] = lab.day_class.where(lab.day_class != "residual", other=np.nan)
    lab.loc[res_all.index, "item"] = "res_" + assign.astype(str)

    train_items = lab.loc[train.index]
    canon = train_items.groupby("item").agg(
        **{f"sig_{a}": (f"top15_{a}", "mean") for a in ARCH},
        sig_wg_prop=("wg_prop", "mean"), n_members=("comp_id", "size"))
    logger.info("menu k=%d items: %s", k,
                {i: int(n) for i, n in canon.n_members.items()})

    out = lab[["comp_id", "item"]].merge(
        canon.reset_index(), on="item", how="left")
    out["sig_n_refs"] = np.nan
    keep = ["comp_id"] + SIG + ["sig_wg_prop", "sig_n_refs"]
    feats = out[keep].dropna(subset=SIG)
    item_map = lab.set_index("comp_id")["item"]
    return feats, item_map, canon


def attach_menu(df: pd.DataFrame, feats: pd.DataFrame,
                field_shares: pd.DataFrame) -> pd.DataFrame:
    """Attach stage menu fills in the separate dtm_* namespace.

    df is an already od-attached frame (sig_* = production one-day B4,
    stages NaN). Stage comps present in feats get dtm_sig_* + dtm rider
    interactions; everything else NaN in every dtm column.
    """
    f = feats.rename(columns={f"sig_{a}": f"dtm_sig_{a}" for a in ARCH}
                     | {"sig_wg_prop": "dtm_sig_wg_prop"})
    f = f.drop(columns=["sig_n_refs"], errors="ignore")
    out = df.merge(f, left_on="competition_id", right_on="comp_id", how="left")
    out = out.merge(field_shares, left_on="competition_id", right_on="comp_id",
                    how="left", suffixes=("", "_fs"))
    out.drop(columns=[c for c in ("comp_id", "comp_id_fs") if c in out], inplace=True)

    bp = out["best_profile"].map({a: i for i, a in enumerate(ARCH)})
    has_bp = bp.notna().to_numpy()
    bp_idx = bp.fillna(0).astype(int).to_numpy()
    sig_mat = out[DTM_SIG].to_numpy(dtype=float)
    fs_mat = out[[f"field_share_{a}" for a in ARCH]].to_numpy(dtype=float)
    rows = np.arange(len(out))
    out["dtm_rider_sig_share"] = np.where(has_bp, sig_mat[rows, bp_idx], np.nan)
    out["dtm_rider_sig_vs_field"] = np.where(
        has_bp, sig_mat[rows, bp_idx] - fs_mat[rows, bp_idx], np.nan)
    ability = np.column_stack(
        [(4.0 - out[f"{a}_avg_bucket"].to_numpy(dtype=float)) for a in ARCH])
    out["dtm_rider_contest_fit"] = np.einsum(
        "ij,ij->i", np.nan_to_num(sig_mat), ability)
    out.loc[np.isnan(sig_mat).all(axis=1), "dtm_rider_contest_fit"] = np.nan
    out.drop(columns=[f"field_share_{a}" for a in ARCH], inplace=True)
    return out


# ---------------------------------------------------------------------------
# Surfacing metrics
# ---------------------------------------------------------------------------

def surfacing_records(test_df: pd.DataFrame, bucket_pred, labels: pd.DataFrame,
                      place_map: pd.Series, arm: str, fold_label: str,
                      item_map: Optional[pd.Series]) -> List[Dict[str, Any]]:
    """Per labeled stage comp in test: pool membership + composition metrics."""
    lab = labels.set_index("comp_id")
    df = test_df[test_df.competition_id.isin(lab.index)].copy()
    if df.empty:
        return []
    df["expected"] = bucket_pred.predict_continuous(df)
    df["rank"] = df.groupby("competition_id")["expected"].rank(method="first")
    key = pd.MultiIndex.from_arrays([df.competition_id, df.rider_id])
    df["place_n"] = place_map.reindex(key).to_numpy()
    df["bp"] = df["best_profile"].fillna("unknown")

    recs = []
    for comp, g in df.groupby("competition_id"):
        row = lab.loc[comp]
        pool = g[g["rank"] <= POOL_N]
        winner = g[g.place_n == 1]
        if winner.empty:
            continue
        wg = int(row.wg_size)
        front = g[g.place_n <= min(wg, POOL_N)]
        board = np.array([(pool.bp == a).mean() for a in ARCH7])
        real = row[SH15_7].to_numpy(dtype=float)
        denom = (np.linalg.norm(board) * np.linalg.norm(real))
        cosine = float(board @ real / denom) if denom > 0 else np.nan
        recs.append({
            "fold": fold_label, "arm": arm, "comp_id": int(comp),
            "day_class": row.day_class,
            "item": None if item_map is None else item_map.get(comp),
            "n_rows": int(len(g)),
            "winner_model_rank": float(winner["rank"].iloc[0]),
            "winner_in_pool15": bool(winner["rank"].iloc[0] <= POOL_N),
            "front_n": int(len(front)),
            "front_recall15": float(len(front[front["rank"] <= POOL_N]) / len(front))
            if len(front) else np.nan,
            "board_front_cosine": cosine,
        })
    return recs


def slice_deltas(records: pd.DataFrame, arm: str,
                 day_class: str = "residual") -> Dict[str, Any]:
    """Paired per-fold deltas (arm - base) on one day-class slice."""
    out: Dict[str, Any] = {}
    base = records[(records.arm == "base") & (records.day_class == day_class)]
    test = records[(records.arm == arm) & (records.day_class == day_class)]
    merged = base.merge(test, on=["fold", "comp_id"], suffixes=("_b", "_t"))
    out["n_comps"] = int(merged.comp_id.nunique())
    for m in ["winner_in_pool15", "front_recall15", "board_front_cosine",
              "winner_model_rank"]:
        per_fold = (merged.groupby("fold")
                    .apply(lambda g: g[f"{m}_t"].mean() - g[f"{m}_b"].mean(),
                           include_groups=False))
        pooled = float(merged[f"{m}_t"].mean() - merged[f"{m}_b"].mean())
        out[m] = {"pooled_delta": pooled,
                  "per_fold": {k: float(v) for k, v in per_fold.items()},
                  "folds_nonneg": int((per_fold >= 0).sum())}
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="1 fold, tiny estimators — plumbing check only")
    args = ap.parse_args()

    started = datetime.now()
    folds = FOLDS
    if args.smoke:
        folds = FOLDS[-1:]
        H.CONTENDER_CONFIG["n_estimators"] = 60
        H.CONTENDER_CONFIG["early_stopping"] = 10
        print("[SMOKE MODE] 1 fold, 60 trees", flush=True)

    print("=" * 70, flush=True)
    print("DAY-TYPE MENU ORACLE GATE — base vs menu6 vs menu8", flush=True)
    print("=" * 70, flush=True)

    sig = load_signature_table()
    field_shares = sig[["comp_id"] + [f"field_share_{a}" for a in ARCH]].copy()
    od_feats = oneday_b4(sig)
    labels = build_labels(sig)

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
    assert "rider_id" in df.columns, "training frame lacks rider_id"
    print(f"Loaded {len(df):,} rows, {df['competition_id'].nunique():,} comps", flush=True)

    all_records: List[Dict[str, Any]] = []
    fold_results: List[Dict[str, Any]] = []
    for i, fold in enumerate(folds):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(folds)} (test={fold['label']}+)\n{'─'*60}",
              flush=True)
        train, val, test = _slice_fold(df, fold)
        if len(test) == 0:
            continue

        item_maps: Dict[str, Optional[pd.Series]] = {"base": None}
        menu_feats: Dict[str, pd.DataFrame] = {}
        for arm, k in K_ARMS.items():
            feats, item_map, _canon = stage_menu_feats(labels, fold["train_end"], k)
            menu_feats[arm] = feats
            item_maps[arm] = item_map

        # od-attached base frames (identical across arms; sig_* = production)
        base_tr = attach(train, od_feats, field_shares)
        base_va = attach(val, od_feats, field_shares)
        base_te = attach(test, od_feats, field_shares)

        fr: Dict[str, Any] = {"fold_label": fold["label"]}
        for arm in ["base"] + list(K_ARMS):
            print(f"  Training {arm.upper()}...", flush=True)
            if arm == "base":
                tr, va, te = base_tr, base_va, base_te
            else:
                tr = attach_menu(base_tr, menu_feats[arm], field_shares)
                va = attach_menu(base_va, menu_feats[arm], field_shares)
                te = attach_menu(base_te, menu_feats[arm], field_shares)
            bucket, cont, _ = _train_bucket_and_contender(tr, va, fold["label"])
            subsets = {"all": te,
                       "one_day": te[te.competition_type == "one_day"],
                       "stage": te[te.competition_type == "stage"]}
            fr[arm] = {name: dict(zip(("metrics", "n"),
                                      _evaluate_on_test(sub, bucket, cont, top_n=POOL_N)))
                       for name, sub in subsets.items() if len(sub)}
            recs = surfacing_records(te, bucket, labels, place_map,
                                     arm, fold["label"], item_maps[arm])
            all_records.extend(recs)
            if arm != "base":
                fr[f"{arm}_sig_importance"] = {
                    c: float(v) for c, v in _capture_feature_importance(cont).items()
                    if c.startswith(("sig_", "rider_sig", "rider_contest", "dtm_"))}
            w = fr[arm]["all"]["metrics"].get("race_winner_capture_rate", np.nan)
            n_res = sum(1 for r in recs if r["day_class"] == "residual")
            print(f"    {arm}: winner_capture={w:.4f}  residual test comps={n_res}",
                  flush=True)
        fold_results.append(fr)

    rec_df = pd.DataFrame(all_records)
    agg: Dict[str, Any] = {}
    for arm in K_ARMS:
        agg[arm] = {"residual": slice_deltas(rec_df, arm, "residual"),
                    "gc_day": slice_deltas(rec_df, arm, "gc_day"),
                    "bunch": slice_deltas(rec_df, arm, "bunch")}
        # guardrails from global metrics
        guards = {}
        for metric, subset in [("top4_log_loss", "all"),
                               ("race_winner_capture_rate", "all"),
                               ("race_winner_capture_rate", "one_day")]:
            ds = [fr[arm][subset]["metrics"][metric] - fr["base"][subset]["metrics"][metric]
                  for fr in fold_results
                  if subset in fr.get(arm, {}) and subset in fr.get("base", {})]
            guards[f"{subset}.{metric}"] = {
                "mean": float(np.mean(ds)), "per_fold": [float(d) for d in ds]}
        agg[arm]["guardrails"] = guards
        r = agg[arm]["residual"]
        t = THRESHOLDS
        n_folds_run = len(fold_results)
        consistency = min(t["fold_consistency_min"], n_folds_run)
        agg[arm]["PASS"] = bool(
            r["winner_in_pool15"]["pooled_delta"] >= t["winner_in_pool15_delta"]
            and r["winner_in_pool15"]["folds_nonneg"] >= consistency
            and r["board_front_cosine"]["pooled_delta"] >= t["board_front_cosine_delta"]
            and r["board_front_cosine"]["folds_nonneg"] >= consistency
            and guards["all.top4_log_loss"]["mean"] <= t["guard_top4_log_loss_max"]
            and guards["all.race_winner_capture_rate"]["mean"] >= t["guard_winner_capture_min"]
            and abs(guards["one_day.race_winner_capture_rate"]["mean"]) <= t["guard_oneday_winner_abs"])

    print("\n" + "=" * 88, flush=True)
    for arm in K_ARMS:
        r = agg[arm]["residual"]
        print(f"{arm}: RESIDUAL slice (n={r['n_comps']})  "
              f"winner_in_pool15 {r['winner_in_pool15']['pooled_delta']:+.4f} "
              f"({r['winner_in_pool15']['folds_nonneg']}/{len(fold_results)} folds>=0)  "
              f"cosine {r['board_front_cosine']['pooled_delta']:+.4f} "
              f"({r['board_front_cosine']['folds_nonneg']}/{len(fold_results)})  "
              f"front_recall {r['front_recall15']['pooled_delta']:+.4f}  "
              f"winner_rank {r['winner_model_rank']['pooled_delta']:+.2f}  "
              f"PASS={agg[arm]['PASS']}", flush=True)
        print(f"   guardrails: {json.dumps({k: round(v['mean'],5) for k, v in agg[arm]['guardrails'].items()})}",
              flush=True)

    ended = datetime.now()
    ts = ended.strftime("%Y%m%d_%H%M%S")
    tag = "smoke_" if args.smoke else ""
    rec_path = OUT_DIR / f"day_menu_gate_records_{tag}{ts}.csv.gz"
    rec_df.to_csv(rec_path, index=False, compression="gzip")
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": folds, "start_date": START_DATE, "k_arms": K_ARMS,
                   "thresholds": THRESHOLDS, "gc_top": GC_TOP,
                   "itt_seconds": ITT_SECONDS, "wide_bs_prop": WIDE_BS_PROP,
                   "smoke": args.smoke},
        "label_counts": labels.day_class.value_counts().to_dict(),
        "fold_results": fold_results,
        "aggregated": agg,
        "records_csv": rec_path.name,
    }
    path = OUT_DIR / f"day_menu_gate_cv_{tag}{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)", flush=True)


if __name__ == "__main__":
    main()
