"""
Front-local race typing from finishing-time group structure.

Read-only analysis. Computes exact front-of-sheet structure per competition
directly from rider_results time gaps (same 1.0s consecutive-gap grouping as
engineered_metrics.identify_groups), then:

  1. Builds interpretable front-local typing features (winner-group size,
     chase gap, top-15 splintering, ...). Moment statistics (kurtosis, skew,
     gini) are deliberately excluded: they are structurally incomputable
     inside same-time blobs.
  2. Applies a rule-based taxonomy v0 (winner-group size x chase-gap
     decisiveness) and contrasts it with an unsupervised GMM over the same
     features — testing whether the front-local lens splits the one-blob
     (~80%) outcome of the slope-based clustering.
  3. Cross-checks against race_feature_gradients markers:
     kurtosis_null_percentile should track true blob depth;
     variance_zero_percentile is expected to be degenerate (overwrite-without-
     break bug in populate_all_gradients_safe.find_data_quality_indicators).
  4. Measures year-over-year stability of front-local type for one-day races
     (same fc_race_id across editions) vs stage competitions, including
     same-stage-number agreement for stage races.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.front_local_race_typing
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

DB_PATH = Path(__file__).parents[2] / "webscrape_tools" / "database" / "database" / "cycling_races.db"
OUT_DIR = Path(__file__).parents[3] / "experiments"

START_DATE = "2016-01-01"
MIN_FINISHERS = 30
GROUP_THRESHOLD_S = 1.0  # matches engineered_metrics.identify_groups
SEED = 42

# Rule taxonomy v0 thresholds (winner-group size, absolute riders)
WG_MASS = 40
WG_BUNCH = 20
WG_REDUCED = 8
WG_SMALL = 4
# Chase-gap decisiveness (seconds from winner group to next rider)
CHASE_TIGHT = 15.0
CHASE_CLEAR = 60.0


def load_results() -> pd.DataFrame:
    query = """
        SELECT c.id AS comp_id, c.competition_type, c.date, c.stage_number,
               r.fc_race_id, r.name AS race_name, r.year, r.category,
               rr.place, rr.time_gap
        FROM competitions c
        JOIN races r ON c.race_id = r.id
        JOIN rider_results rr ON rr.competition_id = c.id
        WHERE c.competition_type IN ('one_day', 'stage')
          AND c.date IS NOT NULL AND c.date >= ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(query, conn, params=(START_DATE,))
    logger.info("Loaded %d result rows across %d competitions", len(df), df["comp_id"].nunique())
    return df


def group_sizes_from_gaps(gaps: np.ndarray) -> List[int]:
    """Group consecutive finishers whose gap difference <= threshold (sheet order)."""
    sizes = []
    current = 1
    for i in range(1, len(gaps)):
        if gaps[i] - gaps[i - 1] <= GROUP_THRESHOLD_S:
            current += 1
        else:
            sizes.append(current)
            current = 1
    sizes.append(current)
    return sizes


def comp_features(gaps: np.ndarray) -> Dict:
    """Front-local structure features for one competition. gaps sorted ascending, winner=0."""
    n = len(gaps)
    sizes = group_sizes_from_gaps(gaps)
    wg = sizes[0]  # winner group size
    # gap from winner group to next finisher (inf-like sentinel when whole field is one group)
    chase_gap = float(gaps[wg]) if wg < n else 0.0
    single_group = wg == n
    top15 = gaps[: min(15, n)]
    top15_sizes = group_sizes_from_gaps(top15)
    return {
        "n_finishers": n,
        "wg_size": wg,
        "wg_prop": wg / n,
        "winner_margin": float(gaps[1]) if n > 1 else 0.0,
        "chase_gap": chase_gap,
        "single_group": single_group,
        "top15_spread": float(top15[-1]),
        "groups_top15": len(top15_sizes),
        "n_groups": len(sizes),
        "frac_5s": float(np.mean(gaps <= 5.0)),
        "frac_30s": float(np.mean(gaps <= 30.0)),
        "frac_120s": float(np.mean(gaps <= 120.0)),
    }


def rule_label(row: pd.Series) -> str:
    # ITT-like: nearly everyone in the front 15 time-separated
    if row["groups_top15"] >= 13:
        return "itt_like"
    if row["wg_size"] >= WG_MASS:
        return "mass_sprint"
    if row["wg_size"] >= WG_BUNCH:
        return "bunch_sprint"
    if row["wg_size"] >= WG_REDUCED:
        return "reduced_sprint"
    if row["wg_size"] >= WG_SMALL:
        return "small_group"
    if row["wg_size"] >= 2:
        return "tiny_group"
    return "solo"


def chase_label(row: pd.Series) -> str:
    if row["single_group"]:
        return "no_split"
    if row["chase_gap"] < CHASE_TIGHT:
        return "tight"
    if row["chase_gap"] < CHASE_CLEAR:
        return "clear"
    return "decisive"


def build_comp_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    skipped_null, skipped_small = 0, 0
    meta_cols = ["competition_type", "date", "stage_number", "fc_race_id", "race_name", "year", "category"]
    for comp_id, g in df.groupby("comp_id", sort=False):
        gaps = g["time_gap"].to_numpy(dtype=float)
        if np.isnan(gaps).mean() > 0.05:
            skipped_null += 1
            continue
        gaps = np.sort(gaps[~np.isnan(gaps)])
        if len(gaps) < MIN_FINISHERS:
            skipped_small += 1
            continue
        gaps = gaps - gaps[0]
        feats = comp_features(gaps)
        feats["comp_id"] = comp_id
        first = g.iloc[0]
        for c in meta_cols:
            feats[c] = first[c]
        rows.append(feats)
    comp = pd.DataFrame(rows)
    comp["rule_type"] = comp.apply(rule_label, axis=1)
    comp["chase_type"] = comp.apply(chase_label, axis=1)
    logger.info(
        "Built %d competitions (skipped %d null-gap, %d small-field)",
        len(comp), skipped_null, skipped_small,
    )
    return comp


def run_gmm(comp: pd.DataFrame) -> pd.DataFrame:
    feats = pd.DataFrame({
        "log_wg": np.log1p(comp["wg_size"]),
        "wg_prop": comp["wg_prop"],
        "log_margin": np.log1p(comp["winner_margin"]),
        "log_chase": np.log1p(comp["chase_gap"]),
        "log_top15_spread": np.log1p(comp["top15_spread"]),
        "groups_top15": comp["groups_top15"],
        "frac_30s": comp["frac_30s"],
    })
    X = StandardScaler().fit_transform(feats)
    best, best_bic, bics = None, np.inf, {}
    for k in range(3, 11):
        gm = GaussianMixture(n_components=k, covariance_type="diag", random_state=SEED, n_init=3)
        gm.fit(X)
        bic = gm.bic(X)
        bics[k] = round(bic)
        if bic < best_bic:
            best, best_bic = gm, bic
    comp = comp.copy()
    comp["gmm_cluster"] = best.predict(X)
    logger.info("GMM BIC by k: %s -> chose k=%d", bics, best.n_components)
    return comp


def cross_check_markers(comp: pd.DataFrame) -> Dict:
    with sqlite3.connect(DB_PATH) as conn:
        markers = pd.read_sql_query(
            """SELECT competition_id AS comp_id, variance_zero_percentile,
                      kurtosis_null_percentile, lowest_valid_percentile
               FROM race_feature_gradients""",
            conn,
        )
    m = comp.merge(markers, on="comp_id", how="inner")
    out = {"n_joined": len(m)}

    # kurtosis_null_percentile should track true blob depth (wg_prop*100)
    has_k = m["kurtosis_null_percentile"].notna()
    if has_k.sum() > 100:
        sub = m[has_k]
        out["kurtosis_marker_vs_wg_prop_corr"] = round(
            float(np.corrcoef(sub["kurtosis_null_percentile"], sub["wg_prop"] * 100)[0, 1]), 3
        )
        out["kurtosis_marker_n"] = int(has_k.sum())

    # variance_zero bug: non-null values should equal lowest_valid_percentile ~always
    has_v = m["variance_zero_percentile"].notna()
    if has_v.sum() > 0:
        sub = m[has_v]
        out["variance_zero_n"] = int(has_v.sum())
        out["variance_zero_equals_lowest_valid_pct"] = round(
            float((sub["variance_zero_percentile"] == sub["lowest_valid_percentile"]).mean()), 4
        )
    return out


def icc_oneway(values: pd.Series, groups: pd.Series) -> float:
    """One-way ANOVA ICC(1): between-race variance share of total."""
    d = pd.DataFrame({"v": values, "g": groups}).dropna()
    counts = d.groupby("g")["v"].count()
    d = d[d["g"].isin(counts[counts >= 2].index)]
    if d["g"].nunique() < 3:
        return float("nan")
    grand = d["v"].mean()
    group_means = d.groupby("g")["v"].mean()
    n_per = d.groupby("g")["v"].count()
    k = len(group_means)
    n_total = len(d)
    ss_between = float((n_per * (group_means - grand) ** 2).sum())
    ss_within = float(((d["v"] - d["g"].map(group_means)) ** 2).sum())
    ms_between = ss_between / (k - 1)
    ms_within = ss_within / (n_total - k)
    n_bar = (n_total - (n_per ** 2).sum() / n_total) / (k - 1)
    return float((ms_between - ms_within) / (ms_between + (n_bar - 1) * ms_within))


def stability_analysis(comp: pd.DataFrame) -> Dict:
    out = {}
    oneday = comp[comp["competition_type"] == "one_day"]
    eds = oneday.groupby("fc_race_id").filter(lambda g: g["year"].nunique() >= 4)

    # Modal type agreement per race entity
    agree = eds.groupby("fc_race_id").apply(
        lambda g: g["rule_type"].value_counts(normalize=True).iloc[0], include_groups=False
    )
    out["one_day_races_with_4plus_editions"] = int(eds["fc_race_id"].nunique())
    out["one_day_modal_type_share_mean"] = round(float(agree.mean()), 3)
    out["one_day_modal_type_share_median"] = round(float(agree.median()), 3)

    # Continuous stability of winner-group proportion
    out["one_day_icc_wg_prop"] = round(icc_oneway(eds["wg_prop"], eds["fc_race_id"]), 3)
    out["one_day_icc_log_chase"] = round(
        icc_oneway(np.log1p(eds["chase_gap"]), eds["fc_race_id"]), 3
    )

    # Baseline: shuffle race identity -> expected agreement by chance
    rng = np.random.default_rng(SEED)
    shuffled = eds.copy()
    shuffled["fc_race_id"] = rng.permutation(shuffled["fc_race_id"].to_numpy())
    agree_null = shuffled.groupby("fc_race_id").apply(
        lambda g: g["rule_type"].value_counts(normalize=True).iloc[0], include_groups=False
    )
    out["one_day_modal_type_share_null"] = round(float(agree_null.mean()), 3)

    # Examples: most/least stable one-days (by modal share, then name)
    names = eds.groupby("fc_race_id")["race_name"].first()
    ex = pd.DataFrame({"agree": agree, "name": names}).sort_values("agree")
    out["least_stable_examples"] = [
        f"{r['name']}: {r['agree']:.2f}" for _, r in ex.head(8).iterrows()
    ]
    out["most_stable_examples"] = [
        f"{r['name']}: {r['agree']:.2f}" for _, r in ex.tail(8).iterrows()
    ]

    # Stage races: same stage_number across years — expect low agreement
    stages = comp[(comp["competition_type"] == "stage") & comp["stage_number"].notna()]
    slots = stages.groupby(["fc_race_id", "stage_number"]).filter(lambda g: g["year"].nunique() >= 4)
    if len(slots):
        slot_agree = slots.groupby(["fc_race_id", "stage_number"]).apply(
            lambda g: g["rule_type"].value_counts(normalize=True).iloc[0], include_groups=False
        )
        out["stage_slot_groups_4plus_years"] = int(len(slot_agree))
        out["stage_slot_modal_type_share_mean"] = round(float(slot_agree.mean()), 3)
        out["stage_slot_icc_wg_prop"] = round(
            icc_oneway(slots["wg_prop"], slots["fc_race_id"].astype(str) + "_s" + slots["stage_number"].astype(str)), 3
        )
    return out


def main():
    df = load_results()
    comp = build_comp_table(df)
    comp = run_gmm(comp)

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "start_date": START_DATE,
        "min_finishers": MIN_FINISHERS,
        "n_competitions": len(comp),
        "by_competition_type": comp["competition_type"].value_counts().to_dict(),
        "rule_type_distribution": (comp["rule_type"].value_counts(normalize=True).round(4)).to_dict(),
        "rule_type_counts": comp["rule_type"].value_counts().to_dict(),
        "chase_type_distribution": (comp["chase_type"].value_counts(normalize=True).round(4)).to_dict(),
        "rule_x_chase": {
            str(k): v for k, v in comp.groupby(["rule_type", "chase_type"]).size().to_dict().items()
        },
        "gmm_cluster_sizes": comp["gmm_cluster"].value_counts(normalize=True).round(4).to_dict(),
        "gmm_x_rule": {
            str(k): v for k, v in comp.groupby(["gmm_cluster", "rule_type"]).size().to_dict().items()
        },
        "largest_gmm_cluster_share": round(float(comp["gmm_cluster"].value_counts(normalize=True).iloc[0]), 4),
        "marker_cross_check": cross_check_markers(comp),
        "stability": stability_analysis(comp),
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = OUT_DIR / f"front_local_race_typing_{ts}.json"
    out_json.write_text(json.dumps(summary, indent=2, default=str))
    out_csv = OUT_DIR / f"front_local_comp_features_{ts}.csv.gz"
    comp.to_csv(out_csv, index=False, compression="gzip")

    print(json.dumps(summary, indent=2, default=str))
    logger.info("Wrote %s and %s", out_json, out_csv)


if __name__ == "__main__":
    main()
