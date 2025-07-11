import multiprocessing as mp
import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Iterator
from pathlib import Path
from datetime import datetime
import json
from tqdm import tqdm
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
import sys
import traceback
import time

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from rider_embeddings.data_generation.correlation_generator import CorrelationDataGenerator
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator
from rider_embeddings.performance_optimization.batched_database_loader import BatchedDatabaseLoader


def process_rider_chunk(chunk_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Worker function to process a chunk of riders in parallel.
    
    This function must be at module level to be pickleable for multiprocessing.
    
    Args:
        chunk_data: Dictionary containing:
            - rider_result_data: List of (rider_result_id, competition_date) tuples
            - feature_tables: List of feature tables to analyze
            - db_path: Path to database
            - calculator_config: Configuration for the correlation calculator
            - chunk_id: ID for this chunk (for logging)
    
    Returns:
        List of correlation results
    """
    rider_result_data = chunk_data['rider_result_data']
    feature_tables = chunk_data['feature_tables']
    db_path = chunk_data['db_path']
    calculator_config = chunk_data['calculator_config']
    chunk_id = chunk_data.get('chunk_id', 'unknown')
    
    # Set up logging for this worker
    logging.basicConfig(level=logging.INFO, format=f'Worker-{chunk_id}: %(message)s')
    logger = logging.getLogger(f'worker_{chunk_id}')
    
    try:
        # Initialize calculator for this worker
        if calculator_config['type'] == 'race_type':
            calculator = RaceTypeCorrelationCalculator(
                db_path,
                min_races_all=calculator_config.get('min_races_all', 35),
                min_races_stage=calculator_config.get('min_races_stage', 25),
                min_races_one_day=calculator_config.get('min_races_one_day', 15),
                min_races_gc=calculator_config.get('min_races_gc', 10)
            )
        else:
            # Import and use standard calculator
            from rider_embeddings.performance_feature_link.correlation_method.correlation_calculator import CorrelationCalculator
            calculator = CorrelationCalculator(
                db_path,
                min_races=calculator_config.get('min_races', 5)
            )
        
        logger.info(f"Processing chunk with {len(rider_result_data)} riders")
        
        results = []
        successful = 0
        failed = 0
        
        for rider_result_id, competition_date in rider_result_data:
            try:
                result = calculator.calculate_feature_relationships(
                    rider_result_id, competition_date, feature_tables
                )
                results.append(result)
                successful += 1
                
            except Exception as e:
                failed += 1
                error_result = {
                    'rider_result_id': rider_result_id,
                    'feature_correlations': {},
                    'metadata': {
                        'n_races': 0,
                        'method': calculator_config['type'],
                        'calculation_date': datetime.now(),
                        'warnings': [f"Error processing rider {rider_result_id}: {str(e)}"],
                        'error': str(e)
                    }
                }
                results.append(error_result)
                logger.warning(f"Error processing rider {rider_result_id}: {e}")
        
        logger.info(f"Chunk complete: {successful} successful, {failed} failed")
        return results
        
    except Exception as e:
        logger.error(f"Chunk processing failed: {e}")
        logger.error(traceback.format_exc())
        return []


class ParallelCorrelationGenerator(CorrelationDataGenerator):
    """
    Parallel version of correlation data generator with significant performance improvements.
    
    Uses multiprocessing to parallelize correlation generation across multiple CPU cores
    and batched database loading to minimize I/O overhead.
    """
    
    def __init__(
        self,
        db_path: str,
        output_dir: str = "correlation_data",
        batch_size: int = 100,
        min_races: int = 5,
        n_workers: int = None,
        use_batched_loading: bool = True
    ):
        """
        Initialize the parallel correlation data generator.
        
        Args:
            db_path: Path to the cycling database
            output_dir: Directory to save parquet files
            batch_size: Number of rider results to process per batch (for output)
            min_races: Minimum races required for correlation calculation
            n_workers: Number of worker processes (default: CPU count)
            use_batched_loading: Whether to use batched database loading
        """
        # Don't call parent __init__ directly to avoid double initialization
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.min_races = min_races
        self.n_workers = n_workers or mp.cpu_count()
        self.use_batched_loading = use_batched_loading
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize batched loader if enabled
        self._batched_loader = None
        if use_batched_loading:
            self._batched_loader = BatchedDatabaseLoader(db_path)
        
        # Setup logging
        self._setup_logging()
        
        self.logger.info(f"Initialized parallel generator with {self.n_workers} workers")
    
    def generate_all_correlations_parallel(
        self,
        feature_tables: List[str] = None,
        limit: Optional[int] = None,
        resume: bool = True,
        calculator_type: str = 'race_type',
        calculator_config: Dict[str, Any] = None
    ) -> None:
        """
        Generate correlations for all eligible rider results using parallel processing.
        
        Args:
            feature_tables: List of race_features_N tables to analyze
            limit: Optional limit on number of rider results to process
            resume: Whether to resume from checkpoint
            calculator_type: Type of calculator to use ('race_type' or 'standard')
            calculator_config: Configuration for the correlation calculator
        """
        if feature_tables is None:
            feature_tables = [
                'race_features_30', 'race_features_40', 'race_features_50',
                'race_features_60', 'race_features_70', 'race_features_80',
                'race_features_90', 'race_features_100'
            ]
        
        if calculator_config is None:
            if calculator_type == 'race_type':
                calculator_config = {
                    'type': 'race_type',
                    'min_races_all': 35,
                    'min_races_stage': 25,
                    'min_races_one_day': 15,
                    'min_races_gc': 10
                }
            else:
                calculator_config = {
                    'type': 'standard',
                    'min_races': self.min_races
                }
        
        # Load checkpoint if resuming
        checkpoint = self.load_checkpoint() if resume else {
            'last_processed_id': 0,
            'processed_count': 0,
            'batch_number': 0,
            'start_time': datetime.now().isoformat()
        }
        
        self.logger.info(f"Starting parallel correlation generation...")
        self.logger.info(f"Feature tables: {feature_tables}")
        self.logger.info(f"Calculator type: {calculator_type}")
        self.logger.info(f"Workers: {self.n_workers}")
        
        if resume and checkpoint['last_processed_id'] > 0:
            self.logger.info(f"Resuming from rider_result_id {checkpoint['last_processed_id']}")
        
        # Get eligible rider results
        eligible_results = self.get_eligible_rider_results(limit)
        
        # Filter out already processed if resuming
        if resume:
            eligible_results = [
                (rr_id, date) for rr_id, date in eligible_results
                if rr_id > checkpoint['last_processed_id']
            ]
        
        total_to_process = len(eligible_results)
        self.logger.info(f"Found {total_to_process} rider results to process")
        
        if total_to_process == 0:
            self.logger.info("No rider results to process")
            return
        
        # Split work into chunks for parallel processing
        chunk_size = max(1, total_to_process // (self.n_workers * 4))  # 4 chunks per worker
        rider_chunks = [
            eligible_results[i:i+chunk_size] 
            for i in range(0, total_to_process, chunk_size)
        ]
        
        self.logger.info(f"Split work into {len(rider_chunks)} chunks of ~{chunk_size} riders each")
        
        # Process chunks in parallel
        start_time = time.time()
        all_results = []
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all chunks
            future_to_chunk = {}
            for i, chunk in enumerate(rider_chunks):
                chunk_data = {
                    'rider_result_data': chunk,
                    'feature_tables': feature_tables,
                    'db_path': self.db_path,
                    'calculator_config': calculator_config,
                    'chunk_id': i
                }
                future = executor.submit(process_rider_chunk, chunk_data)
                future_to_chunk[future] = i
            
            # Collect results as they complete
            with tqdm(total=len(rider_chunks), desc="Processing chunks") as pbar:
                for future in as_completed(future_to_chunk):
                    chunk_id = future_to_chunk[future]
                    try:
                        chunk_results = future.result()
                        all_results.extend(chunk_results)
                        self.logger.info(f"Chunk {chunk_id} completed with {len(chunk_results)} results")
                    except Exception as e:
                        self.logger.error(f"Chunk {chunk_id} failed: {e}")
                    
                    pbar.update(1)
        
        processing_time = time.time() - start_time
        self.logger.info(f"Parallel processing completed in {processing_time:.2f} seconds")
        self.logger.info(f"Processed {len(all_results)} total results")
        
        # Save results in batches
        self._save_results_in_batches(all_results, checkpoint, feature_tables)
        
        # Save generation metadata
        self._save_generation_metadata(checkpoint, feature_tables, processing_time)
        
        self.logger.info(f"Parallel correlation generation complete!")
    
    def _save_results_in_batches(
        self, 
        all_results: List[Dict[str, Any]], 
        checkpoint: Dict[str, Any],
        feature_tables: List[str]
    ) -> None:
        """Save results to parquet files in batches."""
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
                self._save_batch(batch_data, checkpoint['batch_number'])
                checkpoint['batch_number'] += 1
                batch_data = []
                self.save_checkpoint(checkpoint)
        
        # Save final batch
        if batch_data:
            self._save_batch(batch_data, checkpoint['batch_number'])
            checkpoint['batch_number'] += 1
            self.save_checkpoint(checkpoint)
    
    def _save_generation_metadata(
        self, 
        checkpoint: Dict[str, Any], 
        feature_tables: List[str],
        processing_time: float
    ) -> None:
        """Save metadata about the parallel generation run."""
        metadata = {
            'generation_complete': datetime.now().isoformat(),
            'start_time': checkpoint['start_time'],
            'total_processed': checkpoint['processed_count'],
            'total_batches': checkpoint['batch_number'],
            'feature_tables': feature_tables,
            'min_races': self.min_races,
            'batch_size': self.batch_size,
            'parallel_processing': {
                'enabled': True,
                'n_workers': self.n_workers,
                'processing_time_seconds': processing_time,
                'riders_per_second': checkpoint['processed_count'] / processing_time if processing_time > 0 else 0
            }
        }
        
        metadata_file = self.output_dir / "generation_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def generate_sample_parallel(
        self,
        sample_size: int = 1000,
        feature_tables: List[str] = None,
        output_name: str = "parallel_sample",
        calculator_type: str = 'race_type',
        calculator_config: Dict[str, Any] = None
    ) -> None:
        """
        Generate correlations for a sample of rider results using parallel processing.
        
        Args:
            sample_size: Number of rider results to sample
            feature_tables: List of feature tables to analyze
            output_name: Name for output file
            calculator_type: Type of calculator to use
            calculator_config: Configuration for the correlation calculator
        """
        if feature_tables is None:
            feature_tables = ['race_features_80', 'race_features_100']
        
        if calculator_config is None:
            if calculator_type == 'race_type':
                calculator_config = {
                    'type': 'race_type',
                    'min_races_all': 25,  # Lower for samples
                    'min_races_stage': 15,
                    'min_races_one_day': 10,
                    'min_races_gc': 8
                }
            else:
                calculator_config = {
                    'type': 'standard',
                    'min_races': self.min_races
                }
        
        self.logger.info(f"Generating parallel sample correlation data for {sample_size} rider results")
        
        # Get random sample of eligible results
        query = """
        SELECT rr.id, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE EXISTS (
            SELECT 1 
            FROM rider_results rr2
            JOIN competitions c2 ON rr2.competition_id = c2.id
            WHERE rr2.rider_id = rr.rider_id
            AND c2.date < c.date
            GROUP BY rr2.rider_id
            HAVING COUNT(*) >= ?
        )
        ORDER BY RANDOM()
        LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (self.min_races, sample_size))
            sample_results = cursor.fetchall()
        
        if not sample_results:
            self.logger.warning("No sample results found")
            return
        
        # Process sample in parallel (use smaller chunks for samples)
        chunk_size = max(1, len(sample_results) // self.n_workers)
        sample_chunks = [
            sample_results[i:i+chunk_size] 
            for i in range(0, len(sample_results), chunk_size)
        ]
        
        self.logger.info(f"Processing sample in {len(sample_chunks)} parallel chunks")
        
        start_time = time.time()
        all_results = []
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all chunks
            future_to_chunk = {}
            for i, chunk in enumerate(sample_chunks):
                chunk_data = {
                    'rider_result_data': chunk,
                    'feature_tables': feature_tables,
                    'db_path': self.db_path,
                    'calculator_config': calculator_config,
                    'chunk_id': i
                }
                future = executor.submit(process_rider_chunk, chunk_data)
                future_to_chunk[future] = i
            
            # Collect results
            for future in as_completed(future_to_chunk):
                chunk_id = future_to_chunk[future]
                try:
                    chunk_results = future.result()
                    all_results.extend(chunk_results)
                except Exception as e:
                    self.logger.error(f"Sample chunk {chunk_id} failed: {e}")
        
        processing_time = time.time() - start_time
        self.logger.info(f"Sample processing completed in {processing_time:.2f} seconds")
        
        # Filter out failed results
        successful_results = [r for r in all_results if r.get('feature_correlations')]
        
        self.logger.info(f"Successfully processed {len(successful_results)}/{len(sample_results)} rider results")
        
        # Convert to flat format and save
        all_data = []
        for result in successful_results:
            flat_result = self._flatten_correlation_result(result)
            all_data.extend(flat_result)
        
        if all_data:
            df = pd.DataFrame(all_data)
            output_file = self.output_dir / f"{output_name}_correlations.parquet"
            df.to_parquet(output_file, compression='snappy')
            
            self.logger.info(f"Saved parallel sample data with {len(df)} records to {output_file}")
            
            # Save sample metadata
            metadata = {
                'type': 'parallel_sample',
                'sample_size': sample_size,
                'actual_riders': len(sample_results),
                'successful_riders': len(successful_results),
                'total_records': len(df),
                'feature_tables': feature_tables,
                'generation_date': datetime.now().isoformat(),
                'processing_time_seconds': processing_time,
                'parallel_processing': {
                    'n_workers': self.n_workers,
                    'chunk_count': len(sample_chunks),
                    'riders_per_second': len(successful_results) / processing_time if processing_time > 0 else 0
                }
            }
            
            metadata_file = self.output_dir / f"{output_name}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        else:
            self.logger.warning("No successful results to save")