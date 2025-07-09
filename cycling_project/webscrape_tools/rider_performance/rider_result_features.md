# rider_result_features.py

Module for collecting all features for a single rider result including both types of UCI points. Automatically reads the latest configuration to determine which features to use for each competition type.

## Classes

### RiderResultFeatures

Collects all features for a single rider result including race features, race kind features, and both types of UCI points.

#### Methods

##### `__init__(db_path: str)`
Initialize the feature collector.

**Parameters:**
- `db_path` (str): Path to the SQLite database

##### `get_features_for_result(result_id: int) -> Optional[Dict]`
Get all features for a single rider result.

**Parameters:**
- `result_id` (int): The ID from the rider_results table

**Returns:**
- `Optional[Dict]`: Dictionary containing all features and metadata, or None if not found

**Dictionary keys include:**
- `result_id`: Original result ID
- `rider_id`, `rider_name`: Rider information
- `competition_id`, `competition_name`, `competition_type`: Competition details
- `race_name`, `race_category`, `race_year`: Race information
- `place`, `time_gap`, `percentile`, `rider_age`: Result details
- `uci_points_actual`, `uci_points_proportional`: Both UCI point calculations
- `race_features_source`: Which table the race features came from
- `feature_columns_used`: List of feature columns used for this competition type
- `rf_*`: Race features (prefixed with 'rf_')
- `rkf_*`: Race kind features (prefixed with 'rkf_')

##### `get_feature_info() -> Dict`
Get information about the features being used.

**Returns:**
- `Dict`: Dictionary containing feature configuration information

**Dictionary keys:**
- `gc_features`: List of features used for GC races
- `stage_features`: List of features used for stage races  
- `one_day_features`: List of features used for one-day races
- `race_kind_features`: List of race kind features
- `config_source`: Timestamp of configuration file
- `race_kind_table`: Name of race kind features table

## Private Methods

### `_load_latest_config() -> Dict`
Load the latest configuration JSON file from database/race_kinds/race_kind_feature_guide/.

### `_get_race_features(conn, competition_id, table_name, feature_columns) -> Optional[Dict]`
Get race features from the appropriate percentile table using only the relevant feature columns.

### `_get_race_kind_features(conn, competition_id) -> Optional[Dict]`
Get race kind features from the unified table specified in the configuration.

### `_calculate_uci_points(place, race_type, race_level, fc_race_id) -> Dict[str, int]`
Calculate both actual and proportional UCI points for a result.

## Usage Example

```python
from rider_result_features import RiderResultFeatures

db_path = "database/database/cycling_races.db"
collector = RiderResultFeatures(db_path)

# Get features for a specific result
features = collector.get_features_for_result(1000)

if features:
    print(f"Rider: {features['rider_name']}")
    print(f"Competition: {features['competition_name']}")
    print(f"UCI Points: {features['uci_points_actual']}")
    
    # Access race features (prefixed with 'rf_')
    race_features = {k: v for k, v in features.items() if k.startswith('rf_')}
    
    # Access race kind features (prefixed with 'rkf_')
    race_kind_features = {k: v for k, v in features.items() if k.startswith('rkf_')}

# Get information about feature configuration
feature_info = collector.get_feature_info()
print(f"GC features: {feature_info['gc_features']}")
print(f"Stage features: {feature_info['stage_features']}")
```

## Notes

- Automatically reads the latest configuration file to determine which features to use
- Routes GC races to race_features_70, stage/one-day races to race_features_40
- Uses only the features that were actually used in the race kind models
- Calculates both actual UCI points and proportional UCI points
- Handles missing features gracefully by filling with None
- Feature columns are prefixed with 'rf_' for race features and 'rkf_' for race kind features