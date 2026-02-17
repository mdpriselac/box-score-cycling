#!/usr/bin/env python3
"""
Migration script to parse bib numbers into team_bib and personal_bib columns.

Parses the existing bib_number TEXT column into:
- team_bib: The team identifier (1-digit or 2-digit)
- personal_bib: The rider's personal number within the team (1-digit)

Bib parsing logic:
- 1-digit bib (e.g., "5"): team_bib=0, personal_bib=5
- 2-digit bib (e.g., "35"): team_bib=3, personal_bib=5
- 3-digit bib (e.g., "125"): team_bib=12, personal_bib=5
"""

import sqlite3
from datetime import datetime
import sys
import os
from typing import Tuple, Optional


def parse_bib_number(raw_bib: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse raw bib number string into team_bib and personal_bib.

    Args:
        raw_bib: The raw bib number string from database

    Returns:
        Tuple of (team_bib, personal_bib), both may be None if invalid
    """
    if raw_bib is None or raw_bib == '':
        return None, None

    raw_bib = str(raw_bib).strip()

    # Handle empty after strip
    if not raw_bib:
        return None, None

    try:
        if len(raw_bib) == 1:
            return 0, int(raw_bib)
        elif len(raw_bib) == 2:
            return int(raw_bib[0]), int(raw_bib[1])
        elif len(raw_bib) == 3:
            return int(raw_bib[0:-1]), int(raw_bib[-1])
        else:
            # Longer bibs - take last digit as personal, rest as team
            return int(raw_bib[:-1]), int(raw_bib[-1])
    except (ValueError, IndexError):
        return None, None


def add_bib_columns(conn: sqlite3.Connection):
    """Add team_bib and personal_bib columns to rider_results table."""
    print("Adding bib columns to rider_results table...")

    columns_to_add = [
        'team_bib INTEGER',
        'personal_bib INTEGER',
    ]

    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(rider_results)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    for column_def in columns_to_add:
        column_name = column_def.split()[0]
        if column_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE rider_results ADD COLUMN {column_def}")
                print(f"  Added column: {column_name}")
            except sqlite3.OperationalError as e:
                print(f"  Warning: Could not add {column_name}: {e}")

    conn.commit()
    print("Column addition complete.")


def populate_bib_columns(conn: sqlite3.Connection, batch_size: int = 10000):
    """Parse and populate bib columns from existing bib_number column."""
    print("Populating bib columns from existing bib_number...")

    cursor = conn.cursor()

    # Get count of records to update
    cursor.execute("SELECT COUNT(*) FROM rider_results WHERE bib_number IS NOT NULL AND bib_number != ''")
    total_count = cursor.fetchone()[0]
    print(f"  Found {total_count} records with bib numbers")

    # Get all records with bib numbers
    cursor.execute("""
        SELECT id, bib_number
        FROM rider_results
        WHERE bib_number IS NOT NULL AND bib_number != ''
    """)

    update_data = []
    processed = 0

    for row in cursor.fetchall():
        result_id, raw_bib = row
        team_bib, personal_bib = parse_bib_number(raw_bib)
        update_data.append((team_bib, personal_bib, result_id))

        if len(update_data) >= batch_size:
            # Execute batch update
            conn.executemany(
                "UPDATE rider_results SET team_bib = ?, personal_bib = ? WHERE id = ?",
                update_data
            )
            conn.commit()
            processed += len(update_data)
            print(f"  Processed {processed}/{total_count} records ({100*processed/total_count:.1f}%)")
            update_data = []

    # Final batch
    if update_data:
        conn.executemany(
            "UPDATE rider_results SET team_bib = ?, personal_bib = ? WHERE id = ?",
            update_data
        )
        conn.commit()
        processed += len(update_data)

    print(f"  Completed: {processed} records updated")


def create_indexes(conn: sqlite3.Connection):
    """Create indexes for bib columns."""
    print("Creating indexes for bib columns...")

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_rider_results_team_bib ON rider_results(team_bib)",
        "CREATE INDEX IF NOT EXISTS idx_rider_results_personal_bib ON rider_results(personal_bib)",
    ]

    cursor = conn.cursor()
    for index_sql in indexes:
        cursor.execute(index_sql)
        index_name = index_sql.split('idx_')[1].split(' ON')[0]
        print(f"  Created index: {index_name}")

    conn.commit()


def verify_migration(conn: sqlite3.Connection):
    """Verify the migration completed successfully."""
    print("\nVerifying migration...")

    cursor = conn.cursor()

    # Check distribution
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN team_bib IS NOT NULL THEN 1 ELSE 0 END) as with_team_bib,
            SUM(CASE WHEN personal_bib IS NOT NULL THEN 1 ELSE 0 END) as with_personal_bib
        FROM rider_results
    """)
    row = cursor.fetchone()
    print(f"  Total records: {row[0]}")
    print(f"  Records with team_bib: {row[1]} ({100*row[1]/row[0]:.1f}%)")
    print(f"  Records with personal_bib: {row[2]} ({100*row[2]/row[0]:.1f}%)")

    # Show sample
    print("\nSample parsed bibs:")
    cursor.execute("""
        SELECT bib_number, team_bib, personal_bib
        FROM rider_results
        WHERE team_bib IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  '{row[0]}' -> team={row[1]}, personal={row[2]}")


def migrate_bib_number_columns(db_path: str):
    """Main migration function."""
    print("=" * 80)
    print("BIB NUMBER COLUMNS MIGRATION")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Started at: {datetime.now()}")
    print()

    conn = sqlite3.connect(db_path)

    try:
        # Step 1: Add columns
        add_bib_columns(conn)

        # Step 2: Populate from existing data
        populate_bib_columns(conn)

        # Step 3: Create indexes
        create_indexes(conn)

        # Step 4: Verify
        verify_migration(conn)

        print()
        print("=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print(f"Completed at: {datetime.now()}")

    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path (relative to webscrape_tools directory)
    db_path = "database/database/cycling_races.db"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    migrate_bib_number_columns(db_path)
