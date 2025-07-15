"""
Shared Data Loader for Interaction Embeddings

This module provides optimized data loading that pre-loads all necessary data
into shared memory to eliminate redundant database queries during processing.

Key features:
- Pre-loads ALL race features for given competitions
- Bulk loads rider histories in single optimized queries
- Provides cached access to loaded data
- Supports sharing data across multiple workers

Usage:
    loader = SharedDataLoader(db_path)
    race_features = loader.preload_race_features(competition_ids, feature_tables)
    rider_histories = loader.preload_rider_histories(rider_result_ids)
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from pathlib import Path
import time


class SharedDataLoader:
    """
    Optimized data loader that pre-loads data into shared memory for efficient access.
    
    This class eliminates the need for repeated database queries by loading all
    necessary data upfront and providing cached access methods.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the shared data loader.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        
        # Validate database exists
        if not Path(db_path).exists():
            raise ValueError(f"Database not found at {db_path}")
    
    def preload_race_features(
        self, 
        competition_ids: List[int], 
        feature_tables: List[str]
    ) -> Dict[str, Dict[int, Dict[str, float]]]:
        """
        Pre-load ALL race features for the given competitions.
        
        This method loads all race features from all specified tables for all
        competitions in a single pass, eliminating the need for repeated queries.
        
        Args:
            competition_ids: List of competition IDs to load features for
            feature_tables: List of feature table names (e.g., ['race_features_60', 'race_features_70'])
            
        Returns:
            Dictionary structure: {table_name: {competition_id: {feature_name: value}}}
            
        Example:
            >>> loader = SharedDataLoader('database.db')
            >>> features = loader.preload_race_features([1, 2, 3], ['race_features_60'])
            >>> features['race_features_60'][1]['avg_group_size']
            2.5
        """
        self.logger.info(f"Pre-loading race features for {len(competition_ids)} competitions from {len(feature_tables)} tables")
        
        start_time = time.time()
        race_features = {}
        
        with sqlite3.connect(self.db_path) as conn:
            for table in feature_tables:
                table_start = time.time()
                self.logger.info(f"  Loading {table}...")
                
                try:
                    # Single query to load all features for all competitions
                    # Convert numpy int64 types to regular Python ints for sqlite3 compatibility
                    comp_ids_converted = [int(comp_id) for comp_id in competition_ids]
                    placeholders = ','.join(['?' for _ in comp_ids_converted])
                    query = f"SELECT * FROM {table} WHERE competition_id IN ({placeholders})"
                    
                    df = pd.read_sql_query(query, conn, params=comp_ids_converted)
                    
                    # Define the specific numeric features we want to use
                    numeric_feature_names = [
                        'total_finishers', 'included_finishers', 'abandon_ratio', 
                        'winning_time', 'total_race_duration',
                        'variance_absolute', 'variance_normalized',
                        'std_deviation_absolute', 'std_deviation_normalized',
                        'skewness_absolute', 'skewness_normalized',
                        'kurtosis_absolute', 'kurtosis_normalized',
                        'gini_coefficient',
                        'shannon_entropy_absolute', 'shannon_entropy_normalized',
                        '5th_percentile_gap', '10th_percentile_gap', '15th_percentile_gap',
                        '20th_percentile_gap', '25th_percentile_gap', '30th_percentile_gap',
                        '35th_percentile_gap', '40th_percentile_gap', '45th_percentile_gap',
                        '50th_percentile_gap',
                        'total_groups', 'riders_in_groups', 'proportion_in_groups',
                        'largest_group_size', 'largest_group_position', 'avg_group_size',
                        'std_group_size', 'biggest_group_metric', 'time_gap_evenness_metric',
                        'clumpiness_score', 'selection_metric'
                    ]
                    
                    # Convert to nested dictionary for fast lookup
                    table_features = {}
                    for _, row in df.iterrows():
                        comp_id = row['competition_id']
                        
                        # Extract only the numeric features we want
                        numeric_features = {}
                        for feature_name in numeric_feature_names:
                            if feature_name in row:
                                value = row[feature_name]
                                # Convert to float, use 0.0 for None values
                                numeric_features[feature_name] = float(value) if value is not None else 0.0
                        
                        table_features[comp_id] = numeric_features
                    
                    race_features[table] = table_features
                    
                    table_time = time.time() - table_start
                    self.logger.info(f"    Loaded {len(table_features)} competitions in {table_time:.1f}s")
                    
                except Exception as e:
                    self.logger.error(f"    Error loading {table}: {e}")
                    race_features[table] = {}
        
        total_time = time.time() - start_time
        total_competitions = sum(len(table_data) for table_data in race_features.values())
        
        self.logger.info(f"✓ Pre-loaded {total_competitions} competition feature sets in {total_time:.1f}s")
        
        return race_features
    
    def preload_rider_histories(
        self, 
        rider_result_ids: List[int]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Pre-load rider histories for all rider results in a single optimized query.
        
        This method loads the complete historical performance data for all riders
        in one query, eliminating the need for per-rider database queries.
        
        Args:
            rider_result_ids: List of rider_result IDs to load histories for
            
        Returns:
            Dictionary mapping rider_result_id to list of historical race results
            
        Example:
            >>> loader = SharedDataLoader('database.db')
            >>> histories = loader.preload_rider_histories([123, 456])
            >>> histories[123][0]['uci_points_proportional']
            15.5
        """
        self.logger.info(f"Pre-loading rider histories for {len(rider_result_ids)} rider results")
        
        start_time = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            # Single optimized query to get all rider histories
            # Convert numpy int64 types to regular Python ints for sqlite3 compatibility
            rider_ids_converted = [int(rider_id) for rider_id in rider_result_ids]
            placeholders = ','.join(['?' for _ in rider_ids_converted])
            query = f"""
            WITH target_riders AS (
                SELECT 
                    rr.id as rider_result_id,
                    rr.rider_id,
                    c.date as target_date
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE rr.id IN ({placeholders})
            ),
            historical_results AS (
                SELECT 
                    tr.rider_result_id,
                    hr.competition_id,
                    hr.uci_points_proportional,
                    hc.date,
                    hc.competition_type,
                    hc.name as competition_name
                FROM target_riders tr
                JOIN rider_results hr ON tr.rider_id = hr.rider_id
                JOIN competitions hc ON hr.competition_id = hc.id
                WHERE hc.date < tr.target_date
            )
            SELECT * FROM historical_results
            ORDER BY rider_result_id, date DESC
            """
            
            df = pd.read_sql_query(query, conn, params=rider_ids_converted)
            
            # Group by rider_result_id and convert to list of dictionaries
            rider_histories = {}
            
            for rider_result_id, group in df.groupby('rider_result_id'):
                history = []
                for _, row in group.iterrows():
                    history.append({
                        'competition_id': row['competition_id'],
                        'uci_points_proportional': row['uci_points_proportional'],
                        'date': row['date'],
                        'competition_type': row['competition_type'],
                        'competition_name': row['competition_name']
                    })
                rider_histories[rider_result_id] = history
            
            # Fill in empty histories for riders with no historical data
            for rider_result_id in rider_result_ids:
                if rider_result_id not in rider_histories:
                    rider_histories[rider_result_id] = []
        
        total_time = time.time() - start_time
        total_races = sum(len(history) for history in rider_histories.values())
        
        self.logger.info(f"✓ Pre-loaded {total_races} historical races for {len(rider_histories)} riders in {total_time:.1f}s")
        
        return rider_histories
    
    def get_competition_metadata(
        self, 
        competition_ids: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """
        Load competition metadata for the given competition IDs.
        
        Args:
            competition_ids: List of competition IDs
            
        Returns:
            Dictionary mapping competition_id to metadata dictionary
        """
        self.logger.info(f"Loading metadata for {len(competition_ids)} competitions")
        
        with sqlite3.connect(self.db_path) as conn:
            # Convert numpy int64 types to regular Python ints for sqlite3 compatibility
            comp_ids_converted = [int(comp_id) for comp_id in competition_ids]
            placeholders = ','.join(['?' for _ in comp_ids_converted])
            query = f"""
            SELECT 
                id,
                name,
                date,
                competition_type,
                country,
                category
            FROM competitions
            WHERE id IN ({placeholders})
            """
            
            df = pd.read_sql_query(query, conn, params=comp_ids_converted)
            
            metadata = {}
            for _, row in df.iterrows():
                metadata[row['id']] = {
                    'name': row['name'],
                    'date': row['date'],
                    'competition_type': row['competition_type'],
                    'country': row['country'],
                    'category': row['category']
                }
        
        self.logger.info(f"✓ Loaded metadata for {len(metadata)} competitions")
        return metadata
    
    def validate_data_integrity(
        self, 
        race_features: Dict[str, Dict[int, Dict[str, float]]],
        rider_histories: Dict[int, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Validate the integrity of pre-loaded data.
        
        Args:
            race_features: Pre-loaded race features data
            rider_histories: Pre-loaded rider histories data
            
        Returns:
            Dictionary with validation results and statistics
        """
        self.logger.info("Validating data integrity...")
        
        validation_results = {
            'race_features_stats': {},
            'rider_histories_stats': {},
            'data_quality_issues': [],
            'summary': {}
        }
        
        # Validate race features
        for table_name, table_data in race_features.items():
            stats = {
                'competitions_count': len(table_data),
                'features_count': len(next(iter(table_data.values()), {})),
                'missing_values': 0,
                'feature_names': list(next(iter(table_data.values()), {}).keys())
            }
            
            # Check for missing values
            for comp_id, features in table_data.items():
                for feature_name, value in features.items():
                    if value is None or (isinstance(value, float) and np.isnan(value)):
                        stats['missing_values'] += 1
            
            validation_results['race_features_stats'][table_name] = stats
        
        # Validate rider histories
        total_riders = len(rider_histories)
        total_races = sum(len(history) for history in rider_histories.values())
        riders_with_no_history = sum(1 for history in rider_histories.values() if len(history) == 0)
        
        validation_results['rider_histories_stats'] = {
            'total_riders': total_riders,
            'total_historical_races': total_races,
            'riders_with_no_history': riders_with_no_history,
            'average_races_per_rider': total_races / total_riders if total_riders > 0 else 0
        }
        
        # Summary
        validation_results['summary'] = {
            'total_competitions_with_features': len(set().union(*[table_data.keys() for table_data in race_features.values()])),
            'total_feature_tables': len(race_features),
            'total_riders_with_histories': total_riders,
            'data_load_successful': True
        }
        
        self.logger.info("✓ Data integrity validation completed")
        return validation_results
    
    def get_cache_statistics(
        self, 
        race_features: Dict[str, Dict[int, Dict[str, float]]],
        rider_histories: Dict[int, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Get statistics about the cached data for monitoring and optimization.
        
        Args:
            race_features: Pre-loaded race features data
            rider_histories: Pre-loaded rider histories data
            
        Returns:
            Dictionary with cache statistics
        """
        # Calculate memory usage estimates
        race_features_size = sum(
            len(table_data) * len(next(iter(table_data.values()), {}))
            for table_data in race_features.values()
        )
        
        rider_histories_size = sum(len(history) for history in rider_histories.values())
        
        return {
            'race_features': {
                'tables_count': len(race_features),
                'total_competition_feature_pairs': race_features_size,
                'competitions_per_table': {
                    table: len(table_data) for table, table_data in race_features.items()
                }
            },
            'rider_histories': {
                'riders_count': len(rider_histories),
                'total_historical_races': rider_histories_size,
                'average_races_per_rider': rider_histories_size / len(rider_histories) if rider_histories else 0
            },
            'estimated_memory_efficiency': {
                'race_features_entries': race_features_size,
                'rider_history_entries': rider_histories_size,
                'total_cached_entries': race_features_size + rider_histories_size
            }
        }