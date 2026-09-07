"""Weekly race calendar merge and campaign registry synchronisation.

The cloud nightly only reads this registry.  All writes happen during the
supervised Mac pipeline, from FirstCycling's rate-limited race-list scrape.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from cycling_project.nightly.secrets import load_local_env
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

CATEGORIES = ("wt", "pro", "d1")
_CATEGORY_ORDER = {name: index for index, name in enumerate(CATEGORIES)}

# Calendar flag titles have varied between ISO codes and English names.  The
# list intentionally leaves an unknown country unset instead of guessing.
COUNTRY_TIMEZONES = {
    "ad": "Europe/Andorra", "andorra": "Europe/Andorra",
    "at": "Europe/Vienna", "austria": "Europe/Vienna",
    "au": "Australia/Sydney", "australia": "Australia/Sydney",
    "be": "Europe/Brussels", "belgium": "Europe/Brussels",
    "ca": "America/Toronto", "canada": "America/Toronto",
    "ch": "Europe/Zurich", "switzerland": "Europe/Zurich",
    "cn": "Asia/Shanghai", "china": "Asia/Shanghai",
    "co": "America/Bogota", "colombia": "America/Bogota",
    "cz": "Europe/Prague", "czech republic": "Europe/Prague", "czechia": "Europe/Prague",
    "de": "Europe/Berlin", "germany": "Europe/Berlin",
    "dk": "Europe/Copenhagen", "denmark": "Europe/Copenhagen",
    "es": "Europe/Madrid", "spain": "Europe/Madrid",
    "fr": "Europe/Paris", "france": "Europe/Paris",
    "gb": "Europe/London", "great britain": "Europe/London", "united kingdom": "Europe/London",
    "hr": "Europe/Zagreb", "croatia": "Europe/Zagreb",
    "hu": "Europe/Budapest", "hungary": "Europe/Budapest",
    "ie": "Europe/Dublin", "ireland": "Europe/Dublin",
    "it": "Europe/Rome", "italy": "Europe/Rome",
    "jp": "Asia/Tokyo", "japan": "Asia/Tokyo",
    "lu": "Europe/Luxembourg", "luxembourg": "Europe/Luxembourg",
    "mc": "Europe/Monaco", "monaco": "Europe/Monaco",
    "nl": "Europe/Amsterdam", "netherlands": "Europe/Amsterdam",
    "no": "Europe/Oslo", "norway": "Europe/Oslo",
    "nz": "Pacific/Auckland", "new zealand": "Pacific/Auckland",
    "pl": "Europe/Warsaw", "poland": "Europe/Warsaw",
    "pt": "Europe/Lisbon", "portugal": "Europe/Lisbon",
    "si": "Europe/Ljubljana", "slovenia": "Europe/Ljubljana",
    "sk": "Europe/Bratislava", "slovakia": "Europe/Bratislava",
    "se": "Europe/Stockholm", "sweden": "Europe/Stockholm",
    "tr": "Europe/Istanbul", "turkey": "Europe/Istanbul", "türkiye": "Europe/Istanbul",
    "us": "America/New_York", "usa": "America/New_York", "united states": "America/New_York",
}


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def slugify(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    plain = re.sub(r"\b(?:19|20)\d{2}\b", "", plain.lower())
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "race"


def _calendar_rows(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [dict(row) for row in value]
    if isinstance(value, dict):
        return [dict(row) for row in value.get("races", [])]
    return []


def merge_calendar_sidecars(
    scraped_data_dir: Path,
    performance_eval_dir: Path,
    years: Optional[Iterable[int]] = None,
    *,
    as_of: Optional[date] = None,
    dry_run: bool = False,
) -> Dict[int, List[Dict[str, Any]]]:
    """Merge per-tier sidecars into committed, deterministically ordered files."""
    scraped_data_dir = Path(scraped_data_dir)
    performance_eval_dir = Path(performance_eval_dir)
    as_of = as_of or date.today()
    if years is None:
        years = sorted(int(p.name) for p in scraped_data_dir.iterdir()
                       if p.is_dir() and p.name.isdigit())

    merged: Dict[int, List[Dict[str, Any]]] = {}
    for year in sorted(set(int(y) for y in years)):
        records: Dict[tuple, Dict[str, Any]] = {}
        for category in CATEGORIES:
            sidecar = scraped_data_dir / str(year) / category / f"{category}.calendar.json"
            for raw in _calendar_rows(_read_json(sidecar, [])):
                row = dict(raw)
                row.update({"year": year, "category": category})
                key = (str(row.get("fc_race_id") or ""), row.get("url") or "")
                old = records.get(key)
                if old is None or _CATEGORY_ORDER[category] < _CATEGORY_ORDER[old["category"]]:
                    records[key] = row

        rows = sorted(records.values(), key=lambda row: (
            row.get("start_date") or "9999-12-31",
            _CATEGORY_ORDER.get(row.get("category"), 99),
            row.get("name") or "",
            str(row.get("fc_race_id") or ""),
        ))
        source = f"performance_eval/calendar/{year}.json"
        week = f"{as_of.isocalendar().year}-W{as_of.isocalendar().week:02d}"
        for row in rows:
            row["week"] = week
            row["source"] = source
        merged[year] = rows
        if not dry_run:
            _write_json(performance_eval_dir / "calendar" / f"{year}.json", {
                "schema_version": 1,
                "year": year,
                "races": rows,
            })
    return merged


def _is_absent(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def merge_new_information(existing: Any, proposed: Any) -> Any:
    """Recursively fill unknown fields without replacing a known value."""
    if isinstance(existing, dict) and isinstance(proposed, dict):
        result = dict(existing)
        for key, value in proposed.items():
            if key not in result:
                result[key] = value
            elif _is_absent(result[key]):
                if not _is_absent(value):
                    result[key] = value
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_new_information(result[key], value)
            elif key == "stages" and isinstance(result[key], list) and isinstance(value, list):
                result[key] = _merge_stages(result[key], value,
                                            allow_append=bool(result.get("stages_provisional")))
        return result
    return existing if not _is_absent(existing) else proposed


def _merge_stages(existing: List[dict], proposed: List[dict], *, allow_append: bool = False) -> List[dict]:
    """Fill unknown fields of known stages; invent none unless allowed.

    A campaign that declares its stages (hand-written, or PCS-supplied) is
    authoritative on HOW MANY there are: the calendar's one-stage-per-day
    proposal must not append phantom stages on rest days (the Vuelta spans 23
    calendar days for 21 stages). Only a campaign flagged
    ``stages_provisional`` (generated from the calendar, schedule not yet
    known) may grow.
    """
    by_number = {stage.get("number"): dict(stage) for stage in existing}
    for stage in proposed:
        number = stage.get("number")
        if existing and number not in by_number and not allow_append:
            continue
        by_number[number] = merge_new_information(by_number.get(number, {}), stage)
    return [by_number[key] for key in sorted(by_number, key=lambda value: (value is None, value or 0))]


CALENDAR_COLUMNS = ("fc_race_id", "year", "name", "category", "is_stage_race",
                    "start_date", "end_date", "country", "pcs_slug", "week", "source")


def _calendar_store_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Project a calendar row onto public.calendar's columns (the sidecar also
    carries url / calendar_category, which PostgREST rejects)."""
    return {k: row.get(k) for k in CALENDAR_COLUMNS}


def timezone_for_country(country: Optional[str]) -> Optional[str]:
    return COUNTRY_TIMEZONES.get((country or "").strip().lower())


def _dates_inclusive(start: str, end: str) -> List[str]:
    current = date.fromisoformat(start)
    finish = date.fromisoformat(end)
    out = []
    while current <= finish:
        out.append(current.isoformat())
        current += timedelta(days=1)
    return out


def campaign_from_calendar(row: Dict[str, Any]) -> Dict[str, Any]:
    year = int(row["year"])
    base_slug = slugify(row["name"])
    campaign_slug = f"{base_slug}-{year}"
    is_stage = bool(row.get("is_stage_race"))
    dates = _dates_inclusive(row["start_date"], row["end_date"])
    stages = []
    if is_stage:
        stages = [
            {"number": number, "date": stage_date, "towns": None,
             "distance_km": None, "kind": None}
            for number, stage_date in enumerate(dates, 1)
        ]
    else:
        stages = [{"number": None, "date": row["start_date"], "towns": None,
                   "distance_km": None, "kind": "one_day"}]
    match = unicodedata.normalize("NFKD", row["name"]).encode("ascii", "ignore").decode().lower()
    return {
        "slug": campaign_slug,
        "name": row["name"],
        "fc_race_id": str(row["fc_race_id"]),
        # UCI results bridge (uci_acquire.py): set by an operator from the UCI calendar, never guessed.
        "uci_competition_url": None,
        "uci_competition_id": None,
        "uci_discipline": None,
        "year": year,
        "category": row["category"],
        "is_stage_race": is_stage,
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "stages": stages,
        "timezone": timezone_for_country(row.get("country")),
        "kambi_match": " ".join(match.split()),
        "kambi_localised_name": None,
        "kambi_event_ids": {},
        "pcs_slug": base_slug,
        "organiser_stage_urls": {},
        "void_stages": [],
    }


def _campaign_row(config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "campaign_slug": config["slug"],
        "fc_race_id": str(config["fc_race_id"]),
        "year": int(config["year"]),
        "name": config["name"],
        "category": config.get("category"),
        "is_stage_race": bool(config.get("is_stage_race")),
        "start_date": config.get("start_date"),
        "end_date": config.get("end_date"),
        "timezone": config.get("timezone"),
        "pcs_slug": config.get("pcs_slug"),
        "config": config,
        "active": True,
    }


def _stage_rows(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    void = set(config.get("void_stages") or [])
    rows = []
    for stage in config.get("stages") or []:
        number = stage.get("number")
        one_day = not config.get("is_stage_race")
        rows.append({
            "campaign_slug": config["slug"],
            "unit": "one_day" if one_day else f"stage_{int(number):02d}",
            "kind": "one_day" if one_day else (stage.get("kind") or "stage"),
            "stage_number": None if one_day else int(number),
            "date": stage.get("date"),
            "void": number in void,
            "settle_late": False,
        })
    return rows


def _write_campaign_json(path: Path, config: Dict[str, Any], existing: Optional[Dict[str, Any]]) -> None:
    """Write a campaign file, keeping a hand-formatted one byte-for-byte.

    The Tour and Vuelta files are written by hand (compact stage rows); a plain
    re-dump would reformat hundreds of lines nobody touched.
    """
    try:
        from cycling_project.nightly.uci_calendar import render_campaign
    except ImportError:  # pragma: no cover
        _write_json(path, config)
        return
    original_text = path.read_text() if path.exists() else None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_campaign(original_text, existing or {}, config))
    tmp.replace(path)


def _uci_matcher(snapshot_dir: Optional[Path]) -> Optional[Any]:
    """``(entries, provenance)`` from the archived UCI calendar, or None.

    Kept optional on purpose: a missing or unreadable snapshot must never stop
    a registry sync — the campaign is simply created with a null
    ``uci_competition_url``, exactly as before, and
    ``uci_calendar resolve`` can fill it in later.
    """
    try:
        from cycling_project.nightly import uci_calendar
    except ImportError:  # pragma: no cover - the module ships with the package
        return None
    try:
        entries, index = uci_calendar.load_snapshot(snapshot_dir or uci_calendar.SNAPSHOT_DIR)
    except Exception as exc:  # noqa: BLE001 - any snapshot problem is non-fatal here
        logger.info("no usable UCI calendar snapshot (%s); campaigns keep uci_competition_url = null", exc)
        return None
    return uci_calendar, entries, uci_calendar.snapshot_provenance(index)


def _apply_uci_match(config: Dict[str, Any], matcher: Optional[Any]) -> Dict[str, Any]:
    """Fill the UCI fields at creation when the calendar match is exact.

    Same matcher, same evidence and the same refusal to guess as
    ``uci_calendar resolve``: only an exact date range with name similarity at
    or above the bar writes a URL; anything else leaves it null and records why.
    """
    if not matcher:
        return config
    uci_calendar, entries, provenance = matcher
    match = uci_calendar.match_campaign(config, entries)
    return uci_calendar.apply_match(config, match, provenance)


def _resolve_store(store: Any, mode: str) -> Any:
    if store is not None or mode == "none":
        return store
    load_local_env()
    if mode == "auto" and not (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SECRET_KEY")):
        logger.info("Supabase operator credentials are absent; registry files only")
        return None
    from cycling_project.nightly.store import SupabaseStore
    return SupabaseStore(role="operator")


def sync(
    performance_eval_dir: Path,
    *,
    horizon: int = 14,
    now: Optional[date] = None,
    dry_run: bool = False,
    store: Any = None,
    store_mode: str = "auto",
    uci_snapshot: Optional[Path] = None,
    match_uci: bool = True,
) -> Dict[str, Any]:
    """Create/complete campaign files for races intersecting the horizon."""
    performance_eval_dir = Path(performance_eval_dir)
    now = now or date.today()
    horizon_end = now + timedelta(days=horizon)
    calendar_rows: List[Dict[str, Any]] = []
    for path in sorted((performance_eval_dir / "calendar").glob("*.json")):
        calendar_rows.extend(_calendar_rows(_read_json(path, {})))
    eligible = [row for row in calendar_rows if row.get("fc_race_id") and row.get("start_date")
                and row.get("end_date") and date.fromisoformat(row["end_date"]) >= now
                and date.fromisoformat(row["start_date"]) <= horizon_end
                and row.get("category") in CATEGORIES]

    existing_campaigns: Dict[tuple, tuple[Path, Dict[str, Any]]] = {}
    for campaign_file in sorted(performance_eval_dir.glob("*/campaign.json")):
        campaign = _read_json(campaign_file, {})
        if campaign.get("fc_race_id") is not None and campaign.get("year") is not None:
            existing_campaigns[(str(campaign["fc_race_id"]), int(campaign["year"]))] = (
                campaign_file, campaign
            )

    matcher = _uci_matcher(uci_snapshot) if match_uci else None
    synced = []
    campaign_rows = []
    stage_rows = []
    uci_resolved = 0
    for row in sorted(eligible, key=lambda value: (value["start_date"], value["name"])):
        proposed = campaign_from_calendar(row)
        known = existing_campaigns.get((str(row["fc_race_id"]), int(row["year"])))
        if known:
            path, existing = known
            proposed["slug"] = existing.get("slug") or path.parent.name
        else:
            path = performance_eval_dir / proposed["slug"] / "campaign.json"
            existing = _read_json(path, {})
        config = merge_new_information(existing, proposed)
        if not existing and config.get("is_stage_race"):
            config["stages_provisional"] = True   # one stage per calendar day until PCS supplies the schedule
        config = _apply_uci_match(config, matcher)
        if config.get("uci_competition_url") and not (existing.get("uci_competition_url") if existing else None):
            uci_resolved += 1
        if not dry_run and config != existing:
            _write_campaign_json(path, config, existing)
        synced.append({"slug": config["slug"], "path": str(path), "changed": config != existing,
                       "uci_competition_url": config.get("uci_competition_url"),
                       "uci_decision": (config.get("uci_match_evidence") or {}).get("decision")})
        campaign_rows.append(_campaign_row(config))
        stage_rows.extend(_stage_rows(config))

    resolved_store = None if dry_run else _resolve_store(store, store_mode)
    if resolved_store is not None:
        resolved_store.sync_calendar([_calendar_store_row(r) for r in calendar_rows])
        for row in campaign_rows:
            resolved_store.sync_campaign(row)
        resolved_store.sync_stages(stage_rows)

    return {
        "as_of": now.isoformat(),
        "horizon_end": horizon_end.isoformat(),
        "calendar_rows": len(calendar_rows),
        "campaigns": synced,
        "uci_matched": matcher is not None,
        "uci_urls_resolved": uci_resolved,
        "store_synced": resolved_store is not None,
        "dry_run": dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Weekly campaign registry")
    sub = parser.add_subparsers(dest="command", required=True)
    sync_parser = sub.add_parser("sync", help="sync the configured calendar horizon")
    sync_parser.add_argument("--horizon", type=int, default=14)
    sync_parser.add_argument("--dry-run", action="store_true")
    sync_parser.add_argument("--now", type=date.fromisoformat, default=None)
    sync_parser.add_argument("--store", choices=("auto", "hosted", "none"), default="auto")
    sync_parser.add_argument("--uci-snapshot", type=Path, default=None,
                             help="UCI calendar capture directory (default: the archived snapshot)")
    sync_parser.add_argument("--no-uci-match", action="store_true",
                             help="do not consult the UCI calendar; campaigns keep uci_competition_url = null")
    sync_parser.add_argument(
        "--performance-eval", type=Path,
        default=Path(__file__).resolve().parents[2] / "performance_eval",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "sync":
        result = sync(
            args.performance_eval, horizon=args.horizon, now=args.now,
            dry_run=args.dry_run, store_mode=args.store,
            uci_snapshot=args.uci_snapshot, match_uci=not args.no_uci_match,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
