# Parallelization Implementation Plan

## Phase 1: Database Query Optimization (Foundation)
**Priority: Critical** - Must implement first as it benefits all subsequent optimizations

### 1.1 Batch Database Loading
**Target**: Eliminate per-rider database queries

```python
class BatchedDatabaseLoader:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._rider_histories_cache = {}
        self._race_features_cache = {}
    
    def preload_rider_histories(self, rider_ids: List[int], max_lookback_date: str):
        """Load all rider histories in one query"""
        # Single query to get ALL rider histories at once
        # Group by rider_id in memory
        
    def preload_race_features(self, feature_tables: List[str]):
        """Load all race features into memory"""
        # One query per feature table to load everything
        # Index by competition_id for O(1) lookup
```

**Implementation Steps:**
1. Create batched loader class
2. Modify base.py to use cached data instead of individual queries  
3. Pre-load data at start of correlation generation
4. **Expected Speedup**: 10-20x reduction in database I/O

### 1.2 Connection Pooling
```python
from multiprocessing import Manager
import sqlite3
from queue import Queue

class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 8):
        self.pool = Queue(maxsize=pool_size)
        for _ in range(pool_size):
            self.pool.put(sqlite3.connect(db_path))
```

## Phase 2: Parallel Correlation Generation
**Priority: High** - Biggest single performance gain

### 2.1 Worker Process Architecture
```python
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed

class ParallelCorrelationGenerator:
    def __init__(self, db_path: str, n_workers: int = None):
        self.n_workers = n_workers or mp.cpu_count()
        self.db_path = db_path
    
    def generate_correlations_parallel(self, rider_result_ids: List[int], 
                                     feature_tables: List[str]):
        # Split riders into chunks for workers
        chunk_size = max(1, len(rider_result_ids) // (self.n_workers * 4))
        rider_chunks = [rider_result_ids[i:i+chunk_size] 
                       for i in range(0, len(rider_result_ids), chunk_size)]
        
        # Process chunks in parallel
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = [
                executor.submit(self._process_rider_chunk, chunk, feature_tables)
                for chunk in rider_chunks
            ]
            
            # Collect results as they complete
            for future in as_completed(futures):
                yield future.result()
```

### 2.2 Worker Function Design
```python
def process_rider_chunk(chunk_data: dict) -> List[dict]:
    """Worker function - must be pickleable"""
    rider_ids = chunk_data['rider_ids']
    feature_tables = chunk_data['feature_tables']
    db_path = chunk_data['db_path']
    
    # Each worker gets its own calculator instance
    calculator = RaceTypeCorrelationCalculator(db_path)
    
    # Pre-load data for this chunk (if using batched approach)
    # Or use connection pooling
    
    results = []
    for rider_id in rider_ids:
        try:
            result = calculator.calculate_feature_relationships(...)
            results.append(result)
        except Exception as e:
            # Handle errors gracefully
            results.append({'rider_result_id': rider_id, 'error': str(e)})
    
    return results
```

### 2.3 Shared Memory Optimization (Advanced)
```python
import numpy as np
from multiprocessing import shared_memory

class SharedMemoryCorrelationGenerator:
    """For very large datasets - share race features across processes"""
    
    def create_shared_arrays(self, race_features: dict):
        # Create shared numpy arrays for race features
        # All workers can read from shared memory
        # Eliminates memory duplication across processes
        pass
```

**Implementation Steps:**
1. Refactor correlation calculator to be process-safe
2. Implement chunk-based parallel processing
3. Add progress tracking across processes
4. Handle checkpointing with parallel writes
5. **Expected Speedup**: 4-12x depending on CPU cores

## Phase 3: Parallel Race Type Processing
**Priority: Medium** - Good gains for race type correlation method

### 3.1 Race Type Parallelization
```python
class ParallelRaceTypeCalculator:
    def calculate_feature_relationships_parallel(self, rider_result_id: int, 
                                               lookback_date: str, 
                                               feature_tables: List[str]):
        # Get rider history once
        rider_id = self._get_rider_id(rider_result_id)
        full_history = self.get_rider_history(rider_id, lookback_date)
        race_type_histories = self._segment_history_by_race_type(full_history)
        
        # Process race types in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:  # 5 race types
            futures = {
                executor.submit(self._process_race_type, race_type, history, feature_tables): race_type
                for race_type, history in race_type_histories.items()
            }
            
            feature_correlations = {}
            for future in as_completed(futures):
                race_type = futures[future]
                feature_correlations[race_type] = future.result()
        
        return {...}
```

### 3.2 Percentile Parallelization
```python
def _process_race_type_parallel(self, race_type: str, history: List[dict], 
                               feature_tables: List[str]):
    """Process all percentiles for a race type in parallel"""
    
    with ThreadPoolExecutor(max_workers=len(feature_tables)) as executor:
        futures = {
            executor.submit(self._calculate_table_correlations, history, table, race_type): table
            for table in feature_tables
        }
        
        race_type_correlations = {}
        for future in as_completed(futures):
            table = futures[future]
            correlations, warnings = future.result()
            race_type_correlations[table] = correlations
    
    return race_type_correlations
```

**Implementation Steps:**
1. Use ThreadPoolExecutor for I/O-bound race type processing
2. Parallelize within individual rider calculations
3. **Expected Speedup**: 2-4x for race type calculations

## Phase 4: Parallel Clustering Analysis
**Priority: Medium** - Good gains for feature selection

### 4.1 Parallel K-Means Evaluation
```python
class ParallelClusteringAnalyzer:
    def analyze_clustering_quality_parallel(self, correlation_results: List[dict], 
                                          percentile: str, k_range: List[int]):
        # Prepare data once
        correlation_matrix, rider_ids, feature_names = self.prepare_correlation_matrix(...)
        scaled_matrix = StandardScaler().fit_transform(correlation_matrix)
        
        # Parallel k-means evaluation
        with ProcessPoolExecutor(max_workers=min(len(k_range), mp.cpu_count())) as executor:
            futures = {
                executor.submit(self._evaluate_k_clustering, scaled_matrix, k, self.random_state): k
                for k in k_range
            }
            
            clustering_results = {}
            for future in as_completed(futures):
                k = futures[future]
                clustering_results[k] = future.result()
```

### 4.2 Parallel Percentile Analysis
```python
def compare_percentiles_parallel(self, correlation_results: List[dict], 
                               percentiles: List[str], k_range: List[int]):
    """Analyze all percentiles in parallel"""
    
    with ProcessPoolExecutor(max_workers=min(len(percentiles), mp.cpu_count())) as executor:
        futures = {
            executor.submit(self.analyze_clustering_quality, correlation_results, p, k_range): p
            for p in percentiles
        }
        
        percentile_analyses = {}
        for future in as_completed(futures):
            percentile = futures[future]
            percentile_analyses[percentile] = future.result()
```

**Implementation Steps:**
1. Parallelize k-means evaluation across different k values
2. Parallelize percentile analysis
3. Use process pools for CPU-intensive clustering
4. **Expected Speedup**: 3-6x for clustering analysis

## Phase 5: Vectorized Correlation Computation
**Priority: Medium** - Optimize core computation

### 5.1 Batch Correlation Calculation
```python
import numpy as np
from scipy.stats import spearmanr

class VectorizedCorrelationCalculator:
    def calculate_batch_correlations(self, points_matrix: np.ndarray, 
                                   features_matrix: np.ndarray) -> np.ndarray:
        """Calculate correlations for multiple rider-feature pairs at once"""
        
        # points_matrix: (n_riders, n_races)
        # features_matrix: (n_races, n_features)
        
        # Vectorized correlation computation
        correlations = np.zeros((points_matrix.shape[0], features_matrix.shape[1]))
        
        for i in range(features_matrix.shape[1]):
            for j in range(points_matrix.shape[0]):
                valid_mask = ~(np.isnan(points_matrix[j]) | np.isnan(features_matrix[:, i]))
                if np.sum(valid_mask) >= self.min_races:
                    corr, _ = spearmanr(points_matrix[j][valid_mask], 
                                       features_matrix[valid_mask, i])
                    correlations[j, i] = corr if not np.isnan(corr) else 0.0
        
        return correlations
```

### 5.2 Memory-Efficient Processing
```python
class StreamingCorrelationProcessor:
    """Process correlations in chunks to manage memory"""
    
    def process_in_chunks(self, rider_data: Iterator, chunk_size: int = 1000):
        for chunk in self._chunk_iterator(rider_data, chunk_size):
            # Process chunk in memory
            # Write results immediately
            # Free memory before next chunk
            pass
```

**Expected Speedup**: 2-5x for correlation computation

## Phase 6: Advanced GPU Acceleration (Optional)
**Priority: Low** - Only for very large datasets

### 6.1 GPU Correlation Computation
```python
import cupy as cp  # or PyTorch

class GPUCorrelationCalculator:
    def calculate_correlations_gpu(self, points_gpu: cp.ndarray, 
                                 features_gpu: cp.ndarray) -> cp.ndarray:
        """GPU-accelerated correlation calculation"""
        # Transfer data to GPU
        # Vectorized correlation computation on GPU
        # Transfer results back to CPU
        pass
```

**Assessment**: Only beneficial for:
- 10,000+ riders
- Large feature sets (100+ features)
- High-end GPU available

## Implementation Strategy

### Phase 1 (Week 1): Foundation
1. **Batch database loading** - Implement SharedDataLoader
2. **Connection pooling** - Add to base.py
3. **Test with existing pipeline** - Verify 10-20x I/O improvement

### Phase 2 (Week 2): Core Parallelization  
1. **Parallel correlation generation** - ProcessPoolExecutor implementation
2. **Chunk-based processing** - Handle large rider sets
3. **Progress tracking** - Maintain visibility across processes
4. **Error handling** - Graceful failure recovery

### Phase 3 (Week 3): Advanced Features
1. **Parallel race type processing** - ThreadPoolExecutor for I/O
2. **Parallel clustering** - ProcessPoolExecutor for CPU-intensive work
3. **Memory optimization** - Streaming where possible

### Phase 4 (Week 4): Polish & GPU (Optional)
1. **Vectorized computations** - Optimize core algorithms  
2. **GPU acceleration** - If dataset size justifies it
3. **Performance testing** - Benchmark against original

## Expected Overall Speedup
- **Conservative**: 10-25x total speedup
- **Optimistic**: 20-50x total speedup
- **Database I/O**: 10-20x improvement
- **Correlation generation**: 4-12x improvement  
- **Clustering analysis**: 3-6x improvement
- **Combined effect**: Multiplicative gains

## Risk Mitigation
1. **Backward compatibility** - Keep original sequential code as fallback
2. **Memory management** - Monitor memory usage with large datasets
3. **Process management** - Handle worker process failures gracefully
4. **Testing** - Extensive testing with different dataset sizes
5. **Checkpointing** - Maintain resume capability with parallel processing

This plan prioritizes the highest-impact optimizations first and provides a clear path to implementation while maintaining system reliability.