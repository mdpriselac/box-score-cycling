"""
Day-menu step-4 gate — FULL-STACK integration + serve-side day keys.

The pre-ship decision experiment for the step-3 kernel family (menu8kernod,
passed 2026-08-08 on the light harness). Two questions, one run:

  1. INTEGRATION (v5 lesson): do the day-menu features survive on top of the
     SHIPPED arm-C stack (meta-OOF + one-day B4 sigs + contested Elo), under
     the honest DNF-adjusted market frame — market_avg_log_loss primary per
     the 2026-08-08 gate-policy addendum (NOT winner capture)?
  2. SERVE SIDE (plan step 4): stage day-keys were oracle-only. Here a
     MECHANICAL selector (pre-race observables -> menu item) prices the
     serving gap, and the designed serve mode — run the board per plausible
     item, MIX OUTPUT BOARDS under the selector prior (never feature
     averages) — is evaluated end to end.

Arms (per fold; K-model trained ONCE, oracle keys at train/val — that is the
design: training always conditions on the realized day; only TEST-time key
sourcing varies):
  A      shipped arm-C stack (production baseline).
  korc   A + menu8kernod features, test keys = ORACLE own-assignment
         (ceiling; matches the step-3 passing config).
  kmech  same model, test keys = selector argmax (deployable, hard key).
  kmix   same model, test boards = mixture over the selector's top-5 items
         (calibrated probs, renormalized) — the deployable designed mode.

Mechanical selector: LightGBM multiclass over menu items on LABELED stage
comps, train-period only, val period for early stopping + a scalar
temperature (p^(1/T) renormalized, T by val NLL). Features are strictly
pre-race: 6 race profile scores, startlist archetype counts + field strength
aggregates (bucket_*/experience_*), per-event historical shape descriptors
(*_slope/*_volatility/percentile stats), field_share_* (B4 composition),
stage_number / n_stages / stage_frac / month / category / is_stage_race.
EXCLUDED as realized outcomes: winning_time, abandon_ratio.
REGISTERED ASSUMPTION: ITT format is exogenous-known at serve (race format
is public before the stage; the DB merely lacks the field) — itt comps get
the itt key with prob 1 in all mechanical arms; the selector classifies the
genuinely-uncertain remainder (bunch / gc_day / res_*). One-day kernel keys
are already mechanical (nearest canonical to own as-of-then B4 signature).

PRE-REGISTERED DECISION RULE (registered before the run; deployable arm
kmix vs A, paired by fold):
  G1 probability (primary): honest_adjusted market_avg_log_loss, all subset,
     pooled mean <= +0.0010 AND >= 3/5 folds <= 0; one_day subset pooled
     mean <= +0.0015 (od watch-item adjudication — od kernels differ from
     base BY DESIGN, so the bar is no-material-degradation).
  G2 surfacing (residual slice): winner_model_rank pooled delta <= -1.00
     with >= 4/5 folds < 0 AND board_front_cosine pooled delta >= +0.010
     with >= 4/5 folds >= 0 (step-3 bars, now demanded of the deployable
     serve mode on the full stack).
  Guardrails: all-subset winner capture delta >= -0.005; one_day winner
     capture delta >= -0.005 (one-sided).
  korc is the reported ceiling (korc - kmix = the selector bounty), kmech
  the hard-key reference; neither is gated. pool recall curves, entry/exit
  and per-item effects come from the persisted per-race records.

Outputs: experiments/day_menu_gate4_cv_<ts>.json + per-race records
experiments/day_menu_gate4_records_<ts>.csv.gz (pool ids to rank 25, front
ranks, board/realized composition, selector diagnostics per comp).

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.day_menu_gate4_cv [--smoke]
"""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

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
from cycling_project.prediction_tools.experiments.day_menu_gate_cv import (
    DB_PATH,
    POOL_N,
    attach_menu,
    build_labels,
    stage_menu_feats,
)
from cycling_project.prediction_tools.experiments.day_menu_gate3_cv import (
    GAMMA,
    HALF_LIFE_DAYS,
    K_MENU,
    KERNEL_COLS,
    MIN_EFF_N,
    attach_kernels,
    build_rider_history,
    extend_item_map_oneday,
    kernel_cumulants,
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
SEED = 42
ARCH7 = ARCH + ["unknown"]
SH15_7 = [f"top15_{a}" for a in ARCH7]
EVAL_SUBSETS = ("all", "one_day", "stage")
ARMS = ("A", "korc", "kmech", "kmix")
ARM_DESC = {
    "A": "shipped arm-C stack",
    "korc": "stack + menu8kernod, oracle test keys (ceiling)",
    "kmech": "stack + menu8kernod, selector argmax test keys",
    "kmix": "stack + menu8kernod, top-5 board mixture under selector prior",
}
MIX_TOP = 5
TEMP_BOUNDS = (0.25, 4.0)
RECORD_POOL_N = 25
SELECTOR_EXCLUDE = {"winning_time", "abandon_ratio"}  # realized outcomes

THRESHOLDS = {
    "g1_all_honest_mkt_ll_max": 0.0010,
    "g1_all_folds_nonpos_min": 3,
    "g1_oneday_honest_mkt_ll_max": 0.0015,
    "g2_winner_rank_delta_max": -1.00,
    "g2_winner_rank_folds_neg_min": 4,
    "g2_cosine_delta_min": 0.010,
    "g2_cosine_folds_nonneg_min": 4,
    "guard_all_winner_capture_min": -0.005,
    "guard_oneday_winner_capture_min": -0.005,
}

DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "podium_log_loss",
    "top5_log_loss", "top15_log_loss", "market_avg_brier",
    "win_cal_ratio", "podium_cal_ratio",
    "race_winner_capture_rate", "race_podium_capture_rate",
]
HONEST_DELTA_METRICS = [
    "market_avg_log_loss", "win_log_loss", "top15_log_loss", "win_cal_ratio",
]


# ---------------------------------------------------------------------------
# Mechanical selector
# ---------------------------------------------------------------------------

def build_selector_features(df: pd.DataFrame, sig: pd.DataFrame) -> pd.DataFrame:
    """Per-comp pre-race feature table (fold-independent).

    Comp-constant numeric columns of the production frame (detected on a
    fixed sample), minus realized outcomes, plus field shares and DB
    calendar/stage context.
    """
    st = df[df["competition_type"] == "stage"]
    samp = st["competition_id"].drop_duplicates().sample(
        min(500, st["competition_id"].nunique()), random_state=0)
    s = st[st["competition_id"].isin(samp)]
    num = s.select_dtypes(include=[np.number]).columns
    nun = s.groupby("competition_id")[list(num)].nunique(dropna=True).max()
    const_cols = sorted(
        c for c in num
        if nun[c] <= 1 and c != "competition_id" and c not in SELECTOR_EXCLUDE)
    comp_feats = (df.groupby("competition_id")[const_cols].first()
                  .rename_axis("comp_id"))

    fs = sig.set_index("comp_id")[[f"field_share_{a}" for a in ARCH]]
    comp_feats = comp_feats.join(fs, how="outer")

    con = sqlite3.connect(DB_PATH)
    meta = pd.read_sql(
        """SELECT c.id AS comp_id, c.race_id, c.stage_number, c.date, c.name,
                  r.category, r.is_stage_race
           FROM competitions c JOIN races r ON r.id = c.race_id
           WHERE c.competition_type = 'stage'""", con)
    con.close()
    meta["date"] = pd.to_datetime(meta["date"])
    meta["month"] = meta["date"].dt.month
    meta["is_prologue"] = meta["name"].str.contains("rologue", na=False).astype(int)
    n_st = meta.groupby("race_id")["comp_id"].transform("count")
    meta["n_stages"] = n_st
    meta["stage_frac"] = meta["stage_number"] / n_st.clip(lower=1)
    meta["is_gt"] = (n_st >= 15).astype(int)
    cat_codes = {c: i for i, c in enumerate(sorted(meta["category"].dropna().unique()))}
    meta["category_code"] = meta["category"].map(cat_codes)
    keep = ["comp_id", "stage_number", "month", "is_prologue", "n_stages",
            "stage_frac", "is_gt", "category_code", "is_stage_race"]
    comp_feats = comp_feats.join(meta.set_index("comp_id")[keep[1:]], how="left")
    logger.info("selector features: %d comps x %d cols",
                len(comp_feats), comp_feats.shape[1])
    return comp_feats


def _apply_temperature(p: np.ndarray, T: float) -> np.ndarray:
    q = np.clip(p, 1e-12, 1.0) ** (1.0 / T)
    return q / q.sum(axis=1, keepdims=True)


def fit_selector(comp_feats: pd.DataFrame, labels: pd.DataFrame,
                 item_map: pd.Series, train_end: str, val_end: str,
                 smoke: bool = False) -> Dict[str, Any]:
    """Train the day-key classifier on non-itt labeled comps, train period."""
    lab = labels[["comp_id", "day_class"]].copy()
    lab["date"] = pd.to_datetime(labels["date"])
    lab["item"] = lab.comp_id.map(item_map)
    lab = lab[(lab.day_class != "itt") & lab.item.notna()]
    X_all = comp_feats.reindex(lab.comp_id)
    classes = sorted(lab.item.unique())
    cls_idx = {c: i for i, c in enumerate(classes)}
    y_all = lab.item.map(cls_idx).to_numpy()

    tr = (lab.date <= pd.to_datetime(train_end)).to_numpy()
    vl = ((lab.date > pd.to_datetime(train_end))
          & (lab.date <= pd.to_datetime(val_end))).to_numpy()
    te = (lab.date > pd.to_datetime(val_end)).to_numpy()

    clf = lgb.LGBMClassifier(
        objective="multiclass",
        n_estimators=60 if smoke else 500, learning_rate=0.05,
        num_leaves=63, min_child_samples=15, random_state=SEED, verbose=-1)
    clf.fit(X_all[tr], y_all[tr],
            eval_set=[(X_all[vl], y_all[vl])],
            callbacks=[lgb.early_stopping(50, verbose=False)])

    p_val = clf.predict_proba(X_all[vl])
    yv = y_all[vl]

    def nll(T: float) -> float:
        q = np.clip(_apply_temperature(p_val, T), 1e-12, 1.0)
        return float(-np.mean(np.log(q[np.arange(len(yv)), yv])))

    T = float(minimize_scalar(nll, bounds=TEMP_BOUNDS, method="bounded").x)

    p_te = _apply_temperature(clf.predict_proba(X_all[te]), T)
    yt = y_all[te]
    top1 = float((p_te.argmax(1) == yt).mean()) if len(yt) else np.nan
    top2 = float(np.mean([yt[i] in p_te[i].argsort()[-2:] for i in range(len(yt))])) if len(yt) else np.nan
    conf = {}
    per_class = {}
    for c, i in cls_idx.items():
        m = yt == i
        if m.sum():
            per_class[c] = {"n": int(m.sum()),
                            "recall": float((p_te[m].argmax(1) == i).mean())}
        pred_c = pd.Series(p_te.argmax(1)[m]).map(
            {v: k for k, v in cls_idx.items()}).value_counts().to_dict()
        if pred_c:
            conf[c] = {k: int(v) for k, v in pred_c.items()}

    # calibrated probs for ALL labeled non-itt comps (test-period keys)
    p_full = _apply_temperature(clf.predict_proba(X_all), T)
    probs = pd.DataFrame(p_full, index=lab.comp_id.values, columns=classes)
    return {"classes": classes, "T": T, "probs": probs,
        "diag": {"n_train": int(tr.sum()), "n_val": int(vl.sum()),
                 "n_test": int(te.sum()), "temperature": T,
                 "best_iteration": int(clf.best_iteration_ or 0),
                 "test_top1": top1, "test_top2": top2,
                 "per_class_test": per_class, "confusion_test": conf}}


def selector_maps(sel: Dict[str, Any], labels: pd.DataFrame,
                  oracle_ext: pd.Series) -> Tuple[pd.Series, pd.DataFrame]:
    """(hard mechanical map incl. exogenous itt + od keys, weight matrix)."""
    itt = labels.loc[labels.day_class == "itt", "comp_id"]
    hard = pd.Series("itt", index=itt.values)
    probs = sel["probs"]
    hard = pd.concat([hard, pd.Series(probs.idxmax(1), index=probs.index)])
    od_keys = oracle_ext[~oracle_ext.index.isin(set(labels.comp_id))]
    hard = pd.concat([hard, od_keys])
    return hard[~hard.index.duplicated()], probs


# ---------------------------------------------------------------------------
# Keyed attachment (menu fills + kernels under an arbitrary comp->item map)
# ---------------------------------------------------------------------------

def feats_from_map(key_map: pd.Series, canon: pd.DataFrame,
                   stage_comps: set) -> pd.DataFrame:
    """attach_menu-shaped fill table for LABELED STAGE comps under key_map."""
    km = key_map[key_map.index.isin(stage_comps)]
    out = pd.DataFrame({"comp_id": km.index, "item": km.values})
    out = out.merge(canon.reset_index(), on="item", how="left")
    out["sig_n_refs"] = np.nan
    keep = ["comp_id"] + [f"sig_{a}" for a in ARCH] + ["sig_wg_prop", "sig_n_refs"]
    return out[keep].dropna(subset=[f"sig_{a}" for a in ARCH])


def key_attach(base_frame: pd.DataFrame, key_map: pd.Series,
               canon: pd.DataFrame, cum: pd.DataFrame, items: List[str],
               field_shares: pd.DataFrame, stage_comps: set) -> pd.DataFrame:
    f = attach_menu(base_frame,
                    feats_from_map(key_map, canon, stage_comps), field_shares)
    return attach_kernels(f, cum, items, key_map)


# ---------------------------------------------------------------------------
# Board mixing
# ---------------------------------------------------------------------------

def mixed_predictions(base_frame: pd.DataFrame, bucket, cont,
                      fixed_map: pd.Series, weights: pd.DataFrame,
                      canon: pd.DataFrame, cum: pd.DataFrame,
                      items: List[str], field_shares: pd.DataFrame,
                      stage_comps: set) -> Tuple[np.ndarray, np.ndarray]:
    """Mixture of per-item boards: expected bucket + contender proba.

    weights: comps x items (rows sum to 1; only labeled non-itt stage comps).
    Comps absent from weights keep their fixed key (itt / one-day / none) —
    their per-item predictions are identical, so any convex mix is exact.
    """
    var_comps = weights.index.to_numpy()
    comp_ids = base_frame["competition_id"].to_numpy()
    w_rows = weights.reindex(comp_ids)          # NaN rows = fixed comps
    is_var = w_rows.notna().all(axis=1).to_numpy()

    mixed_exp = np.zeros(len(base_frame))
    mixed_proba: Optional[np.ndarray] = None
    done_fixed = False
    for m in items:
        w_col = (w_rows[m].to_numpy(dtype=float) if m in w_rows.columns
                 else np.zeros(len(w_rows)))
        w_m = np.where(is_var, w_col, 0.0)
        if not done_fixed:
            w_m = w_m + (~is_var).astype(float)   # fixed comps ride item #1
        if w_m.sum() == 0:
            continue
        key_m = fixed_map.copy()
        km = pd.Series(m, index=var_comps)
        key_m = pd.concat([key_m[~key_m.index.isin(var_comps)], km])
        fr_m = key_attach(base_frame, key_m, canon, cum, items,
                          field_shares, stage_comps)
        exp_m = np.asarray(bucket.predict_continuous(fr_m), dtype=float)
        pr_m = cont.predict_proba(fr_m)
        mixed_exp += w_m * exp_m
        if mixed_proba is None:
            mixed_proba = np.zeros_like(pr_m)
        mixed_proba += w_m[:, None] * pr_m
        done_fixed = True
    return mixed_exp, mixed_proba


def mix_weights(probs: pd.DataFrame, top: int = MIX_TOP) -> pd.DataFrame:
    """Top-N truncated, renormalized calibrated selector distribution."""
    arr = probs.to_numpy()
    if probs.shape[1] > top:
        thresh = np.sort(arr, axis=1)[:, -top][:, None]
        arr = np.where(arr >= thresh, arr, 0.0)
    arr = arr / arr.sum(axis=1, keepdims=True)
    return pd.DataFrame(arr, index=probs.index, columns=probs.columns)


# ---------------------------------------------------------------------------
# Eval from arrays (replicates full_stack eval_arm / honest_eval)
# ---------------------------------------------------------------------------

def eval_from_arrays(te: pd.DataFrame, expected: np.ndarray,
                     proba: np.ndarray, n_classes: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    exp_s = pd.Series(expected, index=te.index)
    for name in EVAL_SUBSETS:
        mask = np.ones(len(te), bool) if name == "all" else \
            (te["competition_type"] == name).to_numpy()
        if mask.sum() == 0:
            continue
        sub = te[mask]
        rank = exp_s[mask].groupby(sub["competition_id"]).rank()
        sel = (rank <= TOP_N).to_numpy()
        y = np.clip(sub["place_bucket"].to_numpy()[sel].astype(int),
                    0, n_classes - 1)
        pr = proba[mask][sel]
        m = MarketProbabilityEvaluator.evaluate(y, pr)
        t4 = Top4ProbabilityEvaluator.evaluate(
            y, pr, competition_ids=sub["competition_id"].to_numpy()[sel])
        for k in ("race_winner_capture_rate", "race_podium_capture_rate"):
            if k in t4:
                m[k] = t4[k]
        out[name] = m
    return out


def honest_from_arrays(pool: pd.DataFrame, expected: np.ndarray,
                       proba: np.ndarray, p_map: Dict, n_classes: int) -> Dict[str, Any]:
    d = pool.copy()
    d["classifier_expected_bucket"] = expected
    fin = d["is_dnf_row"] == 0
    d["_rank_fin"] = d[fin].groupby("competition_id")["classifier_expected_bucket"].rank()
    d["_rank_pool"] = d.groupby("competition_id")["classifier_expected_bucket"].rank()
    sel_std = (fin & (d["_rank_fin"] <= TOP_N)).to_numpy()
    sel_hon = (d["_rank_pool"] <= TOP_N).to_numpy()
    need = sel_std | sel_hon

    cd = d[need]
    pr = proba[need]
    y_bucket = np.clip(cd["place_bucket"].to_numpy().astype(int), 0, n_classes - 1)
    is_dnf = cd["is_dnf_row"].to_numpy().astype(bool)
    keys = list(zip(cd["competition_id"].to_numpy(), cd["rider_id"].to_numpy()))
    p_dnf = np.array([p_map.get(k, 0.0) for k in keys])
    p_finish = 1.0 - p_dnf
    raw = proba_to_markets(pr)
    comp_ids = cd["competition_id"].to_numpy()
    in_std = sel_std[need]
    in_hon = sel_hon[need]
    ctype = cd["competition_type"].to_numpy()

    def view(rows: np.ndarray, adjusted: bool) -> Dict[str, float]:
        mp = {m: raw[m][rows] for m in raw}
        if adjusted:
            mp = adjust_markets(mp, p_finish[rows], comp_ids[rows])
        return market_metrics(mp, y_bucket[rows], is_dnf[rows])

    out: Dict[str, Any] = {}
    for subset in HONEST_SUBSETS:
        smask = np.ones(len(cd), bool) if subset == "all" else (ctype == subset)
        rows_s, rows_h = in_std & smask, in_hon & smask
        if rows_s.sum() == 0:
            continue
        out[subset] = {
            "n_rows_standard": int(rows_s.sum()),
            "n_rows_honest": int(rows_h.sum()),
            "n_dnf_rows_in_honest_pool": int((rows_h & is_dnf).sum()),
            "standard": view(rows_s, False),
            "honest_adjusted": view(rows_h, True),
            "honest_unadjusted": view(rows_h, False),
        }
    return out


# ---------------------------------------------------------------------------
# Per-race pool records (the pool-selection instrument)
# ---------------------------------------------------------------------------

def pool_records(te: pd.DataFrame, expected: np.ndarray, labels: pd.DataFrame,
                 place_map: pd.Series, arm: str, fold_label: str,
                 oracle_map: pd.Series,
                 used_map: Optional[pd.Series],
                 sel_probs: Optional[pd.DataFrame]) -> List[Dict[str, Any]]:
    lab = labels.set_index("comp_id")
    df = te[te.competition_id.isin(lab.index)].copy()
    if df.empty:
        return []
    df["expected"] = np.asarray(expected)[te.competition_id.isin(lab.index).to_numpy()]
    df["rank"] = df.groupby("competition_id")["expected"].rank(method="first")
    key = pd.MultiIndex.from_arrays([df.competition_id, df.rider_id])
    df["place_n"] = place_map.reindex(key).to_numpy()
    df["bp"] = df["best_profile"].fillna("unknown")

    recs = []
    for comp, g in df.groupby("competition_id"):
        row = lab.loc[comp]
        winner = g[g.place_n == 1]
        if winner.empty:
            continue
        pool15 = g[g["rank"] <= POOL_N]
        pool25 = g[g["rank"] <= RECORD_POOL_N].sort_values("rank")
        wg = int(row.wg_size)
        front = g[g.place_n <= min(wg, POOL_N)]
        board = np.array([(pool15.bp == a).mean() for a in ARCH7])
        real = row[SH15_7].to_numpy(dtype=float)
        denom = np.linalg.norm(board) * np.linalg.norm(real)
        item_true = oracle_map.get(comp)
        rec = {
            "fold": fold_label, "arm": arm, "comp_id": int(comp),
            "date": str(row.date)[:10], "day_class": row.day_class,
            "item_true": item_true,
            "item_used": None if used_map is None else used_map.get(comp),
            "n_rows": int(len(g)),
            "winner_rider_id": int(winner.rider_id.iloc[0]),
            "winner_model_rank": float(winner["rank"].iloc[0]),
            "winner_in_pool15": bool(winner["rank"].iloc[0] <= POOL_N),
            "front_n": int(len(front)),
            "front_recall15": float((front["rank"] <= POOL_N).mean())
            if len(front) else np.nan,
            "front_ranks": "|".join(str(int(r)) for r in sorted(front["rank"])),
            "pool25_rider_ids": "|".join(str(int(r)) for r in pool25.rider_id),
            "board_front_cosine": float(board @ real / denom) if denom > 0 else np.nan,
        }
        for a, b in zip(ARCH7, board):
            rec[f"board_{a}"] = round(float(b), 4)
        if sel_probs is not None and comp in sel_probs.index:
            p = sel_probs.loc[comp]
            rec["sel_p_top"] = round(float(p.max()), 4)
            rec["sel_p_true"] = round(float(p.get(item_true, np.nan)), 4) \
                if item_true is not None else np.nan
            rec["sel_entropy"] = round(float(-(p * np.log(p.clip(1e-12))).sum()), 4)
        recs.append(rec)
    return recs


def slice_deltas4(records: pd.DataFrame, arm: str, day_class: str) -> Dict[str, Any]:
    base = records[(records.arm == "A") & (records.day_class == day_class)]
    test = records[(records.arm == arm) & (records.day_class == day_class)]
    merged = base.merge(test, on=["fold", "comp_id"], suffixes=("_b", "_t"))
    out: Dict[str, Any] = {"n_comps": int(merged.comp_id.nunique())}
    for m in ["winner_in_pool15", "front_recall15", "board_front_cosine",
              "winner_model_rank"]:
        per_fold = (merged.groupby("fold")
                    .apply(lambda g: g[f"{m}_t"].mean() - g[f"{m}_b"].mean(),
                           include_groups=False))
        out[m] = {"pooled_delta": float(merged[f"{m}_t"].mean() - merged[f"{m}_b"].mean()),
                  "per_fold": {k: float(v) for k, v in per_fold.items()},
                  "folds_nonneg": int((per_fold >= 0).sum()),
                  "folds_neg": int((per_fold < 0).sum())}
    return out


# ---------------------------------------------------------------------------
# Per-fold pipeline
# ---------------------------------------------------------------------------

def run_fold(i: int, fold: Dict[str, str], df: pd.DataFrame,
             df_rated: pd.DataFrame, od_feats: pd.DataFrame,
             field_shares: pd.DataFrame, rating_snaps: pd.DataFrame,
             labels: pd.DataFrame, hist: pd.DataFrame,
             comp_selfeats: pd.DataFrame, place_map: pd.Series,
             dnf_labels: pd.DataFrame, dnf_snaps: pd.DataFrame,
             head_frame: pd.DataFrame, smoke: bool) -> Tuple[Dict[str, Any], List[Dict]]:
    label = fold["label"]
    train, val, test = _slice_fold(df, fold)
    train_r, val_r, test_r = _slice_fold(df_rated, fold)
    if len(test) == 0:
        return {"fold_label": label, "skipped": True}, []
    print(f"  train {len(train):,} | val {len(val):,} | test {len(test):,} rows "
          f"({test['competition_id'].nunique():,} comps)", flush=True)

    # ---- menu + kernels (fold-honest) ----
    feats, item_map, canon = stage_menu_feats(labels, fold["train_end"], K_MENU)
    cum, items = kernel_cumulants(hist, canon)
    oracle_ext = extend_item_map_oneday(item_map, od_feats, canon)
    stage_comps = set(labels.comp_id)

    # ---- selector ----
    sel = fit_selector(comp_selfeats, labels, item_map,
                       fold["train_end"], fold["val_end"], smoke=smoke)
    mech_map, sel_probs = selector_maps(sel, labels, oracle_ext)
    weights = mix_weights(sel_probs)
    print(f"  selector: top1={sel['diag']['test_top1']:.3f} "
          f"top2={sel['diag']['test_top2']:.3f} T={sel['T']:.2f} "
          f"(test n={sel['diag']['n_test']})", flush=True)

    # ---- shipped-stack frames (arm A) ----
    print("  OOF time_gap + LambdaRank (5 sub-folds each)...", flush=True)
    oof_tg = _generate_oof_time_gap(train, val)
    oof_lr = _generate_oof_lambdarank_winp(train, val)
    main_tg = _train_main_time_gap(train, val)
    main_lr = _train_main_lambdarank(train, val)

    def stackify(frame: pd.DataFrame, rated: pd.DataFrame,
                 oof_vals: Optional[Tuple] = None) -> pd.DataFrame:
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

    # ---- arm-K frames (oracle keys at train/val, per design) ----
    kw = dict(canon=canon, cum=cum, items=items,
              field_shares=field_shares, stage_comps=stage_comps)
    train_k = key_attach(train_a, oracle_ext, **kw)
    val_k = key_attach(val_a, oracle_ext, **kw)

    # ---- train the two models ----
    print(f"  Training ARM A — {ARM_DESC['A']}...", flush=True)
    bucket_a, cont_a, _ = _train_bucket_and_contender(train_a, val_a, label)
    print("  Training ARM K (shared by korc/kmech/kmix)...", flush=True)
    bucket_k, cont_k, _ = _train_bucket_and_contender(train_k, val_k, label)
    n_classes = cont_a.config.lgb_params.get("num_class", 8)

    # ---- test-time evaluation, 4 arms ----
    res: Dict[str, Any] = {}
    all_records: List[Dict] = []

    exp_a = np.asarray(bucket_a.predict_continuous(test_a), dtype=float)
    proba_a = cont_a.predict_proba(test_a)
    res["A"] = eval_from_arrays(test_a, exp_a, proba_a, n_classes)
    all_records += pool_records(test_a, exp_a, labels, place_map, "A",
                                label, item_map, None, sel_probs)

    for arm, key_map in (("korc", oracle_ext), ("kmech", mech_map)):
        fr = key_attach(test_a, key_map, **kw)
        e = np.asarray(bucket_k.predict_continuous(fr), dtype=float)
        p = cont_k.predict_proba(fr)
        res[arm] = eval_from_arrays(fr, e, p, n_classes)
        all_records += pool_records(fr, e, labels, place_map, arm, label,
                                    item_map, key_map, sel_probs)

    fixed_map = mech_map[~mech_map.index.isin(set(weights.index))]
    exp_mix, proba_mix = mixed_predictions(
        test_a, bucket_k, cont_k, fixed_map, weights, **kw)
    res["kmix"] = eval_from_arrays(test_a, exp_mix, proba_mix, n_classes)
    all_records += pool_records(test_a, exp_mix, labels, place_map, "kmix",
                                label, item_map, mech_map, sel_probs)
    kern_imp = {}
    try:
        imp = cont_k.get_feature_importance(importance_type="gain")
        kern_imp = {f: float(v) for f, v in
                    zip(imp["feature"], imp["importance"]) if f.startswith("dtm_")}
    except Exception:
        pass

    # ---- DNF head + honest pools ----
    train_end = pd.to_datetime(fold["train_end"])
    val_end = pd.to_datetime(fold["val_end"])
    h_tr = head_frame[head_frame["competition_date"] <= train_end]
    h_vl = head_frame[(head_frame["competition_date"] > train_end)
                      & (head_frame["competition_date"] <= val_end)]
    h_te = head_frame[head_frame["competition_date"] > val_end]
    print(f"  Training DNF head on {len(h_tr):,} starter rows...", flush=True)
    head = DNFPredictor()
    head.train(h_tr, h_vl)
    p_te = head.predict_dnf_proba(h_te)
    head_auc = evaluate_dnf(h_te["dnf"].values, p_te)["auc"]
    p_map = dict(zip(zip(h_te["competition_id"].values,
                         h_te["rider_id"].values), p_te))

    dnf_rows, _ = build_dnf_pipeline_rows(
        test, dnf_labels, dnf_snaps, str(DEFAULT_DB_PATH),
        test_period_start=val_end)
    pool_plain = pd.concat(
        [test.assign(is_dnf_row=0), dnf_rows.assign(is_dnf_row=1)],
        ignore_index=True)
    print(f"  Honest pool: {len(pool_plain):,} rows "
          f"({len(dnf_rows):,} DNF starters); head AUC={head_auc:.3f}", flush=True)

    pool_rated = attach_rating_features(pool_plain, rating_snaps,
                                        db_path=DEFAULT_DB_PATH)
    pool_a = attach(pool_rated, od_feats, field_shares)
    pool_a["oof_time_gap_pred"] = main_tg.predict(pool_a)
    pool_a["oof_lambdarank_win_p"] = np.asarray(
        main_lr.predict_win_probabilities(pool_a))

    honest: Dict[str, Any] = {}
    e = np.asarray(bucket_a.predict_continuous(pool_a), dtype=float)
    honest["A"] = honest_from_arrays(pool_a, e, cont_a.predict_proba(pool_a),
                                     p_map, n_classes)
    for arm, key_map in (("korc", oracle_ext), ("kmech", mech_map)):
        fr = key_attach(pool_a, key_map, **kw)
        honest[arm] = honest_from_arrays(
            fr, np.asarray(bucket_k.predict_continuous(fr), dtype=float),
            cont_k.predict_proba(fr), p_map, n_classes)
    e_mix, p_mix = mixed_predictions(pool_a, bucket_k, cont_k, fixed_map,
                                     weights, **kw)
    honest["kmix"] = honest_from_arrays(pool_a, e_mix, p_mix, p_map, n_classes)

    # ---- fold summary ----
    for arm in ARMS:
        r = res[arm].get("all", {})
        h = honest[arm].get("all", {}).get("honest_adjusted", {})
        print(f"    {arm:<6s} mkt_ll={r.get('market_avg_log_loss', np.nan):.4f} "
              f"honest={h.get('market_avg_log_loss', np.nan):.4f} "
              f"wcap={r.get('race_winner_capture_rate', np.nan):.4f}", flush=True)

    return {
        "fold_label": label, "skipped": False,
        "selector": sel["diag"],
        "arms": res,
        "honest": honest,
        "dtm_importance_K": kern_imp,
        "dnf_head_auc": float(head_auc),
    }, all_records


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _stat(vals: List[float]) -> Dict[str, Any]:
    return {"mean": float(np.mean(vals)), "std": float(np.std(vals)),
            "per_fold": [float(v) for v in vals]}


def build_aggregates(usable: List[Dict[str, Any]],
                     rec_df: pd.DataFrame) -> Dict[str, Any]:
    agg: Dict[str, Any] = {"paired_deltas": {}, "honest": {},
                           "surfacing": {}, "selector": {}}
    karms = [a for a in ARMS if a != "A"]
    for subset in EVAL_SUBSETS:
        agg["paired_deltas"][subset] = {}
        for arm in karms:
            block = {}
            for k in DELTA_METRICS:
                ds = [fr["arms"][arm][subset][k] - fr["arms"]["A"][subset][k]
                      for fr in usable
                      if subset in fr["arms"][arm] and subset in fr["arms"]["A"]
                      and k in fr["arms"][arm][subset]
                      and not np.isnan(fr["arms"][arm][subset][k])]
                if ds:
                    block[k] = _stat(ds)
            agg["paired_deltas"][subset][f"{arm}_minus_A"] = block

    for subset in HONEST_SUBSETS:
        entry: Dict[str, Any] = {}
        for arm in ARMS:
            folds_with = [fr for fr in usable if subset in fr["honest"][arm]]
            if folds_with:
                entry[arm] = {"level_honest_adjusted_market_avg_log_loss": _stat(
                    [fr["honest"][arm][subset]["honest_adjusted"]["market_avg_log_loss"]
                     for fr in folds_with])}
        for arm in karms:
            both = [fr for fr in usable
                    if subset in fr["honest"][arm] and subset in fr["honest"]["A"]]
            if both:
                entry[f"{arm}_minus_A__honest_adjusted"] = {
                    k: _stat([fr["honest"][arm][subset]["honest_adjusted"][k]
                              - fr["honest"]["A"][subset]["honest_adjusted"][k]
                              for fr in both])
                    for k in HONEST_DELTA_METRICS}
        if entry:
            agg["honest"][subset] = entry

    for arm in karms:
        agg["surfacing"][arm] = {
            dc: slice_deltas4(rec_df, arm, dc)
            for dc in ("residual", "gc_day", "bunch", "itt")}

    agg["selector"] = {
        "test_top1": _stat([fr["selector"]["test_top1"] for fr in usable]),
        "test_top2": _stat([fr["selector"]["test_top2"] for fr in usable]),
        "temperature": _stat([fr["selector"]["temperature"] for fr in usable]),
    }

    # ---- pre-registered PASS (kmix vs A) ----
    t = THRESHOLDS
    n = len(usable)
    g1 = agg["honest"].get("all", {}).get("kmix_minus_A__honest_adjusted", {}) \
        .get("market_avg_log_loss")
    g1_od = agg["honest"].get("one_day", {}).get("kmix_minus_A__honest_adjusted", {}) \
        .get("market_avg_log_loss")
    r = agg["surfacing"]["kmix"]["residual"]
    guards = agg["paired_deltas"]["all"]["kmix_minus_A"].get("race_winner_capture_rate")
    guards_od = agg["paired_deltas"].get("one_day", {}).get("kmix_minus_A", {}) \
        .get("race_winner_capture_rate")
    checks = {
        "g1_all": bool(g1 and g1["mean"] <= t["g1_all_honest_mkt_ll_max"]
                       and sum(1 for v in g1["per_fold"] if v <= 0)
                       >= min(t["g1_all_folds_nonpos_min"], n)),
        "g1_oneday": bool(g1_od and g1_od["mean"] <= t["g1_oneday_honest_mkt_ll_max"]),
        "g2_winner_rank": bool(
            r["winner_model_rank"]["pooled_delta"] <= t["g2_winner_rank_delta_max"]
            and r["winner_model_rank"]["folds_neg"]
            >= min(t["g2_winner_rank_folds_neg_min"], n)),
        "g2_cosine": bool(
            r["board_front_cosine"]["pooled_delta"] >= t["g2_cosine_delta_min"]
            and r["board_front_cosine"]["folds_nonneg"]
            >= min(t["g2_cosine_folds_nonneg_min"], n)),
        "guard_all_wcap": bool(guards and guards["mean"]
                               >= t["guard_all_winner_capture_min"]),
        "guard_od_wcap": bool(guards_od and guards_od["mean"]
                              >= t["guard_oneday_winner_capture_min"]),
    }
    agg["pass_checks_kmix"] = checks
    agg["PASS_kmix"] = bool(all(checks.values()))
    return agg


def print_summary(agg: Dict[str, Any], n_folds: int):
    print("\n" + "=" * 92, flush=True)
    print("HONEST FRAME market_avg_log_loss deltas vs A (PRIMARY)", flush=True)
    print("=" * 92, flush=True)
    for subset in HONEST_SUBSETS:
        e = agg["honest"].get(subset, {})
        for arm in ("korc", "kmech", "kmix"):
            d = e.get(f"{arm}_minus_A__honest_adjusted", {}).get("market_avg_log_loss")
            if d:
                per = " ".join(f"{v:+.4f}" for v in d["per_fold"])
                neg = sum(1 for v in d["per_fold"] if v <= 0)
                print(f"  {subset:<8s} {arm}-A {d['mean']:+.4f}±{d['std']:.4f} "
                      f"({neg}/{len(d['per_fold'])} <=0)  [{per}]", flush=True)
        if e:
            print("", flush=True)
    print("=" * 92, flush=True)
    print("SURFACING (residual slice, deltas vs A)", flush=True)
    print("=" * 92, flush=True)
    for arm in ("korc", "kmech", "kmix"):
        r = agg["surfacing"][arm]["residual"]
        print(f"  {arm:<6s} winner_rank {r['winner_model_rank']['pooled_delta']:+.3f} "
              f"({r['winner_model_rank']['folds_neg']}/{n_folds} neg)  "
              f"pool15 {r['winner_in_pool15']['pooled_delta']:+.4f}  "
              f"front_recall {r['front_recall15']['pooled_delta']:+.4f}  "
              f"cosine {r['board_front_cosine']['pooled_delta']:+.4f} "
              f"({r['board_front_cosine']['folds_nonneg']}/{n_folds})", flush=True)
    print(f"\n  selector: top1={agg['selector']['test_top1']['mean']:.3f} "
          f"top2={agg['selector']['test_top2']['mean']:.3f}", flush=True)
    print(f"\n  PASS checks (kmix): {json.dumps(agg['pass_checks_kmix'])}", flush=True)
    print(f"  PASS_kmix = {agg['PASS_kmix']}", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

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
    print("DAY-MENU STEP-4 GATE — full stack, serve keys, board mixing", flush=True)
    print(f"Arms: {ARM_DESC}", flush=True)
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

    if DEFAULT_SNAPSHOT_PATH.exists():
        rating_snaps = load_snapshots(DEFAULT_SNAPSHOT_PATH)
    else:
        rating_snaps = build_and_save()

    df = _load_full_df()
    df["rider_id"] = df["rider_id"].astype(np.int64)
    df_rated = attach_rating_features(df, rating_snaps, db_path=DEFAULT_DB_PATH)
    assert (df_rated["competition_id"].to_numpy()
            == df["competition_id"].to_numpy()).all()
    print(f"Loaded {len(df):,} rows, {df['competition_id'].nunique():,} comps",
          flush=True)

    comp_selfeats = build_selector_features(df, sig)

    print("Loading DNF labels + head frame...", flush=True)
    dnf_labels = load_labels()
    dnf_labels = dnf_labels[dnf_labels["competition_date"].notna()
                            & dnf_labels["rider_id"].notna()].copy()
    dnf_labels["rider_id"] = dnf_labels["rider_id"].astype("int64")
    dnf_labels = add_asof_dates(dnf_labels)
    dnf_snaps = load_snapshot_table()
    head_frame = build_feature_frame(labels=dnf_labels, snaps=dnf_snaps,
                                     start_date=START_DATE)
    head_frame["competition_date"] = pd.to_datetime(head_frame["competition_date"])

    partial = OUT_DIR / "day_menu_gate4_cv_partial.json"
    fold_results: List[Dict[str, Any]] = []
    all_records: List[Dict] = []
    for i, fold in enumerate(folds):
        print(f"\n{'─'*60}\nFOLD {i+1}/{len(folds)} (test={fold['label']}+)\n{'─'*60}",
              flush=True)
        fr, recs = run_fold(i, fold, df, df_rated, od_feats, field_shares,
                            rating_snaps, labels, hist, comp_selfeats,
                            place_map, dnf_labels, dnf_snaps, head_frame,
                            args.smoke)
        fold_results.append(fr)
        all_records.extend(recs)
        partial.write_text(json.dumps(
            {"folds_done": i + 1, "fold_results": fold_results},
            indent=2, default=str))

    usable = [fr for fr in fold_results if not fr.get("skipped")]
    rec_df = pd.DataFrame(all_records)
    agg = build_aggregates(usable, rec_df)
    print_summary(agg, len(usable))

    ended = datetime.now()
    ts = ended.strftime("%Y%m%d_%H%M%S")
    tag = "smoke_" if args.smoke else ""
    rec_path = OUT_DIR / f"day_menu_gate4_records_{tag}{ts}.csv.gz"
    rec_df.to_csv(rec_path, index=False, compression="gzip")
    out = {
        "started_at": started.isoformat(), "ended_at": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "config": {"folds": folds, "start_date": START_DATE, "k_menu": K_MENU,
                   "gamma": GAMMA, "half_life_days": HALF_LIFE_DAYS,
                   "min_eff_n": MIN_EFF_N, "mix_top": MIX_TOP,
                   "thresholds": THRESHOLDS, "arms": ARM_DESC,
                   "selector_excluded": sorted(SELECTOR_EXCLUDE),
                   "smoke": args.smoke},
        "label_counts": labels.day_class.value_counts().to_dict(),
        "fold_results": fold_results,
        "aggregated": agg,
        "records_csv": rec_path.name,
    }
    path = OUT_DIR / f"day_menu_gate4_cv_{tag}{ts}.json"
    path.write_text(json.dumps(out, indent=2, default=str))
    if partial.exists():
        partial.unlink()
    print(f"\nSaved {path}  ({(ended-started).total_seconds()/60:.1f} min)",
          flush=True)


if __name__ == "__main__":
    main()
