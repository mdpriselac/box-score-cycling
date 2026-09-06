"""
Generate netlify_site/site-index.json from the campaign archives.

    uv run python netlify_site/build/build_site_index.py

One machine-readable index of races -> stages -> page URLs, dates, and
status, so the site frame (home / races / calendar / race hubs, built by
build_site_frame.py) and the Worker router render from data instead of
parsing HTML. Re-run whenever a new stage page is built or a stage settles,
then re-run build_site_frame.py.

Sources of truth:
  - performance_eval/<campaign>/predictions/stage_NN/scenarios.json
        stage number, date, label, day_key, void_stages
  - performance_eval/<campaign>/results/stage_NN/results.csv
        presence == the stage is settled
  - netlify_site/<prefix>stageNN.html etc.
        presence == a public page exists for the entry

The CAMPAIGNS registry below is the only hand-maintained part: identity,
slug, page prefix, and race dates for each published campaign (mirroring
CAMPAIGN_BRANDING in build_stage_page.py). ARCHIVE_CAMPAIGNS lists earlier
model-vs-market evaluation campaigns that never published pages; they appear
in /races as archive entries only.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
PERF_ROOT = PROJECT_ROOT / "performance_eval"
OUT_PATH = SITE_DIR / "site-index.json"

# Published campaigns: pages exist in netlify_site/ under `prefix`.
CAMPAIGNS = [
    {
        "dir": "tour-de-france-2026",
        "slug": "tour-de-france",
        "year": 2026,
        "name": "Tour de France 2026",
        "short_name": "TdF 2026",
        "type": "stage_race",
        "prefix": "",
        "n_stages": 21,
        "start_date": "2026-07-04",
        "end_date": "2026-07-26",
        "blurb": ("Twenty-one stages predicted the evening before and settled "
                  "the evening after — the model's first full grand tour in "
                  "public, benchmarked against the market throughout."),
        "extra_pages": {"review": {"asset": "/review.html",
                                   "title": "Post-race review"}},
    },
    {
        "dir": "vuelta-2026",
        "slug": "vuelta-a-espana",
        "year": 2026,
        "name": "Vuelta a España 2026",
        "short_name": "Vuelta 2026",
        "type": "stage_race",
        "prefix": "vuelta-",
        "n_stages": 21,
        "start_date": "2026-08-22",
        "end_date": "2026-09-13",
        "blurb": ("The live campaign: day-type keys chosen each morning, "
                  "stage predictions published before the flag drops, and a "
                  "GC tracker updated as the race reshapes itself."),
        "extra_pages": {},
    },
]

# Earlier 2026 evaluation campaigns: model-vs-market data archived in the
# repo, no published pages. `circa` is derived from capture-file dates below.
ARCHIVE_CAMPAIGNS = [
    {"dir": "strade-bianche-2026", "name": "Strade Bianche 2026", "type": "one_day"},
    {"dir": "paris-nice-2026", "name": "Paris–Nice 2026", "type": "stage_race"},
    {"dir": "tirreno-adriatico-2026", "name": "Tirreno–Adriatico 2026", "type": "stage_race"},
    {"dir": "catalunya-2026", "name": "Volta a Catalunya 2026", "type": "stage_race"},
    {"dir": "e3-2026", "name": "E3 Classic 2026", "type": "one_day"},
    {"dir": "tour-of-bruges-2026", "name": "Tour of Bruges 2026", "type": "one_day"},
    {"dir": "flanders-2026", "name": "Tour of Flanders 2026", "type": "one_day"},
    {"dir": "tour-of-the-alps-2026", "name": "Tour of the Alps 2026", "type": "stage_race"},
    {"dir": "amstel-gold-2026", "name": "Amstel Gold Race 2026", "type": "one_day"},
    {"dir": "la-fleche-wallone-2026", "name": "La Flèche Wallonne 2026", "type": "one_day"},
    {"dir": "LBL-2026", "name": "Liège–Bastogne–Liège 2026", "type": "one_day"},
    {"dir": "tour-de-romandie-2026", "name": "Tour de Romandie 2026", "type": "stage_race"},
]


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def race_url(camp):
    return f"/race/{camp['slug']}/{camp['year']}"


def stage_asset(camp, n):
    name = f"{camp['prefix']}stage{n:02d}.html"
    return f"/{name}" if (SITE_DIR / name).exists() else None


def named_asset(camp, base):
    name = f"{camp['prefix']}{base}.html"
    return f"/{name}" if (SITE_DIR / name).exists() else None


def build_stage_entries(camp, today):
    pred_root = PERF_ROOT / camp["dir"] / "predictions"
    res_root = PERF_ROOT / camp["dir"] / "results"

    # A stage cancelled mid-race appears in later configs' void_stages; its
    # own config predates the cancellation, so take the union.
    void = set()
    for cfg_path in pred_root.glob("stage_*/scenarios.json"):
        cfg = load_json(cfg_path) or {}
        void.update(cfg.get("void_stages") or [])

    stages = []
    for n in range(1, camp["n_stages"] + 1):
        cfg = load_json(pred_root / f"stage_{n:02d}" / "scenarios.json") or {}
        pred_dir = pred_root / f"stage_{n:02d}"
        has_predictions = pred_dir.is_dir() and any(
            f.name != "scenarios.json" for f in pred_dir.glob("*.json"))
        settled = (res_root / f"stage_{n:02d}" / "results.csv").exists()
        asset = stage_asset(camp, n)

        stage_date = cfg.get("date")
        if stage_date is None and n == 1:
            stage_date = camp["start_date"]

        if n in void:
            status = "cancelled"
        elif settled:
            status = "settled"
        elif has_predictions or asset:
            status = "predicted"
        else:
            status = "upcoming"

        label = cfg.get("label") or f"Stage {n}"
        entry = {
            "stage": n,
            "date": stage_date,
            "label": label,
            "status": status,
            "predicted": bool(has_predictions or asset),
            "url": f"{race_url(camp)}/stage-{n:02d}" if asset else None,
            "asset": asset,
        }
        if cfg.get("day_key"):
            entry["day_key"] = cfg["day_key"]
        stages.append(entry)
    return stages


def build_campaign(camp, today):
    stages = build_stage_entries(camp, today)

    start = date.fromisoformat(camp["start_date"])
    end = date.fromisoformat(camp["end_date"])
    if today > end:
        status = "settled"
    elif today >= start:
        status = "in_progress"
    else:
        status = "upcoming"

    pages = {}
    gc_asset = named_asset(camp, "gc")
    if gc_asset:
        pages["gc"] = {"url": f"{race_url(camp)}/gc", "asset": gc_asset,
                       "title": "GC tracker"}
    stages_asset = named_asset(camp, "stages")
    if stages_asset:
        pages["stages"] = {"url": f"{race_url(camp)}/stages",
                           "asset": stages_asset,
                           "title": "Stage-by-stage diary"}
    for key, spec in camp.get("extra_pages", {}).items():
        if (SITE_DIR / spec["asset"].lstrip("/")).exists():
            pages[key] = {"url": f"{race_url(camp)}/{key}",
                          "asset": spec["asset"], "title": spec["title"]}

    n_settled = sum(1 for s in stages if s["status"] == "settled")
    n_predicted = sum(1 for s in stages if s["predicted"])
    return {
        "slug": camp["slug"],
        "year": camp["year"],
        "name": camp["name"],
        "short_name": camp["short_name"],
        "type": camp["type"],
        "status": status,
        "start_date": camp["start_date"],
        "end_date": camp["end_date"],
        "blurb": camp["blurb"],
        "campaign_dir": f"performance_eval/{camp['dir']}",
        "url": race_url(camp),
        "pages": pages,
        "stages": stages,
        "n_stages": camp["n_stages"],
        "n_settled": n_settled,
        "n_predicted": n_predicted,
    }


def build_archive_entry(spec):
    """Archive campaigns have no pages; a circa month comes from the newest
    capture-file date in the directory, displayed month-granular only."""
    camp_dir = PERF_ROOT / spec["dir"]
    dates = []
    if camp_dir.is_dir():
        for f in camp_dir.rglob("*"):
            dates += re.findall(r"20\d{2}-\d{2}-\d{2}", f.name)
    circa = max(dates)[:7] if dates else None
    return {
        "slug": spec["dir"].lower(),
        "year": 2026,
        "name": spec["name"],
        "type": spec["type"],
        "status": "archive",
        "circa": circa,
        "campaign_dir": f"performance_eval/{spec['dir']}",
        "url": None,
        "pages": {},
        "stages": [],
    }


def build_routes(races):
    """Aliases (legacy flat path -> clean URL, served as redirects) and clean
    routes (clean URL -> asset; base=True means the asset lives at site root
    and needs <base href="/"> injected when served at a deeper path)."""
    aliases = {"/index.html": "/model"}
    clean = {
        "/": {"asset": "/_frame/home.html"},
        "/races": {"asset": "/_frame/races.html"},
        "/model": {"asset": "/index.html"},
    }
    for race in races:
        if race["status"] == "archive":
            continue
        clean[race["url"]] = {
            "asset": f"/_frame/race/{race['slug']}-{race['year']}.html"}
        for page in race["pages"].values():
            aliases[page["asset"]] = page["url"]
            clean[page["url"]] = {"asset": page["asset"], "base": True}
        for s in race["stages"]:
            if s["asset"]:
                aliases[s["asset"]] = s["url"]
                clean[s["url"]] = {"asset": s["asset"], "base": True}
    return aliases, clean


def month_range(races):
    months = set()
    for race in races:
        for s in race.get("stages", []):
            if s.get("date"):
                months.add(s["date"][:7])
    for m in sorted(months):
        yield m


def main():
    today = date.today()
    races = [build_campaign(c, today) for c in CAMPAIGNS]
    races.sort(key=lambda r: r["start_date"], reverse=True)
    archives = [build_archive_entry(a) for a in ARCHIVE_CAMPAIGNS]
    archives.sort(key=lambda a: a["circa"] or "", reverse=True)

    months = list(month_range(races))
    aliases, clean = build_routes(races)
    for m in months:
        clean[f"/calendar/{m.replace('-', '/')}"] = {
            "asset": f"/_frame/calendar/{m}.html"}

    # The month the calendar root should land on: the current month if it has
    # entries, else the nearest generated month.
    this_month = today.strftime("%Y-%m")
    default_month = this_month if this_month in months else (
        min(months, key=lambda m: abs(
            (int(m[:4]) * 12 + int(m[5:7])) -
            (today.year * 12 + today.month))) if months else None)

    index = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "site_name": "Cycling Race Predictor",
        "races": races + archives,
        "months": months,
        "default_month": default_month,
        "aliases": aliases,
        "clean_routes": clean,
    }
    OUT_PATH.write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    n_stage_pages = sum(1 for r in races for s in r["stages"] if s["asset"])
    print(f"wrote {OUT_PATH.relative_to(PROJECT_ROOT)}: "
          f"{len(races)} published races ({n_stage_pages} stage pages), "
          f"{len(archives)} archive campaigns, months {months}, "
          f"{len(aliases)} aliases, {len(clean)} clean routes")


if __name__ == "__main__":
    main()
