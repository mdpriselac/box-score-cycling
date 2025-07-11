# PerformanceFeatureLinkBase

Abstract base class for linking rider performance to race features.

## Class: PerformanceFeatureLinkBase

### Constructor
```python
PerformanceFeatureLinkBase(db_path: str)
```
- `db_path`: Path to the cycling races database

### Abstract Methods

#### calculate_feature_relationships
```python
calculate_feature_relationships(
    rider_result_id: int,
    lookback_date: str,
    feature_tables: List[str]
) -> Dict[str, Any]
```
Must be implemented by all subclasses to calculate performance-feature relationships.

**Arguments:**
- `rider_result_id`: ID from the rider_results table
- `lookback_date`: Date string (YYYY-MM-DD) to calculate history up to
- `feature_tables`: List of race_features_N tables to analyze (e.g., ['race_features_100', 'race_features_80'])

**Returns:**
Dictionary with structure:
```python
{
    'rider_result_id': int,
    'feature_correlations': {
        'race_features_100': {
            'variance_normalized': float,
            'gini_coefficient': float,
            # ... all other features
        },
        'race_features_80': {...}
    },
    'metadata': {
        'n_races': int,  # number of historical races used
        'method': str,   # name of the method used
        'calculation_date': datetime,
        'warnings': List[str]  # any warnings or issues
    }
}
```

### Helper Methods

#### get_connection
```python
get_connection() -> sqlite3.Connection
```
Returns a database connection.

#### get_rider_history
```python
get_rider_history(rider_id: int, lookback_date: str) -> List[Dict[str, Any]]
```
Get historical race results for a rider up to a specific date.

#### get_race_features
```python
get_race_features(competition_ids: List[int], feature_table: str) -> Dict[int, Dict[str, float]]
```
Get race features for competitions from a specific feature table.

#### validate_feature_tables
```python
validate_feature_tables(feature_tables: List[str]) -> List[str]
```
Validate that the requested feature tables exist in the database.