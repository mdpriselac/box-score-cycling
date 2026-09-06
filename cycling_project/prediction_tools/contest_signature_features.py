"""
Contest-signature features — production port of the one-day B4 selection
signatures (gate passed 2026-06-11, see experiment_log.md and
experiments/contest_signature_gate_cv.py / full_stack_integration_cv.py).

The 11 signature columns describe WHO is expected to contest the front of a
one-day race (archetype mix of the projected front group), built strictly
as-of-then:

  sig_<archetype>   B4 continuous: clip(current field share + mean
                    prior-edition enrichment, 0, 1). Cold start (first
                    edition on record) -> plain field share.
  sig_wg_prop       mean prior-edition winner-group proportion (NaN cold).
  sig_n_refs        number of prior editions feeding the enrichment.
  rider_sig_share   predicted contesting share of the rider's own archetype.
  rider_contest_fit rider profile-ability (4 - avg_bucket) dot predicted shares.
  rider_sig_vs_field  rider's archetype share minus its field share.

STAGE AND GC ROWS GET NaN for every signature column — the gate showed
ref-keyed stage serving costs +0.078 log loss, so stages are deliberately
out of scope. LightGBM consumes the NaNs natively; the column names avoid
the 'avg_bucket' / '_count' substrings that trigger pattern imputation in
feature_engineering.py.

Training entry: build_oneday_signature_features(db_path) reads the DB
directly (rider_results + as-of-then best_profile snapshots +
competition_field_features) — no dependence on the experiments CSV.
Serving entry: build_serving_signature_context + attach_signature_features
on a future-race frame using the chosen reference comps and the scraped
startlist's field shares.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.db_path import default_db_path

logger = get_logger(__name__)

DEFAULT_DB_PATH = default_db_path()

# Signature construction constants — must match the gated experiment
# (experiments/selection_signatures.py + contest_signature_gate_cv.py).
START_DATE = "2016-01-01"
MIN_FINISHERS = 30
GROUP_THRESHOLD_S = 1.0  # canonical same-time grouping (engineered_metrics.identify_groups)
PRIMARY_K = 10           # front-of-sheet depth for contesting shares

ARCHETYPES = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial", "unknown"]
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
SIG = [f"sig_{a}" for a in ARCH]
SIGNATURE_FEATURE_COLS = SIG + [
    "sig_wg_prop", "sig_n_refs",
    "rider_sig_share", "rider_contest_fit", "rider_sig_vs_field",
]
ABILITY = {a: f"{a}_avg_bucket" for a in ARCH}

# best_profile value -> competition_field_features count column
FIELD_COUNT_COLS = {
    "sprint": "sprinter_count",
    "mountain": "climber_count",
    "hilly": "hilly_specialist_count",
    "rolling": "rolling_specialist_count",
    "breakaway": "breakaway_specialist_count",
    "time_trial": "time_trialist_count",
    "unknown": "unknown_profile_count",
}


def group_sizes_from_gaps(gaps: np.ndarray) -> List[int]:
    """Group consecutive finishers whose gap difference <= threshold (sheet order).

    Canonical port of experiments/front_local_race_typing.group_sizes_from_gaps
    (identical to engineered_metrics.identify_groups' 1.0s rule).
    """
    sizes: List[int] = []
    current = 1
    for i in range(1, len(gaps)):
        if gaps[i] - gaps[i - 1] <= GROUP_THRESHOLD_S:
            current += 1
        else:
            sizes.append(current)
            current = 1
    sizes.append(current)
    return sizes


# ---------------------------------------------------------------------------
# DB loading
# ---------------------------------------------------------------------------

def _load_oneday_results(db_path: Path, start_date: str = START_DATE) -> pd.DataFrame:
    """One-day result rows with as-of-then rider archetypes.

    best_profile comes from rider_competition_snapshots keyed to the SAME
    competition — the snapshot is taken before the competition, so no
    hindsight (identical join to experiments/selection_signatures.py).
    """
    query = """
        SELECT c.id AS comp_id, c.date,
               r.fc_race_id, r.year,
               rr.place, rr.time_gap,
               COALESCE(s.best_profile, 'unknown') AS best_profile
        FROM competitions c
        JOIN races r ON c.race_id = r.id
        JOIN rider_results rr ON rr.competition_id = c.id
        LEFT JOIN rider_competition_snapshots s
          ON s.competition_id = rr.competition_id AND s.rider_id = rr.rider_id
        WHERE c.competition_type = 'one_day'
          AND c.date IS NOT NULL AND c.date >= ?
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(start_date,))
    logger.info(
        "Loaded %d one-day result rows across %d comps for signatures",
        len(df), df["comp_id"].nunique(),
    )
    return df


def load_field_shares(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Per-competition archetype field shares from competition_field_features."""
    cols = ", ".join(FIELD_COUNT_COLS.values())
    with sqlite3.connect(db_path) as conn:
        ff = pd.read_sql_query(
            f"SELECT competition_id AS comp_id, field_size, {cols} "
            "FROM competition_field_features",
            conn,
        )
    for arch, col in FIELD_COUNT_COLS.items():
        ff[f"field_share_{arch}"] = ff[col] / ff["field_size"].clip(lower=1)
    return ff[["comp_id"] + [f"field_share_{a}" for a in ARCHETYPES]]


# ---------------------------------------------------------------------------
# Per-competition signatures (top-10 contesting shares + wg_prop + enrichment)
# ---------------------------------------------------------------------------

def _comp_signature_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Per one-day comp: wg_prop + top-10 archetype shares.

    Filters mirror the experiment exactly: skip comps with >5% NaN gaps or
    fewer than MIN_FINISHERS valid-gap finishers. Top-K shares come from the
    full sheet sorted by place (NaN-gap rows included, as in the original).
    """
    rows = []
    for comp_id, g in df.groupby("comp_id", sort=False):
        gaps = g["time_gap"].to_numpy(dtype=float)
        if np.isnan(gaps).mean() > 0.05:
            continue
        valid_gaps = np.sort(gaps[~np.isnan(gaps)])
        if len(valid_gaps) < MIN_FINISHERS:
            continue
        valid_gaps = valid_gaps - valid_gaps[0]

        sizes = group_sizes_from_gaps(valid_gaps)
        row: Dict = {
            "comp_id": comp_id,
            "fc_race_id": g["fc_race_id"].iloc[0],
            "year": g["year"].iloc[0],
            "date": g["date"].iloc[0],
            "wg_prop": sizes[0] / len(valid_gaps),
        }
        top = g.sort_values("place")["best_profile"].iloc[:PRIMARY_K]
        shares = top.value_counts(normalize=True)
        for arch in ARCHETYPES:
            row[f"top{PRIMARY_K}_{arch}"] = float(shares.get(arch, 0.0))
        rows.append(row)
    comp = pd.DataFrame(rows)
    logger.info("Built %d one-day competition signatures", len(comp))
    return comp


def build_signature_table(db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """One-day signature table with enrichment columns, straight from the DB.

    Columns: comp_id, fc_race_id, year, date, wg_prop, top10_<arch>,
    field_share_<arch>, enrich_<arch> (= top10 share - field share).
    """
    results = _load_oneday_results(db_path)
    comp = _comp_signature_rows(results)
    field = load_field_shares(db_path)
    comp = comp.merge(field, on="comp_id", how="left")
    for arch in ARCHETYPES:
        comp[f"enrich_{arch}"] = comp[f"top{PRIMARY_K}_{arch}"] - comp[f"field_share_{arch}"]
    return comp


# ---------------------------------------------------------------------------
# One-day B4 features (as-of-then, fold-independent)
# ---------------------------------------------------------------------------

def oneday_b4(sig: pd.DataFrame) -> pd.DataFrame:
    """As-of-then B4 features per one-day comp (port of the gated rule).

    For each edition: sig_<a> = clip(own field share + mean prior-edition
    enrichment, 0, 1); first edition falls back to the plain field share.
    sig_wg_prop / sig_n_refs from prior editions only.
    """
    rows = []
    for rid, g in sig.groupby("fc_race_id"):
        g = g.sort_values("year").reset_index(drop=True)
        for i in range(len(g)):
            r = g.iloc[i]
            prior = g.iloc[:i]
            row = {"comp_id": r["comp_id"], "sig_n_refs": float(i)}
            for a in ARCH:
                fs = float(r[f"field_share_{a}"])
                if i > 0:
                    row[f"sig_{a}"] = float(np.clip(fs + prior[f"enrich_{a}"].mean(), 0, 1))
                else:
                    row[f"sig_{a}"] = fs
            row["sig_wg_prop"] = float(prior["wg_prop"].mean()) if i > 0 else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def build_oneday_signature_features(
    db_path: Optional[Path] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Training entry point: (od_feats, field_shares) straight from the DB.

    od_feats: one row per qualifying one-day comp with sig_<arch>,
              sig_wg_prop, sig_n_refs (comp_id-keyed; everything else NaN
              after the left-join in attach_signature_features).
    field_shares: comp_id + field_share_<archetype> for ALL competitions
              (needed by the rider_sig_vs_field interaction).
    """
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    sig = build_signature_table(db_path)
    od_feats = oneday_b4(sig)
    # Restrict to the 6 known archetypes — matches the gated experiment's
    # field_shares frame exactly (no field_share_unknown on the model frame).
    field_shares = load_field_shares(db_path)[
        ["comp_id"] + [f"field_share_{a}" for a in ARCH]
    ]
    if not od_feats.empty:
        assert od_feats["comp_id"].is_unique, "duplicate comp_id in signature features"
    return od_feats, field_shares


# ---------------------------------------------------------------------------
# Attachment (training + serving share this; port of contest_signature_gate_cv.attach)
# ---------------------------------------------------------------------------

def attach_signature_features(
    df: pd.DataFrame,
    comp_feats: pd.DataFrame,
    field_shares: pd.DataFrame,
) -> pd.DataFrame:
    """Join comp-level sig features on competition_id and add rider interactions.

    Rows whose competition has no signature row (stage / gc / filtered
    one-days) get NaN in every signature column. Requires best_profile and
    the six <archetype>_avg_bucket columns on df (raw, pre-encoding).
    """
    out = df.merge(comp_feats, left_on="competition_id", right_on="comp_id", how="left")
    out = out.merge(field_shares, left_on="competition_id", right_on="comp_id",
                    how="left", suffixes=("", "_fs"))
    out.drop(columns=[c for c in ("comp_id", "comp_id_fs") if c in out], inplace=True)

    bp = out["best_profile"].map({a: i for i, a in enumerate(ARCH)})
    has_bp = bp.notna().to_numpy()
    bp_idx = bp.fillna(0).astype(int).to_numpy()

    sig_mat = out[SIG].to_numpy(dtype=float)
    fs_mat = out[[f"field_share_{a}" for a in ARCH]].to_numpy(dtype=float)
    rows = np.arange(len(out))
    out["rider_sig_share"] = np.where(has_bp, sig_mat[rows, bp_idx], np.nan)
    out["rider_sig_vs_field"] = np.where(
        has_bp, sig_mat[rows, bp_idx] - fs_mat[rows, bp_idx], np.nan
    )
    ability = np.column_stack([(4.0 - out[ABILITY[a]].to_numpy(dtype=float)) for a in ARCH])
    out["rider_contest_fit"] = np.einsum("ij,ij->i", np.nan_to_num(sig_mat), ability)
    out.loc[np.isnan(sig_mat).all(axis=1), "rider_contest_fit"] = np.nan
    out.drop(columns=[f"field_share_{a}" for a in ARCH], inplace=True)
    return out


# ---------------------------------------------------------------------------
# Serving (future races): B4 from chosen reference comps + scraped field shares
# ---------------------------------------------------------------------------

def build_serving_signature_context(
    reference_comp_ids: List[int],
    field_features: Dict,
    db_path: Optional[Path] = None,
) -> Dict:
    """Signature context for ONE future one-day race.

    Mirrors the B4 rule with the user's chosen reference comps standing in
    for "prior editions": enrichment + wg_prop are computed fresh from the
    DB for those comps (as-of-then archetypes, same construction as
    training); the future race's field shares come from the scraped
    startlist counts (field_features as computed by compute_field_features).

    Returns {'sig': {col: value}} with the 8 comp-level columns
    (sig_<arch> x6, sig_wg_prop, sig_n_refs) plus
    {'field_shares': {arch: share}} for the rider interactions.
    References without a qualifying signature row (small field / null gaps)
    are skipped; cold start (no usable references) -> plain field shares,
    sig_wg_prop NaN, sig_n_refs 0.
    """
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH

    field_size = max(int(field_features.get("field_size") or 0), 1)
    shares = {
        arch: float(field_features.get(col, 0) or 0) / field_size
        for arch, col in FIELD_COUNT_COLS.items()
    }

    # Per-reference enrichment, computed exactly like training
    enrich_rows = []
    wg_props = []
    if reference_comp_ids:
        placeholders = ",".join("?" for _ in reference_comp_ids)
        query = f"""
            SELECT c.id AS comp_id, c.date,
                   r.fc_race_id, r.year,
                   rr.place, rr.time_gap,
                   COALESCE(s.best_profile, 'unknown') AS best_profile
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            JOIN rider_results rr ON rr.competition_id = c.id
            LEFT JOIN rider_competition_snapshots s
              ON s.competition_id = rr.competition_id AND s.rider_id = rr.rider_id
            WHERE c.id IN ({placeholders})
              AND c.competition_type = 'one_day'
        """
        with sqlite3.connect(db_path) as conn:
            res = pd.read_sql_query(query, conn, params=[int(c) for c in reference_comp_ids])
        if len(res):
            comp = _comp_signature_rows(res)
            if len(comp):
                ref_field = load_field_shares(db_path)
                comp = comp.merge(ref_field, on="comp_id", how="left")
                for _, r in comp.iterrows():
                    enrich_rows.append({
                        a: r[f"top{PRIMARY_K}_{a}"] - r[f"field_share_{a}"] for a in ARCH
                    })
                    wg_props.append(float(r["wg_prop"]))

    n_refs = len(enrich_rows)
    sig: Dict[str, float] = {"sig_n_refs": float(n_refs)}
    for a in ARCH:
        if n_refs:
            mean_enrich = float(np.nanmean([e[a] for e in enrich_rows]))
            sig[f"sig_{a}"] = float(np.clip(shares[a] + mean_enrich, 0, 1))
        else:
            sig[f"sig_{a}"] = shares[a]
    sig["sig_wg_prop"] = float(np.mean(wg_props)) if wg_props else np.nan

    return {"sig": sig, "field_shares": shares, "n_refs": n_refs}


def attach_serving_signature_features(
    df: pd.DataFrame,
    context: Optional[Dict],
) -> pd.DataFrame:
    """Attach signature columns to a future-race frame.

    context=None (stage / gc target, or signatures unavailable) -> all 11
    columns NaN, which is exactly the trained models' out-of-scope state.
    """
    out = df.copy()
    if context is None:
        for col in SIGNATURE_FEATURE_COLS:
            out[col] = np.nan
        return out

    sig = context["sig"]
    shares = context["field_shares"]
    for col in SIG + ["sig_wg_prop", "sig_n_refs"]:
        out[col] = sig[col]

    bp = out["best_profile"].map({a: i for i, a in enumerate(ARCH)})
    has_bp = bp.notna().to_numpy()
    bp_idx = bp.fillna(0).astype(int).to_numpy()
    sig_vec = np.array([sig[f"sig_{a}"] for a in ARCH], dtype=float)
    fs_vec = np.array([shares[a] for a in ARCH], dtype=float)

    out["rider_sig_share"] = np.where(has_bp, sig_vec[bp_idx], np.nan)
    out["rider_sig_vs_field"] = np.where(has_bp, sig_vec[bp_idx] - fs_vec[bp_idx], np.nan)
    ability = np.column_stack([(4.0 - out[ABILITY[a]].to_numpy(dtype=float)) for a in ARCH])
    sig_mat = np.tile(np.nan_to_num(sig_vec), (len(out), 1))
    out["rider_contest_fit"] = np.einsum("ij,ij->i", sig_mat, ability)
    if np.isnan(sig_vec).all():
        out["rider_contest_fit"] = np.nan
    return out
