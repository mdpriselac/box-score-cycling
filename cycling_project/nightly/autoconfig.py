"""Machine-written scenario configs: a stage race needs no human setup.

Until 2026-09-16 the cloud driver could only preview a stage race that already
carried a hand-written ``predictions/TEMPLATE_scenarios.json`` (only the Vuelta
ever did), and even then a human had to write each scenario's reference
competitions by hand.  Four races died at that gate in one week.  This module
is the other half of the driver's ``_ensure_config`` / ``scenario_refs`` pair:

* :func:`build_stage_skeleton` — the config shape for ``stage_NN`` built from
  ``campaign.json`` alone, with **empty** references (they are judgment tied to
  the day key, which is resolved later in the preview).
* :func:`archetype_for_item` — the deterministic day-menu item → ``refs.ARCHETYPES``
  mapping, derived from the item's canonical archetype-share signature in
  ``models/production/day_menu_v1.json`` rather than from a hand-written table.
* :func:`fill_scenario_refs` — fills every reference-less scenario from the
  resolved key, preferring the same category tier and this race's own earlier
  editions, never reusing a reference the campaign already spent.
* :func:`alternate_scenario` — the one alternate branch: the second-weighted
  *family* of the key (families per ``day_key_record.FAMILY_OF``), so the board
  set covers the read and its nearest rival shape.
* :func:`build_gc_skeleton` / :func:`own_edition_gc_refs` — the stage race's GC
  config, from its own earlier editions when the database has three or more,
  else from GC-competition archetype references.

Everything written here records *that it was machine-chosen*
(``refs_source`` / ``refs_note`` / ``config_source``) so the page and the
retrospective can say so.  Nothing here writes to the database or the network;
the caller owns the file.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from cycling_project.nightly import day_key_record as rec
from cycling_project.nightly.refs import ARCHETYPES, query_refs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MENU_PATH = PROJECT_ROOT / "models" / "production" / "day_menu_v1.json"
REFS_PER_SCENARIO = 5
GC_OWN_EDITION_MIN = 3
REFS_SOURCE = "auto:day_menu_archetype"
GC_REFS_SOURCE = "auto:gc_archetype"
CONFIG_SOURCE = "auto:campaign.json"

# Prose for a menu item, used in generated labels and notes.  These name the
# *shape of the day*, never a rider or a team: a generated config carries no
# judgment beyond the key it was handed.
ITEM_PROSE = {
    "bunch": "a mass sprint",
    "gc_day": "the classification men deciding it on the last climb",
    "itt": "a time-separated finish",
    "res_0": "a day that comes apart",
    "res_1": "a small group that bridges clear",
    "res_2": "a mountain finish decided among a handful",
    "res_3": "a reduced bunch sprint",
    "res_4": "a mountain day won from the escape",
    "res_6": "an escape that stays away",
    "res_7": "a fractured, power-sprint finale",
}
FAMILY_PROSE = {
    "macro": "the macro read",
    "escape": "the escape",
    "power_sprint": "a sprint off a hard finale",
    "bridge": "a small group off the front",
}


class AutoConfigError(RuntimeError):
    """A config cannot be machine-written (missing menu or signature table)."""


# ---------------------------------------------------------------------------
# menu item -> archetype
# ---------------------------------------------------------------------------

def load_canonicals(menu_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """``item -> {sig_sprint, sig_mountain, …, sig_wg_prop}`` from the frozen menu."""
    path = Path(menu_path) if menu_path else MENU_PATH
    if not path.exists():
        raise AutoConfigError(f"no day menu at {path}: the release bundle must carry models/production/day_menu_v1.json")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoConfigError(f"{path}: unreadable day menu ({exc})") from exc
    canon = raw.get("canonicals")
    if not isinstance(canon, dict) or not canon:
        raise AutoConfigError(f"{path}: no canonicals in the day menu")
    return canon


def archetype_for_item(item: str, canonicals: Optional[Dict[str, Dict[str, float]]] = None) -> str:
    """The ``refs.ARCHETYPES`` name that best matches a menu item's canonical signature.

    The menu's canonicals hold, per item, the top-15 contesting archetype shares
    (sprint / mountain / hilly / rolling / breakaway / time_trial) and
    ``sig_wg_prop``, the winning group as a share of the field.  The rules below
    read those shares; they are written against the frozen menu v1 and produce:

        bunch → bunch_sprint · itt → itt_like · gc_day → gc_from_two
        res_3 → reduced_sprint · res_7 → punchy_select · res_1 → small_group
        res_2 → gc_from_two · res_4 → mountain_break · res_6 → solo · res_0 → solo

    An unknown item (never keyed today) falls back to ``small_group``.
    """
    canon = canonicals if canonicals is not None else load_canonicals()
    sig = canon.get(item)
    if not sig:
        return "small_group"
    wg = float(sig.get("sig_wg_prop") or 0.0)
    terrain = {k: float(sig.get(f"sig_{k}") or 0.0)
               for k in ("sprint", "mountain", "hilly", "rolling", "breakaway")}
    tt = float(sig.get("sig_time_trial") or 0.0)
    if tt >= max(terrain.values()):
        return "itt_like"
    top = max(terrain, key=lambda k: terrain[k])
    if wg >= 0.30:                          # a genuine bunch arrives together
        return "bunch_sprint"
    if top == "sprint":
        if wg >= 0.05:                      # still a group, just a small one
            return "reduced_sprint"
        return "punchy_select" if terrain["sprint"] >= 0.30 else "small_group"
    if top == "mountain":
        if terrain["mountain"] >= 0.36:     # the climbers alone at the front
            return "gc_from_two"
        if terrain["mountain"] >= 0.28:
            return "mountain_break"
        return "solo"
    if top == "hilly":
        return "punchy_select"
    return "small_group"


def item_archetypes(canonicals: Optional[Dict[str, Dict[str, float]]] = None) -> Dict[str, str]:
    canon = canonicals if canonicals is not None else load_canonicals()
    return {item: archetype_for_item(item, canon) for item in canon if item not in rec.FORBIDDEN_ITEMS}


def dominant_item(key: Optional[Dict[str, float]]) -> Optional[str]:
    """The heaviest item of a day key (ties broken by menu order, so it is deterministic)."""
    if not key:
        return None
    order = {it: i for i, it in enumerate(rec.MENU_ITEMS)}
    return sorted(key.items(), key=lambda kv: (-float(kv[1]), order.get(kv[0], 99)))[0][0]


def second_family_item(key: Optional[Dict[str, float]]) -> Optional[str]:
    """The heaviest item belonging to a family other than the key's leading family."""
    lead = dominant_item(key)
    if not lead or not key:
        return None
    lead_family = rec.FAMILY_OF.get(lead)
    order = {it: i for i, it in enumerate(rec.MENU_ITEMS)}
    rivals = [(it, w) for it, w in key.items()
              if rec.FAMILY_OF.get(it) != lead_family and float(w) > 0]
    if not rivals:
        return None
    return sorted(rivals, key=lambda kv: (-float(kv[1]), order.get(kv[0], 99)))[0][0]


# ---------------------------------------------------------------------------
# references
# ---------------------------------------------------------------------------

def own_edition_comp_ids(fc_race_id: Optional[str | int], year: Optional[int],
                         db_path: Optional[Path]) -> Set[int]:
    """Every competition id this race ran in an earlier year (for the preference sort)."""
    if not fc_race_id or not year or not db_path or not Path(db_path).exists():
        return set()
    try:
        con = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    except sqlite3.Error:
        return set()
    try:
        rows = con.execute(
            "SELECT c.id FROM competitions c JOIN races r ON c.race_id = r.id "
            "WHERE r.fc_race_id = ? AND r.year < ?", (str(fc_race_id), int(year))).fetchall()
    except sqlite3.Error:
        return set()
    finally:
        con.close()
    return {int(r[0]) for r in rows}


def own_edition_gc_refs(fc_race_id: str | int, year: int, *, limit: int = REFS_PER_SCENARIO,
                        db_path: Optional[Path] = None) -> List[int]:
    """GC competition ids of this race's ``limit`` most recent earlier editions (newest first).

    Same shape as ``oneday.own_edition_refs`` — only editions with a
    ``competition_field_features`` row can be averaged into a profile.
    """
    if not db_path or not Path(db_path).exists():
        return []
    try:
        con = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    except sqlite3.Error:
        return []
    try:
        rows = con.execute(
            """
            SELECT c.id
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            JOIN competition_field_features cff ON cff.competition_id = c.id
            WHERE r.fc_race_id = ? AND r.year < ? AND c.competition_type = 'gc'
            ORDER BY r.year DESC, c.date DESC
            LIMIT ?
            """, (str(fc_race_id), int(year), int(limit))).fetchall()
    except sqlite3.Error:
        return []
    finally:
        con.close()
    return [int(r[0]) for r in rows]


def _candidates(*, archetype: Optional[str], where: Sequence[str], campaign_dir: Optional[Path],
                signatures: Optional[Path], db_path: Optional[Path]) -> List[Dict[str, Any]]:
    try:
        out = query_refs(archetype=archetype, where=list(where), campaign_dir=campaign_dir,
                         signatures=signatures, top=400, db_path=db_path)
    except FileNotFoundError as exc:
        raise AutoConfigError(
            "no experiments/selection_signatures_*.csv.gz: references cannot be machine-chosen "
            "(the release bundle must carry the signature table)") from exc
    return list(out.get("refs") or [])


def pick_refs(archetype: str, *, campaign_dir: Optional[Path] = None, db_path: Optional[Path] = None,
              signatures: Optional[Path] = None, category: Optional[str] = None,
              own_ids: Optional[Set[int]] = None, exclude: Optional[Set[int]] = None,
              count: int = REFS_PER_SCENARIO, competition_type: str = "stage") -> Tuple[List[int], Dict[str, Any]]:
    """``count`` reference competitions for an archetype, best first, plus a provenance dict.

    Preference order: this race's own earlier editions, then the same category
    tier as the campaign, then the most recent day that matches the archetype.
    References the campaign has already spent are never reused (``refs.used_refs``
    via ``campaign_dir``, plus the in-run ``exclude`` set).  When the archetype
    matches fewer than ``count`` unspent days the set is topped up from any day
    of the same competition type, and the note says so.
    """
    exclude = set(exclude or ())
    own = set(own_ids or ())
    rows = _candidates(archetype=archetype, where=[], campaign_dir=campaign_dir,
                       signatures=signatures, db_path=db_path)
    rows = [r for r in rows if int(r["comp_id"]) not in exclude]
    cat = str(category or "").lower()

    def rank(row: Dict[str, Any]) -> Tuple[int, int]:
        return (0 if int(row["comp_id"]) in own else 1,
                0 if cat and str(row.get("category") or "").lower() == cat else 1)

    rows.sort(key=rank)                       # stable: query_refs already ordered newest first
    chosen = rows[:count]
    topped_up = 0
    if len(chosen) < count:
        have = {int(r["comp_id"]) for r in chosen}
        extra = _candidates(archetype=None, where=[f"competition_type=={competition_type}"],
                            campaign_dir=campaign_dir, signatures=signatures, db_path=db_path)
        extra = [r for r in extra if int(r["comp_id"]) not in exclude and int(r["comp_id"]) not in have]
        extra.sort(key=rank)
        topped_up = min(count - len(chosen), len(extra))
        chosen = chosen + extra[:count - len(chosen)]
    ids = [int(r["comp_id"]) for r in chosen]
    meta = {
        "archetype": archetype,
        "doc": ARCHETYPES.get(archetype, {}).get("doc"),
        "own_editions": [i for i in ids if i in own],
        "category": cat or None,
        "n_same_category": sum(1 for r in chosen if cat and str(r.get("category") or "").lower() == cat),
        "topped_up": topped_up,
        "rows": [{k: r.get(k) for k in ("comp_id", "race_name", "year", "date", "stage_number",
                                        "category", "rule_type", "winner")} for r in chosen],
    }
    return ids, meta


def refs_note(item: str, meta: Dict[str, Any]) -> str:
    """The sentence a generated scenario carries instead of a human's reference rationale."""
    names = ", ".join(
        f"{r.get('race_name') or 'race'} {int(r['year']) if r.get('year') else ''}"
        + (f" stage {int(r['stage_number'])}" if r.get("stage_number") else "")
        for r in (meta.get("rows") or []))
    bits = [
        f"References chosen by the driver, not by a human: the day key leads with {item} "
        f"({ITEM_PROSE.get(item, item)}), which maps to the {meta.get('archetype')} archetype "
        f"({meta.get('doc')}).",
    ]
    if meta.get("own_editions"):
        bits.append(f"{len(meta['own_editions'])} of them are this race's own earlier editions.")
    if meta.get("n_same_category"):
        bits.append(f"{meta['n_same_category']} are at the campaign's own category tier.")
    if meta.get("topped_up"):
        bits.append(f"{meta['topped_up']} had to be topped up from outside the archetype filter "
                    "(too few unspent matching days).")
    if names:
        bits.append(f"Reference days: {names}.")
    return " ".join(bits)


# ---------------------------------------------------------------------------
# the stage config
# ---------------------------------------------------------------------------

def stage_label(stage: int, entry: Optional[Dict[str, Any]] = None) -> str:
    """``Stage 7 — Aubel → Spa, 168.5 km`` when the campaign knows the route, else ``Stage 7``."""
    label = f"Stage {int(stage)}"
    if not entry:
        return label
    towns = (entry.get("towns") or "").strip() if isinstance(entry.get("towns"), str) else None
    dist = entry.get("distance_km")
    tail = []
    if towns:
        tail.append(towns)
    if dist not in (None, ""):
        try:
            tail.append(f"{float(dist):g} km")
        except (TypeError, ValueError):
            pass
    return f"{label} — " + ", ".join(tail) if tail else label


MAIN_SCENARIO = "main_read"


def build_stage_skeleton(*, slug: str, stage: int, fc_race_id: Optional[str], year: Optional[int],
                         date: Optional[str], label: str, void_stages: Sequence[int] = ()) -> Dict[str, Any]:
    """A stage config with one reference-less scenario: references need the key, which comes later.

    ``odds_capture`` / ``event_id`` are deliberately absent — the preview's odds
    step fills them when Kambi lists a market, and most ``.1`` / ``.Pro`` races
    have none, which is not an error.
    """
    return {
        "stage": int(stage),
        "fc_race_id": str(fc_race_id) if fc_race_id is not None else None,
        "year": int(year) if year is not None else None,
        "date": date,
        "label": label,
        "void_stages": sorted({int(v) for v in void_stages}),
        "config_source": CONFIG_SOURCE,
        "config_note": ("Written by the nightly driver from campaign.json: this race ships no "
                        "TEMPLATE_scenarios.json, so the day's boards, its references and its "
                        "alternate branch are all machine-chosen. Nothing here is a human read."),
        "scenarios": {
            MAIN_SCENARIO: {
                "label": "The main read — the day as the key says it goes",
                "short": "Main read",
                "refs": [],
                "tag": f"{slug}_st{int(stage):02d}_{MAIN_SCENARIO}",
                "note": ("The main board. It inherits the config-root day key and is priced on the "
                         "reference set that key selects."),
            }
        },
    }


def alternate_scenario(key: Dict[str, float], *, slug: str, stage: int) -> Optional[Tuple[str, Dict[str, Any]]]:
    """``(scenario_key, spec)`` for the key's second-weighted family, or None when it has only one."""
    item = second_family_item(key)
    if not item:
        return None
    family = rec.FAMILY_OF.get(item, "other")
    name = f"alt_{item}"
    spec = {
        "label": f"The other branch — {ITEM_PROSE.get(item, item)}",
        "short": f"Alt: {item}",
        "refs": [],
        "tag": f"{slug}_st{int(stage):02d}_{name}",
        "day_key": {item: 1.0},
        "note": (f"The alternate branch, chosen by the driver because the day key carries weight in a "
                 f"second family ({FAMILY_PROSE.get(family, family)}). It is priced as if that shape "
                 f"were certain, so the two boards bracket the read."),
    }
    return name, spec


def scenarios_missing_refs(config: Dict[str, Any]) -> List[str]:
    out = []
    for key, spec in (config.get("scenarios") or {}).items():
        if not isinstance(spec, dict):
            continue
        refs = [x for x in (spec.get("refs") or spec.get("base_refs") or []) if _positive(x)]
        if not refs:
            out.append(key)
    return out


def _positive(x: Any) -> bool:
    try:
        return int(x) > 0
    except (TypeError, ValueError):
        return False


def fill_scenario_refs(config: Dict[str, Any], *, key: Optional[Dict[str, float]], slug: str,
                       campaign_dir: Optional[Path] = None, db_path: Optional[Path] = None,
                       signatures: Optional[Path] = None, category: Optional[str] = None,
                       canonicals: Optional[Dict[str, Dict[str, float]]] = None,
                       count: int = REFS_PER_SCENARIO) -> Dict[str, Any]:
    """Fill every reference-less scenario of a stage config from the day key.

    A scenario's own ``day_key`` wins over the config root, so the alternate
    branch is priced on its own shape.  Returns a report; the caller writes the
    file.
    """
    canon = canonicals if canonicals is not None else load_canonicals()
    own = own_edition_comp_ids(config.get("fc_race_id"), config.get("year"), db_path)
    exclude: Set[int] = set()
    for spec in (config.get("scenarios") or {}).values():
        if isinstance(spec, dict):
            exclude.update(int(x) for x in (spec.get("refs") or spec.get("base_refs") or []) if _positive(x))
    filled: Dict[str, Any] = {}
    for skey in scenarios_missing_refs(config):
        spec = config["scenarios"][skey]
        skey_key = spec.get("day_key") or key or config.get("day_key")
        item = dominant_item(rec.normalise_key(skey_key) if skey_key else None)
        if not item:
            raise AutoConfigError(f"scenario {skey}: no day key to choose references from")
        archetype = archetype_for_item(item, canon)
        ids, meta = pick_refs(archetype, campaign_dir=campaign_dir, db_path=db_path, signatures=signatures,
                              category=category, own_ids=own, exclude=exclude, count=count)
        if not ids:
            raise AutoConfigError(f"scenario {skey}: the signature table has no unspent {archetype} day to reference")
        exclude.update(ids)
        spec["refs"] = ids
        spec["refs_source"] = REFS_SOURCE
        spec["refs_archetype"] = archetype
        spec["refs_item"] = item
        spec["refs_note"] = refs_note(item, meta)
        filled[skey] = {"archetype": archetype, "item": item, "refs": ids,
                        "own_editions": meta["own_editions"], "topped_up": meta["topped_up"]}
    if filled:
        config["refs_source"] = REFS_SOURCE
    return {"filled": filled, "scenarios": sorted(filled), "slug": slug}


# ---------------------------------------------------------------------------
# the GC config
# ---------------------------------------------------------------------------

def build_gc_skeleton(*, slug: str, fc_race_id: Optional[str], year: Optional[int], date: Optional[str],
                      refs: Sequence[int], source: str, void_stages: Sequence[int] = (),
                      race_name: Optional[str] = None) -> Dict[str, Any]:
    """The stage race's ``predictions/gc/scenarios.json`` — minimal, valid, machine-written."""
    note = ("Pre-race heads on the averaged profile of "
            + ("this race's own earlier editions" if source == "own_editions"
               else "recent stage-race general classifications")
            + ". Written by the nightly driver, not by a human; the settle step re-stamps the "
              "state sentence after each stage.")
    return {
        "target": "gc",
        "fc_race_id": str(fc_race_id) if fc_race_id is not None else None,
        "year": int(year) if year is not None else None,
        "date": date,
        "label": "General Classification",
        "config_source": CONFIG_SOURCE,
        "void_stages": sorted({int(v) for v in void_stages}),
        "scenarios": {
            "gc": {
                "label": f"General classification — {race_name or slug}",
                "short": "GC",
                "refs": [int(r) for r in refs],
                "tag": f"{slug}_gc",
                "refs_source": ("auto:own_editions" if source == "own_editions" else GC_REFS_SOURCE),
                "note": note,
            }
        },
    }


def gc_refs(*, fc_race_id: Optional[str], year: Optional[int], campaign_dir: Optional[Path],
            db_path: Optional[Path], signatures: Optional[Path], category: Optional[str] = None,
            count: int = REFS_PER_SCENARIO) -> Tuple[List[int], str]:
    """``(refs, source)`` for a GC board: own earlier editions when ≥ 3, else GC archetype days."""
    own: List[int] = []
    if fc_race_id and year:
        own = own_edition_gc_refs(fc_race_id, year, limit=count, db_path=db_path)
    if len(own) >= GC_OWN_EDITION_MIN:
        return own, "own_editions"
    rows = _candidates(archetype=None, where=["competition_type==gc"], campaign_dir=campaign_dir,
                       signatures=signatures, db_path=db_path)
    cat = str(category or "").lower()
    rows.sort(key=lambda r: 0 if cat and str(r.get("category") or "").lower() == cat else 1)
    ids = [int(r["comp_id"]) for r in rows[:count]]
    return ids, "archetype"


def validate_gc_config(config: Dict[str, Any]) -> List[str]:
    """Problems with a generated GC config; empty means it can be served."""
    problems: List[str] = []
    if config.get("target") != "gc":
        problems.append(f"target is {config.get('target')!r}, not 'gc'")
    for field in ("fc_race_id", "year", "date", "label"):
        if config.get(field) in (None, ""):
            problems.append(f"config lacks {field}")
    scenarios = config.get("scenarios")
    if not isinstance(scenarios, dict) or not scenarios:
        problems.append("config lacks scenarios")
        return problems
    for key, spec in scenarios.items():
        if not isinstance(spec, dict):
            problems.append(f"scenario {key}: not an object")
            continue
        if not spec.get("tag"):
            problems.append(f"scenario {key}: no tag")
        if not spec.get("label"):
            problems.append(f"scenario {key}: no label")
        if not [x for x in (spec.get("refs") or spec.get("base_refs") or []) if _positive(x)]:
            problems.append(f"scenario {key}: placeholder/missing refs")
        if spec.get("day_key"):
            problems.append(f"scenario {key}: a GC board carries no day key")
    return problems


def describe_mapping(canonicals: Optional[Dict[str, Dict[str, float]]] = None) -> List[Dict[str, Any]]:
    """The item → archetype table, for reports and tests."""
    canon = canonicals if canonicals is not None else load_canonicals()
    rows = []
    for item in rec.MENU_ITEMS:
        if item not in canon:
            continue
        rows.append({"item": item, "family": rec.FAMILY_OF.get(item),
                     "archetype": archetype_for_item(item, canon),
                     "prose": ITEM_PROSE.get(item)})
    return rows
