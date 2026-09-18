"""``nightly refs`` — hindsight / scenario reference sets from the signature table.

The runbook (Vuelta 2026, open items): "Hindsight reference sets are found
by querying ``experiments/selection_signatures_*.csv.gz`` (wg_size,
winner_margin, frac_120s, top15 archetype shares) joined to ``competitions``;
exclude every ref already used in the campaign."

Archetypes are named filter presets over the signature columns (below);
``--where`` adds ad-hoc clauses (``col<op>value``, e.g. ``top15_mountain>=0.4``).
The winners (place 1 and 2) are joined from ``rider_results`` when the
serving database is reachable, for display only. Nothing here writes.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import io
import json
import operator
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from cycling_project.db_path import default_db_path
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SIGNATURE_GLOB = "selection_signatures_*.csv.gz"

# name -> list of (column, op, value); every clause must hold
ARCHETYPES: Dict[str, Dict[str, Any]] = {
    "bunch_sprint": {"doc": "mass or bunch sprint (winner group ≥ 20)",
                     "where": [("rule_type", "in", ["mass_sprint", "bunch_sprint"])]},
    "reduced_sprint": {"doc": "reduced bunch (8 ≤ winner group < 20)",
                       "where": [("rule_type", "==", "reduced_sprint")]},
    "small_group": {"doc": "small-group finish (4 ≤ winner group < 8)",
                    "where": [("rule_type", "==", "small_group")]},
    "two_up": {"doc": "two- or three-up finish",
               "where": [("wg_size", ">=", 2), ("wg_size", "<=", 3)]},
    "solo": {"doc": "solo win by ≥ 5 s",
             "where": [("wg_size", "==", 1), ("winner_margin", ">=", 5)]},
    "gc_from_two": {"doc": "GC-type mountain finish decided among ≤ 3 (mountain share ≥ 0.4)",
                    "where": [("wg_size", "<=", 3), ("top15_mountain", ">=", 0.4), ("competition_type", "==", "stage")]},
    "mountain_break": {"doc": "mountain day won from the escape: mountain share ≥ 0.35, field spread (frac_120s < 0.5)",
                       "where": [("top15_mountain", ">=", 0.35), ("frac_120s", "<", 0.5), ("competition_type", "==", "stage")]},
    "punchy_select": {"doc": "punchy selection: hilly share ≥ 0.3, winner group ≤ 8",
                      "where": [("top15_hilly", ">=", 0.3), ("wg_size", "<=", 8)]},
    "itt_like": {"doc": "time-separated front (ITT-like)",
                 "where": [("rule_type", "==", "itt_like")]},
}

_OPS = {">=": operator.ge, "<=": operator.le, "==": operator.eq, "!=": operator.ne, ">": operator.gt, "<": operator.lt}
_WHERE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(>=|<=|==|!=|>|<|=|\bin\b)\s*(.+?)\s*$")


def newest_signature_table(experiments_dir: Optional[Path] = None) -> Optional[Path]:
    root = Path(experiments_dir) if experiments_dir else PROJECT_ROOT / "experiments"
    paths = sorted(glob.glob(str(root / SIGNATURE_GLOB)))
    return Path(paths[-1]) if paths else None


def load_signatures(path: Path) -> List[Dict[str, Any]]:
    import csv
    with gzip.open(path, "rb") as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8")
        rows = list(csv.DictReader(text))
    out = []
    for r in rows:
        clean: Dict[str, Any] = {}
        for k, v in r.items():
            if v is None or v == "":
                clean[k] = None
                continue
            try:
                clean[k] = float(v) if re.fullmatch(r"-?\d+(\.\d+)?(e-?\d+)?", v) else v
            except ValueError:
                clean[k] = v
        if clean.get("comp_id") is not None:
            clean["comp_id"] = int(clean["comp_id"])
        out.append(clean)
    return out


def parse_where(expr: str) -> tuple:
    m = _WHERE_RE.match(expr)
    if not m:
        raise ValueError(f"cannot parse --where {expr!r} (expected col<op>value)")
    col, op, raw = m.group(1), m.group(2).strip(), m.group(3).strip()
    if op == "=":
        op = "=="
    if op == "in":
        vals = [v.strip().strip("'\"") for v in raw.strip("[]()").split(",")]
        return (col, "in", vals)
    try:
        val: Any = float(raw)
    except ValueError:
        val = raw.strip("'\"")
    return (col, op, val)


def _holds(row: Dict[str, Any], clause: tuple) -> bool:
    col, op, val = clause
    have = row.get(col)
    if have is None:
        return False
    if op == "in":
        return str(have) in [str(v) for v in val]
    if isinstance(val, (int, float)):
        try:
            return _OPS[op](float(have), float(val))
        except (TypeError, ValueError):
            return False
    return _OPS[op](str(have), str(val))


def used_refs(campaign_dir: Optional[Path]) -> Set[int]:
    """Every competition id any scenario config in the campaign already references."""
    used: Set[int] = set()
    if not campaign_dir:
        return used
    for cfg in Path(campaign_dir).glob("predictions/*/scenarios.json"):
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for spec in (data.get("scenarios") or {}).values():
            if not isinstance(spec, dict):
                continue
            for key in ("refs", "base_refs"):
                for c in spec.get(key) or []:
                    try:
                        used.add(int(c))
                    except (TypeError, ValueError):
                        pass
    return used


def usable_reference_ids(db_path: Optional[Path]) -> Optional[Set[int]]:
    """Competition ids the serving DB can turn into a profile, or ``None`` when it cannot say.

    ``future_race_loader.get_reference_race_profile`` needs a ``competition_field_features``
    row; the signature table is built from the full DB and knows nothing about that, so a
    reference taken from it blind can kill ``predict`` (Tour de Luxembourg stage 4, 2026-09-18:
    ``No competition_field_features found for competition_id=9878``).  ``None`` — no DB, or no
    such table (unit tests) — means "do not filter".
    """
    if not db_path or not Path(db_path).exists():
        return None
    try:
        con = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        return {int(r[0]) for r in con.execute("SELECT competition_id FROM competition_field_features")}
    except sqlite3.Error:
        return None
    finally:
        con.close()


def unusable_refs(comp_ids: Iterable[Any], db_path: Optional[Path]) -> List[int]:
    """The ids among ``comp_ids`` that ``usable_reference_ids`` rules out (empty when it cannot say)."""
    usable = usable_reference_ids(db_path)
    if usable is None:
        return []
    out = []
    for c in comp_ids:
        try:
            if int(c) not in usable:
                out.append(int(c))
        except (TypeError, ValueError):
            continue
    return out


def winners_for(comp_ids: Iterable[int], db_path: Optional[Path] = None) -> Dict[int, Dict[str, Any]]:
    """``comp_id → {name, date, winner, second}`` from the serving DB (best effort)."""
    ids = [int(c) for c in comp_ids]
    if not ids:
        return {}
    path = Path(db_path) if db_path else default_db_path()
    if not path.exists():
        return {}
    out: Dict[int, Dict[str, Any]] = {}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            q = ",".join("?" * len(ids))
            for cid, name, date in con.execute(f"select id, name, date from competitions where id in ({q})", ids):
                out[int(cid)] = {"name": name, "date": date, "winner": None, "second": None}
            for cid, place, rname in con.execute(
                    f"select rr.competition_id, rr.place, r.name from rider_results rr join riders r on r.id = rr.rider_id "
                    f"where rr.competition_id in ({q}) and rr.place in (1, 2)", ids):
                row = out.setdefault(int(cid), {"name": None, "date": None, "winner": None, "second": None})
                row["winner" if int(place) == 1 else "second"] = rname
        finally:
            con.close()
    except sqlite3.Error as exc:  # noqa: BLE001 — display only
        logger.warning("winner join unavailable: %s", exc)
    return out


def query_refs(*, archetype: Optional[str], where: Sequence[str] = (), campaign_dir: Optional[Path] = None,
               signatures: Optional[Path] = None, top: int = 12, min_year: Optional[int] = None,
               categories: Optional[Sequence[str]] = None, db_path: Optional[Path] = None,
               include_used: bool = False) -> Dict[str, Any]:
    table = Path(signatures) if signatures else newest_signature_table()
    if table is None or not table.exists():
        raise FileNotFoundError("no experiments/selection_signatures_*.csv.gz (run label_days / the signature build first)")
    clauses: List[tuple] = []
    if archetype:
        if archetype not in ARCHETYPES:
            raise KeyError(f"unknown archetype {archetype!r}; known: {', '.join(sorted(ARCHETYPES))}")
        clauses.extend(ARCHETYPES[archetype]["where"])
    clauses.extend(parse_where(w) for w in where)
    if min_year:
        clauses.append(("year", ">=", float(min_year)))
    if categories:
        clauses.append(("category", "in", list(categories)))
    rows = load_signatures(table)
    used = set() if include_used else used_refs(campaign_dir)
    hits = [r for r in rows if all(_holds(r, c) for c in clauses) and r["comp_id"] not in used]
    hits.sort(key=lambda r: (str(r.get("date") or ""), r["comp_id"]), reverse=True)
    hits = hits[:top]
    meta = winners_for([h["comp_id"] for h in hits], db_path)
    keep = ("comp_id", "race_name", "year", "date", "stage_number", "category", "competition_type", "rule_type",
            "wg_size", "winner_margin", "chase_gap", "frac_120s", "winner_archetype", "dominant_archetype",
            "top15_sprint", "top15_mountain", "top15_hilly", "top15_rolling", "top15_breakaway", "top15_time_trial")
    out_rows = []
    for h in hits:
        row = {k: h.get(k) for k in keep}
        row.update({k: v for k, v in meta.get(h["comp_id"], {}).items() if k in ("name", "winner", "second")})
        out_rows.append(row)
    return {"archetype": archetype, "doc": ARCHETYPES[archetype]["doc"] if archetype else None,
            "clauses": [list(c) for c in clauses], "signatures": str(table), "excluded_used_refs": sorted(used),
            "n_matched": len([r for r in rows if all(_holds(r, c) for c in clauses)]), "refs": out_rows}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--archetype", choices=sorted(ARCHETYPES), default=None)
    ap.add_argument("--where", action="append", default=[], help="extra clause col<op>value (repeatable)")
    ap.add_argument("--campaign", type=Path, default=None, help="campaign dir whose used refs are excluded")
    ap.add_argument("--signatures", type=Path, default=None)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--min-year", type=int, default=None)
    ap.add_argument("--category", action="append", default=None, help="wt|pro|d1 (repeatable)")
    ap.add_argument("--include-used", action="store_true")
    ap.add_argument("--list", action="store_true", help="list archetypes and exit")
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        print(json.dumps({k: v["doc"] for k, v in ARCHETYPES.items()}, indent=1))
        return 0
    if not args.archetype and not args.where:
        print("give --archetype and/or --where", flush=True)
        return 2
    out = query_refs(archetype=args.archetype, where=args.where, campaign_dir=args.campaign,
                     signatures=args.signatures, top=args.top, min_year=args.min_year,
                     categories=args.category, include_used=args.include_used)
    print(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
