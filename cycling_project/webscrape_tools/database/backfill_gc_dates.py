#!/usr/bin/env python3
"""Backfill NULL dates on stage races and their GC competitions.

Stage-race pickles never carry a race-level date (the scraper only sets one
for one-day races). Through 2024 a manual cleaning pass
(data_cleaning_tools/clean_scraped_data.py) patched the pickles before
migration, but that step was never wired into update_pipeline, so every
stage race migrated from 2025 onward landed with races.date NULL and a
NULL-dated GC competition — invisible to the chronological feature
precomputer, and with NULL rider_age on all its results. migrate_races.py
now derives the date at insert time; this script repairs rows migrated
before that fix.

The backfill date is the latest dated stage of the race (the GC competition
additionally falls back to races.date), matching the historical convention
of dating a stage race by its final day. rider_age on the repaired GC
results is recomputed from the new date.

Note: backfilled dates fall behind feature_computation_checkpoint, so the
repaired competitions only enter training data after a full snapshot
rebuild (FeaturePrecomputer.run(resume=False)).

Usage:
    uv run python -m cycling_project.webscrape_tools.database.backfill_gc_dates [--dry-run]
"""

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "database" / "cycling_races.db"
BACKUP_DIR = Path(__file__).resolve().parent / "backups"


def backup_database(db_path: Path) -> Path:
    """Copy the DB file to the backups directory before mutating it."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"{db_path.stem}_pre_gc_date_backfill_{stamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    logger.info(f"Backed up database to {backup_path}")
    return backup_path


def backfill_race_dates(conn: sqlite3.Connection, dry_run: bool) -> int:
    """Set races.date for NULL-dated stage races from their latest dated stage."""
    rows = conn.execute("""
        SELECT r.id, r.name, r.year, MAX(c.date) AS final_stage_date
        FROM races r
        JOIN competitions c ON c.race_id = r.id
            AND c.competition_type = 'stage' AND c.date IS NOT NULL
        WHERE r.is_stage_race = 1 AND r.date IS NULL
        GROUP BY r.id
    """).fetchall()

    for race_id, name, year, final_stage_date in rows:
        logger.info(f"races.date: {name} ({year}) [id={race_id}] -> {final_stage_date}")
        if not dry_run:
            conn.execute(
                "UPDATE races SET date = ? WHERE id = ? AND date IS NULL",
                (final_stage_date, race_id),
            )
    return len(rows)


def backfill_gc_competition_dates(conn: sqlite3.Connection, dry_run: bool) -> list:
    """Set NULL GC competition dates from the race's final stage date.

    Falls back to races.date (already repaired by backfill_race_dates when
    derivable). Returns (competition_id, new_date) pairs for the rider_age
    repair pass.
    """
    rows = conn.execute("""
        SELECT c.id, r.name, r.year,
               COALESCE(
                   (SELECT MAX(s.date) FROM competitions s
                    WHERE s.race_id = c.race_id
                      AND s.competition_type = 'stage' AND s.date IS NOT NULL),
                   r.date
               ) AS new_date
        FROM competitions c
        JOIN races r ON r.id = c.race_id
        WHERE c.competition_type = 'gc' AND c.date IS NULL
    """).fetchall()

    updated = []
    for comp_id, name, year, new_date in rows:
        if new_date is None:
            logger.warning(f"GC comp {comp_id} ({name} {year}): no stage dates or "
                           f"race date available, leaving NULL")
            continue
        logger.info(f"GC date: {name} ({year}) [comp={comp_id}] -> {new_date}")
        if not dry_run:
            conn.execute(
                "UPDATE competitions SET date = ? WHERE id = ? AND date IS NULL",
                (new_date, comp_id),
            )
        updated.append((comp_id, new_date))
    return updated


def backfill_rider_ages(conn: sqlite3.Connection, updated: list, dry_run: bool) -> int:
    """Recompute rider_age (comp year - birth year) on the repaired GC results."""
    total = 0
    for comp_id, new_date in updated:
        comp_year = int(new_date[:4])
        if dry_run:
            (count,) = conn.execute("""
                SELECT COUNT(*) FROM rider_results rr
                JOIN riders ri ON ri.id = rr.rider_id
                WHERE rr.competition_id = ? AND rr.rider_age IS NULL
                  AND ri.birth_year IS NOT NULL
            """, (comp_id,)).fetchone()
        else:
            cursor = conn.execute("""
                UPDATE rider_results
                SET rider_age = ? - (SELECT birth_year FROM riders
                                     WHERE riders.id = rider_results.rider_id)
                WHERE competition_id = ? AND rider_age IS NULL
                  AND (SELECT birth_year FROM riders
                       WHERE riders.id = rider_results.rider_id) IS NOT NULL
            """, (comp_year, comp_id))
            count = cursor.rowcount
        total += count
    return total


def run_backfill(db_path: Path, dry_run: bool) -> None:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    if dry_run:
        logger.info("DRY RUN — no backup taken, no changes will be written")
    else:
        backup_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        races_fixed = backfill_race_dates(conn, dry_run)
        gc_updated = backfill_gc_competition_dates(conn, dry_run)
        ages_fixed = backfill_rider_ages(conn, gc_updated, dry_run)
        if not dry_run:
            conn.commit()

        (remaining,) = conn.execute(
            "SELECT COUNT(*) FROM competitions WHERE competition_type = 'gc' AND date IS NULL"
        ).fetchone()
        if dry_run:
            remaining -= len(gc_updated)

        verb = "would be" if dry_run else "were"
        logger.info("=" * 50)
        logger.info(f"Stage races whose races.date {verb} backfilled: {races_fixed}")
        logger.info(f"GC competitions whose date {verb} backfilled: {len(gc_updated)}")
        logger.info(f"GC results whose rider_age {verb} backfilled: {ages_fixed}")
        logger.info(f"GC competitions still NULL-dated: {remaining}")
        logger.info("=" * 50)
        if not dry_run and len(gc_updated):
            logger.info("Reminder: backfilled dates are behind "
                        "feature_computation_checkpoint — a full snapshot rebuild "
                        "(FeaturePrecomputer.run(resume=False)) is required before "
                        "these rows appear in training data.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill NULL dates on stage races and their GC competitions")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH,
                        help="Path to the SQLite database")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log what would change without writing")
    args = parser.parse_args()
    run_backfill(args.db_path, args.dry_run)


if __name__ == "__main__":
    main()
