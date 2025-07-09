"""
Optimized dataset generator that pre-calculates rider histories and processes in batches.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

from rider_result_features import RiderResultFeatures
from enhanced_rider_experience import EnhancedRiderExperience


class OptimizedDatasetGenerator:
    """Fast dataset generator using batch processing and caching."""
    
    def __init__(self, db_path: str, use_enhanced_experience: bool = False):
        self.db_path = db_path
        self.result_features = RiderResultFeatures(db_path)
        self.use_enhanced_experience = use_enhanced_experience
        
        # Initialize enhanced experience calculator if requested
        if self.use_enhanced_experience:
            self.enhanced_experience = EnhancedRiderExperience()
        
        # Cache for rider histories
        self._rider_histories = {}
        self._rider_experience_cache = {}
    
    def generate_datasets_fast(self, 
                              cutoff_date: str,
                              min_results: int = 10,
                              target_variable: str = 'uci_points_actual',
                              use_parallel: bool = True,
                              max_workers: int = None) -> Dict[str, pd.DataFrame]:
        """
        Generate datasets using optimized batch processing.
        
        Args:
            cutoff_date: Training data cutoff
            min_results: Minimum results per rider
            target_variable: Target variable to use
            use_parallel: Whether to use parallel processing
            max_workers: Number of parallel workers (None = auto)
            
        Returns:
            Dictionary with gc_dataset and stage_one_day_dataset
        """
        print(f"Generating datasets with optimized approach...")
        
        # Step 1: Get all relevant pairs in one query
        pairs = self._get_all_pairs_batch(cutoff_date, min_results)
        print(f"Found {len(pairs)} rider-competition pairs")
        
        # Step 2: Pre-calculate all rider histories
        unique_riders = list(set(pair[0] for pair in pairs))
        print(f"Pre-calculating histories for {len(unique_riders)} riders...")
        self._precompute_rider_histories(unique_riders, cutoff_date)
        
        # Step 3: Get all competition features in batch
        print("Loading competition features...")
        competition_features = self._get_competition_features_batch(pairs)
        
        # Step 4: Process pairs in batches
        print("Building feature matrix...")
        if use_parallel and len(pairs) > 1000:
            dataset = self._process_pairs_parallel(pairs, competition_features, 
                                                 cutoff_date, max_workers)
        else:
            dataset = self._process_pairs_sequential(pairs, competition_features, cutoff_date)
        
        # Step 5: Split by competition type
        gc_dataset = dataset[dataset['competition_type'] == 'gc'].copy()
        stage_one_day_dataset = dataset[
            dataset['competition_type'].isin(['stage', 'one_day'])
        ].copy()
        
        print(f"Final datasets: {len(gc_dataset)} GC, {len(stage_one_day_dataset)} Stage/One-day")
        
        return {
            'gc_dataset': gc_dataset,
            'stage_one_day_dataset': stage_one_day_dataset
        }
    
    def _get_all_pairs_batch(self, cutoff_date: str, min_results: int) -> List[Tuple[int, int]]:
        """Get all rider-competition pairs in a single query."""
        conn = sqlite3.connect(self.db_path)
        try:
            query = """
            WITH qualified_riders AS (
                SELECT rider_id
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date <= ?
                GROUP BY rider_id
                HAVING COUNT(*) >= ?
            )
            SELECT DISTINCT rr.rider_id, rr.competition_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN qualified_riders qr ON rr.rider_id = qr.rider_id
            WHERE c.date <= ?
            ORDER BY rr.rider_id, c.date
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_date, min_results, cutoff_date))
            return [(row[0], row[1]) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def _precompute_rider_histories(self, rider_ids: List[int], cutoff_date: str):
        """Pre-compute all rider histories to avoid repeated queries."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get all rider results in one query
            placeholders = ','.join('?' * len(rider_ids))
            
            if self.use_enhanced_experience:
                # Include additional columns needed for enhanced experience features
                query = f"""
                SELECT 
                    rr.rider_id,
                    rr.competition_id,
                    rr.id as result_id,
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
                AND c.date <= ?
                ORDER BY rr.rider_id, c.date
                """
            else:
                # Basic query for simple experience features
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
                AND c.date <= ?
                ORDER BY rr.rider_id, c.date
                """
            
            df = pd.read_sql_query(query, conn, params=rider_ids + [cutoff_date])
            
            # Group by rider and store
            for rider_id, rider_data in df.groupby('rider_id'):
                self._rider_histories[rider_id] = rider_data.sort_values('competition_date')
                
        finally:
            conn.close()
    
    def _get_competition_features_batch(self, pairs: List[Tuple[int, int]]) -> Dict[int, Dict]:
        """Get all competition features in batch queries."""
        competition_ids = list(set(pair[1] for pair in pairs))
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # Get basic competition info
            placeholders = ','.join('?' * len(competition_ids))
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
            competition_features = {}
            for _, row in basic_df.iterrows():
                comp_id = row['competition_id']
                competition_features[comp_id] = {
                    **dict(row),
                    'race_features': race_features.get(comp_id, {}),
                    'race_kind_features': race_kind_features.get(comp_id, {})
                }
            
            return competition_features
            
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
    
    def _process_pairs_parallel(self, pairs: List[Tuple[int, int]], 
                               competition_features: Dict, cutoff_date: str,
                               max_workers: int = None) -> pd.DataFrame:
        """Process pairs in parallel batches."""
        if max_workers is None:
            max_workers = min(multiprocessing.cpu_count(), 8)
        
        # Split pairs into batches
        batch_size = max(100, len(pairs) // max_workers)
        batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]
        
        print(f"Processing {len(batches)} batches with {max_workers} workers...")
        
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._process_batch, batch, competition_features, cutoff_date)
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
                                 competition_features: Dict, cutoff_date: str) -> pd.DataFrame:
        """Process pairs sequentially."""
        return self._process_batch(pairs, competition_features, cutoff_date)
    
    def _process_batch(self, batch: List[Tuple[int, int]], 
                      competition_features: Dict, cutoff_date: str) -> pd.DataFrame:
        """Process a batch of pairs."""
        from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points
        
        results = []
        
        for rider_id, competition_id in batch:
            # Get competition info
            comp_info = competition_features.get(competition_id)
            if not comp_info:
                continue
            
            # Get rider result for this competition
            rider_result = self._get_rider_result(rider_id, competition_id)
            if rider_result is None:
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
    
    def _get_rider_result(self, rider_id: int, competition_id: int) -> Dict:
        """Get rider result for specific competition."""
        conn = sqlite3.connect(self.db_path)
        try:
            query = """
            SELECT place, time_gap, percentile, rider_age
            FROM rider_results
            WHERE rider_id = ? AND competition_id = ?
            """
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, competition_id))
            row = cursor.fetchone()
            
            if row:
                return {
                    'place': row[0],
                    'time_gap': row[1],
                    'percentile': row[2],
                    'rider_age': row[3]
                }
            return None
        finally:
            conn.close()
    
    def _calculate_experience_features(self, rider_id: int, 
                                     competition_date: str, cutoff_date: str) -> Dict:
        """Calculate experience features from cached rider history."""
        rider_history = self._rider_histories.get(rider_id)
        if rider_history is None or len(rider_history) == 0:
            return self._get_zero_experience_features()
        
        # Filter to races before this competition
        prior_races = rider_history[rider_history['competition_date'] < competition_date]
        
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
    # Test the optimized generator
    db_path = "database/database/cycling_races.db"
    
    # Compare timing
    import time
    
    print("Testing optimized dataset generation...")
    start_time = time.time()
    
    generator = OptimizedDatasetGenerator(db_path)
    datasets = generator.generate_datasets_fast(
        cutoff_date="2010-12-31",
        min_results=60,
        target_variable='uci_points_actual',
        use_parallel=True
    )
    
    elapsed = time.time() - start_time
    print(f"Generated datasets in {elapsed:.2f} seconds")
    print(f"GC dataset: {len(datasets['gc_dataset'])} rows")
    print(f"Stage/One-day dataset: {len(datasets['stage_one_day_dataset'])} rows")