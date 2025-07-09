#!/usr/bin/env python3
"""
Migration script to pre-compute experience features for all rider results.

This script adds columns to the rider_results table and populates them with
pre-calculated experience metrics, dramatically speeding up dataset generation.

Features to pre-compute:
- Prior UCI points (actual & proportional) by race category: wt, pro, d1
- Prior UCI points (actual & proportional) by competition type: gc, stage, one_day  
- Prior race counts by race category: wt, pro, d1
- Prior race counts by competition type: gc, stage, one_day
- Total prior races and total prior UCI points
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points


def add_experience_columns(conn: sqlite3.Connection):
    """Add experience feature columns to rider_results table."""
    print("Adding experience feature columns to rider_results table...")
    
    columns_to_add = [
        # Prior points by race category
        'prior_wt_points_actual INTEGER DEFAULT 0',
        'prior_wt_points_proportional REAL DEFAULT 0.0',
        'prior_pro_points_actual INTEGER DEFAULT 0',
        'prior_pro_points_proportional REAL DEFAULT 0.0',
        'prior_d1_points_actual INTEGER DEFAULT 0',
        'prior_d1_points_proportional REAL DEFAULT 0.0',
        
        # Prior points by competition type
        'prior_gc_points_actual INTEGER DEFAULT 0',
        'prior_gc_points_proportional REAL DEFAULT 0.0',
        'prior_stage_points_actual INTEGER DEFAULT 0',
        'prior_stage_points_proportional REAL DEFAULT 0.0',
        'prior_one_day_points_actual INTEGER DEFAULT 0',
        'prior_one_day_points_proportional REAL DEFAULT 0.0',
        
        # Prior race counts by race category
        'prior_wt_races INTEGER DEFAULT 0',
        'prior_pro_races INTEGER DEFAULT 0',
        'prior_d1_races INTEGER DEFAULT 0',
        
        # Prior race counts by competition type
        'prior_gc_races INTEGER DEFAULT 0',
        'prior_stage_races INTEGER DEFAULT 0',
        'prior_one_day_races INTEGER DEFAULT 0',
        
        # Total prior experience
        'total_prior_races INTEGER DEFAULT 0',
        'total_prior_points_actual INTEGER DEFAULT 0',
        'total_prior_points_proportional REAL DEFAULT 0.0',
        'prior_wt_proportion REAL DEFAULT 0.0',
        
        # Current race UCI points
        'uci_points_actual INTEGER DEFAULT 0',
        'uci_points_proportional REAL DEFAULT 0.0',
        
        # Metadata
        'experience_calculated_at TIMESTAMP'
    ]
    
    # Check which columns already exist
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(rider_results)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    
    # Add only non-existing columns
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


def get_all_results_chronologically(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get all rider results in chronological order with necessary information."""
    print("Loading all rider results chronologically...")
    
    query = """
    SELECT 
        rr.id as result_id,
        rr.rider_id,
        rr.competition_id,
        rr.place,
        rr.rider_age,
        c.date as competition_date,
        c.competition_type,
        r.category as race_category,
        r.fc_race_id,
        r.name as race_name,
        c.name as competition_name
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    ORDER BY rr.rider_id, c.date, rr.id
    """
    
    df = pd.read_sql_query(query, conn)
    print(f"Loaded {len(df)} rider results")
    return df


def calculate_current_uci_points(row):
    """Calculate current UCI points for a result."""
    try:
        actual = get_actual_uci_place_points(
            row['place'], row['competition_type'], 
            row['race_category'], row['fc_race_id']
        )
        proportional = get_top_tier_based_points(
            row['place'], row['competition_type'], 
            row['race_category'], row['fc_race_id']
        )
        return actual, proportional
    except:
        return 0, 0


def calculate_experience_features_for_rider(rider_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate experience features for a single rider's results."""
    rider_df = rider_df.sort_values('competition_date').copy()
    
    # Initialize experience tracking
    experience_data = []
    
    # Running totals for experience calculation
    running_totals = {
        'wt_actual': 0, 'wt_proportional': 0.0, 'wt_count': 0,
        'pro_actual': 0, 'pro_proportional': 0.0, 'pro_count': 0,
        'd1_actual': 0, 'd1_proportional': 0.0, 'd1_count': 0,
        'gc_actual': 0, 'gc_proportional': 0.0, 'gc_count': 0,
        'stage_actual': 0, 'stage_proportional': 0.0, 'stage_count': 0,
        'one_day_actual': 0, 'one_day_proportional': 0.0, 'one_day_count': 0,
        'total_actual': 0, 'total_proportional': 0.0, 'total_count': 0
    }
    
    for _, row in rider_df.iterrows():
        result_id = row['result_id']
        
        # Calculate current UCI points
        current_actual, current_proportional = calculate_current_uci_points(row)
        
        # Create experience record with current running totals (prior experience)
        experience_record = {
            'result_id': result_id,
            
            # Prior points by race category
            'prior_wt_points_actual': running_totals['wt_actual'],
            'prior_wt_points_proportional': running_totals['wt_proportional'],
            'prior_pro_points_actual': running_totals['pro_actual'],
            'prior_pro_points_proportional': running_totals['pro_proportional'],
            'prior_d1_points_actual': running_totals['d1_actual'],
            'prior_d1_points_proportional': running_totals['d1_proportional'],
            
            # Prior points by competition type
            'prior_gc_points_actual': running_totals['gc_actual'],
            'prior_gc_points_proportional': running_totals['gc_proportional'],
            'prior_stage_points_actual': running_totals['stage_actual'],
            'prior_stage_points_proportional': running_totals['stage_proportional'],
            'prior_one_day_points_actual': running_totals['one_day_actual'],
            'prior_one_day_points_proportional': running_totals['one_day_proportional'],
            
            # Prior race counts by race category
            'prior_wt_races': running_totals['wt_count'],
            'prior_pro_races': running_totals['pro_count'],
            'prior_d1_races': running_totals['d1_count'],
            
            # Prior race counts by competition type
            'prior_gc_races': running_totals['gc_count'],
            'prior_stage_races': running_totals['stage_count'],
            'prior_one_day_races': running_totals['one_day_count'],
            
            # Total prior experience
            'total_prior_races': running_totals['total_count'],
            'total_prior_points_actual': running_totals['total_actual'],
            'total_prior_points_proportional': running_totals['total_proportional'],
            'prior_wt_proportion': running_totals['wt_count'] / running_totals['total_count'] if running_totals['total_count'] > 0 else 0.0,
            
            # Current race UCI points
            'uci_points_actual': current_actual,
            'uci_points_proportional': current_proportional,
            
            # Metadata
            'experience_calculated_at': datetime.now().isoformat()
        }
        
        experience_data.append(experience_record)
        
        # Update running totals with current race results
        race_category = row['race_category']
        competition_type = row['competition_type']
        
        # Update by race category
        if race_category == 'wt':
            running_totals['wt_actual'] += current_actual
            running_totals['wt_proportional'] += current_proportional
            running_totals['wt_count'] += 1
        elif race_category == 'pro':
            running_totals['pro_actual'] += current_actual
            running_totals['pro_proportional'] += current_proportional
            running_totals['pro_count'] += 1
        elif race_category == 'd1':
            running_totals['d1_actual'] += current_actual
            running_totals['d1_proportional'] += current_proportional
            running_totals['d1_count'] += 1
        
        # Update by competition type
        if competition_type == 'gc':
            running_totals['gc_actual'] += current_actual
            running_totals['gc_proportional'] += current_proportional
            running_totals['gc_count'] += 1
        elif competition_type == 'stage':
            running_totals['stage_actual'] += current_actual
            running_totals['stage_proportional'] += current_proportional
            running_totals['stage_count'] += 1
        elif competition_type == 'one_day':
            running_totals['one_day_actual'] += current_actual
            running_totals['one_day_proportional'] += current_proportional
            running_totals['one_day_count'] += 1
        
        # Update totals
        running_totals['total_actual'] += current_actual
        running_totals['total_proportional'] += current_proportional
        running_totals['total_count'] += 1
    
    return pd.DataFrame(experience_data)


def update_rider_results_with_experience(conn: sqlite3.Connection, experience_df: pd.DataFrame):
    """Update rider_results table with calculated experience features."""
    print(f"Updating rider_results table with {len(experience_df)} experience records...")
    
    # Prepare update query
    update_query = """
    UPDATE rider_results SET
        prior_wt_points_actual = ?,
        prior_wt_points_proportional = ?,
        prior_pro_points_actual = ?,
        prior_pro_points_proportional = ?,
        prior_d1_points_actual = ?,
        prior_d1_points_proportional = ?,
        prior_gc_points_actual = ?,
        prior_gc_points_proportional = ?,
        prior_stage_points_actual = ?,
        prior_stage_points_proportional = ?,
        prior_one_day_points_actual = ?,
        prior_one_day_points_proportional = ?,
        prior_wt_races = ?,
        prior_pro_races = ?,
        prior_d1_races = ?,
        prior_gc_races = ?,
        prior_stage_races = ?,
        prior_one_day_races = ?,
        total_prior_races = ?,
        total_prior_points_actual = ?,
        total_prior_points_proportional = ?,
        prior_wt_proportion = ?,
        uci_points_actual = ?,
        uci_points_proportional = ?,
        experience_calculated_at = ?
    WHERE id = ?
    """
    
    # Prepare data for batch update
    update_data = []
    for _, row in experience_df.iterrows():
        update_data.append((
            row['prior_wt_points_actual'],
            row['prior_wt_points_proportional'],
            row['prior_pro_points_actual'],
            row['prior_pro_points_proportional'],
            row['prior_d1_points_actual'],
            row['prior_d1_points_proportional'],
            row['prior_gc_points_actual'],
            row['prior_gc_points_proportional'],
            row['prior_stage_points_actual'],
            row['prior_stage_points_proportional'],
            row['prior_one_day_points_actual'],
            row['prior_one_day_points_proportional'],
            row['prior_wt_races'],
            row['prior_pro_races'],
            row['prior_d1_races'],
            row['prior_gc_races'],
            row['prior_stage_races'],
            row['prior_one_day_races'],
            row['total_prior_races'],
            row['total_prior_points_actual'],
            row['total_prior_points_proportional'],
            row['prior_wt_proportion'],
            row['uci_points_actual'],
            row['uci_points_proportional'],
            row['experience_calculated_at'],
            row['result_id']
        ))
    
    # Execute batch update
    cursor = conn.cursor()
    cursor.executemany(update_query, update_data)
    conn.commit()
    print(f"Updated {cursor.rowcount} records")


def create_indexes(conn: sqlite3.Connection):
    """Create indexes for faster lookups."""
    print("Creating indexes for faster lookups...")
    
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_rider_results_rider_comp ON rider_results(rider_id, competition_id)",
        "CREATE INDEX IF NOT EXISTS idx_rider_results_experience_calc ON rider_results(experience_calculated_at)",
        "CREATE INDEX IF NOT EXISTS idx_rider_results_total_prior ON rider_results(total_prior_races)",
    ]
    
    cursor = conn.cursor()
    for index_sql in indexes:
        cursor.execute(index_sql)
        print(f"  Created index: {index_sql.split('idx_')[1].split(' ON')[0]}")
    
    conn.commit()


def migrate_precompute_experience_features(db_path: str):
    """Main migration function."""
    print("=" * 80)
    print("RIDER EXPERIENCE FEATURES MIGRATION")
    print("=" * 80)
    print(f"Database: {db_path}")
    print(f"Started at: {datetime.now()}")
    print()
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Step 1: Add columns
        add_experience_columns(conn)
        
        # Step 2: Get all results
        all_results = get_all_results_chronologically(conn)
        
        # Step 3: Process each rider
        print("Calculating experience features for all riders...")
        unique_riders = all_results['rider_id'].unique()
        print(f"Processing {len(unique_riders)} riders...")
        
        all_experience_data = []
        
        for i, rider_id in enumerate(unique_riders):
            if i % 100 == 0:
                print(f"  Processing rider {i+1}/{len(unique_riders)} (ID: {rider_id})")
            
            rider_results = all_results[all_results['rider_id'] == rider_id]
            rider_experience = calculate_experience_features_for_rider(rider_results)
            all_experience_data.append(rider_experience)
        
        # Combine all experience data
        experience_df = pd.concat(all_experience_data, ignore_index=True)
        
        # Step 4: Update database
        update_rider_results_with_experience(conn, experience_df)
        
        # Step 5: Create indexes
        create_indexes(conn)
        
        print()
        print("=" * 80)
        print("MIGRATION COMPLETE")
        print("=" * 80)
        print(f"Processed {len(experience_df)} rider results")
        print(f"Added {len([col for col in experience_df.columns if col != 'result_id'])} experience features")
        print(f"Completed at: {datetime.now()}")
        
        # Show some sample data
        print("\nSample of calculated features:")
        sample_query = """
        SELECT 
            rider_id, 
            total_prior_races, 
            prior_wt_proportion,
            total_prior_points_actual,
            uci_points_actual
        FROM rider_results 
        WHERE total_prior_races > 0 
        ORDER BY total_prior_races DESC 
        LIMIT 5
        """
        sample_df = pd.read_sql_query(sample_query, conn)
        print(sample_df.to_string(index=False))
        
    except Exception as e:
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = "database/database/cycling_races.db"
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    if not os.path.exists(db_path):
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)
    
    # Run migration
    migrate_precompute_experience_features(db_path)