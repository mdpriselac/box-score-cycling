"""
Core correlation processor engine for rider embeddings.
Processes rider results to calculate historical performance correlations against race features.
"""
import numpy as np
import pandas as pd
import sqlite3
import gzip
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import psutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue
import time

from config import ProcessingConfig
from threshold_calculator import ThresholdCalculator
from race_features_loader import RaceFeaturesLoader
from checkpoint_manager import CheckpointManager
from memory_manager import MemoryManager
from cpu_monitor import CPUMonitor

class DatabaseConnectionPool:
    """Thread-safe database connection pool for SQLite"""
    
    def __init__(self, db_path: str, pool_size: int = 4, timeout_seconds: int = 30):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout_seconds = timeout_seconds
        self.connections = queue.Queue(maxsize=pool_size)
        self.lock = threading.Lock()
        
        # Pre-create connections
        for _ in range(pool_size):
            conn = self._create_connection()
            self.connections.put(conn)
    
    def _create_connection(self):
        """Create a properly configured SQLite connection"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        
        # Configure for thread safety and performance
        conn.execute(f"PRAGMA busy_timeout = {self.timeout_seconds * 1000}")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache per connection
        
        return conn
    
    def get_connection(self, timeout=None):
        """Get a connection from the pool"""
        if timeout is None:
            timeout = self.timeout_seconds
            
        try:
            conn = self.connections.get(timeout=timeout)
            # Test the connection
            conn.execute("SELECT 1").fetchone()
            return conn
        except queue.Empty:
            raise Exception(f"Could not get database connection within {timeout} seconds")
        except sqlite3.Error:
            # Connection is stale, create a new one
            conn = self._create_connection()
            return conn
    
    def return_connection(self, conn):
        """Return a connection to the pool"""
        try:
            if conn and not self.connections.full():
                self.connections.put(conn, block=False)
            elif conn:
                # Pool is full, close this connection
                conn.close()
        except queue.Full:
            # Pool is full, close the connection
            conn.close()
    
    def close_all(self):
        """Close all connections in the pool"""
        while not self.connections.empty():
            try:
                conn = self.connections.get(block=False)
                conn.close()
            except queue.Empty:
                break

class CorrelationProcessor:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
        self.threshold_calculator = ThresholdCalculator(db_path, config)
        self.features_loader = RaceFeaturesLoader(db_path, config)
        self.checkpoint_manager = CheckpointManager(db_path, config)
        self.db_pool = None  # Initialize when parallel processing starts
        
    def run(self, resume: bool = True):
        """Main entry point for processing"""
        start_time = datetime.now()
        logging.info("Starting correlation processing pipeline")
        
        # Calculate percentile-based thresholds
        self.threshold_calculator.calculate_thresholds()
        
        # Validate thresholds
        if not self.threshold_calculator.validate_thresholds():
            logging.error("Threshold validation failed")
            return
        
        # Initialize or resume from checkpoint
        start_competition_id = 0
        if resume:
            checkpoint_data = self.checkpoint_manager.load_checkpoint()
            if checkpoint_data:
                start_competition_id = checkpoint_data['last_competition_id']
                logging.info(f"Resuming from competition {start_competition_id}")
        
        # Pre-load race features
        self.features_loader.preload_race_features()
        if not self.features_loader.validate_features_cache():
            logging.error("Race features validation failed")
            return
        
        # Get competitions to process
        competitions = self._get_competitions_to_process(start_competition_id)
        total_competitions = len(competitions)
        logging.info(f"Processing {total_competitions} competitions")
        
        # Process in batches
        for batch_idx, comp_batch in enumerate(self._batch_competitions(competitions)):
            batch_start = datetime.now()
            MemoryManager.log_memory_usage(f"before batch {batch_idx}")
            
            # Process batch
            results = self._process_competition_batch(comp_batch)
            
            # Write results
            self._write_results_batch(results)
            
            # Log progress
            self._log_progress(batch_idx, comp_batch, batch_start)
            
            # Checkpoint if needed
            if (batch_idx + 1) % self.config.CHECKPOINT_FREQUENCY == 0:
                self.checkpoint_manager.save_checkpoint(
                    comp_batch[-1]['competition_id']
                )
            
            # Check memory usage and optimize if needed
            if MemoryManager.check_memory_pressure():
                self.features_loader.optimize_cache()
                MemoryManager.log_memory_usage("after optimization")
        
        # Final checkpoint
        self.checkpoint_manager.finalize()
        
        # Cleanup connection pool
        if self.db_pool:
            self.db_pool.close_all()
            self.db_pool = None
        
        total_time = datetime.now() - start_time
        logging.info(f"Processing completed in {total_time}")
    
    def _get_competitions_to_process(self, start_competition_id: int) -> List[Dict]:
        """Get list of competitions to process"""
        with sqlite3.connect(self.db_path) as conn:
            query = """
            SELECT DISTINCT c.id as competition_id, c.date as competition_date, c.competition_type
            FROM competitions c
            WHERE c.id > ?
            ORDER BY c.date, c.id
            """
            results = conn.execute(query, [start_competition_id]).fetchall()
            
        return [{'competition_id': r[0], 'competition_date': r[1], 'race_type': r[2]} for r in results]
    
    def _batch_competitions(self, competitions: List[Dict]):
        """Yield batches of competitions"""
        for i in range(0, len(competitions), self.config.COMPETITION_BATCH_SIZE):
            yield competitions[i:i + self.config.COMPETITION_BATCH_SIZE]
    
    def _process_competition_batch(self, competitions: List[Dict]) -> List[Dict]:
        """Process a batch of competitions with parallel rider processing"""
        results = []
        comp_ids = [c['competition_id'] for c in competitions]
        
        # Get eligible rider results
        eligible_results = self._get_eligible_rider_results(comp_ids)
        
        logging.info(f"Processing {len(eligible_results)} eligible rider results in batch")
        
        # Check if parallel processing is enabled
        if not self.config.THREAD_SAFETY_ENABLED or self.config.NUM_WORKERS == 1:
            # Fall back to sequential processing
            return self._process_competition_batch_sequential(competitions)
        
        # Initialize connection pool for this batch
        if self.db_pool is None:
            self.db_pool = DatabaseConnectionPool(
                self.db_path, 
                pool_size=self.config.NUM_WORKERS,
                timeout_seconds=self.config.DB_TIMEOUT_SECONDS
            )
        
        # Create worker tasks
        tasks = []
        for rr in eligible_results:
            race_type = rr['race_type']
            correlation_types = self.config.RACE_TYPE_CORRELATIONS[race_type]
            
            for corr_type in correlation_types:
                tasks.append({
                    'rider_result': rr,
                    'correlation_type': corr_type,
                    'task_id': f"{rr['rider_result_id']}_{corr_type}"
                })
        
        logging.debug(f"Created {len(tasks)} parallel tasks for {len(eligible_results)} riders")
        
        # Process tasks in parallel with CPU monitoring
        failed_tasks = []
        successful_tasks = 0
        cpu_monitor = CPUMonitor(interval_seconds=0.5)
        
        # Start CPU monitoring if we have a significant number of tasks
        if len(tasks) >= 10:
            cpu_monitor.start_monitoring()
        
        with ThreadPoolExecutor(max_workers=self.config.NUM_WORKERS) as executor:
            # Submit all tasks
            future_to_task = {}
            for task in tasks:
                future = executor.submit(
                    self._calculate_rider_correlation_parallel,
                    task['rider_result'],
                    task['correlation_type'],
                    task['task_id']
                )
                future_to_task[future] = task
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    correlation_result, race_count = future.result()
                    successful_tasks += 1
                    
                    if correlation_result is not None:
                        result_dict = {
                            'rider_result_id': task['rider_result']['rider_result_id'],
                            'competition_id': task['rider_result']['competition_id'],
                            'rider_id': task['rider_result']['rider_id'],
                            'correlation_type': task['correlation_type'],
                            'race_count': race_count  # Keep for backward compatibility
                        }
                        # Add all the correlation result data
                        result_dict.update(correlation_result)
                        results.append(result_dict)
                        
                except Exception as e:
                    failed_tasks.append({
                        'task_id': task['task_id'],
                        'error': str(e),
                        'rider_result_id': task['rider_result']['rider_result_id']
                    })
                    logging.error(f"Error processing task {task['task_id']}: {e}")
        
        # Stop CPU monitoring and get results
        if len(tasks) >= 10:
            cpu_summary = cpu_monitor.get_summary()
            if cpu_summary and not cpu_summary.get('error'):
                if cpu_summary['parallel_processing_detected']:
                    logging.info(f"✅ Parallel processing verified: {cpu_summary['max_cores_active']} cores active, {cpu_summary['avg_cpu_overall']:.1f}% avg CPU")
                else:
                    logging.warning(f"⚠️ Parallel processing not detected: {cpu_summary['max_cores_active']} cores, {cpu_summary['avg_cpu_overall']:.1f}% CPU")
        
        # Log processing summary
        if failed_tasks:
            logging.warning(f"Failed to process {len(failed_tasks)} tasks out of {len(tasks)}")
            # Log first few failed tasks for debugging
            for failed_task in failed_tasks[:5]:
                logging.warning(f"Failed task: {failed_task}")
        
        logging.debug(f"Successfully processed {successful_tasks}/{len(tasks)} tasks")
        
        return results
    
    def _process_competition_batch_sequential(self, competitions: List[Dict]) -> List[Dict]:
        """Sequential processing fallback (original implementation)"""
        results = []
        comp_ids = [c['competition_id'] for c in competitions]
        
        # Get eligible rider results
        eligible_results = self._get_eligible_rider_results(comp_ids)
        
        logging.info(f"Processing {len(eligible_results)} eligible rider results in batch (sequential)")
        
        # Use a single connection for all rider history queries in this batch
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            # Process each rider result
            for rr in eligible_results:
                race_type = rr['race_type']
                
                # Get correlation types for this race type
                correlation_types = self.config.RACE_TYPE_CORRELATIONS[race_type]
                
                for corr_type in correlation_types:
                    # Get rider history and calculate correlation
                    correlation_result, race_count = self._calculate_rider_correlation(rr, corr_type, conn)
                    
                    if correlation_result is not None:
                        # correlation_result is now a dict with matrix and metadata
                        result_dict = {
                            'rider_result_id': rr['rider_result_id'],
                            'competition_id': rr['competition_id'],
                            'rider_id': rr['rider_id'],
                            'correlation_type': corr_type,
                            'race_count': race_count  # Keep for backward compatibility
                        }
                        # Add all the correlation result data
                        result_dict.update(correlation_result)
                        results.append(result_dict)
        
        return results
    
    def _get_eligible_rider_results(self, comp_ids: List[int]) -> List[Dict]:
        """Get eligible rider results that meet minimum race requirements"""
        
        query = """
        SELECT rr.id as rider_result_id, rr.competition_id, rr.rider_id, 
               rr.total_prior_races, rr.prior_gc_races, rr.prior_stage_races,
               rr.prior_one_day_races, rr.prior_stage_one_days,
               c.competition_type as race_type, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE rr.competition_id IN ({})
        AND rr.total_prior_races >= ?  -- Global minimum
        AND (
            -- Race-type specific minimums
            (c.competition_type = 'gc' AND rr.prior_gc_races >= ?)
            OR
            (c.competition_type = 'stage' AND rr.prior_stage_races >= ? AND rr.prior_stage_one_days >= ?)
            OR
            (c.competition_type = 'one_day' AND rr.prior_one_day_races >= ? AND rr.prior_stage_one_days >= ?)
        )
        ORDER BY c.date, rr.competition_id
        """.format(','.join(['?'] * len(comp_ids)))
        
        params = comp_ids + [
            self.config.MIN_RACES['total_prior_races'],       # Global minimum
            self.config.MIN_RACES['prior_gc_races'],         # GC minimum
            self.config.MIN_RACES['prior_stage_races'],      # Stage minimum
            self.config.MIN_RACES['prior_stage_one_days'],   # Stage combined minimum
            self.config.MIN_RACES['prior_one_day_races'],    # One-day minimum
            self.config.MIN_RACES['prior_stage_one_days']    # One-day combined minimum
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            results = conn.execute(query, params).fetchall()
        
        return [dict(r) for r in results]
    
    def _calculate_rider_correlation(self, rider_result: Dict, corr_type: str, conn) -> Tuple[Optional[np.ndarray], int]:
        """Calculate correlation matrix for a rider's history"""
        
        # Get rider history based on correlation type
        history = self._get_rider_history(
            rider_result['rider_id'], 
            rider_result['competition_date'],
            rider_result['race_type'],
            corr_type,
            conn
        )
        
        # Check minimum requirements
        min_required = self._get_min_required_races(rider_result['race_type'], corr_type)
        
        if len(history) < min_required:
            return None, len(history)
        
        # Calculate correlation matrix
        correlation_result = self._calculate_correlation_matrix(history)
        
        if correlation_result is None:
            return None, len(history)
        
        return correlation_result, len(history)
    
    def _calculate_rider_correlation_parallel(self, rider_result: Dict, corr_type: str, task_id: str) -> Tuple[Optional[Dict], int]:
        """Thread-safe version of rider correlation calculation using connection pool"""
        
        # Get connection from pool
        conn = None
        try:
            conn = self.db_pool.get_connection()
            if conn is None:
                raise Exception("Failed to get database connection from pool")
            
            # Get rider history (thread-safe)
            history = self._get_rider_history(
                rider_result['rider_id'],
                rider_result['competition_date'],
                rider_result['race_type'],
                corr_type,
                conn
            )
            
            # Check minimum requirements
            min_required = self._get_min_required_races(rider_result['race_type'], corr_type)
            
            if len(history) < min_required:
                return None, len(history)
            
            # Calculate correlation matrix (thread-safe - uses read-only cache)
            correlation_result = self._calculate_correlation_matrix(history)
            
            if correlation_result is None:
                return None, len(history)
            
            return correlation_result, len(history)
            
        except Exception as e:
            raise Exception(f"Database error in task {task_id}: {str(e)}")
        finally:
            # Always return connection to pool
            if conn and self.db_pool:
                self.db_pool.return_connection(conn)
    
    def _get_rider_history(self, rider_id: int, before_date: str, 
                          race_type: str, corr_type: str, conn) -> List[Dict]:
        """Get rider's history before a specific date"""
        
        if corr_type == 'stage_one_days':
            # Special case: combined stage and one-day races
            query = """
            SELECT rr.competition_id, rr.percentile as points, c.date as competition_date
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date < ?
            AND c.competition_type IN ('stage', 'one_day')
            ORDER BY c.date DESC
            """
            params = [rider_id, before_date]
            
        elif corr_type == 'same_type':
            query = """
            SELECT rr.competition_id, rr.percentile as points, c.date as competition_date
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date < ?
            AND c.competition_type = ?
            ORDER BY c.date DESC
            """
            params = [rider_id, before_date, race_type]
            
        else:  # all_races
            query = """
            SELECT rr.competition_id, rr.percentile as points, c.date as competition_date
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date < ?
            ORDER BY c.date DESC
            """
            params = [rider_id, before_date]
        
        results = conn.execute(query, params).fetchall()
        
        return [dict(r) for r in results]
    
    def _calculate_correlation_matrix(self, history: List[Dict]) -> Optional[Dict]:
        """Calculate correlation matrix for a rider's history"""
        if not history:
            return None
        
        # Extract points and competition IDs
        points = np.array([h['points'] for h in history])
        comp_ids = [h['competition_id'] for h in history]
        
        # Build feature matrix - include all competitions, use NaN for missing percentiles
        feature_matrices = []
        missing_competitions = []
        percentile_availability_combined = np.ones(len(self.config.PERCENTILES), dtype=int)
        
        for comp_id in comp_ids:
            features = self.features_loader.get_race_features(comp_id)
            if features is not None:
                feature_matrices.append(features)
                # Track which percentiles are available for this competition
                comp_availability = self.features_loader.get_percentile_availability(comp_id)
                if comp_availability:
                    # Update combined availability (0 if any race is missing that percentile)
                    percentile_availability_combined = np.logical_and(
                        percentile_availability_combined, 
                        comp_availability
                    ).astype(int)
            else:
                missing_competitions.append(comp_id)
                logging.debug(f"Missing race features for competition {comp_id}")
                # Create matrix with all NaN for missing competition
                nan_matrix = np.full((len(self.config.PERCENTILES), self.config.NUM_FEATURES), np.nan)
                feature_matrices.append(nan_matrix)
                # Mark all percentiles as unavailable for this race
                percentile_availability_combined = np.zeros(len(self.config.PERCENTILES), dtype=int)
        
        if len(feature_matrices) == 0:
            logging.info(f"No races found for rider")
            return None
        
        # Stack into 3D array: (n_races, 8, 37)
        features_3d = np.stack(feature_matrices)
        
        # Calculate correlations per percentile
        correlation_matrix = np.full((len(self.config.PERCENTILES), self.config.NUM_FEATURES), np.nan)
        
        for p_idx, percentile in enumerate(self.config.PERCENTILES):
            # Only calculate correlation if this percentile has data for all races
            if percentile_availability_combined[p_idx] == 1:
                percentile_features = features_3d[:, p_idx, :]  # Shape: (n_races, 37)
                
                for f_idx in range(self.config.NUM_FEATURES):
                    feature_values = percentile_features[:, f_idx]
                    # Skip if any values are NaN or if no variation
                    if not np.any(np.isnan(feature_values)) and np.std(feature_values) > 0:
                        corr = np.corrcoef(points, feature_values)[0, 1]
                        if not np.isnan(corr):
                            correlation_matrix[p_idx, f_idx] = corr
        
        # Return both correlation matrix and metadata
        return {
            'correlation_matrix': correlation_matrix,
            'total_races': len(history),
            'races_with_features': len(history) - len(missing_competitions),
            'missing_competitions': missing_competitions,
            'percentile_availability': percentile_availability_combined.tolist()
        }
    
    def _get_min_required_races(self, race_type: str, corr_type: str) -> int:
        """Get minimum required races for a correlation type"""
        if corr_type == 'all_races':
            return self.config.MIN_RACES['total_prior_races']
        elif corr_type == 'same_type':
            col_name = self.config.RACE_TYPE_COLUMNS[race_type]
            return self.config.MIN_RACES[col_name]
        elif corr_type == 'stage_one_days':
            return self.config.MIN_RACES['prior_stage_one_days']
        else:
            return 5  # Default
    
    def _write_results_batch(self, results: List[Dict]):
        """Write results to database in batch"""
        if not results:
            return
        
        with sqlite3.connect(self.db_path) as conn:
            # Optimize for writes
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA cache_size = -2000000")
            
            # Prepare denormalized records
            denorm_records = []
            blob_records = []
            quality_records = []
            
            for r in results:
                # Extract data from the new format
                matrix = r['correlation_matrix']
                total_races = r['total_races']
                races_with_features = r['races_with_features']
                missing_competitions = r['missing_competitions']
                percentile_availability = r['percentile_availability']
                
                # Store BLOB version for backup
                matrix_blob = gzip.compress(matrix.tobytes())
                blob_records.append((
                    r['rider_result_id'],
                    r['competition_id'],
                    r['rider_id'],
                    r['correlation_type'],
                    matrix_blob,
                    races_with_features  # Updated to use races_with_features
                ))
                
                # Store data quality information
                import json
                quality_records.append((
                    r['rider_result_id'],
                    r['correlation_type'],
                    total_races,
                    races_with_features,
                    json.dumps(missing_competitions),
                    json.dumps(percentile_availability),
                    races_with_features / total_races if total_races > 0 else 0.0
                ))
                
                # Create denormalized records
                for p_idx, percentile in enumerate(self.config.PERCENTILES):
                    for f_idx in range(self.config.NUM_FEATURES):
                        correlation_value = matrix[p_idx, f_idx]
                        # Use None for NaN values in database
                        if np.isnan(correlation_value):
                            correlation_value = None
                        
                        denorm_records.append((
                            r['rider_result_id'],
                            r['competition_id'],
                            r['rider_id'],
                            r['correlation_type'],
                            percentile,
                            f_idx,
                            self.config.RACE_FEATURES[f_idx],  # feature_name
                            correlation_value,
                            races_with_features  # Updated to use races_with_features
                        ))
            
            # Batch insert denormalized data
            conn.executemany("""
                INSERT OR REPLACE INTO rider_correlations_denorm 
                (rider_result_id, competition_id, rider_id, correlation_type,
                 percentile, feature_idx, feature_name, correlation_value, race_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, denorm_records)
            
            # Batch insert blob backup
            conn.executemany("""
                INSERT OR REPLACE INTO rider_correlations_blob
                (rider_result_id, competition_id, rider_id, correlation_type,
                 correlation_matrix, race_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, blob_records)
            
            # Batch insert data quality records
            conn.executemany("""
                INSERT OR REPLACE INTO correlation_data_quality
                (rider_result_id, correlation_type, total_races, races_with_features,
                 missing_competition_ids, percentile_availability, data_completeness)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, quality_records)
            
            conn.commit()
            
            logging.info(f"Wrote {len(results)} correlation matrices ({len(denorm_records)} values) with data quality tracking")
    
    def _log_progress(self, batch_idx: int, comp_batch: List[Dict], 
                     batch_start: datetime):
        """Log processing progress"""
        processing_time = (datetime.now() - batch_start).total_seconds()
        memory_stats = MemoryManager.get_memory_stats()
        
        with sqlite3.connect(self.db_path) as conn:
            # Get batch statistics
            comp_ids = [c['competition_id'] for c in comp_batch]
            placeholders = ','.join(['?'] * len(comp_ids))
            
            stats = conn.execute(f"""
                SELECT 
                    COUNT(DISTINCT rider_id) as riders,
                    COUNT(*) as correlations
                FROM rider_correlations_denorm
                WHERE competition_id IN ({placeholders})
            """, comp_ids).fetchone()
            
            # Log to database
            conn.execute("""
                INSERT INTO processing_log
                (batch_number, competitions_processed, riders_processed,
                 correlations_calculated, processing_time_seconds, memory_usage_mb)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                batch_idx,
                len(comp_batch),
                stats[0] if stats else 0,
                stats[1] if stats else 0,
                processing_time,
                memory_stats['used_gb'] * 1024
            ))
            conn.commit()
        
        # Calculate parallel processing throughput
        estimated_tasks = stats[1] if stats else 0  # Use correlations as proxy for tasks
        throughput = estimated_tasks / processing_time if processing_time > 0 else 0
        
        logging.info(
            f"Batch {batch_idx}: Processed {len(comp_batch)} competitions "
            f"in {processing_time:.1f}s, Memory: {memory_stats['used_gb']:.1f}GB"
        )
        
        if self.config.THREAD_SAFETY_ENABLED and self.config.NUM_WORKERS > 1:
            logging.info(f"Parallel processing throughput: {throughput:.1f} tasks/second using {self.config.NUM_WORKERS} workers")