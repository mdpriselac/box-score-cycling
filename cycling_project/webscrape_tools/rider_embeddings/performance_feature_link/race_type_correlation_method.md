# Race Type Correlation Method

Module for calculating race-type-specific correlations between rider performance and race features.

## Class: RaceTypeCorrelationCalculator

Extends `PerformanceFeatureLinkBase` to calculate separate correlations for different race types (GC, stage, one-day, stage/one-day combined, and all races).

### Constructor

```python
RaceTypeCorrelationCalculator(
    db_path: str,
    min_races_all: int = 35,
    min_races_stage: int = 25,
    min_races_one_day: int = 15,
    min_races_gc: int = 10
)
```

**Parameters:**
- `db_path`: Path to the cycling races database
- `min_races_all`: Minimum races required for all-race correlations (default: 35)
- `min_races_stage`: Minimum races required for stage correlations (default: 25)
- `min_races_one_day`: Minimum races required for one-day correlations (default: 15)
- `min_races_gc`: Minimum races required for GC correlations (default: 10)

### Methods

#### calculate_feature_relationships

```python
calculate_feature_relationships(
    rider_result_id: int,
    lookback_date: str,
    feature_tables: List[str]
) -> Dict[str, Any]
```

Calculate correlations between rider performance and race features, segmented by race type.

**Parameters:**
- `rider_result_id`: ID from the rider_results table
- `lookback_date`: Date string (YYYY-MM-DD) to calculate history up to
- `feature_tables`: List of race_features_N tables to analyze (e.g., ['race_features_70', 'race_features_80'])

**Returns:**
Dictionary with structure:
```python
{
    'rider_result_id': int,
    'feature_correlations': {
        'gc': {
            'race_features_70': {
                'variance_normalized': float,
                'gini_coefficient': float,
                # ... all other features
            },
            'race_features_80': {...}
        },
        'stage': {...},
        'one_day': {...},
        'stage_one_day': {...},
        'all': {...}
    },
    'metadata': {
        'n_races': {
            'gc': int,
            'stage': int,
            'one_day': int,
            'stage_one_day': int,
            'all': int
        },
        'method': 'race_type_correlation',
        'calculation_date': datetime,
        'warnings': List[str]
    }
}
```

#### batch_calculate

```python
batch_calculate(
    rider_result_ids: List[int],
    feature_tables: List[str]
) -> List[Dict[str, Any]]
```

Calculate correlations for multiple rider results efficiently.

**Parameters:**
- `rider_result_ids`: List of rider_result IDs to process
- `feature_tables`: List of race_features_N tables to analyze

**Returns:**
List of correlation results for each rider_result_id

#### get_race_type_summary

```python
get_race_type_summary(
    rider_id: int,
    lookback_date: str
) -> Dict[str, int]
```

Get a summary of race counts by type for a rider up to a specific date.

**Parameters:**
- `rider_id`: The rider's ID
- `lookback_date`: Date string (YYYY-MM-DD) to look back from

**Returns:**
Dictionary mapping race type to count:
```python
{
    'gc': 15,
    'stage': 45,
    'one_day': 23,
    'stage_one_day': 68,
    'all': 83
}
```

## Race Type Definitions

The calculator uses the following race type categories:

- **gc**: General Classification races only
- **stage**: Stage races only
- **one_day**: One-day races only
- **stage_one_day**: Combined stage and one-day races
- **all**: All race types combined

## Usage Example

```python
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator

# Initialize calculator with custom minimums
calculator = RaceTypeCorrelationCalculator(
    db_path="database/database/cycling_races.db",
    min_races_gc=8,  # Lower minimum for GC races
    min_races_all=40  # Higher minimum for all races
)

# Calculate correlations for a single rider result
result = calculator.calculate_feature_relationships(
    rider_result_id=12345,
    lookback_date="2023-06-01",
    feature_tables=['race_features_70', 'race_features_80', 'race_features_90']
)

# Access correlations for specific race type and percentile
gc_correlations = result['feature_correlations']['gc']['race_features_80']
stage_correlations = result['feature_correlations']['stage']['race_features_80']

# Check race counts
race_counts = result['metadata']['n_races']
print(f"GC races: {race_counts['gc']}")
print(f"Stage races: {race_counts['stage']}")

# Process multiple riders
rider_ids = [12345, 12346, 12347]
results = calculator.batch_calculate(rider_ids, ['race_features_70', 'race_features_80'])
```

## Key Features

1. **Race Type Segmentation**: Automatically segments rider history into different race types
2. **Flexible Minimums**: Different minimum race requirements for each race type
3. **Comprehensive Output**: Returns correlations for all race types in a single call
4. **Efficient Batch Processing**: Process multiple riders with optimized database queries
5. **Detailed Metadata**: Includes race counts and warnings for each race type

## Notes

- Correlations are only calculated if the rider has sufficient history for each race type
- The `stage_one_day` category uses the same minimum as `one_day` races
- Warnings are generated for race types with insufficient data
- Uses Spearman correlation for all calculations
- Handles missing data and zero-variance features appropriately