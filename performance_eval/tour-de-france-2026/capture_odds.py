"""
Daily Kambi (Unibet NL) odds capture for the Tour de France 2026.

Run each morning BEFORE the stage starts — once a stage goes live/settles it
drops out of Kambi's pre-match feed and that day's stage odds are gone.

    uv run python performance_eval/tour-de-france-2026/capture_odds.py

Discovers all live TdF events (next stage, GC, jerseys, stage-win specials)
from the Kambi cycling listView, fetches every betoffer for each, and writes
a timestamped snapshot under odds/YYYY-MM-DD/:

    raw/listview_HHMM.json           full cycling listView response
    raw/event_{id}_{slug}_HHMM.json  full betoffer response per event
    markets_HHMM.json                parsed markets (all betoffers, all events)
    provenance_HHMM.json             URLs, timestamps, event map, overrounds
    win_odds_HHMM.csv                flat CSV of full-field win/podium/top-N
                                     markets with devigged probabilities

Safe to run multiple times a day (files are timestamped, nothing overwritten).
Uses stdlib only. The feed may require NL egress (VPN) depending on network —
a 403/451 or empty event list means flip the VPN on and rerun.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://eu-offering-api.kambicdn.com/offering/v2018"
OUT_ROOT = Path(__file__).resolve().parent / "odds"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
FETCH_SLEEP_S = 1.5


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def slugify(name: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]", "_", name.lower())).strip("_")


def book_sum_for(bet_offer_type_name: str) -> float | None:
    """Number of 'winning' places a full-field market pays — the devig target.

    'Winnaar' pays 1 place; '(1-3)' pays 3; '(1-10)' pays 10. Returns None for
    market types we shouldn't devig (head-to-heads, yes/no specials, etc.).
    """
    if bet_offer_type_name == "Winnaar":
        return 1.0
    m = re.fullmatch(r"\(1-(\d+)\)", bet_offer_type_name.strip())
    return float(m.group(1)) if m else None


def parse_betoffer(bo: dict) -> dict:
    outcomes = []
    for o in bo.get("outcomes", []):
        if o.get("odds") is None:
            continue
        outcomes.append({
            "name": o.get("participant") or o.get("label"),
            "label": o.get("label"),
            "odds": o["odds"] / 1000.0,
            "implied": 1000.0 / o["odds"],
        })
    parsed = {
        "betoffer_id": bo.get("id"),
        "criterion": bo.get("criterion", {}).get("label"),
        "bet_offer_type": bo.get("betOfferType", {}).get("name"),
        "outcomes": outcomes,
    }
    book_sum = book_sum_for(parsed["bet_offer_type"] or "")
    if book_sum is not None and outcomes:
        implied_sum = sum(o["implied"] for o in outcomes)
        parsed["book_sum"] = book_sum
        parsed["overround"] = round(implied_sum / book_sum, 4)
        for o in outcomes:
            o["devig"] = o["implied"] / implied_sum * book_sum
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--brand", default="ubnl", help="Kambi brand code (default ubnl = Unibet NL)")
    ap.add_argument("--lang", default="nl_NL")
    ap.add_argument("--market", default="NL")
    ap.add_argument("--match", default="(tour de france 2026)",
                    help="case-insensitive substring an event name must contain; "
                         "matched against BOTH the localised name and englishName, "
                         "so 'vuelta a espa' finds the Dutch 'Ronde van Spanje' "
                         "(default excludes TdF Femmes; use 'tour de france' to include it)")
    ap.add_argument("--out-root", default=str(OUT_ROOT),
                    help="odds archive root (default: this campaign's odds/); "
                         "other campaigns pass their own, e.g. "
                         "performance_eval/vuelta-2026/odds")
    args = ap.parse_args()

    now_utc = datetime.now(timezone.utc)
    day = datetime.now().strftime("%Y-%m-%d")
    hhmm = datetime.now().strftime("%H%M")
    out_dir = Path(args.out_root) / day
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    listview_url = (f"{BASE}/{args.brand}/listView/cycling.json"
                    f"?lang={args.lang}&market={args.market}&useCombined=true")
    print(f"Fetching cycling listView ({args.brand}) ...")
    try:
        listview = fetch_json(listview_url)
    except urllib.error.HTTPError as e:
        print(f"ERROR: listView returned HTTP {e.code}.")
        if e.code in (403, 451):
            print("The Kambi feed is geo-blocked from this network — turn on the NL VPN and rerun.")
        return 1

    (raw_dir / f"listview_{hhmm}.json").write_text(json.dumps(listview))

    events = []
    for item in listview.get("events", []):
        ev = item.get("event", item)
        # The feed localises event names (the Vuelta is "Ronde van Spanje" on
        # the NL brand), so match the English name as well.
        names = f"{ev.get('name', '')} | {ev.get('englishName', '')}"
        if args.match.lower() in names.lower():
            events.append(ev)

    if not events:
        print(f"No events matching '{args.match}' in the feed.")
        print("Either all its markets are live/settled right now (run earlier in the day),")
        print("or the feed is geo-filtered — try with the NL VPN on.")
        return 1

    print(f"Found {len(events)} matching events:")
    for ev in events:
        print(f"  {ev['id']}  {ev.get('start', '?'):>22}  {ev['name']}")

    markets = {}
    prov = {
        "source": f"Kambi CDN, brand={args.brand}, lang={args.lang}, market={args.market}",
        "listview_url": listview_url,
        "fetched_at_utc": now_utc.isoformat(timespec="seconds"),
        "events": {str(ev["id"]): {"name": ev["name"], "start": ev.get("start"),
                                   "group": ev.get("group")} for ev in events},
        "overrounds": {},
    }

    for ev in events:
        eid, slug = ev["id"], slugify(ev.get("englishName") or ev["name"])
        url = f"{BASE}/{args.brand}/betoffer/event/{eid}.json?lang={args.lang}&market={args.market}"
        print(f"Fetching betoffers for {ev['name']} ...")
        try:
            data = fetch_json(url)
        except urllib.error.HTTPError as e:
            print(f"  WARNING: HTTP {e.code} for event {eid}, skipping")
            continue
        (raw_dir / f"event_{eid}_{slug}_{hhmm}.json").write_text(json.dumps(data))

        parsed = [parse_betoffer(bo) for bo in data.get("betOffers", [])]
        markets[str(eid)] = {"event_name": ev["name"], "start": ev.get("start"),
                             "betoffers": parsed}
        for p in parsed:
            if "overround" in p:
                key = f"{slug} | {p['criterion']} | {p['bet_offer_type']}"
                prov["overrounds"][key] = p["overround"]
        time.sleep(FETCH_SLEEP_S)

    (out_dir / f"markets_{hhmm}.json").write_text(json.dumps(markets, indent=1))
    (out_dir / f"provenance_{hhmm}.json").write_text(json.dumps(prov, indent=1))

    # Flat CSV of every full-field (devigged) market across all events.
    csv_path = out_dir / f"win_odds_{hhmm}.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event", "market", "rider", "odds", "implied", "devig"])
        for eid, m in markets.items():
            for p in m["betoffers"]:
                if "overround" not in p:
                    continue
                market_label = f"{p['criterion']} {p['bet_offer_type']}".strip()
                for o in sorted(p["outcomes"], key=lambda x: x["odds"]):
                    w.writerow([m["event_name"], market_label, o["name"], o["odds"],
                                round(o["implied"], 5), round(o["devig"], 5)])

    print(f"\nSaved snapshot to {out_dir}  (timestamp {hhmm})")
    print("Overrounds:")
    for k, v in prov["overrounds"].items():
        print(f"  {v:6.3f}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
