"""``python -m cycling_project.nightly.horizon`` — the Mac's daily handover to the cloud.

The nightly container (Anthropic Managed Agents) cannot reach FirstCycling or
ProCyclingStats — both sit behind Cloudflare — and the UCI gives it a calendar
and results but no field and no route.  Kambi lists WorldTour only.  So every
non-WorldTour race the cloud is about to preview arrives with no start list, a
calendar-shaped stage list (``stages_provisional: true``, ``towns: null``) and
nothing for ``route_facts`` to read.  2026-09-15 is the canonical week: GP de
Wallonie failed with "no start list from any source", and Abruzzo, Luxembourg,
Slovenska and Huangshan previewed with no route or stage facts at all.

This module runs on the owner's Mac (launchd, ``agents/mac/com.cycling.horizon.plist``),
before the 19:45 UTC tick.  For every unit the cloud is about to preview it:

1. captures the **start list** through the project's rate-limited scraper into
   ``cached_start_lists`` AND as ``predictions/<unit>/startlist.json`` — the
   handover shape ``oneday.load_startlist_file`` reads and
   ``predict_stage_scenarios.resolve_startlist`` prefers;
2. archives the **FirstCycling stage page** verbatim to
   ``results/<unit>/stage_page_<date>.html`` (what ``route_facts.ingest_route``
   consumes) and runs the ingest, producing ``predictions/<unit>/route.json``;
   With ``--route-research`` (PAID, off by default; chip Z1 2026-10-02) a due
   stage-race unit whose route.json is still partial/missing then gets one
   ``route_research.research_unit`` conversation (web search + fetch,
   sourced ``route_raw.json``, re-ingest), capped by ``--max-route-research``;
3. fills the campaign's **stage metadata** (date, towns, distance, kind) from
   those pages, flipping ``stages_provisional`` to false only when every stage
   is known;
4. **uploads** all of it as ``nightly-artifacts`` objects keyed
   ``<run_id>/<campaign_slug>/<relpath>``, which ``bootstrap.overlay_artifacts``
   lays over the release bundle on the next tick, and syncs the campaign /
   stage rows into the hosted registry when the stage list changed.

Everything is recorded in the ledger as a run with phase ``horizon``
(``start_run`` / ``add_step`` / ``finish_run``), so the tick can see what the
Mac supplied.  A unit that fails files an ``operator_tasks`` row of kind
``horizon_failed`` (urgency ``routine``) and the command still exits 0: one
bad race must never cost the others their handover.

Idempotent and cheap: anything fresher than ``--max-age-hours`` (default 20)
is reused, and no HTTP client is constructed at all when there is nothing to
fetch — which matters, because ``SCRAPER_USE_BROWSER=1`` opens a **visible**
Chrome window.

    uv run python -m cycling_project.nightly.horizon --store auto
    uv run python -m cycling_project.nightly.horizon --days 5 --store fake
    uv run python -m cycling_project.nightly.horizon --dry-run

``--store`` follows the driver: ``auto`` uses the hosted control plane when
Supabase operator credentials load, ``fake`` / ``--dry-run`` keep the hosted
ledger clean (**mandatory for tests and experiments**, see CLAUDE.md).  Unlike
the cloud driver this is an **operator-role** process: it runs on the Mac
(``runs.host = 'mac'``) and the registry sync is operator-only.

Never run in a tight loop: every request goes through ``WebClient``'s 3-second
minimum, and nothing here bypasses it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from cycling_project.db_path import default_db_path
from cycling_project.nightly import registry, route_facts, tiers
from cycling_project.nightly import route_research as route_research_mod
from cycling_project.nightly.crosswalk import build_operator_task
from cycling_project.nightly.driver import (
    FINISHED_AFTER_DAYS, ONE_DAY_UNIT, RACE_DAY_OVER_HOUR, Campaign, _has_scenario_boards,
    day_has_started, find_open_duplicate,
)
from cycling_project.nightly.secrets import load_local_env
from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.webscrape_tools.scrape_client import WebClient

logger = get_logger(__name__)

__version__ = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERF_EVAL = PROJECT_ROOT / "performance_eval"
BASE_URL = "https://firstcycling.com"

PHASE = "horizon"
TASK_KIND = "horizon_failed"
DEFAULT_DAYS = 3
DEFAULT_MAX_AGE_HOURS = 20.0
# One race page + one stage page per due unit is the daily cost.  The backfill
# (a stage page for a stage we have never seen) is capped so a 21-stage grand
# tour cannot turn one night into a 21-request crawl.
DEFAULT_MAX_BACKFILL = 6
# Route research is paid (one Messages conversation per unit): a hard cap per run.
DEFAULT_MAX_ROUTE_RESEARCH = 3
INDEX_NAME = "horizon_raw.json"
STARTLIST_NAME = "startlist.json"
FAKESTORE_DIRNAME = "fakestore"

# public.stages.kind is CHECK-constrained to these; a FirstCycling profile code
# ("GT2", "H") is recorded verbatim as fc_profile_code and never translated.
STAGE_KINDS = ("stage", "itt", "ttt", "gc", "one_day")
ITT_RE = re.compile(r"\b(itt|individual time trial|prologue)\b", re.IGNORECASE)
TTT_RE = re.compile(r"\b(ttt|team time trial)\b", re.IGNORECASE)


class HorizonError(Exception):
    """A unit could not be captured; the reason becomes an operator task."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False, default=str) + "\n",
                    encoding="utf-8")


def _age_hours(path: Path, *, now: Optional[dt.datetime] = None) -> Optional[float]:
    """Age of a file in hours, preferring a ``captured_at`` stamp inside it."""
    if not path.is_file():
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    stamped = None
    if path.suffix == ".json":
        doc = _read_json(path)
        if isinstance(doc, dict):
            stamped = doc.get("captured_at") or doc.get("acquired_at") or doc.get("fetched_at")
    if stamped:
        try:
            when = dt.datetime.fromisoformat(str(stamped))
            if when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
            return (now - when).total_seconds() / 3600.0
        except ValueError:
            pass
    mtime = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
    return (now - mtime).total_seconds() / 3600.0


def _is_fresh(path: Path, max_age_hours: float, *, now: Optional[dt.datetime] = None) -> bool:
    age = _age_hours(path, now=now)
    return age is not None and age <= max_age_hours


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _newest_stage_page(results_unit_dir: Path) -> Optional[Path]:
    """The archive ``route_facts`` would read (same glob, same ordering)."""
    return route_facts.newest_fc_archive(results_unit_dir) if results_unit_dir.is_dir() else None


# ---------------------------------------------------------------------------
# fetching (lazy: no client, no Chrome window, unless something is due)
# ---------------------------------------------------------------------------

@dataclass
class Fetcher:
    """Lazily-built ``WebClient``; counts requests so a run can prove its cost."""

    factory: Optional[Callable[[], Any]] = None
    client: Any = None
    requests_made: int = 0

    def get(self, url: str) -> Any:
        if self.client is None:
            self.client = (self.factory or (lambda: WebClient(BASE_URL)))()
        self.requests_made += 1
        response = self.client.get(url)
        status = getattr(response, "status_code", 200)
        if status != 200:
            raise HorizonError(f"{url} returned HTTP {status}")
        text = getattr(response, "text", "") or ""
        if "<body" not in text.lower():
            raise HorizonError(f"{url} returned no page body ({len(text)} bytes)")
        return response

    def close(self) -> None:
        if self.client is not None:
            try:
                self.client.close()
            except Exception:  # noqa: BLE001 — closing must never fail a run
                pass
            self.client = None


def race_url(fc_race_id: str, year: int, stage: Optional[int] = None) -> str:
    url = f"{BASE_URL}/race.php?r={fc_race_id}&y={year}"
    return url if stage is None else f"{url}&e={int(stage):02d}"


# ---------------------------------------------------------------------------
# selection
# ---------------------------------------------------------------------------

@dataclass
class Due:
    """One campaign and the units whose preview falls inside the horizon."""

    campaign: Campaign
    units: List[str] = field(default_factory=list)
    plan: Dict[str, Any] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return self.campaign.slug


def has_boards(pred_dir: Path) -> bool:
    """The driver's own board test (``driver._has_scenario_boards``).

    Until 2026-09-16 this carried its own copy of the preview rule, because
    ``startlist.json`` — the handover this module writes — was missing from the
    driver's ``NON_BOARD_JSON`` and read there as a rendered board, so a unit
    with only a start list looked already previewed.  The fix landed in
    ``driver.py`` the same day (``startlist.json`` and ``horizon_raw.json`` are
    in the set), so the due logic here is the driver's, unmodified.
    """
    return _has_scenario_boards(pred_dir)


def preview_due(campaign: Campaign, *, days: int, today: dt.date,
                void: Optional[Sequence[int]] = None,
                local_now: Optional[dt.datetime] = None) -> List[str]:
    """Units whose preview falls inside the horizon (the driver's rule).

    "Still ahead" is the driver's race-local clock (``driver.day_has_started``), not
    ``today < d``: at 17:30 UTC it is already the small hours of the next day in
    Asia/Shanghai, and the cloud tick two hours later previews THAT day's stage — the
    date test skipped it and captured the day after (Tour of Huangshan, 2026-09-18).
    A bare ``today`` with no clock reads as that evening, as it does in the driver.
    The window is deliberately not shortened the way the driver's is: capturing one
    unit more than the tick previews costs nothing.
    """
    if local_now is None:
        local_now = dt.datetime.combine(today, dt.time(RACE_DAY_OVER_HOUR, 0))
    void_set = set(campaign.void_stages) | {int(v) for v in (void or [])}
    if campaign.is_stage_race:
        entries = [(int(s["number"]), s.get("date")) for s in campaign.stages]
    else:
        entries = [(None, campaign.stage_date(None))]
    dated = [dt.date.fromisoformat(d) for _n, d in entries if d]
    if dated and max(dated) < today - dt.timedelta(days=FINISHED_AFTER_DAYS):
        return []                                    # the campaign is over
    due = []
    for number, date_s in sorted(entries, key=lambda t: (t[0] is None, t[0] or 0)):
        if not date_s or (number is not None and number in void_set):
            continue
        d = dt.date.fromisoformat(date_s)
        unit = campaign.unit_for(number)
        if (not day_has_started(d, local_now) and d <= today + dt.timedelta(days=days)
                and not has_boards(campaign.pred_dir(unit))):
            due.append(unit)
    return due


def select_units(perf_eval: Path, store: Any, *, days: int = DEFAULT_DAYS,
                 today: Optional[dt.date] = None,
                 only: Optional[Sequence[str]] = None,
                 local_now: Optional[dt.datetime] = None,
                 automation_tiers: Optional[Sequence[str]] = None) -> List[Due]:
    """Campaigns with a preview due inside ``days``, in date order.

    The same units the cloud is about to preview: the first stage or the
    one-day race of a race starting soon, and the next unraced stages of a race
    in progress.  Void stages (both the config's and the hosted registry's),
    units that already have boards and campaigns whose last unit is long past
    are all excluded.

    A campaign the unattended nightly does not cover is skipped too (owner rule,
    2026-09-22: WorldTour and .Pro).  There is nothing to hand over to a tick
    that will never ask.  ``automation_tiers`` — from ``--all-tiers`` /
    ``--include-tier`` — widens the set for an attended Mac capture; an explicit
    ``--campaign`` does not, so the rule stays one rule.
    """
    out: List[Due] = []
    wanted = {str(s) for s in only} if only else None
    for config in sorted(Path(perf_eval).glob("*/campaign.json")):
        slug = config.parent.name
        if wanted and slug not in wanted and (_read_json(config, {}) or {}).get("slug") not in wanted:
            continue
        try:
            campaign = Campaign.load(config.parent)
        except Exception as exc:  # noqa: BLE001 — a malformed file must not stop the sweep
            logger.warning("skipping %s: %s", slug, exc)
            continue
        if not campaign.fc_race_id or not campaign.year:
            continue
        skipped = tiers.skip_reason(campaign.cfg, tiers=automation_tiers)
        if skipped:
            logger.info("skipping %s: %s", campaign.slug, skipped)
            continue
        # The race-local clock, as the driver reads it: ``--local-now`` wins, a bare ``--today``
        # is that evening, else the campaign's own zone.
        clock = local_now or (None if today else campaign.local_now())
        day = today or (clock.date() if clock else campaign.today())
        store_void = []
        try:
            for row in store.stages(campaign.slug) or []:
                number = Campaign.stage_of(str(row.get("unit") or ""))
                if row.get("void") and number is not None:
                    store_void.append(number)
        except Exception:  # noqa: BLE001 — the registry is an optimisation here
            pass
        units = preview_due(campaign, days=days, today=day, void=store_void, local_now=clock)
        if units:
            out.append(Due(campaign=campaign, units=units,
                           plan={"today": str(day), "preview": units,
                                 "local_now": clock.isoformat(timespec="minutes") if clock else None}))
    return sorted(out, key=lambda d: d.campaign.stage_date(Campaign.stage_of(d.units[0])) or "")


# ---------------------------------------------------------------------------
# start list
# ---------------------------------------------------------------------------

def startlist_document(campaign: Campaign, teams: List[Any], *, source: str) -> Dict[str, Any]:
    """``startlist.json`` in the shape ``oneday.load_startlist_file`` reads."""
    return {
        "fc_race_id": str(campaign.fc_race_id),
        "year": int(campaign.year),
        "source": source,
        "captured_at": _utcnow(),
        "captured_by": f"horizon {__version__}",
        "teams": [
            {"name": team.name, "team_id": team.team_id,
             "riders": [{"name": rider.name, "rider_id": rider.rider_id,
                         "number": rider.number} for rider in team.riders]}
            for team in teams
        ],
    }


def capture_startlist(campaign: Campaign, units: Sequence[str], *, db_path: Optional[Path],
                      max_age_hours: float, dry_run: bool = False,
                      now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """Refresh ``cached_start_lists`` and write the handover beside each config.

    The completeness check is the existing one (``future_race_loader``'s
    ``MIN_STARTLIST_RIDERS`` + "every rider linked", commit e019cc3): a
    preliminary FirstCycling team shell raises rather than freezing a field
    nobody can serve.  ``force_refresh`` is used when the cached copy is older
    than ``--max-age-hours``, so a withdrawal the day before a race is picked up.
    """
    from cycling_project.prediction_tools import future_race_loader as frl

    targets = [campaign.pred_dir(u) / STARTLIST_NAME for u in _startlist_units(campaign, units)]
    fresh = [t for t in targets if _is_fresh(t, max_age_hours, now=now)]
    if targets and len(fresh) == len(targets):
        return {"state": "skipped", "reason": "handover fresh", "files": [str(t) for t in targets]}
    if dry_run:
        return {"state": "planned", "files": [str(t) for t in targets]}

    stale_cache = not any(_is_fresh(t, max_age_hours, now=now) for t in targets)
    teams, from_cache = frl.scrape_or_load_startlist(
        int(campaign.fc_race_id), int(campaign.year),
        force_refresh=stale_cache, db_path=str(db_path) if db_path else None)
    if not teams:
        raise HorizonError(f"FirstCycling returned no start list for race {campaign.fc_race_id} "
                           f"{campaign.year}")
    doc = startlist_document(campaign, teams, source="cache" if from_cache else race_url(
        campaign.fc_race_id, campaign.year) + "&k=8")
    written = []
    for target in targets:
        _write_json(target, doc)
        written.append(str(target))
    riders = sum(len(t["riders"]) for t in doc["teams"])
    return {"state": "ok", "from_cache": from_cache, "teams": len(doc["teams"]),
            "riders": riders, "files": written}


def _startlist_units(campaign: Campaign, units: Sequence[str]) -> List[str]:
    """Where the handover goes: every due unit, plus every unit not yet settled.

    It is one list for the whole race and writing it costs no request, so every
    stage that has no ``results.csv`` yet (and is not void) gets a copy — which
    unit the cloud previews next is the driver's decision, made hours later on a
    clock this capture cannot see (2026-09-18: the list sat in ``stage_03`` while
    the tick wanted ``stage_02``).  ``resolve_startlist`` also falls back to a
    sibling unit's copy, so this is belt and braces.
    """
    if campaign.is_stage_race:
        void = set(campaign.void_stages)
        unsettled = [campaign.unit_for(int(s["number"])) for s in campaign.stages
                     if int(s["number"]) not in void
                     and not (campaign.results_dir(campaign.unit_for(int(s["number"]))) / "results.csv").exists()]
    else:
        unsettled = [] if (campaign.results_dir(ONE_DAY_UNIT) / "results.csv").exists() else [ONE_DAY_UNIT]
    ordered = list(dict.fromkeys([*units, *unsettled]))
    return [u for u in ordered if u != "gc"]


# ---------------------------------------------------------------------------
# stage pages and route facts
# ---------------------------------------------------------------------------

def archive_page(results_unit_dir: Path, name: str, url: str, text: str,
                 *, now: Optional[dt.datetime] = None) -> Dict[str, Any]:
    """Write a page verbatim and record it in ``horizon_raw.json``.

    Naming follows the existing archive discipline: ``stage_page_<date>.html``
    (what ``capture_results.py`` writes and ``route_facts`` globs) beside a
    small index with the url, the fetch time and the sha256 — the same
    provenance ``uci_acquire`` keeps for a UCI capture.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    results_unit_dir.mkdir(parents=True, exist_ok=True)
    path = results_unit_dir / name
    data = text.encode("utf-8")
    path.write_bytes(data)
    index = _read_json(results_unit_dir / INDEX_NAME, {}) or {}
    index.setdefault("capturer", f"horizon {__version__}")
    index["captured_at"] = now.isoformat(timespec="seconds")
    pages = index.setdefault("pages", {})
    pages[name] = {"source_url": url, "fetched_at": now.isoformat(timespec="seconds"),
                   "bytes": len(data), "sha256": _sha256(data)}
    _write_json(results_unit_dir / INDEX_NAME, index)
    return {"file": str(path), "sha256": _sha256(data), "bytes": len(data)}


def parse_stage_facts(html: str) -> Dict[str, Any]:
    """Date, towns, distance and kind from one FirstCycling stage page.

    Distance and the two towns come from ``route_facts.parse_fc_stage_page``
    (the Information ``div.sideBox``), the date from
    ``get_race_results.extract_race_date`` (which handles both the old
    ``div#race h2`` and the 2026-08 ``div#raceSub`` markup).  ``kind`` is only
    set when the page says so in words — ``itt`` / ``ttt`` — because
    ``public.stages.kind`` is a CHECK-constrained vocabulary and a FirstCycling
    profile code is not a member of it.  The code is kept verbatim as
    ``fc_profile_code``; nothing is translated.
    """
    from bs4 import BeautifulSoup

    from cycling_project.webscrape_tools.get_race_results import extract_race_date

    soup = BeautifulSoup(html, "html.parser")
    facts: Dict[str, Any] = {}
    side = route_facts.parse_fc_stage_page(html)
    if side.get("distance_km") is not None:
        facts["distance_km"] = side["distance_km"]
    if side.get("start") and side.get("finish"):
        facts["towns"] = f"{side['start']} → {side['finish']}"
    if side.get("fc_profile_code"):
        facts["fc_profile_code"] = side["fc_profile_code"]
    try:
        date_s = extract_race_date(soup)
    except Exception:  # noqa: BLE001 — a markup change must not fail the capture
        date_s = None
    if date_s:
        facts["date"] = date_s
    header = " ".join(
        el.get_text(" ", strip=True)
        for el in (soup.find("div", id="raceSub"), soup.find("div", id="race"), soup.find("title"))
        if el is not None)
    if TTT_RE.search(header):
        facts["kind"] = "ttt"
    elif ITT_RE.search(header):
        facts["kind"] = "itt"
    return facts


def fc_stage_numbers(html: str) -> List[int]:
    """The race page's stage selector, as numbers (``0`` = GC, dropped)."""
    from bs4 import BeautifulSoup

    from cycling_project.webscrape_tools.create_race_data import extract_stages_with_links

    stages = extract_stages_with_links(BeautifulSoup(html, "html.parser")) or {}
    numbers = []
    for value in stages.values():
        value = str(value or "").strip()
        if value.isdigit() and int(value) > 0:
            numbers.append(int(value))
    return sorted(set(numbers))


def capture_stage_page(fetcher: Fetcher, campaign: Campaign, unit: str, *,
                       max_age_hours: float, now: Optional[dt.datetime] = None,
                       dry_run: bool = False, cached_html: Optional[str] = None) -> Dict[str, Any]:
    """Archive a unit's FirstCycling page and run ``ingest_route`` over it."""
    results = campaign.results_dir(unit)
    existing = _newest_stage_page(results)
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
    if existing is not None and _is_fresh(existing, max_age_hours, now=now):
        html = existing.read_text(encoding="utf-8", errors="replace")
        page = {"state": "skipped", "reason": "archive fresh", "file": str(existing)}
    elif dry_run:
        return {"state": "planned", "url": race_url(campaign.fc_race_id, campaign.year,
                                                    Campaign.stage_of(unit))}
    else:
        stage = Campaign.stage_of(unit)
        url = race_url(campaign.fc_race_id, campaign.year, stage)
        html = cached_html if cached_html is not None else fetcher.get(url).text
        page = {"state": "ok", **archive_page(results, f"stage_page_{stamp}.html", url, html, now=now)}
    facts = parse_stage_facts(html)
    route = route_facts.ingest_route(campaign.dir, unit)
    return {**page, "facts": facts, "route_grade": route.get("route_facts"),
            "route_file": str(campaign.pred_dir(unit) / "route.json")}


# ---------------------------------------------------------------------------
# campaign.json stage metadata
# ---------------------------------------------------------------------------

def update_stages(campaign: Campaign, facts: Dict[Optional[int], Dict[str, Any]],
                  *, fc_numbers: Optional[List[int]] = None,
                  dry_run: bool = False) -> Dict[str, Any]:
    """Fill stage rows from captured pages; flip the provisional flag when whole.

    The chip-D gate holds: ``registry.merge_new_information`` fills only fields
    that were absent and appends a stage number the campaign does not have
    **only** while ``stages_provisional`` is true.  While provisional the
    FirstCycling stage selector is also authoritative on *how many* stages
    there are, so a calendar-invented rest-day stage is dropped — that is the
    whole point of the flag.  A campaign that has already declared its stages
    is never restructured here.
    """
    config = dict(campaign.cfg)
    before = json.dumps(config.get("stages"), sort_keys=True)
    provisional = bool(config.get("stages_provisional"))
    one_day = not config.get("is_stage_race", True)
    dropped: List[int] = []

    if provisional and fc_numbers and not one_day:
        keep = set(fc_numbers)
        stages = [s for s in (config.get("stages") or []) if s.get("number") in keep]
        dropped = sorted({int(s["number"]) for s in (config.get("stages") or [])
                          if s.get("number") is not None and int(s["number"]) not in keep})
        known = {s.get("number") for s in stages}
        for number in fc_numbers:
            if number not in known:
                stages.append({"number": number, "date": None, "towns": None,
                               "distance_km": None, "kind": None})
        config["stages"] = sorted(stages, key=lambda s: int(s["number"]))

    proposed = []
    for number, parsed in facts.items():
        row = {"number": number}
        for key in ("date", "towns", "distance_km", "kind", "fc_profile_code"):
            if parsed.get(key) is not None:
                row[key] = parsed[key]
        if row.get("kind") not in STAGE_KINDS:
            row.pop("kind", None)
        proposed.append(row)
    if proposed:
        merged = registry.merge_new_information(config, {"stages": proposed})
        config = merged if isinstance(merged, dict) else config

    complete = bool(config.get("stages")) and all(
        s.get("date") and s.get("towns") and s.get("distance_km") is not None
        for s in (config.get("stages") or []))
    flipped = False
    if provisional and complete:
        config["stages_provisional"] = False
        flipped = True

    changed = json.dumps(config, sort_keys=True, default=str) != json.dumps(
        campaign.cfg, sort_keys=True, default=str)
    stages_changed = json.dumps(config.get("stages"), sort_keys=True, default=str) != before
    if changed and not dry_run:
        registry._write_campaign_json(campaign.dir / "campaign.json", config, campaign.cfg)
        campaign.cfg = config
    return {"state": "ok" if changed else "unchanged", "changed": changed,
            "stages_changed": stages_changed, "provisional_cleared": flipped,
            "still_provisional": bool(config.get("stages_provisional")),
            "dropped_stages": dropped,
            "filled": sorted(str(n) for n in facts)}


# ---------------------------------------------------------------------------
# the store side
# ---------------------------------------------------------------------------

def resolve_store(kind: str, root: Optional[Path], *, dry_run: bool) -> Any:
    """Mirror of ``driver.resolve_store``, at the **operator** role.

    The horizon runs on the Mac: its runs are ``host = 'mac'`` and the registry
    sync (``sync_campaign`` / ``sync_stages``) is operator-only.  Without
    operator credentials it falls back to a ``FakeStore`` and says so rather
    than writing half a handover into the hosted ledger.
    """
    from cycling_project.nightly import store as _store

    if dry_run or kind == "fake":
        return _store.FakeStore(Path(root or (PERF_EVAL / "runs" / FAKESTORE_DIRNAME)), role="operator")
    load_local_env()
    have = bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY"))
    if kind == "supabase" or (kind == "auto" and have):
        if not have:
            raise HorizonError("SUPABASE_URL and SUPABASE_SECRET_KEY are required for --store supabase")
        return _store.SupabaseStore(role="operator")
    base = root or (PERF_EVAL / "runs" / FAKESTORE_DIRNAME)
    logger.info("no Supabase operator credentials; using FakeStore at %s", base)
    return _store.FakeStore(Path(base), role="operator")


def upload_files(store: Any, run_id: str, campaign: Campaign, paths: Sequence[Path]) -> List[str]:
    """Upload each file as ``<run_id>/<campaign_slug>/<relpath>``.

    That is the driver's key convention (``Driver._upload``), and the one
    ``bootstrap.overlay_artifacts`` unwinds: it drops the run id and lays the
    rest over ``performance_eval/`` in the container.
    """
    from cycling_project.nightly.store import StoreConflictError

    uploaded: List[str] = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(campaign.dir)
        except ValueError:
            continue
        key = f"{campaign.slug}/{rel.as_posix()}"
        try:
            uploaded.append(store.upload_artifact(run_id, key, path.read_bytes()))
        except StoreConflictError:
            uploaded.append(f"{key} (exists)")
    return uploaded


def sync_registry(store: Any, campaign: Campaign) -> Dict[str, Any]:
    """Push the campaign and its stage rows to the hosted registry."""
    from cycling_project.nightly.store import StorePermissionError

    config = campaign.cfg
    try:
        store.sync_campaign(registry._campaign_row(config))
        rows = registry._stage_rows(config)
        store.sync_stages(rows)
    except StorePermissionError as exc:
        return {"state": "skipped", "reason": f"registry sync needs the operator role ({exc})"}
    return {"state": "ok", "stages": len(config.get("stages") or [])}


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

class Run:
    """One campaign's handover: a ledger run, a list of steps, a summary line."""

    def __init__(self, store: Any, due: Due, *, dry_run: bool, quiet: bool = False):
        self.store, self.due, self.dry_run, self.quiet = store, due, dry_run, quiet
        self.campaign = due.campaign
        self.steps: List[Dict[str, Any]] = []
        self.run_id: Optional[str] = None
        self.task: Optional[Dict[str, Any]] = None

    def say(self, line: str) -> None:
        if not self.quiet:
            print(line, flush=True)

    def start(self) -> None:
        unit = self.due.units[0] if self.due.units else None
        try:
            row = self.store.start_run(self.campaign.slug, unit, PHASE, meta={
                "host": "mac", "capturer": f"horizon {__version__}",
                "units": list(self.due.units), "dry_run": self.dry_run})
            self.run_id = str(row.get("run_id") or row.get("id"))
        except Exception as exc:  # noqa: BLE001 — the ledger is never the reason a capture stops
            logger.warning("%s: start_run failed (%s); continuing without a ledger run",
                           self.campaign.slug, exc)

    def step(self, name: str, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        started = _utcnow()
        t0 = time.time()
        try:
            detail = fn() or {}
        except Exception as exc:  # noqa: BLE001 — recorded, then re-raised to the unit loop
            self._add(name, "failed", started, t0, {"error": str(exc),
                                                    "error_class": type(exc).__name__})
            raise
        state = "skipped" if detail.get("state") in ("skipped", "planned") else "ok"
        self._add(name, state, started, t0, detail)
        return detail

    def _add(self, name: str, state: str, started: str, t0: float, detail: Dict[str, Any]) -> None:
        self.steps.append({"step": name, "state": state, **detail})
        if not self.run_id:
            return
        try:
            self.store.add_step(self.run_id, name, state, started_at=started, finished_at=_utcnow(),
                                duration_ms=int((time.time() - t0) * 1000), detail=detail)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: add_step(%s) failed (%s)", self.campaign.slug, name, exc)

    def fail(self, summary: str, detail: Dict[str, Any]) -> None:
        """File the ``horizon_failed`` task and finish the run; never raise."""
        task = build_operator_task(TASK_KIND, self.campaign.slug, summary,
                                   {**detail, "units": list(self.due.units),
                                    "run_id": self.run_id, "capturer": f"horizon {__version__}"},
                                   urgency="routine")
        self.task = task
        try:
            duplicate = find_open_duplicate(self.store, task)   # a daily job must not file the same ask daily
            if duplicate:
                logger.info("%s: same ask already open as task %s; not filed again", self.campaign.slug, duplicate.get("id"))
                detail = {**detail, "duplicate_of": duplicate.get("id")}
            else:
                self.store.insert_task(task)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: insert_task failed (%s)", self.campaign.slug, exc)
        self.finish("failed", 20, {"summary": summary, **detail})

    def finish(self, state: str, exit_code: int, detail: Dict[str, Any]) -> None:
        if not self.run_id:
            return
        try:
            self.store.finish_run(self.run_id, state, exit_code, detail)
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s: finish_run failed (%s)", self.campaign.slug, exc)


def capture_campaign(due: Due, store: Any, *, fetcher: Fetcher, db_path: Optional[Path],
                     max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
                     max_backfill: int = DEFAULT_MAX_BACKFILL, backfill: bool = True,
                     dry_run: bool = False, now: Optional[dt.datetime] = None,
                     quiet: bool = False, route_research_enabled: bool = False,
                     researcher: Optional[Callable[[Path, str], Dict[str, Any]]] = None,
                     research_budget: Optional[Dict[str, int]] = None,
                     automation_tiers: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Capture one campaign's handover.  Never raises: a failure files a task."""
    campaign = due.campaign
    run = Run(store, due, dry_run=dry_run, quiet=quiet)
    run.start()
    out: Dict[str, Any] = {"campaign": campaign.slug, "units": list(due.units),
                           "run_id": run.run_id, "dry_run": dry_run, "steps": []}
    facts: Dict[Optional[int], Dict[str, Any]] = {}
    written: List[Path] = []
    fc_numbers: Optional[List[int]] = None
    try:
        # -- the race page: the stage selector, and for a one-day the race page
        #    IS the stage page route_facts reads.
        if campaign.is_stage_race:
            def _race_page() -> Dict[str, Any]:
                nonlocal fc_numbers
                archive = campaign.dir / "results" / "race_page"
                newest = sorted(archive.glob("race_page_*.html"))
                if newest and _is_fresh(newest[-1], max_age_hours, now=now):
                    fc_numbers = fc_stage_numbers(newest[-1].read_text(encoding="utf-8",
                                                                       errors="replace"))
                    return {"state": "skipped", "reason": "archive fresh", "file": str(newest[-1]),
                            "stages_listed": len(fc_numbers)}
                url = race_url(campaign.fc_race_id, campaign.year)
                if dry_run:
                    return {"state": "planned", "url": url}
                html = fetcher.get(url).text
                stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y-%m-%d")
                info = archive_page(archive, f"race_page_{stamp}.html", url, html, now=now)
                fc_numbers = fc_stage_numbers(html)
                return {"state": "ok", "stages_listed": len(fc_numbers), **info}

            run.step("race_page", _race_page)

        # -- the start list
        run.step("startlist", lambda: capture_startlist(
            campaign, due.units, db_path=db_path, max_age_hours=max_age_hours,
            dry_run=dry_run, now=now))
        for unit in _startlist_units(campaign, due.units):
            written.append(campaign.pred_dir(unit) / STARTLIST_NAME)

        # -- one stage page per due unit, then route facts
        units = list(due.units)
        opportunistic: set = set()
        if backfill and campaign.is_stage_race:
            unseen = [n for n in (fc_numbers or [])
                      if campaign.unit_for(n) not in units
                      and _newest_stage_page(campaign.results_dir(campaign.unit_for(n))) is None
                      and n not in campaign.void_stages]
            opportunistic = {campaign.unit_for(n) for n in unseen[:max_backfill]}
            units += sorted(opportunistic)
        for unit in units:
            stage = Campaign.stage_of(unit)

            def _unit(unit=unit, stage=stage) -> Dict[str, Any]:
                # A one-day race has no stage selector and no &e page: its race
                # page IS the stage page, fetched here, once.
                result = capture_stage_page(fetcher, campaign, unit, max_age_hours=max_age_hours,
                                            now=now, dry_run=dry_run)
                if result.get("facts"):
                    facts[stage] = result["facts"]
                return result

            try:
                detail = run.step(f"unit:{unit}", _unit)
            except Exception as exc:  # noqa: BLE001
                if unit not in opportunistic:
                    raise
                # A stage the race has not published yet is not a failure: the
                # backfill is opportunistic, the due units are the contract.
                run.say(f"  {campaign.slug} {unit}: backfill skipped — {exc}")
                continue
            if not dry_run:
                written.append(campaign.pred_dir(unit) / "route.json")
                page = _newest_stage_page(campaign.results_dir(unit))
                if page is not None:
                    written.append(page)
                    written.append(campaign.results_dir(unit) / INDEX_NAME)
            run.say(f"  {campaign.slug} {unit}: {detail.get('state')} "
                    f"route={detail.get('route_grade')} "
                    f"{'/'.join(k for k in ('date', 'towns', 'distance_km') if (detail.get('facts') or {}).get(k))}")

        # -- route research (paid, opt-in: --route-research; chip Z1 2026-10-02).  Due
        #    units only, never the opportunistic backfill; one attempt per unit
        #    (route_research.needs_research), so a re-run tomorrow costs nothing.
        if route_research_enabled and campaign.is_stage_race and not dry_run:
            for unit in due.units:
                if research_budget is not None and research_budget["left"] <= 0:
                    break
                needed, why = route_research_mod.needs_research(
                    campaign.dir, unit, campaign.cfg, covered=automation_tiers)
                if not needed:
                    continue
                if research_budget is not None:
                    research_budget["left"] -= 1

                def _research(unit=unit) -> Dict[str, Any]:
                    return (researcher or route_research_mod.research_unit)(campaign.dir, unit)

                try:
                    detail = run.step(f"route_research:{unit}", _research)
                except Exception as exc:  # noqa: BLE001 — research is an extra, never the handover
                    run.say(f"  {campaign.slug} {unit}: route research failed — {exc}")
                    continue
                pred = campaign.pred_dir(unit)
                written += [pred / route_research_mod.RAW_NAME, pred / route_research_mod.LOG_NAME,
                            pred / "route.json"]
                run.say(f"  {campaign.slug} {unit}: route research {detail.get('status')} "
                        f"route={detail.get('route_facts')} cost=${detail.get('cost_usd')}")

        # -- campaign.json
        stages = run.step("stages", lambda: update_stages(
            campaign, facts, fc_numbers=fc_numbers, dry_run=dry_run))
        if stages.get("changed") and not dry_run:
            written.append(campaign.dir / "campaign.json")

        # -- upload + registry
        if run.run_id and not dry_run:
            uploaded = run.step("upload", lambda: {
                "state": "ok", "keys": upload_files(store, run.run_id, campaign,
                                                    list(dict.fromkeys(written)))})
            out["uploaded"] = uploaded.get("keys") or []
        if stages.get("changed") and not dry_run:
            run.step("registry_sync", lambda: sync_registry(store, campaign))
        run.finish("ok", 0, {"units": list(due.units), "requests": fetcher.requests_made})
        out["status"] = "ok"
    except Exception as exc:  # noqa: BLE001 — one race's failure costs only that race
        logger.warning("%s: horizon capture failed (%s)", campaign.slug, exc)
        run.fail(f"horizon capture failed for {campaign.slug}: {exc}",
                 {"error": str(exc), "error_class": type(exc).__name__})
        out.update({"status": "failed", "error": str(exc), "error_class": type(exc).__name__,
                    "operator_task": run.task})
        run.say(f"  {campaign.slug}: FAILED — {exc} (operator task filed)")
    out["steps"] = run.steps
    return out


def run_horizon(*, days: int = DEFAULT_DAYS, store: Any = None, perf_eval: Optional[Path] = None,
                db_path: Optional[Path] = None, max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
                max_backfill: int = DEFAULT_MAX_BACKFILL, backfill: bool = True,
                dry_run: bool = False, today: Optional[dt.date] = None,
                now: Optional[dt.datetime] = None, only: Optional[Sequence[str]] = None,
                local_now: Optional[dt.datetime] = None,
                automation_tiers: Optional[Sequence[str]] = None,
                client_factory: Optional[Callable[[], Any]] = None,
                quiet: bool = False, route_research_enabled: bool = False,
                researcher: Optional[Callable[[Path, str], Dict[str, Any]]] = None,
                max_route_research: int = DEFAULT_MAX_ROUTE_RESEARCH) -> Dict[str, Any]:
    """Select, capture, upload — the whole daily pass.  Returns the summary."""
    perf_eval = Path(perf_eval or PERF_EVAL)
    due = select_units(perf_eval, store, days=days, today=today, only=only, local_now=local_now,
                       automation_tiers=automation_tiers)
    fetcher = Fetcher(factory=client_factory)
    summary: Dict[str, Any] = {
        "capturer": f"horizon {__version__}", "as_of": _utcnow(),
        "today": str(today or dt.date.today()), "days": days, "dry_run": dry_run,
        "automation_tiers": list(automation_tiers if automation_tiers is not None
                                 else tiers.AUTOMATION_TIERS),
        "store": type(store).__name__, "campaigns": [],
    }
    if not quiet:
        print(f"horizon {__version__}: {len(due)} campaign(s) due within {days} day(s)", flush=True)
    budget = {"left": max_route_research}
    summary["route_research"] = bool(route_research_enabled)
    try:
        for item in due:
            summary["campaigns"].append(capture_campaign(
                item, store, fetcher=fetcher, db_path=db_path, max_age_hours=max_age_hours,
                max_backfill=max_backfill, backfill=backfill, dry_run=dry_run, now=now,
                quiet=quiet, route_research_enabled=route_research_enabled, researcher=researcher,
                research_budget=budget, automation_tiers=automation_tiers))
    finally:
        fetcher.close()
    summary["requests_made"] = fetcher.requests_made
    summary["failed"] = [c["campaign"] for c in summary["campaigns"] if c.get("status") == "failed"]
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m cycling_project.nightly.horizon",
        description="Mac-side daily capture of what the cloud cannot fetch: start lists, "
                    "stage pages, route facts and stage metadata.")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS,
                   help=f"preview horizon in days (default {DEFAULT_DAYS})")
    p.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS,
                   help=f"reuse anything younger than this (default {DEFAULT_MAX_AGE_HOURS})")
    p.add_argument("--campaign", action="append", default=None,
                   help="limit to this campaign slug (repeatable)")
    p.add_argument("--store", choices=("auto", "supabase", "fake"), default="auto")
    p.add_argument("--store-root", type=Path, default=None, help="FakeStore directory")
    p.add_argument("--dry-run", action="store_true",
                   help="select and report; fetch nothing, write nothing, fake store")
    p.add_argument("--today", type=dt.date.fromisoformat, default=None,
                   help="date override for replay (YYYY-MM-DD)")
    p.add_argument("--local-now", type=dt.datetime.fromisoformat, default=None,
                   help="race-local wall-clock override, ISO datetime (replay); the driver's flag, same meaning")
    p.add_argument("--db-path", type=Path, default=None, help="SQLite database (start-list cache)")
    p.add_argument("--no-backfill", action="store_true",
                   help="only fetch pages for due units, never for stages never seen")
    p.add_argument("--max-backfill", type=int, default=DEFAULT_MAX_BACKFILL,
                   help=f"cap on never-seen stage pages per campaign (default {DEFAULT_MAX_BACKFILL})")
    p.add_argument("--route-research", action="store_true",
                   help="PAID: research sourced route facts (climbs, vertical, finale) for due "
                        "stage-race units whose route.json is partial/missing (route_research.py)")
    p.add_argument("--max-route-research", type=int, default=DEFAULT_MAX_ROUTE_RESEARCH,
                   help=f"cap on researched units per run (default {DEFAULT_MAX_ROUTE_RESEARCH})")
    p.add_argument("--performance-eval", type=Path, default=PERF_EVAL)
    p.add_argument("--quiet", action="store_true", help="JSON summary only")
    tiers.add_tier_flags(p)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    # The environment is loaded inside resolve_store, and only for a hosted
    # store: `--store fake` / `--dry-run` must not so much as read the secrets
    # file (a test that loads it leaks credentials into every later test).
    try:
        store = resolve_store(args.store, args.store_root, dry_run=args.dry_run)
    except HorizonError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=1))
        return 20
    summary = run_horizon(
        days=args.days, store=store, perf_eval=args.performance_eval,
        db_path=args.db_path or default_db_path(), max_age_hours=args.max_age_hours,
        max_backfill=args.max_backfill, backfill=not args.no_backfill, dry_run=args.dry_run,
        today=args.today, local_now=args.local_now, only=args.campaign, quiet=args.quiet,
        automation_tiers=tiers.tiers_from_args(args),
        route_research_enabled=args.route_research, max_route_research=args.max_route_research)
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    # Exit 0 even when a unit failed: the failure is an operator task, and the
    # scheduler must not treat one bad race as a broken nightly handover.
    return 0


if __name__ == "__main__":
    sys.exit(main())
