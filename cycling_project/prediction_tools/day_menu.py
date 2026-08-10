"""
Day-type menu — production port of the retrieval-only ranking channel
(Option A, decided 2026-08-09; gates 4/5/6 in experiment_log.md).

The menu is a frozen vocabulary of day types ("what kind of day is this?")
keyed by CONTESTING-RIDER COMPOSITION: 3 mechanically-routed macro items
(itt / bunch / gc_day) + 8 residual analogs fit by a GMM on realized top-15
archetype shares. Serving keys a stage to one item (or a weighted set); the
kernod-featured bucket model then governs ONLY contender selection (pool
membership + board order). The untouched production heads price the pool.

HARD ARCHITECTURE CONSTRAINTS (gate verdicts, permanent):
  - dtm_* features NEVER go into any pricing head (gate 4: +0.0107 honest
    market LL, 0/5 folds — the conditioning tax is global).
  - Conditional boards NEVER serve prices at any tier (gate 5: residual
    home-turf +0.0158 with perfect keys).
  - Weighted key sets are mixed at the RANKING stage (board mixing) — never
    by averaging item descriptions or features.

Feature namespace: 14 columns, all prefixed dtm_ (day-type menu), names
deliberately avoiding the 'avg_bucket' / '_count' substrings that trigger
pattern imputation in feature_engineering.py:
  fills (stage comps with a key):   dtm_sig_<arch> x6, dtm_sig_wg_prop,
                                    dtm_rider_sig_share, dtm_rider_sig_vs_field,
                                    dtm_rider_contest_fit
  kernels (any comp with a key,     dtm_k_expos, dtm_k_attend, dtm_k_top3,
   incl. one-day self-keys):        dtm_k_perf_place

Key sources at serve (priority): judgment read > one-day self-key
(automatic, nearest canonical to own as-of-then B4 signature) > none
(production ranking; the mechanical-selector fallback is default OFF).
Training always uses oracle own-assignment keys (settled design — same
epistemic move as training on realized winning_time).

Artifacts:
  models/production/day_menu_v1.json      frozen canonicals + GMM params +
                                          labeler config (assignment is a
                                          stored-parameter predict — NEVER
                                          a refit)
  models/production/day_menu_kernels.parquet
                                          per-rider cumulative kernel sums,
                                          rebuilt at update time from the
                                          signature table

Experiment lineage: day_menu_gate_cv.py (labeler, fills),
day_menu_gate3_cv.py (kernels), day_menu_gate4_cv.py (key_attach, board
mixing), build_day_menu_v1.py (freeze).
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = (
    Path(__file__).parent.parent
    / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)
PRODUCTION_DIR = Path(__file__).parent.parent.parent / "models" / "production"
MENU_PATH = PRODUCTION_DIR / "day_menu_v1.json"
KERNELS_PATH = PRODUCTION_DIR / "day_menu_kernels.parquet"

ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
SH15 = [f"top15_{a}" for a in ARCH]
SIGC = [f"sig_{a}" for a in ARCH]
DTM_SIG = [f"dtm_sig_{a}" for a in ARCH]
DTM_FILL_COLS = DTM_SIG + [
    "dtm_sig_wg_prop",
    "dtm_rider_sig_share", "dtm_rider_sig_vs_field", "dtm_rider_contest_fit",
]
DTM_KERNEL_COLS = ["dtm_k_expos", "dtm_k_attend", "dtm_k_top3", "dtm_k_perf_place"]
DAY_MENU_FEATURE_COLS = DTM_FILL_COLS + DTM_KERNEL_COLS

# Kernel constants — must match the gated experiment (day_menu_gate3_cv.py).
GAMMA = 8.0
HALF_LIFE_DAYS = 730.0
LAM = np.log(2.0) / HALF_LIFE_DAYS
EPOCH = pd.Timestamp("2010-01-01")
MIN_EFF_N = 3.0
CUM_KINDS = ["expos", "att", "top3", "perf"]


def _unit(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, dtype=float)
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    n[n == 0] = 1
    return m / n


# ---------------------------------------------------------------------------
# Frozen menu artifact
# ---------------------------------------------------------------------------

@dataclass
class DayMenu:
    version: str
    canonicals: pd.DataFrame          # index=item; sig_* x6, sig_wg_prop, n_members
    gmm_means: np.ndarray             # k x 6
    gmm_covariances: np.ndarray       # k x 6 x 6
    gmm_weights: np.ndarray           # k
    labeler: Dict[str, float]         # itt_seconds, wide_bs_prop, gc_top, unknown_junk

    @property
    def items(self) -> List[str]:
        return list(self.canonicals.index)

    @property
    def residual_items(self) -> List[str]:
        return [i for i in self.items if i.startswith("res_")]


def load_menu(path: Optional[Path] = None) -> DayMenu:
    """Load the frozen menu artifact. Serving NEVER refits — assignment of a
    new day is a stored-parameter GMM predict."""
    path = Path(path) if path else MENU_PATH
    raw = json.loads(path.read_text())
    canon = pd.DataFrame.from_dict(raw["canonicals"], orient="index")
    canon.index.name = "item"
    menu = DayMenu(
        version=raw["version"],
        canonicals=canon,
        gmm_means=np.asarray(raw["gmm"]["means"], dtype=float),
        gmm_covariances=np.asarray(raw["gmm"]["covariances"], dtype=float),
        gmm_weights=np.asarray(raw["gmm"]["weights"], dtype=float),
        labeler=raw["labeler"],
    )
    logger.info("Day menu %s loaded: %d items (%d residual analogs)",
                menu.version, len(menu.items), len(menu.residual_items))
    return menu


def assign_residual_items(shares: np.ndarray, menu: DayMenu) -> np.ndarray:
    """GMM assignment from stored parameters (identical to sklearn predict:
    argmax_k [log w_k + log N(x; mu_k, Sigma_k)]). shares: n x 6 top-15
    archetype shares. Returns array of 'res_<k>' labels."""
    x = np.atleast_2d(np.asarray(shares, dtype=float))
    k = len(menu.gmm_weights)
    log_prob = np.empty((len(x), k))
    d = x.shape[1]
    for j in range(k):
        cov = menu.gmm_covariances[j]
        chol = np.linalg.cholesky(cov)
        dev = x - menu.gmm_means[j]
        z = np.linalg.solve(chol, dev.T).T          # whitened deviations
        log_det = 2.0 * np.log(np.diag(chol)).sum()
        log_prob[:, j] = (
            -0.5 * (d * np.log(2 * np.pi) + log_det + (z ** 2).sum(axis=1))
            + np.log(menu.gmm_weights[j])
        )
    return np.array([f"res_{int(i)}" for i in log_prob.argmax(axis=1)])


# ---------------------------------------------------------------------------
# Signature table (DB-fresh rebuild; the menu REFIT instead uses the CSV
# artifact emitted by experiments/selection_signatures.py)
# ---------------------------------------------------------------------------

def build_signature_table_from_db() -> pd.DataFrame:
    """Per-comp contest signatures straight from the DB (stage + one_day).

    Same construction as the experiments/selection_signatures.py artifact
    (comp_features + rule_label + top-K archetype shares + enrichment) but
    built in memory at update time so kernels and oracle labels never run on
    a stale CSV. Import is lazy — the experiment modules are heavy.
    """
    from cycling_project.prediction_tools.experiments.selection_signatures import (
        add_enrichment,
        build_signatures,
        load_field_shares as _load_sig_field_shares,
        load_results as _load_sig_results,
    )
    sig = add_enrichment(build_signatures(_load_sig_results()),
                         _load_sig_field_shares())
    sig["date"] = pd.to_datetime(sig["date"])
    logger.info("Signature table (DB-fresh): %d comps through %s",
                len(sig), sig.date.max().date())
    return sig


# ---------------------------------------------------------------------------
# Oracle labeler (post-hoc day classification; update-time + evening scoring)
# ---------------------------------------------------------------------------

def label_days(sig: pd.DataFrame, menu: DayMenu,
               db_path: Optional[Path] = None) -> pd.DataFrame:
    """Per stage comp in the signature table: day_class + menu item (oracle).

    Port of day_menu_gate_cv.build_labels + residual assignment under the
    FROZEN menu. Used at update time (oracle own-assignment training keys)
    and each evening at the Vuelta (label the settled stage, score the key).
    """
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    cfg = menu.labeler
    st = sig[sig["competition_type"] == "stage"].copy()

    con = sqlite3.connect(db_path)
    comps = pd.read_sql(
        "SELECT id, race_id, competition_type, winning_time FROM competitions", con)
    gc_comps = comps[comps.competition_type == "gc"][["id", "race_id"]]
    need = set(st.comp_id) | set(gc_comps.id)
    con.execute("CREATE TEMP TABLE need(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO need VALUES (?)",
                    [(int(i),) for i in need])
    rr = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN need n ON n.id = r.competition_id""", con)
    state = pd.read_sql(
        "SELECT competition_id, rider_id, gc_rank_current FROM rider_race_state", con)
    con.close()
    rr["place_n"] = pd.to_numeric(rr.place, errors="coerce")

    st = st.merge(comps[["id", "race_id", "winning_time"]],
                  left_on="comp_id", right_on="id", how="left").drop(columns=["id"])

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

    st["is_itt"] = st.winning_time < cfg["itt_seconds"]
    st["is_bunch"] = (st.rule_type == "mass_sprint") | (
        (st.rule_type == "bunch_sprint") & (st.wg_prop >= cfg["wide_bs_prop"]))
    st["is_gc_day"] = (st.gc_eff <= cfg["gc_top"]) | (st.front5_gc_m <= cfg["gc_top"])
    st["day_class"] = np.select(
        [st.is_itt, st.is_bunch, st.is_gc_day],
        ["itt", "bunch", "gc_day"], default="residual")

    res_mask = st.day_class == "residual"
    st["item"] = st.day_class.where(~res_mask, other=np.nan)
    if res_mask.any():
        st.loc[res_mask, "item"] = assign_residual_items(
            st.loc[res_mask, SH15].values, menu)
    logger.info("labeled %d stage comps: %s", len(st),
                st.day_class.value_counts().to_dict())
    return st


def oracle_key_map(labels: pd.DataFrame) -> pd.Series:
    """comp_id -> item for every labeled stage comp (the training key map)."""
    return labels.set_index("comp_id")["item"]


def self_key_oneday(od_feats: pd.DataFrame, menu: DayMenu) -> pd.Series:
    """One-day comps -> nearest menu canonical to their as-of-then B4
    signature (cosine). Automatic — no judgment involved."""
    odv = od_feats.dropna(subset=SIGC)
    if odv.empty:
        return pd.Series(dtype=object)
    u = _unit(odv[SIGC].values)
    c = _unit(menu.canonicals[SIGC].values.astype(float))
    best = (u @ c.T).argmax(axis=1)
    return pd.Series(menu.canonicals.index.values[best], index=odv.comp_id.values)


# ---------------------------------------------------------------------------
# Kernel cumulants (update-time build; parquet artifact)
# ---------------------------------------------------------------------------

def build_rider_history(sig: pd.DataFrame,
                        db_path: Optional[Path] = None) -> pd.DataFrame:
    """Every finisher row in a signature-covered comp, with realized shares."""
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    con = sqlite3.connect(db_path)
    con.execute("CREATE TEMP TABLE sc(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO sc VALUES (?)",
                    [(int(i),) for i in sig.comp_id])
    rr = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN sc ON sc.id = r.competition_id""", con)
    con.close()
    rr["place_n"] = pd.to_numeric(rr.place, errors="coerce")
    rr = rr[rr.place_n.notna()]
    hist = rr.merge(sig[["comp_id", "date"] + SH15],
                    left_on="competition_id", right_on="comp_id")
    hist["date"] = pd.to_datetime(hist["date"])
    hist["top15"] = (hist.place_n <= 15).astype(float)
    hist["top3"] = (hist.place_n <= 3).astype(float)
    logger.info("kernel rider history: %d rows, %d riders, %d comps",
                len(hist), hist.rider_id.nunique(), hist.comp_id.nunique())
    return hist


def kernel_cumulants(hist: pd.DataFrame, menu: DayMenu) -> pd.DataFrame:
    """Per-rider date-sorted cumulative kernel sums for every menu item.

    Decay factorization: sum_h w_h * exp(-lam*(t - t_h)) =
    exp(-lam*t) * sum_h w_h * exp(lam*t_h) — cumulants store growth-weighted
    sums; the attach divides by exp(lam*t) (ratio features cancel it).
    """
    items = menu.items
    s = _unit(hist[SH15].values)
    c = _unit(menu.canonicals[SIGC].values.astype(float))
    w = np.clip(s @ c.T, 0, None) ** GAMMA          # n_hist x n_items
    growth = np.exp(LAM * (hist.date - EPOCH).dt.days.to_numpy())
    w = w * growth[:, None]

    cum = hist[["rider_id", "date"]].copy()
    top15 = hist.top15.to_numpy()
    top3 = hist.top3.to_numpy()
    place = hist.place_n.to_numpy()
    for j, item in enumerate(items):
        cum[f"expos__{item}"] = w[:, j]
        cum[f"att__{item}"] = w[:, j] * top15
        cum[f"top3__{item}"] = w[:, j] * top3
        cum[f"perf__{item}"] = w[:, j] * top15 * place
    cum = cum.sort_values(["date", "rider_id"], kind="mergesort")
    val_cols = [col for col in cum.columns if "__" in col]
    cum[val_cols] = cum.groupby("rider_id")[val_cols].cumsum()
    return cum


def save_kernels(cum: pd.DataFrame, path: Optional[Path] = None) -> Path:
    path = Path(path) if path else KERNELS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    cum.to_parquet(path, index=False)
    logger.info("Saved kernel cumulants: %s (%d rows, %d riders)",
                path, len(cum), cum.rider_id.nunique())
    return path


def load_kernels(path: Optional[Path] = None) -> pd.DataFrame:
    path = Path(path) if path else KERNELS_PATH
    cum = pd.read_parquet(path)
    cum["date"] = pd.to_datetime(cum["date"])
    return cum


# ---------------------------------------------------------------------------
# Feature attachment (training + serving share this path)
# ---------------------------------------------------------------------------

def _feats_from_map(key_map: pd.Series, menu: DayMenu,
                    stage_comps: set) -> pd.DataFrame:
    """Canonical-fill table for keyed STAGE comps (one-day comps keep their
    production sig_* B4 and receive kernels only)."""
    km = key_map[key_map.index.isin(stage_comps)]
    out = pd.DataFrame({"comp_id": km.index, "item": km.values})
    out = out.merge(menu.canonicals.reset_index(), on="item", how="left")
    keep = ["comp_id"] + SIGC + ["sig_wg_prop"]
    return out[keep].dropna(subset=SIGC)


def _attach_fills(df: pd.DataFrame, fills: pd.DataFrame,
                  field_shares: pd.DataFrame) -> pd.DataFrame:
    """dtm_sig_* fills + rider-interaction features (dtm namespace).

    Requires best_profile and the six <arch>_avg_bucket columns on df.
    Rows whose competition is not in fills get NaN in every fill column.
    """
    f = fills.rename(columns={f"sig_{a}": f"dtm_sig_{a}" for a in ARCH}
                     | {"sig_wg_prop": "dtm_sig_wg_prop"})
    out = df.merge(f, left_on="competition_id", right_on="comp_id", how="left")
    out = out.merge(field_shares, left_on="competition_id", right_on="comp_id",
                    how="left", suffixes=("", "_fs"))
    out.drop(columns=[c for c in ("comp_id", "comp_id_fs") if c in out],
             inplace=True)

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


def _attach_kernels(df: pd.DataFrame, cum: pd.DataFrame, items: List[str],
                    key_map: pd.Series) -> pd.DataFrame:
    """The four dtm_k_* features for every row whose comp has a key.

    As-of-then discipline: merge_asof backward with allow_exact_matches=False
    — a ride ON the target date never feeds its own kernels.
    """
    out = df.copy()
    out["_item"] = out["competition_id"].map(key_map)
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


def attach_day_menu_features(
    frame: pd.DataFrame,
    key_map: pd.Series,
    menu: DayMenu,
    cum: pd.DataFrame,
    field_shares: pd.DataFrame,
    stage_comps: Optional[set] = None,
) -> pd.DataFrame:
    """Attach all 14 dtm_* columns to a model frame under a key assignment.

    frame: any frame carrying competition_id, rider_id, competition_date,
           best_profile, <arch>_avg_bucket x6 (raw, pre-encoding).
    key_map: comp_id -> item. Stage comps get fills + kernels; one-day comps
           (self-keys) get kernels only; comps absent from key_map get NaN
           in every dtm_* column — the trained models' unkeyed state.
    stage_comps: comps eligible for fills. Defaults to every keyed comp
           whose item is in the menu (callers with one-day self-keys in
           key_map MUST pass the true stage set).
    """
    if stage_comps is None:
        stage_comps = set(key_map.index)
    fills = _feats_from_map(key_map, menu, stage_comps)
    out = _attach_fills(frame, fills, field_shares)
    return _attach_kernels(out, cum, menu.items, key_map)


# ---------------------------------------------------------------------------
# Serving (future races): one race, one key (or weighted set)
# ---------------------------------------------------------------------------

# best_profile value -> compute_field_features count key (6 known archetypes)
_FIELD_COUNT_COLS = {
    "sprint": "sprinter_count",
    "mountain": "climber_count",
    "hilly": "hilly_specialist_count",
    "rolling": "rolling_specialist_count",
    "breakaway": "breakaway_specialist_count",
    "time_trial": "time_trialist_count",
}


def attach_day_menu_serving(
    frame: pd.DataFrame,
    item: str,
    menu: DayMenu,
    cum: pd.DataFrame,
    field_features: Dict,
    race_date,
) -> pd.DataFrame:
    """Attach all 14 dtm_* columns to a single-race serve frame for ONE item.

    Broadcast analogue of attach_day_menu_features for a future race: fills
    come from the frozen canonical, rider interactions from the scraped
    startlist's field shares (compute_field_features dict), kernels from the
    cumulants parquet as of race_date (all settled history is strictly
    before race morning, preserving the as-of-then discipline).
    """
    if item not in menu.items:
        raise ValueError(f"unknown menu item '{item}'")
    out = frame.copy()
    canon = menu.canonicals.loc[item]
    for a in ARCH:
        out[f"dtm_sig_{a}"] = float(canon[f"sig_{a}"])
    out["dtm_sig_wg_prop"] = float(canon["sig_wg_prop"])

    field_size = max(int(field_features.get("field_size") or 0), 1)
    shares = {a: float(field_features.get(col, 0) or 0) / field_size
              for a, col in _FIELD_COUNT_COLS.items()}
    bp = out["best_profile"].map({a: i for i, a in enumerate(ARCH)})
    has_bp = bp.notna().to_numpy()
    bp_idx = bp.fillna(0).astype(int).to_numpy()
    sig_vec = np.array([float(canon[f"sig_{a}"]) for a in ARCH])
    fs_vec = np.array([shares[a] for a in ARCH])
    out["dtm_rider_sig_share"] = np.where(has_bp, sig_vec[bp_idx], np.nan)
    out["dtm_rider_sig_vs_field"] = np.where(
        has_bp, sig_vec[bp_idx] - fs_vec[bp_idx], np.nan)
    ability = np.column_stack(
        [(4.0 - out[f"{a}_avg_bucket"].to_numpy(dtype=float)) for a in ARCH])
    out["dtm_rider_contest_fit"] = np.einsum(
        "ij,ij->i", np.tile(np.nan_to_num(sig_vec), (len(out), 1)), ability)

    # kernels as of race morning
    race_date = pd.Timestamp(race_date)
    t = out[["rider_id"]].copy()
    t["_date"] = race_date
    t["_date"] = t["_date"].astype("datetime64[ns]")
    t = t.reset_index()
    cs = cum.rename(columns={"date": "_date"}).sort_values(
        ["_date", "rider_id"], kind="mergesort")
    cs["_date"] = cs["_date"].astype("datetime64[ns]")
    merged = pd.merge_asof(
        t.sort_values("_date", kind="mergesort"), cs,
        on="_date", by="rider_id", direction="backward",
        allow_exact_matches=False)
    merged = merged.set_index("index").reindex(out.index)
    decay = float(np.exp(LAM * (race_date - EPOCH).days))
    expos = merged[f"expos__{item}"].to_numpy(dtype=float) / decay
    att = merged[f"att__{item}"].to_numpy(dtype=float)
    top3 = merged[f"top3__{item}"].to_numpy(dtype=float)
    perf = merged[f"perf__{item}"].to_numpy(dtype=float)
    ex_raw = merged[f"expos__{item}"].to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        attend = np.where(ex_raw > 0, att / ex_raw, np.nan)
        t3 = np.where(ex_raw > 0, top3 / ex_raw, np.nan)
        pp = np.where(att > 0, perf / att, np.nan)
    thin = ~(expos >= MIN_EFF_N)
    attend[thin] = np.nan
    t3[thin] = np.nan
    pp[thin] = np.nan
    out["dtm_k_expos"] = expos
    out["dtm_k_attend"] = attend
    out["dtm_k_top3"] = t3
    out["dtm_k_perf_place"] = pp
    return out


def serving_board_scores(
    frame: pd.DataFrame,
    bucket_model,
    key_weights: Dict[str, float],
    menu: DayMenu,
    cum: pd.DataFrame,
    field_features: Dict,
    race_date,
) -> np.ndarray:
    """Kernod ranking scores for one future race under a weighted key set.

    key_weights: {item: weight} — the judgment read for THIS race (singleton
    is the common case). Weights normalize; mixing happens at the RANKING-
    SCORE level (one prediction per item, blended) — never by averaging
    item descriptions. Lower score = better expected finish.
    """
    wts = {i: float(w) for i, w in key_weights.items() if float(w) > 0}
    bad = set(wts) - set(menu.items)
    if bad:
        raise ValueError(f"unknown menu item(s): {sorted(bad)}")
    tot = sum(wts.values())
    if tot <= 0:
        raise ValueError("non-positive day-key weights")
    scores = np.zeros(len(frame), dtype=float)
    for item, w in wts.items():
        fr = attach_day_menu_serving(frame, item, menu, cum,
                                     field_features, race_date)
        scores += (w / tot) * np.asarray(
            bucket_model.predict_continuous(fr), dtype=float)
    return scores


# ---------------------------------------------------------------------------
# Serve-time board mixing (ranking scores only — never prices)
# ---------------------------------------------------------------------------

def mixed_ranking_scores(
    frame: pd.DataFrame,
    bucket_model,
    key_weights: Dict[int, Dict[str, float]],
    menu: DayMenu,
    cum: pd.DataFrame,
    field_shares: pd.DataFrame,
    stage_comps: Optional[set] = None,
    fixed_key_map: Optional[pd.Series] = None,
) -> np.ndarray:
    """Expected-bucket ranking scores under weighted day keys.

    key_weights: {comp_id: {item: weight}} — the judgment read (weights
    normalized per comp; singletons are the common case). fixed_key_map
    carries automatic keys for other comps in the frame (one-day self-keys).
    Mixing happens at the RANKING-SCORE level: the frame is scored once per
    item under a complete key assignment and blended per-comp — never by
    averaging features. Comps with no key anywhere get the unkeyed (all-NaN
    dtm) prediction; production serving uses the production board for those.
    """
    norm: Dict[int, Dict[str, float]] = {}
    for comp, wts in key_weights.items():
        wts = {i: float(w) for i, w in wts.items() if w > 0}
        bad = set(wts) - set(menu.items)
        if bad:
            raise ValueError(f"unknown menu item(s) {bad} for comp {comp}")
        tot = sum(wts.values())
        if tot <= 0:
            raise ValueError(f"non-positive key weights for comp {comp}")
        norm[comp] = {i: w / tot for i, w in wts.items()}

    fixed = fixed_key_map if fixed_key_map is not None else pd.Series(dtype=object)
    fixed = fixed[~fixed.index.isin(norm)]
    comp_ids = frame["competition_id"].to_numpy()
    items_used = sorted({i for wts in norm.values() for i in wts})

    scores = np.zeros(len(frame), dtype=float)
    covered = np.zeros(len(frame), dtype=float)
    done_rest = False
    for m in items_used or [None]:
        w_m = np.array([norm.get(c, {}).get(m, 0.0) for c in comp_ids]) \
            if m is not None else np.zeros(len(frame))
        if not done_rest:
            # everything outside key_weights rides the first pass: fixed keys
            # (self-keys) or no key at all — identical under every m.
            w_m = w_m + np.array([1.0 if c not in norm else 0.0 for c in comp_ids])
        if w_m.sum() == 0:
            continue
        km = pd.concat([
            fixed,
            pd.Series({c: m for c in norm}) if m is not None
            else pd.Series(dtype=object),
        ])
        fr_m = attach_day_menu_features(
            frame, km, menu, cum, field_shares, stage_comps=stage_comps)
        exp_m = np.asarray(bucket_model.predict_continuous(fr_m), dtype=float)
        scores += w_m * exp_m
        covered += w_m
        done_rest = True
    if not np.allclose(covered, 1.0):
        raise RuntimeError("board mixing weights failed to cover the frame")
    return scores
