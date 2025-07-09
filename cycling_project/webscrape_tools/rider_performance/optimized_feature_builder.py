"""
Optimized feature builder for fast bulk dataset generation.

This module provides batch processing and caching optimizations for generating
features for multiple rider-competition pairs efficiently. It's designed to
work alongside the original FeatureBuilder for single-race predictions.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

from rider_result_features import RiderResultFeatures


class OptimizedFeatureBuilder:
    """Fast feature builder using batch processing and caching."""
    
    def __init__(self, db_path: str):
        """
        Initialize the optimized feature builder.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.result_features = RiderResultFeatures(db_path)
        
        # Cache for rider histories and competition features
        self._rider_histories = {}
        self._competition_features = {}
        
    def build_bulk_dataset_fast(self,
                               rider_competition_pairs: List[Tuple[int, int]],
                               cutoff_date: Optional[str] = None,
                               use_parallel: bool = True,
                               max_workers: int = None) -> pd.DataFrame:
        """
        Build features for multiple pairs using optimized batch processing.
        
        Args:
            rider_competition_pairs: List of (rider_id, competition_id) tuples
            cutoff_date: Optional cutoff date for experience calculation
            use_parallel: Whether to use parallel processing
            max_workers: Number of parallel workers (None = auto)
            
        Returns:
            DataFrame with all feature vectors
        """
        if not rider_competition_pairs:
            return pd.DataFrame()
            
        print(f"Building features for {len(rider_competition_pairs)} pairs (optimized)...")
        
        # Step 1: Pre-load all rider histories
        unique_riders = list(set(pair[0] for pair in rider_competition_pairs))
        print(f"Pre-loading histories for {len(unique_riders)} riders...")
        self._preload_rider_histories(unique_riders, cutoff_date)
        
        # Step 2: Pre-load all competition features
        unique_competitions = list(set(pair[1] for pair in rider_competition_pairs))
        print(f"Pre-loading features for {len(unique_competitions)} competitions...")
        self._preload_competition_features(unique_competitions)
        
        # Step 3: Get all rider results for the pairs
        print("Pre-loading rider results...")
        rider_results = self._preload_rider_results(rider_competition_pairs)
        
        # Step 4: Process pairs in batches
        print("Processing feature vectors...")
        if use_parallel and len(rider_competition_pairs) > 100:
            dataset = self._process_pairs_parallel(
                rider_competition_pairs, rider_results, cutoff_date, max_workers
            )
        else:
            dataset = self._process_pairs_sequential(
                rider_competition_pairs, rider_results, cutoff_date
            )
        
        return dataset
    
    def _preload_rider_histories(self, rider_ids: List[int], cutoff_date: Optional[str]):
        """Pre-load all rider histories to avoid repeated queries."""
        if not rider_ids:
            return
            
        conn = sqlite3.connect(self.db_path)
        try:
            placeholders = ','.join('?' * len(rider_ids))
            params = rider_ids.copy()
            
            # Build query with optional date filter
            query = f"""
            SELECT 
                rr.rider_id,
                rr.competition_id,
                c.date as competition_date,
                c.competition_type,
                r.category as race_category,
                rr.place,
                rr.time_gap,
                rr.percentile,
                rr.rider_age
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            WHERE rr.rider_id IN ({placeholders})
            """
            
            if cutoff_date:
                query += " AND c.date <= ?"
                params.append(cutoff_date)
            
            query += " ORDER BY rr.rider_id, c.date"
            
            df = pd.read_sql_query(query, conn, params=params)
            
            # Group by rider and store
            for rider_id, rider_data in df.groupby('rider_id'):
                self._rider_histories[rider_id] = rider_data.sort_values('competition_date')
                
        finally:
            conn.close()
    
    def _preload_competition_features(self, competition_ids: List[int]):
        """Pre-load all competition features in batch."""
        if not competition_ids:
            return
            
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            placeholders = ','.join('?' * len(competition_ids))
            
            # Get basic competition info
            basic_query = f"""
            SELECT 
                c.id as competition_id,
                c.name as competition_name,
                c.competition_type,
                c.date as competition_date,
                r.name as race_name,
                r.category as race_category,
                r.year as race_year,
                r.fc_race_id
            FROM competitions c
            JOIN races r ON c.race_id = r.id
            WHERE c.id IN ({placeholders})
            """
            
            basic_df = pd.read_sql_query(basic_query, conn, params=competition_ids)
            
            # Get race features for each competition type
            gc_competitions = basic_df[basic_df['competition_type'] == 'gc']['competition_id'].tolist()
            stage_one_day_competitions = basic_df[
                basic_df['competition_type'].isin(['stage', 'one_day'])
            ]['competition_id'].tolist()
            
            # Get race features from appropriate tables
            race_features = {}
            
            if gc_competitions:
                race_features.update(self._get_race_features_batch(gc_competitions, 'race_features_70'))
            
            if stage_one_day_competitions:
                race_features.update(self._get_race_features_batch(stage_one_day_competitions, 'race_features_40'))
            
            # Get race kind features
            race_kind_features = self._get_race_kind_features_batch(competition_ids)
            
            # Combine all features
            for _, row in basic_df.iterrows():
                comp_id = row['competition_id']
                self._competition_features[comp_id] = {
                    **dict(row),
                    'race_features': race_features.get(comp_id, {}),
                    'race_kind_features': race_kind_features.get(comp_id, {})
                }
            
        finally:
            conn.close()
    
    def _get_race_features_batch(self, competition_ids: List[int], table_name: str) -> Dict[int, Dict]:
        """Get race features for multiple competitions from specific table."""
        if not competition_ids:
            return {}
            
        conn = sqlite3.connect(self.db_path)
        try:
            # Get feature column names from config
            feature_info = self.result_features.get_feature_info()
            if table_name == 'race_features_70':
                feature_cols = feature_info['gc_features']
            else:
                feature_cols = feature_info['stage_features']
            
            if not feature_cols:
                return {}
            
            # Quote column names and build query
            quoted_cols = [f'"{col}"' for col in feature_cols]
            placeholders = ','.join('?' * len(competition_ids))
            
            query = f"""
            SELECT competition_id, {', '.join(quoted_cols)}
            FROM {table_name}
            WHERE competition_id IN ({placeholders})
            """
            
            cursor = conn.cursor()
            cursor.execute(query, competition_ids)
            
            results = {}
            for row in cursor.fetchall():
                comp_id = row[0]
                features = dict(zip(feature_cols, row[1:]))
                results[comp_id] = features
            
            return results
            
        finally:
            conn.close()
    
    def _get_race_kind_features_batch(self, competition_ids: List[int]) -> Dict[int, Dict]:
        """Get race kind features for multiple competitions."""
        if not competition_ids:
            return {}
            
        conn = sqlite3.connect(self.db_path)
        try:
            # Get race kind feature columns from config
            feature_info = self.result_features.get_feature_info()
            race_kind_cols = feature_info['race_kind_features']
            
            if not race_kind_cols:
                return {}
            
            # Check which columns actually exist
            cursor = conn.cursor()
            table_name = self.result_features.config['metadata']['table_name']
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_columns = {row[1] for row in cursor.fetchall()}
            
            columns_to_query = [col for col in race_kind_cols if col in existing_columns]
            
            if not columns_to_query:
                return {}
            
            # Quote column names and build query
            quoted_cols = [f'"{col}"' for col in columns_to_query]
            placeholders = ','.join('?' * len(competition_ids))
            
            query = f"""
            SELECT competition_id, {', '.join(quoted_cols)}
            FROM {table_name}
            WHERE competition_id IN ({placeholders})
            """
            
            cursor.execute(query, competition_ids)
            
            results = {}
            for row in cursor.fetchall():
                comp_id = row[0]
                features = dict(zip(columns_to_query, row[1:]))
                results[comp_id] = features
            
            return results
            
        finally:
            conn.close()
    
    def _preload_rider_results(self, pairs: List[Tuple[int, int]]) -> Dict[Tuple[int, int], Dict]:
        """Pre-load all rider results for the given pairs."""
        if not pairs:
            return {}
            
        conn = sqlite3.connect(self.db_path)
        try:
            # Create temporary table for pairs
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TEMP TABLE pair_lookup (
                rider_id INTEGER,
                competition_id INTEGER,
                PRIMARY KEY (rider_id, competition_id)
            )
            """)
            
            # Insert pairs
            cursor.executemany(
                "INSERT INTO pair_lookup (rider_id, competition_id) VALUES (?, ?)",
                pairs
            )
            
            # Query results for all pairs at once
            query = """
            SELECT 
                pl.rider_id,
                pl.competition_id,
                rr.place,
                rr.time_gap,
                rr.percentile,
                rr.rider_age
            FROM pair_lookup pl
            JOIN rider_results rr ON pl.rider_id = rr.rider_id 
                                 AND pl.competition_id = rr.competition_id
            """
            
            cursor.execute(query)
            results = {}
            
            for row in cursor.fetchall():
                key = (row[0], row[1])  # (rider_id, competition_id)
                results[key] = {
                    'place': row[2],
                    'time_gap': row[3],
                    'percentile': row[4],
                    'rider_age': row[5]
                }
            
            return results
            
        finally:
            conn.close()
    
    def _process_pairs_parallel(self, pairs: List[Tuple[int, int]], 
                               rider_results: Dict, cutoff_date: Optional[str],
                               max_workers: int = None) -> pd.DataFrame:
        """Process pairs in parallel batches."""
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 8)
        
        # Split pairs into batches
        batch_size = max(50, len(pairs) // max_workers)
        batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]
        
        print(f"Processing {len(batches)} batches with {max_workers} workers...")
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._process_batch, batch, rider_results, cutoff_date)
                for batch in batches
            ]
            
            for i, future in enumerate(as_completed(futures)):
                batch_result = future.result()
                if batch_result is not None and not batch_result.empty:
                    results.append(batch_result)
                print(f"Completed batch {i+1}/{len(batches)}")
        
        # Filter out empty DataFrames before concatenating
        non_empty_results = [df for df in results if not df.empty]
        if non_empty_results:
            # Use concat with explicit handling of empty/NA columns
            return pd.concat(non_empty_results, ignore_index=True, sort=False)
        else:
            return pd.DataFrame()
    
    def _process_pairs_sequential(self, pairs: List[Tuple[int, int]], 
                                 rider_results: Dict, cutoff_date: Optional[str]) -> pd.DataFrame:
        """Process pairs sequentially."""
        return self._process_batch(pairs, rider_results, cutoff_date)
    
    def _process_batch(self, batch: List[Tuple[int, int]], 
                      rider_results: Dict, cutoff_date: Optional[str]) -> pd.DataFrame:
        """Process a batch of pairs."""
        from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points
        
        results = []
        
        for rider_id, competition_id in batch:
            # Get competition info
            comp_info = self._competition_features.get(competition_id)
            if not comp_info:
                continue
            
            # Get rider result
            rider_result = rider_results.get((rider_id, competition_id))
            if not rider_result:
                continue
            
            # Calculate experience features
            experience_features = self._calculate_experience_features(
                rider_id, comp_info['competition_date'], cutoff_date
            )
            
            # Calculate UCI points
            try:
                uci_actual = get_actual_uci_place_points(
                    rider_result['place'], comp_info['competition_type'], 
                    comp_info['race_category'], comp_info['fc_race_id']
                )
                uci_proportional = get_top_tier_based_points(
                    rider_result['place'], comp_info['competition_type'], 
                    comp_info['race_category'], comp_info['fc_race_id']
                )
            except (ValueError, KeyError):
                uci_actual = uci_proportional = 0
            
            # Combine all features
            result = {
                'rider_id': rider_id,
                'competition_id': competition_id,
                'competition_name': comp_info['competition_name'],
                'competition_type': comp_info['competition_type'],
                'race_name': comp_info['race_name'],
                'race_category': comp_info['race_category'],
                'race_year': comp_info['race_year'],
                'competition_date': comp_info['competition_date'],
                'place': rider_result['place'],
                'time_gap': rider_result['time_gap'],
                'percentile': rider_result['percentile'],
                'rider_age': rider_result['rider_age'],
                'uci_points_actual': uci_actual,
                'uci_points_proportional': uci_proportional,
                **experience_features
            }
            
            # Add race features
            for key, value in comp_info['race_features'].items():
                result[f'rf_{key}'] = value
            
            # Add race kind features
            for key, value in comp_info['race_kind_features'].items():
                result[f'rkf_{key}'] = value
            
            results.append(result)
        
        return pd.DataFrame(results) if results else pd.DataFrame()
    
    def _calculate_experience_features(self, rider_id: int, 
                                     competition_date: str, cutoff_date: Optional[str]) -> Dict:
        """Calculate experience features from cached rider history."""
        rider_history = self._rider_histories.get(rider_id)
        if rider_history is None or len(rider_history) == 0:
            return self._get_zero_experience_features()
        
        # Filter to races before this competition
        prior_races = rider_history[rider_history['competition_date'] < competition_date]
        
        # Apply cutoff if specified
        if cutoff_date:
            prior_races = prior_races[prior_races['competition_date'] <= cutoff_date]
        
        if len(prior_races) == 0:
            return self._get_zero_experience_features()
        
        # Calculate metrics
        total_prior = len(prior_races)
        
        return {
            'total_prior_races': total_prior,
            'prior_gc_races': len(prior_races[prior_races['competition_type'] == 'gc']),
            'prior_stage_races': len(prior_races[prior_races['competition_type'] == 'stage']),
            'prior_one_day_races': len(prior_races[prior_races['competition_type'] == 'one_day']),
            'prior_wt_races': len(prior_races[prior_races['race_category'] == 'wt']),
            'prior_pro_races': len(prior_races[prior_races['race_category'] == 'pro']),
            'prior_d1_races': len(prior_races[prior_races['race_category'] == 'd1']),
            'prior_wt_proportion': len(prior_races[prior_races['race_category'] == 'wt']) / total_prior,
            'total_prior_uci_points_actual': 0,  # Would need to calculate from history
            'total_prior_uci_points_proportional': 0,
            'rider_age_at_race': prior_races.iloc[-1]['rider_age'] if len(prior_races) > 0 else 0
        }
    
    def _get_zero_experience_features(self) -> Dict:
        """Get zero experience features for first-time riders."""
        return {
            'total_prior_races': 0,
            'prior_gc_races': 0,
            'prior_stage_races': 0,
            'prior_one_day_races': 0,
            'prior_wt_races': 0,
            'prior_pro_races': 0,
            'prior_d1_races': 0,
            'prior_wt_proportion': 0.0,
            'total_prior_uci_points_actual': 0,
            'total_prior_uci_points_proportional': 0,
            'rider_age_at_race': 0
        }


if __name__ == "__main__":
    # Test the optimized feature builder
    import sqlite3
    
    db_path = "database/database/cycling_races.db"
    
    # Get some test pairs
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT DISTINCT rr.rider_id, rr.competition_id
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    WHERE c.date BETWEEN '2011-01-01' AND '2011-03-31'
    LIMIT 100
    """)
    test_pairs = [(row[0], row[1]) for row in cursor.fetchall()]
    conn.close()
    
    print(f"Testing with {len(test_pairs)} pairs...")
    
    # Test optimized builder
    import time
    start_time = time.time()
    
    builder = OptimizedFeatureBuilder(db_path)
    result = builder.build_bulk_dataset_fast(
        test_pairs, 
        cutoff_date="2010-12-31",
        use_parallel=True
    )
    
    elapsed = time.time() - start_time
    print(f"Optimized builder completed in {elapsed:.2f} seconds")
    print(f"Generated {len(result)} feature vectors")
    
    if len(result) > 0:
        print(f"Columns: {list(result.columns)}")
        print(f"Sample data:")
        print(result.head(2))