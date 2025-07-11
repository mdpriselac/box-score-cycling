# CorrelationDataGenerator

Class for generating rider performance correlation data and saving to parquet files.

## Class: CorrelationDataGenerator

### Constructor
```python
CorrelationDataGenerator(
    db_path: str,
    output_dir: str = "correlation_data",
    batch_size: int = 100,
    min_races: int = 5
)
```
- `db_path`: Path to the cycling database
- `output_dir`: Directory to save parquet files
- `batch_size`: Number of rider results to process per batch
- `min_races`: Minimum races required for correlation calculation

### Main Methods

#### generate_all_correlations
```python
generate_all_correlations(
    feature_tables: List[str] = None,
    limit: Optional[int] = None,
    resume: bool = True
)
```
Generate correlations for all eligible rider results.

**Arguments:**
- `feature_tables`: List of race_features_N tables to analyze (default: all)
- `limit`: Optional limit on number of rider results to process
- `resume`: Whether to resume from checkpoint (default: True)

**Features:**
- Batch processing with configurable batch size
- Checkpoint system for resuming interrupted runs
- Progress tracking with tqdm
- Error handling and logging
- Efficient parquet storage

#### generate_sample
```python
generate_sample(
    sample_size: int = 1000,
    feature_tables: List[str] = None,
    output_name: str = "sample"
)
```
Generate correlations for a random sample of rider results.

**Arguments:**
- `sample_size`: Number of rider results to sample
- `feature_tables`: List of feature tables to analyze
- `output_name`: Name for output file

### Output Format

#### Parquet Files
Each batch creates a parquet file with columns:
- `rider_result_id`: ID of the rider result
- `percentile`: Race features table (e.g., 'race_features_100')
- `feature`: Feature name
- `correlation`: Correlation value
- `n_races`: Number of races used for correlation
- `calculation_date`: When correlation was calculated

#### Metadata Files
- `checkpoint.json`: Progress tracking for resume capability
- `generation_metadata.json`: Information about the generation run
- `generation.log`: Detailed logs of the generation process

### Usage Example
```python
# Generate correlations for all riders
generator = CorrelationDataGenerator(
    db_path="database/database/cycling_races.db",
    output_dir="correlation_data",
    batch_size=100
)

# Full generation with all percentiles
generator.generate_all_correlations()

# Or generate a sample for testing
generator.generate_sample(sample_size=500)
```