"""
Bulk Query Utilities for Database Optimization

This module provides utility functions for efficient bulk database operations
used in the interaction embeddings pipeline.

Key features:
- Bulk retrieval of rider result samples
- Efficient competition ID extraction
- Optimized minimum race calculations
- Database connection management utilities
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path


class BulkQueryUtils:
    """
    Utility class for efficient bulk database operations.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the bulk query utilities.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Validate database exists
        if not Path(db_path).exists():
            raise ValueError(f"Database not found at {db_path}")
    
    def calculate_percentile_minimums(self, percentile_config: Dict[str, int]) -> Dict[str, int]:
        """
        Calculate minimum race counts based on percentiles for each race type.
        
        Args:
            percentile_config: Dictionary mapping race type to percentile
                             (e.g., {'gc': 60, 'stage': 60})
        
        Returns:
            Dictionary mapping race type to minimum race count
        """
        self.logger.info("Calculating percentile-based minimum race requirements...")
        
        race_type_definitions = {
            'gc': ['gc'],
            'stage': ['stage'],
            'one_day': ['one_day'],
            'stage_one_day': ['stage', 'one_day'],
            'all': ['gc', 'stage', 'one_day']
        }
        
        minimums = {}
        
        with sqlite3.connect(self.db_path) as conn:
            for race_type, percentile in percentile_config.items():
                try:
                    competition_types = race_type_definitions[race_type]
                    
                    # Build the competition type filter
                    if len(competition_types) == 1:
                        type_filter = f"= '{competition_types[0]}'"
                    else:
                        type_list = "', '".join(competition_types)
                        type_filter = f"IN ('{type_list}')"
                    
                    # Query to get all prior race counts for this race type
                    query = f"""
                    WITH race_type_results AS (
                        SELECT 
                            rr.id as rider_result_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY rr.rider_id 
                                ORDER BY c.date
                            ) - 1 as prior_races_of_type
                        FROM rider_results rr
                        JOIN competitions c ON rr.competition_id = c.id
                        WHERE c.date <= '2025-01-01'
                        AND c.competition_type {type_filter}
                    )
                    SELECT prior_races_of_type
                    FROM race_type_results
                    WHERE prior_races_of_type > 0
                    """
                    
                    df = pd.read_sql_query(query, conn)
                    
                    if not df.empty:
                        minimum_races = int(np.percentile(df['prior_races_of_type'], percentile))
                        minimums[race_type] = minimum_races
                        
                        total_results = len(df)
                        eligible_results = len(df[df['prior_races_of_type'] >= minimum_races])
                        coverage_pct = (eligible_results / total_results) * 100
                        
                        self.logger.info(f"  {race_type}: {percentile}th percentile = {minimum_races} races "
                                       f"({eligible_results:,} results, {coverage_pct:.1f}% coverage)")
                    else:
                        minimums[race_type] = 1
                        self.logger.warning(f"  {race_type}: No data found, using minimum of 1")
                        
                except Exception as e:
                    self.logger.error(f"  {race_type}: Error calculating minimum - {e}")
                    minimums[race_type] = 1
        
        return minimums
    
    def get_rider_result_sample_with_competitions(
        self, 
        sample_size: int, 
        minimums: Dict[str, int],
        date_range: Tuple[str, str] = ('2020-01-01', '2025-01-01')
    ) -> List[Tuple[int, int]]:
        """
        Get a sample of rider results with their competition IDs.
        
        Args:
            sample_size: Number of rider results to sample
            minimums: Dictionary of minimum race requirements by race type
            date_range: Tuple of (start_date, end_date) for filtering
            
        Returns:
            List of (rider_result_id, competition_id) tuples
        """
        self.logger.info(f"Getting sample of {sample_size} rider results...")
        
        start_date, end_date = date_range
        min_races = minimums.get('all', 35)
        
        query = """
        WITH eligible_results AS (
            SELECT 
                rr.id as rider_result_id,
                rr.competition_id,
                c.date as competition_date,
                c.competition_type,
                ROW_NUMBER() OVER (PARTITION BY rr.rider_id ORDER BY c.date) - 1 as prior_races
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date >= ? AND c.date <= ?
        )
        SELECT DISTINCT rider_result_id, competition_id
        FROM eligible_results
        WHERE prior_races >= ?
        ORDER BY RANDOM()
        LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=(start_date, end_date, min_races, sample_size))
            
            result = [(row['rider_result_id'], row['competition_id']) for _, row in df.iterrows()]
            
            self.logger.info(f"✓ Retrieved {len(result)} rider result samples")
            return result
    
    def get_full_rider_result_dataset(
        self, 
        minimums: Dict[str, int],
        date_range: Tuple[str, str] = ('2020-01-01', '2025-01-01'),
        batch_size: int = 10000
    ) -> List[Tuple[int, int]]:
        """
        Get the complete dataset of rider results with competition IDs.
        
        Args:
            minimums: Dictionary of minimum race requirements by race type
            date_range: Tuple of (start_date, end_date) for filtering
            batch_size: Size of batches for processing large datasets
            
        Returns:
            List of (rider_result_id, competition_id) tuples
        """
        self.logger.info("Getting full rider result dataset...")
        
        start_date, end_date = date_range
        min_races = minimums.get('all', 35)
        
        # First, get the total count
        count_query = """
        WITH eligible_results AS (
            SELECT 
                rr.id as rider_result_id,
                ROW_NUMBER() OVER (PARTITION BY rr.rider_id ORDER BY c.date) - 1 as prior_races
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date >= ? AND c.date <= ?
        )
        SELECT COUNT(DISTINCT rider_result_id) as total_count
        FROM eligible_results
        WHERE prior_races >= ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            total_count = pd.read_sql_query(count_query, conn, params=(start_date, end_date, min_races))
            total_count = total_count['total_count'].iloc[0]
            
            self.logger.info(f"Total eligible rider results: {total_count:,}")
            
            # Get all results
            main_query = """
            WITH eligible_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    rr.competition_id,
                    c.date as competition_date,
                    c.competition_type,
                    ROW_NUMBER() OVER (PARTITION BY rr.rider_id ORDER BY c.date) - 1 as prior_races
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date >= ? AND c.date <= ?
            )
            SELECT DISTINCT rider_result_id, competition_id
            FROM eligible_results
            WHERE prior_races >= ?
            ORDER BY rider_result_id
            """
            
            df = pd.read_sql_query(main_query, conn, params=(start_date, end_date, min_races))
            
            result = [(row['rider_result_id'], row['competition_id']) for _, row in df.iterrows()]
            
            self.logger.info(f"✓ Retrieved {len(result)} rider results from full dataset")
            return result
    
    def get_unique_competition_ids(self, rider_results: List[Tuple[int, int]]) -> List[int]:
        """
        Extract unique competition IDs from rider results.
        
        Args:
            rider_results: List of (rider_result_id, competition_id) tuples
            
        Returns:
            List of unique competition IDs
        """
        competition_ids = list(set(comp_id for _, comp_id in rider_results))
        self.logger.info(f"Extracted {len(competition_ids)} unique competition IDs")
        return competition_ids
    
    def get_rider_result_ids(self, rider_results: List[Tuple[int, int]]) -> List[int]:
        """
        Extract rider result IDs from rider results.
        
        Args:
            rider_results: List of (rider_result_id, competition_id) tuples
            
        Returns:
            List of rider result IDs
        """
        rider_result_ids = [rr_id for rr_id, _ in rider_results]
        self.logger.info(f"Extracted {len(rider_result_ids)} rider result IDs")
        return rider_result_ids
    
    def validate_feature_tables(self, feature_tables: List[str]) -> List[str]:
        """
        Validate that feature tables exist in the database.
        
        Args:
            feature_tables: List of feature table names to validate
            
        Returns:
            List of validated feature table names
        """
        self.logger.info(f"Validating {len(feature_tables)} feature tables...")
        
        valid_tables = []
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for table in feature_tables:
                try:
                    # Check if table exists
                    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
                    if cursor.fetchone():
                        # Check if table has data
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        if count > 0:
                            valid_tables.append(table)
                            self.logger.info(f"  ✓ {table} ({count:,} rows)")
                        else:
                            self.logger.warning(f"  ✗ {table} (empty)")
                    else:
                        self.logger.warning(f"  ✗ {table} (does not exist)")
                except Exception as e:
                    self.logger.error(f"  ✗ {table} (error: {e})")
        
        self.logger.info(f"✓ Validated {len(valid_tables)} feature tables")
        return valid_tables
    
    def get_database_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the database for monitoring and optimization.
        
        Returns:
            Dictionary with database statistics
        """
        self.logger.info("Collecting database statistics...")
        
        stats = {}
        
        with sqlite3.connect(self.db_path) as conn:
            # Get table counts
            table_queries = {
                'competitions': "SELECT COUNT(*) FROM competitions",
                'riders': "SELECT COUNT(*) FROM riders",
                'rider_results': "SELECT COUNT(*) FROM rider_results",
            }
            
            for table_name, query in table_queries.items():
                try:
                    result = pd.read_sql_query(query, conn)
                    stats[f'{table_name}_count'] = result.iloc[0, 0]
                except Exception as e:
                    self.logger.error(f"Error getting {table_name} count: {e}")
                    stats[f'{table_name}_count'] = 0
            
            # Get feature table counts
            feature_table_stats = {}
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'race_features_%'")
            feature_tables = [row[0] for row in cursor.fetchall()]
            
            for table in feature_tables:
                try:
                    result = pd.read_sql_query(f"SELECT COUNT(*) FROM {table}", conn)
                    feature_table_stats[table] = result.iloc[0, 0]
                except Exception as e:
                    self.logger.error(f"Error getting {table} count: {e}")
                    feature_table_stats[table] = 0
            
            stats['feature_tables'] = feature_table_stats
            
            # Get date range
            try:
                date_query = """
                SELECT 
                    MIN(date) as earliest_date,
                    MAX(date) as latest_date
                FROM competitions
                """
                result = pd.read_sql_query(date_query, conn)
                stats['date_range'] = {
                    'earliest': result.iloc[0, 0],
                    'latest': result.iloc[0, 1]
                }
            except Exception as e:
                self.logger.error(f"Error getting date range: {e}")
                stats['date_range'] = {'earliest': None, 'latest': None}
        
        self.logger.info("✓ Database statistics collected")
        return stats
    
    def optimize_database_connection(self) -> sqlite3.Connection:
        """
        Create an optimized database connection with performance settings.
        
        Returns:
            Optimized SQLite connection
        """
        conn = sqlite3.connect(self.db_path)
        
        # Apply performance optimizations
        conn.execute("PRAGMA journal_mode = WAL")  # Write-Ahead Logging
        conn.execute("PRAGMA synchronous = NORMAL")  # Faster writes
        conn.execute("PRAGMA cache_size = 10000")  # Larger cache
        conn.execute("PRAGMA temp_store = MEMORY")  # Memory for temp tables
        
        return conn