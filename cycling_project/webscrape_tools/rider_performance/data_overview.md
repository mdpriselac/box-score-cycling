# Rider Performance Data Overview

## Overview

This document describes the structure and generation of training data for the global rider performance prediction models. The system generates two separate datasets for two global models:

1. **GC Model**: Trained on General Classification races
2. **Stage/One-day Model**: Trained on Stage and One-day races

## Data Generation Pipeline

```
Database Tables → RiderHistory → FeatureBuilder → DatasetGenerator → ML-Ready Datasets
```

### Key Components

1. **FeatureBuilder**: Single-entry point that combines all features for a rider-competition pair
2. **DatasetGenerator**: Orchestrates bulk dataset creation and train/test splits

## Feature Structure

Each row in the dataset represents a single rider result with the following feature categories:

### 1. Race Features (rf_*)
These are race-specific statistical features calculated from finish time distributions.

**GC races** (8 features from race_features_70):
- `rf_variance_absolute`
- `rf_winning_time` 
- `rf_largest_group_size`
- `rf_time_gap_evenness_metric`
- `rf_clumpiness_score`
- `rf_riders_in_groups`
- `rf_total_groups`
- `rf_skewness_absolute`

**Stage/One-day races** (14 features from race_features_40):
- `rf_clumpiness_score`
- `rf_biggest_group_metric`
- `rf_avg_group_size`
- `rf_selection_metric`
- `rf_gini_coefficient`
- `rf_std_group_size`
- `rf_proportion_in_groups`
- `rf_time_gap_evenness_metric`
- `rf_total_groups`
- `rf_std_deviation_normalized`
- `rf_total_race_duration`
- `rf_50th_percentile_gap`
- `rf_variance_absolute`
- `rf_skewness_normalized`

### 2. Race Kind Features (rkf_*)
Clustering-based race classification features (same for all competition types):
- `rkf_cluster_label`: Which cluster (0, 1, or 2) the race belongs to
- `rkf_local_density`: How typical the race is within its cluster
- `rkf_boundary_distance`: Distance to nearest different cluster
- `rkf_cluster_0`, `rkf_cluster_1`, `rkf_cluster_2`: One-hot encoding
- `rkf_distance_to_cluster_0`, `rkf_distance_to_cluster_1`, `rkf_distance_to_cluster_2`: Distances to each cluster center

### 3. Experience Features
Cumulative metrics calculated from the rider's history **up to but not including** the current race:
- `total_prior_races`: Total number of races completed before this race
- `prior_gc_races`, `prior_stage_races`, `prior_one_day_races`: By competition type
- `prior_wt_races`, `prior_pro_races`, `prior_d1_races`: By race category
- `prior_wt_proportion`: Fraction of prior races that were WorldTour level
- `total_prior_uci_points_actual`: Cumulative actual UCI points earned
- `total_prior_uci_points_proportional`: Cumulative proportional UCI points earned
- `rider_age_at_race`: Rider's age at time of race

### 4. Metadata (not features)
- `rider_id`, `rider_name`: Rider identification
- `competition_id`, `competition_name`, `competition_type`: Competition details
- `race_name`, `race_category`, `race_year`: Race information
- `competition_date`: Date of the competition
- `place`: Finishing position

### 5. Target Variables
- `uci_points_actual`: Official UCI points based on 2026 scheme
- `uci_points_proportional`: Alternative point system with deeper coverage

## Dataset Characteristics

### Typical Dataset Sizes
- **Full dataset (2023)**: ~900,000+ results from ~7,000 riders
- **Filtered dataset (min 10 results)**: ~500,000 results from ~3,000 riders
- **GC races**: ~15-20% of total results
- **Stage races**: ~60-65% of total results  
- **One-day races**: ~20-25% of total results

### Feature Counts by Model
- **GC Model**: 8 race features + 9 race kind features + 11 experience features = 28 total features
- **Stage/One-day Model**: 14 race features + 9 race kind features + 11 experience features = 34 total features

### Target Variable Distribution
- **Zero points**: ~80-90% of results (only top finishers earn points)
- **Non-zero points**: ~10-20% of results
- **Point range**: 0-1300 (actual), 0-1300 (proportional)
- **Highly skewed**: Most results have 0 points, few have high points

## Important Considerations for Model Design

### 1. Imbalanced Target
The vast majority of results earn 0 UCI points. Models should account for this through:
- Appropriate loss functions (e.g., zero-inflated models)
- Sampling strategies
- Evaluation metrics beyond simple RMSE

### 2. Different Feature Sets
GC and Stage/One-day models have different race features but share:
- Same race kind features
- Same experience features
- Same target variables

### 3. Temporal Nature
- Experience features are cumulative up to race date
- Proper train/test splits must respect temporal ordering
- Backtesting should use historical cutoffs for experience calculation

### 4. Missing Features
Some races may have NULL race features due to:
- Insufficient finishers for statistical calculations
- Missing data in source
- Models should handle missing features appropriately

### 5. Feature Scales
Features have different scales:
- Time-based features (seconds)
- Count features (number of races)
- Proportions (0-1)
- Points (0-1300)
- Consider feature normalization/standardization

## Data Access Examples

### Getting Training Data
```python
from dataset_generator import DatasetGenerator

generator = DatasetGenerator(db_path)
datasets = generator.generate_datasets(
    cutoff_date="2023-12-31",
    min_results=10,
    target_variable='uci_points_actual'
)

gc_data = datasets['gc_dataset']
stage_one_day_data = datasets['stage_one_day_dataset']
```

### Preparing Features for Training
```python
# Get feature columns
feature_info = generator.get_feature_columns(gc_data, 'gc')
feature_cols = (feature_info['race_features'] + 
                feature_info['race_kind_features'] + 
                feature_info['experience_features'])

# Prepare training data
X_train = gc_data[feature_cols]
y_train = gc_data['uci_points_actual']

# Check for missing values
print(f"Missing values per feature:")
print(X_train.isnull().sum())
```

### Making Predictions for New Races
```python
from feature_builder import FeatureBuilder

builder = FeatureBuilder(db_path)

# Get features for a single prediction
features = builder.get_prediction_features(
    rider_id=1234,
    competition_id=5678,
    cutoff_date="2024-06-14"  # Day before the race
)

# Extract feature vector
if features['competition_type'] == 'gc':
    model = gc_model
    feature_cols = gc_feature_columns
else:
    model = stage_one_day_model
    feature_cols = stage_one_day_feature_columns

X = pd.DataFrame([features])[feature_cols]
prediction = model.predict(X)[0]
```

## Backtesting Structure

For each test year, the system provides:
- **Training data**: All results up to Dec 31 of previous year
- **Test data**: Results from the test year with experience calculated up to training cutoff

Example for 2023 testing:
- Train: All results up to 2022-12-31
- Test: 2023 results with experience as of 2022-12-31

This ensures no data leakage and realistic evaluation.

## Recommended Next Steps

1. **Exploratory Data Analysis**: Understand feature distributions and correlations
2. **Feature Engineering**: Consider interactions, transformations, or additional features
3. **Model Selection**: Choose algorithms that handle zero-inflated targets well
4. **Evaluation Strategy**: Define metrics that capture both classification (0 vs non-0) and regression (point values) performance
5. **Rider Characterization**: Use model predictions across race types to identify rider specialties