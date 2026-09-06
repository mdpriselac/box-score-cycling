"""
Config-driven stage prediction runner — headless arm-C serving path.

Reads a per-stage scenario config (performance_eval/<campaign>/
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
    tag:       suffix appended to model_version in prediction_log. Exact
               reruns update the same semantic opinion; changed release,
               scenario, field, profile, day key, or race state creates a new
               run identity.
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

from cycling_project.prediction_tools.live_race_state import (
    fetch_live_race_state,
)
from cycling_project.prediction_tools.future_race_loader import (
    average_race_profiles,
    compute_field_features,
    get_latest_rider_snapshots,
    get_reference_race_profile,
    match_riders_to_db,
    scrape_or_load_startlist,
)
from cycling_project.prediction_tools.prediction_log import (
    PredictionLogRow,
    PredictionRunIdentity,
    log_predictions,
    prediction_input_fingerprint,
    resolve_competition_id,
)
from cycling_project.prediction_tools.prediction_service import (
    PredictionRequest,
    PredictionService,
)
from cycling_project.db_path import default_db_path

MODEL_DIR = PROJECT_ROOT / "models" / "production"
DB_PATH = str(default_db_path())

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


def json_number(value):
    """Return a finite JSON number, or None for missing/non-finite values."""
    return (
        float(value)
        if value is not None and np.isfinite(value)
        else None
    )


def norm_name(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("'", "").replace("-", " ").replace(".", " ")
    return " ".join(sorted(s.split()))


def campaign_odds_root(config, config_path):
    """This campaign's odds archive.

    Configs live at <campaign>/predictions/{stage_NN,gc}/scenarios.json, so the
    campaign root is two levels up — the runner works for any campaign
    directory (TdF, Vuelta, ...) with no flag. A config may override with an
    "odds_root" key (absolute, or relative to the project root).
    """
    override = config.get("odds_root")
    if override:
        root = Path(override)
        return root if root.is_absolute() else PROJECT_ROOT / root
    return config_path.parents[2] / "odds"


def load_book(config, odds_root):
    """Rider -> win-market outcome from the archived Kambi capture.

    Both "odds_capture" and "event_id" are optional: a post-hoc board for a
    stage whose market was never captured (a missed day) has no book to
    compare against, and should still run with empty book columns rather than
    raising.
    """
    capture = config.get("odds_capture")
    event_id = config.get("event_id")
    if not capture or not event_id:
        return {}, None
    odds_file = odds_root / capture
    if not odds_file.exists():
        return {}, None
    mk = json.loads(odds_file.read_text())
    for bo in mk.get(str(event_id), {}).get("betoffers", []):
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
    service = PredictionService.from_production(MODEL_DIR, db_path=DB_PATH)
    release_id = service.artifacts.model_version
    print(f"validated production release {release_id[:12]}", flush=True)

    teams, from_cache = scrape_or_load_startlist(
        int(config["fc_race_id"]), int(config["year"]), db_path=DB_PATH)
    assert from_cache, "startlist should come from cache"
    matched, unmatched = match_riders_to_db(teams, DB_PATH)
    print(f"Startlist: {len(matched)} matched, {len(unmatched)} unmatched", flush=True)

    conn = sqlite3.connect(DB_PATH)
    target = config.get("target", "stage")   # "stage", "gc" or "one_day"
    stage_number = int(config["stage"]) if target == "stage" else None
    comp_id = resolve_competition_id(conn, str(config["fc_race_id"]),
                                     int(config["year"]), stage_number)

    # ── within-race state (mirrors web app step 3) ──
    # stage >= 2: state feeds the MAIN models; gc: state feeds only the
    # separate GC outlook head — main GC prediction stays pre-race.
    state_df, state_info = None, None
    want_state = (target == "gc") or (stage_number and stage_number >= 2)
    if want_state:
        # "void_stages" in the config = stages CANCELLED outright. They add
        # no time to anyone, so the reconstruction skips them instead of
        # treating them as a contiguity break — without this a cancelled stage
        # freezes state at the stage before it for the rest of the race.
        state_df, state_info = fetch_live_race_state(
            int(config["fc_race_id"]), int(config["year"]),
            target_stage_number=stage_number if target == "stage" else None,
            db_path=DB_PATH,
            void_stages=config.get("void_stages"),
        )
        print(f"race state: available={state_info.get('available')} "
              f"through stage {state_info.get('stages_completed')} "
              f"(sources {state_info.get('sources')}; "
              f"missing {state_info.get('missing_stages')}; "
              f"void {state_info.get('void_stages')}; "
              f"leader {state_info.get('leader_name')})", flush=True)
    state_through = (int(state_info["stages_completed"])
                     if state_info and state_info.get("available") else None)

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
    book, book_source = load_book(config, campaign_odds_root(config, config_path))

    for key, spec in todo.items():
        prof, ref_meta, ref_ids = build_profile(spec, DB_PATH)
        print(f"\n=== {key}: {spec['label']} ===", flush=True)
        print("  profile:", ", ".join(
            f"{sk}={prof[fk]:.2f}" for sk, fk in SCORE_KEY_MAP.items()
            if prof.get(fk) is not None), flush=True)

        day_key = spec.get("day_key") or config.get("day_key")
        prediction = service.predict(PredictionRequest(
            snapshots=snapshots,
            matched_riders=matched,
            field_features=field_features,
            profile=prof,
            target_type=target,
            stage_number=stage_number,
            race_state=state_df,
            reference_competition_ids=ref_ids,
            day_key=day_key,
            race_date=config["date"],
            asof_date=config["date"],
        ))
        for w in prediction.warnings:
            print(f"  [warn] {w}", flush=True)
        if prediction.board == "daymenu":
            print(f"  day key: {day_key} -> kernod board", flush=True)

        cols = [c for c in RESULT_COLS if c in prediction.riders.columns]
        board_col = (
            "daymenu_rank" if prediction.board == "daymenu" else "predicted_rank"
        )
        tab = prediction.riders.sort_values(board_col)[cols].copy()
        tab["team_name"] = tab["rider_id"].map(team_map)
        records = json.loads(tab.to_json(orient="records"))
        for r in records:
            b = find_book(book, r["rider_name"])
            r["book_odds"] = b["odds"] if b else None
            r["book_devig"] = b.get("devig") if b else None

        # GC targets: state-aware outlook head alongside the pre-race heads
        if prediction.gc_outlook is not None:
            outlook_by_rider = (
                prediction.gc_outlook.set_index("rider_id").to_dict("index")
            )
            for r in records:
                o = outlook_by_rider.get(int(r["rider_id"]), {})
                for k2 in ("gc_outlook_win_p", "gc_outlook_podium_p",
                           "gc_outlook_top5_p", "gc_outlook_top15_p"):
                    value = o.get(k2)
                    # Pandas keeps non-contender values as floating NaN.
                    # Python's json module will otherwise emit the non-standard
                    # token `NaN`, which strict JSON consumers (including
                    # JSON.parse in a Worker/browser) reject.  Missing outlook
                    # prices are part of the public artifact contract, so
                    # represent them as JSON null.
                    r[k2] = json_number(value)

        out_path = out_dir / f"{key}.json"
        out_path.write_text(json.dumps({
            "scenario": spec["label"],
            "scenario_key": key,
            "stage_number": stage_number,
            "references": ref_meta,
            "note": spec.get("note"),
            "model_version": f"{release_id}|{spec['tag']}",
            "day_key": prediction.day_key,
            "board": prediction.board,
            "avg_profile": {k: prof.get(k) for k in prof
                            if not hasattr(prof.get(k), "shape")},
            "form_status": prediction.form_status,
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
                model_version=f"{release_id}|{spec['tag']}",
                multiclass_win_p=r.get("prob_win"),
                multiclass_podium_p=r.get("prob_podium"),
                multiclass_top5_p=r.get("prob_top5"),
                multiclass_top15_p=r.get("prob_top15"),
                lambdarank_win_p=r.get("lambdarank_win_p"),
                lambdarank_temperature=prediction.lambdarank_temperature,
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
            run_identity = PredictionRunIdentity(
                fc_race_id=str(config["fc_race_id"]),
                year=int(config["year"]),
                stage_number=stage_number,
                model_version=f"{release_id}|{spec['tag']}",
                reference_comp_ids=ref_ids,
                state_through_stage=state_through,
                scenario_key=key,
                target=target,
                day_key=json.dumps(day_key, sort_keys=True) if day_key else None,
                input_fingerprint=prediction_input_fingerprint(
                    matched["rider_id"], prof, config["date"]
                ),
            )
            n = log_predictions(conn, log_rows, run_identity=run_identity)
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
