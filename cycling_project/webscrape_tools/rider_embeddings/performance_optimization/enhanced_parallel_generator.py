import multiprocessing as mp
import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json
from tqdm import tqdm
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed, ThreadPoolExecutor
import sys
import time
import pickle

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from rider_embeddings.performance_optimization.parallel_correlation_generator import ParallelCorrelationGenerator
from rider_embeddings.performance_optimization.batched_database_loader import BatchedDatabaseLoader
from rider_embeddings.performance_optimization.optimized_race_type_calculator import OptimizedRaceTypeCorrelationCalculator


def process_rider_chunk_with_shared_data(chunk_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Enhanced worker function that uses pre-loaded shared data.
    
    Args:
        chunk_data: Dictionary containing:
            - rider_result_data: List of (rider_result_id, competition_date) tuples
            - feature_tables: List of feature tables to analyze
            - calculator_config: Configuration for the correlation calculator
            - shared_data: Pre-loaded rider histories and race features
            - chunk_id: ID for this chunk
    
    Returns:
        List of correlation results
    """
    rider_result_data = chunk_data['rider_result_data']
    feature_tables = chunk_data['feature_tables']
    calculator_config = chunk_data['calculator_config']
    shared_data = chunk_data.get('shared_data', {})
    chunk_id = chunk_data.get('chunk_id', 'unknown')
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format=f'Worker-{chunk_id}: %(message)s')
    logger = logging.getLogger(f'worker_{chunk_id}')
    
    try:
        logger.info(f"Processing chunk with {len(rider_result_data)} riders using shared data")
        
        results = []
        successful = 0
        failed = 0
        
        for rider_result_id, competition_date in rider_result_data:
            try:
                # Use shared data to calculate correlations
                result = calculate_correlations_from_shared_data(
                    rider_result_id,
                    feature_tables,
                    shared_data,
                    calculator_config
                )
                results.append(result)
                successful += 1
                
            except Exception as e:
                failed += 1
                error_result = {
                    'rider_result_id': rider_result_id,
                    'feature_correlations': {},
                    'metadata': {
                        'n_races': {},
                        'method': 'enhanced_race_type_correlation',
                        'calculation_date': datetime.now(),
                        'warnings': [f"Error processing rider {rider_result_id}: {str(e)}"],
                        'error': str(e)
                    }
                }
                results.append(error_result)
        
        logger.info(f"Chunk complete: {successful} successful, {failed} failed")
        return results
        
    except Exception as e:
        logger.error(f"Chunk processing failed: {e}")
        return []


def calculate_correlations_from_shared_data(
    rider_result_id: int,
    feature_tables: List[str],
    shared_data: Dict[str, Any],
    calculator_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate correlations using pre-loaded shared data.
    
    Args:
        rider_result_id: The rider result ID
        feature_tables: List of feature tables to analyze
        shared_data: Pre-loaded rider histories and race features
        calculator_config: Calculator configuration
    
    Returns:
        Correlation results dictionary
    """
    from scipy import stats
    import warnings
    
    # Get rider history from shared data
    rider_histories = shared_data.get('rider_histories', {})
    race_features = shared_data.get('race_features', {})
    
    full_history = rider_histories.get(rider_result_id, [])
    if not full_history:
        return {
            'rider_result_id': rider_result_id,
            'feature_correlations': {},
            'metadata': {
                'n_races': {},
                'method': 'enhanced_race_type_correlation',
                'calculation_date': datetime.now(),
                'warnings': ['No historical data found']
            }
        }
    
    # Race type definitions
    RACE_TYPES = {
        'gc': ['gc'],
        'stage': ['stage'],
        'one_day': ['one_day'],
        'stage_one_day': ['stage', 'one_day'],
        'all': ['gc', 'stage', 'one_day']
    }
    
    # Minimum races configuration
    min_races = {
        'gc': calculator_config.get('min_races_gc', 10),
        'stage': calculator_config.get('min_races_stage', 25),
        'one_day': calculator_config.get('min_races_one_day', 15),
        'stage_one_day': calculator_config.get('min_races_one_day', 15),
        'all': calculator_config.get('min_races_all', 35)
    }
    
    # Segment history by race type
    race_type_histories = {}
    for race_type, competition_types in RACE_TYPES.items():
        if race_type == 'all':
            race_type_histories[race_type] = full_history
        else:
            race_type_histories[race_type] = [
                h for h in full_history 
                if h['competition_type'] in competition_types
            ]
    
    # Calculate correlations for each race type
    feature_correlations = {}
    warnings_list = []
    race_counts = {}
    
    for race_type, history in race_type_histories.items():
        race_counts[race_type] = len(history)
        
        # Check if enough history
        if len(history) < min_races[race_type]:
            warnings_list.append(
                f"{race_type}: Insufficient history - {len(history)} races "
                f"(minimum {min_races[race_type]} required)"
            )
            continue
        
        # Calculate correlations for each feature table
        race_type_correlations = {}
        for feature_table in feature_tables:
            correlations = calculate_correlations_for_history(
                history, 
                race_features.get(feature_table, {}),
                min_races[race_type]
            )
            race_type_correlations[feature_table] = correlations
        
        feature_correlations[race_type] = race_type_correlations
    
    return {
        'rider_result_id': rider_result_id,
        'feature_correlations': feature_correlations,
        'metadata': {
            'n_races': race_counts,
            'method': 'enhanced_race_type_correlation',
            'calculation_date': datetime.now(),
            'warnings': warnings_list
        }
    }


def calculate_correlations_for_history(
    history: List[Dict[str, Any]], 
    features_data: Dict[int, Dict[str, float]],
    min_races_required: int
) -> Dict[str, float]:
    """Calculate correlations for a race history and feature data."""
    from scipy import stats
    import warnings
    
    # Get competition IDs
    competition_ids = [h['competition_id'] for h in history]
    
    # Filter history to races with feature data
    valid_history = [h for h in history if h['competition_id'] in features_data]
    
    if len(valid_history) < min_races_required:
        return {}
    
    # Extract points
    points = np.array([h['uci_points_proportional'] for h in valid_history])
    
    if np.std(points) == 0:
        return {}
    
    # Get feature names
    feature_names = set()
    if valid_history:
        first_comp_id = valid_history[0]['competition_id']
        if first_comp_id in features_data:
            feature_names = set(features_data[first_comp_id].keys())
    
    correlations = {}
    
    for feature_name in feature_names:
        # Extract feature values
        feature_values = []
        for h in valid_history:
            comp_id = h['competition_id']
            value = features_data[comp_id].get(feature_name)
            feature_values.append(value if value is not None else np.nan)
        
        feature_array = np.array(feature_values)
        
        # Calculate correlation
        if np.sum(~np.isnan(feature_array)) >= min_races_required:
            valid_mask = ~(np.isnan(feature_array) | np.isnan(points))
            valid_points = points[valid_mask]
            valid_features = feature_array[valid_mask]
            
            if (len(valid_features) >= min_races_required and 
                np.std(valid_features) > 1e-10 and 
                np.std(valid_points) > 1e-10):
                
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    corr, _ = stats.spearmanr(valid_points, valid_features)
                
                correlations[feature_name] = float(corr) if not np.isnan(corr) else None
            else:
                correlations[feature_name] = None
        else:
            correlations[feature_name] = None
    
    return correlations


class EnhancedParallelCorrelationGenerator(ParallelCorrelationGenerator):
    """
    Enhanced parallel correlation generator that pre-loads all data once
    and shares it efficiently across workers.
    """
    
    def __init__(
        self,
        db_path: str,
        output_dir: str = "correlation_data",
        batch_size: int = 100,
        min_races: int = 5,
        n_workers: int = None,
        preload_all_data: bool = True
    ):
        """
        Initialize the enhanced parallel correlation generator.
        
        Args:
            db_path: Path to the cycling database
            output_dir: Directory to save parquet files
            batch_size: Number of rider results to process per batch
            min_races: Minimum races required for correlation calculation
            n_workers: Number of worker processes
            preload_all_data: Whether to preload all data before processing
        """
        super().__init__(
            db_path=db_path,
            output_dir=output_dir,
            batch_size=batch_size,
            min_races=min_races,
            n_workers=n_workers,
            use_batched_loading=preload_all_data
        )
        self.preload_all_data = preload_all_data
    
    def generate_sample_parallel_enhanced(
        self,
        sample_size: int = 1000,
        feature_tables: List[str] = None,
        output_name: str = "enhanced_parallel_sample",
        calculator_config: Dict[str, Any] = None
    ) -> None:
        """
        Generate correlations using enhanced parallel processing with shared data.
        
        Args:
            sample_size: Number of rider results to sample
            feature_tables: List of feature tables to analyze
            output_name: Name for output file
            calculator_config: Configuration for the correlation calculator
        """
        if feature_tables is None:
            feature_tables = ['race_features_80', 'race_features_100']
        
        if calculator_config is None:
            calculator_config = {
                'type': 'race_type',
                'min_races_all': 25,
                'min_races_stage': 15,
                'min_races_one_day': 10,
                'min_races_gc': 8
            }
        
        self.logger.info(f"Generating enhanced parallel sample for {sample_size} rider results")
        
        # Step 1: Get sample rider results using optimized two-step approach
        self.logger.info("Step 1: Getting sample rider results...")
        sample_start = time.time()
        
        sample_results = self._get_sample_rider_results_optimized(sample_size)
        
        if not sample_results:
            self.logger.error("No eligible rider results found")
            return
        
        rider_result_ids = [r[0] for r in sample_results]
        sample_time = time.time() - sample_start
        
        self.logger.info(f"Step 1 complete: {len(sample_results)} rider results in {sample_time:.2f}s")
        
        # Step 2: Pre-load all data
        if self.preload_all_data:
            self.logger.info("Step 2: Pre-loading all rider histories and race features...")
            preload_start = time.time()
            
            loader = BatchedDatabaseLoader(self.db_path)
            loader.preload_all_data(rider_result_ids, feature_tables)
            
            # Prepare shared data structure
            shared_data = {
                'rider_histories': {},
                'race_features': {}
            }
            
            # Extract rider histories
            for rider_result_id in rider_result_ids:
                history = loader.get_cached_rider_history(rider_result_id)
                shared_data['rider_histories'][rider_result_id] = history
            
            # Extract race features
            for feature_table in feature_tables:
                # Get all competition IDs
                all_comp_ids = set()
                for history in shared_data['rider_histories'].values():
                    all_comp_ids.update(h['competition_id'] for h in history)
                
                features = loader.get_cached_race_features(list(all_comp_ids), feature_table)
                shared_data['race_features'][feature_table] = features
            
            preload_time = time.time() - preload_start
            stats = loader.get_cache_stats()
            
            self.logger.info(f"Step 2 complete: Preloaded data in {preload_time:.2f}s")
            self.logger.info(f"  - {stats['rider_results_cached']} rider histories")
            self.logger.info(f"  - {stats['total_historical_races']} total races")
            self.logger.info(f"  - {len(feature_tables)} feature tables")
            
            loader.clear_cache()  # Free the loader's cache
        else:
            shared_data = {}
            preload_time = 0
        
        # Step 3: Process in parallel with shared data
        self.logger.info("Step 3: Processing correlations in parallel...")
        processing_start = time.time()
        
        # Split into chunks
        chunk_size = max(1, len(sample_results) // self.n_workers)
        sample_chunks = [
            sample_results[i:i+chunk_size] 
            for i in range(0, len(sample_results), chunk_size)
        ]
        
        all_results = []
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all chunks
            future_to_chunk = {}
            for i, chunk in enumerate(sample_chunks):
                chunk_data = {
                    'rider_result_data': chunk,
                    'feature_tables': feature_tables,
                    'calculator_config': calculator_config,
                    'shared_data': shared_data,
                    'chunk_id': i
                }
                
                if self.preload_all_data:
                    # Use enhanced worker with shared data
                    future = executor.submit(process_rider_chunk_with_shared_data, chunk_data)
                else:
                    # Fall back to original worker
                    from rider_embeddings.performance_optimization.parallel_correlation_generator import process_rider_chunk
                    future = executor.submit(process_rider_chunk, chunk_data)
                
                future_to_chunk[future] = i
            
            # Collect results
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                try:
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
                except Exception as e:
                    self.logger.error(f"Enhanced chunk {chunk_id} failed: {e}")
        
        processing_time = time.time() - processing_start
        total_time = sample_time + preload_time + processing_time
        
        # Step 4: Save results
        self.logger.info("Step 4: Saving results...")
        
        successful_results = [r for r in all_results if r.get('feature_correlations')]
        
        self.logger.info(f"Enhanced parallel processing complete!")
        self.logger.info(f"  - Sample time: {sample_time:.2f}s")
        self.logger.info(f"  - Preload time: {preload_time:.2f}s") 
        self.logger.info(f"  - Processing time: {processing_time:.2f}s")
        self.logger.info(f"  - Total time: {total_time:.2f}s")
        self.logger.info(f"  - Success rate: {len(successful_results)}/{len(sample_results)}")
        
        if processing_time > 0:
            self.logger.info(f"  - Processing rate: {len(successful_results)/processing_time:.2f} riders/second")
        
        # Save data
        if successful_results:
            all_data = []
            for result in successful_results:
                flat_result = self._flatten_correlation_result(result)
                all_data.extend(flat_result)
            
            df = pd.DataFrame(all_data)
            output_file = self.output_dir / f"{output_name}_correlations.parquet"
            df.to_parquet(output_file, compression='snappy')
            
            # Save metadata
            metadata = {
                'type': 'enhanced_parallel_sample',
                'sample_size': sample_size,
                'successful_riders': len(successful_results),
                'total_records': len(df),
                'feature_tables': feature_tables,
                'generation_date': datetime.now().isoformat(),
                'timing': {
                    'sample_time': sample_time,
                    'preload_time': preload_time,
                    'processing_time': processing_time,
                    'total_time': total_time
                },
                'performance': {
                    'n_workers': self.n_workers,
                    'preload_enabled': self.preload_all_data,
                    'riders_per_second': len(successful_results) / processing_time if processing_time > 0 else 0
                }
            }
            
            metadata_file = self.output_dir / f"{output_name}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Saved {len(df)} records to {output_file}")
        else:
            self.logger.warning("No successful results to save")
    
    def _get_sample_rider_results_optimized(self, sample_size: int) -> List[Tuple[int, str]]:
        """
        Get sample rider results using optimized two-step approach.
        
        This replaces the slow EXISTS subquery with a much faster two-step process:
        1. Find eligible riders (riders with sufficient race history) 
        2. Sample random results from those eligible riders
        
        Args:
            sample_size: Number of rider results to sample
            
        Returns:
            List of (rider_result_id, competition_date) tuples
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Step 1: Find eligible riders with sufficient race history
            # This is much faster than EXISTS subquery
            self.logger.info("  Step 1a: Finding eligible riders...")
            step1_start = time.time()
            
            eligible_riders_query = """
            SELECT rider_id, COUNT(*) as race_count
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id  
            WHERE c.date <= '2025-01-01'  -- Reasonable cutoff date
            GROUP BY rider_id
            HAVING COUNT(*) >= ?
            ORDER BY RANDOM()
            LIMIT ?
            """
            
            # Sample more riders than needed to ensure we get enough results
            oversample_factor = max(3, int(sample_size / 50))  # Get 3x more riders than needed
            max_riders = sample_size * oversample_factor
            
            cursor.execute(eligible_riders_query, (self.min_races, max_riders))
            eligible_riders = cursor.fetchall()
            
            step1_time = time.time() - step1_start
            self.logger.info(f"  Step 1a complete: Found {len(eligible_riders)} eligible riders in {step1_time:.2f}s")
            
            if not eligible_riders:
                self.logger.error("No eligible riders found")
                return []
            
            # Step 2: Get random results from eligible riders using pre-computed approach
            self.logger.info("  Step 1b: Sampling results from eligible riders...")
            step2_start = time.time()
            
            # Extract rider IDs
            rider_ids = [rider[0] for rider in eligible_riders]
            
            # Create placeholders for IN clause
            placeholders = ','.join(['?'] * len(rider_ids))
            
            # Use window functions to efficiently compute historical race counts
            # This is much faster than correlated subqueries
            window_query = f"""
            WITH ordered_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    c.date as competition_date,
                    rr.rider_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.rider_id 
                        ORDER BY c.date
                    ) - 1 as prior_race_count
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE rr.rider_id IN ({placeholders})
                AND c.date <= '2025-01-01'
                ORDER BY rr.rider_id, c.date
            )
            SELECT rider_result_id, competition_date
            FROM ordered_results
            WHERE prior_race_count >= ?
            ORDER BY RANDOM()
            LIMIT ?
            """
            
            # Execute with rider IDs + min_races + sample_size parameters
            params = rider_ids + [self.min_races, sample_size]
            cursor.execute(window_query, params)
            sample_results = cursor.fetchall()
            
            step2_time = time.time() - step2_start
            self.logger.info(f"  Step 1b complete: Sampled {len(sample_results)} results in {step2_time:.2f}s")
            
            return sample_results