"""
Daily FirstCycling results capture for the Tour de France 2026 (fc_race_id=17).

Run each evening AFTER the stage finishes:

    uv run python performance_eval/tour-de-france-2026/capture_results.py

Archive-only — never touches the pickle store or the SQLite DB (the weekly
update_pipeline handles that after the race). Each run:

  1. Fetches the race page and snapshots it (raw HTML + parsed standings JSON)
     into results/race_page/ — this is the daily record of the current GC.
  2. Walks the stage list in order; for each stage not already archived with
     results, fetches the stage page and writes results/stage_NN/:
         stage_page_YYYY-MM-DD.html   raw HTML
         results.json                 parsed results + metadata
         results.csv                  place, rider, team, gap per row
     Stops at the first stage with no results yet (stages are sequential),
     so a normal daily run costs ~3 rate-limited requests.

Flags: --force re-fetches archived stages, --all keeps scanning past empty
stages, --stage N fetches only that stage.

Uses the project WebClient — with SCRAPER_USE_BROWSER=1 in .env this opens a
visible Chrome window for the Cloudflare challenge. Requests are rate-limited;
do not run in a tight loop.
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.create_race_data import BASE_URL, extract_stages_with_links
from cycling_project.webscrape_tools.get_race_results import (
    extract_race_date,
    extract_race_time,
    extract_results,
    find_table_head_order,
    parse_rider_row,
)
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger("capture_tdf_results")

OUT_ROOT = Path(__file__).resolve().parent / "results"
RESULT_FIELDS = ["place", "name", "rider_id", "team", "team_id", "gap", "dob"]


def write_results_csv(path: Path, results: list) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(results)


def parse_classification_tables(soup: BeautifulSoup) -> dict:
    """Parse every standings table on a stage page, keyed by its container
    div id. FirstCycling wraps each one in an identified div: #sta (stage
    result), #gc (GC after the stage, full field, individual gaps incl.
    bonus seconds), #youth, #teamcomp, and points/KOM equivalents.
    Rider tables parse to the usual result dicts; team-only tables (TTT
    stage result, team classification) to raw cell lists.
    """
    out = {}
    for table in soup.find_all("table"):
        div = table.find_parent("div", id=True)
        if div is None:
            continue
        did = div["id"]
        if did in out or did in ("cont720", "wrapper"):
            continue
        ths = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "pos" not in ths:
            continue
        rows = table.find_all("tr")
        if "rider" in ths:
            head_order = find_table_head_order(table)
            parsed = [parse_rider_row(r, head_order) for r in rows[1:]]
            out[did] = [p for p in parsed if p]
        else:
            out[did] = [[c.get_text(strip=True, separator=" ")
                         for c in r.find_all("td")] for r in rows[1:]]
    return out


def stage_dir_for(e_val: str) -> Path:
    padded = f"{int(e_val):02d}" if e_val.isdigit() else e_val
    return OUT_ROOT / f"stage_{padded}"


def stage_already_archived(stage_dir: Path) -> bool:
    f = stage_dir / "results.json"
    if not f.exists():
        return False
    try:
        return bool(json.loads(f.read_text()).get("results"))
    except (json.JSONDecodeError, OSError):
        return False


def capture_stage(client: WebClient, stage_num: str, stage_name: str, url: str,
                  today: str) -> bool:
    """Fetch one stage page and archive it. Returns True if results were found."""
    stage_dir = stage_dir_for(stage_num)
    stage_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {stage_name} ...")
    resp = client.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    (stage_dir / f"stage_page_{today}.html").write_text(resp.text)

    results, race_time, date = [], None, None
    try:
        results = extract_results(soup)
    except Exception as e:
        logger.warning(f"Error parsing results for {stage_name}: {e}")
    try:
        race_time = extract_race_time(soup)
    except Exception as e:
        logger.warning(f"Error parsing race time for {stage_name}: {e}")
    try:
        date = extract_race_date(soup)
    except Exception as e:
        logger.warning(f"Error parsing date for {stage_name}: {e}")

    if not results:
        print(f"  no results yet for {stage_name} (raw HTML archived)")
        return False

    payload = {
        "stage": stage_num,
        "stage_name": stage_name,
        "url": url,
        "date": date,
        "race_time": race_time,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "n_results": len(results),
        "results": results,
    }
    (stage_dir / "results.json").write_text(json.dumps(payload, indent=1))
    write_results_csv(stage_dir / "results.csv", results)
    print(f"  archived {len(results)} results "
          f"(winner: {results[0].get('name')}, date: {date})")

    try:
        classifications = parse_classification_tables(soup)
    except Exception as e:
        logger.warning(f"Error parsing classification tables for {stage_name}: {e}")
        classifications = {}
    if classifications:
        (stage_dir / "classifications.json").write_text(json.dumps(
            {"stage": stage_num, "fetched_at": payload["fetched_at"],
             "tables": classifications}, indent=1))
        gc = classifications.get("gc")
        if gc and isinstance(gc[0], dict):
            write_results_csv(stage_dir / "gc.csv", gc)
        print(f"  classifications archived: {', '.join(sorted(classifications))}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--race-id", default="17", help="FirstCycling race id (default 17 = TdF)")
    ap.add_argument("--year", default="2026")
    ap.add_argument("--force", action="store_true", help="re-fetch stages already archived")
    ap.add_argument("--all", action="store_true",
                    help="keep scanning past the first stage with no results")
    ap.add_argument("--stage", default=None, help="fetch only this stage number (e.g. 05)")
    args = ap.parse_args()

    today = datetime.now().strftime("%Y-%m-%d")
    race_page_dir = OUT_ROOT / "race_page"
    race_page_dir.mkdir(parents=True, exist_ok=True)

    client = WebClient(BASE_URL)
    try:
        race_url = f"{BASE_URL}/race.php?r={args.race_id}&y={args.year}"
        print(f"Fetching race page {race_url} ...")
        resp = client.get(race_url)
        soup = BeautifulSoup(resp.text, "html.parser")
        (race_page_dir / f"race_page_{today}.html").write_text(resp.text)

        # Whatever standings table the race page currently shows (running GC
        # mid-race, final GC afterwards) — the dated snapshots are the GC record.
        try:
            standings = extract_results(soup)
        except Exception as e:
            logger.warning(f"Error parsing race-page standings: {e}")
            standings = []
        if standings:
            (race_page_dir / f"standings_{today}.json").write_text(json.dumps(
                {"fetched_at": datetime.now().isoformat(timespec="seconds"),
                 "url": race_url, "n_results": len(standings),
                 "results": standings}, indent=1))
            write_results_csv(race_page_dir / f"standings_{today}.csv", standings)
            print(f"Race-page standings archived ({len(standings)} rows, "
                  f"leader: {standings[0].get('name')})")
        else:
            print("No standings table on the race page yet (raw HTML archived).")

        stages = extract_stages_with_links(soup)
        if not stages:
            print("ERROR: no stage selector found on the race page.")
            return 1
        stage_list = [(name, val.strip()) for name, val in stages.items()
                      if val and val.strip()]
        print(f"Race page lists {len(stage_list)} stages.")

        n_new = 0
        for stage_name, e_val in stage_list:
            if args.stage and e_val.lstrip("0") != args.stage.lstrip("0"):
                continue
            stage_dir = stage_dir_for(e_val)
            if not args.force and stage_already_archived(stage_dir):
                continue
            url = f"{BASE_URL}/race.php?r={args.race_id}&y={args.year}&e={e_val}"
            got_results = capture_stage(client, e_val, stage_name, url, today)
            if got_results:
                n_new += 1
            elif not args.all and not args.stage:
                break  # stages are sequential — nothing after this one either

        archived = sorted(p.name for p in OUT_ROOT.glob("stage_*")
                          if stage_already_archived(p))
        print(f"\nDone. {n_new} new stage(s) archived this run; "
              f"{len(archived)}/{len(stage_list)} stages archived total.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
