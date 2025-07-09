# dataset_generator.py

Integration module for generating training datasets for the global rider performance models using FeatureBuilder.

## Overview

This module orchestrates dataset creation by:
1. Finding relevant rider-competition pairs
2. Using FeatureBuilder to get complete features for each pair
3. Splitting results into GC and Stage/One-day datasets
4. Providing utilities for backtesting and saving datasets

## Classes

### DatasetGenerator

Generates training datasets for the global rider performance models.

#### Methods

##### `__init__(db_path: str)`
Initialize the dataset generator.

**Parameters:**
- `db_path` (str): Path to the SQLite database

##### `generate_datasets(cutoff_date: str, min_results: int = 5, min_uci_points: int = 0, target_variable: str = 'uci_points_actual') -> Dict[str, pd.DataFrame]`
Generate both training datasets for the global models.

**Parameters:**
- `cutoff_date` (str): Date cutoff in 'YYYY-MM-DD' format
- `min_results` (int): Minimum number of results required for a rider to be included (default: 5)
- `min_uci_points` (int): Minimum UCI points threshold for filtering (default: 0)
- `target_variable` (str): Target variable to use (default: 'uci_points_actual')

**Returns:**
- `Dict[str, pd.DataFrame]`: Dictionary with 'gc_dataset' and 'stage_one_day_dataset' keys

##### `get_feature_columns(dataset: pd.DataFrame, competition_type: str) -> Dict[str, List[str]]`
Get the feature columns for a specific dataset, categorized by type.

**Parameters:**
- `dataset` (pd.DataFrame): The dataset to analyze
- `competition_type` (str): 'gc' or 'stage_one_day'

**Returns:**
- `Dict[str, List[str]]`: Dictionary with keys:
  - 'race_features': Race-specific features (rf_*)
  - 'race_kind_features': Race clustering features (rkf_*)
  - 'experience_features': Rider experience features
  - 'metadata_features': Non-feature columns
  - 'target_features': Target variable columns

##### `get_feature_summary(datasets: Dict[str, pd.DataFrame]) -> Dict`
Get summary information about the generated datasets.

**Parameters:**
- `datasets` (Dict[str, pd.DataFrame]): Dictionary containing the generated datasets

**Returns:**
- `Dict`: Summary statistics including feature counts, target stats, and data distributions

##### `save_datasets(datasets: Dict[str, pd.DataFrame], output_dir: str = "rider_performance/datasets")`
Save the generated datasets to CSV files with timestamps.

**Parameters:**
- `datasets` (Dict[str, pd.DataFrame]): Dictionary containing the datasets
- `output_dir` (str): Directory to save the datasets (default: "rider_performance/datasets")

##### `generate_backtest_datasets(test_years: List[int] = [2022, 2023, 2024], min_results: int = 5) -> Dict[int, Dict[str, pd.DataFrame]]`
Generate datasets for backtesting on specific years.

**Parameters:**
- `test_years` (List[int]): List of years to generate test datasets for
- `min_results` (int): Minimum number of results required for a rider

**Returns:**
- `Dict[int, Dict[str, pd.DataFrame]]`: Nested dictionary with structure:
  ```
  {
      year: {
          'train_gc': DataFrame,
          'train_stage_one_day': DataFrame,
          'test_gc': DataFrame,
          'test_stage_one_day': DataFrame
      }
  }
  ```

## Usage Examples

### Basic Dataset Generation
```python
from dataset_generator import DatasetGenerator

db_path = "database/database/cycling_races.db"
generator = DatasetGenerator(db_path)

# Generate datasets up to end of 2023
datasets = generator.generate_datasets(
    cutoff_date="2023-12-31",
    min_results=10,
    target_variable='uci_points_actual'
)

gc_data = datasets['gc_dataset']
stage_one_day_data = datasets['stage_one_day_dataset']

print(f"GC dataset: {len(gc_data)} results")
print(f"Stage/One-day dataset: {len(stage_one_day_data)} results")
```

### Analyzing Generated Datasets
```python
# Get feature breakdown
summary = generator.get_feature_summary(datasets)

for dataset_name, stats in summary.items():
    print(f"\n{dataset_name}:")
    print(f"  Total features: {stats['feature_counts']['total_features']}")
    print(f"  Riders: {stats['num_riders']}")
    print(f"  Mean UCI points: {stats['target_stats']['uci_points_actual']['mean']:.2f}")

# Get specific feature columns
gc_features = generator.get_feature_columns(gc_data, 'gc')
print(f"GC race features: {gc_features['race_features']}")
print(f"Experience features: {gc_features['experience_features']}")
```

### Backtesting Setup
```python
# Generate train/test splits for multiple years
backtest_data = generator.generate_backtest_datasets(
    test_years=[2022, 2023, 2024],
    min_results=10
)

# Access specific year's data
data_2023 = backtest_data[2023]
train_gc = data_2023['train_gc']  # Training data up to 2022-12-31
test_gc = data_2023['test_gc']    # Test data from 2023

print(f"2023 GC - Train: {len(train_gc)}, Test: {len(test_gc)}")
```

### Saving Datasets
```python
# Save to CSV files
generator.save_datasets(datasets, output_dir="my_datasets")

# Files will be saved as:
# - gc_dataset_20240115_143022.csv
# - stage_one_day_dataset_20240115_143022.csv
```

### Filtering Low-Value Results
```python
# Exclude results with 0 UCI points
datasets = generator.generate_datasets(
    cutoff_date="2023-12-31",
    min_results=10,
    min_uci_points=1,  # Exclude 0-point results
    target_variable='uci_points_actual'
)
```

### Using Proportional Points
```python
# Generate datasets using proportional UCI points as target
datasets = generator.generate_datasets(
    cutoff_date="2023-12-31",
    min_results=10,
    target_variable='uci_points_proportional'
)
```

## Key Features

1. **Clean Architecture**: Uses FeatureBuilder internally for consistent feature extraction
2. **Efficient Processing**: Bulk processes rider-competition pairs
3. **Flexible Filtering**: Filter by minimum results, UCI points, and date ranges
4. **Backtesting Support**: Built-in train/test split generation for multiple years
5. **Feature Organization**: Automatically categorizes features by type
6. **Comprehensive Summary**: Detailed statistics about generated datasets

## Performance Considerations

- Processing time scales with number of rider-competition pairs
- Typical performance: ~10-20 pairs per second
- Memory usage depends on date range and rider filtering
- Consider using higher `min_results` values for faster processing

## Integration with ML Pipeline

```python
# Example ML pipeline integration
from dataset_generator import DatasetGenerator
from sklearn.ensemble import GradientBoostingRegressor

# Generate datasets
generator = DatasetGenerator(db_path)
datasets = generator.generate_datasets("2023-12-31", min_results=10)

# Get feature columns
gc_features = generator.get_feature_columns(datasets['gc_dataset'], 'gc')
feature_cols = (gc_features['race_features'] + 
                gc_features['race_kind_features'] + 
                gc_features['experience_features'])

# Prepare for training
gc_data = datasets['gc_dataset']
X_train = gc_data[feature_cols]
y_train = gc_data['uci_points_actual']

# Train model
model = GradientBoostingRegressor()
model.fit(X_train, y_train)
```