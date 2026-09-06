"""
TdF 2026 prediction run — headless arm-C serving path (mirrors the web app).

GC scenario: references = last 5 TdF GC editions (2021-2025).
Six stage archetypes: references = real TdF stages 2021-2025 whose DB profile
scores embody the archetype. Startlist comes from cached_start_lists (r=17,
y=2026, scraped 2026-07-03).

Output: JSON in the scratchpad with per-scenario averaged profile, reference
metadata, and the fully priced field.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.dnf_predictor import load_production_dnf_head
from cycling_project.prediction_tools.future_race_loader import (
    assemble_prediction_df,
    attach_stack_features,
    average_race_profiles,
    compute_field_features,
    get_latest_rider_snapshots,
    get_reference_race_profile,
    load_production_rating_snapshots,
    match_riders_to_db,
    scrape_or_load_startlist,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.pricing_layer import apply_pricing_layer
from cycling_project.prediction_tools.win_calibration import load_corrector
from cycling_project.db_path import default_db_path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models" / "production"
DB_PATH = str(default_db_path())
OUT_PATH = Path(__file__).parent / "tdf_2026_predictions.json"

# scenario -> (reference competition_ids, representative stage_number)
SCENARIOS = {
    "gc": {
        "label": "General Classification",
        "refs": [2090, 1511, 301, 139, 9738],   # TdF GC 2021..2025
        "stage_number": None,
    },
    "flat_sprint": {
        "label": "Flat stage — big bunch sprint",
        "refs": [2095, 2097, 145, 150, 9741],   # '21 s4/s6, '24 s5/s10, '25 s3
        "stage_number": 5,
    },
    "reduced_sprint": {
        "label": "Reduced-group hilly sprint",
        "refs": [2101, 309, 320, 323, 9746],    # '21 s10, '23 s7/s18/s21, '25 s8
        "stage_number": 10,
    },
    "punchy": {
        "label": "Punchy hilly stage",
        "refs": [2093, 1518, 304, 142, 9742],   # '21 s2, '22 s6, '23 s2, '24 s2, '25 s4
        "stage_number": 2,
    },
    "mountain": {
        "label": "Mountain stage — summit finish",
        "refs": [2109, 307, 308, 154, 9748],    # '21 s18, '23 s5/s6, '24 s14, '25 s10
        "stage_number": 14,
    },
    "tt30": {
        "label": "Individual time trial (~30 min)",
        "refs": [2096, 318, 147, 9743],         # '21 s5, '23 s16, '24 s7, '25 s5
        "stage_number": 7,
    },
    "queen": {
        "label": "Queen stage — long, brutal mountains",
        "refs": [2102, 1530, 319, 159, 160],    # '21 s11, '22 s18, '23 s17, '24 s19/s20
        "stage_number": 19,
    },
}

PROFILE_KEYS = [
    "race_sprint_score", "race_mountain_score", "race_hilly_score",
    "race_rolling_score", "race_breakaway_score", "race_time_trial_score",
    "race_dominant_profile", "competition_type", "race_category",
    "winning_time", "abandon_ratio",
    "selection_metric_slope", "biggest_group_metric_slope",
    "variance_normalized_slope",
]

RESULT_COLS = [
    "rider_id", "rider_name", "predicted_rank", "expected_bucket",
    "is_contender", "predicted_time_gap",
    "prob_win", "prob_podium", "prob_top5", "prob_top15",
    "lambdarank_win_p", "blend_win_p",
    "dnf_p", "dnf_adj_win_p", "dnf_adj_podium_p", "dnf_adj_top5_p",
    "dnf_adj_top15_p", "odds_win",
    "contested_rating", "contested_rating_n",
]


def main():
    print("Loading production registry + serving artifacts...", flush=True)
    registry = ModelRegistry(str(MODEL_DIR))
    bucket_pred, time_gap_pred, race_ranker, lambdarank_pred = registry.load_with_ranker(
        ranking_method="ensemble"
    )
    win_corrector = load_corrector(MODEL_DIR)
    dnf_bundle = load_production_dnf_head(MODEL_DIR)
    rating_snaps = load_production_rating_snapshots()
    print(f"  corrector={win_corrector and win_corrector.get('method')}, "
          f"dnf={'ok' if dnf_bundle else 'ABSENT'}, "
          f"elo_snaps={len(rating_snaps) if rating_snaps is not None else 'ABSENT'}",
          flush=True)

    teams, from_cache = scrape_or_load_startlist(17, 2026, db_path=DB_PATH)
    n_riders = sum(len(t.riders) for t in teams)
    assert from_cache, "startlist should come from cache"
    print(f"Startlist: {len(teams)} teams, {n_riders} riders (cached)", flush=True)

    matched, unmatched = match_riders_to_db(teams, DB_PATH)
    print(f"Matched {len(matched)} riders to DB ({len(unmatched)} unmatched: "
          f"{[u for u in unmatched][:6]}...)", flush=True)

    snapshots = get_latest_rider_snapshots(matched["rider_id"].tolist(), DB_PATH)
    field_features = compute_field_features(snapshots)
    team_map = matched.set_index("rider_id")["team_name"].to_dict()
    print(f"Snapshots: {len(snapshots)} riders", flush=True)

    out = {
        "generated_asof": None,   # filled by caller if needed
        "startlist": {"teams": len(teams), "riders": n_riders,
                      "matched": len(matched),
                      "unmatched": [str(u) for u in unmatched]},
        "scenarios": {},
    }

    for key, spec in SCENARIOS.items():
        print(f"\n=== {key}: {spec['label']} ===", flush=True)
        profiles = [get_reference_race_profile(c, DB_PATH) for c in spec["refs"]]
        avg_profile = average_race_profiles(profiles)
        ref_meta = [
            {"competition_id": int(c),
             "name": p["competition_name"],
             "date": p["competition_date"]}
            for c, p in zip(spec["refs"], profiles)
        ]
        print("  refs: " + "; ".join(r["name"] for r in ref_meta), flush=True)
        print("  avg profile: " + ", ".join(
            f"{k.replace('race_', '').replace('_score', '')}="
            f"{avg_profile[k]:.2f}"
            for k in ("race_sprint_score", "race_mountain_score",
                      "race_hilly_score", "race_rolling_score",
                      "race_breakaway_score", "race_time_trial_score")
            if avg_profile.get(k) is not None), flush=True)

        form_status = {}
        pred_df = assemble_prediction_df(
            snapshots, matched, field_features, avg_profile,
            form_status=form_status,
        )
        print(f"  form re-aging: {form_status.get('mode')} "
              f"asof={form_status.get('asof_date')} "
              f"err={form_status.get('error')}", flush=True)

        pred_df = attach_stack_features(
            pred_df, time_gap_pred, lambdarank_pred,
            rating_snapshots=rating_snaps, signature_context=None,
        )
        lr_book = float(pred_df["oof_lambdarank_win_p"].sum())
        elo_cov = float(pred_df["contested_rating"].notna().mean())
        print(f"  LR book={lr_book:.4f}, Elo coverage={elo_cov:.0%}", flush=True)

        result = race_ranker.predict_race(pred_df, return_details=True)
        # merge LR win p onto result (the app does this via _attach_lambdarank;
        # values identical to the stack feature by construction)
        lr_map = dict(zip(pred_df["rider_id"].astype(int),
                          pred_df["oof_lambdarank_win_p"].astype(float)))
        result["lambdarank_win_p"] = result["rider_id"].astype(int).map(lr_map)
        # merge Elo columns (the app does this via _attach_elo)
        for col in ("contested_rating", "contested_rating_n"):
            elo_map = dict(zip(pred_df["rider_id"].astype(int), pred_df[col]))
            result[col] = result["rider_id"].astype(int).map(elo_map)

        priced, warnings = apply_pricing_layer(
            result, pred_df, avg_profile,
            win_corrector=win_corrector, dnf_bundle=dnf_bundle,
            stage_number=spec["stage_number"], db_path=DB_PATH,
        )
        for w in warnings:
            print(f"  [warn] {w}", flush=True)

        cols = [c for c in RESULT_COLS if c in priced.columns]
        tab = priced.sort_values("predicted_rank")[cols].copy()
        tab["team_name"] = tab["rider_id"].map(team_map)
        # numpy -> plain python for JSON
        records = json.loads(tab.to_json(orient="records"))

        out["scenarios"][key] = {
            "label": spec["label"],
            "stage_number": spec["stage_number"],
            "references": ref_meta,
            "avg_profile": {k: avg_profile.get(k) for k in PROFILE_KEYS},
            "mc_win_book": float(priced["prob_win"].sum()),
            "form_status": form_status,
            "riders": records,
        }

        top = tab.head(8)
        print("  top-8: " + " | ".join(
            f"{r.rider_name} bl={100*r.blend_win_p:.1f}%"
            for r in top.itertuples()), flush=True)

    OUT_PATH.write_text(json.dumps(out, indent=1))
    print(f"\nWrote {OUT_PATH} ({OUT_PATH.stat().st_size/1024:.0f} KB)", flush=True)


if __name__ == "__main__":
    main()
