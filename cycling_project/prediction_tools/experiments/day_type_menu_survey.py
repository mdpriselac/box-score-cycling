"""Day-type menu survey (step 1 of day_type_menu_plan.md).

Maps the space of non-GC, non-bunch-sprint stage days ("residual" days) in
contesting-composition space, matches them against a library of perennial
one-day anchor races, clusters them into candidate menu items, and validates
the pipeline against the settled TdF 2026 corpus.

Inputs (all pre-existing):
  - experiments/selection_signatures_20260611_084046.csv.gz   (June artifacts)
  - experiments/contest_archetype_assignments_20260611_093323.csv.gz
  - cycling_races.db (GC ranks, rider best_profile snapshots)
  - performance_eval/tour-de-france-2026/results/               (validation)

Outputs (timestamped, in experiments/):
  - day_type_menu_assignments_<ts>.csv.gz  per-stage-comp class + cluster + anchor
  - day_type_menu_v0_<ts>.json             menu items (canonical values) + survey stats

Run:  uv run python -m cycling_project.prediction_tools.experiments.day_type_menu_survey
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
EXP = ROOT / "experiments"
DB = ROOT / "cycling_project/webscrape_tools/database/database/cycling_races.db"
TDF = ROOT / "performance_eval/tour-de-france-2026"

SIG_CSV = EXP / "selection_signatures_20260611_084046.csv.gz"
ASSIGN_CSV = EXP / "contest_archetype_assignments_20260611_093323.csv.gz"

SEED = 0
SH = ["top15_sprint", "top15_mountain", "top15_hilly", "top15_rolling",
      "top15_breakaway", "top15_time_trial", "top15_unknown"]
ARCH = ["sprint", "mountain", "hilly", "rolling", "breakaway", "time_trial", "unknown"]
SHAPE_COLS = ["wg_prop", "winner_margin", "chase_gap", "frac_30s", "top15_spread"]

POOL_OUT = {"mass_sprint", "bunch_sprint", "itt_like"}
GC_TOP = 10            # "won by a GC guy" = winner's final GC rank <= 10
WIDE_BS_PROP = 0.20    # bunch_sprint days with wg_prop below this join residual_wide
K_RANGE = range(2, 13)
K_CAP = 8              # interpretability cap on cluster count
GT_PAT = r"Tour de France|Giro d'Italia|Vuelta a Espa"
SNAPSHOT_CUTOFF = "2026-07-01"  # pre-Tour best_profile for validation rows


def unit(m: np.ndarray) -> np.ndarray:
    m = np.asarray(m, float)
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1
    return m / n


def rule_label(wg_size: int, groups_top15: int) -> str:
    # mirrors front_local_race_typing.rule_label (WG_MASS/BUNCH/REDUCED/SMALL)
    if groups_top15 >= 13:
        return "itt_like"
    if wg_size >= 40:
        return "mass_sprint"
    if wg_size >= 20:
        return "bunch_sprint"
    if wg_size >= 8:
        return "reduced_sprint"
    if wg_size >= 4:
        return "small_group"
    if wg_size >= 2:
        return "tiny_group"
    return "solo"


def build_stage_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    sig = pd.read_csv(SIG_CSV)
    asg = pd.read_csv(ASSIGN_CSV).rename(columns={"archetype": "june_library_cluster"})
    sig = sig.merge(asg, on="comp_id", how="left")
    st = sig[sig.competition_type == "stage"].copy()
    od = sig[sig.competition_type == "one_day"].copy()

    con = sqlite3.connect(DB)
    comps = pd.read_sql(
        "SELECT id, race_id, competition_type FROM competitions", con)
    gc_comps = comps[comps.competition_type == "gc"][["id", "race_id"]]
    need = set(st.comp_id) | set(gc_comps.id)
    con.execute("CREATE TEMP TABLE need(id INTEGER PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO need VALUES (?)",
                    [(int(i),) for i in need])
    rr = pd.read_sql(
        """SELECT r.competition_id, r.rider_id, r.place FROM rider_results r
           JOIN need n ON n.id = r.competition_id""", con)
    con.close()
    rr["place_n"] = pd.to_numeric(rr.place, errors="coerce")

    gcr = rr.merge(gc_comps.rename(columns={"id": "gc_comp_id"}),
                   left_on="competition_id", right_on="gc_comp_id")
    gc_lookup = gcr.set_index(["race_id", "rider_id"]).place_n

    st = st.merge(comps[["id", "race_id"]], left_on="comp_id",
                  right_on="id", how="left").drop(columns=["id"])
    srr = rr[rr.competition_id.isin(set(st.comp_id))]
    winners = srr[srr.place_n == 1].groupby("competition_id").rider_id.first()

    def gc_rank(race_id, rider_id):
        try:
            return gc_lookup.loc[(race_id, rider_id)]
        except KeyError:
            return np.nan

    st["winner_rider_id"] = st.comp_id.map(winners)
    st["winner_gc_rank"] = [
        gc_rank(r, w) if pd.notna(w) else np.nan
        for r, w in zip(st.race_id, st.winner_rider_id)]

    st["is_gt"] = st.race_name.str.contains(GT_PAT, case=False, na=False, regex=True)
    st["in_pool"] = ~st.rule_type.isin(POOL_OUT)
    st["residual"] = st.in_pool & ~(st.winner_gc_rank <= GC_TOP)
    st["res_wide"] = st.residual | (
        (st.rule_type == "bunch_sprint") & (st.wg_prop < WIDE_BS_PROP)
        & ~(st.winner_gc_rank <= GC_TOP))
    st["day_class"] = np.select(
        [st.rule_type.isin({"mass_sprint", "bunch_sprint"}) & ~st.res_wide,
         st.rule_type == "itt_like",
         st.in_pool & (st.winner_gc_rank <= GC_TOP)],
        ["bunch_day", "itt_like", "gc_day"], default="residual")
    logger.info("stages %d | pool %d | residual %d (wide %d) | GT residual %d",
                len(st), st.in_pool.sum(), st.residual.sum(),
                st.res_wide.sum(), (st.residual & st.is_gt).sum())
    return st, od


def build_anchors(od: pd.DataFrame, min_editions: int = 4) -> pd.DataFrame:
    odp = od[od.category.isin(["wt", "pro"])]
    keep = odp.groupby("fc_race_id")["year"].transform("size") >= min_editions
    rows = odp[keep]
    anchors = rows.groupby("fc_race_id").agg(
        name=("race_name", lambda s: s.iloc[-1]), n_ed=("year", "size"),
        cat=("category", lambda s: s.mode().iloc[0]),
        wg_prop=("wg_prop", "mean"),
        **{c: (c, "mean") for c in SH}).reset_index()
    logger.info("anchor library: %d races / %d editions", len(anchors), keep.sum())
    return anchors


def match_to_anchors(df: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    A = unit(anchors[SH].values)
    X = unit(df[SH].values)
    C = X @ A.T
    best = C.argmax(1)
    out = df[["comp_id"]].copy()
    out["best_anchor"] = anchors.name.values[best]
    out["best_anchor_fc_id"] = anchors.fc_race_id.values[best]
    out["best_cos"] = C.max(1)
    out["second_cos"] = np.sort(C, 1)[:, -2]
    return out


def cluster_residual(st: pd.DataFrame) -> tuple[pd.Series, GaussianMixture, int]:
    res = st[st.residual]
    X = res[SH].values
    bics = {}
    models = {}
    for k in K_RANGE:
        g = GaussianMixture(k, covariance_type="full", n_init=5,
                            random_state=SEED, reg_covar=1e-5).fit(X)
        bics[k] = g.bic(X)
        models[k] = g
    k_best = min(bics, key=bics.get)
    k_use = min(k_best, K_CAP)
    gm = models[k_use]
    logger.info("GMM BIC best k=%d, using k=%d", k_best, k_use)
    # assign every pool day (GC days included) for downstream label use
    pool = st[st.in_pool | st.res_wide]
    labels = pd.Series(gm.predict(pool[SH].values), index=pool.index)
    return labels, gm, k_use


def tdf_validation(gm: GaussianMixture, anchors: pd.DataFrame) -> pd.DataFrame:
    con = sqlite3.connect(DB)
    riders = pd.read_sql(
        "SELECT id, CAST(fc_rider_id AS INTEGER) fc_rider_id FROM riders", con)
    frames = {}
    for s in range(2, 22):
        f = TDF / f"results/stage_{s:02d}/results.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f)
        df["place_n"] = pd.to_numeric(df.place, errors="coerce")
        df = df[df.place_n.notna()].sort_values("place_n").reset_index(drop=True)
        df["gap"] = pd.to_numeric(df.gap, errors="coerce").ffill().fillna(0)
        df["rider_id"] = pd.to_numeric(df.rider_id, errors="coerce").astype("Int64")
        frames[s] = df
    fc_ids = sorted(set(pd.concat([d.rider_id for d in frames.values()]).dropna().astype(int)))
    riders = riders[riders.fc_rider_id.isin(fc_ids)]
    ids = ",".join(map(str, riders.id))
    snaps = pd.read_sql(
        f"""SELECT s.rider_id, s.best_profile, c.date
            FROM rider_competition_snapshots s
            JOIN competitions c ON c.id = s.competition_id
            WHERE s.rider_id IN ({ids}) AND c.date < '{SNAPSHOT_CUTOFF}'""", con)
    con.close()
    latest = snaps.sort_values("date").groupby("rider_id").best_profile.last()
    fc2prof = pd.Series(riders.id.map(latest).values, index=riders.fc_rider_id.values)

    standings = pd.read_csv(TDF / "results/race_page/standings_2026-07-26.csv")
    standings["rider_id"] = pd.to_numeric(standings.rider_id, errors="coerce").astype("Int64")
    gc_rank = pd.to_numeric(standings.set_index("rider_id")["place"], errors="coerce")

    A = unit(anchors[SH].values)
    rows = []
    for s, df in sorted(frames.items()):
        g = df.gap.values
        newg = np.concatenate([[0], (np.diff(g) > 1.0).cumsum()])
        wg = int((newg == 0).sum())
        g15 = int(len(np.unique(newg[:15])))
        profs = df.head(15).rider_id.map(fc2prof).fillna("unknown")
        shares = np.array([(profs == a).mean() for a in ARCH])
        rt = rule_label(wg, g15)
        wfc = int(df.iloc[0].rider_id)
        wgc = gc_rank.get(wfc, np.nan)
        in_pool = rt not in POOL_OUT
        cos = (shares / (np.linalg.norm(shares) or 1)) @ A.T
        order = np.argsort(-cos)
        rows.append(dict(
            stage=s, rule=rt, wg_size=wg,
            winner=df.iloc[0]["name"], winner_gc=float(wgc) if pd.notna(wgc) else np.nan,
            in_pool=in_pool, residual=bool(in_pool and not (wgc <= GC_TOP)),
            cluster=int(gm.predict(shares.reshape(1, -1))[0]) if in_pool else -1,
            anchor1=anchors.name.values[order[0]], cos1=round(float(cos[order[0]]), 3),
            anchor2=anchors.name.values[order[1]], cos2=round(float(cos[order[1]]), 3),
            **{f"share_{a}": round(float(sh), 3) for a, sh in zip(ARCH, shares)}))
    return pd.DataFrame(rows)


def main() -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    st, od = build_stage_table()
    anchors = build_anchors(od)
    labels, gm, k_use = cluster_residual(st)
    st["menu_cluster"] = labels
    match = match_to_anchors(st, anchors)
    st = st.merge(match, on="comp_id", how="left")

    res = st[st.residual]
    menu = []
    for c in sorted(res.menu_cluster.dropna().unique()):
        d = res[res.menu_cluster == c]
        cent = d[SH].mean().values
        ca = unit(cent.reshape(1, -1)) @ unit(anchors[SH].values).T
        top3 = np.argsort(-ca[0])[:3]
        menu.append({
            "item": int(c), "n": int(len(d)), "n_gt": int(d.is_gt.sum()),
            "canonical_shares": {a: round(float(v), 4) for a, v in
                                 zip([s.replace("top15_", "") for s in SH], cent)},
            "canonical_shape": {k: round(float(d[k].median()), 3) for k in SHAPE_COLS},
            "winner_archetypes": d.winner_archetype.value_counts(normalize=True)
                                  .round(3).to_dict(),
            "anchors": [{"name": anchors.name.values[i],
                         "cos": round(float(ca[0][i]), 3)} for i in top3],
            "gt_examples": [f"{r.race_name} {r.year} st{int(r.stage_number)}"
                            for r in d[d.is_gt].nlargest(3, "year").itertuples()],
        })

    val = tdf_validation(gm, anchors)

    per_ed = st[st.is_gt].groupby(["race_name", "year"]).res_wide.sum()
    summary = {
        "generated_at": ts,
        "n_stage_comps": int(len(st)),
        "n_pool": int(st.in_pool.sum()),
        "n_residual": int(st.residual.sum()),
        "n_residual_wide": int(st.res_wide.sum()),
        "n_residual_gt": int((st.residual & st.is_gt).sum()),
        "residual_wide_per_gt_edition_mean": round(float(per_ed.mean()), 2),
        "anchor_matching": {
            "residual_best_cos_median": round(float(
                st[st.residual].best_cos.median()), 3),
            "residual_ge_080": round(float((st[st.residual].best_cos >= 0.8).mean()), 3),
            "match_margin_median": round(float(
                (st[st.residual].best_cos - st[st.residual].second_cos).median()), 3),
            "note": "raw best-cos is non-discriminative (dense anchor space); "
                    "menu lives at cluster level, anchors are display labels",
        },
        "k_bic_range": {str(k): 0 for k in []},  # BIC detail logged, not persisted
        "k_used": k_use,
        "menu_items": menu,
    }

    out_csv = EXP / f"day_type_menu_assignments_{ts}.csv.gz"
    keep_cols = ["comp_id", "race_name", "year", "stage_number", "category",
                 "is_gt", "rule_type", "day_class", "in_pool", "residual",
                 "res_wide", "menu_cluster", "winner_gc_rank", "winner_archetype",
                 "best_anchor", "best_cos", "june_library_cluster"] + SH + SHAPE_COLS
    st[keep_cols].to_csv(out_csv, index=False, compression="gzip")
    out_json = EXP / f"day_type_menu_v0_{ts}.json"
    with open(out_json, "w") as f:
        json.dump({"summary": summary,
                   "tdf_2026_validation": val.to_dict(orient="records")}, f, indent=2)
    logger.info("wrote %s and %s", out_csv.name, out_json.name)
    print(val.to_string(index=False))


if __name__ == "__main__":
    main()
