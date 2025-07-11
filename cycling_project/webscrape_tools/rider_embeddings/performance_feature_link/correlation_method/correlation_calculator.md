# CorrelationCalculator

Class for calculating Spearman correlations between rider performance and race features.

## Class: CorrelationCalculator

Inherits from: `PerformanceFeatureLinkBase`

### Constructor
```python
CorrelationCalculator(db_path: str, min_races: int = 5)
```
- `db_path`: Path to the cycling races database
- `min_races`: Minimum number of races required for correlation calculation (default: 5)

### Main Methods

#### calculate_feature_relationships
```python
calculate_feature_relationships(
    rider_result_id: int,
    lookback_date: str,
    feature_tables: List[str]
) -> Dict[str, Any]
```
Calculate correlations between rider performance and race features.

**Arguments:**
- `rider_result_id`: ID from the rider_results table
- `lookback_date`: Date string (YYYY-MM-DD) to calculate history up to
- `feature_tables`: List of race_features_N tables to analyze

**Returns:**
Dictionary containing:
- `rider_result_id`: The input rider result ID
- `feature_correlations`: Dict mapping each feature table to correlation values
- `metadata`: Including number of races, method name, calculation date, and warnings

#### batch_calculate
```python
batch_calculate(
    rider_result_ids: List[int],
    feature_tables: List[str]
) -> List[Dict[str, Any]]
```
Efficiently calculate correlations for multiple rider results.

**Arguments:**
- `rider_result_ids`: List of rider_result IDs to process
- `feature_tables`: List of race_features_N tables to analyze

**Returns:**
List of correlation results, one for each rider_result_id

### Key Features
- Uses Spearman correlation (robust to non-linear relationships)
- Handles missing data gracefully
- Requires minimum number of races for reliable correlations
- Separates correlations by race_features_N table for comparison
- Returns None for features with insufficient data or zero variance
- Provides detailed warnings for edge cases