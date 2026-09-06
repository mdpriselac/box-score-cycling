"""
Seed the app's live-race-state cache (cached_race_results) from the daily
FirstCycling archive written by capture_results.py.

    uv run python performance_eval/tour-de-france-2026/seed_state_cache.py

Defaults to this campaign (TdF 2026, fc_race_id 17); point it at another
campaign's archive with --race-id/--year/--out-root, e.g.

    uv run python performance_eval/tour-de-france-2026/seed_state_cache.py \
        --race-id 23 --year 2026 \
        --out-root performance_eval/vuelta-2026/results

fetch_live_race_state() loads completed stages local-first (DB -> cache ->
live scrape); seeding the cache from results/stage_NN/results.json makes
in-race state available without re-scraping — and without depending on
FirstCycling serving a complete page at run time. Idempotent
(INSERT OR REPLACE on the same stage/rider keys).
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from cycling_project.prediction_tools.future_race_loader import (
    get_cached_results,
    save_results_to_cache,
)

DEFAULT_RACE_ID, DEFAULT_YEAR = 17, 2026
DEFAULT_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
DB_PATH = str(PROJECT_ROOT / "cycling_project" / "webscrape_tools" / "database"
              / "database" / "cycling_races.db")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--race-id", type=int, default=DEFAULT_RACE_ID,
                    help="FirstCycling race id (default 17 = TdF; Vuelta = 23)")
    ap.add_argument("--year", type=int, default=DEFAULT_YEAR)
    ap.add_argument("--out-root", default=None,
                    help="results archive to seed from "
                         "(default: this campaign's results/)")
    args = ap.parse_args()

    fc_race_id, year = args.race_id, args.year
    results_root = (Path(args.out_root) if args.out_root
                    else DEFAULT_RESULTS_ROOT)
    print(f"Seeding race {fc_race_id} ({year}) from {results_root}")

    seeded = []
    for stage_dir in sorted(results_root.glob("stage_*")):
        f = stage_dir / "results.json"
        if not f.exists():
            continue
        payload = json.loads(f.read_text())
        stage_num = str(int(payload["stage"]))
        rows = []
        for r in payload["results"]:
            place = str(r.get("place", "")).strip()
            gap = r.get("gap")
            rows.append({
                "rider_fc_id": r.get("rider_id"),
                "rider_name": r.get("name"),
                "team_name": r.get("team"),
                "place": int(place) if place.isdigit() else None,
                "time_gap": float(gap) if isinstance(gap, (int, float)) else None,
                "place_bucket": None,
            })
        df = pd.DataFrame(rows)
        save_results_to_cache(
            fc_race_id, year, df,
            winning_time=payload.get("race_time"),
            stage_id=stage_num,
            stage_name=payload.get("stage_name"),
            db_path=DB_PATH,
        )
        cached = get_cached_results(fc_race_id, year, stage_id=stage_num,
                                    db_path=DB_PATH)
        n_check = 0 if cached is None else len(cached)
        seeded.append(stage_num)
        print(f"stage {stage_num}: cached {len(df)} rows "
              f"(cache now holds {n_check}; winning_time={payload.get('race_time')})")
    if not seeded:
        print("No archived stage results found — run capture_results.py first.")
        return 1
    print(f"Seeded stages: {', '.join(seeded)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
