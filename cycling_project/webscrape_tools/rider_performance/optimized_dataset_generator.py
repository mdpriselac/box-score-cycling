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
    
    def __init__(self, db_path: str, use_enhanced_experience: bool = True):
        self.db_path = db_path
        self.result_features = RiderResultFeatures(db_path)
        self.use_enhanced_experience = use_enhanced_experience
        
        # Experience features are now pre-computed in the database
        self.experience_feature_names = self._get_experience_feature_names_from_db()
        
        # Cache for rider histories (no longer needed for enhanced features)
        self._rider_histories = {}
    
    def _get_experience_feature_names_from_db(self) -> List[str]:
        """Dynamically get experience feature names from the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(rider_results)")
            columns = cursor.fetchall()
            
            # Find columns that are experience features (added by the migration)
            experience_columns = []
            for column in columns:
                col_name = column[1]  # Column name is at index 1
                if (col_name.startswith('prior_') or 
                    col_name.startswith('total_prior_') or
                    col_name == 'rider_age' or
                    col_name.endswith('_success_rate')):
                    experience_columns.append(col_name)
            
            # Add calculated features that we derive from the base data
            calculated_features = ['overall_success_rate', 'prior_wt_success_rate', 
                                 'prior_gc_success_rate', 'prior_stage_success_rate', 
                                 'prior_one_day_success_rate']
            
            # Combine and return unique features
            all_features = list(set(experience_columns + calculated_features))
            return sorted(all_features)
            
        finally:
            conn.close()
    
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
        
        # Step 2: Experience features are now pre-computed in database
        # No need to pre-calculate rider histories for experience features
        
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
        if dataset.empty:
            print("No data found - returning empty datasets")
            return {
                'gc_dataset': pd.DataFrame(),
                'stage_one_day_dataset': pd.DataFrame()
            }
        
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
                rider_id, competition_id, comp_info['competition_date']
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
                                     competition_id: int, competition_date: str) -> Dict:
        """Get experience features from pre-computed database values."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get pre-computed experience features directly from database
            query = """
            SELECT 
                prior_wt_points_actual, prior_wt_points_proportional,
                prior_pro_points_actual, prior_pro_points_proportional,
                prior_d1_points_actual, prior_d1_points_proportional,
                prior_gc_points_actual, prior_gc_points_proportional,
                prior_stage_points_actual, prior_stage_points_proportional,
                prior_one_day_points_actual, prior_one_day_points_proportional,
                prior_wt_races, prior_pro_races, prior_d1_races,
                prior_gc_races, prior_stage_races, prior_one_day_races,
                total_prior_races, total_prior_points_actual,
                total_prior_points_proportional, prior_wt_proportion,
                rider_age
            FROM rider_results
            WHERE rider_id = ? AND competition_id = ?
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, competition_id))
            row = cursor.fetchone()
            
            if row:
                # Map database columns to feature names
                experience_features = {
                    'prior_wt_points_actual': row[0],
                    'prior_wt_points_proportional': row[1],
                    'prior_pro_points_actual': row[2],
                    'prior_pro_points_proportional': row[3],
                    'prior_d1_points_actual': row[4],
                    'prior_d1_points_proportional': row[5],
                    'prior_gc_points_actual': row[6],
                    'prior_gc_points_proportional': row[7],
                    'prior_stage_points_actual': row[8],
                    'prior_stage_points_proportional': row[9],
                    'prior_one_day_points_actual': row[10],
                    'prior_one_day_points_proportional': row[11],
                    'prior_wt_races': row[12],
                    'prior_pro_races': row[13],
                    'prior_d1_races': row[14],
                    'prior_gc_races': row[15],
                    'prior_stage_races': row[16],
                    'prior_one_day_races': row[17],
                    'total_prior_races': row[18],
                    'total_prior_points_actual': row[19],
                    'total_prior_points_proportional': row[20],
                    'prior_wt_proportion': row[21],
                    'rider_age': row[22]
                }
                
                # Calculate success rates from the base data
                total_races = experience_features['total_prior_races']
                if total_races > 0:
                    experience_features['overall_success_rate'] = (
                        1.0 if experience_features['total_prior_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_wt_success_rate'] = (
                        1.0 if experience_features['prior_wt_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_gc_success_rate'] = (
                        1.0 if experience_features['prior_gc_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_stage_success_rate'] = (
                        1.0 if experience_features['prior_stage_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_one_day_success_rate'] = (
                        1.0 if experience_features['prior_one_day_points_actual'] > 0 else 0.0
                    )
                else:
                    experience_features['overall_success_rate'] = 0.0
                    experience_features['prior_wt_success_rate'] = 0.0
                    experience_features['prior_gc_success_rate'] = 0.0
                    experience_features['prior_stage_success_rate'] = 0.0
                    experience_features['prior_one_day_success_rate'] = 0.0
                
                return experience_features
            else:
                # No result found - return zero features
                return self._get_zero_experience_features()
                
        finally:
            conn.close()
    
    def _get_zero_experience_features(self) -> Dict:
        """Get zero experience features for first-time riders."""
        zero_features = {}
        for feature_name in self.experience_feature_names:
            # Special handling for proportion/rate features (should be 0.0)
            if 'proportion' in feature_name or 'rate' in feature_name:
                zero_features[feature_name] = 0.0
            else:
                zero_features[feature_name] = 0
        return zero_features


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