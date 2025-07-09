# optimized_feature_builder.py

Fast feature builder for bulk dataset generation using batch processing and caching optimizations.

## Classes

### OptimizedFeatureBuilder

Fast feature builder using batch processing and caching for generating features for multiple rider-competition pairs efficiently.

#### Constructor
```python
OptimizedFeatureBuilder(db_path: str)
```
- **db_path**: Path to the SQLite database

#### Methods

##### build_bulk_dataset_fast
```python
build_bulk_dataset_fast(rider_competition_pairs: List[Tuple[int, int]], 
                        cutoff_date: Optional[str] = None,
                        use_parallel: bool = True,
                        max_workers: int = None) -> pd.DataFrame
```
Build features for multiple pairs using optimized batch processing.

- **rider_competition_pairs**: List of (rider_id, competition_id) tuples
- **cutoff_date**: Optional cutoff date for experience calculation  
- **use_parallel**: Whether to use parallel processing
- **max_workers**: Number of parallel workers (None = auto)
- **Returns**: DataFrame with all feature vectors

## Key Optimizations

1. **Batch Database Queries**: Pre-loads all rider histories, competition features, and rider results in bulk
2. **Caching**: Stores rider histories and competition features to avoid repeated database hits
3. **Parallel Processing**: Processes pairs in parallel batches for faster computation
4. **Efficient Data Structures**: Uses temporary tables and optimized queries for faster lookups

## Performance Benefits

- Eliminates individual database queries for each pair
- Reduces database connection overhead
- Enables parallel processing of feature calculations
- Provides significant speedup over sequential processing

## Usage Example

```python
from optimized_feature_builder import OptimizedFeatureBuilder

db_path = "database/database/cycling_races.db"
builder = OptimizedFeatureBuilder(db_path)

# List of (rider_id, competition_id) pairs
pairs = [(1001, 2001), (1002, 2002), ...]

# Generate features with optimization
result = builder.build_bulk_dataset_fast(
    pairs, 
    cutoff_date="2010-12-31",
    use_parallel=True
)
```

## Compatibility

- Generates identical output to original `FeatureBuilder.build_bulk_dataset()`
- Maintains same column names and data structure
- Can be used as drop-in replacement for bulk operations
- Original `FeatureBuilder` remains available for single-pair predictions