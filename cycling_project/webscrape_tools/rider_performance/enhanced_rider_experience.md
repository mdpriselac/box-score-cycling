# enhanced_rider_experience.py

Advanced rider experience feature calculator that provides sophisticated rider representations for global model performance.

## Classes

### EnhancedRiderExperience

Advanced rider experience feature calculator providing sophisticated rider representations including performance-based experience metrics and rider-race interaction profiles.

#### Constructor
```python
EnhancedRiderExperience(race_feature_columns: Optional[List[str]] = None,
                       race_kind_feature_columns: Optional[List[str]] = None)
```
- **race_feature_columns**: List of race feature column names (rf_*) - auto-detected if None
- **race_kind_feature_columns**: List of race kind feature column names (rkf_*) - auto-detected if None

#### Methods

##### add_enhanced_experience_features
```python
add_enhanced_experience_features(rider_history_df: pd.DataFrame) -> pd.DataFrame
```
Add comprehensive experience features to rider history data.

- **rider_history_df**: DataFrame with rider history including race features
- **Returns**: DataFrame with enhanced experience features added

## Enhanced Feature Categories

### 1. Points-Based Experience Features (by Competition Type)
For each competition type (gc, stage, one_day):
- `prior_{type}_points_actual`: Total points earned in this competition type
- `prior_{type}_points_proportional`: Total proportional points earned
- `prior_{type}_avg_points_actual`: Average points per race in this type
- `prior_{type}_success_rate`: Percentage of races with points earned
- `prior_{type}_races`: Number of races of this type

### 2. Points-Based Experience Features (by Race Category)  
For each race category (wt, pro, d1):
- `prior_{category}_points_actual`: Total points earned at this level
- `prior_{category}_points_proportional`: Total proportional points earned
- `prior_{category}_avg_points_actual`: Average points per race at this level
- `prior_{category}_success_rate`: Success rate at this level
- `prior_{category}_races`: Number of races at this level

### 3. Overall Performance Quality Features
- `total_prior_races`: Total number of prior races
- `total_points_actual`: Total points earned across all races
- `total_points_proportional`: Total proportional points earned
- `avg_points_per_race_actual`: Overall average points per race
- `avg_points_per_race_proportional`: Overall average proportional points
- `overall_success_rate`: Overall percentage of races with points
- `points_variance`: Variance in points earned (consistency measure)
- `points_consistency`: Inverse of variance (higher = more consistent)
- `performance_trend`: Recent performance vs early career trend

### 4. Rider-Race Interaction Features
For key race features (clumpiness_score, selection_metric, gini_coefficient, etc.):
- `rider_vs_{feature}_performance`: Correlation between feature value and rider points
- `rider_vs_{feature}_success_rate`: Success rate in high-feature-value races

For race kind features (cluster_label, local_density, boundary_distance):
- `rider_vs_{feature}_performance`: Performance metric for this feature
- `rider_vs_{feature}_affinity`: Affinity for current race's feature value

### 5. Recent Form Features
- `recent_avg_points`: Average points in recent races (last 5 or 25% of career)
- `recent_success_rate`: Success rate in recent races
- `recent_race_count`: Number of races considered "recent"

## Key Improvements Over Basic Experience Features

1. **Quality over Quantity**: Instead of just counting races, tracks actual performance and success rates
2. **Rider Profiles**: Creates rider-specific performance profiles against race characteristics
3. **Performance Trends**: Captures whether rider is improving, declining, or stable
4. **Specialization Detection**: Identifies what types of races/conditions each rider excels in
5. **Recent Form**: Weights recent performance to capture current form

## Usage Example

```python
from enhanced_rider_experience import EnhancedRiderExperience

# Initialize with auto-detection of race feature columns
enhancer = EnhancedRiderExperience()

# Add enhanced features to rider history
enhanced_df = enhancer.add_enhanced_experience_features(rider_history_df)

# The enhanced_df now contains ~67 sophisticated rider experience features
# instead of the basic 10 count-based features
```

## Integration with Global Models

These enhanced features enable global models to:
- Understand rider quality beyond simple race counts
- Learn rider specializations and preferences  
- Predict performance based on rider-race fit
- Account for recent form and performance trends
- Capture rider consistency and reliability patterns