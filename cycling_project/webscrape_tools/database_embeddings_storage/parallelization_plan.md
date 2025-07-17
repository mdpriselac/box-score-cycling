# Parallelization Plan: Rider Correlation Processing

## Project Background

### System Overview
The rider correlation processing system calculates historical performance correlations between riders and race features. It processes ~8,590 competitions and generates correlation matrices for ~182K rider results, creating ~54M individual correlation records.

### Current Architecture

#### Core Components
1. **CorrelationProcessor** (`correlation_processor.py`): Main processing engine
2. **RaceFeaturesLoader** (`race_features_loader.py`): Pre-loads race features into memory
3. **ThresholdCalculator** (`threshold_calculator.py`): Calculates minimum race thresholds
4. **CheckpointManager** (`checkpoint_manager.py`): Handles resume/checkpoint functionality
5. **MemoryManager** (`memory_manager.py`): Monitors memory usage

#### Data Structures
- **Race Features Cache**: 8,414 competitions × 8 percentiles × 37 features (~19MB)
- **Correlation Matrix**: 8 percentiles × 37 features per rider
- **Three Correlation Types**: `all_races`, `same_type`, `stage_one_days`

#### Database Schema
```sql
-- Main output table
rider_correlations_denorm (
    rider_result_id, competition_id, rider_id, correlation_type,
    percentile, feature_idx, feature_name, correlation_value, race_count
)

-- Data quality tracking
correlation_data_quality (
    rider_result_id, correlation_type, total_races, races_with_features,
    missing_competition_ids, percentile_availability, data_completeness
)
```

### Current Processing Flow

#### 1. Batch Processing (`_process_competition_batch`)
```python
def _process_competition_batch(self, competitions: List[Dict]) -> List[Dict]:
    # Get eligible riders for this batch of competitions
    eligible_results = self._get_eligible_rider_results(comp_ids)
    
    # Use single connection for all queries in batch
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # SEQUENTIAL PROCESSING - TARGET FOR PARALLELIZATION
        for rr in eligible_results:
            for corr_type in correlation_types:
                correlation_result, race_count = self._calculate_rider_correlation(rr, corr_type, conn)
                # ... collect results ...
```

#### 2. Rider Correlation Calculation (`_calculate_rider_correlation`)
```python
def _calculate_rider_correlation(self, rider_result: Dict, corr_type: str, conn) -> Tuple[Optional[Dict], int]:
    # Get historical races for this rider
    history = self._get_rider_history(rider_id, before_date, race_type, corr_type, conn)
    
    # Calculate correlation matrix
    correlation_result = self._calculate_correlation_matrix(history)
    
    return correlation_result, len(history)
```

#### 3. Correlation Matrix Calculation (`_calculate_correlation_matrix`)
```python
def _calculate_correlation_matrix(self, history: List[Dict]) -> Optional[Dict]:
    # Extract points and competition IDs
    points = np.array([h['points'] for h in history])
    comp_ids = [h['competition_id'] for h in history]
    
    # Build feature matrix with NaN for missing competitions
    # Calculate per-percentile correlations
    # Return matrix + metadata
```

### Current Performance Characteristics

#### Processing Stats
- **Batch Size**: 50 competitions per batch
- **Checkpoint Frequency**: Every 10 batches
- **Memory Usage**: ~7-8GB peak
- **Processing Speed**: ~1,561 competitions remaining (originally 8,590)

#### Bottlenecks Identified
1. **Sequential rider processing**: Each rider processed one at a time
2. **Database I/O**: Multiple queries per rider for history
3. **Correlation calculation**: NumPy operations on large matrices

### Recent Improvements
- **Database connection management**: Single connection per batch (prevents "unable to open database file" errors)
- **Per-percentile missing data handling**: Uses NaN for missing percentiles instead of skipping riders
- **Feature name tracking**: Includes readable feature names in output
- **Data quality tracking**: Comprehensive metadata about data completeness

## Parallelization Plan: Option 2 - Parallel Rider Processing

### Strategy Overview
Parallelize the processing of individual riders within each batch while maintaining the existing batch structure and database connection management.

### Key Insights
1. **Rider independence**: Each rider's correlation calculation is completely independent
2. **Shared resources**: Race features cache is read-only and thread-safe
3. **Database safety**: Single connection per batch is already implemented
4. **Memory efficiency**: No data duplication required

### Implementation Details

#### 1. Import Requirements
```python
# Add to correlation_processor.py
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
```

#### 2. Configuration Update
```python
# config.py already has:
NUM_WORKERS: int = 4  # M1 Pro efficiency cores

# Add thread safety settings
THREAD_SAFETY_ENABLED: bool = True
MAX_THREADS_PER_BATCH: int = 4
```

#### 3. Core Parallelization Changes

##### A. Modify `_process_competition_batch`
```python
def _process_competition_batch(self, competitions: List[Dict]) -> List[Dict]:
    """Process a batch of competitions with parallel rider processing"""
    results = []
    comp_ids = [c['competition_id'] for c in competitions]
    
    # Get eligible rider results
    eligible_results = self._get_eligible_rider_results(comp_ids)
    
    logging.info(f"Processing {len(eligible_results)} eligible rider results in batch")
    
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
    
    # Process tasks in parallel
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
                
                if correlation_result is not None:
                    result_dict = {
                        'rider_result_id': task['rider_result']['rider_result_id'],
                        'competition_id': task['rider_result']['competition_id'],
                        'rider_id': task['rider_result']['rider_id'],
                        'correlation_type': task['correlation_type'],
                        'race_count': race_count
                    }
                    result_dict.update(correlation_result)
                    results.append(result_dict)
                    
            except Exception as e:
                logging.error(f"Error processing task {task['task_id']}: {e}")
                # Continue processing other tasks
    
    return results
```

##### B. Create Thread-Safe Correlation Method
```python
def _calculate_rider_correlation_parallel(self, rider_result: Dict, corr_type: str, task_id: str) -> Tuple[Optional[Dict], int]:
    """Thread-safe version of rider correlation calculation"""
    
    # Create thread-local database connection
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        
        # Set connection timeout and pragmas for thread safety
        conn.execute("PRAGMA busy_timeout = 30000")  # 30 second timeout
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA journal_mode = WAL")    # Write-ahead logging
        
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
```

#### 4. Thread Safety Considerations

##### A. Race Features Cache (Already Thread-Safe)
```python
# No changes needed - read-only access is thread-safe
# RaceFeaturesLoader.get_race_features() only reads from cache
# RaceFeaturesLoader.get_percentile_availability() only reads from cache
```

##### B. Database Connection Management
```python
# Each thread gets its own connection
# WAL mode allows concurrent reads
# Busy timeout prevents lock conflicts
```

##### C. Logging Thread Safety
```python
# Python's logging module is thread-safe by default
# No changes needed for existing logging statements
```

#### 5. Error Handling and Monitoring

##### A. Enhanced Error Handling
```python
def _process_competition_batch(self, competitions: List[Dict]) -> List[Dict]:
    # ... existing code ...
    
    failed_tasks = []
    successful_tasks = 0
    
    for future in as_completed(future_to_task):
        task = future_to_task[future]
        try:
            correlation_result, race_count = future.result()
            successful_tasks += 1
            # ... process result ...
        except Exception as e:
            failed_tasks.append({
                'task_id': task['task_id'],
                'error': str(e),
                'rider_result_id': task['rider_result']['rider_result_id']
            })
            logging.error(f"Error processing task {task['task_id']}: {e}")
    
    if failed_tasks:
        logging.warning(f"Failed to process {len(failed_tasks)} tasks out of {len(tasks)}")
        # Optionally save failed tasks for retry
    
    logging.info(f"Successfully processed {successful_tasks}/{len(tasks)} tasks")
```

##### B. Performance Monitoring
```python
# Add to _log_progress method
def _log_progress(self, batch_idx: int, comp_batch: List[Dict], batch_start: datetime):
    # ... existing code ...
    
    # Add parallel processing stats
    total_tasks = len(comp_batch) * 3  # Estimated correlation types per competition
    throughput = total_tasks / processing_time if processing_time > 0 else 0
    
    logging.info(f"Parallel processing throughput: {throughput:.1f} tasks/second")
```

### Performance Expectations

#### Expected Speed Improvements
- **Single-threaded**: ~1 core utilization
- **4-thread parallel**: ~4 core utilization
- **Expected speedup**: 3-4x faster processing
- **Remaining 1,561 competitions**: Complete in ~25-40% of current time

#### Resource Impact
- **Memory**: Minimal increase (each thread has small connection overhead)
- **CPU**: Full utilization of 4 cores
- **Database**: WAL mode handles concurrent reads efficiently

### Implementation Steps

#### Phase 1: Preparation (15 minutes)
1. **Add imports**: `ThreadPoolExecutor`, `as_completed`, `threading`
2. **Update config**: Add thread safety settings
3. **Test database**: Verify WAL mode works correctly

#### Phase 2: Core Implementation (30 minutes)
1. **Create parallel method**: `_calculate_rider_correlation_parallel`
2. **Modify batch processing**: Add ThreadPoolExecutor to `_process_competition_batch`
3. **Add error handling**: Robust exception handling for failed tasks

#### Phase 3: Testing (15 minutes)
1. **Small batch test**: Process 1-2 batches to verify functionality
2. **Performance verification**: Monitor CPU usage and throughput
3. **Data integrity check**: Verify results match single-threaded version

#### Phase 4: Deployment (5 minutes)
1. **Resume processing**: Continue from current checkpoint
2. **Monitor performance**: Watch for thread contention or errors
3. **Validate checkpoints**: Ensure checkpointing still works correctly

### Risk Mitigation

#### Potential Issues
1. **Database lock contention**: Mitigated by WAL mode and timeouts
2. **Memory pressure**: Monitored by existing MemoryManager
3. **Thread deadlocks**: Prevented by independent database connections
4. **Error propagation**: Handled with comprehensive exception catching

#### Rollback Plan
- **Immediate**: Set `NUM_WORKERS = 1` to disable parallelization
- **Code rollback**: Revert to single-threaded `_process_competition_batch`
- **Data integrity**: Parallel processing doesn't affect database schema

### Testing Strategy

#### Unit Tests
```python
def test_parallel_processing():
    # Test with small batch
    # Compare results with single-threaded
    # Verify data quality metrics
    # Check checkpoint functionality
```

#### Integration Tests
```python
def test_full_batch_parallel():
    # Process complete batch
    # Verify all correlation types
    # Check database integrity
    # Validate performance improvement
```

### Success Metrics
- **Processing speed**: 3-4x improvement in competitions/hour
- **CPU utilization**: ~80-90% across 4 cores
- **Error rate**: <1% failed tasks
- **Data integrity**: 100% match with single-threaded results
- **Memory usage**: <10% increase from baseline

### Future Enhancements
1. **Dynamic thread scaling**: Adjust workers based on batch size
2. **Correlation-level parallelization**: Parallelize within correlation calculation
3. **Async I/O**: Use asyncio for database operations
4. **Distributed processing**: Scale across multiple machines