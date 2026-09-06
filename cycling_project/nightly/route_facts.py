"""Route facts for a stage: ingest, validate, override — never invent.

The nightly acquisition thread fetches the PCS / organiser stage page and
writes what it read **verbatim** to ``predictions/<unit>/route_raw.json``. It
does not compute or restructure anything. This module is the deterministic
side of that contract: it parses, validates, merges an operator override on
top, and writes ``predictions/<unit>/route.json`` with an honest grade.

    uv run python -m cycling_project.nightly.route_facts \\
        ingest-route performance_eval/vuelta-2026 stage_15

Inputs, in increasing order of authority:

1. ``results/<unit>/stage_page_*.html`` — the FirstCycling stage page archive
   (newest), when the weekly Mac run has one. Its ``div.sideBox`` carries
   ``15th stage | 110.2 km``, ``Palma del Rio -> Cordoba`` and a bare profile
   code (``GT2``). Used as a cross-check, and as a source for distance,
   start and finish when the raw transcription lacks them.
2. ``predictions/<unit>/route_raw.json`` — the acquisition thread's verbatim
   transcription. Shape (every field optional; numbers may arrive as strings
   like ``"110.2 km"``, ``"1,900 m"``, ``"4.1%"``)::

       {
         "unit": "stage_15", "stage": 15,
         "distance_km": 189.7, "vertical_metres": 2350,
         "profile_class": "medium mountains",
         "start": "Palma del Rio", "finish": "Cordoba",
         "climbs_listed": true,
         "climbs": [{"name": "Puerto de la Forestal", "category": "3",
                     "km_mark": 34.5, "length_km": 6.7, "gradient_pct": 4.1}],
         "sources": [{"url": "...", "fetched_at": "...", "file": "..."}],
         "notes": "free text"
       }

3. ``predictions/<unit>/route.override.json`` — an operator correction, same
   field names plus ``reason`` / ``source`` / ``recorded_by``. It wins field
   by field; a ``climbs`` array in the override REPLACES the whole list,
   because that is what a redrawn stage means. The canonical case is Vuelta
   2026 stage 15, cut from 189.7 km to 110.2 km on the afternoon of
   2026-09-05 under the extreme-heat protocol.

Validation (a failure never becomes a default — the value is rejected with a
reason and the field goes to null):

* every number parses, distance in (0, 400] km, vertical in [0, 10000] m,
  gradients in (0, 25] %;
* a climb's km mark lies on the course (``0 <= km_mark <= distance_km``) and
  the climb starts at or after the start (``length_km <= km_mark``);
* climbs are ordered by km mark — out-of-order climbs are kept but the day is
  graded ``partial`` and the disorder recorded.

``route_facts`` grades the result:

* ``complete``  — distance, vertical, profile class and the climb list are
  all known and valid (``climbs_listed: false`` counts as known-empty);
* ``partial``   — something is known, something is missing or flagged;
* ``missing``   — no usable input at all. Recorded, never invented.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

MAX_DISTANCE_KM = 400.0
MAX_VERTICAL_M = 10000.0
MAX_GRADIENT_PCT = 25.0
CLIMB_FIELDS = ("name", "category", "km_mark", "length_km", "gradient_pct")

# Fields that must all be known and valid for a `complete` grade.
REQUIRED_FOR_COMPLETE = ("distance_km", "vertical_metres", "profile_class")


class RouteFactsError(Exception):
    """Bad invocation — a missing campaign or unit directory."""


# --------------------------------------------------------------------------
# Lenient number parsing that never guesses


def parse_number(value: Any, *, field: str) -> tuple[float | None, str | None]:
    """Return ``(number, error)``. A transcription may carry units or a
    thousands separator; anything else is an error, never a default."""
    if value is None or value == "":
        return None, None
    if isinstance(value, bool):
        return None, f"{field}: expected a number, got a boolean"
    if isinstance(value, (int, float)):
        return float(value), None
    if not isinstance(value, str):
        return None, f"{field}: expected a number, got {type(value).__name__}"
    cleaned = value.strip().replace(",", "")
    m = re.match(r"^[+-]?\d*\.?\d+", cleaned)
    if not m:
        return None, f"{field}: cannot read a number from {value!r}"
    trailing = cleaned[m.end():].strip()
    if trailing and not re.fullmatch(r"(km|m|%|meter|metres|meters|pct)\.?", trailing,
                                     re.IGNORECASE):
        return None, f"{field}: unexpected text after the number in {value!r}"
    return float(m.group(0)), None


def parse_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# --------------------------------------------------------------------------
# FirstCycling stage page (cross-check + fallback source)


def parse_fc_stage_page(html: str) -> dict:
    """Pull route facts out of the stage page's Information sideBox.

    Verified against the committed Vuelta 2026 archive: the box holds the race
    link, the nation, ``15th stage | 110.2 km``, ``Palma del Rio -> Cordoba``
    and a bare profile code (``GT2``). The code is recorded verbatim and never
    translated into a profile class — its scale is FirstCycling's, not ours.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    box = soup.find("div", class_="sideBox")
    out: dict[str, Any] = {}
    if box is None:
        return out
    for p in box.find_all("p"):
        text = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
        if not text:
            continue
        m = re.search(r"\|\s*([\d.,]+)\s*km\b", text, re.IGNORECASE)
        if m:
            distance, err = parse_number(m.group(1), field="distance_km")
            if distance is not None and err is None:
                out["distance_km"] = distance
            continue
        if "->" in text or "→" in text:
            parts = re.split(r"->|→", text, maxsplit=1)
            start, finish = parse_text(parts[0]), parse_text(parts[1])
            if start:
                out["start"] = start
            if finish:
                out["finish"] = finish
            continue
        if re.fullmatch(r"[A-Z]{1,4}\d{0,2}", text):
            out["fc_profile_code"] = text
    return out


def newest_fc_archive(results_unit_dir: Path) -> Path | None:
    pages = sorted(results_unit_dir.glob("stage_page_*.html"))
    return pages[-1] if pages else None


# --------------------------------------------------------------------------
# Validation


def validate_climb(raw: Any, index: int, distance_km: float | None,
                   errors: list[str], rejected: list[dict]) -> dict | None:
    where = f"climbs[{index}]"
    if not isinstance(raw, dict):
        errors.append(f"{where}: expected an object, got {type(raw).__name__}")
        rejected.append({"field": where, "value": raw, "reason": "not an object"})
        return None

    name = parse_text(raw.get("name"))
    if not name:
        errors.append(f"{where}: no climb name")
        rejected.append({"field": where, "value": raw, "reason": "no name"})
        return None

    climb: dict[str, Any] = {"name": name, "category": parse_text(raw.get("category"))}
    local_errors: list[str] = []
    for field, limit in (("km_mark", None), ("length_km", None),
                         ("gradient_pct", MAX_GRADIENT_PCT)):
        value, err = parse_number(raw.get(field), field=f"{where}.{field}")
        if err:
            local_errors.append(err)
            value = None
        if value is not None and value < 0:
            local_errors.append(f"{where}.{field}: negative ({value})")
            value = None
        if value is not None and limit is not None and value > limit:
            local_errors.append(f"{where}.{field}: {value} is above the "
                                f"plausible maximum {limit}")
            value = None
        climb[field] = value

    if (climb["km_mark"] is not None and distance_km is not None
            and climb["km_mark"] > distance_km):
        local_errors.append(f"{where}: km mark {climb['km_mark']} is past the "
                            f"finish at {distance_km} km")
        climb["km_mark"] = None
    if (climb["km_mark"] is not None and climb["length_km"] is not None
            and climb["length_km"] > climb["km_mark"]):
        local_errors.append(f"{where}: a {climb['length_km']} km climb cresting at "
                            f"km {climb['km_mark']} would start before the start")

    for extra in raw:
        if extra not in CLIMB_FIELDS:
            climb[extra] = raw[extra]
    if local_errors:
        errors.extend(local_errors)
        rejected.append({"field": where, "value": raw, "reason": "; ".join(local_errors)})
    return climb


def merge_layer(merged: dict, sources: dict, layer: dict, label: str,
                applied: list[str]) -> None:
    """Apply one source layer on top of the merge, recording provenance."""
    for field, value in layer.items():
        if value is None:
            continue
        if label == "override":
            applied.append(field)
        merged[field] = value
        sources[field] = label


# --------------------------------------------------------------------------
# The ingest


def ingest_route(campaign_dir: Path, unit: str, *, write: bool = True) -> dict:
    campaign_dir = Path(campaign_dir)
    if not campaign_dir.is_dir():
        raise RouteFactsError(f"no campaign directory at {campaign_dir}")
    unit_dir = campaign_dir / "predictions" / unit
    results_dir = campaign_dir / "results" / unit

    errors: list[str] = []
    warnings: list[str] = []
    rejected: list[dict] = []
    cross_checks: list[dict] = []
    inputs: list[dict] = []
    field_sources: dict[str, str] = {}
    overrides_applied: list[str] = []

    # ---- layer 1: the FirstCycling archive ------------------------------
    fc_facts: dict[str, Any] = {}
    fc_page = newest_fc_archive(results_dir) if results_dir.is_dir() else None
    if fc_page is not None:
        try:
            fc_facts = parse_fc_stage_page(fc_page.read_text(encoding="utf-8",
                                                             errors="replace"))
            inputs.append({"layer": "firstcycling", "file": str(fc_page),
                           "fields": sorted(fc_facts)})
        except Exception as e:  # a vendor page shape change must not crash the night
            warnings.append(f"could not parse {fc_page.name}: {e}")
            inputs.append({"layer": "firstcycling", "file": str(fc_page),
                           "error": str(e)})

    # ---- layer 2: the acquisition thread's verbatim transcription -------
    raw: dict[str, Any] = {}
    raw_path = unit_dir / "route_raw.json"
    if raw_path.exists():
        try:
            raw = json.loads(raw_path.read_text())
            if not isinstance(raw, dict):
                errors.append("route_raw.json is not a JSON object")
                raw = {}
            inputs.append({"layer": "route_raw", "file": str(raw_path),
                           "fields": sorted(raw)})
        except json.JSONDecodeError as e:
            errors.append(f"route_raw.json is not valid JSON: {e}")
            inputs.append({"layer": "route_raw", "file": str(raw_path),
                           "error": str(e)})

    # ---- layer 3: the operator override ---------------------------------
    override: dict[str, Any] = {}
    override_path = unit_dir / "route.override.json"
    if override_path.exists():
        try:
            override = json.loads(override_path.read_text())
            if not isinstance(override, dict):
                errors.append("route.override.json is not a JSON object")
                override = {}
            inputs.append({"layer": "override", "file": str(override_path),
                           "fields": sorted(override)})
        except json.JSONDecodeError as e:
            errors.append(f"route.override.json is not valid JSON: {e}")
            inputs.append({"layer": "override", "file": str(override_path),
                           "error": str(e)})

    # ---- scalar merge ----------------------------------------------------
    merged: dict[str, Any] = {}
    for layer, label in ((fc_facts, "firstcycling"), (raw, "route_raw"),
                         (override, "override")):
        scalars: dict[str, Any] = {}
        for field in ("distance_km", "vertical_metres", "profile_class",
                      "start", "finish", "fc_profile_code", "notes"):
            if field not in layer:
                continue
            if field in ("distance_km", "vertical_metres"):
                value, err = parse_number(layer[field], field=f"{label}.{field}")
                if err:
                    errors.append(err)
                    rejected.append({"field": field, "value": layer[field],
                                     "reason": err, "layer": label})
                    continue
                scalars[field] = value
            else:
                scalars[field] = parse_text(layer[field])
        merge_layer(merged, field_sources, scalars, label, overrides_applied)

    distance = merged.get("distance_km")
    if distance is not None and not (0 < distance <= MAX_DISTANCE_KM):
        errors.append(f"distance_km {distance} is outside (0, {MAX_DISTANCE_KM}] km")
        rejected.append({"field": "distance_km", "value": distance,
                         "reason": "implausible distance"})
        merged["distance_km"] = distance = None
        field_sources.pop("distance_km", None)
    vertical = merged.get("vertical_metres")
    if vertical is not None and not (0 <= vertical <= MAX_VERTICAL_M):
        errors.append(f"vertical_metres {vertical} is outside [0, {MAX_VERTICAL_M}] m")
        rejected.append({"field": "vertical_metres", "value": vertical,
                         "reason": "implausible vertical"})
        merged["vertical_metres"] = None
        field_sources.pop("vertical_metres", None)

    # ---- FirstCycling cross-check ---------------------------------------
    if (fc_facts.get("distance_km") is not None and distance is not None
            and field_sources.get("distance_km") != "firstcycling"):
        delta = round(distance - fc_facts["distance_km"], 3)
        agrees = abs(delta) <= 0.5
        cross_checks.append({"field": "distance_km", "ours": distance,
                             "firstcycling": fc_facts["distance_km"],
                             "delta_km": delta, "agrees": agrees,
                             "source": field_sources.get("distance_km")})
        if not agrees:
            warnings.append(
                f"distance disagrees with FirstCycling: {distance} km from "
                f"{field_sources.get('distance_km')} vs {fc_facts['distance_km']} km "
                f"on the archived stage page"
            )

    # ---- climbs ----------------------------------------------------------
    climbs: list[dict] | None = None
    climbs_source: str | None = None
    climbs_listed: bool | None = None
    for layer, label in ((raw, "route_raw"), (override, "override")):
        if "climbs_listed" in layer and isinstance(layer["climbs_listed"], bool):
            climbs_listed = layer["climbs_listed"]
        if "climbs" in layer:
            # Only the winning layer is validated. A redrawn stage replaces the
            # whole list, and climbs that the rewrite removed must not raise
            # errors against the new, shorter course they are no longer on.
            climbs_source = label

    if climbs_source is not None:
        value = (override if climbs_source == "override" else raw)["climbs"]
        if not isinstance(value, list):
            errors.append(f"{climbs_source}.climbs: expected a list, "
                          f"got {type(value).__name__}")
            rejected.append({"field": "climbs", "value": value,
                             "reason": "not a list", "layer": climbs_source})
            climbs_source = None
        else:
            if climbs_source == "override":
                overrides_applied.append("climbs")
            parsed = [validate_climb(c, i, distance, errors, rejected)
                      for i, c in enumerate(value)]
            climbs = [c for c in parsed if c is not None]
            if climbs:
                climbs_listed = True

    ordered = True
    if climbs:
        marks = [c["km_mark"] for c in climbs if c["km_mark"] is not None]
        if marks != sorted(marks):
            ordered = False
            errors.append("climbs are not in ascending km order "
                          f"({marks}) — kept as transcribed, not reordered")
    if climbs_source:
        field_sources["climbs"] = climbs_source

    # ---- grade -----------------------------------------------------------
    known_climbs = bool(climbs) or climbs_listed is False
    missing_fields = [f for f in REQUIRED_FOR_COMPLETE if merged.get(f) is None]
    if not known_climbs:
        missing_fields.append("climbs")

    if not inputs or (not merged and not climbs):
        grade = "missing"
    elif missing_fields or errors or warnings or not ordered:
        # A warning is a live disagreement between sources — a distance that
        # does not match the archived stage page is exactly the case a
        # consumer must not read as settled fact.
        grade = "partial"
    else:
        grade = "complete"

    route = {
        "unit": unit,
        "campaign": campaign_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "route_facts": grade,
        "distance_km": merged.get("distance_km"),
        "vertical_metres": merged.get("vertical_metres"),
        "profile_class": merged.get("profile_class"),
        "start": merged.get("start"),
        "finish": merged.get("finish"),
        "climbs": climbs if climbs is not None else [],
        "climbs_listed": climbs_listed,
        "climbs_ordered": ordered,
        "fc_profile_code": merged.get("fc_profile_code"),
        "notes": merged.get("notes"),
        "missing_fields": missing_fields,
        "errors": errors,
        "warnings": warnings,
        "rejected": rejected,
        "cross_checks": cross_checks,
        "field_sources": field_sources,
        "overrides_applied": sorted(set(overrides_applied)),
        "override": {k: override[k] for k in ("reason", "source", "recorded_by",
                                              "recorded_at")
                     if k in override} or None,
        "inputs": inputs,
        "source_urls": [s for layer in (raw, override)
                        for s in (layer.get("sources") or [])],
    }

    if write:
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "route.json").write_text(json.dumps(route, indent=2,
                                                        ensure_ascii=False) + "\n")
    return route


# --------------------------------------------------------------------------
# CLI


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m cycling_project.nightly.route_facts",
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="command", required=True)
    ing = sub.add_parser("ingest-route",
                         help="validate route_raw.json + override into route.json")
    ing.add_argument("campaign", help="campaign directory, e.g. performance_eval/vuelta-2026")
    ing.add_argument("unit", help="unit directory name, e.g. stage_15")
    ing.add_argument("--dry-run", action="store_true",
                     help="validate and print, write nothing")
    ing.add_argument("--json", action="store_true", help="print the full route.json")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        route = ingest_route(Path(args.campaign), args.unit, write=not args.dry_run)
    except RouteFactsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(route, indent=2, ensure_ascii=False))
    else:
        print(f"{args.unit}: route_facts={route['route_facts']}"
              f"  distance={route['distance_km']}"
              f"  climbs={len(route['climbs'])}"
              f"  sources={sorted(set(route['field_sources'].values()))}")
        for field in route["missing_fields"]:
            print(f"  missing: {field}")
        for err in route["errors"]:
            print(f"  ERROR: {err}")
        for warn in route["warnings"]:
            print(f"  warning: {warn}")
        for check in route["cross_checks"]:
            verdict = "agrees" if check["agrees"] else "DISAGREES"
            print(f"  cross-check {check['field']}: {verdict} "
                  f"(ours {check['ours']}, FirstCycling {check['firstcycling']})")
    # `missing` is a recorded state, not a failure: the night continues.
    return 0 if not route["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
