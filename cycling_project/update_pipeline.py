"""
Weekly Update Pipeline

Single script to scrape new race data, migrate to SQLite, rebuild features,
and retrain the production model.

Usage:
    uv run python -m cycling_project.update_pipeline              # full pipeline
    uv run python -m cycling_project.update_pipeline --skip-scrape # skip scraping
    uv run python -m cycling_project.update_pipeline --only train  # single step
    uv run python -m cycling_project.update_pipeline --dry-run     # show plan
"""

import argparse
import os
import pickle
import sqlite3
import time
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from cycling_project.webscrape_tools.logging_config import get_logger

logger = get_logger("update_pipeline")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    """Single source of truth for all paths."""
    project_root: Path
    scraped_data_dir: Path
    db_path: Path
    model_dir: Path
    tour_levels: Tuple[str, ...] = ('wt', 'pro', 'd1')

    @classmethod
    def from_defaults(cls) -> "PipelineConfig":
        project_root = Path(__file__).resolve().parent.parent
        db_path = (
            project_root / "cycling_project" / "webscrape_tools"
            / "database" / "database" / "cycling_races.db"
        )
        model_dir = project_root / "models" / "production"

        # Scraped data directory: check .env, then default
        scraped_data_dir = Path.home() / "cycling_data" / "scraped_data"
        try:
            from dotenv import load_dotenv
            load_dotenv(project_root / ".env")
            env_path = os.getenv("SCRAPED_DATA_DIR") or os.getenv("DB_PATH")
            if env_path:
                candidate = Path(env_path)
                if candidate.is_dir():
                    scraped_data_dir = candidate
        except ImportError:
            pass

        return cls(
            project_root=project_root,
            scraped_data_dir=scraped_data_dir,
            db_path=db_path,
            model_dir=model_dir,
        )


# ---------------------------------------------------------------------------
# Step result tracking
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    name: str
    success: bool
    duration: float
    summary: str
    error: Optional[str] = None


def run_step(name: str, func: Callable, *args, **kwargs) -> StepResult:
    """Execute a pipeline step with timing and error capture."""
    logger.info("=" * 60)
    logger.info(f"STEP: {name}")
    logger.info("=" * 60)
    start = time.time()
    try:
        summary = func(*args, **kwargs) or "done"
        duration = time.time() - start
        logger.info(f"  completed in {duration:.1f}s")
        return StepResult(name, True, duration, str(summary))
    except Exception as e:
        duration = time.time() - start
        logger.error(f"  FAILED after {duration:.1f}s: {e}")
        logger.error(traceback.format_exc())
        return StepResult(name, False, duration, "", str(e))


# ---------------------------------------------------------------------------
# Step 1: Determine scrape targets
# ---------------------------------------------------------------------------

def determine_scrape_targets(config: PipelineConfig) -> List[Tuple[str, List[int]]]:
    """Figure out which (year, months) need scraping.

    Uses a 45-day lookback from today to ensure recent races from prior
    months are always re-checked, regardless of what's already in the DB.
    """
    today = date.today()

    conn = sqlite3.connect(str(config.db_path))
    cursor = conn.execute(
        "SELECT MAX(c.date) FROM competitions c JOIN races r ON c.race_id = r.id"
    )
    latest_str = cursor.fetchone()[0]
    conn.close()

    if latest_str is None:
        return [(str(today.year), None)]

    # Start from 45 days ago to catch missed races from prior months
    lookback = today - timedelta(days=45)
    start = date(lookback.year, lookback.month, 1)
    end = date(today.year, today.month, 1)

    year_months: List[Tuple[int, int]] = []
    current = start
    while current <= end:
        year_months.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)

    grouped: Dict[int, List[int]] = defaultdict(list)
    for y, m in year_months:
        grouped[y].append(m)

    targets = [(str(y), months) for y, months in sorted(grouped.items())]
    logger.info(f"Scrape targets: {targets}")
    return targets


# ---------------------------------------------------------------------------
# Step 2: Scrape race lists
# ---------------------------------------------------------------------------

def scrape_race_lists(
    config: PipelineConfig, targets: List[Tuple[str, List[int]]]
) -> str:
    """Scrape race lists from FirstCycling for each target year/months."""
    from cycling_project.webscrape_tools.find_races import create_race_year_db

    for year_str, months in targets:
        logger.info(f"Scraping race lists for {year_str} months={months}")
        create_race_year_db(
            year_str,
            race_data_dir=str(config.scraped_data_dir),
            months=months,
        )

    return f"Scraped lists for {len(targets)} year(s)"


# ---------------------------------------------------------------------------
# Step 3: Scrape race data
# ---------------------------------------------------------------------------

def scrape_race_data(
    config: PipelineConfig, targets: List[Tuple[str, List[int]]]
) -> str:
    """Scrape individual race pages (incremental - skips existing pkl)."""
    from cycling_project.webscrape_tools.download_race_data import (
        update_tour_folder,
        remove_duplicates_across_tours,
    )

    total_scraped = 0
    for year_str, _ in targets:
        year_dir = config.scraped_data_dir / year_str

        # Remove cross-tour duplicates first
        if year_dir.exists():
            remove_duplicates_across_tours(str(year_dir))

        for tour in config.tour_levels:
            tour_dir = year_dir / tour
            if not tour_dir.exists():
                logger.info(f"Skipping {tour_dir} (does not exist)")
                continue
            logger.info(f"Scraping race data: {tour_dir}")
            try:
                update_tour_folder(str(tour_dir))
                total_scraped += 1
            except Exception as e:
                logger.error(f"Error scraping {tour_dir}: {e}")

    return f"Processed {total_scraped} tour folder(s)"


# ---------------------------------------------------------------------------
# Step 4: Migrate to SQLite (with duplicate prevention)
# ---------------------------------------------------------------------------

def _get_existing_race_keys(db_path: str) -> Set[Tuple[str, int, str]]:
    """Get all (fc_race_id, year, category) tuples from the races table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT fc_race_id, year, category FROM races")
    keys = {(str(row[0]), row[1], row[2]) for row in cursor.fetchall()}
    conn.close()
    return keys


def _get_incomplete_race_keys(
    db_path: str, years: List[int]
) -> Set[Tuple[str, int, str]]:
    """Get race keys where competitions are missing or have zero rider results.

    Only checks the specified years to avoid touching historical data where
    empty competitions may be legitimate (e.g. GC classifications).
    """
    if not years:
        return set()
    conn = sqlite3.connect(db_path)
    placeholders = ",".join("?" for _ in years)
    cursor = conn.execute(f"""
        SELECT DISTINCT r.fc_race_id, r.year, r.category
        FROM races r
        JOIN competitions c ON c.race_id = r.id
        LEFT JOIN rider_results rr ON rr.competition_id = c.id
        WHERE rr.id IS NULL AND r.year IN ({placeholders})
        UNION
        SELECT r.fc_race_id, r.year, r.category
        FROM races r
        LEFT JOIN competitions c ON c.race_id = r.id
        WHERE c.id IS NULL AND r.year IN ({placeholders})
    """, years + years)
    keys = {(str(row[0]), row[1], row[2]) for row in cursor.fetchall()}
    conn.close()
    return keys


_COMPETITION_DEPENDENT_TABLES = [
    "rider_results",
    "race_feature_gradients",
    "rider_competition_snapshots",
    "competition_field_features",
    "correlation_data_quality",
    "rider_correlations_blob",
    "processing_checkpoint",
    "feature_computation_checkpoint",
    "form_team_backfill_checkpoint",
] + [f"race_features_{p}" for p in range(10, 105, 5)]


def _delete_race_by_key(db_path: str, fc_race_id: str, year: int, category: str) -> None:
    """Delete a race and all its related data from all dependent tables."""
    conn = sqlite3.connect(db_path)
    # Disable FK checks — we handle deletion order ourselves
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        cursor = conn.execute(
            "SELECT id FROM races WHERE fc_race_id = ? AND year = ? AND category = ?",
            (fc_race_id, year, category),
        )
        race_ids = [row[0] for row in cursor.fetchall()]
        for race_id in race_ids:
            comp_ids_q = "SELECT id FROM competitions WHERE race_id = ?"
            # Delete from all tables that reference competition_id
            for table in _COMPETITION_DEPENDENT_TABLES:
                try:
                    conn.execute(
                        f"DELETE FROM {table} WHERE competition_id IN ({comp_ids_q})",
                        (race_id,),
                    )
                except sqlite3.OperationalError:
                    pass  # Table may not exist or have different schema
            conn.execute("DELETE FROM competitions WHERE race_id = ?", (race_id,))
            conn.execute("DELETE FROM races WHERE id = ?", (race_id,))
        conn.commit()
        logger.info(f"Deleted incomplete race {fc_race_id}/{year}/{category} ({len(race_ids)} entries)")
    finally:
        conn.close()


def migrate_new_races(
    config: PipelineConfig, targets: List[Tuple[str, List[int]]]
) -> str:
    """Migrate only new races to SQLite, skipping duplicates."""
    from cycling_project.webscrape_tools.database.migrate_races import RaceMigrator

    db_path_str = str(config.db_path)
    existing_keys = _get_existing_race_keys(db_path_str)
    target_years = [int(y) for y, _ in targets]
    incomplete_keys = _get_incomplete_race_keys(db_path_str, target_years)
    logger.info(f"Found {len(existing_keys)} existing races in DB, {len(incomplete_keys)} incomplete in target years")

    # Delete incomplete races so they can be re-migrated with full data
    for key in incomplete_keys:
        _delete_race_by_key(db_path_str, *key)
        existing_keys.discard(key)

    migrator = RaceMigrator(str(config.scraped_data_dir), db_path_str)
    migrator.connect()

    new_races = 0
    skipped = 0
    empty = 0

    try:
        for year_str, _ in targets:
            for tour in config.tour_levels:
                tour_dir = config.scraped_data_dir / year_str / tour
                if not tour_dir.exists():
                    continue

                pkl_files = list(tour_dir.glob("*.pkl"))
                for pkl_file in pkl_files:
                    try:
                        with open(pkl_file, "rb") as f:
                            race = pickle.load(f)
                    except Exception as e:
                        logger.warning(f"Could not load {pkl_file.name}: {e}")
                        continue

                    # Skip empty pickles (no results yet)
                    if not race.results and (
                        not hasattr(race, "stages") or not race.stages
                    ):
                        empty += 1
                        continue

                    # Check for duplicates
                    key = (str(race.fc_race_id), race.year, tour)
                    if key in existing_keys:
                        skipped += 1
                        continue

                    # Migrate this race
                    migrator.migrate_race(pkl_file, tour)
                    existing_keys.add(key)
                    new_races += 1

                # Commit after each tour level
                migrator.conn.commit()

    finally:
        migrator.print_statistics()
        migrator.disconnect()

    # Clean up empty future competitions (stages with no results)
    conn = sqlite3.connect(db_path_str)
    try:
        cursor = conn.execute("""
            DELETE FROM competitions WHERE id IN (
                SELECT c.id FROM competitions c
                LEFT JOIN rider_results rr ON rr.competition_id = c.id
                WHERE c.date > date('now') AND rr.id IS NULL
            )
        """)
        future_deleted = cursor.rowcount
        if future_deleted:
            conn.commit()
            logger.info(f"Cleaned up {future_deleted} empty future competition entries")
    finally:
        conn.close()

    return f"{new_races} new, {skipped} skipped, {empty} empty, {future_deleted} future cleaned"


# ---------------------------------------------------------------------------
# Step 4b: Backfill place_bucket
# ---------------------------------------------------------------------------

def backfill_place_bucket(config: PipelineConfig) -> str:
    """Ensure all rider_results have place_bucket set (safety net)."""
    conn = sqlite3.connect(str(config.db_path))

    # Check how many NULLs exist
    cursor = conn.execute(
        "SELECT COUNT(*) FROM rider_results WHERE place_bucket IS NULL"
    )
    null_count = cursor.fetchone()[0]

    if null_count == 0:
        conn.close()
        return "No NULL place_buckets found"

    # Apply the same bucketing as place_handling.place_bucketer()
    updates = [
        ("UPDATE rider_results SET place_bucket = 0 "
         "WHERE place_bucket IS NULL AND place = 1"),
        ("UPDATE rider_results SET place_bucket = 1 "
         "WHERE place_bucket IS NULL AND place >= 2 AND place <= 3"),
        ("UPDATE rider_results SET place_bucket = 2 "
         "WHERE place_bucket IS NULL AND place >= 4 AND place <= 5"),
        ("UPDATE rider_results SET place_bucket = 3 "
         "WHERE place_bucket IS NULL AND place >= 6 AND place <= 15"),
        ("UPDATE rider_results SET place_bucket = 4 "
         "WHERE place_bucket IS NULL AND place >= 16 AND place <= 30"),
        ("UPDATE rider_results SET place_bucket = 5 "
         "WHERE place_bucket IS NULL AND place >= 31 AND place <= 50"),
        ("UPDATE rider_results SET place_bucket = 6 "
         "WHERE place_bucket IS NULL AND place > 50"),
    ]

    total_updated = 0
    for sql in updates:
        cursor = conn.execute(sql)
        total_updated += cursor.rowcount

    conn.commit()
    conn.close()
    return f"Backfilled {total_updated} rows (from {null_count} NULLs)"


# ---------------------------------------------------------------------------
# Step 5: Bib number migration
# ---------------------------------------------------------------------------

def run_bib_migration(config: PipelineConfig) -> str:
    from cycling_project.webscrape_tools.database.migrate_bib_number_columns import (
        migrate_bib_number_columns,
    )
    migrate_bib_number_columns(str(config.db_path))
    return "done"


# ---------------------------------------------------------------------------
# Step 6: Experience features migration
# ---------------------------------------------------------------------------

def run_experience_migration(config: PipelineConfig) -> str:
    from cycling_project.webscrape_tools.database.migrate_precompute_experience_features import (
        migrate_precompute_experience_features,
    )
    migrate_precompute_experience_features(str(config.db_path))
    return "done"


# ---------------------------------------------------------------------------
# Step 7: Percentile tables
# ---------------------------------------------------------------------------

def run_percentile_tables(
    config: PipelineConfig, targets: List[Tuple[str, List[int]]]
) -> str:
    from cycling_project.webscrape_tools.database.build_percentile_tables import (
        build_percentile_tables,
    )
    years = [int(y) for y, _ in targets]
    build_percentile_tables(
        db_path=str(config.db_path),
        years=years,
        rebuild=False,
    )
    return f"Built percentile tables for years {years}"


# ---------------------------------------------------------------------------
# Step 8: Gradient calculation
# ---------------------------------------------------------------------------

def run_gradient_calculation(config: PipelineConfig) -> str:
    from cycling_project.webscrape_tools.database.populate_all_gradients_safe import (
        get_all_unprocessed_competitions,
        calculate_gradients_for_competition,
        SafeDatabaseWriter,
    )

    db_path = str(config.db_path)
    competitions = get_all_unprocessed_competitions(db_path)

    if not competitions:
        return "No unprocessed competitions"

    logger.info(f"Processing {len(competitions)} competitions for gradients")

    db_writer = SafeDatabaseWriter(db_path)
    max_workers = min(8, len(competitions))
    batch_size = 25
    success_count = 0
    error_count = 0
    batch_data: List[Dict[str, Any]] = []

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_comp = {
                executor.submit(
                    calculate_gradients_for_competition, comp_id, db_path
                ): comp_id
                for comp_id in competitions
            }

            for i, future in enumerate(as_completed(future_to_comp)):
                try:
                    result = future.result()
                    if result:
                        batch_data.append(result)
                        success_count += 1
                        if len(batch_data) >= batch_size:
                            db_writer.insert_batch(batch_data)
                            batch_data = []
                    else:
                        error_count += 1
                except Exception:
                    error_count += 1

                if (i + 1) % 100 == 0:
                    logger.info(
                        f"Gradients: {i+1}/{len(competitions)} "
                        f"({success_count} ok, {error_count} errors)"
                    )

        if batch_data:
            db_writer.insert_batch(batch_data)

    finally:
        db_writer.close()

    return f"{success_count} processed, {error_count} errors"


# ---------------------------------------------------------------------------
# Step 9: Feature precomputation
# ---------------------------------------------------------------------------

def run_feature_precomputation(config: PipelineConfig) -> str:
    from cycling_project.engineering_tools.feature_precomputation import (
        FeaturePrecomputer,
    )
    precomputer = FeaturePrecomputer(db_path=str(config.db_path), batch_size=100)
    precomputer.run(resume=True)
    return "done"


# ---------------------------------------------------------------------------
# Step 9b: Stage-race state (incremental; feeds rider_race_state)
# ---------------------------------------------------------------------------

def run_stage_race_state(config: PipelineConfig) -> str:
    from cycling_project.engineering_tools.stage_race_state import (
        StageRaceStateBuilder,
    )
    builder = StageRaceStateBuilder(db_path=str(config.db_path))
    summary = builder.run()
    return (
        f"{summary['races_processed']} races, "
        f"{summary['state_rows']} state rows, "
        f"{summary['suspect_races']} suspect"
    )


# ---------------------------------------------------------------------------
# Step 9c: Contested-rating (Elo) snapshots artifact (incremental)
# ---------------------------------------------------------------------------

def run_elo_snapshot_update(config: PipelineConfig) -> str:
    from cycling_project.prediction_tools.contested_rating import (
        PRODUCTION_SNAPSHOT_PATH,
        build_or_update_snapshots,
    )
    snaps = build_or_update_snapshots(db_path=config.db_path)
    return f"{len(snaps):,} snapshot rows -> {PRODUCTION_SNAPSHOT_PATH.name}"


# ---------------------------------------------------------------------------
# Step 10: Train production model
# ---------------------------------------------------------------------------

def run_model_training(config: PipelineConfig) -> str:
    from cycling_project.prediction_tools.train_production_model import (
        main as train_main,
    )
    train_main()
    return "done"


# ---------------------------------------------------------------------------
# Step 11: Train LambdaRank probability head
# ---------------------------------------------------------------------------

def run_lambdarank_training(config: PipelineConfig) -> str:
    from cycling_project.prediction_tools.train_lambdarank_production import (
        main as lambdarank_main,
    )
    lambdarank_main()
    return "done"


# ---------------------------------------------------------------------------
# Step 12: Train GC outlook head (state-aware final-GC prediction)
# ---------------------------------------------------------------------------

def run_gc_outlook_training(config: PipelineConfig) -> str:
    from cycling_project.prediction_tools.train_gc_outlook_production import (
        main as gc_outlook_main,
    )
    gc_outlook_main()
    return "done"


# ---------------------------------------------------------------------------
# Step 13: Train DNF head (P(finish) multiplier for the pricing layer)
# ---------------------------------------------------------------------------

def run_dnf_training(config: PipelineConfig) -> str:
    from cycling_project.prediction_tools.dnf_predictor import (
        train_production_dnf_head,
    )
    meta = train_production_dnf_head(db_path=str(config.db_path))
    es = meta.get("early_stop_metrics", {})
    return (
        f"best_iter={meta.get('best_iteration')} "
        f"AUC={es.get('auc', float('nan')):.3f} cal={es.get('cal_ratio', float('nan')):.3f}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

STEP_NAMES = [
    "scrape-lists", "scrape-data", "migrate", "place-bucket",
    "bib", "experience", "percentiles", "gradients", "features",
    "race-state", "elo-snapshots", "train", "train-lambdarank",
    "train-gc-outlook", "train-dnf",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Weekly update pipeline for cycling race prediction",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python -m cycling_project.update_pipeline
  uv run python -m cycling_project.update_pipeline --skip-scrape
  uv run python -m cycling_project.update_pipeline --only train
  uv run python -m cycling_project.update_pipeline --dry-run
        """,
    )

    skip = parser.add_argument_group("Skip steps")
    skip.add_argument("--skip-scrape", action="store_true",
                      help="Skip scraping (race lists + race data)")
    skip.add_argument("--skip-migrate", action="store_true",
                      help="Skip migration (SQLite + bib + experience)")
    skip.add_argument("--skip-features", action="store_true",
                      help="Skip feature building (percentiles + gradients + precomputation)")
    skip.add_argument("--skip-train", action="store_true",
                      help="Skip model training")
    skip.add_argument("--skip-lambdarank", action="store_true",
                      help="Skip LambdaRank probability head training")

    parser.add_argument("--only", choices=STEP_NAMES,
                        help="Run ONLY the specified step")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without executing")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Debug-level logging")

    return parser


def should_run(step: str, args: argparse.Namespace) -> bool:
    """Determine whether a step should run given the CLI flags."""
    if args.only:
        return step == args.only

    scrape_steps = {"scrape-lists", "scrape-data"}
    migrate_steps = {"migrate", "place-bucket", "bib", "experience"}
    feature_steps = {"percentiles", "gradients", "features", "race-state"}
    # elo-snapshots and train-dnf ride with --skip-train: the Elo artifact
    # exists to feed training, and the DNF head is a (re)trained model.
    train_steps = {"train", "train-gc-outlook", "elo-snapshots", "train-dnf"}
    lambdarank_steps = {"train-lambdarank"}

    if args.skip_scrape and step in scrape_steps:
        return False
    if args.skip_migrate and step in migrate_steps:
        return False
    if args.skip_features and step in feature_steps:
        return False
    if args.skip_train and step in train_steps:
        return False
    if args.skip_lambdarank and step in lambdarank_steps:
        return False

    return True


def print_summary(results: List[StepResult]):
    """Print a summary table of all step results."""
    print("\n" + "=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    print(f"{'Step':<30} {'Status':<10} {'Time':>8}  {'Details'}")
    print("-" * 70)
    for r in results:
        status = "OK" if r.success else "FAILED"
        time_str = f"{r.duration:.1f}s"
        detail = r.summary if r.success else r.error or ""
        # Truncate long details
        if len(detail) > 40:
            detail = detail[:37] + "..."
        print(f"{r.name:<30} {status:<10} {time_str:>8}  {detail}")

    total_time = sum(r.duration for r in results)
    failed = sum(1 for r in results if not r.success)
    print("-" * 70)
    print(f"Total: {len(results)} steps, {failed} failed, {total_time:.1f}s elapsed")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(args: argparse.Namespace):
    config = PipelineConfig.from_defaults()
    results: List[StepResult] = []

    logger.info("Pipeline config:")
    logger.info(f"  DB:           {config.db_path}")
    logger.info(f"  Scraped data: {config.scraped_data_dir}")
    logger.info(f"  Models:       {config.model_dir}")

    # Step 1: Determine targets (always runs)
    targets = determine_scrape_targets(config)

    if args.dry_run:
        print("\n=== DRY RUN ===")
        print(f"Scrape targets: {targets}")
        print(f"\nSteps that would run:")
        for step in STEP_NAMES:
            marker = "  RUN " if should_run(step, args) else "  SKIP"
            print(f"  {marker}  {step}")
        return

    # Step 2: Scrape race lists
    if should_run("scrape-lists", args):
        results.append(
            run_step("Scrape Race Lists", scrape_race_lists, config, targets)
        )

    # Step 3: Scrape race data
    if should_run("scrape-data", args):
        results.append(
            run_step("Scrape Race Data", scrape_race_data, config, targets)
        )

    # Step 4: Migrate to SQLite
    if should_run("migrate", args):
        r = run_step("Migrate to SQLite", migrate_new_races, config, targets)
        results.append(r)
        if not r.success:
            logger.error("Migration failed - stopping pipeline")
            print_summary(results)
            return

    # Step 4b: Backfill place_bucket
    if should_run("place-bucket", args):
        results.append(
            run_step("Backfill place_bucket", backfill_place_bucket, config)
        )

    # Step 5: Bib numbers
    if should_run("bib", args):
        results.append(run_step("Bib Numbers", run_bib_migration, config))

    # Step 6: Experience features
    if should_run("experience", args):
        results.append(
            run_step("Experience Features", run_experience_migration, config)
        )

    # Step 7: Percentile tables
    if should_run("percentiles", args):
        r = run_step(
            "Percentile Tables", run_percentile_tables, config, targets
        )
        results.append(r)
        if not r.success:
            logger.error("Percentile tables failed - stopping pipeline")
            print_summary(results)
            return

    # Step 8: Gradients
    if should_run("gradients", args):
        r = run_step("Gradient Calculation", run_gradient_calculation, config)
        results.append(r)
        if not r.success:
            logger.error("Gradient calculation failed - stopping pipeline")
            print_summary(results)
            return

    # Step 9: Feature precomputation
    if should_run("features", args):
        r = run_step(
            "Feature Precomputation", run_feature_precomputation, config
        )
        results.append(r)
        if not r.success:
            logger.error("Feature precomputation failed - stopping pipeline")
            print_summary(results)
            return

    # Step 9b: Stage-race state (non-fatal: training tolerates a stale
    # rider_race_state via the LEFT JOIN; rows simply come through NULL)
    if should_run("race-state", args):
        results.append(
            run_step("Stage-Race State", run_stage_race_state, config)
        )

    # Step 9c: Contested-rating snapshots (non-fatal: training falls back
    # to building/updating the artifact itself when the stack is enabled)
    if should_run("elo-snapshots", args):
        results.append(
            run_step("Elo Rating Snapshots", run_elo_snapshot_update, config)
        )

    # Step 10: Train model
    if should_run("train", args):
        results.append(
            run_step("Train Production Model", run_model_training, config)
        )

    # Step 11: Train LambdaRank probability head (separate, appends to registry)
    if should_run("train-lambdarank", args):
        results.append(
            run_step("Train LambdaRank Head", run_lambdarank_training, config)
        )

    # Step 12: Train GC outlook head (state-aware final-GC prediction;
    # non-fatal — the app degrades gracefully when the head is absent)
    if should_run("train-gc-outlook", args):
        results.append(
            run_step("Train GC Outlook Head", run_gc_outlook_training, config)
        )

    # Step 13: Train DNF head (non-fatal — the app's pricing layer degrades
    # to unadjusted prices when the head is absent)
    if should_run("train-dnf", args):
        results.append(
            run_step("Train DNF Head", run_dnf_training, config)
        )

    print_summary(results)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)

    print("=" * 70)
    print("CYCLING PREDICTION - WEEKLY UPDATE PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    start = time.time()
    run_pipeline(args)

    elapsed = time.time() - start
    print(f"\nPipeline finished in {elapsed/60:.1f} minutes")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
