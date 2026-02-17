"""
Migration Script: Add Form and Team Features to rider_competition_snapshots

This script:
1. Adds 15 new columns to rider_competition_snapshots table
2. Backfills existing rows with computed form and team features
3. Supports checkpointing for resume capability

Run with: uv run python engineering_tools/migrate_form_team_features.py
"""

import sqlite3
import os
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path

try:
    from cycling_project.engineering_tools.form_team_features import (
        RiderFormHistory, TeamFeatureComputer,
        FORM_FEATURE_COLUMNS, TEAM_FEATURE_COLUMNS
    )
    from cycling_project.engineering_tools.place_handling import place_bucketer
except ModuleNotFoundError:
    from form_team_features import (
        RiderFormHistory, TeamFeatureComputer,
        FORM_FEATURE_COLUMNS, TEAM_FEATURE_COLUMNS
    )
    from place_handling import place_bucketer

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def find_database() -> str:
    """Find the SQLite database file."""
    if HAS_DOTENV:
        load_dotenv()
        db_path = os.getenv('DB_PATH')
        # Only use if it's a file that exists (not a directory)
        if db_path and os.path.isfile(db_path):
            return db_path

    possible_paths = [
        Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db",
        Path(__file__).parent.parent / "cycling_races.db",
    ]
    for path in possible_paths:
        if path.exists() and path.is_file():
            return str(path)
    raise FileNotFoundError("Database not found. Searched: " + ", ".join(str(p) for p in possible_paths))


def add_columns(conn: sqlite3.Connection) -> bool:
    """
    Add new columns to rider_competition_snapshots.

    Returns True if any columns were added.
    """
    cursor = conn.cursor()
    columns_added = False

    # Form feature columns
    form_columns = [
        ('form_recent_avg_bucket', 'REAL'),
        ('form_recent_best_bucket', 'REAL'),
        ('form_recent_count', 'INTEGER'),
        ('form_delta', 'REAL'),
        ('form_profile_recent_avg', 'REAL'),
        ('days_since_last_race', 'INTEGER'),
    ]

    # Team feature columns
    team_columns = [
        ('team_quality_mean', 'REAL'),
        ('team_quality_median', 'REAL'),
        ('team_quality_std', 'REAL'),
        ('team_quality_min', 'REAL'),
        ('team_quality_max', 'REAL'),
        ('team_quality_p25', 'REAL'),
        ('team_quality_p75', 'REAL'),
        ('team_size', 'INTEGER'),
        ('team_depth', 'INTEGER'),
    ]

    for col_name, col_type in form_columns + team_columns:
        try:
            cursor.execute(f"""
                ALTER TABLE rider_competition_snapshots
                ADD COLUMN {col_name} {col_type}
            """)
            print(f"  Added column: {col_name}")
            columns_added = True
        except sqlite3.OperationalError as e:
            if 'duplicate column' in str(e).lower():
                print(f"  Column already exists: {col_name}")
            else:
                raise

    conn.commit()
    return columns_added


def create_checkpoint_table(conn: sqlite3.Connection):
    """Create checkpoint table for backfill resume."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS form_team_backfill_checkpoint (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_processed_date TEXT,
            last_processed_competition_id INTEGER,
            processed_count INTEGER,
            updated_at TEXT
        )
    """)
    conn.commit()


def load_checkpoint(conn: sqlite3.Connection) -> Tuple[Optional[str], int]:
    """Load last checkpoint."""
    try:
        cursor = conn.execute(
            "SELECT last_processed_date, processed_count FROM form_team_backfill_checkpoint WHERE id = 1"
        )
        row = cursor.fetchone()
        if row:
            return row[0], row[1]
    except sqlite3.OperationalError:
        pass
    return None, 0


def save_checkpoint(conn: sqlite3.Connection, last_date: str, count: int):
    """Save checkpoint."""
    conn.execute("""
        INSERT OR REPLACE INTO form_team_backfill_checkpoint
        (id, last_processed_date, processed_count, updated_at)
        VALUES (1, ?, ?, ?)
    """, (last_date, count, datetime.now().isoformat()))
    conn.commit()


def get_race_start_dates(conn: sqlite3.Connection) -> Dict[Tuple[int, int], str]:
    """
    Get race start date for each (race_id, year) combination.
    Used for GC date handling.
    """
    cursor = conn.execute("""
        SELECT c.race_id, r.year, MIN(c.date) as start_date
        FROM competitions c
        JOIN races r ON c.race_id = r.id
        WHERE c.competition_type IN ('stage', 'one_day')
        GROUP BY c.race_id, r.year
    """)
    return {(row[0], row[1]): row[2] for row in cursor}


def run_backfill(
    conn: sqlite3.Connection,
    batch_size: int = 100,
    resume: bool = True
):
    """
    Backfill form and team features for existing snapshots.

    Processes chronologically to build correct rider history.
    """
    print("\n" + "=" * 70)
    print("BACKFILLING FORM AND TEAM FEATURES")
    print("=" * 70)

    create_checkpoint_table(conn)

    # Load checkpoint
    start_date = '2018-01-01'
    processed_count = 0
    if resume:
        checkpoint_date, checkpoint_count = load_checkpoint(conn)
        if checkpoint_date:
            start_date = checkpoint_date
            processed_count = checkpoint_count
            print(f"Resuming from checkpoint: {checkpoint_date} ({processed_count} competitions)")

    # Get race start dates for GC handling
    race_start_dates = get_race_start_dates(conn)
    print(f"Loaded {len(race_start_dates)} race start dates for GC handling")

    # Get all competitions to process
    cursor = conn.execute("""
        SELECT DISTINCT
            cff.competition_id,
            cff.competition_date,
            cff.competition_type,
            cff.race_category,
            cff.race_dominant_profile,
            c.race_id,
            r.year
        FROM competition_field_features cff
        JOIN competitions c ON cff.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE cff.competition_date >= ?
        ORDER BY cff.competition_date, cff.competition_id
    """, (start_date,))
    competitions = cursor.fetchall()
    total_competitions = len(competitions)
    print(f"Found {total_competitions} competitions to process")

    # Initialize rider form histories
    rider_histories: Dict[int, RiderFormHistory] = {}

    # If resuming, we need to rebuild rider histories from prior data
    if processed_count > 0:
        print("Rebuilding rider histories from prior data...")
        rebuild_rider_histories(conn, rider_histories, start_date)
        print(f"  Rebuilt histories for {len(rider_histories)} riders")

    # Process competitions in batches
    batch_start_idx = 0
    while batch_start_idx < total_competitions:
        batch = competitions[batch_start_idx:batch_start_idx + batch_size]
        updates = []

        for comp_data in batch:
            (comp_id, comp_date, comp_type, race_cat,
             race_profile, race_id, race_year) = comp_data

            # Get race start date for GC handling
            race_start = race_start_dates.get((race_id, race_year), comp_date)

            # Load riders for this competition
            riders_cursor = conn.execute("""
                SELECT
                    rcs.rider_id,
                    rcs.stage_avg_bucket, rcs.stage_count,
                    rcs.one_day_avg_bucket, rcs.one_day_count,
                    rcs.gc_avg_bucket, rcs.gc_count,
                    rr.team_id,
                    rr.place_bucket
                FROM rider_competition_snapshots rcs
                JOIN rider_results rr ON rcs.rider_id = rr.rider_id
                    AND rcs.competition_id = rr.competition_id
                WHERE rcs.competition_id = ?
            """, (comp_id,))
            riders_data = riders_cursor.fetchall()

            if not riders_data:
                continue

            # Build snapshot dict and team mapping
            rider_snapshots = {}
            rider_team_ids = {}

            for row in riders_data:
                rider_id = row[0]
                snapshot = {
                    'stage_avg_bucket': row[1],
                    'stage_count': row[2],
                    'one_day_avg_bucket': row[3],
                    'one_day_count': row[4],
                    'gc_avg_bucket': row[5],
                    'gc_count': row[6],
                }
                team_id = row[7]
                place_bucket = row[8]

                rider_snapshots[rider_id] = snapshot
                rider_team_ids[rider_id] = team_id

                # Get or create form history
                if rider_id not in rider_histories:
                    rider_histories[rider_id] = RiderFormHistory(rider_id=rider_id)
                history = rider_histories[rider_id]

                # Compute career average for form delta
                career_avg = compute_career_avg(snapshot)

                # Compute form features
                form_features = history.get_form_features(
                    target_date=comp_date,
                    target_year=race_year,
                    target_race_id=race_id,
                    target_comp_type=comp_type,
                    target_profile=race_profile or 'unknown',
                    race_start_date=race_start if comp_type == 'gc' else None,
                    career_avg_bucket=career_avg
                )

                # Store for update
                rider_snapshots[rider_id]['form_features'] = form_features
                rider_snapshots[rider_id]['place_bucket'] = place_bucket

            # Compute team features for all riders
            team_features = TeamFeatureComputer.compute_for_competition(
                rider_snapshots={k: v for k, v in rider_snapshots.items()},
                rider_team_ids=rider_team_ids
            )

            # Prepare updates
            for rider_id, snapshot in rider_snapshots.items():
                form = snapshot.get('form_features', {})
                team = team_features.get(rider_id, {})

                updates.append((
                    form.get('form_recent_avg_bucket'),
                    form.get('form_recent_best_bucket'),
                    form.get('form_recent_count'),
                    form.get('form_delta'),
                    form.get('form_profile_recent_avg'),
                    form.get('days_since_last_race'),
                    team.get('team_quality_mean'),
                    team.get('team_quality_median'),
                    team.get('team_quality_std'),
                    team.get('team_quality_min'),
                    team.get('team_quality_max'),
                    team.get('team_quality_p25'),
                    team.get('team_quality_p75'),
                    team.get('team_size'),
                    team.get('team_depth'),
                    rider_id,
                    comp_id
                ))

                # Update form history AFTER computing features (for next race)
                place_bucket = snapshot.get('place_bucket')
                if place_bucket is not None and place_bucket != 7:
                    rider_histories[rider_id].add_race(
                        date=comp_date,
                        bucket=place_bucket,
                        race_id=race_id,
                        race_year=race_year,
                        comp_type=comp_type,
                        profile=race_profile or 'unknown'
                    )

        # Apply batch updates
        if updates:
            conn.executemany("""
                UPDATE rider_competition_snapshots SET
                    form_recent_avg_bucket = ?,
                    form_recent_best_bucket = ?,
                    form_recent_count = ?,
                    form_delta = ?,
                    form_profile_recent_avg = ?,
                    days_since_last_race = ?,
                    team_quality_mean = ?,
                    team_quality_median = ?,
                    team_quality_std = ?,
                    team_quality_min = ?,
                    team_quality_max = ?,
                    team_quality_p25 = ?,
                    team_quality_p75 = ?,
                    team_size = ?,
                    team_depth = ?
                WHERE rider_id = ? AND competition_id = ?
            """, updates)
            conn.commit()

        # Update checkpoint
        batch_start_idx += batch_size
        processed_count += len(batch)
        if batch:
            last_date = batch[-1][1]  # competition_date
            save_checkpoint(conn, last_date, processed_count)

        pct = 100 * processed_count / total_competitions if total_competitions > 0 else 0
        print(f"  Processed {processed_count}/{total_competitions} competitions ({pct:.1f}%)")

    print("\n" + "=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"Processed {processed_count} competitions")
    print(f"Tracked {len(rider_histories)} riders")


def rebuild_rider_histories(
    conn: sqlite3.Connection,
    rider_histories: Dict[int, RiderFormHistory],
    up_to_date: str
):
    """
    Rebuild rider form histories from historical data up to a given date.
    Used when resuming from checkpoint.
    """
    cursor = conn.execute("""
        SELECT
            rr.rider_id,
            cff.competition_date,
            rr.place_bucket,
            c.race_id,
            r.year,
            cff.competition_type,
            cff.race_dominant_profile
        FROM rider_results rr
        JOIN competition_field_features cff ON rr.competition_id = cff.competition_id
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE cff.competition_date < ?
        AND rr.place_bucket IS NOT NULL
        AND rr.place_bucket != 7
        ORDER BY cff.competition_date
    """, (up_to_date,))

    for row in cursor:
        rider_id, comp_date, place_bucket, race_id, race_year, comp_type, profile = row

        if rider_id not in rider_histories:
            rider_histories[rider_id] = RiderFormHistory(rider_id=rider_id)

        rider_histories[rider_id].add_race(
            date=comp_date,
            bucket=place_bucket,
            race_id=race_id,
            race_year=race_year,
            comp_type=comp_type,
            profile=profile or 'unknown'
        )


def compute_career_avg(snapshot: Dict) -> float:
    """Compute weighted career average bucket from snapshot."""
    stage_sum = (snapshot.get('stage_avg_bucket') or 4.0) * (snapshot.get('stage_count') or 0)
    one_day_sum = (snapshot.get('one_day_avg_bucket') or 4.0) * (snapshot.get('one_day_count') or 0)
    gc_sum = (snapshot.get('gc_avg_bucket') or 4.0) * (snapshot.get('gc_count') or 0)

    total_count = (
        (snapshot.get('stage_count') or 0) +
        (snapshot.get('one_day_count') or 0) +
        (snapshot.get('gc_count') or 0)
    )

    if total_count == 0:
        return 4.0

    return (stage_sum + one_day_sum + gc_sum) / total_count


def main():
    """Main entry point for migration."""
    print("=" * 70)
    print("FORM AND TEAM FEATURES MIGRATION")
    print("=" * 70)

    db_path = find_database()
    print(f"Database: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # Step 1: Add columns
        print("\nStep 1: Adding columns...")
        add_columns(conn)

        # Step 2: Backfill
        print("\nStep 2: Backfilling data...")
        run_backfill(conn, batch_size=100, resume=True)

        # Verify
        print("\nVerifying...")
        cursor = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(form_recent_count) as with_form,
                COUNT(team_size) as with_team
            FROM rider_competition_snapshots
        """)
        row = cursor.fetchone()
        print(f"  Total snapshots: {row[0]}")
        print(f"  With form features: {row[1]}")
        print(f"  With team features: {row[2]}")

    finally:
        conn.close()

    print("\nMigration complete!")


if __name__ == "__main__":
    main()
