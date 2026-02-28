"""
Build Race Feature Tables by Percentile

This script creates separate tables for each percentile cutoff, allowing for
more efficient querying and analysis of percentile-specific features.
"""

import logging
import time
from datetime import datetime, timedelta
from cycling_project.webscrape_tools.database.race_feature_database import (
    get_competition_ids,
    create_feature_table,
    process_competitions_batch,
    get_feature_summary
)

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"

def print_progress_bar(current, total, start_time, prefix='Progress', length=50):
    """Print a progress bar with timing information."""
    percent = current / total
    filled_length = int(length * percent)
    bar = '█' * filled_length + '-' * (length - filled_length)
    
    # Calculate timing
    elapsed = time.time() - start_time
    if current > 0:
        rate = current / elapsed
        eta_seconds = (total - current) / rate if rate > 0 else 0
        eta = str(timedelta(seconds=int(eta_seconds)))
    else:
        eta = "calculating..."
    
    elapsed_str = str(timedelta(seconds=int(elapsed)))
    
    print(f'\r{prefix} |{bar}| {current}/{total} ({percent:.1%}) '
          f'Elapsed: {elapsed_str} ETA: {eta}', end='', flush=True)

def build_percentile_tables(
    db_path: str = DB_PATH,
    years: list = None,
    start_percentile: int = 10,
    end_percentile: int = 100,
    step: int = 5,
    n_threads: int = 8,
    rebuild: bool = False
):
    """
    Build separate feature tables for each percentile cutoff.
    
    Args:
        db_path: Path to SQLite database
        years: List of years to process (None = all available)
        start_percentile: Starting percentile (10 = top 10%)
        end_percentile: Ending percentile (100 = full field)
        step: Step between percentiles
        n_threads: Number of parallel threads
        rebuild: Whether to rebuild existing tables
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # Convert percentiles to decimal
    percentiles = [p/100.0 for p in range(start_percentile, end_percentile + step, step)]
    
    print(f"\n🏁 Building tables for percentiles: {[f'{p:.0%}' for p in percentiles]}")
    
    # Get all years if not specified
    if years is None:
        import sqlite3
        import pandas as pd
        conn = sqlite3.connect(db_path)
        years = pd.read_sql_query("SELECT DISTINCT year FROM races ORDER BY year", conn)['year'].tolist()
        conn.close()
    
    print(f"📅 Processing years: {years}")
    
    # Get total work estimate
    total_percentiles = len(percentiles)
    total_years = len(years)
    
    print(f"📊 Total work: {total_percentiles} percentiles × {total_years} years = {total_percentiles * total_years} processing tasks")
    
    # Overall timing
    overall_start = time.time()
    completed_tasks = 0
    total_tasks = total_percentiles * total_years
    
    # Process each percentile
    for p_idx, percentile in enumerate(percentiles):
        percentile_int = int(percentile * 100)
        table_name = f"race_features_{percentile_int}"
        
        print(f"\n{'='*80}")
        print(f"🎯 Processing percentile {percentile:.0%} ({p_idx + 1}/{total_percentiles}) -> table: {table_name}")
        print(f"{'='*80}")

        # Create table only if it doesn't exist (or rebuild if requested)
        if rebuild:
            print(f"🗄️  Rebuilding table: {table_name}")
            create_feature_table(db_path, table_name, drop_existing=True)
        else:
            print(f"🗄️  Ensuring table exists: {table_name}")
            create_feature_table(db_path, table_name, drop_existing=False)

        # Get existing competition IDs to skip them
        existing_comp_ids = set()
        if not rebuild:
            import sqlite3 as _sqlite3
            _conn = _sqlite3.connect(db_path)
            try:
                _cursor = _conn.execute(f"SELECT DISTINCT competition_id FROM {table_name}")
                existing_comp_ids = {row[0] for row in _cursor.fetchall()}
            except _sqlite3.OperationalError:
                pass
            _conn.close()

        total_successful = 0
        total_failed = 0
        percentile_start = time.time()

        # Process each year
        for y_idx, year in enumerate(years):
            year_start = time.time()

            print(f"\n📆 Processing year {year} ({y_idx + 1}/{total_years}) at {percentile:.0%}")

            # Get competitions for this year
            comp_ids = get_competition_ids(
                db_path,
                year=year,
                min_finishers=40  # Minimum for reliable statistics
            )

            # Skip already-processed competitions
            if existing_comp_ids:
                new_comp_ids = [c for c in comp_ids if c not in existing_comp_ids]
                if len(new_comp_ids) < len(comp_ids):
                    print(f"⏭️  Skipping {len(comp_ids) - len(new_comp_ids)} already-processed competitions")
                comp_ids = new_comp_ids

            if not comp_ids:
                print(f"⚠️  No competitions found for year {year}")
                completed_tasks += 1
                print_progress_bar(completed_tasks, total_tasks, overall_start, "Overall")
                continue
            
            print(f"🏆 Found {len(comp_ids)} competitions in {year}")
            
            # Process competitions with progress tracking
            print("⚙️  Processing competitions...")
            batch_start = time.time()
            
            successful, failed = process_competitions_batch(
                comp_ids,
                percentile,
                db_path,
                table_name,
                n_threads
            )
            
            batch_time = time.time() - batch_start
            total_successful += successful
            total_failed += failed
            
            print(f"\n✅ Year {year} complete: {successful} successful, {failed} failed "
                  f"(⏱️  {batch_time:.1f}s, {successful/batch_time:.1f} comps/sec)")
            
            completed_tasks += 1
            print_progress_bar(completed_tasks, total_tasks, overall_start, "Overall")
        
        # Summary for this percentile
        percentile_time = time.time() - percentile_start
        print(f"\n\n🎉 Percentile {percentile:.0%} complete (⏱️  {percentile_time:.1f}s):")
        print(f"   📈 Total successful: {total_successful}")
        print(f"   ❌ Total failed: {total_failed}")
        if total_successful + total_failed > 0:
            print(f"   📊 Success rate: {total_successful/(total_successful+total_failed):.1%}")
        
        # Get table summary
        try:
            summary = get_feature_summary(db_path, table_name)
            print(f"   🗃️  Table contains {len(summary)} competition groups")
        except Exception as e:
            print(f"   ⚠️  Could not get summary for {table_name}: {e}")
    
    # Final summary
    total_time = time.time() - overall_start
    print(f"\n{'='*80}")
    print(f"🏁 ALL PERCENTILE TABLES COMPLETE! (⏱️  Total time: {total_time:.1f}s)")
    print(f"{'='*80}")
    
    print("\n📋 Created tables:")
    for percentile in percentiles:
        percentile_int = int(percentile * 100)
        table_name = f"race_features_{percentile_int}"
        print(f"   ✓ {table_name} (top {percentile:.0%})")


def verify_tables(db_path: str = DB_PATH):
    """Verify that all percentile tables were created correctly."""
    import sqlite3
    import pandas as pd
    
    print("\n🔍 Verifying Tables...")
    
    conn = sqlite3.connect(db_path)
    
    # Get all race_features tables
    tables_query = """
    SELECT name FROM sqlite_master 
    WHERE type='table' AND name LIKE 'race_features_%'
    ORDER BY name
    """
    tables = pd.read_sql_query(tables_query, conn)
    
    print("\n📊 Percentile Table Verification:")
    print("=" * 60)
    
    total_records = 0
    for table_name in tables['name']:
        # Get count
        count_query = f"SELECT COUNT(*) as count FROM {table_name}"
        count = pd.read_sql_query(count_query, conn).iloc[0, 0]
        total_records += count
        
        # Get percentile info
        if count > 0:
            percentile_query = f"SELECT DISTINCT percentile_analyzed FROM {table_name}"
            percentile = pd.read_sql_query(percentile_query, conn).iloc[0, 0]
            print(f"✅ {table_name:<22} - {count:>6,} records (percentile: {percentile:.0%})")
        else:
            print(f"❌ {table_name:<22} - {count:>6,} records (EMPTY)")
    
    print("=" * 60)
    print(f"📈 Total records across all tables: {total_records:,}")
    
    conn.close()


if __name__ == "__main__":
    import sys
    
    print("🏁 RACE FEATURE PERCENTILE TABLE BUILDER")
    print("=" * 60)
    print("This will create separate tables for each percentile cutoff:")
    print("   🎯 race_features_5 (top 5%)")
    print("   🎯 race_features_10 (top 10%)")
    print("   🎯 race_features_15 (top 15%)")
    print("   🎯 race_features_20 (top 20%)")
    print("   🎯 race_features_25 (top 25%)")
    print("   🎯 race_features_30 (top 30%)")
    print("   🎯 ... and so on every 5% up to ...")
    print("   🎯 race_features_100 (full field)")
    print("=" * 60)
    
    # Get user confirmation
    response = input("\n▶️  Proceed with building all percentile tables? (y/N): ")
    if response.lower() != 'y':
        print("❌ Cancelled.")
        sys.exit(0)
    
    # Record overall start time
    script_start = time.time()
    
    # Build tables
    print(f"\n🚀 Starting at {datetime.now().strftime('%H:%M:%S')}")
    
    build_percentile_tables(
        #years=[2010,2011,2012,2013,2014,2015,2016,2017,2018,2019],  # Start with 2024, can change to None for all years
        rebuild=True
    )
    
    # Verify results
    verify_tables()
    
    # Final timing
    total_script_time = time.time() - script_start
    print(f"\n⏱️  Total script runtime: {str(timedelta(seconds=int(total_script_time)))}")
    print(f"✅ Completed at {datetime.now().strftime('%H:%M:%S')}")
    
    print("\n🎉 Complete! You can now query individual percentile tables:")
    print("   SELECT * FROM race_features_50 WHERE race_category = 'wt';")
    print("   SELECT * FROM race_features_30 WHERE competition_type = 'gc';")