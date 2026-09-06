"""Slice parity: the same configs must price identically on the slice (§2.10 step 3).

Runs ``db_trace`` twice — once against the full database, once with
``CYCLING_DB_PATH`` pointing at the slice — and compares every scenario JSON
rider-by-rider.  Every numeric column (all probability heads, DNF-adjusted
prices, time gap, ranks, Elo, day-menu scores) must be identical; the slice
run's trace must show no connection to any database other than the slice.

Usage::

    uv run python -m cycling_project.nightly.slice_parity --slice inference_slice.db
    uv run python -m cycling_project.nightly.slice_parity --slice S --full-outputs DIR  # reuse a full run

Exit 0 on parity, 1 on any difference.  The fix for a difference is in
``export_slice.py`` (widen what the slice keeps), never in the outputs.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from cycling_project.db_path import ENV_VAR as DB_ENV_VAR, default_db_path
from cycling_project.nightly.db_trace import DEFAULT_CONFIGS, synth_one_day_config
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IGNORE_KEYS = {"team_name", "rider_name", "book_odds", "book_devig"}  # non-model columns


def run_configs(db_path: Path, outputs_dir: Path, trace_report: Optional[Path],
                extra_args: Sequence[str] = ()) -> None:
    env = dict(os.environ, **{DB_ENV_VAR: str(db_path), "PYTHONUNBUFFERED": "1",
                              "SCRAPER_USE_BROWSER": "0"})
    cmd = [sys.executable, "-m", "cycling_project.nightly.db_trace",
           "--outputs-dir", str(outputs_dir), "--no-row-counts", *extra_args]
    if trace_report is None:
        cmd.append("--no-trace")
    else:
        cmd += ["--out", str(trace_report)]
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=True)


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        if math.isnan(a) and math.isnan(b):
            return True
        return a == b
    return a == b


def compare_outputs(full_dir: Path, slice_dir: Path) -> Tuple[List[str], Dict[str, int]]:
    """Return (problems, columns_compared)."""
    problems: List[str] = []
    compared: Dict[str, int] = {}
    full_files = sorted(p.relative_to(full_dir) for p in full_dir.rglob("*.json"))
    slice_files = sorted(p.relative_to(slice_dir) for p in slice_dir.rglob("*.json"))
    if full_files != slice_files:
        problems.append(f"file sets differ: {sorted(set(full_files) ^ set(slice_files))}")
    for rel in full_files:
        if rel not in slice_files:
            continue
        a = json.loads((full_dir / rel).read_text())
        b = json.loads((slice_dir / rel).read_text())
        for key in ("scenario", "target", "stage_number", "board", "day_key", "state", "references"):
            if a.get(key) != b.get(key):
                problems.append(f"{rel}: header {key} differs: {a.get(key)!r} vs {b.get(key)!r}")
        ra = {int(r["rider_id"]): r for r in a["riders"]}
        rb = {int(r["rider_id"]): r for r in b["riders"]}
        if set(ra) != set(rb):
            problems.append(f"{rel}: rider sets differ ({len(set(ra) ^ set(rb))} ids)")
        for rid in sorted(set(ra) & set(rb)):
            for col, va in ra[rid].items():
                if col in IGNORE_KEYS:
                    continue
                vb = rb[rid].get(col)
                if isinstance(va, (int, float)) or isinstance(vb, (int, float)):
                    compared[col] = compared.get(col, 0) + 1
                if not _same(va, vb):
                    if len(problems) < 200:
                        problems.append(f"{rel}: rider {rid} {col}: {va!r} vs {vb!r}")
    return problems, compared


def check_trace_db_files(trace_report: Path, slice_path: Path) -> List[str]:
    report = json.loads(trace_report.read_text())
    opened = {os.path.realpath(p) for p in report.get("db_files_opened", [])}
    bad = sorted(p for p in opened if p != os.path.realpath(str(slice_path)))
    return [f"slice run opened a foreign database: {p}" for p in bad]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--slice", type=Path, required=True)
    ap.add_argument("--full-db", type=Path, default=None)
    ap.add_argument("--full-outputs", type=Path, default=None,
                    help="reuse scenario JSONs from an earlier full-DB run")
    ap.add_argument("--work-dir", type=Path, default=None)
    ap.add_argument("--config", action="append", type=Path, default=None,
                    help="scenarios.json to run (repeatable; default = db_trace defaults "
                         "+ a synthesised one-day config)")
    ap.add_argument("--one-day-race", default="11",
                    help="preferred FirstCycling race id for the synthesised one-day config")
    args = ap.parse_args(argv)

    work = Path(args.work_dir or tempfile.mkdtemp(prefix="slice_parity_"))
    full_db = Path(args.full_db or default_db_path()).resolve()
    slice_path = args.slice.resolve()
    extra: List[str] = ["--no-one-day"]
    for c in args.config or list(DEFAULT_CONFIGS):
        extra += ["--config", str(c)]
    if not args.config:
        # One synthesised one-day config from the FULL database, run on both
        # sides (synthesising per side would pick different races).  Its
        # race must be a horizon key of the slice: export with --race FC:YEAR.
        synth = synth_one_day_config(str(full_db), args.one_day_race)
        if synth is None:
            print("no cached one-day startlist in the full DB; one-day path not compared")
        else:
            cfg_dir = work / "one-day-parity" / "predictions" / "one_day"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            cfg = cfg_dir / "scenarios.json"
            cfg.write_text(json.dumps(synth, indent=2, ensure_ascii=False))
            extra += ["--config", str(cfg)]
            print(f"one-day config: {synth['race']} {synth['year']} "
                  f"(fc {synth['fc_race_id']}; refs {synth['scenarios']['trace_one_day']['refs']})")

    full_out = args.full_outputs
    if full_out is None:
        full_out = work / "full"
        print(f"## full-DB run -> {full_out}", flush=True)
        run_configs(full_db, full_out, None, extra)
    slice_out = work / "slice"
    slice_trace = work / "slice_trace.json"
    print(f"## slice run -> {slice_out}", flush=True)
    run_configs(slice_path, slice_out, slice_trace, extra)

    problems, compared = compare_outputs(Path(full_out), slice_out)
    problems += check_trace_db_files(slice_trace, slice_path)
    n_files = len(list(slice_out.rglob("*.json")))
    print(f"\n=== parity: {n_files} scenario files, "
          f"{sum(compared.values())} numeric cells over {len(compared)} columns ===")
    print("columns: " + ", ".join(sorted(compared)))
    if problems:
        print(f"FAIL: {len(problems)} differences")
        for p in problems[:60]:
            print("  " + p)
        return 1
    print("PASS: every compared value identical; slice run touched only the slice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
