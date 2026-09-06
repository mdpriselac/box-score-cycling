"""
Freeze the production day-type menu (v1) — the serve-time key vocabulary.

Fits ONE GMM (k=8, seed 42 — the gated menu8 config) on ALL labeled residual
stage days (junk-filtered), computes canonical signatures for every item
(8 residual analogs + bunch / gc_day / itt macro items), and emits:

  models/production/day_menu_v1.json   — frozen canonicals + GMM parameters
                                          + labeler config (serving reads
                                          this; NEVER refits)
  experiments/day_menu_v1_report_<ts>.json — rich per-item documentation
     (anchor matches, winner archetypes, exemplar races, GT share,
      TdF 2026 stage assignments under the frozen menu)

Data note: the signature table is the 2026-06-11 artifact (comps through
early June 2026). Post-Tour DB refresh + signature rebuild will produce a
v1.1 refit before the Vuelta; this freeze fixes item identity and the doc.

Usage:
    uv run python -m cycling_project.prediction_tools.experiments.build_day_menu_v1
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture

from cycling_project.prediction_tools.experiments.contest_signature_gate_cv import (
    load_signature_table,
)
from cycling_project.prediction_tools.experiments.day_menu_gate_cv import (
    ARCH,
    GC_TOP,
    ITT_SECONDS,
    SEED,
    SH15,
    UNKNOWN_JUNK,
    WIDE_BS_PROP,
    build_labels,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

K = 8
OUT_PROD = Path("models/production/day_menu_v1.json")
OUT_DIR = Path("experiments")
ANCHOR_MIN_EDITIONS = 4
TOP_CATS = None  # set after inspecting category values


def unit(m):
    m = np.asarray(m, float)
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    n[n == 0] = 1
    return m / n


def main():
    sig = load_signature_table()
    labels = build_labels(sig)
    lab = labels.copy()
    lab["date"] = pd.to_datetime(lab["date"])

    # ---- GMM on all junk-filtered residual days ----
    res = lab[(lab.day_class == "residual") & (lab.top15_unknown <= UNKNOWN_JUNK)]
    gm = GaussianMixture(K, covariance_type="full", n_init=5,
                         random_state=SEED, reg_covar=1e-5)
    gm.fit(res[SH15].values)
    res_all = lab[lab.day_class == "residual"]
    assign = pd.Series(gm.predict(res_all[SH15].values), index=res_all.index)
    lab["item"] = lab.day_class.where(lab.day_class != "residual", other=np.nan)
    lab.loc[res_all.index, "item"] = "res_" + assign.astype(str)

    canon = lab.groupby("item").agg(
        **{f"sig_{a}": (f"top15_{a}", "mean") for a in ARCH},
        sig_wg_prop=("wg_prop", "mean"), n_members=("comp_id", "size"))
    print("items:", {i: int(n) for i, n in canon.n_members.items()}, flush=True)

    # ---- anchor library: perennial one-days, multi-edition mean shares ----
    od = sig[sig.competition_type == "one_day"].copy()
    print("categories present:", od.category.value_counts().to_dict(), flush=True)
    ed = od.groupby("fc_race_id").agg(
        n_ed=("comp_id", "size"), name=("race_name", "last"),
        cat=("category", "last"),
        **{f"m_{a}": (f"top15_{a}", "mean") for a in ARCH})
    anchors = ed[ed.n_ed >= ANCHOR_MIN_EDITIONS]
    print(f"anchor library: {len(anchors)} races", flush=True)

    # ---- GT membership: races with >=15 stage comps in a year ----
    st = sig[sig.competition_type == "stage"]
    stage_counts = st.groupby(["fc_race_id", "year"]).comp_id.count()
    gt_keys = set(stage_counts[stage_counts >= 15].index)
    lab["is_gt"] = [
        (r, y) in gt_keys for r, y in zip(lab.fc_race_id, lab.year)]

    # ---- per-item documentation ----
    A = unit(anchors[[f"m_{a}" for a in ARCH]].values)
    report = {}
    for item, row in canon.iterrows():
        members = lab[lab.item == item]
        c = unit(row[[f"sig_{a}" for a in ARCH]].values.astype(float))
        cos = A @ c
        top_anchor_idx = np.argsort(cos)[::-1][:4]
        top_anchors = [
            {"race": str(anchors.iloc[i]["name"]),
             "cosine": round(float(cos[i]), 3),
             "category": str(anchors.iloc[i]["cat"])}
            for i in top_anchor_idx]
        warch = (members.winner_archetype.value_counts(normalize=True)
                 .round(3).to_dict())
        ex = members.sort_values(["year", "wg_size"], ascending=[False, True])
        exemplars = [
            {"race": str(r.race_name), "year": int(r.year),
             "stage": None if pd.isna(r.stage_number) else int(r.stage_number),
             "date": str(r.date)[:10], "winner_arch": str(r.winner_archetype),
             "wg_size": int(r.wg_size)}
            for r in ex.head(12).itertuples()]
        report[item] = {
            "n_members": int(row.n_members),
            "gt_share": round(float(members.is_gt.mean()), 3),
            "per_year": {int(k): int(v) for k, v in
                         members.year.value_counts().sort_index().items()},
            "canonical": {a: round(float(row[f"sig_{a}"]), 4) for a in ARCH},
            "wg_prop": round(float(row.sig_wg_prop), 4),
            "median_wg_size": int(members.wg_size.median()),
            "winner_archetypes": warch,
            "top_anchors": top_anchors,
            "exemplars": exemplars,
        }

    # ---- TdF 2026 stages under the frozen menu (survey validation vectors) ----
    tdf = {}
    survey = json.loads(Path(
        "experiments/day_type_menu_v0_20260808_172753.json").read_text())
    tv = survey.get("tdf_2026_validation", {})
    for stage_key, entry in (tv.items() if isinstance(tv, dict) else []):
        vec = None
        if isinstance(entry, dict):
            for k in ("top15_shares", "shares", "signature"):
                if k in entry:
                    vec = entry[k]
                    break
            if vec is None and all(a in entry for a in
                                   [f"top15_{x}" for x in ARCH]):
                vec = [entry[f"top15_{x}"] for x in ARCH]
        if vec is None:
            continue
        v = np.asarray([[float(x) for x in
                         (vec.values() if isinstance(vec, dict) else vec)][:6]])
        tdf[stage_key] = {
            "frozen_item": f"res_{int(gm.predict(v)[0])}",
            "note": entry.get("rule_label") or entry.get("label"),
        }
    if tdf:
        report["_tdf_2026_under_frozen_menu"] = tdf

    # ---- production artifact ----
    prod = {
        "version": "v1",
        "frozen_at": datetime.now().isoformat(),
        "data_through": str(lab.date.max())[:10],
        "signature_artifact": "selection_signatures_20260611_084046.csv.gz",
        "labeler": {"itt_seconds": ITT_SECONDS, "wide_bs_prop": WIDE_BS_PROP,
                    "gc_top": GC_TOP, "unknown_junk": UNKNOWN_JUNK},
        "k_residual": K, "seed": SEED,
        "arch": ARCH,
        "canonicals": {
            item: {**{f"sig_{a}": round(float(canon.loc[item, f"sig_{a}"]), 6)
                      for a in ARCH},
                   "sig_wg_prop": round(float(canon.loc[item, "sig_wg_prop"]), 6),
                   "n_members": int(canon.loc[item, "n_members"])}
            for item in canon.index},
        "gmm": {"means": gm.means_.tolist(),
                "covariances": gm.covariances_.tolist(),
                "weights": gm.weights_.tolist()},
    }
    OUT_PROD.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROD.write_text(json.dumps(prod, indent=2))
    from cycling_project.prediction_tools.production_release import write_release_manifest
    write_release_manifest(OUT_PROD.parent)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rep_path = OUT_DIR / f"day_menu_v1_report_{ts}.json"
    rep_path.write_text(json.dumps(report, indent=2))
    assign_path = OUT_DIR / f"day_menu_v1_assignments_{ts}.csv.gz"
    lab[["comp_id", "race_name", "year", "stage_number", "date", "day_class",
         "item", "is_gt", "wg_size", "winner_archetype"]].to_csv(
        assign_path, index=False, compression="gzip")

    print(f"\nSaved {OUT_PROD}", flush=True)
    print(f"Saved {rep_path}", flush=True)
    print(f"Saved {assign_path}", flush=True)
    for item in sorted(report):
        if item.startswith("_"):
            continue
        r = report[item]
        anch = ", ".join(f"{a['race']} {a['cosine']}" for a in r["top_anchors"][:3])
        wa = sorted(r["winner_archetypes"].items(), key=lambda kv: -kv[1])[:3]
        print(f"\n{item}: n={r['n_members']} gt={r['gt_share']:.0%} "
              f"med_wg={r['median_wg_size']}", flush=True)
        print(f"  canon: " + " ".join(f"{a}={r['canonical'][a]:.2f}"
                                      for a in ARCH), flush=True)
        print(f"  winners: " + " ".join(f"{k}={v:.0%}" for k, v in wa), flush=True)
        print(f"  anchors: {anch}", flush=True)
        print(f"  e.g.: " + "; ".join(
            f"{e['race']} {e['year']}" + (f" st{e['stage']}" if e['stage'] else "")
            for e in r["exemplars"][:4]), flush=True)


if __name__ == "__main__":
    main()
