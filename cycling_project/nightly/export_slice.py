"""Export ``inference_slice.db`` — the slim serving database (§2.10 step 2).

The cloud nightly cannot open the 3.3 GB ``cycling_races.db``.  This tool
``ATTACH``es it, copies every schema object from ``sqlite_master`` (tables,
indexes, views ``v_race_results`` / ``v_rider_stats``) and fills only what
the traced serving path reads (``db_trace.py`` report):

===================================  ==========================================
table(s)                             rows copied
===================================  ==========================================
riders, races, competitions, teams,  everything
rider_team_history,
race_history_thresholds
competition_field_features,          everything (serving scans field features
race_feature_gradients,              whole; the rest is ~100 MB and referenced
race_features_10..100 (19),          by competition id)
race_cluster_v1_scores
rider_results                        every rider on a cached startlist of a
                                     horizon race, every rider with a result in
                                     the last ``--active-days`` (so startlists
                                     published after the release still price),
                                     plus every competition referenced as
                                     ``refs``/``base_refs`` in any
                                     ``performance_eval/*/predictions/*/scenarios.json``
                                     and every competition of the horizon races'
                                     current + last three editions
rider_competition_snapshots          the latest row per rider above (the
                                     serving lookup is MAX(competition_id) per
                                     rider) plus every row at the referenced
                                     competitions (one-day signature join)
rider_race_state                     current-year competitions of horizon races
cached_start_lists,                  horizon races
cached_race_results
prediction_log                       empty (identical schema + indexes)
rider_crosswalk                      everything, when the table exists
everything else                      empty
===================================  ==========================================

``VACUUM`` at the end; prints a per-table size table.  Target < 500 MB.

Usage::

    uv run python -m cycling_project.nightly.export_slice --out inference_slice.db --horizon-days 14
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from cycling_project.db_path import default_db_path
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PERF_EVAL = PROJECT_ROOT / "performance_eval"

FULL_TABLES = (
    "riders", "races", "competitions", "teams", "rider_team_history",
    "race_history_thresholds", "competition_field_features",
    "race_feature_gradients", "race_cluster_v1_scores", "rider_crosswalk",
)
FULL_TABLE_PREFIXES = ("race_features_",)
STAGE_RACE_LOOKBACK_DAYS = 25     # a Grand Tour still in progress started ≤ 25 days ago
CONFIG_LOOKBACK_DAYS = 7          # settle-late campaigns
STARTLIST_CACHE_LOOKBACK_DAYS = 30
PRIOR_EDITIONS = 3


# ---------------------------------------------------------------------------
# Inputs from the repo
# ---------------------------------------------------------------------------

def scenario_configs(perf_eval: Path = PERF_EVAL) -> List[Tuple[Path, dict]]:
    out = []
    for cfg in sorted(perf_eval.glob("*/predictions/*/scenarios.json")):
        try:
            out.append((cfg, json.loads(cfg.read_text())))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(f"skipping unreadable config {cfg}: {exc}")
    return out


def referenced_competitions(configs: Iterable[Tuple[Path, dict]]) -> Set[int]:
    refs: Set[int] = set()
    for _, cfg in configs:
        for spec in (cfg.get("scenarios") or {}).values():
            for key in ("refs", "base_refs"):
                for c in spec.get(key) or []:
                    try:
                        refs.add(int(c))
                    except (TypeError, ValueError):
                        pass
    return refs


def config_race_keys(
    configs: Iterable[Tuple[Path, dict]], today: dt.date, horizon_days: int,
) -> Set[Tuple[str, int]]:
    lo = (today - dt.timedelta(days=CONFIG_LOOKBACK_DAYS)).isoformat()
    hi = (today + dt.timedelta(days=horizon_days)).isoformat()
    keys = set()
    for _, cfg in configs:
        d = cfg.get("date")
        if isinstance(d, str) and lo <= d <= hi and cfg.get("fc_race_id") and cfg.get("year"):
            keys.add((str(cfg["fc_race_id"]), int(cfg["year"])))
    return keys


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _table_list(conn: sqlite3.Connection, schema: str) -> List[str]:
    return [n for (n,) in conn.execute(
        f"SELECT name FROM {schema}.sqlite_master WHERE type='table' "
        f"AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def horizon_race_keys(
    conn: sqlite3.Connection, today: dt.date, horizon_days: int,
    configs: Iterable[Tuple[Path, dict]], extra: Iterable[Tuple[str, int]] = (),
) -> Set[Tuple[str, int]]:
    """(fc_race_id, year) pairs the nightly may serve inside the horizon."""
    keys: Set[Tuple[str, int]] = set(config_race_keys(configs, today, horizon_days))
    keys.update((str(k), int(y)) for k, y in extra)
    hi = (today + dt.timedelta(days=horizon_days)).isoformat()
    lo_one_day = (today - dt.timedelta(days=CONFIG_LOOKBACK_DAYS)).isoformat()
    lo_stage = (today - dt.timedelta(days=STAGE_RACE_LOOKBACK_DAYS)).isoformat()
    for fc, year in conn.execute(
        "SELECT fc_race_id, year FROM src.races WHERE date IS NOT NULL AND date <= ? AND "
        "((is_stage_race = 1 AND date >= ?) OR (is_stage_race = 0 AND date >= ?))",
        (hi, lo_stage, lo_one_day),
    ):
        keys.add((str(fc), int(year)))
    lo_cache = (today - dt.timedelta(days=STARTLIST_CACHE_LOOKBACK_DAYS)).isoformat()
    for fc, year in conn.execute(
        "SELECT DISTINCT fc_race_id, year FROM src.cached_start_lists WHERE created_at >= ?",
        (lo_cache,),
    ):
        keys.add((str(fc), int(year)))
    return keys


def export_slice(
    out: Path,
    horizon_days: int = 14,
    full_db: Optional[Path] = None,
    today: Optional[dt.date] = None,
    perf_eval: Path = PERF_EVAL,
    active_days: int = 400,
    race_keys: Iterable[Tuple[str, int]] = (),
    budget_mb: int = 500,
    quiet: bool = False,
) -> dict:
    """Write the slice to ``out`` and return statistics."""
    today = today or dt.date.today()
    full_db = Path(full_db or default_db_path()).resolve()
    out = Path(out).resolve()
    if not full_db.is_file():
        raise FileNotFoundError(full_db)
    if out == full_db:
        raise ValueError("refusing to overwrite the source database")
    for suffix in ("", "-journal", "-wal", "-shm"):
        p = Path(str(out) + suffix)
        if p.exists():
            p.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    say = (lambda *a, **k: None) if quiet else (lambda *a, **k: print(*a, **k, flush=True))
    configs = scenario_configs(perf_eval)
    refs = referenced_competitions(configs)

    conn = sqlite3.connect(f"file:{out}", uri=True)
    conn.execute("PRAGMA journal_mode = OFF")
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -262144")
    conn.execute("ATTACH DATABASE ? AS src", (f"file:{full_db}?mode=ro",))

    # 1. schema: tables now, indexes + views after the fill
    objects = conn.execute(
        "SELECT type, name, tbl_name, sql FROM src.sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rowid").fetchall()
    for typ, name, _tbl, sql in objects:
        if typ == "table":
            conn.execute(sql)
    tables = _table_list(conn, "src")

    # 2. selection sets
    keys = horizon_race_keys(conn, today, horizon_days, configs, race_keys)
    conn.execute("CREATE TEMP TABLE slice_keys (fc_race_id TEXT, year INTEGER, PRIMARY KEY (fc_race_id, year))")
    conn.executemany("INSERT OR IGNORE INTO slice_keys VALUES (?, ?)", sorted(keys))

    conn.execute("CREATE TEMP TABLE slice_races (race_id INTEGER PRIMARY KEY)")
    # current editions + prior editions of every horizon race
    conn.execute(
        """
        INSERT OR IGNORE INTO slice_races
        SELECT r.id FROM src.races r JOIN slice_keys k
          ON k.fc_race_id = r.fc_race_id AND k.year = r.year
        """)
    conn.execute(
        f"""
        INSERT OR IGNORE INTO slice_races
        SELECT r.id FROM src.races r JOIN slice_keys k ON k.fc_race_id = r.fc_race_id
        WHERE r.year < k.year AND r.year >= k.year - {PRIOR_EDITIONS}
        """)

    conn.execute("CREATE TEMP TABLE slice_comps (competition_id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT OR IGNORE INTO slice_comps VALUES (?)", [(c,) for c in sorted(refs)])
    conn.execute(
        "INSERT OR IGNORE INTO slice_comps SELECT c.id FROM src.competitions c "
        "JOIN slice_races s ON s.race_id = c.race_id")
    conn.execute("CREATE TEMP TABLE current_comps (competition_id INTEGER PRIMARY KEY)")
    conn.execute(
        """
        INSERT OR IGNORE INTO current_comps
        SELECT c.id FROM src.competitions c JOIN src.races r ON r.id = c.race_id
        JOIN slice_keys k ON k.fc_race_id = r.fc_race_id AND k.year = r.year
        """)

    conn.execute("CREATE TEMP TABLE slice_riders (rider_id INTEGER PRIMARY KEY, source TEXT)")
    conn.execute(
        """
        INSERT OR IGNORE INTO slice_riders
        SELECT DISTINCT rd.id, 'startlist' FROM src.cached_start_lists csl
        JOIN slice_keys k ON k.fc_race_id = csl.fc_race_id AND k.year = csl.year
        JOIN src.riders rd ON rd.fc_rider_id = csl.rider_fc_id
        """)
    n_startlist = conn.execute("SELECT COUNT(*) FROM slice_riders").fetchone()[0]
    if active_days > 0:
        since = (today - dt.timedelta(days=active_days)).isoformat()
        conn.execute(
            """
            INSERT OR IGNORE INTO slice_riders
            SELECT DISTINCT rr.rider_id, 'active' FROM src.rider_results rr
            JOIN src.competitions c ON c.id = rr.competition_id
            WHERE c.date >= ?
            """, (since,))
    n_riders = conn.execute("SELECT COUNT(*) FROM slice_riders").fetchone()[0]
    n_comps = conn.execute("SELECT COUNT(*) FROM slice_comps").fetchone()[0]
    say(f"horizon {today} +{horizon_days}d: {len(keys)} race keys, "
        f"{n_comps} competitions ({len(refs)} refs), "
        f"{n_riders} riders ({n_startlist} on cached startlists, active_days={active_days})")

    # 3. fill
    plan: Dict[str, Optional[str]] = {}
    for t in tables:
        if t in FULL_TABLES or t.startswith(FULL_TABLE_PREFIXES):
            plan[t] = f"INSERT INTO main.{_q(t)} SELECT * FROM src.{_q(t)}"
    plan["rider_results"] = (
        "INSERT INTO main.rider_results SELECT rr.* FROM src.rider_results rr "
        "WHERE rr.rider_id IN (SELECT rider_id FROM slice_riders) "
        "OR rr.competition_id IN (SELECT competition_id FROM slice_comps)")
    plan["rider_competition_snapshots"] = (
        "INSERT INTO main.rider_competition_snapshots "
        "SELECT s.* FROM src.rider_competition_snapshots s "
        "JOIN (SELECT rider_id, MAX(competition_id) AS cid FROM src.rider_competition_snapshots "
        "      WHERE rider_id IN (SELECT rider_id FROM slice_riders) GROUP BY rider_id) latest "
        "  ON latest.rider_id = s.rider_id AND latest.cid = s.competition_id "
        "UNION "
        "SELECT s.* FROM src.rider_competition_snapshots s "
        "WHERE s.competition_id IN (SELECT competition_id FROM slice_comps) "
        "  AND NOT EXISTS (SELECT 1 FROM main.rider_competition_snapshots m "
        "                  WHERE m.rider_id = s.rider_id AND m.competition_id = s.competition_id)")
    plan["rider_race_state"] = (
        "INSERT INTO main.rider_race_state SELECT * FROM src.rider_race_state "
        "WHERE competition_id IN (SELECT competition_id FROM current_comps)")
    plan["cached_start_lists"] = (
        "INSERT INTO main.cached_start_lists SELECT c.* FROM src.cached_start_lists c "
        "JOIN slice_keys k ON k.fc_race_id = c.fc_race_id AND k.year = c.year")
    plan["cached_race_results"] = (
        "INSERT INTO main.cached_race_results SELECT c.* FROM src.cached_race_results c "
        "JOIN slice_keys k ON k.fc_race_id = c.fc_race_id AND k.year = c.year")

    rows: Dict[str, int] = {}
    for t in tables:
        sql = plan.get(t)
        if sql is None:
            rows[t] = 0
            continue
        if t not in tables:
            continue
        t1 = time.monotonic()
        conn.execute(sql)
        rows[t] = conn.execute(f"SELECT COUNT(*) FROM main.{_q(t)}").fetchone()[0]
        say(f"  {t:<34} {rows[t]:>9,} rows  {time.monotonic() - t1:5.1f}s")
    # AUTOINCREMENT counters follow the copied ids (so a nightly prediction_log
    # insert never collides with an id the Mac already issued)
    for name, seq in conn.execute("SELECT name, seq FROM src.sqlite_sequence").fetchall():
        conn.execute("INSERT OR REPLACE INTO main.sqlite_sequence(name, seq) VALUES (?, ?)", (name, seq))

    # 4. indexes + views
    for typ, name, _tbl, sql in objects:
        if typ in ("index", "view"):
            conn.execute(sql)
    conn.commit()
    conn.execute("DETACH DATABASE src")
    for tmp in ("slice_keys", "slice_races", "slice_comps", "current_comps", "slice_riders"):
        conn.execute(f"DROP TABLE IF EXISTS temp.{tmp}")
    conn.execute("VACUUM")
    conn.execute("PRAGMA journal_mode = DELETE")
    sizes = _object_sizes(conn)
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    conn.close()

    size = out.stat().st_size
    stats = {
        "path": str(out),
        "source": str(full_db),
        "today": today.isoformat(),
        "horizon_days": horizon_days,
        "active_days": active_days,
        "race_keys": sorted(keys),
        "n_reference_competitions": len(refs),
        "n_competitions": n_comps,
        "n_riders": n_riders,
        "n_startlist_riders": n_startlist,
        "rows": rows,
        "sizes_mb": sizes,
        "size_bytes": size,
        "integrity": integrity,
        "elapsed_s": round(time.monotonic() - t0, 1),
    }
    say(size_table(stats))
    say(f"slice {out}: {size / 1048576:.1f} MB in {stats['elapsed_s']}s, integrity={integrity}")
    if size > budget_mb * 1048576:
        say(f"WARNING: slice exceeds {budget_mb} MB budget — lower --active-days")
    if integrity != "ok":
        raise RuntimeError(f"slice integrity check failed: {integrity}")
    return stats


def _object_sizes(conn: sqlite3.Connection) -> Dict[str, float]:
    """MB per table (with its indexes) via dbstat, when the build has it."""
    try:
        rows = conn.execute(
            "SELECT m.tbl_name, SUM(d.pgsize) FROM dbstat d "
            "JOIN sqlite_master m ON m.name = d.name GROUP BY m.tbl_name").fetchall()
    except sqlite3.Error:
        return {}
    return {name: round(bytes_ / 1048576, 2) for name, bytes_ in rows if bytes_}


def size_table(stats: dict) -> str:
    rows, sizes = stats["rows"], stats.get("sizes_mb", {})
    lines = [f"{'table':<40} {'rows':>10} {'MB':>8}"]
    order = sorted(rows, key=lambda t: (-(sizes.get(t, 0)), -rows[t], t))
    for t in order:
        if rows[t] == 0 and not sizes.get(t):
            continue
        lines.append(f"{t:<40} {rows[t]:>10,} {sizes.get(t, 0):>8.1f}")
    empty = [t for t in order if rows[t] == 0 and not sizes.get(t)]
    if empty:
        lines.append(f"empty: {', '.join(empty)}")
    lines.append(f"{'TOTAL FILE':<40} {'':>10} {stats['size_bytes'] / 1048576:>8.1f}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("inference_slice.db"))
    ap.add_argument("--horizon-days", type=int, default=14)
    ap.add_argument("--active-days", type=int, default=400,
                    help="also keep results for riders active in the last N days (0 = startlists only)")
    ap.add_argument("--full-db", type=Path, default=None, help="source DB (default: CYCLING_DB_PATH / repo)")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=None)
    ap.add_argument("--race", action="append", default=[], metavar="FC_ID:YEAR",
                    help="extra horizon race key (repeatable)")
    ap.add_argument("--budget-mb", type=int, default=500)
    ap.add_argument("--stats-json", type=Path, default=None, help="write the statistics here")
    args = ap.parse_args(argv)
    extra = []
    for item in args.race:
        fc, year = item.split(":")
        extra.append((fc, int(year)))
    stats = export_slice(args.out, horizon_days=args.horizon_days, full_db=args.full_db,
                         today=args.today, active_days=args.active_days, race_keys=extra,
                         budget_mb=args.budget_mb)
    if args.stats_json:
        args.stats_json.write_text(json.dumps(stats, indent=2))
    return 0 if stats["size_bytes"] <= args.budget_mb * 1048576 else 2


if __name__ == "__main__":
    raise SystemExit(main())
