#!/usr/bin/env python3
"""
One-off cleanup: remove duplicated races from the database.

Background: the initial bulk migration on 2025-07-05 ran migrate_races.py over
a database that already contained 30 races (2024/wt) from a partial run the day
before. migrate_races.py had no existence check at the time, so those 30 races
were inserted a second time, each with a full copy of its competitions and
rider_results. This double-counted both 2024 Grand Tours in training data.

This script:
1. Backs up the database file to the backups/ directory (sqlite3 backup API).
2. Finds duplicate race groups keyed on (fc_race_id, year, category).
3. For each group keeps the most complete copy (most rider_results, then most
   competitions, then lowest id) and deletes the rest.
4. Deletes dependent rows bottom-up across every table that references the
   doomed races -- several derived tables (race_feature_gradients,
   rider_correlations_blob, correlation_data_quality, race_features_*) have
   foreign keys WITHOUT ON DELETE CASCADE that would otherwise block the
   delete, and others (rider_competition_snapshots, competition_field_features,
   race_cluster_v1_scores) have no foreign keys and would be silently orphaned.
5. Creates a UNIQUE index on races(fc_race_id, year, category) so duplicates
   cannot recur.

Usage:
    uv run python -m cycling_project.webscrape_tools.database.dedupe_races --dry-run
    uv run python -m cycling_project.webscrape_tools.database.dedupe_races
"""

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "database" / "cycling_races.db"
DEFAULT_BACKUPS_DIR = Path(__file__).resolve().parent / "backups"

UNIQUE_INDEX_NAME = "idx_races_unique_fc_year_category"
UNIQUE_INDEX_SQL = (
    f"CREATE UNIQUE INDEX IF NOT EXISTS {UNIQUE_INDEX_NAME} "
    "ON races(fc_race_id, year, category)"
)

# Chunk size for parameterized IN (...) lists, well under SQLite's limit.
_CHUNK = 500


@dataclass
class RaceCopy:
    race_id: int
    name: str
    n_competitions: int
    n_results: int


@dataclass
class DuplicateGroup:
    fc_race_id: str
    year: int
    category: str
    keeper: RaceCopy
    doomed: List[RaceCopy]


def backup_database(db_path: Path, backups_dir: Path) -> Path:
    """Copy the database into backups_dir using the sqlite3 backup API."""
    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    dest = backups_dir / f"{db_path.stem}.{stamp}_pre_dedupe{db_path.suffix}"
    counter = 2
    while dest.exists():
        dest = backups_dir / f"{db_path.stem}.{stamp}_pre_dedupe_{counter}{db_path.suffix}"
        counter += 1

    logger.info(f"Backing up {db_path} -> {dest}")
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()
    logger.info(f"Backup complete ({dest.stat().st_size / 1e9:.2f} GB)")
    return dest


def find_duplicate_groups(conn: sqlite3.Connection) -> List[DuplicateGroup]:
    """Find race groups sharing (fc_race_id, year, category) and pick keepers."""
    dup_keys = conn.execute("""
        SELECT fc_race_id, year, category
        FROM races
        GROUP BY fc_race_id, year, category
        HAVING COUNT(*) > 1
    """).fetchall()

    groups = []
    for fc_race_id, year, category in dup_keys:
        rows = conn.execute("""
            SELECT r.id, r.name,
                   (SELECT COUNT(*) FROM competitions c
                    WHERE c.race_id = r.id) AS n_comps,
                   (SELECT COUNT(*) FROM rider_results rr
                    JOIN competitions c ON rr.competition_id = c.id
                    WHERE c.race_id = r.id) AS n_results
            FROM races r
            WHERE r.fc_race_id = ? AND r.year = ? AND r.category = ?
        """, (fc_race_id, year, category)).fetchall()

        copies = [RaceCopy(r[0], r[1], r[2], r[3]) for r in rows]
        # Most complete first; lowest id wins ties.
        copies.sort(key=lambda c: (-c.n_results, -c.n_competitions, c.race_id))
        groups.append(DuplicateGroup(
            fc_race_id=fc_race_id, year=year, category=category,
            keeper=copies[0], doomed=copies[1:],
        ))
    return groups


def _tables_with_column(conn: sqlite3.Connection, column: str,
                        exclude: Sequence[str] = ()) -> List[str]:
    """All user tables containing `column`, excluding the given names."""
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    matched = []
    for table in tables:
        if table in exclude:
            continue
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        if column in cols:
            matched.append(table)
    return sorted(matched)


def _chunked(ids: Sequence[int]):
    for i in range(0, len(ids), _CHUNK):
        yield ids[i:i + _CHUNK]


def _delete_or_count(conn: sqlite3.Connection, table: str, where_column: str,
                     ids: Sequence[int], dry_run: bool,
                     subquery: str = "") -> int:
    """DELETE (or COUNT in dry-run) rows where where_column matches ids.

    If `subquery` is given it is used as the IN (...) source, with the ids
    bound to placeholders inside it.
    """
    verb = "SELECT COUNT(*) FROM" if dry_run else "DELETE FROM"
    total = 0
    for chunk in _chunked(ids):
        placeholders = ",".join("?" for _ in chunk)
        source = subquery.format(placeholders=placeholders) if subquery \
            else f"({placeholders})"
        cursor = conn.execute(
            f'{verb} "{table}" WHERE {where_column} IN {source}', chunk)
        total += cursor.fetchone()[0] if dry_run else cursor.rowcount
    return total


def cleanup_duplicates(conn: sqlite3.Connection, groups: List[DuplicateGroup],
                       dry_run: bool) -> Dict[str, int]:
    """Delete doomed race copies and every dependent row, bottom-up."""
    doomed_race_ids = [c.race_id for g in groups for c in g.doomed]
    doomed_comp_ids = []
    for chunk in _chunked(doomed_race_ids):
        placeholders = ",".join("?" for _ in chunk)
        doomed_comp_ids.extend(r[0] for r in conn.execute(
            f"SELECT id FROM competitions WHERE race_id IN ({placeholders})",
            chunk))

    logger.info(f"{len(doomed_race_ids)} race rows to delete, "
                f"{len(doomed_comp_ids)} competitions underneath")

    deleted: Dict[str, int] = {}

    rr_ref_tables = _tables_with_column(conn, "rider_result_id")
    comp_tables = _tables_with_column(
        conn, "competition_id", exclude=["competitions"] + rr_ref_tables)
    race_tables = _tables_with_column(
        conn, "race_id", exclude=["races", "competitions"] + rr_ref_tables
        + comp_tables)
    touched_tables = rr_ref_tables + comp_tables + race_tables + ["competitions"]

    # Pre-existing FK violations (orphans left by older FK-off deletions) are
    # not this script's problem -- only fail on violations *we* introduce.
    baseline_violations = {
        table: set(conn.execute(f'PRAGMA foreign_key_check("{table}")').fetchall())
        for table in touched_tables
    } if not dry_run else {}
    for table, rows in baseline_violations.items():
        if rows:
            logger.warning(f"{len(rows)} pre-existing FK violation(s) in "
                           f"{table} (ignored, not caused by this cleanup)")

    # 1. Tables referencing rider_results (FKs without cascade) -- must go
    #    before rider_results rows disappear.
    rr_subquery = ("(SELECT id FROM rider_results "
                   "WHERE competition_id IN ({placeholders}))")
    for table in rr_ref_tables:
        n = _delete_or_count(conn, table, "rider_result_id", doomed_comp_ids,
                             dry_run, subquery=rr_subquery)
        deleted[table] = n

    # 2. Every other table keyed on competition_id (rider_results itself,
    #    derived feature tables with non-cascading FKs, and FK-less tables
    #    that would otherwise be orphaned).
    for table in comp_tables:
        deleted[table] = _delete_or_count(
            conn, table, "competition_id", doomed_comp_ids, dry_run)

    # 3. Tables keyed on race_id (competitions handled by cascade from races;
    #    feature tables normally already cleaned via competition_id).
    for table in race_tables:
        deleted[table] = _delete_or_count(
            conn, table, "race_id", doomed_race_ids, dry_run)

    # 4. The races rows themselves; competitions go via ON DELETE CASCADE.
    deleted["races"] = _delete_or_count(
        conn, "races", "id", doomed_race_ids, dry_run)
    deleted["competitions (cascade)"] = len(doomed_comp_ids)

    # 5. Safety net: verify the cleanup introduced no new dangling foreign
    #    keys (covers rows the column-based passes could conceivably miss).
    if not dry_run:
        for table in touched_tables:
            violations = set(conn.execute(
                f'PRAGMA foreign_key_check("{table}")').fetchall())
            new_violations = violations - baseline_violations[table]
            if new_violations:
                raise RuntimeError(
                    f"Cleanup introduced FK violations in {table}: "
                    f"{sorted(new_violations)[:5]}")

    return deleted


def run(db_path: Path, backups_dir: Path, dry_run: bool) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        fk_on = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        if fk_on != 1:
            raise RuntimeError("PRAGMA foreign_keys could not be enabled; "
                               "aborting to avoid orphaning child rows")

        groups = find_duplicate_groups(conn)
        if not groups:
            logger.info("No duplicate races found.")
        else:
            logger.info(f"Found {len(groups)} duplicate race groups:")
            for g in groups:
                doomed_ids = [c.race_id for c in g.doomed]
                logger.info(
                    f"  {g.keeper.name} ({g.fc_race_id}/{g.year}/{g.category}): "
                    f"keeping id {g.keeper.race_id} "
                    f"({g.keeper.n_competitions} comps, {g.keeper.n_results} results), "
                    f"deleting id(s) {doomed_ids}")

        if dry_run:
            if groups:
                deleted = cleanup_duplicates(conn, groups, dry_run=True)
                logger.info("[DRY RUN] Rows that would be deleted:")
                for table, n in sorted(deleted.items()):
                    if n:
                        logger.info(f"  {table}: {n}")
            index_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                (UNIQUE_INDEX_NAME,)).fetchone() is not None
            logger.info(f"[DRY RUN] Unique index present: {index_exists}; "
                        "no changes made.")
            return

        if groups:
            backup_database(db_path, backups_dir)
            deleted = cleanup_duplicates(conn, groups, dry_run=False)

            remaining = find_duplicate_groups(conn)
            if remaining:
                raise RuntimeError(
                    f"{len(remaining)} duplicate groups remain after cleanup; "
                    "rolling back")

            logger.info("Rows deleted:")
            for table, n in sorted(deleted.items()):
                if n:
                    logger.info(f"  {table}: {n}")

        conn.execute(UNIQUE_INDEX_SQL)
        logger.info(f"Unique index {UNIQUE_INDEX_NAME} ensured on "
                    "races(fc_race_id, year, category)")
        conn.commit()
        logger.info("Cleanup committed.")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Remove duplicate races (same fc_race_id, year, category) "
                    "and add a unique index to prevent recurrence")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH,
                        help="Path to the SQLite database")
    parser.add_argument("--backups-dir", type=Path, default=DEFAULT_BACKUPS_DIR,
                        help="Directory for the pre-cleanup backup")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would be deleted without changing anything")
    args = parser.parse_args()

    run(args.db_path, args.backups_dir, args.dry_run)


if __name__ == "__main__":
    main()
