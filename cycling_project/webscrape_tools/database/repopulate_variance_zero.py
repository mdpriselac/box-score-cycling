"""
One-off repair: repopulate race_feature_gradients.variance_zero_percentile.

The original loop in populate_all_gradients_safe.py iterated trim percentiles
high-to-low and kept overwriting without break, so it stored the LOWEST valid
percentile where variance_normalized == 0 instead of the HIGHEST. Because
variance == 0 at trim p implies == 0 at every lower trim, the stored value
degenerated to lowest_valid_percentile in 100% of non-null rows and carried
no information about how deep the same-time front blob extends.

This script recomputes the intended value (highest trim percentile p such
that race_features_p.variance_normalized == 0) directly from the
race_features_N source tables and updates only that one column, in a single
transaction, after backing up the old values to
race_feature_gradients_vzp_backup_20260611.

Usage:
    uv run python -m cycling_project.webscrape_tools.database.repopulate_variance_zero [--dry-run]
"""

import argparse
import sqlite3

from cycling_project.webscrape_tools.database.populate_all_gradients_safe import find_database
from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger(__name__)

PERCENTILES = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
BACKUP_TABLE = "race_feature_gradients_vzp_backup_20260611"


def compute_new_values(conn: sqlite3.Connection) -> dict:
    """Map competition_id -> highest trim percentile with variance_normalized == 0."""
    best = {}
    for p in PERCENTILES:  # ascending, so later (higher) percentiles overwrite
        rows = conn.execute(
            f"SELECT competition_id FROM race_features_{p} WHERE variance_normalized = 0"
        ).fetchall()
        for (comp_id,) in rows:
            best[comp_id] = p
    return best


def backup_old_values(conn: sqlite3.Connection) -> None:
    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (BACKUP_TABLE,)
    ).fetchone()
    if existing:
        count = conn.execute(f"SELECT COUNT(*) FROM {BACKUP_TABLE}").fetchone()[0]
        logger.info(f"Backup table {BACKUP_TABLE} already exists ({count} rows); keeping it")
        return
    conn.execute(
        f"""CREATE TABLE {BACKUP_TABLE} AS
            SELECT competition_id, variance_zero_percentile FROM race_feature_gradients"""
    )
    conn.commit()
    logger.info(f"Backed up old values to {BACKUP_TABLE}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()

    db_path = find_database()
    logger.info(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        new_values = compute_new_values(conn)
        logger.info(
            f"{len(new_values)} competitions have variance_normalized == 0 at some trim"
        )

        current = conn.execute(
            "SELECT competition_id, variance_zero_percentile FROM race_feature_gradients"
        ).fetchall()

        updates = []
        null_to_value = value_to_null = changed = unchanged = 0
        for comp_id, old in current:
            new = new_values.get(comp_id)
            if new == old:
                unchanged += 1
                continue
            if old is None:
                null_to_value += 1
            elif new is None:
                value_to_null += 1
            else:
                changed += 1
            updates.append((new, comp_id))

        logger.info(
            f"Rows: {len(current)} total, {unchanged} unchanged, {changed} value changed, "
            f"{null_to_value} null->value, {value_to_null} value->null"
        )
        # The fix only deepens existing values; nullness flips would mean the
        # race_features_N tables drifted since gradient population.
        if null_to_value or value_to_null:
            logger.warning(
                "Nullness changes detected — race_features_N tables differ from "
                "what race_feature_gradients was populated from"
            )

        if args.dry_run:
            logger.info("Dry run — no changes written")
            return

        backup_old_values(conn)

        conn.execute("BEGIN")
        conn.executemany(
            "UPDATE race_feature_gradients SET variance_zero_percentile = ? WHERE competition_id = ?",
            updates,
        )
        conn.commit()
        logger.info(f"Updated {len(updates)} rows")

        dist = conn.execute(
            """SELECT variance_zero_percentile, COUNT(*) FROM race_feature_gradients
               WHERE variance_zero_percentile IS NOT NULL GROUP BY 1 ORDER BY 1"""
        ).fetchall()
        logger.info("New distribution: " + ", ".join(f"{p}: {n}" for p, n in dist))

        match, total = conn.execute(
            """SELECT SUM(variance_zero_percentile = kurtosis_null_percentile), COUNT(*)
               FROM race_feature_gradients
               WHERE variance_zero_percentile IS NOT NULL
                 AND kurtosis_null_percentile IS NOT NULL"""
        ).fetchone()
        logger.info(
            f"Agreement with kurtosis_null_percentile: {match}/{total} exact "
            f"({match / total:.1%})"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
