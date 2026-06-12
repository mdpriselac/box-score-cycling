"""
Contest archetype library (step 4 design validation).

Clusters historical contesting signatures (top-10 archetype shares, 6 known
dims) into K canonical contest archetypes, then reports the three numbers the
training design depends on:

  1. The library itself: canonical profiles, sizes, shape descriptors,
     comp-type split, nearest example races.
  2. Quantization fidelity: cosine(actual signature, assigned canonical
     profile) — how much signal survives hard assignment. Ceiling for
     archetype-mediated transfer.
  3. Leak delta: how predictable the archetype assignment is from the
     race-level features production ALREADY uses (6 profile scores +
     gradient slopes + null markers + shape scalars). High accuracy =>
     the assignment adds little outcome information beyond the status quo.

Also computes, per archetype, P(rider archetype | finishing position 1..10)
— the sampling distribution a randomized contest-sequence generator would
draw from (positional inputs must be sampled, never observed).

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.contest_archetype_library
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from cycling_project.prediction_tools.experiments.front_local_race_typing import DB_PATH
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

OUT_DIR = Path(__file__).parents[3] / "experiments"
SEED = 42
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial"]
SHARE = [f"top10_{a}" for a in ARCH]
K_RANGE = range(4, 13)
TEST_YEAR_START = 2024

EXISTING_RACE_FEATURES_SQL = """
    SELECT g.competition_id AS comp_id,
           f.race_sprint_score, f.race_mountain_score, f.race_hilly_score,
           f.race_rolling_score, f.race_breakaway_score, f.race_time_trial_score,
           g.variance_normalized_slope, g.skewness_normalized_slope,
           g.kurtosis_normalized_slope, g.gini_coefficient_slope,
           g.clumpiness_score_slope, g.selection_metric_slope,
           g.biggest_group_metric_slope, g.nth_percentile_gap_5_slope,
           g.nth_percentile_gap_25_slope, g.nth_percentile_gap_50_slope,
           g.kurtosis_null_percentile, g.lowest_valid_percentile,
           g.percentile_coverage_ratio, g.total_finishers
    FROM race_feature_gradients g
    LEFT JOIN competition_field_features f ON f.competition_id = g.competition_id
"""


def load_signatures() -> pd.DataFrame:
    f = sorted(OUT_DIR.glob("selection_signatures_*.csv.gz"))[-1]
    comp = pd.read_csv(f)
    logger.info("Loaded %s (%d comps)", f.name, len(comp))
    return comp


def fit_library(comp: pd.DataFrame) -> pd.DataFrame:
    X = comp[SHARE].to_numpy()
    best, best_bic, bics = None, np.inf, {}
    for k in K_RANGE:
        gm = GaussianMixture(n_components=k, covariance_type="diag", random_state=SEED, n_init=5)
        gm.fit(X)
        bic = gm.bic(X)
        bics[k] = round(bic)
        if bic < best_bic:
            best, best_bic = gm, bic
    comp = comp.copy()
    comp["archetype"] = best.predict(X)
    logger.info("BIC by k: %s -> chose k=%d", bics, best.n_components)
    comp.attrs["k_chosen"] = best.n_components
    comp.attrs["bics"] = bics
    return comp


def describe_library(comp: pd.DataFrame) -> Dict:
    out = {}
    centroids = comp.groupby("archetype")[SHARE].mean()
    for k, row in centroids.iterrows():
        sub = comp[comp["archetype"] == k]
        # nearest examples to centroid
        X = sub[SHARE].to_numpy()
        c = row.to_numpy()
        d = np.linalg.norm(X - c, axis=1)
        ex = sub.iloc[np.argsort(d)[:5]]
        label_parts = [(a, row[f"top10_{a}"]) for a in ARCH]
        label_parts.sort(key=lambda t: -t[1])
        out[int(k)] = {
            "profile": {a: round(float(row[f"top10_{a}"]), 3) for a in ARCH},
            "auto_label": " + ".join(f"{a} {v:.0%}" for a, v in label_parts[:2]),
            "share_of_comps": round(len(sub) / len(comp), 3),
            "pct_stage": round(float((sub["competition_type"] == "stage").mean()), 2),
            "mean_wg_prop": round(float(sub["wg_prop"].mean()), 3),
            "mean_wg_size": round(float(sub["wg_size"].mean()), 1),
            "coarse_mix": sub["coarse"].value_counts(normalize=True).round(2).to_dict(),
            "examples": [f"{r['race_name']} {r['year']}"
                         + (f" st{int(r['stage_number'])}" if pd.notna(r["stage_number"]) else "")
                         for _, r in ex.iterrows()],
        }
    return out


def quantization_fidelity(comp: pd.DataFrame) -> Dict:
    centroids = comp.groupby("archetype")[SHARE].mean()
    C = centroids.loc[comp["archetype"]].to_numpy()
    Y = comp[SHARE].to_numpy()
    yn = Y / np.clip(np.linalg.norm(Y, axis=1, keepdims=True), 1e-9, None)
    cn = C / np.clip(np.linalg.norm(C, axis=1, keepdims=True), 1e-9, None)
    cos = np.sum(yn * cn, axis=1)
    out = {"overall_mean_cosine": round(float(cos.mean()), 4)}
    for ct in ["stage", "one_day"]:
        m = (comp["competition_type"] == ct).to_numpy()
        out[f"{ct}_mean_cosine"] = round(float(cos[m].mean()), 4)
    return out


def leak_delta(comp: pd.DataFrame) -> Dict:
    with sqlite3.connect(DB_PATH) as conn:
        feats = pd.read_sql_query(EXISTING_RACE_FEATURES_SQL, conn)
    m = comp.merge(feats, on="comp_id", how="inner")
    fc = [c for c in feats.columns if c != "comp_id"]
    tr = m["year"] < TEST_YEAR_START
    te = m["year"] >= TEST_YEAR_START
    k = comp.attrs["k_chosen"]
    clf = lgb.LGBMClassifier(
        objective="multiclass", num_class=k, n_estimators=300, learning_rate=0.05,
        num_leaves=31, min_child_samples=20, random_state=SEED, verbose=-1,
    )
    clf.fit(m.loc[tr, fc], m.loc[tr, "archetype"])
    pred = clf.predict(m.loc[te, fc])
    acc = float((pred == m.loc[te, "archetype"]).mean())
    majority = float(m.loc[te, "archetype"].value_counts(normalize=True).iloc[0])
    return {
        "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "accuracy_from_existing_race_features": round(acc, 3),
        "majority_baseline": round(majority, 3),
        "test_years": f"{TEST_YEAR_START}+",
    }


def positional_distributions(comp: pd.DataFrame) -> Dict:
    """P(rider archetype | finishing position 1..10, contest archetype)."""
    with sqlite3.connect(DB_PATH) as conn:
        riders = pd.read_sql_query(
            """SELECT rr.competition_id AS comp_id, rr.place,
                      COALESCE(s.best_profile, 'unknown') AS best_profile
               FROM rider_results rr
               LEFT JOIN rider_competition_snapshots s
                 ON s.competition_id = rr.competition_id AND s.rider_id = rr.rider_id
               WHERE rr.place <= 10""",
            conn,
        )
    m = riders.merge(comp[["comp_id", "archetype"]], on="comp_id", how="inner")
    out = {}
    for k, g in m.groupby("archetype"):
        mat = (
            g.pivot_table(index="place", columns="best_profile", values="comp_id", aggfunc="count")
            .reindex(index=range(1, 11))
            .fillna(0)
        )
        mat = mat.div(mat.sum(axis=1), axis=0).round(3)
        out[int(k)] = {int(p): {a: float(v) for a, v in row.items() if v >= 0.01}
                       for p, row in mat.iterrows()}
    return out


def main():
    comp = load_signatures()
    comp = fit_library(comp)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_competitions": len(comp),
        "k_chosen": comp.attrs["k_chosen"],
        "bic_by_k": comp.attrs["bics"],
        "library": describe_library(comp),
        "quantization_fidelity": quantization_fidelity(comp),
        "leak_delta": leak_delta(comp),
        "positional_distributions": positional_distributions(comp),
    }
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    (OUT_DIR / f"contest_archetype_library_{ts}.json").write_text(json.dumps(summary, indent=2, default=str))
    comp[["comp_id", "archetype"]].to_csv(OUT_DIR / f"contest_archetype_assignments_{ts}.csv.gz",
                                          index=False, compression="gzip")
    print(json.dumps({k: v for k, v in summary.items() if k != "positional_distributions"},
                     indent=2, default=str))
    logger.info("Wrote contest_archetype_library_%s.json (incl. positional distributions)", ts)


if __name__ == "__main__":
    main()
