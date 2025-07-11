import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
import logging
from collections import defaultdict
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))


class BatchedDatabaseLoader:
    """
    Optimized database loader that preloads data in batches to eliminate
    per-rider database queries during correlation generation.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the batched database loader.
        
        Args:
            db_path: Path to the cycling races database
        """
        self.db_path = db_path
        self._rider_histories_cache = {}
        self._race_features_cache = {}
        self.logger = logging.getLogger(__name__)
        
        # Validate database exists
        if not Path(db_path).exists():
            raise ValueError(f"Database not found at {db_path}")
    
    def preload_rider_histories(
        self, 
        rider_result_ids: List[int], 
        max_lookback_date: str = "2025-01-01"
    ) -> None:
        """
        Preload rider histories for all specified rider results in a single query.
        
        Args:
            rider_result_ids: List of rider_result IDs to preload histories for
            max_lookback_date: Maximum lookback date for history queries
        """
        self.logger.info(f"Preloading rider histories for {len(rider_result_ids)} rider results...")
        
        # First, get rider_ids and competition dates for all rider_result_ids
        rider_info_query = """
        SELECT rr.id as rider_result_id, rr.rider_id, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE rr.id IN ({})
        """.format(','.join(['?' for _ in rider_result_ids]))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(rider_info_query, rider_result_ids)
            rider_info = [dict(row) for row in cursor.fetchall()]
        
        if not rider_info:
            self.logger.warning("No rider result data found")
            return
        
        # Get unique rider_ids for history loading
        unique_rider_ids = list(set(info['rider_id'] for info in rider_info))
        
        # Load ALL historical race results for these riders in one query
        history_query = """
        SELECT 
            rr.rider_id,
            rr.competition_id,
            rr.place,
            rr.uci_points_proportional,
            c.date as competition_date,
            c.competition_type,
            c.race_id,
            r.category as race_level
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races r ON c.race_id = r.id
        WHERE rr.rider_id IN ({})
        AND c.date < ?
        ORDER BY rr.rider_id, c.date DESC
        """.format(','.join(['?' for _ in unique_rider_ids]))
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(history_query, unique_rider_ids + [max_lookback_date])
            all_histories = [dict(row) for row in cursor.fetchall()]
        
        # Group histories by rider_id
        histories_by_rider = defaultdict(list)
        for record in all_histories:
            histories_by_rider[record['rider_id']].append(record)
        
        # Cache histories for each rider_result_id with proper date filtering
        for info in rider_info:
            rider_result_id = info['rider_result_id']
            rider_id = info['rider_id']
            competition_date = info['competition_date']
            
            # Filter history to only include races before this specific competition
            filtered_history = [
                h for h in histories_by_rider[rider_id]
                if h['competition_date'] < competition_date
            ]
            
            self._rider_histories_cache[rider_result_id] = filtered_history
        
        self.logger.info(f"Cached histories for {len(self._rider_histories_cache)} rider results")
    
    def preload_race_features(self, feature_tables: List[str]) -> None:
        """
        Preload race features for all specified tables.
        
        Args:
            feature_tables: List of race_features_N table names to preload
        """
        self.logger.info(f"Preloading race features from {len(feature_tables)} tables...")
        
        for feature_table in feature_tables:
            try:
                # Get all competition IDs that exist in rider histories
                all_competition_ids = set()
                for history in self._rider_histories_cache.values():
                    all_competition_ids.update(h['competition_id'] for h in history)
                
                if not all_competition_ids:
                    self.logger.warning(f"No competition IDs found for {feature_table}")
                    continue
                
                # Load race features for all these competitions at once
                competition_ids_list = list(all_competition_ids)
                placeholders = ','.join(['?' for _ in competition_ids_list])
                
                # Get column names first (excluding metadata columns)
                exclude_cols = {
                    'id', 'competition_id', 'extraction_date', 'competition_name',
                    'competition_type', 'race_id', 'race_name', 'race_category',
                    'race_year', 'race_date', 'percentile_analyzed'
                }
                
                with sqlite3.connect(self.db_path) as conn:
                    # Get column names
                    cursor = conn.cursor()
                    cursor.execute(f"PRAGMA table_info({feature_table})")
                    all_cols = [row[1] for row in cursor.fetchall()]
                    feature_cols = [col for col in all_cols if col not in exclude_cols]
                    
                    if not feature_cols:
                        self.logger.warning(f"No feature columns found in {feature_table}")
                        continue
                    
                    # Quote column names to handle those starting with numbers
                    quoted_cols = [f'`{col}`' for col in feature_cols]
                    query = f"""
                    SELECT competition_id, {', '.join(quoted_cols)}
                    FROM {feature_table}
                    WHERE competition_id IN ({placeholders})
                    """
                    
                    # Set row factory for dictionary access
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(query, competition_ids_list)
                    
                    # Store features indexed by competition_id
                    features_data = {}
                    for row in cursor.fetchall():
                        comp_id = row['competition_id']
                        features_data[comp_id] = {col: row[col] for col in feature_cols}
                    
                    self._race_features_cache[feature_table] = features_data
                
                self.logger.info(f"Cached {len(features_data)} competitions for {feature_table}")
                
            except Exception as e:
                self.logger.error(f"Error loading {feature_table}: {e}")
                self._race_features_cache[feature_table] = {}
    
    def get_cached_rider_history(self, rider_result_id: int) -> List[Dict[str, Any]]:
        """
        Get cached rider history for a specific rider result.
        
        Args:
            rider_result_id: The rider result ID
            
        Returns:
            List of historical race records
        """
        return self._rider_histories_cache.get(rider_result_id, [])
    
    def get_cached_race_features(
        self, 
        competition_ids: List[int], 
        feature_table: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Get cached race features for a list of competitions.
        
        Args:
            competition_ids: List of competition IDs
            feature_table: Name of the race_features_N table
            
        Returns:
            Dictionary mapping competition_id to feature values
        """
        if feature_table not in self._race_features_cache:
            return {}
        
        features_data = self._race_features_cache[feature_table]
        result = {}
        
        for comp_id in competition_ids:
            if comp_id in features_data:
                result[comp_id] = features_data[comp_id]
        
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about cached data.
        
        Returns:
            Dictionary with cache statistics
        """
        rider_count = len(self._rider_histories_cache)
        total_races = sum(len(history) for history in self._rider_histories_cache.values())
        
        feature_stats = {}
        for table, features in self._race_features_cache.items():
            feature_stats[table] = {
                'competitions': len(features),
                'features': len(next(iter(features.values()), {}))
            }
        
        return {
            'rider_results_cached': rider_count,
            'total_historical_races': total_races,
            'average_races_per_rider': total_races / rider_count if rider_count > 0 else 0,
            'feature_tables': feature_stats
        }
    
    def clear_cache(self) -> None:
        """Clear all cached data to free memory."""
        self._rider_histories_cache.clear()
        self._race_features_cache.clear()
        self.logger.info("Cache cleared")
    
    def preload_all_data(
        self, 
        rider_result_ids: List[int], 
        feature_tables: List[str],
        max_lookback_date: str = "2025-01-01"
    ) -> None:
        """
        Convenience method to preload all necessary data.
        
        Args:
            rider_result_ids: List of rider_result IDs to process
            feature_tables: List of feature tables to preload
            max_lookback_date: Maximum lookback date for histories
        """
        self.logger.info("Starting batch data preload...")
        
        # Preload rider histories first
        self.preload_rider_histories(rider_result_ids, max_lookback_date)
        
        # Then preload race features
        self.preload_race_features(feature_tables)
        
        # Log statistics
        stats = self.get_cache_stats()
        self.logger.info(f"Preload complete: {stats}")