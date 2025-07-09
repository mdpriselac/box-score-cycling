# rider_experience_features.py

Module for calculating rider experience features from rider history data.

## Overview

This module works as a **post-processing step** that takes the DataFrame output from RiderHistory and adds cumulative experience features based on chronological race history.

**Integration Flow:**
```
Database → RiderHistory → RiderExperienceFeatures → ML Model
```

The RiderHistory module already joins all necessary database tables and provides all basic features. This module adds cumulative experience metrics calculated from the chronologically sorted race history up to each race date.

## Classes

### RiderExperienceFeatures

Calculates cumulative experience features for rider results.

#### Methods

##### `__init__()`
Initialize the experience feature calculator.

##### `add_experience_features(rider_history_df: pd.DataFrame) -> pd.DataFrame`
Add experience features to rider history data.

**Required Input Columns:**
- `rider_id`: Rider identifier
- `competition_date`: Date of competition (for chronological sorting)
- `competition_type`: 'gc', 'stage', or 'one_day'
- `race_category`: 'wt', 'pro', or 'd1'
- `rider_age`: Age of rider at time of race
- `uci_points_actual`: Actual UCI points earned
- `uci_points_proportional`: Proportional UCI points earned
- `result_id`: Unique result identifier (for merging)

**New Columns Added:**
- `total_prior_races`: Total races completed before this race
- `prior_gc_races`: GC races completed before this race
- `prior_stage_races`: Stage races completed before this race
- `prior_one_day_races`: One-day races completed before this race
- `prior_wt_races`: WT races completed before this race
- `prior_pro_races`: Pro races completed before this race
- `prior_d1_races`: D1 races completed before this race
- `prior_wt_proportion`: Proportion of prior races that were WT level
- `total_prior_uci_points_actual`: Total actual UCI points earned before this race
- `total_prior_uci_points_proportional`: Total proportional UCI points earned before this race
- `rider_age_at_race`: Rider age at time of race (same as rider_age)

**Parameters:**
- `rider_history_df` (pd.DataFrame): DataFrame from RiderHistory.get_rider_history() or RiderHistory.get_all_rider_histories()

**Returns:**
- `pd.DataFrame`: Original DataFrame with additional experience feature columns

##### `get_feature_info() -> Dict`
Get information about the experience features.

**Returns:**
- `Dict`: Dictionary containing feature names and descriptions

## Functions

### `create_training_dataset(rider_history_df: pd.DataFrame) -> pd.DataFrame`
Convenience function to create a complete training dataset with experience features.

**Parameters:**
- `rider_history_df` (pd.DataFrame): DataFrame from RiderHistory methods

**Returns:**
- `pd.DataFrame`: Complete dataset ready for machine learning

## Usage Examples

### Basic Usage
```python
from rider_history import RiderHistory
from rider_experience_features import RiderExperienceFeatures

db_path = "database/database/cycling_races.db"
history = RiderHistory(db_path)

# Get rider history
rider_df = history.get_rider_history(rider_id=1000, cutoff_date="2023-12-31")

# Add experience features
experience_calc = RiderExperienceFeatures()
enhanced_df = experience_calc.add_experience_features(rider_df)

# Now enhanced_df has all original features plus experience features
print(f"Original columns: {len(rider_df.columns)}")
print(f"Enhanced columns: {len(enhanced_df.columns)}")
```

### Using Convenience Function
```python
from rider_history import RiderHistory
from rider_experience_features import create_training_dataset

db_path = "database/database/cycling_races.db"
history = RiderHistory(db_path)

# Get all riders with sufficient history
all_riders_df = history.get_all_rider_histories(
    cutoff_date="2023-12-31", 
    min_results=10
)

# Create complete training dataset
training_df = create_training_dataset(all_riders_df)

# Ready for machine learning
feature_columns = [col for col in training_df.columns 
                  if col.startswith(('rf_', 'rkf_', 'prior_', 'total_prior'))]
target_column = 'uci_points_actual'

X = training_df[feature_columns]
y = training_df[target_column]
```

### Analyzing Experience Progression
```python
# Look at how experience builds over time for a rider
rider_data = enhanced_df[enhanced_df['rider_id'] == 1000]

progression_cols = [
    'competition_date', 'competition_name', 'total_prior_races',
    'prior_wt_races', 'prior_wt_proportion', 'total_prior_uci_points_actual'
]

print("Experience progression:")
print(rider_data[progression_cols].head(10))
```

### Separating by Competition Type
```python
# Create separate datasets for the two global models
gc_data = enhanced_df[enhanced_df['competition_type'] == 'gc']
stage_one_day_data = enhanced_df[enhanced_df['competition_type'].isin(['stage', 'one_day'])]

# Each will have different race features but same experience features
gc_race_features = [col for col in gc_data.columns if col.startswith('rf_')]
stage_race_features = [col for col in stage_one_day_data.columns if col.startswith('rf_')]

# Common experience features for both models
experience_features = [col for col in enhanced_df.columns 
                      if col.startswith(('prior_', 'total_prior', 'rider_age'))]

print(f"GC race features: {len(gc_race_features)}")
print(f"Stage/One-day race features: {len(stage_race_features)}")
print(f"Common experience features: {len(experience_features)}")
```

## Key Features

- **Chronological Processing**: Processes each rider's results in chronological order
- **Cumulative Calculations**: Each race's experience features reflect only prior races
- **Database Integration**: Works seamlessly with RiderHistory output
- **Flexible Input**: Works with single rider or multi-rider datasets
- **Error Handling**: Validates required columns and handles missing data
- **Performance**: Efficient processing using pandas operations

## Important Notes

1. **Data Integrity**: The module ensures that experience features only include races that occurred before the current race date
2. **First Race Handling**: A rider's first race will have all experience features set to 0
3. **Column Validation**: Validates that all required columns from RiderHistory are present
4. **Memory Efficiency**: Processes riders individually to manage memory usage
5. **Integration**: Designed to work as a seamless post-processing step after RiderHistory

## Experience Feature Descriptions

- **total_prior_races**: Foundation experience metric
- **prior_*_races**: Experience by competition type (gc, stage, one_day) and race category (wt, pro, d1)
- **prior_wt_proportion**: Quality of experience metric (higher = more elite racing)
- **total_prior_uci_points_***: Performance-based experience metric
- **rider_age_at_race**: Age factor (already calculated in database)

These features capture the key aspects mentioned in the original system goals: rider age, rider experience (total and by type), and tour level experience proportions.