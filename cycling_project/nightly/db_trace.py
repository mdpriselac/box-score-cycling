"""Trace every SQLite statement the scenario runner issues (§2.10 step 1).

Runs ``netlify_site/build/predict_stage_scenarios.py --no-log`` in-process
for a stage config, the GC config and a one-day config, with
``sqlite3.connect`` monkeypatched process-wide so every connection — the
runner's own, ``pandas.read_sql`` callers, the form/Elo/DNF/day-menu
helpers — gets a ``set_trace_callback``.  Statements arrive with their bound
parameters expanded, so the report can list the rider ids, competition ids
and dates the serving path actually touches, and the tables it reads.  That
report is the specification for ``export_slice.py``.

Usage::

    uv run python -m cycling_project.nightly.db_trace                 # default 3 configs
    uv run python -m cycling_project.nightly.db_trace --config A --config B
    uv run python -m cycling_project.nightly.db_trace --no-trace --outputs-dir X

``--no-trace`` just runs the configs and collects their scenario JSONs into
``--outputs-dir`` (used by the slice parity check, which runs this twice
with different ``CYCLING_DB_PATH`` values).

The configs are copied into a scratch campaign layout before running, so
the campaign directories in ``performance_eval/`` are never written to.
No one-day config exists in the runner's format, so one is synthesised from
the most recent one-day race with a cached startlist (its three prior
editions as ``refs``) and embedded in the report for reproducibility.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import runpy
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from cycling_project.db_path import default_db_path
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNNER = PROJECT_ROOT / "netlify_site" / "build" / "predict_stage_scenarios.py"
RUNS_DIR = PROJECT_ROOT / "performance_eval" / "runs"
DEFAULT_CONFIGS = (
    PROJECT_ROOT / "performance_eval" / "vuelta-2026" / "predictions" / "stage_15" / "scenarios.json",
    PROJECT_ROOT / "performance_eval" / "vuelta-2026" / "predictions" / "gc" / "scenarios.json",
)

# Predicate columns worth reporting (ids, dates, categorical keys).
_PREDICATE_COL = re.compile(
    r"\b(?:[a-z_]+\.)?"
    r"(id|rider_id|competition_id|race_id|fc_race_id|fc_rider_id|team_id|"
    r"year|date|stage_number|stage_id|competition_type|category|"
    r"race_category|place_bucket|competition_date)"
    r"\s*(=|!=|<>|>=|<=|>|<|IN|NOT IN)\s*"
    r"(\((?:[^()]|\([^()]*\))*\)|'(?:[^']|'')*'|-?\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_TABLE_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE(?:\s+IF\s+NOT\s+EXISTS)?)\s+"
    r"(?:\"([^\"]+)\"|`([^`]+)`|([A-Za-z_][A-Za-z0-9_]*))",
    re.IGNORECASE,
)
_STR_LIT = re.compile(r"'(?:[^']|'')*'")
_NUM_LIT = re.compile(r"(?<![A-Za-z_\d])-?\d+(?:\.\d+)?(?![A-Za-z_\d])")
_IN_LIST = re.compile(r"IN\s*\(\s*\?(?:\s*,\s*\?)*\s*\)", re.IGNORECASE)
_WS = re.compile(r"\s+")


def _shape(sql: str) -> str:
    """Parameter-free, whitespace-normalised form of a statement."""
    s = _STR_LIT.sub("'?'", sql)
    s = _NUM_LIT.sub("?", s)
    s = _IN_LIST.sub("IN (?...)", s)
    return _WS.sub(" ", s).strip()


def _tables(sql: str, known: Optional[set] = None) -> List[str]:
    out: List[str] = []
    for m in _TABLE_REF.finditer(sql):
        name = next(g for g in m.groups() if g)
        if known is not None and name not in known:
            continue
        if name not in out:
            out.append(name)
    return out


def _literal(token: str):
    token = token.strip()
    if token.startswith("'"):
        return token[1:-1].replace("''", "'")
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return token


def _predicates(sql: str) -> Dict[str, List]:
    """column -> literal values used in comparisons / IN lists."""
    found: Dict[str, List] = defaultdict(list)
    for m in _PREDICATE_COL.finditer(sql):
        col, _op, rhs = m.group(1).lower(), m.group(2), m.group(3)
        if rhs.startswith("("):
            inner = rhs[1:-1]
            if re.match(r"\s*SELECT\b", inner, re.IGNORECASE):
                continue  # subquery, not literals
            values = [_literal(v) for v in re.split(r",\s*", inner.strip()) if v.strip()]
        else:
            values = [_literal(rhs)]
        found[col].extend(v for v in values if isinstance(v, (int, float, str)))
    return dict(found)


class StatementTracer:
    """Process-wide ``sqlite3.connect`` wrapper that records every statement."""

    def __init__(self) -> None:
        self.connections: List[dict] = []
        self.statements: List[dict] = []
        self._orig_connect = None
        self.current_config: Optional[str] = None

    def install(self) -> None:
        if self._orig_connect is not None:
            return
        self._orig_connect = sqlite3.connect
        tracer = self

        def _connect(*args, **kwargs):
            conn = tracer._orig_connect(*args, **kwargs)
            database = args[0] if args else kwargs.get("database")
            cid = len(tracer.connections)
            tracer.connections.append({
                "id": cid,
                "database": os.fspath(database) if database is not None else None,
                "config": tracer.current_config,
            })
            conn.set_trace_callback(lambda sql, cid=cid: tracer._record(cid, sql))
            return conn

        sqlite3.connect = _connect  # type: ignore[assignment]

    def uninstall(self) -> None:
        if self._orig_connect is not None:
            sqlite3.connect = self._orig_connect  # type: ignore[assignment]
            self._orig_connect = None

    def _record(self, cid: int, sql: str) -> None:
        self.statements.append({
            "conn": cid,
            "config": self.current_config,
            "sql": sql,
        })


# ---------------------------------------------------------------------------
# Config preparation
# ---------------------------------------------------------------------------

def _campaign_layout(config_path: Path, scratch: Path, label: str) -> Path:
    """Copy a scenarios.json into ``<scratch>/<campaign>/predictions/<unit>/``.

    The runner writes its per-scenario JSONs next to the config and resolves
    the odds archive two levels up, so the copy carries an absolute
    ``odds_root`` pointing back at the real campaign's odds directory.
    """
    config = json.loads(config_path.read_text())
    unit = config_path.parent.name
    campaign_dir = config_path.parents[2]
    dest_dir = scratch / label / "predictions" / unit
    dest_dir.mkdir(parents=True, exist_ok=True)
    if "odds_root" not in config and (campaign_dir / "odds").is_dir():
        config["odds_root"] = str(campaign_dir / "odds")
    dest = dest_dir / "scenarios.json"
    dest.write_text(json.dumps(config, indent=2, ensure_ascii=False))
    return dest


def synth_one_day_config(db_path: str, prefer_fc_race_id: Optional[str] = None) -> Optional[dict]:
    """A one-day scenario config from the newest cached one-day startlist.

    ``refs`` are the three most recent prior editions with a ``one_day``
    competition in the DB — the same construction a human would choose for
    a real preview.  Returns None when no cached one-day startlist exists.
    """
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            """
            SELECT r.fc_race_id, r.year, r.name, r.date, r.category
            FROM (SELECT DISTINCT fc_race_id, year FROM cached_start_lists) csl
            JOIN races r ON r.fc_race_id = csl.fc_race_id AND r.year = csl.year
            WHERE r.is_stage_race = 0 AND r.date IS NOT NULL
            ORDER BY (r.fc_race_id = ?) DESC, r.date DESC
            """,
            (str(prefer_fc_race_id) if prefer_fc_race_id else "",),
        ).fetchall()
        if not rows:
            return None
        fc_race_id, year, name, race_date, category = rows[0]
        refs = [
            int(cid) for (cid,) in conn.execute(
                """
                SELECT c.id FROM competitions c
                JOIN races r ON r.id = c.race_id
                WHERE r.fc_race_id = ? AND r.year < ? AND c.competition_type = 'one_day'
                ORDER BY r.year DESC LIMIT 3
                """,
                (str(fc_race_id), int(year)),
            ).fetchall()
        ]
    return {
        "race": name,
        "fc_race_id": int(fc_race_id),
        "year": int(year),
        "date": race_date,
        "category": category,
        "target": "one_day",
        "synthesised_by": "cycling_project.nightly.db_trace",
        "scenarios": {
            "trace_one_day": {
                "label": f"{name} {year} (trace)",
                "short": "trace",
                "tag": "trace",
                "refs": refs,
            }
        },
    }


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

def run_runner(config_path: Path) -> None:
    """Execute the scenario runner in-process for one config."""
    argv = sys.argv
    sys.argv = [str(RUNNER), str(config_path), "--no-log"]
    try:
        runpy.run_path(str(RUNNER), run_name="__main__")
    except SystemExit as exc:  # argparse / sys.exit inside the runner
        if exc.code not in (None, 0):
            raise RuntimeError(f"runner exited {exc.code} for {config_path}")
    finally:
        sys.argv = argv


def prepare_configs(
    configs: Sequence[Path],
    scratch: Path,
    db_path: str,
    one_day: bool = True,
    prefer_one_day: Optional[str] = None,
) -> List[dict]:
    """Return [{label, source, path, target, config}] ready to run."""
    prepared = []
    for cfg in configs:
        cfg = Path(cfg).resolve()
        label = f"{cfg.parents[2].name}"
        dest = _campaign_layout(cfg, scratch, label)
        prepared.append({
            "label": f"{label}/{cfg.parent.name}",
            "source": str(cfg.relative_to(PROJECT_ROOT)) if cfg.is_relative_to(PROJECT_ROOT) else str(cfg),
            "path": dest,
            "target": json.loads(cfg.read_text()).get("target", "stage"),
        })
    if one_day:
        synth = synth_one_day_config(db_path, prefer_one_day)
        if synth is None:
            logger.warning("no cached one-day startlist found; one-day path not traced")
        else:
            dest_dir = scratch / "one-day-trace" / "predictions" / "one_day"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / "scenarios.json"
            dest.write_text(json.dumps(synth, indent=2, ensure_ascii=False))
            prepared.append({
                "label": "one-day-trace/one_day",
                "source": "<synthesised>",
                "path": dest,
                "target": "one_day",
                "config": synth,
            })
    return prepared


def collect_outputs(prepared: Iterable[dict], outputs_dir: Path) -> List[Path]:
    """Copy each run's scenario JSONs to ``outputs_dir/<label>/``."""
    copied = []
    for item in prepared:
        dest = outputs_dir / item["label"]
        dest.mkdir(parents=True, exist_ok=True)
        for f in sorted(Path(item["path"]).parent.glob("*.json")):
            if f.name == "scenarios.json":
                continue
            shutil.copy2(f, dest / f.name)
            copied.append(dest / f.name)
    return copied


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _row_count(db_path: str, sql: str, budget_s: float = 30.0) -> Optional[int]:
    """Rows a SELECT/WITH statement returns, re-executed read-only."""
    head = sql.lstrip()[:6].upper()
    if not (head.startswith("SELECT") or head.startswith("WITH")):
        return None
    try:
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            deadline = time.monotonic() + budget_s
            conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 100000)
            return int(conn.execute(f"SELECT COUNT(*) FROM ({sql.rstrip().rstrip(';')})").fetchone()[0])
    except Exception as exc:  # syntax we cannot wrap, interrupted, etc.
        logger.debug(f"row count skipped: {exc}")
        return None


def _summarise_values(values: List) -> dict:
    distinct = sorted({v for v in values if v is not None}, key=lambda v: (str(type(v)), v))
    out = {"n_values": len(values), "n_distinct": len(distinct)}
    if distinct:
        nums = [v for v in distinct if isinstance(v, (int, float))]
        strs = [v for v in distinct if isinstance(v, str)]
        if nums:
            out["min"], out["max"] = min(nums), max(nums)
        if strs:
            out["min_str"], out["max_str"] = min(strs), max(strs)
        out["sample"] = distinct[:25]
        if len(distinct) <= 2000:
            out["values"] = distinct
    return out


def build_report(
    tracer: StatementTracer,
    prepared: List[dict],
    db_path: str,
    count_rows: bool = True,
) -> dict:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        known = {name for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}

    by_shape: Dict[str, dict] = {}
    per_table: Dict[str, dict] = defaultdict(lambda: {
        "statements": 0, "shapes": set(), "max_rows": 0, "predicates": defaultdict(list),
        "configs": set(),
    })
    global_preds: Dict[str, List] = defaultdict(list)
    counted: Dict[str, Optional[int]] = {}

    for st in tracer.statements:
        sql = st["sql"]
        shape = _shape(sql)
        tables = _tables(sql, known)
        preds = _predicates(sql)
        entry = by_shape.setdefault(shape, {
            "shape": shape[:2000],
            "count": 0,
            "tables": tables,
            "configs": set(),
            "row_counts": [],
            "predicates": defaultdict(list),
            "example": sql[:600],
        })
        entry["count"] += 1
        entry["configs"].add(st["config"])
        for col, vals in preds.items():
            entry["predicates"][col].extend(vals)
            global_preds[col].extend(vals)
        rows = None
        if count_rows and tables:
            if sql not in counted:
                counted[sql] = _row_count(db_path, sql)
            rows = counted[sql]
            if rows is not None:
                entry["row_counts"].append(rows)
        for t in tables:
            pt = per_table[t]
            pt["statements"] += 1
            pt["shapes"].add(shape)
            pt["configs"].add(st["config"])
            if rows is not None:
                pt["max_rows"] = max(pt["max_rows"], rows)
            for col, vals in preds.items():
                pt["predicates"][col].extend(vals)

    statements = []
    for e in sorted(by_shape.values(), key=lambda e: (-e["count"], e["shape"])):
        statements.append({
            "shape": e["shape"],
            "count": e["count"],
            "tables": e["tables"],
            "configs": sorted(c for c in e["configs"] if c),
            "rows_max": max(e["row_counts"]) if e["row_counts"] else None,
            "rows_total": sum(e["row_counts"]) if e["row_counts"] else None,
            "predicates": {c: _summarise_values(v) for c, v in e["predicates"].items()},
            "example": e["example"],
        })
    tables = {
        t: {
            "statements": v["statements"],
            "distinct_shapes": len(v["shapes"]),
            "max_rows_single_statement": v["max_rows"],
            "configs": sorted(c for c in v["configs"] if c),
            "predicates": {c: _summarise_values(vals) for c, vals in v["predicates"].items()},
        }
        for t, v in sorted(per_table.items())
    }
    untouched = sorted(known - set(per_table))
    db_files = sorted({c["database"] for c in tracer.connections if c["database"]})
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "db_path": db_path,
        "db_files_opened": db_files,
        "configs": [
            {
                "label": p["label"],
                "source": p["source"],
                "target": p["target"],
                "connections": sum(1 for c in tracer.connections if c["config"] == p["label"]),
                "statements": sum(1 for s in tracer.statements if s["config"] == p["label"]),
                "elapsed_s": p.get("elapsed_s"),
                **({"config": p["config"]} if "config" in p else {}),
            }
            for p in prepared
        ],
        "totals": {
            "connections": len(tracer.connections),
            "statements": len(tracer.statements),
            "distinct_shapes": len(by_shape),
            "tables_touched": len(per_table),
        },
        "tables": tables,
        "tables_untouched": untouched,
        "predicates": {c: _summarise_values(v) for c, v in sorted(global_preds.items())},
        "statements": statements,
    }


def print_summary(report: dict) -> None:
    print("\n=== DB trace summary ===")
    print(f"db files opened: {report['db_files_opened']}")
    for c in report["configs"]:
        print(f"  {c['label']:<32} target={c['target']:<8} conns={c['connections']:<3} "
              f"stmts={c['statements']:<5} {c.get('elapsed_s') or 0:.0f}s")
    t = report["totals"]
    print(f"statements={t['statements']} shapes={t['distinct_shapes']} tables={t['tables_touched']}")
    print(f"{'table':<34} {'stmts':>6} {'shapes':>6} {'max_rows':>9}  predicate columns")
    for name, v in report["tables"].items():
        cols = ", ".join(f"{c}({p['n_distinct']})" for c, p in v["predicates"].items())
        print(f"{name:<34} {v['statements']:>6} {v['distinct_shapes']:>6} "
              f"{v['max_rows_single_statement']:>9}  {cols}")
    print(f"untouched: {', '.join(report['tables_untouched'])}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", action="append", type=Path, default=None,
                    help="scenarios.json to run (repeatable); default: Vuelta stage_15 + gc")
    ap.add_argument("--no-one-day", action="store_true",
                    help="do not synthesise and run a one-day config")
    ap.add_argument("--one-day-race", default="11",
                    help="preferred FirstCycling race id for the synthesised one-day config")
    ap.add_argument("--date", default=dt.date.today().isoformat(),
                    help="date stamp for the report filename")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"report path (default {RUNS_DIR}/db_trace_<date>.json)")
    ap.add_argument("--outputs-dir", type=Path, default=None,
                    help="copy each run's scenario JSONs here (parity input)")
    ap.add_argument("--no-trace", action="store_true",
                    help="run the configs without tracing (parity runs)")
    ap.add_argument("--no-row-counts", action="store_true",
                    help="skip re-executing SELECTs for row counts")
    ap.add_argument("--keep-scratch", action="store_true")
    args = ap.parse_args(argv)

    db_path = str(default_db_path())
    if not Path(db_path).is_file():
        sys.exit(f"database not found: {db_path}")
    configs = args.config or list(DEFAULT_CONFIGS)
    for c in configs:
        if not Path(c).is_file():
            sys.exit(f"config not found: {c}")

    scratch = Path(tempfile.mkdtemp(prefix="db_trace_"))
    prepared = prepare_configs(configs, scratch, db_path,
                               one_day=not args.no_one_day,
                               prefer_one_day=args.one_day_race)
    tracer = StatementTracer()
    if not args.no_trace:
        tracer.install()
    try:
        for item in prepared:
            print(f"\n##### running {item['label']} ({item['target']}) against {db_path}", flush=True)
            tracer.current_config = item["label"]
            t0 = time.monotonic()
            run_runner(item["path"])
            item["elapsed_s"] = round(time.monotonic() - t0, 1)
            tracer.current_config = None
    finally:
        tracer.uninstall()

    if args.outputs_dir:
        copied = collect_outputs(prepared, args.outputs_dir)
        print(f"collected {len(copied)} scenario JSONs into {args.outputs_dir}")

    rc = 0
    if not args.no_trace:
        report = build_report(tracer, prepared, db_path, count_rows=not args.no_row_counts)
        out = args.out or (RUNS_DIR / f"db_trace_{args.date}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        print_summary(report)
        print(f"\nreport: {out}")
    if not args.keep_scratch:
        shutil.rmtree(scratch, ignore_errors=True)
    else:
        print(f"scratch kept: {scratch}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
