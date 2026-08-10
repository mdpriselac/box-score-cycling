"""
Evening day-key scoring for the Vuelta 2026 — the tier-3 judgment evaluation.

For a settled stage, reconstructs the ORACLE menu item from the archived
results (the same labeler + frozen GMM the training keys use) and scores the
morning's logged day_key against it:

    exact           argmax-weight item == oracle item
    covered         oracle item in the keyed set (weight > 0)
    weight_on_true  weight the read put on the oracle item

Run each evening AFTER capture_results.py (which archives the stage) —
requires only the archive + the DB's pre-race rider profiles; the weekly
pipeline is NOT needed mid-race.

    uv run python performance_eval/vuelta-2026/score_day_keys.py            # latest archived stage
    uv run python performance_eval/vuelta-2026/score_day_keys.py --stage 4

Appends to review/key_scorecard.json and prints the running table.

Evening labels are PROVISIONAL: rider archetypes come from the latest DB
snapshots (pre-race mid-campaign), so items can flip between within-family
twins (res_3/res_7 seen on TdF st17 in validation; macro routes and family
identity are stable). The canonical tier-3 numbers are re-scored after the
race from the rebuilt signature table (label_days) — the stored
top15_shares make that a pure re-read.
Oracle construction (mirrors prediction_tools/day_menu.label_days):
  itt      winning time < labeler.itt_seconds
  bunch    rule_label mass_sprint, or bunch_sprint with wg_prop >= wide_bs_prop
  gc_day   stage winner (or front-5 median) inside morning-GC top gc_top —
           morning GC = the newest standings_*.json archived BEFORE the stage
  residual stored-parameter GMM assignment on the realized top-15 archetype
           shares (as-of rider best_profile snapshots from the DB)
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

CAMPAIGN = Path(__file__).resolve().parent
PROJECT_ROOT = CAMPAIGN.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from cycling_project.prediction_tools.day_menu import (   # noqa: E402
    ARCH,
    assign_residual_items,
    load_menu,
)
from cycling_project.prediction_tools.experiments.front_local_race_typing import (  # noqa: E402
    comp_features,
    rule_label,
)

DB_PATH = str(PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
              / "database" / "cycling_races.db")
RESULTS_ROOT = CAMPAIGN / "results"
PREDICTIONS_ROOT = CAMPAIGN / "predictions"
SCORECARD = CAMPAIGN / "review" / "key_scorecard.json"


def latest_archived_stage() -> int:
    stages = sorted(int(p.name.split("_")[1]) for p in RESULTS_ROOT.glob("stage_*")
                    if (p / "results.json").exists())
    if not stages:
        sys.exit("no archived stages under results/ — run capture_results.py first")
    return stages[-1]


def morning_gc_ranks(stage_results_fetched_at: str) -> dict:
    """fc_rider_id -> GC place from the newest standings archived BEFORE the
    stage's results capture (i.e. the previous evening's GC)."""
    race_page = RESULTS_ROOT / "race_page"
    cutoff = stage_results_fetched_at[:10]
    cands = sorted(race_page.glob("standings_*.json"))
    prior = [p for p in cands if p.stem.split("_")[1] < cutoff]
    if not prior:
        return {}
    snap = json.loads(prior[-1].read_text())
    out = {}
    for r in snap.get("results", []):
        place = str(r.get("place", "")).strip()
        if place.isdigit():
            out[str(r.get("rider_id"))] = int(place)
    return out


def rider_profiles(fc_ids: list) -> dict:
    """fc_rider_id -> as-of best_profile (latest snapshot per rider; mid-race
    these are the pre-race snapshots, matching the labeler's as-of-then
    discipline)."""
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TEMP TABLE want(fc_id TEXT PRIMARY KEY)")
    con.executemany("INSERT OR IGNORE INTO want VALUES (?)",
                    [(str(i),) for i in fc_ids])
    rows = con.execute("""
        SELECT r.fc_rider_id, s.best_profile
        FROM riders r
        JOIN want w ON w.fc_id = CAST(r.fc_rider_id AS TEXT)
        JOIN rider_competition_snapshots s ON s.rider_id = r.id
        JOIN (SELECT rider_id, MAX(competition_id) AS mc
              FROM rider_competition_snapshots GROUP BY rider_id) latest
          ON latest.rider_id = s.rider_id AND latest.mc = s.competition_id
    """).fetchall()
    con.close()
    return {str(fc): (bp or "unknown") for fc, bp in rows}


def oracle_item(stage: int, menu) -> dict:
    d = json.loads((RESULTS_ROOT / f"stage_{stage:02d}" / "results.json").read_text())
    rows = [r for r in d["results"]
            if str(r.get("place", "")).strip().isdigit()]
    rows.sort(key=lambda r: int(r["place"]))
    gaps = np.array([r["gap"] for r in rows
                     if isinstance(r.get("gap"), (int, float))], dtype=float)
    gaps = np.sort(gaps) - gaps.min()
    feats = comp_features(gaps)
    rule = rule_label(feats)
    winning_time = d.get("race_time")

    profiles = rider_profiles([r["rider_id"] for r in rows[:15]])
    top15 = [profiles.get(str(r["rider_id"]), "unknown") for r in rows[:15]]
    shares_all = {a: top15.count(a) / len(top15) for a in set(top15)}
    shares6 = np.array([[shares_all.get(a, 0.0) for a in ARCH]])

    cfg = menu.labeler
    gc = morning_gc_ranks(d.get("fetched_at", ""))
    winner_gc = gc.get(str(rows[0]["rider_id"])) if rows else None
    front5 = [gc.get(str(r["rider_id"])) for r in rows[:5]]
    front5 = [g for g in front5 if g is not None]
    front5_med = float(np.median(front5)) if front5 else None

    if winning_time is not None and winning_time < cfg["itt_seconds"]:
        item, day_class = "itt", "itt"
    elif rule == "mass_sprint" or (rule == "bunch_sprint"
                                   and feats["wg_prop"] >= cfg["wide_bs_prop"]):
        item, day_class = "bunch", "bunch"
    elif ((winner_gc is not None and winner_gc <= cfg["gc_top"])
          or (front5_med is not None and front5_med <= cfg["gc_top"])):
        item, day_class = "gc_day", "gc_day"
    else:
        item = assign_residual_items(shares6, menu)[0]
        day_class = "residual"

    return {
        "stage": stage,
        "oracle_item": item,
        "day_class": day_class,
        "rule_type": rule,
        "wg_size": int(feats["wg_size"]),
        "wg_prop": round(float(feats["wg_prop"]), 4),
        "winning_time": winning_time,
        "winner": rows[0]["name"] if rows else None,
        "winner_gc_morning": winner_gc,
        "front5_gc_median": front5_med,
        "top15_shares": {a: round(shares_all.get(a, 0.0), 3) for a in ARCH},
        "top15_unknown": round(shares_all.get("unknown", 0.0), 3),
    }


def logged_key(stage: int) -> dict | None:
    cfg_path = PREDICTIONS_ROOT / f"stage_{stage:02d}" / "scenarios.json"
    if not cfg_path.exists():
        return None
    cfg = json.loads(cfg_path.read_text())
    key = cfg.get("day_key")
    if key is None:
        for spec in cfg.get("scenarios", {}).values():
            if spec.get("day_key"):
                return {"day_key": spec["day_key"],
                        "source": f"scenario:{spec.get('tag')}"}
        return None
    return {"day_key": key, "source": "config-root"}


def score(oracle: dict, logged: dict | None) -> dict:
    row = dict(oracle)
    if logged is None:
        row.update({"day_key": None, "exact": None, "covered": None,
                    "weight_on_true": None, "key_source": None})
        return row
    key = {k: float(v) for k, v in logged["day_key"].items()}
    tot = sum(key.values()) or 1.0
    key = {k: v / tot for k, v in key.items()}
    top_item = max(key, key=key.get)
    row.update({
        "day_key": key,
        "key_source": logged["source"],
        "exact": top_item == oracle["oracle_item"],
        "covered": oracle["oracle_item"] in key,
        "weight_on_true": round(key.get(oracle["oracle_item"], 0.0), 3),
    })
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--stage", type=int, default=None)
    args = ap.parse_args()
    stage = args.stage or latest_archived_stage()

    menu = load_menu()
    row = score(oracle_item(stage, menu), logged_key(stage))
    row["scored_at"] = datetime.now().isoformat()

    SCORECARD.parent.mkdir(parents=True, exist_ok=True)
    card = json.loads(SCORECARD.read_text()) if SCORECARD.exists() else []
    card = [r for r in card if r["stage"] != stage] + [row]
    card.sort(key=lambda r: r["stage"])
    SCORECARD.write_text(json.dumps(card, indent=1))

    print(f"stage {stage}: oracle={row['oracle_item']} ({row['day_class']}, "
          f"rule={row['rule_type']}, wg={row['wg_size']}, "
          f"wt={row['winning_time']})")
    if row["day_key"] is None:
        print("  no day_key logged for this stage")
    else:
        print(f"  read: {row['day_key']} ({row['key_source']})")
        print(f"  exact={row['exact']} covered={row['covered']} "
              f"weight_on_true={row['weight_on_true']}")

    scored = [r for r in card if r.get("exact") is not None]
    if scored:
        print(f"\nrunning tier-3 accuracy over {len(scored)} keyed stages: "
              f"exact {sum(r['exact'] for r in scored)}/{len(scored)}, "
              f"covered {sum(r['covered'] for r in scored)}/{len(scored)}, "
              f"mean weight_on_true "
              f"{np.mean([r['weight_on_true'] for r in scored]):.2f}")


if __name__ == "__main__":
    main()
