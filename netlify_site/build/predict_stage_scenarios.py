"""
Config-driven TdF 2026 stage prediction runner — headless arm-C serving path.

Reads a per-stage scenario config (performance_eval/tour-de-france-2026/
predictions/stage_NN/scenarios.json), runs each scenario, writes one JSON per
scenario next to the config, and logs every run to prediction_log with a
tagged model_version (same fields as the web app writes).

    uv run python netlify_site/build/predict_stage_scenarios.py \
        performance_eval/tour-de-france-2026/predictions/stage_02/scenarios.json \
        [--only key1,key2] [--no-log]

Scenario spec (in the config's "scenarios" map):
    refs:      [competition_ids]  -> averaged real reference profile
    base_refs + scores:           -> synthetic: terrain scores overridden on
                                     the averaged base_refs profile (short
                                     keys: sprint, mountain, hilly, rolling,
                                     breakaway, time_trial); gradients and
                                     metadata inherited from the base average.
    tag:       suffix appended to model_version in prediction_log — rerunning
               a scenario logs a NEW opinion under the same tag, so use --only
               to avoid duplicate logging of unchanged scenarios.
    day_key:   optional {menu_item: weight} map (e.g. {"res_2": 0.6,
               "res_4": 0.4}; see day_menu_v1_reference.md). When present and
               the day-menu channel is installed, the kernod bucket model
               ranks the board (pool membership + display order; weighted
               sets mix at the RANKING-SCORE level) and riders it promotes
               into the top 15 are priced by the contender model like any
               pool member. Prices always come from the untouched production
               heads. A config-root day_key applies to every scenario that
               doesn't set its own. Logged in the output JSON — the morning
               scenarios.json entry is the immutable tier-3 key archive.

Within-race state (mirrors the web app): stage targets >= 2 attach the live
race state (completed stages via DB/cache/scrape) to the MAIN models; a
config with "target": "gc" keeps the main heads pre-race and feeds the state
to the separate GC outlook head instead (gc_outlook_* columns in the JSON and
prediction_log, stage_number logged NULL).
"""

import argparse
import json
import sqlite3
import sys
import unicodedata
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from cycling_project.prediction_tools import day_menu as day_menu_mod
from cycling_project.prediction_tools.dnf_predictor import load_production_dnf_head
from cycling_project.prediction_tools.gc_outlook import GCOutlookHead
from cycling_project.prediction_tools.live_race_state import (
    attach_race_state,
    fetch_live_race_state,
)
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
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    log_predictions,
    resolve_competition_id,
)
from cycling_project.prediction_tools.pricing_layer import apply_pricing_layer
from cycling_project.prediction_tools.win_calibration import load_corrector

MODEL_DIR = PROJECT_ROOT / "models" / "production"
DB_PATH = str(PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
              / "database" / "cycling_races.db")
ODDS_ROOT = PROJECT_ROOT / "performance_eval" / "tour-de-france-2026" / "odds"

SCORE_KEY_MAP = {
    "sprint": "race_sprint_score", "mountain": "race_mountain_score",
    "hilly": "race_hilly_score", "rolling": "race_rolling_score",
    "breakaway": "race_breakaway_score", "time_trial": "race_time_trial_score",
}

RESULT_COLS = [
    "rider_id", "rider_name", "predicted_rank", "expected_bucket",
    "daymenu_rank", "daymenu_score", "in_daymenu_pool",
    "is_contender", "predicted_time_gap",
    "prob_win", "prob_podium", "prob_top5", "prob_top15",
    "lambdarank_win_p", "blend_win_p",
    "dnf_p", "dnf_adj_win_p", "dnf_adj_podium_p", "dnf_adj_top5_p",
    "dnf_adj_top15_p", "odds_win",
    "contested_rating", "contested_rating_n",
]


def norm_name(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace("-", " ").replace(".", " ")
    return " ".join(sorted(s.split()))


def load_book(config):
    """Rider -> win-market outcome from the archived Kambi capture."""
    odds_file = ODDS_ROOT / config["odds_capture"]
    if not odds_file.exists():
        return {}, None
    mk = json.loads(odds_file.read_text())
    for bo in mk.get(str(config["event_id"]), {}).get("betoffers", []):
        if bo["criterion"] == "Winnaar" and bo["bet_offer_type"] == "Winnaar":
            return {norm_name(o["name"]): o for o in bo["outcomes"]}, odds_file.name
    return {}, odds_file.name


def find_book(book, rider_name):
    k = norm_name(rider_name)
    if k in book:
        return book[k]
    bt = set(k.split())
    cands = [v for bk, v in book.items()
             if set(bk.split()) <= bt or bt <= set(bk.split())]
    return cands[0] if len(cands) == 1 else None


def build_profile(spec, db_path):
    """Averaged real profile (refs) or synthetic override (base_refs+scores)."""
    ref_ids = spec.get("refs") or spec["base_refs"]
    profiles = [get_reference_race_profile(c, db_path) for c in ref_ids]
    avg = average_race_profiles(profiles)
    ref_meta = [{"competition_id": int(c), "name": p["competition_name"],
                 "date": p["competition_date"]}
                for c, p in zip(ref_ids, profiles)]
    if spec.get("scores"):
        overrides = {SCORE_KEY_MAP[k]: float(v)
                     for k, v in spec["scores"].items()}
        avg.update(overrides)
        best = max(SCORE_KEY_MAP.values(), key=lambda k: avg.get(k) or 0)
        avg["race_dominant_profile"] = best.replace("race_", "").replace("_score", "")
        avg["competition_name"] = spec["label"]
    return avg, ref_meta, ref_ids


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("config", help="path to stage scenarios.json")
    ap.add_argument("--only", default=None,
                    help="comma-separated scenario keys to run (default: all)")
    ap.add_argument("--no-log", action="store_true",
                    help="skip prediction_log writes")
    args = ap.parse_args()

    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text())
    out_dir = config_path.parent
    only = set(args.only.split(",")) if args.only else None
    todo = {k: v for k, v in config["scenarios"].items()
            if only is None or k in only}
    if not todo:
        sys.exit(f"No scenarios matched --only={args.only}")

    print("Loading production registry + serving artifacts...", flush=True)
    registry = ModelRegistry(str(MODEL_DIR))
    bucket_pred, time_gap_pred, race_ranker, lambdarank_pred = registry.load_with_ranker(
        ranking_method="ensemble")
    win_corrector = load_corrector(MODEL_DIR)
    dnf_bundle = load_production_dnf_head(MODEL_DIR)
    rating_snaps = load_production_rating_snapshots()
    saved_at = registry.get_metadata().get("saved_at", "")
    lr_temp = getattr(lambdarank_pred, "temperature", None)

    # Day-menu retrieval channel (Option A, 2026-08-09): when a scenario
    # carries a day_key, the kernod bucket ranks the board (pool membership
    # + order); the production heads above price it, untouched. Absent any
    # piece, serving falls back to the production board.
    dm_menu = dm_cum = dm_bucket = None
    try:
        dm_bucket = registry.load_bucket_variant("daymenu")
        if dm_bucket is not None:
            dm_menu = day_menu_mod.load_menu()
            dm_cum = day_menu_mod.load_kernels()
            print(f"day-menu channel ready: menu {dm_menu.version}, "
                  f"kernels {len(dm_cum):,} rows", flush=True)
        else:
            print("day-menu channel: bucket_daymenu absent — production board only",
                  flush=True)
    except Exception as e:
        dm_menu = dm_cum = dm_bucket = None
        print(f"[warn] day-menu channel unavailable: {e}", flush=True)

    teams, from_cache = scrape_or_load_startlist(
        int(config["fc_race_id"]), int(config["year"]), db_path=DB_PATH)
    assert from_cache, "startlist should come from cache"
    matched, unmatched = match_riders_to_db(teams, DB_PATH)
    print(f"Startlist: {len(matched)} matched, {len(unmatched)} unmatched", flush=True)

    conn = sqlite3.connect(DB_PATH)
    target = config.get("target", "stage")   # "stage" or "gc"
    stage_number = None if target == "gc" else int(config["stage"])
    comp_id = resolve_competition_id(conn, str(config["fc_race_id"]),
                                     int(config["year"]), stage_number)

    # ── within-race state (mirrors web app step 3) ──
    # stage >= 2: state feeds the MAIN models; gc: state feeds only the
    # separate GC outlook head — main GC prediction stays pre-race.
    state_df, state_info, gc_outlook_head = None, None, None
    want_state = (target == "gc") or (stage_number and stage_number >= 2)
    if want_state:
        state_df, state_info = fetch_live_race_state(
            int(config["fc_race_id"]), int(config["year"]),
            target_stage_number=stage_number if target == "stage" else None,
            db_path=DB_PATH,
        )
        print(f"race state: available={state_info.get('available')} "
              f"through stage {state_info.get('stages_completed')} "
              f"(sources {state_info.get('sources')}; "
              f"missing {state_info.get('missing_stages')}; "
              f"leader {state_info.get('leader_name')})", flush=True)
    if target == "gc":
        gc_outlook_head = GCOutlookHead.load(str(MODEL_DIR))
        if gc_outlook_head is None:
            print("[warn] GC outlook head not installed", flush=True)
    state_through = (int(state_info["stages_completed"])
                     if state_info and state_info.get("available") else None)
    main_state_df = state_df if target == "stage" else None

    # ── drop riders no longer in the race ──
    # Active field = riders still in the reconstructed standings (abandons
    # fall out of the cumulative GC), plus a config-level "exclude_riders"
    # list for announced withdrawals the road hasn't recorded yet (e.g. a
    # rest-day non-starter). Filtering BEFORE the heads means every
    # probability and the field features price the startable field only.
    startlist_size = len(matched)
    if state_df is not None and state_info.get("available"):
        active_ids = set(state_df["rider_id"].astype(int))
        gone = matched[~matched["rider_id"].astype(int).isin(active_ids)]
        if not gone.empty:
            print("  out of race: " + ", ".join(sorted(gone["rider_name"])),
                  flush=True)
            matched = matched[matched["rider_id"].astype(int).isin(active_ids)]
    excluded_cfg = {norm_name(n) for n in config.get("exclude_riders", [])}
    if excluded_cfg:
        mask = matched["rider_name"].map(norm_name).isin(excluded_cfg)
        if mask.any():
            print("  excluded by config: "
                  + ", ".join(sorted(matched.loc[mask, "rider_name"])),
                  flush=True)
            matched = matched[~mask]
    if len(matched) != startlist_size:
        print(f"  active field: {len(matched)} of {startlist_size} on the "
              f"startlist", flush=True)

    snapshots = get_latest_rider_snapshots(matched["rider_id"].tolist(), DB_PATH)
    field_features = compute_field_features(snapshots)
    team_map = matched.set_index("rider_id")["team_name"].to_dict()
    book, book_source = load_book(config)

    for key, spec in todo.items():
        prof, ref_meta, ref_ids = build_profile(spec, DB_PATH)
        print(f"\n=== {key}: {spec['label']} ===", flush=True)
        print("  profile:", ", ".join(
            f"{sk}={prof[fk]:.2f}" for sk, fk in SCORE_KEY_MAP.items()
            if prof.get(fk) is not None), flush=True)

        form_status = {}
        pred_df = assemble_prediction_df(snapshots, matched, field_features,
                                         prof, form_status=form_status)
        pred_df = attach_race_state(pred_df, main_state_df)
        pred_df = attach_stack_features(pred_df, time_gap_pred, lambdarank_pred,
                                        rating_snapshots=rating_snaps,
                                        signature_context=None)

        # ── day-menu ranking channel ──
        day_key = spec.get("day_key") or config.get("day_key")
        dm_scores = None
        if day_key and dm_bucket is not None:
            dm_scores = day_menu_mod.serving_board_scores(
                pred_df, dm_bucket, day_key, dm_menu, dm_cum,
                field_features, config["date"])
            dm_order = np.argsort(np.argsort(dm_scores))  # 0-based ranks
            dm_pool_ids = set(
                pred_df["rider_id"].astype(int).to_numpy()[dm_order < 15])
            print(f"  day key: {day_key} -> kernod board "
                  f"(pool of {len(dm_pool_ids)})", flush=True)
        elif day_key:
            print("  [warn] day_key set but day-menu channel unavailable — "
                  "production board", flush=True)

        result = race_ranker.predict_race(
            pred_df, return_details=True,
            extra_contender_ids=dm_pool_ids if dm_scores is not None else None)
        if dm_scores is not None:
            smap = dict(zip(pred_df["rider_id"].astype(int), dm_scores))
            result["daymenu_score"] = result["rider_id"].astype(int).map(smap)
            ranks = result["daymenu_score"].rank(method="first")
            result["daymenu_rank"] = ranks.astype(int)
            result["in_daymenu_pool"] = ranks <= 15
        lr_map = dict(zip(pred_df["rider_id"].astype(int),
                          pred_df["oof_lambdarank_win_p"].astype(float)))
        result["lambdarank_win_p"] = result["rider_id"].astype(int).map(lr_map)
        for col in ("contested_rating", "contested_rating_n"):
            elo_map = dict(zip(pred_df["rider_id"].astype(int), pred_df[col]))
            result[col] = result["rider_id"].astype(int).map(elo_map)

        priced, warnings = apply_pricing_layer(result, pred_df, prof,
                                               win_corrector=win_corrector,
                                               dnf_bundle=dnf_bundle,
                                               stage_number=stage_number,
                                               db_path=DB_PATH)
        for w in warnings:
            print(f"  [warn] {w}", flush=True)

        cols = [c for c in RESULT_COLS if c in priced.columns]
        board_col = "daymenu_rank" if dm_scores is not None else "predicted_rank"
        tab = priced.sort_values(board_col)[cols].copy()
        tab["team_name"] = tab["rider_id"].map(team_map)
        records = json.loads(tab.to_json(orient="records"))
        for r in records:
            b = find_book(book, r["rider_name"])
            r["book_odds"] = b["odds"] if b else None
            r["book_devig"] = b.get("devig") if b else None

        # GC targets: state-aware outlook head alongside the pre-race heads
        outlook_by_rider = {}
        if gc_outlook_head is not None and state_df is not None:
            outlook_frame = assemble_prediction_df(
                snapshots, matched, field_features, prof,
                form_status=form_status)
            outlook_frame = attach_race_state(outlook_frame, state_df)
            gco = gc_outlook_head.predict(outlook_frame)
            if not gco.empty:
                outlook_by_rider = gco.set_index("rider_id").to_dict("index")
            for r in records:
                o = outlook_by_rider.get(int(r["rider_id"]), {})
                for k2 in ("gc_outlook_win_p", "gc_outlook_podium_p",
                           "gc_outlook_top5_p", "gc_outlook_top15_p"):
                    r[k2] = o.get(k2)

        out_path = out_dir / f"{key}.json"
        out_path.write_text(json.dumps({
            "scenario": spec["label"],
            "scenario_key": key,
            "stage_number": stage_number,
            "references": ref_meta,
            "note": spec.get("note"),
            "model_version": f"{saved_at}|{spec['tag']}",
            "day_key": day_key if dm_scores is not None else None,
            "board": "daymenu" if dm_scores is not None else "production",
            "avg_profile": {k: prof.get(k) for k in prof
                            if not hasattr(prof.get(k), "shape")},
            "form_status": form_status,
            "book_source": book_source,
            "target": target,
            "state": ({"through_stage": state_through,
                       "leader": state_info.get("leader_name"),
                       "sources": state_info.get("sources"),
                       "missing": state_info.get("missing_stages")}
                      if state_info else None),
            "riders": records,
        }, indent=1, default=str))

        if not args.no_log:
            log_rows = [PredictionLogRow(
                fc_race_id=str(config["fc_race_id"]), year=int(config["year"]),
                stage_number=stage_number, competition_id=comp_id,
                rider_id=int(r["rider_id"]), rider_name=r["rider_name"],
                reference_comp_ids=list(ref_ids),
                model_version=f"{saved_at}|{spec['tag']}",
                multiclass_win_p=r.get("prob_win"),
                multiclass_podium_p=r.get("prob_podium"),
                multiclass_top5_p=r.get("prob_top5"),
                multiclass_top15_p=r.get("prob_top15"),
                lambdarank_win_p=r.get("lambdarank_win_p"),
                lambdarank_temperature=lr_temp,
                state_through_stage=state_through,
                gc_outlook_win_p=r.get("gc_outlook_win_p"),
                gc_outlook_podium_p=r.get("gc_outlook_podium_p"),
                gc_outlook_top5_p=r.get("gc_outlook_top5_p"),
                gc_outlook_top15_p=r.get("gc_outlook_top15_p"),
                dnf_p=r.get("dnf_p"),
                dnf_adj_win_p=r.get("dnf_adj_win_p"),
                dnf_adj_podium_p=r.get("dnf_adj_podium_p"),
                dnf_adj_top5_p=r.get("dnf_adj_top5_p"),
                dnf_adj_top15_p=r.get("dnf_adj_top15_p"),
                blend_win_p=r.get("blend_win_p"),
            ) for r in records]
            n = log_predictions(conn, log_rows)
            print(f"  saved {out_path.name}; logged {n} rows "
                  f"(...|{spec['tag']}, comp_id={comp_id})", flush=True)
        else:
            print(f"  saved {out_path.name} (logging skipped)", flush=True)

        top = records[:8]
        print("  top-8: " + " | ".join(
            f"{r['rider_name']} bl={100*(r['blend_win_p'] or 0):.1f}%"
            for r in sorted(top, key=lambda r: -(r['blend_win_p'] or 0))),
            flush=True)

    conn.close()


if __name__ == "__main__":
    main()
