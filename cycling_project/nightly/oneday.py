"""The one-day race path: config shape, own-history references, results archive.

A one-day race has no stages, no race state and no day key.  Everything the
stage path spreads over ``stage_NN`` units it keeps in a single ``race`` unit:

    <campaign>/predictions/race/scenarios.json    the config (``target: one_day``)
    <campaign>/predictions/race/<key>.json        one board per scenario
    <campaign>/predictions/race/startlist.json    optional, cloud acquisition
    <campaign>/results/race/results.{csv,json}    the settled result

``NIGHTLY_AGENT_WORKFLOW.md`` §2.6.  The default scenario prices the race on
its own last five editions — a one-day race is its own best reference set —
and any alternate reading uses archetype references (``nightly refs
--archetype …``).  The day-menu retrieval channel is a stage-race instrument
(the menu's items are stage-day shapes), so a one-day config carries no
``day_key`` and the validator rejects one.

Nothing here writes to the database or the network.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from cycling_project.nightly.uci_acquire import ONE_DAY_UNITS, is_one_day_unit  # noqa: F401  (re-export)

ONE_DAY_UNIT = "race"
OWN_HISTORY_KEY = "own_history"
DEFAULT_REF_COUNT = 5
STARTLIST_NAME = "startlist.json"
CONFIG_NAME = "scenarios.json"
# Keys a stage config carries that make no sense for a race with one day.
STAGE_ONLY_KEYS = ("stage", "void_stages", "day_key", "day_key_note", "day_key_source", "day_key_author")


class OneDayConfigError(ValueError):
    """A ``target: one_day`` config that cannot be served as written."""


# ---------------------------------------------------------------------------
# references: the race's own recent editions
# ---------------------------------------------------------------------------

def own_edition_refs(fc_race_id: str | int, year: int, *, limit: int = DEFAULT_REF_COUNT,
                     db_path: Optional[str | Path] = None) -> List[int]:
    """Competition ids of the race's own ``limit`` most recent editions before ``year``.

    Only editions with a ``competition_field_features`` row are returned: that
    table is what ``get_reference_race_profile`` reads, so an edition without
    one cannot be averaged into a profile.  Newest first.
    """
    from cycling_project.db_path import default_db_path

    path = Path(db_path) if db_path else default_db_path()
    if not Path(path).exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            SELECT c.id
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            JOIN competition_field_features cff ON cff.competition_id = c.id
            WHERE r.fc_race_id = ? AND r.year < ? AND c.competition_type = 'one_day'
            ORDER BY r.year DESC, c.date DESC
            LIMIT ?
            """,
            (str(fc_race_id), int(year), int(limit)),
        ).fetchall()
    finally:
        con.close()
    return [int(r[0]) for r in rows]


def own_edition_detail(fc_race_id: str | int, year: int, *, limit: int = DEFAULT_REF_COUNT,
                       db_path: Optional[str | Path] = None) -> List[Dict[str, Any]]:
    """``own_edition_refs`` with the year and date of each edition, for notes and reports."""
    from cycling_project.db_path import default_db_path

    path = Path(db_path) if db_path else default_db_path()
    if not Path(path).exists():
        return []
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """
            SELECT c.id, r.year, c.date, r.name
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            JOIN competition_field_features cff ON cff.competition_id = c.id
            WHERE r.fc_race_id = ? AND r.year < ? AND c.competition_type = 'one_day'
            ORDER BY r.year DESC, c.date DESC
            LIMIT ?
            """,
            (str(fc_race_id), int(year), int(limit)),
        ).fetchall()
    finally:
        con.close()
    return [{"competition_id": int(i), "year": int(y), "date": d, "name": n} for i, y, d, n in rows]


# ---------------------------------------------------------------------------
# the config
# ---------------------------------------------------------------------------

def _positive_refs(spec: Dict[str, Any]) -> List[int]:
    raw = spec.get("refs") or spec.get("base_refs") or []
    out = []
    for x in raw:
        try:
            v = int(x)
        except (TypeError, ValueError):
            continue
        if v > 0:
            out.append(v)
    return out


def validate_config(config: Dict[str, Any]) -> List[str]:
    """Problems with a one-day scenario config; empty list means it can be served."""
    problems: List[str] = []
    if not isinstance(config, dict):
        return ["config is not a JSON object"]
    if config.get("target") != "one_day":
        problems.append(f"target is {config.get('target')!r}, not 'one_day'")
    for key in ("fc_race_id", "year", "date", "label"):
        if config.get(key) in (None, ""):
            problems.append(f"config lacks {key}")
    if config.get("stage") is not None:
        problems.append("a one-day config must not carry a stage number")
    if config.get("void_stages"):
        problems.append("a one-day race has no stages to void")
    if config.get("day_key"):
        problems.append("a one-day race skips the day-menu channel: remove day_key")

    scenarios = config.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        problems.append("config lacks scenarios")
        return problems
    for key, spec in scenarios.items():
        if not isinstance(spec, dict):
            problems.append(f"scenario {key}: not an object")
            continue
        if not spec.get("label"):
            problems.append(f"scenario {key}: no label")
        if not spec.get("tag"):
            problems.append(f"scenario {key}: no tag")
        if spec.get("day_key"):
            problems.append(f"scenario {key}: a one-day race skips the day-menu channel: remove day_key")
        refs = _positive_refs(spec)
        wanted = spec.get("refs") or spec.get("base_refs") or []
        if not refs or len(refs) != len(list(wanted)):
            problems.append(f"scenario {key}: placeholder/missing refs")
        if spec.get("scores") and not spec.get("base_refs"):
            problems.append(f"scenario {key}: terrain-score overrides need base_refs")
    return problems


def load_config(path: str | Path) -> Dict[str, Any]:
    """Read and validate ``<campaign>/predictions/race/scenarios.json``."""
    p = Path(path)
    try:
        config = json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise OneDayConfigError(f"{p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise OneDayConfigError(f"{p}: not valid JSON ({exc})") from exc
    problems = validate_config(config)
    if problems:
        raise OneDayConfigError(f"{p}: " + "; ".join(problems))
    return config


def build_config(*, fc_race_id: str | int, year: int, date: str, label: str,
                 refs: Sequence[int], tag_prefix: str,
                 alternates: Optional[Dict[str, Dict[str, Any]]] = None,
                 odds_capture: Optional[str] = None, event_id: Optional[str] = None,
                 note: Optional[str] = None, post_hoc: bool = False) -> Dict[str, Any]:
    """A fresh ``target: one_day`` config: own-history default plus optional alternates.

    ``alternates`` maps a scenario key to a partial spec (``label``, ``short``,
    ``refs`` from ``nightly refs --archetype …``, ``note``); the tag is filled
    from ``tag_prefix`` when the caller leaves it out.
    """
    default_note = note or (
        "The race read on its own recent history: the profile is the average of this race's "
        f"last {len(list(refs))} editions, so the terrain and the kind of rider it selects come "
        "from the race itself rather than from an archetype."
    )
    scenarios: Dict[str, Dict[str, Any]] = {
        OWN_HISTORY_KEY: {
            "label": f"{label} on its own recent editions",
            "short": "Own history",
            "refs": [int(r) for r in refs],
            "tag": f"{tag_prefix}_{OWN_HISTORY_KEY}",
            "note": default_note,
        }
    }
    for key, spec in (alternates or {}).items():
        entry = dict(spec)
        entry.setdefault("tag", f"{tag_prefix}_{key}")
        entry.setdefault("short", key.replace("_", " ").title())
        entry.setdefault("label", entry["short"])
        entry["refs"] = [int(r) for r in (entry.get("refs") or [])]
        scenarios[key] = entry
    if post_hoc:
        for spec in scenarios.values():
            spec["post_hoc"] = True
    config: Dict[str, Any] = {
        "target": "one_day",
        "fc_race_id": str(fc_race_id),
        "year": int(year),
        "date": date,
        "label": label,
        "odds_capture": odds_capture,
        "event_id": event_id,
        "scenarios": scenarios,
    }
    if post_hoc:
        config["post_hoc"] = True
    return config


def strip_stage_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    """Drop the stage-only keys a stage template carries into a one-day config."""
    for key in STAGE_ONLY_KEYS:
        config.pop(key, None)
    for spec in (config.get("scenarios") or {}).values():
        if isinstance(spec, dict):
            spec.pop("day_key", None)
    return config


# ---------------------------------------------------------------------------
# start list handed over by the acquisition thread
# ---------------------------------------------------------------------------

def startlist_path(config_dir: str | Path) -> Path:
    return Path(config_dir) / STARTLIST_NAME


def load_startlist_file(path: str | Path) -> List[Any]:
    """``startlist.json`` beside the config → the ``Team`` list the serving path expects.

    The cloud container has no FirstCycling access, so the acquisition thread
    writes the field it transcribed here.  Shape::

        {"fc_race_id": "54", "year": 2026, "source": "...", "captured_at": "...",
         "teams": [{"name": "...", "team_id": "...",
                    "riders": [{"name": "...", "rider_id": "...", "number": "1"}]}]}

    ``rider_id`` / ``team_id`` are FirstCycling ids, exactly as the
    ``cached_start_lists`` cache stores them; names are never ids.
    """
    from cycling_project.webscrape_tools.start_list_parse_tools import Rider, Team

    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OneDayConfigError(f"{p}: not valid JSON ({exc})") from exc
    raw_teams = doc.get("teams") if isinstance(doc, dict) else doc
    if not isinstance(raw_teams, list) or not raw_teams:
        raise OneDayConfigError(f"{p}: no teams in the start list")
    teams: List[Team] = []
    for t in raw_teams:
        team_name = str(t.get("name") or t.get("team_name") or "")
        team_id = t.get("team_id") or t.get("team_fc_id")
        riders = []
        for r in t.get("riders") or []:
            rider_id = r.get("rider_id") or r.get("rider_fc_id")
            if not rider_id:
                raise OneDayConfigError(
                    f"{p}: rider {r.get('name') or r.get('rider_name')!r} has no FirstCycling id "
                    "(names are never ids)")
            riders.append(Rider(
                name=str(r.get("name") or r.get("rider_name") or ""),
                rider_id=str(rider_id),
                number=str(r.get("number") or r.get("bib") or r.get("bib_number") or ""),
                team_name=team_name,
                team_id=str(team_id) if team_id else None,
            ))
        if riders:
            teams.append(Team(name=team_name, team_id=str(team_id) if team_id else None, riders=riders))
    if not teams:
        raise OneDayConfigError(f"{p}: no riders in the start list")
    return teams


# ---------------------------------------------------------------------------
# the results archive (results/race/)
# ---------------------------------------------------------------------------

def results_dir(campaign_dir: str | Path) -> Path:
    return Path(campaign_dir) / "results" / ONE_DAY_UNIT


def is_settled(campaign_dir: str | Path) -> bool:
    """A one-day race is settled when its results.csv is archived — the stage rule, one unit."""
    return (results_dir(campaign_dir) / "results.csv").exists()


def read_results(campaign_dir: str | Path) -> Optional[Dict[str, Any]]:
    """``results/race/results.json`` — the same FC-shaped payload a stage archives.

    ``{stage: "race", url, date, race_time, n_results, results: [{place, name,
    rider_id, team, team_id, gap, dob}], source}``; ``place`` is a rank string
    for classified riders and a status (DNF / DNS / …) otherwise, ``rider_id``
    is the FirstCycling rider id.  Returns None when the race is not settled.
    """
    path = results_dir(campaign_dir) / "results.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OneDayConfigError(f"{path}: not valid JSON ({exc})") from exc


def classified(results: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The finishers of a one-day result payload, in finishing order."""
    rows = (results or {}).get("results") or []
    out = [r for r in rows if str(r.get("place", "")).strip().isdigit()]
    out.sort(key=lambda r: int(r["place"]))
    return out


RESULT_FIELDS = ["place", "name", "rider_id", "team", "team_id", "gap", "dob"]


def export_results_from_db(campaign_dir: str | Path, fc_race_id: str | int, year: int, *,
                           db_path: Optional[str | Path] = None, write: bool = True,
                           now: Optional[str] = None) -> Dict[str, Any]:
    """Write ``results/race/`` for a one-day race already migrated into the database.

    The nightly path archives a result from a provider capture (``uci_ingest``);
    this is the backfill for a race whose result is already in the database —
    the spring evaluation campaigns, or any edition the weekly pipeline
    migrated before the one-day path existed.  The files are the same FC-shaped
    ``results.csv`` / ``results.json`` the ingest writes, so the page builder
    and the site index cannot tell the two apart.

    Only classified rows exist in ``rider_results``, so the archive carries no
    abandons; ``source`` records ``db`` and the payload says so.
    """
    from cycling_project.db_path import default_db_path

    path = Path(db_path) if db_path else default_db_path()
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        comp = con.execute(
            """
            SELECT c.id, c.date, c.winning_time, c.url, c.name
            FROM competitions c JOIN races r ON c.race_id = r.id
            WHERE r.fc_race_id = ? AND r.year = ? AND c.competition_type = 'one_day'
            ORDER BY c.id LIMIT 1
            """,
            (str(fc_race_id), int(year)),
        ).fetchone()
        if comp is None:
            raise OneDayConfigError(
                f"no one-day competition in the database for race {fc_race_id} {year}")
        comp_id, comp_date, winning_time, url, comp_name = comp
        rows = con.execute(
            """
            SELECT rr.place, rr.time_gap, ri.name, ri.fc_rider_id, ri.birth_year,
                   t.name, t.fc_team_id
            FROM rider_results rr
            JOIN riders ri ON ri.id = rr.rider_id
            LEFT JOIN teams t ON t.id = rr.team_id
            WHERE rr.competition_id = ?
            ORDER BY rr.place
            """,
            (int(comp_id),),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        raise OneDayConfigError(f"competition {comp_id} has no archived results")

    results = []
    for place, gap, name, fc_rider_id, birth_year, team, fc_team_id in rows:
        results.append({
            "place": str(int(place)),
            "name": name or "",
            "rider_id": str(fc_rider_id or ""),
            "team": team or "",
            "team_id": str(fc_team_id) if fc_team_id else "",
            "gap": 0 if int(place) == 1 else (float(gap) if gap is not None else ""),
            "dob": str(birth_year) if birth_year else "",
        })
    payload = {
        "stage": ONE_DAY_UNIT,
        "stage_name": comp_name or "",
        "url": url or "",
        "date": comp_date,
        "race_time": float(winning_time) if winning_time is not None else None,
        "fetched_at": now or __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "n_results": len(results),
        "results": results,
        "source": "db",
        "db": {"competition_id": int(comp_id), "fc_race_id": str(fc_race_id), "year": int(year),
               "note": "backfilled from rider_results; classified rows only, no abandons"},
    }
    out = {"competition_id": int(comp_id), "n_results": len(results),
           "winner": results[0]["name"], "written": []}
    if write:
        import csv as _csv

        d = results_dir(campaign_dir)
        d.mkdir(parents=True, exist_ok=True)
        (d / "results.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
        with open(d / "results.csv", "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=RESULT_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(results)
        (d / "classifications.json").write_text(json.dumps(
            {"stage": ONE_DAY_UNIT, "fetched_at": payload["fetched_at"], "source": "db",
             "tables": {"sta": results}}, indent=1), encoding="utf-8")
        out["written"] = ["results.json", "results.csv", "classifications.json"]
    out["payload"] = payload
    return out
