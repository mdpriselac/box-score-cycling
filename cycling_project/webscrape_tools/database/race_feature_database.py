"""
Race Feature Database Integration

This module provides functions to build and manage a comprehensive race feature database
by processing competitions from the cycling database and storing extracted features.
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

from cycling_project.webscrape_tools.database.race_feature_extraction import extract_race_features, extract_features_for_percentile_range


def get_competition_ids(
    db_path: str,
    year: Optional[int] = None,
    category: Optional[str] = None,
    competition_type: Optional[str] = None,
    min_finishers: int = 40
) -> List[int]:
    """
    Get competition IDs based on filtering criteria.
    
    Args:
        db_path: Path to SQLite database
        year: Filter by year (optional)
        category: Filter by race category (wt/pro/d1) (optional)
        competition_type: Filter by type (one_day/stage/gc) (optional)
        min_finishers: Minimum number of finishers required
        
    Returns:
        List of competition IDs matching criteria
    """
    conn = sqlite3.connect(db_path)
    
    # Build query with filters
    query = """
    SELECT c.id, COUNT(rr.id) as finisher_count
    FROM competitions c
    JOIN races r ON c.race_id = r.id
    LEFT JOIN rider_results rr ON c.id = rr.competition_id
    WHERE c.winning_time IS NOT NULL
    """
    
    params = []
    
    if year is not None:
        query += " AND r.year = ?"
        params.append(year)
    
    if category is not None:
        query += " AND r.category = ?"
        params.append(category)
    
    if competition_type is not None:
        query += " AND c.competition_type = ?"
        params.append(competition_type)
    
    query += """
    GROUP BY c.id
    HAVING finisher_count >= ?
    ORDER BY r.year, r.date
    """
    params.append(min_finishers)
    
    result = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return result['id'].tolist()


def create_feature_table(db_path: str, table_name: str = "race_features", drop_existing: bool = True):
    """
    Create a table to store extracted race features.

    Args:
        db_path: Path to SQLite database
        table_name: Name for the feature table
        drop_existing: If True, drops and recreates the table. If False, creates only if missing.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if drop_existing:
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")

    create_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER NOT NULL,
        percentile_analyzed REAL NOT NULL,
        extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Metadata
        competition_name TEXT,
        competition_type TEXT,
        race_id INTEGER,
        race_name TEXT,
        race_category TEXT,
        race_year INTEGER,
        race_date DATE,
        
        -- Basic statistics
        total_finishers INTEGER,
        included_finishers INTEGER,
        abandon_ratio REAL,
        winning_time REAL,
        total_race_duration REAL,
        
        -- Statistical features
        variance_absolute REAL,
        variance_normalized REAL,
        std_deviation_absolute REAL,
        std_deviation_normalized REAL,
        skewness_absolute REAL,
        skewness_normalized REAL,
        kurtosis_absolute REAL,
        kurtosis_normalized REAL,
        kurtosis_absolute_imputed REAL,
        kurtosis_normalized_imputed REAL,
        gini_coefficient REAL,
        shannon_entropy_absolute REAL,
        shannon_entropy_normalized REAL,
        
        -- Percentile gaps
        "5th_percentile_gap" REAL,
        "10th_percentile_gap" REAL,
        "15th_percentile_gap" REAL,
        "20th_percentile_gap" REAL,
        "25th_percentile_gap" REAL,
        "30th_percentile_gap" REAL,
        "35th_percentile_gap" REAL,
        "40th_percentile_gap" REAL,
        "45th_percentile_gap" REAL,
        "50th_percentile_gap" REAL,
        
        -- Engineered features
        total_groups INTEGER,
        riders_in_groups INTEGER,
        proportion_in_groups REAL,
        largest_group_size INTEGER,
        largest_group_position INTEGER,
        avg_group_size REAL,
        std_group_size REAL,
        biggest_group_metric REAL,
        time_gap_evenness_metric REAL,
        clumpiness_score REAL,
        selection_metric REAL,
        
        -- Constraints
        UNIQUE(competition_id, percentile_analyzed),
        FOREIGN KEY (competition_id) REFERENCES competitions(id),
        FOREIGN KEY (race_id) REFERENCES races(id)
    )
    """
    
    cursor.execute(create_query)
    
    # Create indexes for efficient querying
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_competition ON {table_name}(competition_id)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_percentile ON {table_name}(percentile_analyzed)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_year ON {table_name}(race_year)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_category ON {table_name}(race_category)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_type ON {table_name}(competition_type)")
    
    conn.commit()
    conn.close()


def insert_features_to_db(
    features: Dict,
    db_path: str,
    table_name: str = "race_features"
):
    """
    Insert extracted features into the database.
    
    Args:
        features: Dictionary of features from extract_race_features
        db_path: Path to SQLite database
        table_name: Name of the feature table
    """
    conn = sqlite3.connect(db_path)
    
    # Convert dict to DataFrame for easy insertion
    df = pd.DataFrame([features])
    
    # Insert into database
    df.to_sql(table_name, conn, if_exists='append', index=False)
    
    conn.close()


def process_competitions_batch(
    competition_ids: List[int],
    percentile: float,
    db_path: str,
    table_name: str = "race_features",
    n_threads: int = 4
) -> Tuple[int, int]:
    """
    Process a batch of competitions in parallel.
    
    Args:
        competition_ids: List of competition IDs to process
        percentile: Percentile cutoff for analysis
        db_path: Path to SQLite database
        table_name: Name of the feature table
        n_threads: Number of parallel threads
        
    Returns:
        Tuple of (successful_count, failed_count)
    """
    successful = 0
    failed = 0
    
    def process_single(comp_id):
        try:
            features = extract_race_features(comp_id, percentile, db_path)
            insert_features_to_db(features, db_path, table_name)
            return True
        except Exception as e:
            logging.warning(f"Failed to process competition {comp_id}: {e}")
            return False
    
    with ThreadPoolExecutor(max_workers=n_threads) as executor:
        futures = {executor.submit(process_single, comp_id): comp_id 
                   for comp_id in competition_ids}
        
        for future in as_completed(futures):
            if future.result():
                successful += 1
            else:
                failed += 1
    
    return successful, failed


def build_feature_database(
    db_path: str,
    years: Optional[List[int]] = None,
    categories: Optional[List[str]] = None,
    competition_types: Optional[List[str]] = None,
    percentiles: List[float] = [0.25, 0.5, 0.75, 1.0],
    table_name: str = "race_features",
    n_threads: int = 4,
    rebuild: bool = False
):
    """
    Build a comprehensive feature database for specified races.
    
    Args:
        db_path: Path to SQLite database
        years: List of years to process (None = all)
        categories: List of categories (wt/pro/d1) to process (None = all)
        competition_types: List of types (one_day/stage/gc) to process (None = all)
        percentiles: List of percentile cutoffs to analyze
        table_name: Name for the feature table
        n_threads: Number of parallel threads
        rebuild: Whether to rebuild existing table
        
    Returns:
        Summary DataFrame of processing results
    """
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create or rebuild table
    if rebuild or not table_exists(db_path, table_name):
        logger.info(f"Creating feature table: {table_name}")
        create_feature_table(db_path, table_name)
    
    # Get all years if not specified
    if years is None:
        conn = sqlite3.connect(db_path)
        years = pd.read_sql_query("SELECT DISTINCT year FROM races ORDER BY year", conn)['year'].tolist()
        conn.close()
    
    # Process each combination
    results = []
    
    for year in years:
        logger.info(f"Processing year {year}")
        
        # Get competitions for this year
        comp_ids = get_competition_ids(
            db_path,
            year=year,
            category=None,  # Process all categories
            competition_type=None  # Process all types
        )
        
        logger.info(f"Found {len(comp_ids)} competitions in {year}")
        
        for percentile in percentiles:
            logger.info(f"Processing percentile {percentile:.0%}")
            
            successful, failed = process_competitions_batch(
                comp_ids,
                percentile,
                db_path,
                table_name,
                n_threads
            )
            
            results.append({
                'year': year,
                'percentile': percentile,
                'total_competitions': len(comp_ids),
                'successful': successful,
                'failed': failed,
                'success_rate': successful / len(comp_ids) if comp_ids else 0
            })
    
    return pd.DataFrame(results)


def table_exists(db_path: str, table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def get_feature_summary(db_path: str, table_name: str = "race_features") -> pd.DataFrame:
    """
    Get a summary of the feature database.
    
    Args:
        db_path: Path to SQLite database
        table_name: Name of the feature table
        
    Returns:
        DataFrame with summary statistics
    """
    conn = sqlite3.connect(db_path)
    
    query = f"""
    SELECT 
        race_year,
        race_category,
        competition_type,
        percentile_analyzed,
        COUNT(*) as count,
        AVG(abandon_ratio) as avg_abandon_ratio,
        AVG(biggest_group_metric) as avg_biggest_group,
        AVG(clumpiness_score) as avg_clumpiness,
        AVG(selection_metric) as avg_selection
    FROM {table_name}
    GROUP BY race_year, race_category, competition_type, percentile_analyzed
    ORDER BY race_year, race_category, competition_type, percentile_analyzed
    """
    
    summary = pd.read_sql_query(query, conn)
    conn.close()
    
    return summary


def load_features_for_analysis(
    db_path: str,
    table_name: str = "race_features",
    year: Optional[int] = None,
    category: Optional[str] = None,
    competition_type: Optional[str] = None,
    percentile: Optional[float] = None
) -> pd.DataFrame:
    """
    Load features from database for analysis.
    
    Args:
        db_path: Path to SQLite database
        table_name: Name of the feature table
        year: Filter by year (optional)
        category: Filter by category (optional)
        competition_type: Filter by type (optional)
        percentile: Filter by percentile (optional)
        
    Returns:
        DataFrame with requested features
    """
    conn = sqlite3.connect(db_path)
    
    query = f"SELECT * FROM {table_name} WHERE 1=1"
    params = []
    
    if year is not None:
        query += " AND race_year = ?"
        params.append(year)
    
    if category is not None:
        query += " AND race_category = ?"
        params.append(category)
    
    if competition_type is not None:
        query += " AND competition_type = ?"
        params.append(competition_type)
    
    if percentile is not None:
        query += " AND percentile_analyzed = ?"
        params.append(percentile)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    
    return df