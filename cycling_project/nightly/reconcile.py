"""Weekly PCS ↔ FirstCycling reconciliation (NIGHTLY_AGENT_WORKFLOW.md §2.8).

The nightly agent settles stages from PCS pages; the Mac's weekly run is
the backstop. For every archived ``results/stage_NN/results.csv`` (and the
newest ``gc.csv``) in a campaign directory this compares the PCS-derived
rows with the FirstCycling pickle for the same race under
``SCRAPED_DATA_DIR`` on **place, gap seconds and FC rider id**, appends one
record per unit to ``performance_eval/runs/reconciliation.jsonl``, inserts
``reconciliation`` rows through the store, and exits 10 with an operator
task when the drift is above threshold:

* any classified place where the two sources name a different rider id, or
* more than 2 of the top-20 places differing on id or gap.

Pickle rows are ``{'place','name','rider_id','team','team_id','gap','dob',
'bib_number'}`` (``Race``/``Stage`` from ``webscrape_tools.create_race_data``);
the campaign CSV has ``place,name,rider_id,team,team_id,gap,dob``. Gaps are
seconds; the winner's gap is 0.

Usage::

    uv run python -m cycling_project.nightly.reconcile reconcile \
        --campaign performance_eval/vuelta-2026 --race-id 23 --year 2026
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import pickle
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from cycling_project.nightly.crosswalk import (
    EXIT_FAILED, EXIT_OK, EXIT_WAITING, RUNS_DIR, build_operator_task, campaign_identity,
)
from cycling_project.nightly.store_local import JsonlStore, open_store, utcnow_iso
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

TOURS = ("wt", "pro", "d1")
TOP_N = 20
MAX_TOP_DIFFS = 2
GAP_TOLERANCE = 0.5  # seconds


def default_scraped_dir() -> Path:
    env = os.environ.get("SCRAPED_DATA_DIR") or os.environ.get("DB_PATH")
    if env and Path(env).is_dir():
        return Path(env)
    return Path.home() / "cycling_data" / "scraped_data"


# ---------------------------------------------------------------------------
# Locating the pickle
# ---------------------------------------------------------------------------

def find_race_pickle(scraped_dir: Path, year: int, fc_race_id: str) -> Optional[Path]:
    """``<scraped>/<year>/<tour>/<name>.pkl`` for the race id.

    The ``<tour>.txt`` race list maps name → url (``r=<id>``) so we can pick
    the file without unpickling everything; falls back to scanning pickles.
    """
    year_dir = Path(scraped_dir) / str(year)
    if not year_dir.is_dir():
        return None
    for tour in TOURS:
        lst = year_dir / tour / f"{tour}.txt"
        if lst.exists():
            for line in lst.read_text(encoding="utf-8", errors="replace").splitlines():
                if "," not in line:
                    continue
                name, url = line.rsplit(",", 1)
                m = re.search(r"[?&]r=(\d+)", url)
                if m and m.group(1) == str(fc_race_id):
                    cand = year_dir / tour / f"{name.strip()}.pkl"
                    if cand.exists():
                        return cand
    for tour in TOURS:
        for pkl in sorted((year_dir / tour).glob("*.pkl")) if (year_dir / tour).is_dir() else []:
            try:
                race = pickle.load(open(pkl, "rb"))
            except Exception:  # noqa: BLE001 - corrupt pickle, keep scanning
                continue
            if str(getattr(race, "fc_race_id", None)) == str(fc_race_id):
                return pkl
    return None


def stage_number(stage: Any) -> Optional[int]:
    m = re.search(r"[?&]e=(\d+)", getattr(stage, "url", "") or "")
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", getattr(stage, "name", "") or "")
    return int(m.group(1)) if m else None


def pickle_stage_rows(race: Any, number: int) -> Optional[list[dict[str, Any]]]:
    for st in getattr(race, "stages", []) or []:
        if stage_number(st) == number and not str(getattr(st, "name", "")).upper().startswith("GC"):
            return list(st.results or [])
    return None


def pickle_gc_rows(race: Any) -> list[dict[str, Any]]:
    for st in getattr(race, "stages", []) or []:
        if str(getattr(st, "name", "")).upper().startswith("GC") and st.results:
            return list(st.results)
    return list(getattr(race, "results", []) or [])


# ---------------------------------------------------------------------------
# Diffing
# ---------------------------------------------------------------------------

def _classified(rows: Iterable[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for r in rows:
        place = str(r.get("place", "")).strip()
        if place.isdigit():
            out[int(place)] = r
    return out


def _gap(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class UnitDiff:
    campaign: str
    unit: str                      # "stage_14" or "gc"
    kind: str                      # "stage" | "gc"
    pcs_rows: int
    fc_rows: int
    id_diffs: list[dict[str, Any]] = field(default_factory=list)
    gap_diffs: list[dict[str, Any]] = field(default_factory=list)
    missing_places: list[int] = field(default_factory=list)
    comparable: bool = True
    note: str = ""

    @property
    def top20_diff_places(self) -> list[int]:
        places = {d["place"] for d in self.id_diffs if d["place"] <= TOP_N}
        places |= {d["place"] for d in self.gap_diffs if d["place"] <= TOP_N}
        places |= {p for p in self.missing_places if p <= TOP_N}
        return sorted(places)

    @property
    def drift(self) -> bool:
        return self.comparable and (bool(self.id_diffs) or len(self.top20_diff_places) > MAX_TOP_DIFFS)

    def record(self) -> dict[str, Any]:
        return {
            "campaign": self.campaign, "unit": self.unit, "kind": self.kind,
            "pcs_rows": self.pcs_rows, "fc_rows": self.fc_rows, "comparable": self.comparable,
            "id_diffs": len(self.id_diffs), "gap_diffs": len(self.gap_diffs),
            "missing_places": len(self.missing_places), "top20_diffs": len(self.top20_diff_places),
            "verdict": "drift" if self.drift else ("ok" if self.comparable else "skipped"),
            "sample": (self.id_diffs[:5] + self.gap_diffs[:5]), "note": self.note,
            "checked_at": utcnow_iso(),
        }


def diff_rows(pcs_rows: Iterable[dict[str, Any]], fc_rows: Iterable[dict[str, Any]], *,
              campaign: str, unit: str, kind: str) -> UnitDiff:
    pcs_c, fc_c = _classified(pcs_rows), _classified(fc_rows)
    d = UnitDiff(campaign, unit, kind, pcs_rows=len(pcs_c), fc_rows=len(fc_c))
    if not fc_c:
        d.comparable, d.note = False, "FirstCycling side has no classified rows yet"
        return d
    for place in sorted(set(pcs_c) | set(fc_c)):
        p, f = pcs_c.get(place), fc_c.get(place)
        if p is None or f is None:
            d.missing_places.append(place)
            continue
        pid, fid = str(p.get("rider_id", "")).strip(), str(f.get("rider_id", "")).strip()
        if pid != fid:
            d.id_diffs.append({"place": place, "pcs_rider_id": pid, "fc_rider_id": fid,
                               "pcs_name": p.get("name"), "fc_name": f.get("name")})
            continue
        pg, fg = _gap(p.get("gap")), _gap(f.get("gap"))
        if (pg is None) != (fg is None) or (pg is not None and fg is not None and abs(pg - fg) > GAP_TOLERANCE):
            d.gap_diffs.append({"place": place, "rider_id": pid, "pcs_gap": pg, "fc_gap": fg})
    return d


# ---------------------------------------------------------------------------
# Campaign walk
# ---------------------------------------------------------------------------

def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def reconcile_campaign(campaign_dir: Path, race: Any, *, stages: Optional[Iterable[int]] = None,
                       gc: bool = True) -> list[UnitDiff]:
    """Diff every archived stage (and the newest GC) against the pickle."""
    campaign_dir = Path(campaign_dir)
    diffs: list[UnitDiff] = []
    stage_dirs = sorted(p for p in campaign_dir.glob("results/stage_*") if (p / "results.csv").exists())
    wanted = set(stages) if stages is not None else None
    for sd in stage_dirs:
        num = int(re.sub(r"\D", "", sd.name) or 0)
        if wanted is not None and num not in wanted:
            continue
        fc_rows = pickle_stage_rows(race, num)
        pcs_rows = read_csv_rows(sd / "results.csv")
        if fc_rows is None:
            d = UnitDiff(campaign_dir.name, sd.name, "stage", len(_classified(pcs_rows)), 0,
                         comparable=False, note="stage not in FirstCycling pickle")
        else:
            d = diff_rows(pcs_rows, fc_rows, campaign=campaign_dir.name, unit=sd.name, kind="stage")
        diffs.append(d)
    if gc and stage_dirs:
        newest = stage_dirs[-1]
        gc_csv = newest / "gc.csv"
        if gc_csv.exists():
            fc_gc = pickle_gc_rows(race)
            d = diff_rows(read_csv_rows(gc_csv), fc_gc, campaign=campaign_dir.name,
                          unit=f"gc@{newest.name}", kind="gc")
            if d.comparable and not race_settled(race):
                # Mid-race the pickle GC may be from a later scrape than the
                # archived gc.csv; report but never task on it.
                d.note = "mid-race GC: informational only"
                d.comparable = False
            diffs.append(d)
    return diffs


def race_settled(race: Any) -> bool:
    """A race is settled when the pickle carries a dated GC with results."""
    for st in getattr(race, "stages", []) or []:
        if str(getattr(st, "name", "")).upper().startswith("GC"):
            return bool(st.results) and bool(getattr(st, "date", None))
    return bool(getattr(race, "results", None))


def append_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def run_reconcile(campaign_dir: Path, *, scraped_dir: Path, race_id: Optional[str], year: Optional[int],
                  store: JsonlStore, runs_dir: Path, stages: Optional[Iterable[int]] = None) -> tuple[int, dict[str, Any]]:
    """Returns (exit code, report). Never raises for drift; raises for a missing pickle."""
    campaign_dir = Path(campaign_dir)
    rid, yr = campaign_identity(campaign_dir, race_id, year)
    pkl = find_race_pickle(scraped_dir, yr, rid)
    if pkl is None:
        report = {"campaign": campaign_dir.name, "fc_race_id": rid, "year": yr,
                  "error": f"no FirstCycling pickle for race {rid}/{yr} under {scraped_dir}"}
        return EXIT_FAILED, report
    race = pickle.load(open(pkl, "rb"))
    diffs = reconcile_campaign(campaign_dir, race, stages=stages)
    records = [d.record() for d in diffs]
    for r in records:
        r.update({"fc_race_id": rid, "year": yr, "pickle": str(pkl)})
    # The local JsonlStore mirrors the `reconciliation` table to the same
    # file; only write the ledger ourselves when the store does not.
    if getattr(store, "runs_dir", None) != Path(runs_dir):
        append_jsonl(Path(runs_dir) / "reconciliation.jsonl", records)
    store.insert_reconciliation(records)
    drifted = [d for d in diffs if d.drift]
    task = None
    if drifted:
        task = store.insert_task(build_operator_task(
            "reconciliation_drift", campaign_dir.name,
            f"{len(drifted)} unit(s) differ between PCS and FirstCycling",
            {"units": [{"unit": d.unit, "id_diffs": d.id_diffs[:10], "gap_diffs": d.gap_diffs[:10],
                        "top20_diff_places": d.top20_diff_places} for d in drifted],
             "pickle": str(pkl)},
            urgency="blocks_settlement",
        ))
    report = {"campaign": campaign_dir.name, "fc_race_id": rid, "year": yr, "pickle": str(pkl),
              "units": records, "drift_units": [d.unit for d in drifted], "operator_task": task}
    return (EXIT_WAITING if drifted else EXIT_OK), report


def reconcile_all_campaigns(perf_dir: Path, *, scraped_dir: Path, store: JsonlStore,
                            runs_dir: Path) -> list[dict[str, Any]]:
    """Every campaign dir with a ``campaign.json`` and archived results.
    Used by ``update_pipeline --reconcile``; per-campaign failures are recorded, not raised."""
    out = []
    for cj in sorted(Path(perf_dir).glob("*/campaign.json")):
        cdir = cj.parent
        if not any(cdir.glob("results/stage_*/results.csv")):
            continue
        try:
            code, report = run_reconcile(cdir, scraped_dir=scraped_dir, race_id=None, year=None,
                                         store=store, runs_dir=runs_dir)
        except Exception as e:  # noqa: BLE001 - weekly step must be non-fatal per campaign
            code, report = EXIT_FAILED, {"campaign": cdir.name, "error": str(e)}
        report["exit"] = code
        out.append(report)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="reconcile", description=__doc__.split("\n\n")[0])
    p.add_argument("--scraped-dir", default=None)
    p.add_argument("--runs-dir", default=str(RUNS_DIR))
    p.add_argument("--store", choices=["local", "none", "supabase"], default="local")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("reconcile")
    s.add_argument("--campaign", required=True)
    s.add_argument("--race-id"); s.add_argument("--year", type=int)
    s.add_argument("--stage", type=int, action="append", help="restrict to stage number(s)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    store = open_store(args.store, Path(args.runs_dir), role="agent")
    scraped = Path(args.scraped_dir) if args.scraped_dir else default_scraped_dir()
    code, report = run_reconcile(Path(args.campaign), scraped_dir=scraped, race_id=args.race_id,
                                 year=args.year, store=store, runs_dir=Path(args.runs_dir), stages=args.stage)
    print(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    return code


if __name__ == "__main__":
    sys.exit(main())
