# ParquetStorage

Utilities for managing parquet-based correlation data storage.

## Class: ParquetStorage

### Constructor
```python
ParquetStorage(data_dir: str = "correlation_data")
```
- `data_dir`: Directory containing parquet files

### Storage Management Methods

#### get_storage_stats
```python
get_storage_stats() -> Dict[str, Any]
```
Get statistics about stored correlation data including file count, total size, and record estimates.

#### merge_batches
```python
merge_batches(
    output_file: str = "merged_correlations.parquet",
    batch_numbers: Optional[List[int]] = None,
    delete_originals: bool = False
) -> Path
```
Merge multiple batch files into a single parquet file.

**Arguments:**
- `output_file`: Name for merged file
- `batch_numbers`: Specific batch numbers to merge (None = all)
- `delete_originals`: Whether to delete original batch files

#### partition_by_percentile
```python
partition_by_percentile(
    source_file: Optional[str] = None,
    output_dir: str = "partitioned"
) -> Path
```
Partition correlation data by percentile for efficient querying.

**Returns:** Path to partitioned dataset

#### optimize_storage
```python
optimize_storage(
    source_pattern: str = "correlations_batch_*.parquet",
    chunk_size: int = 10,
    compression: str = 'snappy'
) -> List[Path]
```
Optimize storage by merging small batch files into larger chunks.

### Data Analysis Methods

#### create_feature_index
```python
create_feature_index(source_file: Optional[str] = None) -> Dict[str, List[str]]
```
Create an index of available features per percentile.

**Returns:** Dictionary mapping percentile to list of features

#### validate_data
```python
validate_data(sample_size: int = 1000) -> Dict[str, Any]
```
Validate stored correlation data by checking samples.

**Returns:** Validation report with:
- `valid`: Whether data passes all checks
- `issues`: List of any issues found
- `summary`: Data statistics

### Usage Example
```python
# Initialize storage manager
storage = ParquetStorage("correlation_data")

# Get storage statistics
stats = storage.get_storage_stats()
print(f"Total files: {stats['total_files']}")
print(f"Total size: {stats['total_size_mb']:.2f} MB")

# Merge all batches
merged_path = storage.merge_batches()

# Create partitioned dataset for efficient queries
partitioned_path = storage.partition_by_percentile()

# Validate data quality
validation = storage.validate_data()
if validation['valid']:
    print("Data validation passed!")
```