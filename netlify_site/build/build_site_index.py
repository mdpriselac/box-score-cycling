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

A one-day race (``type: one_day``) has the same shape with one unit: its
config is predictions/race/scenarios.json, its result results/race/results.csv
and its page netlify_site/<slug>-<year>.html. Every entry carries ``kind``
("stage" or "race") and ``unit`` so the frame can render either without
guessing from the stage number.

Published campaign identity is read from each campaign.json.  CAMPAIGNS below
is a compatibility fallback for an old archive without that file.
ARCHIVE_CAMPAIGNS lists earlier model-vs-market evaluation campaigns that
never published pages; they appear in /races as archive entries only.
"""

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE_DIR = HERE.parent
PROJECT_ROOT = SITE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from cycling_project.nightly import site_paths, tiers  # noqa: E402  (page names: chip W; automation tiers: chip Y)
PERF_ROOT = PROJECT_ROOT / "performance_eval"
OUT_PATH = SITE_DIR / "site-index.json"
PUBLISHED_PATH = SITE_DIR / "published-campaigns.json"

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
        "extra_pages": {"review": {"asset": "/vuelta-review.html",
                                   "title": "Post-race review"}},
    },
]


def registry_campaign(dirname):
    """Build site metadata for a campaign admitted by publication approval."""
    registry = load_json(PERF_ROOT / dirname / "campaign.json") or {}
    if not registry:
        raise ValueError(f"published campaign {dirname!r} has no campaign.json")
    year = int(registry.get("year") or str(registry.get("start_date", ""))[:4])
    site = registry.get("site") or {}
    slug = site_paths.route_slug(dirname, {**registry, "year": year})
    is_stage = bool(registry.get("is_stage_race"))
    name = str(registry.get("name") or dirname.replace("-", " ").title())
    short_name = str(site.get("short_name") or name)
    if str(year) not in short_name:
        short_name = f"{short_name} {year}"
    return {
        "dir": dirname,
        "slug": slug,
        "year": year,
        "name": name if str(year) in name else f"{name} {year}",
        "short_name": short_name,
        "type": "stage_race" if is_stage else "one_day",
        "prefix": site_paths.site_prefix(dirname, registry, is_stage_race=is_stage),
        "n_stages": len(registry.get("stages") or []) or 1,
        "start_date": registry["start_date"],
        "end_date": registry.get("end_date") or registry["start_date"],
        "blurb": str(site.get("blurb") or
                     f"Nightly model run and results record for {name}."),
        "extra_pages": dict(site.get("extra_pages") or {}),
        "automated": tiers.is_automated(registry),
    }


def published_campaigns():
    """Resolve the durable allow-list written by the operator-only promoter."""
    names = load_json(PUBLISHED_PATH) or [c["dir"] for c in CAMPAIGNS]
    legacy = {c["dir"]: c for c in CAMPAIGNS}
    out = []
    for dirname in names:
        base = legacy.get(dirname)
        out.append(load_campaign(base) if base else registry_campaign(dirname))
    return out

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


def load_campaign(camp):
    """Overlay a published campaign's committed registry record on fallback data."""
    out = dict(camp)
    registry = load_json(PERF_ROOT / camp["dir"] / "campaign.json") or {}
    site = registry.get("site") or {}
    for key in ("name", "year", "start_date", "end_date"):
        if registry.get(key) is not None:
            out[key] = registry[key]
    if "is_stage_race" in registry:
        out["type"] = "stage_race" if registry["is_stage_race"] else "one_day"
    if registry.get("stages"):
        out["n_stages"] = len(registry["stages"])
    aliases = {
        "route_slug": "slug", "prefix": "prefix", "short_name": "short_name",
        "n_stages": "n_stages", "blurb": "blurb", "extra_pages": "extra_pages",
    }
    for source, target in aliases.items():
        if source in site:
            out[target] = site[source]
    # The legacy table above and campaign.json agree today; site_paths is the
    # rule of record either way (chip W, 2026-09-22).
    out["prefix"] = site_paths.site_prefix(camp["dir"], registry, is_stage_race=out["type"] == "stage_race")
    return out


def race_url(camp):
    return f"/race/{camp['slug']}/{camp['year']}"


def is_one_day(camp):
    return camp.get("type") == "one_day"


def stage_asset(camp, n):
    name = site_paths.stage_page_name(camp["prefix"], n)
    return f"/{name}" if (SITE_DIR / name).exists() else None


def race_asset(camp):
    """The one-day race's own page, netlify_site/<slug>-<year>.html."""
    name = site_paths.oneday_page_name(camp["dir"], {"site": {"route_slug": camp["slug"]}}, year=camp["year"])
    return f"/{name}" if (SITE_DIR / name).exists() else None


def build_race_entry(camp):
    """The single unit of a one-day race, in the same shape as a stage entry."""
    pred_dir = PERF_ROOT / camp["dir"] / "predictions" / "race"
    cfg = load_json(pred_dir / "scenarios.json") or {}
    has_predictions = pred_dir.is_dir() and any(
        f.name != "scenarios.json" for f in pred_dir.glob("*.json"))
    settled = (PERF_ROOT / camp["dir"] / "results" / "race" / "results.csv").exists()
    asset = race_asset(camp)
    if settled:
        status = "settled"
    elif has_predictions or asset:
        status = "predicted"
    else:
        status = "upcoming"
    scenarios = cfg.get("scenarios") or {}
    post_hoc = bool(cfg.get("post_hoc")) or (
        bool(scenarios) and all(s.get("post_hoc") for s in scenarios.values()))
    return {
        "stage": None,
        "unit": "race",
        "kind": "race",
        "date": cfg.get("date") or camp["start_date"],
        "label": cfg.get("label") or camp["name"],
        "status": status,
        "predicted": bool(has_predictions or asset),
        "post_hoc": post_hoc,
        "url": f"{race_url(camp)}/prediction" if asset else None,
        "asset": asset,
    }


def named_asset(camp, name):
    """``/<name>`` when netlify_site/<name> exists; ``name`` already carries the prefix."""
    return f"/{name}" if (SITE_DIR / name).exists() else None


def registry_stage_label(n, row):
    """'Stage 2 — A → B, 101 km' from a campaign.json stage row (autoconfig.stage_label's shape)."""
    tail = []
    towns = row.get("towns")
    if isinstance(towns, str) and towns.strip():
        tail.append(towns.strip())
    try:
        if row.get("distance_km") not in (None, ""):
            tail.append(f"{float(row['distance_km']):g} km")
    except (TypeError, ValueError):
        pass
    return f"Stage {n} — " + ", ".join(tail) if tail else f"Stage {n}"


def build_stage_entries(camp, today):
    pred_root = PERF_ROOT / camp["dir"] / "predictions"
    res_root = PERF_ROOT / camp["dir"] / "results"

    # A stage cancelled mid-race appears in later configs' void_stages; its
    # own config predates the cancellation, so take the union.
    void = set()
    for cfg_path in pred_root.glob("stage_*/scenarios.json"):
        cfg = load_json(cfg_path) or {}
        void.update(cfg.get("void_stages") or [])

    # campaign.json's own stage rows (horizon fills towns / distance / date): the stage log's
    # source for a stage nobody has configured yet.  Until 2026-09-18 only scenarios.json was
    # read, so such a stage showed "TBC" and a blank route on the hub.
    registry = load_json(PERF_ROOT / camp["dir"] / "campaign.json") or {}
    rows = {int(s["number"]): s for s in registry.get("stages") or []
            if isinstance(s, dict) and s.get("number") is not None}

    stages = []
    for n in range(1, camp["n_stages"] + 1):
        cfg = load_json(pred_root / f"stage_{n:02d}" / "scenarios.json") or {}
        row = rows.get(n) or {}
        pred_dir = pred_root / f"stage_{n:02d}"
        non_boards = {"scenarios.json", "startlist.json", "route.json", "route_raw.json",
                      "route.override.json", "agent_key.json", "agent_key_response.json",
                      "retro_facts.json"}
        has_predictions = pred_dir.is_dir() and any(
            f.name not in non_boards and not f.name.startswith("editorial_")
            for f in pred_dir.glob("*.json"))
        settled = (res_root / f"stage_{n:02d}" / "results.csv").exists()
        asset = stage_asset(camp, n)

        stage_date = cfg.get("date") or row.get("date")
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

        label = cfg.get("label") or registry_stage_label(n, row)
        entry = {
            "stage": n,
            "unit": f"stage_{n:02d}",
            "kind": "stage",
            "date": stage_date,
            "label": label,
            "status": status,
            "predicted": bool(has_predictions or asset),
            "url": f"{race_url(camp)}/stage-{n:02d}" if asset else None,
            "asset": asset,
            "post_hoc": bool(cfg.get("post_hoc")) or (
                bool(cfg.get("scenarios")) and
                all(s.get("post_hoc") for s in cfg["scenarios"].values())),
        }
        if cfg.get("day_key"):
            entry["day_key"] = cfg["day_key"]
        stages.append(entry)
    return stages


def campaign_is_automated(camp):
    """Whether the nightly covers this race (tiers.is_automated on its campaign.json).

    A legacy CAMPAIGNS entry has no registry file; those are the Tour and the
    Vuelta, both covered.
    """
    if "automated" in camp:
        return bool(camp["automated"])
    registry = load_json(PERF_ROOT / camp["dir"] / "campaign.json") or {}
    return tiers.is_automated(registry) if registry else True


def build_campaign(camp, today):
    stages = [build_race_entry(camp)] if is_one_day(camp) else build_stage_entries(camp, today)

    start = date.fromisoformat(camp["start_date"])
    end = date.fromisoformat(camp["end_date"])
    automated = campaign_is_automated(camp)
    if today > end:
        status = "settled"
    elif today >= start:
        status = "in_progress"
    else:
        status = "upcoming"
    # Honest status for a race the nightly does not cover (owner rule, 2026-09-22).
    # Its dates say "in progress" whether or not anything was ever published, and a hub
    # entry with no page behind it reads as an automation that is running and silent.
    # With no page at all the truth is simply: not covered.
    if not automated and not any(s["asset"] for s in stages):
        status = "not_covered"

    pages = {}
    # A one-day race has neither: an empty `prefix` would otherwise match the
    # Tour's own gc.html / stages.html and steal their aliases.
    if not is_one_day(camp):
        gc_asset = named_asset(camp, site_paths.gc_tracker_name(camp["prefix"]))
        if gc_asset:
            pages["gc"] = {"url": f"{race_url(camp)}/gc", "asset": gc_asset,
                           "title": "GC tracker"}
        stages_asset = named_asset(camp, site_paths.stages_index_name(camp["prefix"]))
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
    # A board built after the race is a reconstruction; the frame says so rather
    # than letting it read as a prediction published before the start.
    post_hoc = bool(stages) and all(s.get("post_hoc") for s in stages)
    return {
        "slug": camp["slug"],
        "year": camp["year"],
        "name": camp["name"],
        "short_name": camp["short_name"],
        "type": camp["type"],
        "status": status,
        "automated": automated,
        "start_date": camp["start_date"],
        "end_date": camp["end_date"],
        "blurb": camp["blurb"],
        "campaign_dir": f"performance_eval/{camp['dir']}",
        "url": race_url(camp),
        "pages": pages,
        "stages": stages,
        "n_stages": 1 if is_one_day(camp) else camp["n_stages"],
        "n_settled": n_settled,
        "n_predicted": n_predicted,
        "post_hoc": post_hoc,
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
        "/model": {"asset": "/index.html", "chrome": True, "active": "model"},
    }
    for race in races:
        if race["status"] == "archive":
            continue
        clean[race["url"]] = {
            "asset": f"/_frame/race/{race['slug']}-{race['year']}.html"}
        for page in race["pages"].values():
            aliases[page["asset"]] = page["url"]
            clean[page["url"]] = {
                "asset": page["asset"], "base": True, "chrome": True, "active": "races"}
        for s in race["stages"]:
            if s["asset"]:
                aliases[s["asset"]] = s["url"]
                clean[s["url"]] = {
                    "asset": s["asset"], "base": True, "chrome": True, "active": "races"}
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
    races = [build_campaign(c, today) for c in published_campaigns()]
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
