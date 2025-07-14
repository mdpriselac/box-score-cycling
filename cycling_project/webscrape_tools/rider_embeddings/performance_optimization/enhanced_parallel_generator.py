import multiprocessing as mp
import sqlite3
import pandas as pd
import numpy as np
import threading
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
    
    # Set up logging with enhanced chunk ID
    display_id = chunk_id if isinstance(chunk_id, str) and '/' in chunk_id else chunk_id
    logging.basicConfig(level=logging.INFO, format=f'Worker-{display_id}: %(message)s')
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
        Generate correlations using enhanced parallel processing with race type specific sampling.
        
        Args:
            sample_size: Number of rider results to sample (distributed across race types)
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
        
        self.logger.info(f"Generating enhanced parallel sample for {sample_size} rider results using race type logic")
        
        # Step 1: Get sample rider results using race type specific approach
        self.logger.info("Step 1: Getting sample rider results by race type...")
        sample_start = time.time()
        
        # Define race types and their minimum requirements (same as full mode)
        race_type_configs = {
            'gc': {
                'competition_types': ['gc'],
                'min_races': calculator_config.get('min_races_gc', 8)
            },
            'stage': {
                'competition_types': ['stage'],
                'min_races': calculator_config.get('min_races_stage', 15)
            },
            'one_day': {
                'competition_types': ['one_day'],
                'min_races': calculator_config.get('min_races_one_day', 10)
            },
            'stage_one_day': {
                'competition_types': ['stage', 'one_day'],
                'min_races': calculator_config.get('min_races_one_day', 10)
            },
            'all': {
                'competition_types': ['gc', 'stage', 'one_day'],
                'min_races': calculator_config.get('min_races_all', 25)
            }
        }
        
        # Get samples from each race type (distribute sample_size across race types)
        all_sample_results = self._get_sample_results_by_race_type(
            race_type_configs, 
            sample_size
        )
        
        # Combine all results
        sample_results = []
        for race_type, results in all_sample_results.items():
            sample_results.extend(results)
        
        if not sample_results:
            self.logger.error("No eligible rider results found")
            return
        
        # Shuffle to mix race types
        import random
        random.shuffle(sample_results)
        
        # Limit to requested sample size
        sample_results = sample_results[:sample_size]
        
        rider_result_ids = [r[0] for r in sample_results]
        sample_time = time.time() - sample_start
        
        self.logger.info(f"Step 1 complete: {len(sample_results)} rider results in {sample_time:.2f}s")
        
        # Log breakdown by race type
        for race_type, results in all_sample_results.items():
            if results:
                actual_in_sample = len([r for r in sample_results if r in results])
                self.logger.info(f"  {race_type}: {len(results)} available, {actual_in_sample} in final sample")
        
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
        
        # OPTIMIZATION: Use smaller, more balanced chunks for better load distribution
        optimal_chunk_size = min(50, max(10, len(sample_results) // (self.n_workers * 3)))
        sample_chunks = [
            sample_results[i:i+optimal_chunk_size] 
            for i in range(0, len(sample_results), optimal_chunk_size)
        ]
        
        total_chunks = len(sample_chunks)
        self.logger.info(f"Split {len(sample_results)} riders into {total_chunks} chunks of ~{optimal_chunk_size} riders each")
        
        all_results = []
        completed_chunks = 0
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all chunks
            future_to_chunk = {}
            for i, chunk in enumerate(sample_chunks):
                chunk_data = {
                    'rider_result_data': chunk,
                    'feature_tables': feature_tables,
                    'calculator_config': calculator_config,
                    'shared_data': shared_data,
                    'chunk_id': f"sample-{i+1}/{total_chunks}"  # Enhanced chunk ID with progress
                }
                
                if self.preload_all_data:
                    # Use enhanced worker with shared data
                    future = executor.submit(process_rider_chunk_with_shared_data, chunk_data)
                else:
                    # Fall back to original worker
                    from rider_embeddings.performance_optimization.parallel_correlation_generator import process_rider_chunk
                    future = executor.submit(process_rider_chunk, chunk_data)
                
                future_to_chunk[future] = i
            
            # Collect results with progress tracking
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                try:
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
                    completed_chunks += 1
                    
                    # Log progress
                    successful_in_chunk = len([r for r in chunk_results if r.get('feature_correlations')])
                    self.logger.info(f"Sample chunk {completed_chunks}/{total_chunks} complete: "
                                   f"{successful_in_chunk}/{len(sample_chunks[chunk_id])} successful")
                    
                except Exception as e:
                    completed_chunks += 1
                    self.logger.error(f"Sample chunk {completed_chunks}/{total_chunks} failed: {e}")
        
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
    
    def _flatten_correlation_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten correlation result based on calculator type.
        
        For race_type calculators, includes race_type column.
        For standard calculators, uses base implementation.
        """
        # Check if this is race type data by looking at the structure
        if 'feature_correlations' in result and result['feature_correlations']:
            # Get first key to check structure
            first_key = next(iter(result['feature_correlations']))
            
            # If the value is another dict, this is race type data
            if isinstance(result['feature_correlations'][first_key], dict):
                # Race type structure: {race_type: {percentile: {feature: correlation}}}
                return self._flatten_race_type_result(result)
            else:
                # Standard structure: {percentile: {feature: correlation}}
                return super()._flatten_correlation_result(result)
        
        return []
    
    def _flatten_race_type_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten race type correlation result into list of records for parquet storage.
        
        Each record represents one rider-race_type-percentile-feature correlation.
        """
        flat_records = []
        
        rider_result_id = result['rider_result_id']
        calculation_date = result['metadata']['calculation_date']
        
        # Iterate through race types
        for race_type, percentile_data in result['feature_correlations'].items():
            n_races = result['metadata']['n_races'].get(race_type, 0)
            
            # Iterate through percentiles within each race type
            for percentile, correlations in percentile_data.items():
                for feature, correlation in correlations.items():
                    record = {
                        'rider_result_id': rider_result_id,
                        'race_type': race_type,
                        'percentile': percentile,
                        'feature': feature,
                        'correlation': correlation,
                        'n_races': n_races,
                        'calculation_date': calculation_date
                    }
                    flat_records.append(record)
        
        return flat_records
    
    def generate_all_correlations_parallel_enhanced(
        self,
        feature_tables: List[str] = None,
        limit: Optional[int] = None,
        resume: bool = True,
        calculator_type: str = 'race_type',
        calculator_config: Dict[str, Any] = None,
        checkpoint_interval: int = 10000,
        parallel_race_types: bool = False,
        max_concurrent_race_types: int = 2
    ) -> None:
        """
        Generate correlations for all eligible riders using enhanced parallel processing.
        
        This method processes the full dataset with optimized memory management by:
        1. For each race type, finding rider results with sufficient prior races of that type
        2. Processing results in chunks to avoid loading all data at once
        3. Using the enhanced parallel processing with pre-loaded shared data per chunk
        4. Providing checkpoint/resume capability for long runs
        
        Args:
            feature_tables: List of feature tables to analyze
            limit: Optional limit on number of riders to process
            resume: Whether to resume from checkpoint
            calculator_type: Type of calculator ('race_type' or 'standard')
            calculator_config: Configuration for the correlation calculator
            checkpoint_interval: Number of rider results to process before saving checkpoint
            parallel_race_types: Whether to process race types in parallel
            max_concurrent_race_types: Maximum race types to process simultaneously
        """
        if feature_tables is None:
            feature_tables = self._get_all_feature_tables()
        
        if calculator_config is None:
            calculator_config = {
                'type': 'race_type',
                'min_races_all': 150,
                'min_races_stage': 100,
                'min_races_one_day': 30,
                'min_races_gc': 20
            }
        
        self.logger.info("="*80)
        self.logger.info("ENHANCED PARALLEL CORRELATION GENERATION - FULL DATASET")
        self.logger.info("="*80)
        self.logger.info(f"Feature tables: {feature_tables}")
        self.logger.info(f"Calculator type: {calculator_type}")
        self.logger.info(f"Checkpoint interval: {checkpoint_interval} riders")
        
        # Load or create checkpoint
        checkpoint_file = self.output_dir / "checkpoint_enhanced.json"
        if resume and checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
            self.logger.info(f"Resuming from checkpoint: {checkpoint['processed_riders']} riders processed")
        else:
            checkpoint = {
                'processed_riders': 0,
                'total_riders': 0,
                'feature_tables': feature_tables,
                'calculator_config': calculator_config,
                'start_time': datetime.now().isoformat(),
                'batches_completed': []
            }
        
        # For race type calculator, we need to get eligible results for each race type
        if calculator_type == 'race_type':
            self.logger.info("Race type calculator detected - will query eligible results by race type")
            
            # Define race types and their minimum requirements
            race_type_configs = {
                'gc': {
                    'competition_types': ['gc'],
                    'min_races': calculator_config.get('min_races_gc', 20)
                },
                'stage': {
                    'competition_types': ['stage'],
                    'min_races': calculator_config.get('min_races_stage', 100)
                },
                'one_day': {
                    'competition_types': ['one_day'],
                    'min_races': calculator_config.get('min_races_one_day', 30)
                },
                'stage_one_day': {
                    'competition_types': ['stage', 'one_day'],
                    'min_races': calculator_config.get('min_races_one_day', 30)
                },
                'all': {
                    'competition_types': ['gc', 'stage', 'one_day'],
                    'min_races': calculator_config.get('min_races_all', 150)
                }
            }
            
            # Get eligible rider results for each race type
            all_eligible_results = self._get_eligible_results_by_race_type(
                race_type_configs, 
                limit, 
                checkpoint.get('last_processed_race_type', None)
            )
            
            checkpoint['total_results'] = sum(len(results) for results in all_eligible_results.values())
            self.logger.info(f"Found {checkpoint['total_results']} total eligible rider results across all race types")
            
            # Process race types (either in parallel or sequentially)
            if parallel_race_types:
                self._process_race_types_parallel(
                    all_eligible_results, 
                    calculator_config, 
                    feature_tables,
                    checkpoint_interval,
                    checkpoint,
                    checkpoint_file,
                    max_concurrent_race_types
                )
            else:
                self._process_race_types_sequential(
                    all_eligible_results,
                    calculator_config,
                    feature_tables,
                    checkpoint_interval,
                    checkpoint,
                    checkpoint_file
                )
            
            total_processed = checkpoint['total_results']
            
        else:
            # For standard calculator, use the original approach
            self.logger.info("Standard calculator - using original query approach")
            raise NotImplementedError("Standard calculator not yet implemented for enhanced full dataset processing")
            total_processed = 0
        
        # Save final metadata
        self._save_generation_metadata(checkpoint, feature_tables)
        
        # Clean up checkpoint file
        if checkpoint_file.exists():
            checkpoint_file.unlink()
        
        self.logger.info("\n" + "="*80)
        self.logger.info("ENHANCED PARALLEL GENERATION COMPLETE!")
        self.logger.info(f"Processed {total_processed} riders")
        self.logger.info("="*80)
    
    def _process_chunk_enhanced(
        self,
        chunk_results: List[Tuple[int, str]],
        feature_tables: List[str],
        calculator_config: Dict[str, Any],
        batch_number: int,
        progress_info: str = None,
        race_type_suffix: str = None
    ) -> None:
        """
        Process a chunk of rider results using enhanced parallel processing.
        """
        if progress_info:
            self.logger.info(f"Processing {progress_info}: batch {batch_number} with {len(chunk_results)} rider results")
        else:
            self.logger.info(f"Processing batch {batch_number} with {len(chunk_results)} rider results")
        
        # Extract unique rider result IDs
        rider_result_ids = [r[0] for r in chunk_results]
        
        # Pre-load all data for this chunk
        self.logger.info("  Pre-loading data for chunk...")
        preload_start = time.time()
        
        loader = BatchedDatabaseLoader(self.db_path)
        loader.preload_all_data(rider_result_ids, feature_tables)
        
        # Prepare shared data
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
            all_comp_ids = set()
            for history in shared_data['rider_histories'].values():
                all_comp_ids.update(h['competition_id'] for h in history)
            
            features = loader.get_cached_race_features(list(all_comp_ids), feature_table)
            shared_data['race_features'][feature_table] = features
        
        preload_time = time.time() - preload_start
        self.logger.info(f"  Pre-loading complete in {preload_time:.2f}s")
        
        # Clear the loader's cache to free memory
        loader.clear_cache()
        
        # Process in parallel
        self.logger.info("  Processing correlations in parallel...")
        processing_start = time.time()
        
        # Create smaller sub-chunks for parallel processing
        optimal_chunk_size = min(50, max(10, len(chunk_results) // (self.n_workers * 3)))
        sub_chunks = [
            chunk_results[i:i+optimal_chunk_size] 
            for i in range(0, len(chunk_results), optimal_chunk_size)
        ]
        
        all_results = []
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = []
            for i, sub_chunk in enumerate(sub_chunks):
                chunk_data = {
                    'rider_result_data': sub_chunk,
                    'feature_tables': feature_tables,
                    'calculator_config': calculator_config,
                    'shared_data': shared_data,
                    'chunk_id': f"{batch_number}-{i}"
                }
                
                future = executor.submit(process_rider_chunk_with_shared_data, chunk_data)
                futures.append(future)
            
            # Collect results
            for future in as_completed(futures):
                try:
                    sub_results = future.result()
                    all_results.extend(sub_results)
                except Exception as e:
                    self.logger.error(f"Sub-chunk processing failed: {e}")
        
        processing_time = time.time() - processing_start
        self.logger.info(f"  Processing complete in {processing_time:.2f}s")
        
        # Save results for this batch
        if all_results:
            self._save_results_in_batches(
                all_results,
                {'batch_number': batch_number * 1000},  # Offset batch numbers
                feature_tables,
                race_type_suffix=race_type_suffix
            )
            
            successful_results = [r for r in all_results if r.get('feature_correlations')]
            if progress_info:
                self.logger.info(f"  {progress_info} complete: {len(successful_results)}/{len(chunk_results)} successful")
            else:
                self.logger.info(f"  Batch {batch_number} complete: {len(successful_results)}/{len(chunk_results)} successful")
    
    def _get_eligible_results_by_race_type(
        self, 
        race_type_configs: Dict[str, Dict[str, Any]], 
        limit: Optional[int] = None,
        resume_from_race_type: Optional[str] = None
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Get eligible rider results for each race type based on minimum prior races of that type.
        
        Args:
            race_type_configs: Dictionary of race type configurations
            limit: Optional limit on total results
            resume_from_race_type: Race type to resume from (skip earlier types)
            
        Returns:
            Dictionary mapping race type to list of (rider_result_id, competition_date) tuples
        """
        eligible_results = {}
        total_results = 0
        skip_mode = resume_from_race_type is not None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for race_type, config in race_type_configs.items():
                # Skip if we haven't reached the resume point yet
                if skip_mode and race_type != resume_from_race_type:
                    continue
                skip_mode = False  # Start processing from this race type
                
                self.logger.info(f"\nQuerying eligible results for {race_type}...")
                
                competition_types = config['competition_types']
                min_races = config['min_races']
                
                # Build the competition type filter
                if len(competition_types) == 1:
                    type_filter = f"= '{competition_types[0]}'"
                else:
                    type_list = "', '".join(competition_types)
                    type_filter = f"IN ('{type_list}')"
                
                # Optimized query using window functions - much faster than correlated subqueries
                query = f"""
                WITH race_type_results AS (
                    SELECT 
                        rr.id as rider_result_id,
                        rr.rider_id,
                        c.date as competition_date,
                        c.competition_type,
                        -- Use window function to count prior races - much faster
                        ROW_NUMBER() OVER (
                            PARTITION BY rr.rider_id 
                            ORDER BY c.date
                        ) - 1 as prior_races_of_type
                    FROM rider_results rr
                    JOIN competitions c ON rr.competition_id = c.id
                    WHERE c.date <= '2025-01-01'
                    AND c.competition_type {type_filter}
                    ORDER BY rr.rider_id, c.date
                )
                SELECT rider_result_id, competition_date
                FROM race_type_results
                WHERE prior_races_of_type >= ?
                ORDER BY rider_result_id
                """
                
                if limit and total_results >= limit:
                    # We've reached the limit
                    remaining = limit - total_results
                    query += f" LIMIT {remaining}"
                
                cursor.execute(query, (min_races,))
                results = cursor.fetchall()
                
                eligible_results[race_type] = results
                total_results += len(results)
                
                self.logger.info(f"  Found {len(results)} eligible results for {race_type} (min {min_races} prior races)")
                
                if limit and total_results >= limit:
                    self.logger.info(f"  Reached limit of {limit} total results")
                    break
        
        return eligible_results
    
    def _get_sample_results_by_race_type(
        self, 
        race_type_configs: Dict[str, Dict[str, Any]], 
        total_sample_size: int
    ) -> Dict[str, List[Tuple[int, str]]]:
        """
        Get sample rider results for each race type, distributing the total sample size.
        
        Args:
            race_type_configs: Dictionary of race type configurations
            total_sample_size: Total number of results to sample across all race types
            
        Returns:
            Dictionary mapping race type to list of (rider_result_id, competition_date) tuples
        """
        sample_results = {}
        
        # Distribute sample size across race types (equal distribution)
        sample_per_type = max(1, total_sample_size // len(race_type_configs))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for race_type, config in race_type_configs.items():
                self.logger.info(f"Sampling {sample_per_type} results for {race_type}...")
                
                competition_types = config['competition_types']
                min_races = config['min_races']
                
                # Build the competition type filter
                if len(competition_types) == 1:
                    type_filter = f"= '{competition_types[0]}'"
                else:
                    type_list = "', '".join(competition_types)
                    type_filter = f"IN ('{type_list}')"
                
                # Optimized query using window functions with random sampling
                query = f"""
                WITH race_type_results AS (
                    SELECT 
                        rr.id as rider_result_id,
                        rr.rider_id,
                        c.date as competition_date,
                        c.competition_type,
                        -- Use window function to count prior races - much faster
                        ROW_NUMBER() OVER (
                            PARTITION BY rr.rider_id 
                            ORDER BY c.date
                        ) - 1 as prior_races_of_type
                    FROM rider_results rr
                    JOIN competitions c ON rr.competition_id = c.id
                    WHERE c.date <= '2025-01-01'
                    AND c.competition_type {type_filter}
                    ORDER BY rr.rider_id, c.date
                ),
                eligible_results AS (
                    SELECT rider_result_id, competition_date
                    FROM race_type_results
                    WHERE prior_races_of_type >= ?
                )
                SELECT rider_result_id, competition_date
                FROM eligible_results
                ORDER BY RANDOM()
                LIMIT ?
                """
                
                cursor.execute(query, (min_races, sample_per_type))
                results = cursor.fetchall()
                
                sample_results[race_type] = results
                self.logger.info(f"  Sampled {len(results)} results for {race_type}")
        
        return sample_results
    
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
    
    def _process_race_types_parallel(
        self,
        all_eligible_results: Dict[str, List[Tuple[int, str]]],
        calculator_config: Dict[str, Any],
        feature_tables: List[str],
        checkpoint_interval: int,
        checkpoint: Dict[str, Any],
        checkpoint_file: Path,
        max_concurrent_race_types: int
    ) -> None:
        """
        Process race types in parallel with safe file handling.
        
        Args:
            all_eligible_results: Eligible results for each race type
            calculator_config: Calculator configuration
            feature_tables: Feature tables to analyze
            checkpoint_interval: Checkpoint interval
            checkpoint: Checkpoint data
            checkpoint_file: Checkpoint file path
            max_concurrent_race_types: Max concurrent race types
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Filter out completed or empty race types
        pending_race_types = {
            race_type: results 
            for race_type, results in all_eligible_results.items()
            if results and not checkpoint.get('completed_race_types', {}).get(race_type, False)
        }
        
        if not pending_race_types:
            self.logger.info("All race types already completed")
            return
        
        self.logger.info(f"Processing {len(pending_race_types)} race types in parallel")
        self.logger.info(f"Max concurrent race types: {max_concurrent_race_types}")
        
        # Create thread lock for checkpoint updates
        checkpoint_lock = threading.Lock()
        
        # Split race types into batches for parallel processing
        race_types = list(pending_race_types.keys())
        race_type_batches = [
            race_types[i:i+max_concurrent_race_types]
            for i in range(0, len(race_types), max_concurrent_race_types)
        ]
        
        for batch_idx, race_type_batch in enumerate(race_type_batches):
            self.logger.info(f"\nProcessing batch {batch_idx + 1}/{len(race_type_batches)}: {race_type_batch}")
            
            with ThreadPoolExecutor(max_workers=len(race_type_batch)) as executor:
                # Submit race types in this batch
                future_to_race_type = {}
                for race_type in race_type_batch:
                    future = executor.submit(
                        self._process_single_race_type_safe,
                        race_type,
                        pending_race_types[race_type],
                        calculator_config,
                        feature_tables,
                        checkpoint_interval,
                        checkpoint,
                        checkpoint_file,
                        checkpoint_lock
                    )
                    future_to_race_type[future] = race_type
                
                # Wait for all race types in batch to complete
                for future in as_completed(future_to_race_type):
                    race_type = future_to_race_type[future]
                    try:
                        future.result()
                        self.logger.info(f"  ✓ Completed {race_type}")
                    except Exception as e:
                        self.logger.error(f"  ✗ Failed {race_type}: {e}")
                        import traceback
                        traceback.print_exc()
            
            self.logger.info(f"Batch {batch_idx + 1} complete")
    
    def _process_race_types_sequential(
        self,
        all_eligible_results: Dict[str, List[Tuple[int, str]]],
        calculator_config: Dict[str, Any],
        feature_tables: List[str],
        checkpoint_interval: int,
        checkpoint: Dict[str, Any],
        checkpoint_file: Path
    ) -> None:
        """
        Process race types sequentially (original behavior).
        
        Args:
            all_eligible_results: Eligible results for each race type
            calculator_config: Calculator configuration
            feature_tables: Feature tables to analyze
            checkpoint_interval: Checkpoint interval
            checkpoint: Checkpoint data
            checkpoint_file: Checkpoint file path
        """
        # Original sequential processing logic
        for race_type, eligible_results in all_eligible_results.items():
            if not eligible_results:
                continue
                
            self.logger.info(f"\nProcessing {race_type}: {len(eligible_results)} eligible results")
            
            # Skip if we've already processed this race type
            if checkpoint.get('completed_race_types', {}).get(race_type, False):
                self.logger.info(f"  Skipping {race_type} (already completed)")
                continue
            
            # Process in chunks
            chunk_size = min(checkpoint_interval, 5000)
            race_type_processed = checkpoint.get('race_type_progress', {}).get(race_type, 0)
            
            # Calculate total chunks for this race type
            total_chunks = (len(eligible_results) + chunk_size - 1) // chunk_size
            
            # Skip already processed results for this race type
            if race_type_processed > 0:
                eligible_results = eligible_results[race_type_processed:]
                self.logger.info(f"  Resuming from result {race_type_processed}")
            
            for chunk_index, chunk_start in enumerate(range(0, len(eligible_results), chunk_size)):
                chunk_end = min(chunk_start + chunk_size, len(eligible_results))
                chunk_results = eligible_results[chunk_start:chunk_end]
                
                # Calculate actual chunk number (accounting for resumed processing)
                actual_chunk_number = (race_type_processed // chunk_size) + chunk_index + 1
                
                self.logger.info(f"  Processing chunk {actual_chunk_number}/{total_chunks}: results {race_type_processed + chunk_start + 1} to {race_type_processed + chunk_end}")
                
                # Process this chunk
                self._process_chunk_enhanced(
                    chunk_results,
                    feature_tables,
                    calculator_config,
                    batch_number=checkpoint.get('batch_number', 0),
                    progress_info=f"{race_type} chunk {actual_chunk_number}/{total_chunks}"
                )
                
                # Update checkpoint
                checkpoint['batch_number'] = checkpoint.get('batch_number', 0) + 1
                checkpoint['last_processed_race_type'] = race_type
                
                if 'race_type_progress' not in checkpoint:
                    checkpoint['race_type_progress'] = {}
                checkpoint['race_type_progress'][race_type] = race_type_processed + chunk_end
                
                # Save checkpoint
                with open(checkpoint_file, 'w') as f:
                    json.dump(checkpoint, f, indent=2)
            
            # Mark race type as completed
            if 'completed_race_types' not in checkpoint:
                checkpoint['completed_race_types'] = {}
            checkpoint['completed_race_types'][race_type] = True
            checkpoint['race_type_progress'][race_type] = 0  # Reset for next run
            
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
                
            self.logger.info(f"  Completed {race_type}")
    
    def _process_single_race_type_safe(
        self,
        race_type: str,
        eligible_results: List[Tuple[int, str]],
        calculator_config: Dict[str, Any],
        feature_tables: List[str],
        checkpoint_interval: int,
        checkpoint: Dict[str, Any],
        checkpoint_file: Path,
        checkpoint_lock: threading.Lock
    ) -> None:
        """
        Process a single race type with thread-safe checkpoint handling.
        
        Args:
            race_type: Race type to process
            eligible_results: Eligible results for this race type
            calculator_config: Calculator configuration
            feature_tables: Feature tables to analyze
            checkpoint_interval: Checkpoint interval
            checkpoint: Shared checkpoint data
            checkpoint_file: Checkpoint file path
            checkpoint_lock: Thread lock for checkpoint updates
        """
        self.logger.info(f"  {race_type}: Starting with {len(eligible_results)} eligible results")
        
        # Get race type specific progress
        with checkpoint_lock:
            race_type_processed = checkpoint.get('race_type_progress', {}).get(race_type, 0)
        
        # Process in chunks
        chunk_size = min(checkpoint_interval, 5000)
        total_chunks = (len(eligible_results) + chunk_size - 1) // chunk_size
        
        # Skip already processed results
        if race_type_processed > 0:
            eligible_results = eligible_results[race_type_processed:]
            self.logger.info(f"  {race_type}: Resuming from result {race_type_processed}")
        
        for chunk_index, chunk_start in enumerate(range(0, len(eligible_results), chunk_size)):
            chunk_end = min(chunk_start + chunk_size, len(eligible_results))
            chunk_results = eligible_results[chunk_start:chunk_end]
            
            # Calculate actual chunk number
            actual_chunk_number = (race_type_processed // chunk_size) + chunk_index + 1
            
            self.logger.info(f"  {race_type}: Processing chunk {actual_chunk_number}/{total_chunks}")
            
            # Get safe batch number for this race type
            with checkpoint_lock:
                # Use race type specific batch numbering to avoid conflicts
                race_type_batch_base = checkpoint.get('race_type_batch_counters', {}).get(race_type, 0)
                batch_number = race_type_batch_base + chunk_index
                
                # Update race type batch counter
                if 'race_type_batch_counters' not in checkpoint:
                    checkpoint['race_type_batch_counters'] = {}
                checkpoint['race_type_batch_counters'][race_type] = race_type_batch_base + chunk_index + 1
            
            # Process this chunk with race type specific batch number
            self._process_chunk_enhanced(
                chunk_results,
                feature_tables,
                calculator_config,
                batch_number=batch_number,
                progress_info=f"{race_type} chunk {actual_chunk_number}/{total_chunks}",
                race_type_suffix=race_type  # Add race type to avoid file conflicts
            )
            
            # Thread-safe checkpoint update
            with checkpoint_lock:
                if 'race_type_progress' not in checkpoint:
                    checkpoint['race_type_progress'] = {}
                checkpoint['race_type_progress'][race_type] = race_type_processed + chunk_end
                checkpoint['last_processed_race_type'] = race_type
                
                # Save checkpoint
                with open(checkpoint_file, 'w') as f:
                    json.dump(checkpoint, f, indent=2)
        
        # Mark race type as completed
        with checkpoint_lock:
            if 'completed_race_types' not in checkpoint:
                checkpoint['completed_race_types'] = {}
            checkpoint['completed_race_types'][race_type] = True
            
            # Reset progress for next run
            if 'race_type_progress' not in checkpoint:
                checkpoint['race_type_progress'] = {}
            checkpoint['race_type_progress'][race_type] = 0
            
            # Save final checkpoint
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint, f, indent=2)
        
        self.logger.info(f"  {race_type}: Completed successfully")
    
    def _save_results_in_batches(
        self, 
        all_results: List[Dict[str, Any]], 
        checkpoint: Dict[str, Any],
        feature_tables: List[str],
        race_type_suffix: str = None
    ) -> None:
        """
        Save results to parquet files in batches with optional race type suffix.
        
        Args:
            all_results: Results to save
            checkpoint: Checkpoint data
            feature_tables: Feature tables used
            race_type_suffix: Optional race type suffix for file naming
        """
        if race_type_suffix:
            self.logger.info(f"Saving {race_type_suffix} results to parquet files...")
        else:
            self.logger.info("Saving results to parquet files...")
        
        batch_data = []
        results_processed = 0
        
        for result in all_results:
            # Convert to flat structure for parquet
            flat_result = self._flatten_correlation_result(result)
            batch_data.extend(flat_result)
            results_processed += 1
            
            # Update checkpoint
            checkpoint['last_processed_id'] = result['rider_result_id']
            checkpoint['processed_count'] = results_processed
            
            # Save batch if it's large enough
            if len(batch_data) >= self.batch_size * len(feature_tables):
                self._save_batch_with_suffix(batch_data, checkpoint['batch_number'], race_type_suffix)
                checkpoint['batch_number'] += 1
                batch_data = []
                # Note: Don't save checkpoint here for race type processing - handled by caller
        
        # Save final batch
        if batch_data:
            self._save_batch_with_suffix(batch_data, checkpoint['batch_number'], race_type_suffix)
            checkpoint['batch_number'] += 1
    
    def _save_batch_with_suffix(
        self, 
        batch_data: List[Dict[str, Any]], 
        batch_number: int,
        race_type_suffix: str = None
    ) -> None:
        """
        Save a batch of data with optional race type suffix for filename.
        
        Args:
            batch_data: Data to save
            batch_number: Batch number
            race_type_suffix: Optional race type suffix
        """
        if not batch_data:
            return
        
        import pandas as pd
        df = pd.DataFrame(batch_data)
        
        # Create filename with race type suffix
        if race_type_suffix:
            filename = f"race_type_correlations_{race_type_suffix}_batch_{batch_number:04d}.parquet"
        else:
            filename = f"race_type_correlations_batch_{batch_number:04d}.parquet"
        
        output_file = self.output_dir / filename
        df.to_parquet(output_file, compression='snappy')
        
        self.logger.info(f"Saved batch {batch_number} with {len(df)} records to {filename}")