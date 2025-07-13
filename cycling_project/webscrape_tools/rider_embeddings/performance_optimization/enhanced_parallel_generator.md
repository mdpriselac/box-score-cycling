# EnhancedParallelCorrelationGenerator

Enhanced parallel correlation generator that pre-loads data for better performance and avoids database contention issues.

## Class: EnhancedParallelCorrelationGenerator

Inherits from ParallelCorrelationGenerator and adds optimized data loading strategies.

### Constructor
```python
EnhancedParallelCorrelationGenerator(
    db_path: str,
    output_dir: str = "correlation_data",
    batch_size: int = 100,
    min_races: int = 5,
    n_workers: int = None,
    preload_all_data: bool = True
)
```

### Main Methods

#### generate_sample_parallel_enhanced
```python
generate_sample_parallel_enhanced(
    sample_size: int = 1000,
    feature_tables: List[str] = None,
    output_name: str = "enhanced_parallel_sample",
    calculator_config: Dict[str, Any] = None
) -> None
```
Generate correlations for a sample using enhanced parallel processing with race type specific sampling.

**Arguments:**
- `sample_size`: Number of rider results to sample (distributed across race types)
- `feature_tables`: List of feature tables to analyze
- `output_name`: Name for output file
- `calculator_config`: Configuration for correlation calculator

**Features:**
- Uses race type specific filtering (same logic as full dataset mode)
- Distributes sample across all race types for representative sampling
- Only samples rider results that meet minimum race count requirements for each type
- Much more efficient than random sampling

#### generate_all_correlations_parallel_enhanced
```python
generate_all_correlations_parallel_enhanced(
    feature_tables: List[str] = None,
    limit: Optional[int] = None,
    resume: bool = True,
    calculator_type: str = 'race_type',
    calculator_config: Dict[str, Any] = None,
    checkpoint_interval: int = 10000
) -> None
```
Generate correlations for all eligible riders using enhanced parallel processing with memory-efficient chunking.

**Arguments:**
- `feature_tables`: List of feature tables to analyze
- `limit`: Optional limit on number of riders to process
- `resume`: Whether to resume from checkpoint
- `calculator_type`: Type of calculator ('race_type' or 'standard')
- `calculator_config`: Configuration for correlation calculator
- `checkpoint_interval`: Number of riders to process before saving checkpoint

### Key Features

1. **Pre-loaded Shared Data**: Loads all required data before parallel processing to avoid database contention
2. **Memory-Efficient Chunking**: Processes large datasets in manageable chunks
3. **Checkpoint/Resume**: Supports resuming interrupted runs
4. **Optimized for Race Type Analysis**: Special handling for race type correlation calculations

### Helper Functions

#### process_rider_chunk_with_shared_data
```python
process_rider_chunk_with_shared_data(chunk_data: Dict[str, Any]) -> List[Dict[str, Any]]
```
Worker function that processes riders using pre-loaded shared data instead of database queries.

#### calculate_correlations_from_shared_data
```python
calculate_correlations_from_shared_data(
    rider_result_id: int,
    feature_tables: List[str],
    shared_data: Dict[str, Any],
    calculator_config: Dict[str, Any]
) -> Dict[str, Any]
```
Calculate correlations using pre-loaded data without database access.