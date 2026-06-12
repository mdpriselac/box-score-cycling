"""
Selection signatures: archetype mix of the contesting group, per historical competition.

Step 1 of the race-character program (descriptive layer): for every stage /
one-day competition, compute the archetype composition of the riders who
finished at the front ("rider type that finishes high"), using as-of-then
rider archetypes (rider_competition_snapshots.best_profile — snapshot taken
before the competition, no hindsight).

Step 2 (validation): is WHO contests more stable year-over-year than HOW BIG
the front group is? Benchmark: ICC(wg_prop) = 0.33 from the front-local
typing analysis. Computed on the identical one-day >= 4 editions subset.

Outputs:
  - experiments/selection_signatures_<ts>.csv.gz   per-comp signature table
  - experiments/selection_signatures_<ts>.json     summary + stability analysis

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.selection_signatures
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.experiments.front_local_race_typing import (
    DB_PATH,
    GROUP_THRESHOLD_S,
    MIN_FINISHERS,
    OUT_DIR,
    START_DATE,
    comp_features,
    icc_oneway,
    rule_label,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

SEED = 42
ARCHETYPES = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial", "unknown"]
TOP_KS = [5, 10, 15]
PRIMARY_K = 10
N_PERMUTATIONS = 200

COARSE_MAP = {
    "mass_sprint": "sprint", "bunch_sprint": "sprint",
    "reduced_sprint": "selective", "small_group": "selective", "tiny_group": "selective",
    "solo": "solo", "itt_like": "itt",
}

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


def load_results() -> pd.DataFrame:
    query = """
        SELECT c.id AS comp_id, c.competition_type, c.date, c.stage_number,
               r.fc_race_id, r.name AS race_name, r.year, r.category,
               rr.place, rr.time_gap,
               COALESCE(s.best_profile, 'unknown') AS best_profile
        FROM competitions c
        JOIN races r ON c.race_id = r.id
        JOIN rider_results rr ON rr.competition_id = c.id
        LEFT JOIN rider_competition_snapshots s
          ON s.competition_id = rr.competition_id AND s.rider_id = rr.rider_id
        WHERE c.competition_type IN ('one_day', 'stage')
          AND c.date IS NOT NULL AND c.date >= ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(START_DATE,))
    logger.info("Loaded %d result rows, %d comps", len(df), df["comp_id"].nunique())
    return df


def load_field_shares() -> pd.DataFrame:
    cols = ", ".join(FIELD_COUNT_COLS.values())
    with sqlite3.connect(DB_PATH) as conn:
        ff = pd.read_sql_query(
            f"SELECT competition_id AS comp_id, field_size, {cols} FROM competition_field_features",
            conn,
        )
    for arch, col in FIELD_COUNT_COLS.items():
        ff[f"field_share_{arch}"] = ff[col] / ff["field_size"].clip(lower=1)
    return ff[["comp_id"] + [f"field_share_{a}" for a in ARCHETYPES]]


def build_signatures(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    meta_cols = ["competition_type", "date", "stage_number", "fc_race_id", "race_name", "year", "category"]
    for comp_id, g in df.groupby("comp_id", sort=False):
        gaps = g["time_gap"].to_numpy(dtype=float)
        if np.isnan(gaps).mean() > 0.05:
            continue
        valid_gaps = np.sort(gaps[~np.isnan(gaps)])
        if len(valid_gaps) < MIN_FINISHERS:
            continue
        valid_gaps = valid_gaps - valid_gaps[0]

        feats = comp_features(valid_gaps)
        feats["comp_id"] = comp_id
        first = g.iloc[0]
        for c in meta_cols:
            feats[c] = first[c]

        by_place = g.sort_values("place")
        feats["winner_archetype"] = by_place["best_profile"].iloc[0]
        for k in TOP_KS:
            top = by_place["best_profile"].iloc[:k]
            shares = top.value_counts(normalize=True)
            for arch in ARCHETYPES:
                feats[f"top{k}_{arch}"] = float(shares.get(arch, 0.0))
        rows.append(feats)

    comp = pd.DataFrame(rows)
    comp["rule_type"] = comp.apply(rule_label, axis=1)
    comp["coarse"] = comp["rule_type"].map(COARSE_MAP)
    share_cols = [f"top{PRIMARY_K}_{a}" for a in ARCHETYPES]
    known = [c for c in share_cols if not c.endswith("unknown")]
    comp["dominant_archetype"] = comp[known].idxmax(axis=1).str.replace(f"top{PRIMARY_K}_", "", regex=False)
    logger.info("Built %d competition signatures", len(comp))
    return comp


def add_enrichment(comp: pd.DataFrame, field: pd.DataFrame) -> pd.DataFrame:
    comp = comp.merge(field, on="comp_id", how="left")
    for arch in ARCHETYPES:
        comp[f"enrich_{arch}"] = comp[f"top{PRIMARY_K}_{arch}"] - comp[f"field_share_{arch}"]
    return comp


def within_race_cosine(comp: pd.DataFrame, cols, race_ids: pd.Series) -> float:
    """Mean pairwise cosine similarity of signature vectors within the same race entity."""
    X = comp[cols].to_numpy(dtype=float)
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    X = X / np.clip(norms, 1e-9, None)
    sims = []
    for _, idx in pd.Series(range(len(comp))).groupby(race_ids.to_numpy()):
        ii = idx.to_numpy()
        if len(ii) < 2:
            continue
        S = X[ii] @ X[ii].T
        iu = np.triu_indices(len(ii), k=1)
        sims.append(S[iu].mean())
    return float(np.mean(sims))


def stability_analysis(comp: pd.DataFrame) -> Dict:
    out = {}
    oneday = comp[comp["competition_type"] == "one_day"]
    eds = oneday.groupby("fc_race_id").filter(lambda g: g["year"].nunique() >= 4)
    out["one_day_races_4plus_editions"] = int(eds["fc_race_id"].nunique())
    out["n_editions"] = int(len(eds))

    # Benchmark on the SAME subset
    out["icc_wg_prop_benchmark"] = round(icc_oneway(eds["wg_prop"], eds["fc_race_id"]), 3)

    # Per-dimension ICC: raw top-K shares and field-relative enrichment
    icc_shares, icc_enrich = {}, {}
    for arch in ARCHETYPES:
        icc_shares[arch] = round(icc_oneway(eds[f"top{PRIMARY_K}_{arch}"], eds["fc_race_id"]), 3)
        icc_enrich[arch] = round(icc_oneway(eds[f"enrich_{arch}"], eds["fc_race_id"]), 3)
    out[f"icc_top{PRIMARY_K}_shares"] = icc_shares
    out["icc_enrichment"] = icc_enrich

    # Multivariate: within-race cosine of the 6 known-archetype share vector vs permutation null
    cols = [f"top{PRIMARY_K}_{a}" for a in ARCHETYPES if a != "unknown"]
    obs = within_race_cosine(eds, cols, eds["fc_race_id"])
    rng = np.random.default_rng(SEED)
    nulls = []
    ids = eds["fc_race_id"].to_numpy()
    for _ in range(N_PERMUTATIONS):
        nulls.append(within_race_cosine(eds, cols, pd.Series(rng.permutation(ids))))
    nulls = np.array(nulls)
    out["signature_cosine_within_race"] = round(obs, 4)
    out["signature_cosine_null_mean"] = round(float(nulls.mean()), 4)
    out["signature_cosine_null_sd"] = round(float(nulls.std()), 4)
    out["signature_cosine_z"] = round(float((obs - nulls.mean()) / max(nulls.std(), 1e-9)), 1)

    # Winner archetype agreement
    def modal(s):
        return s.value_counts(normalize=True).iloc[0]
    agree = eds.groupby("fc_race_id")["winner_archetype"].apply(modal).mean()
    sh = eds.copy()
    sh["fc_race_id"] = rng.permutation(sh["fc_race_id"].to_numpy())
    agree_null = sh.groupby("fc_race_id")["winner_archetype"].apply(modal).mean()
    out["winner_archetype_modal_agreement"] = round(float(agree), 3)
    out["winner_archetype_modal_null"] = round(float(agree_null), 3)

    # Dominant contesting archetype agreement
    agree_d = eds.groupby("fc_race_id")["dominant_archetype"].apply(modal).mean()
    sh2 = eds.copy()
    sh2["fc_race_id"] = rng.permutation(sh2["fc_race_id"].to_numpy())
    agree_d_null = sh2.groupby("fc_race_id")["dominant_archetype"].apply(modal).mean()
    out["dominant_archetype_modal_agreement"] = round(float(agree_d), 3)
    out["dominant_archetype_modal_null"] = round(float(agree_d_null), 3)

    # Forward prediction: last edition vs mean of priors, per key dimension + full vector
    fwd = {}
    for dim in [f"top{PRIMARY_K}_sprint", f"top{PRIMARY_K}_mountain", "wg_prop"]:
        rows = []
        for rid, g in oneday.groupby("fc_race_id"):
            g = g.sort_values("year")
            if len(g) < 3:
                continue
            v = g[dim].to_numpy()
            for i in range(2, len(v)):
                rows.append({"y": v[i], "last": v[i - 1], "mean_prior": v[:i].mean()})
        p = pd.DataFrame(rows)
        fwd[dim] = {
            "n": len(p),
            "corr_last": round(float(p["y"].corr(p["last"])), 3),
            "corr_mean_priors": round(float(p["y"].corr(p["mean_prior"])), 3),
        }
    out["forward_prediction"] = fwd

    # Examples: most/least stable by within-race cosine
    per_race = {}
    for rid, g in eds.groupby("fc_race_id"):
        if len(g) >= 4:
            per_race[rid] = (
                within_race_cosine(g, cols, g["fc_race_id"]),
                g["race_name"].iloc[0],
            )
    ranked = sorted(per_race.values())
    out["least_stable_signatures"] = [f"{n}: {c:.3f}" for c, n in ranked[:8]]
    out["most_stable_signatures"] = [f"{n}: {c:.3f}" for c, n in ranked[-8:]]
    return out


def main():
    df = load_results()
    comp = build_signatures(df)
    comp = add_enrichment(comp, load_field_shares())

    # Validity: mean contesting shares by coarse shape class
    share_cols = [f"top{PRIMARY_K}_{a}" for a in ARCHETYPES]
    by_class = comp.groupby("coarse")[share_cols].mean().round(3)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_competitions": len(comp),
        "unknown_share_in_top10": round(float(comp[f"top{PRIMARY_K}_unknown"].mean()), 4),
        "mean_top10_shares_by_coarse_class": {
            str(k): v for k, v in by_class.to_dict(orient="index").items()
        },
        "coarse_x_dominant_archetype": {
            str(k): v for k, v in comp.groupby(["coarse", "dominant_archetype"]).size().to_dict().items()
        },
        "stability": stability_analysis(comp),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (OUT_DIR / f"selection_signatures_{ts}.json").write_text(json.dumps(summary, indent=2, default=str))
    comp.to_csv(OUT_DIR / f"selection_signatures_{ts}.csv.gz", index=False, compression="gzip")
    print(json.dumps(summary, indent=2, default=str))
    logger.info("Wrote selection_signatures_%s.{json,csv.gz}", ts)


if __name__ == "__main__":
    main()
