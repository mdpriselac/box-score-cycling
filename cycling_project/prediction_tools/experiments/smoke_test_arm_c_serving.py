"""
Smoke test — arm-C serving path end-to-end on cached startlists (no scraping).

Replicates the web app's prediction path headlessly for:
  1. a ONE-DAY race (Liège-Bastogne-Liège 2026, fc_race_id=11) — signature
     features must attach (coverage > 0), Elo coverage > 90%, pricing layer
     (corrector + blend + DNF) fully populated;
  2. a STAGE-RACE stage (Tour Auvergne - Rhône-Alpes 2026, fc_race_id=15,
     stage 1) — signature columns must be all-NaN (out-of-scope state) while
     everything else still prices.

Checks:
  - features attach (sig coverage > 0 for the one-day; Elo coverage > 90%)
  - probabilities sane (win books ~1 pre-DNF-adjustment; LR book == 1)
  - DNF-adjusted <= unadjusted for podium/top5/top15 (win renormalized:
    book preserved instead)
  - no NaN leakage into displayed numbers
  - prediction_log rows insert cleanly (in-memory DB)

Usage:
    PYTHONUNBUFFERED=1 uv run python -m cycling_project.prediction_tools.experiments.smoke_test_arm_c_serving
"""

import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from cycling_project.prediction_tools.contest_signature_features import (
    SIGNATURE_FEATURE_COLS,
    build_serving_signature_context,
)
from cycling_project.prediction_tools.contested_rating import RATING_FEATURE_COLS
from cycling_project.prediction_tools.dnf_predictor import load_production_dnf_head
from cycling_project.prediction_tools.future_race_loader import (
    assemble_prediction_df,
    attach_stack_features,
    compute_field_features,
    get_default_references,
    get_latest_rider_snapshots,
    get_reference_race_profile,
    average_race_profiles,
    load_production_rating_snapshots,
    match_riders_to_db,
    scrape_or_load_startlist,
)
from cycling_project.prediction_tools.model_registry import ModelRegistry
from cycling_project.prediction_tools.pricing_layer import apply_pricing_layer
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    ensure_schema,
    log_predictions,
)
from cycling_project.prediction_tools.win_calibration import load_corrector

PROJECT_ROOT = Path(__file__).parents[3]
MODEL_DIR = PROJECT_ROOT / "models" / "production"
DB_PATH = str(
    Path(__file__).parents[2] / "webscrape_tools" / "database" / "database" / "cycling_races.db"
)

CHECKS = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""),
          flush=True)


def run_case(fc_race_id: int, year: int, comp_type: str, stage_number,
             registry_bits, expect_sig: bool):
    bucket_pred, time_gap_pred, race_ranker, lambdarank_pred = registry_bits["ranker"]
    win_corrector = registry_bits["win_corrector"]
    dnf_bundle = registry_bits["dnf_bundle"]
    rating_snaps = registry_bits["rating_snaps"]

    label = f"r={fc_race_id} y={year} type={comp_type}" + (
        f" stage={stage_number}" if stage_number else "")
    print(f"\n{'=' * 70}\nCASE {label}\n{'=' * 70}", flush=True)

    teams, from_cache = scrape_or_load_startlist(fc_race_id, year, db_path=DB_PATH)
    check("startlist from cache (no scraping)", from_cache,
          f"{sum(len(t.riders) for t in teams)} riders")
    matched, unmatched = match_riders_to_db(teams, DB_PATH)
    check("riders matched", len(matched) > 50,
          f"{len(matched)} matched / {len(unmatched)} unmatched")

    snapshots = get_latest_rider_snapshots(matched["rider_id"].tolist(), DB_PATH)
    field_features = compute_field_features(snapshots)

    refs = get_default_references(
        fc_race_id, competition_type=comp_type, stage_number=stage_number,
        exclude_year=year, max_results=5, db_path=DB_PATH,
    )
    check("reference editions found", len(refs) >= 1, f"{len(refs)} references")
    reference_ids = [int(c) for c in refs["competition_id"]]

    sig_context = None
    if comp_type == "one_day":
        sig_context = build_serving_signature_context(reference_ids, field_features, DB_PATH)
        check("signature context built", sig_context is not None,
              f"n_refs={sig_context['n_refs']}")

    profiles = [get_reference_race_profile(c, DB_PATH) for c in reference_ids]
    avg_profile = average_race_profiles(profiles)

    pred_df = assemble_prediction_df(snapshots, matched, field_features, avg_profile)
    pred_df = attach_stack_features(
        pred_df, time_gap_pred, lambdarank_pred,
        rating_snapshots=rating_snaps, signature_context=sig_context,
    )

    # ---- feature attachment checks ----
    if expect_sig:
        sig_cov = pred_df["sig_sprint"].notna().mean()
        check("sig coverage > 0 (one-day)", sig_cov > 0, f"coverage={sig_cov:.0%}, "
              f"sig_n_refs={pred_df['sig_n_refs'].iloc[0]}")
        check("rider sig interactions present",
              pred_df["rider_contest_fit"].notna().mean() > 0.5,
              f"contest_fit coverage={pred_df['rider_contest_fit'].notna().mean():.0%}")
    else:
        all_nan = pred_df[SIGNATURE_FEATURE_COLS].isna().all().all()
        check("sig columns all NaN (stage target)", all_nan)

    elo_cov = pred_df["contested_rating"].notna().mean()
    check("Elo coverage > 90%", elo_cov > 0.90, f"coverage={elo_cov:.1%}")
    check("oof meta features populated",
          pred_df["oof_time_gap_pred"].notna().all()
          and pred_df["oof_lambdarank_win_p"].notna().all())
    lr_book = float(pred_df["oof_lambdarank_win_p"].sum())
    check("LambdaRank win book == 1", abs(lr_book - 1.0) < 1e-6, f"sum={lr_book:.6f}")

    # ---- predictions + pricing ----
    result = race_ranker.predict_race(pred_df, return_details=True)
    raw_win = result[["rider_id", "prob_win", "is_contender"]].copy()

    priced, warnings = apply_pricing_layer(
        result, pred_df, avg_profile,
        win_corrector=win_corrector, dnf_bundle=dnf_bundle,
        stage_number=stage_number, db_path=DB_PATH,
    )
    for w in warnings:
        print(f"  [warn] {w}", flush=True)
    check("pricing layer ran without degradation warnings", len(warnings) == 0)

    # The multiclass cascade has NO book-sum constraint by construction
    # (per-rider conditional softmax; the LambdaRank head — asserted == 1
    # above — is the normalized book). Sanity-bound only.
    mc_book = float(priced["prob_win"].sum())
    check("mc win book within sanity bounds (pre-DNF)", 0.2 < mc_book < 3.0,
          f"sum={mc_book:.4f} (unconstrained by design)")

    if win_corrector and win_corrector.get("method") != "identity":
        merged = raw_win.merge(
            priced[["rider_id", "prob_win"]], on="rider_id", suffixes=("_raw", "_cor")
        )
        cont_rows = merged[raw_win.set_index("rider_id").loc[merged["rider_id"], "is_contender"].values]
        changed = (cont_rows["prob_win_raw"] != cont_rows["prob_win_cor"]).mean()
        check("win corrector applied to contender rows", changed > 0.9,
              f"method={win_corrector['method']}, rows changed={changed:.0%}")

    blend_book = float(priced["blend_win_p"].sum())
    check("blend book preserves mc book", abs(blend_book - mc_book) < 1e-6,
          f"blend sum={blend_book:.4f}")

    dnf_ok = priced["dnf_p"].notna().all()
    check("dnf_p populated for every rider", dnf_ok,
          f"mean={priced['dnf_p'].astype(float).mean():.3f}")
    for m in ("podium", "top5", "top15"):
        le = (priced[f"dnf_adj_{m}_p"].astype(float)
              <= priced[f"prob_{m}"].astype(float) + 1e-12).all()
        check(f"dnf-adjusted <= unadjusted ({m})", bool(le))
    adj_book = float(priced["dnf_adj_win_p"].astype(float).sum())
    check("dnf-adjusted win book preserved (renormalized)",
          abs(adj_book - mc_book) < 1e-6, f"adj sum={adj_book:.4f}")

    display_cols = [
        "prob_win", "prob_podium", "prob_top5", "prob_top15",
        "lambdarank_win_p", "lambdarank_podium_p", "blend_win_p", "dnf_p",
        "dnf_adj_win_p", "dnf_adj_podium_p", "dnf_adj_top5_p", "dnf_adj_top15_p",
        "expected_bucket", "predicted_rank", "odds_win",
    ]
    present = [c for c in display_cols if c in priced.columns]
    nan_cols = [c for c in present if priced[c].isna().any()]
    check("no NaN leakage into displayed numbers", not nan_cols,
          f"NaN in: {nan_cols}" if nan_cols else f"{len(present)} display cols clean")

    # ---- prediction_log row compatibility (in-memory DB) ----
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE competitions (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE riders (id INTEGER PRIMARY KEY)")
    ensure_schema(conn)
    rows = [
        PredictionLogRow(
            fc_race_id=str(fc_race_id), year=year, rider_id=int(r["rider_id"]),
            stage_number=stage_number,
            multiclass_win_p=r.get("prob_win"),
            multiclass_podium_p=r.get("prob_podium"),
            multiclass_top5_p=r.get("prob_top5"),
            multiclass_top15_p=r.get("prob_top15"),
            lambdarank_win_p=r.get("lambdarank_win_p"),
            dnf_p=r.get("dnf_p"),
            dnf_adj_win_p=r.get("dnf_adj_win_p"),
            dnf_adj_podium_p=r.get("dnf_adj_podium_p"),
            dnf_adj_top5_p=r.get("dnf_adj_top5_p"),
            dnf_adj_top15_p=r.get("dnf_adj_top15_p"),
            blend_win_p=r.get("blend_win_p"),
        )
        for _, r in priced.iterrows()
    ]
    n = log_predictions(conn, rows)
    got = conn.execute(
        "SELECT COUNT(*), SUM(dnf_p IS NOT NULL), SUM(blend_win_p IS NOT NULL) "
        "FROM prediction_log"
    ).fetchone()
    check("prediction_log insert", n == len(priced) and got[0] == n,
          f"{n} rows, dnf_p filled={got[1]}, blend filled={got[2]}")
    conn.close()

    # ---- top-5 preview ----
    cols = ["predicted_rank", "rider_name", "prob_win", "blend_win_p", "dnf_p",
            "dnf_adj_win_p", "lambdarank_win_p"]
    head = priced.sort_values("predicted_rank")[
        [c for c in cols if c in priced.columns]
    ].head(5)
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
        print("\n  Top-5 preview:\n" + head.to_string(index=False), flush=True)


def main():
    print("Loading production registry + arm-C serving artifacts...", flush=True)
    registry = ModelRegistry(str(MODEL_DIR))
    bucket_pred, time_gap_pred, race_ranker, lambdarank_pred = registry.load_with_ranker(
        ranking_method="ensemble"
    )
    registry_bits = {
        "ranker": (bucket_pred, time_gap_pred, race_ranker, lambdarank_pred),
        "win_corrector": load_corrector(MODEL_DIR),
        "dnf_bundle": load_production_dnf_head(MODEL_DIR),
        "rating_snaps": load_production_rating_snapshots(),
    }
    print(f"  win_corrector: {registry_bits['win_corrector'] and registry_bits['win_corrector'].get('method')}")
    print(f"  dnf head: {'loaded' if registry_bits['dnf_bundle'] else 'ABSENT'}")
    print(f"  rating snapshots: "
          f"{len(registry_bits['rating_snaps']) if registry_bits['rating_snaps'] is not None else 'ABSENT'}")

    # One-day: Liège-Bastogne-Liège 2026 (cached startlist)
    run_case(11, 2026, "one_day", None, registry_bits, expect_sig=True)
    # Stage race: Tour Auvergne - Rhône-Alpes 2026, stage 1 (cached startlist)
    run_case(15, 2026, "stage", 1, registry_bits, expect_sig=False)

    n_fail = sum(1 for _, ok, _ in CHECKS if not ok)
    print(f"\n{'=' * 70}\nSMOKE TEST: {len(CHECKS) - n_fail}/{len(CHECKS)} checks passed",
          flush=True)
    if n_fail:
        for name, ok, detail in CHECKS:
            if not ok:
                print(f"  FAILED: {name} {detail}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
