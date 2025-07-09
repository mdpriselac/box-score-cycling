# feature_builder.py

Module for building feature vectors for rider performance prediction. Provides a single-entry point interface for getting all features needed for a rider-competition pair.

## Classes

### FeatureBuilder

Builds complete feature vectors for rider performance prediction.

#### Methods

##### `__init__(db_path: str)`
Initialize the feature builder.

**Parameters:**
- `db_path` (str): Path to the SQLite database

##### `get_prediction_features(rider_id: int, competition_id: int, cutoff_date: Optional[str] = None) -> Optional[Dict]`
Get complete feature vector for a single rider-competition pair. This is the main entry point for getting features for prediction.

**Parameters:**
- `rider_id` (int): The rider ID
- `competition_id` (int): The competition ID  
- `cutoff_date` (Optional[str]): Date cutoff for experience calculation in 'YYYY-MM-DD' format. If None, uses competition date minus 1 day.

**Returns:**
- `Optional[Dict]`: Dictionary containing all features and target variables, or None if not found

**Return Dictionary Contains:**
- **Metadata**: rider_id, rider_name, competition_id, competition_name, competition_type, race_name, race_category, race_year, competition_date, place
- **Race features** (rf_*): Competition-type specific features from race_features tables
- **Race kind features** (rkf_*): Clustering-based race classification features
- **Experience features**: total_prior_races, prior_gc_races, prior_stage_races, prior_one_day_races, prior_wt_races, prior_pro_races, prior_d1_races, prior_wt_proportion, total_prior_uci_points_actual, total_prior_uci_points_proportional
- **Other features**: rider_age_at_race
- **Target variables**: uci_points_actual, uci_points_proportional

##### `get_feature_names(competition_type: str) -> Dict[str, List[str]]`
Get the feature names for a specific competition type.

**Parameters:**
- `competition_type` (str): 'gc', 'stage', or 'one_day'

**Returns:**
- `Dict[str, List[str]]`: Dictionary with 'race_features', 'race_kind_features', and 'experience_features' keys

##### `build_bulk_dataset(rider_competition_pairs: List[Tuple[int, int]], cutoff_date: Optional[str] = None) -> pd.DataFrame`
Build features for multiple rider-competition pairs using get_prediction_features() internally.

**Parameters:**
- `rider_competition_pairs` (List[Tuple[int, int]]): List of (rider_id, competition_id) tuples
- `cutoff_date` (Optional[str]): Optional cutoff date for all pairs

**Returns:**
- `pd.DataFrame`: DataFrame with all feature vectors

## Usage Examples

### Single Prediction
```python
from feature_builder import FeatureBuilder

db_path = "database/database/cycling_races.db"
builder = FeatureBuilder(db_path)

# Get features for a single rider-competition pair
features = builder.get_prediction_features(
    rider_id=1000,
    competition_id=12345,
    cutoff_date="2023-06-14"  # Optional: defaults to day before competition
)

if features:
    print(f"Rider: {features['rider_name']}")
    print(f"Competition: {features['competition_name']}")
    print(f"Prior races: {features['total_prior_races']}")
    print(f"UCI points earned: {features['uci_points_actual']}")
    
    # Extract feature vectors for ML
    race_features = {k: v for k, v in features.items() if k.startswith('rf_')}
    experience_features = {k: v for k, v in features.items() if k.startswith(('prior_', 'total_prior'))}
```

### Real-time Prediction
```python
# For making predictions on upcoming races
upcoming_competition_id = 99999
rider_id = 1000

# Get features using current date as cutoff
from datetime import datetime, timedelta
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

features = builder.get_prediction_features(
    rider_id=rider_id,
    competition_id=upcoming_competition_id,
    cutoff_date=yesterday
)

# Now you can feed these features to your trained model
```

### Bulk Dataset Creation
```python
# Get all rider-competition pairs for a time period
import sqlite3
conn = sqlite3.connect(db_path)
query = """
SELECT rider_id, competition_id
FROM rider_results rr
JOIN competitions c ON rr.competition_id = c.id
WHERE c.date BETWEEN '2022-01-01' AND '2022-12-31'
"""
pairs = pd.read_sql_query(query, conn).values.tolist()
conn.close()

# Build features for all pairs
dataset = builder.build_bulk_dataset(pairs)

# Split by competition type for different models
gc_data = dataset[dataset['competition_type'] == 'gc']
stage_one_day_data = dataset[dataset['competition_type'].isin(['stage', 'one_day'])]
```

### Integration with DatasetGenerator
```python
# The DatasetGenerator can now be refactored to use FeatureBuilder
class DatasetGenerator:
    def __init__(self, db_path):
        self.builder = FeatureBuilder(db_path)
    
    def generate_datasets(self, cutoff_date):
        # Get all relevant pairs
        pairs = self._get_rider_competition_pairs(cutoff_date)
        
        # Use FeatureBuilder to get all features
        dataset = self.builder.build_bulk_dataset(pairs, cutoff_date)
        
        # Split and return
        return {
            'gc_dataset': dataset[dataset['competition_type'] == 'gc'],
            'stage_one_day_dataset': dataset[dataset['competition_type'].isin(['stage', 'one_day'])]
        }
```

## Key Benefits

1. **Single Entry Point**: One method (`get_prediction_features`) handles all feature extraction
2. **Reusable**: Same logic for training data generation and real-time predictions
3. **Experience Calculation**: Automatically calculates cumulative experience up to any date
4. **Configuration-Driven**: Uses the latest race kind model configuration automatically
5. **Flexible**: Works with any rider-competition pair, past or future

## Performance Considerations

- Single predictions are fast (< 100ms typically)
- Bulk operations process ~10-20 pairs per second
- Experience calculation is the most expensive operation
- Consider caching rider histories for repeated predictions

## Error Handling

- Returns None if rider-competition pair not found
- Handles first-time riders (zero experience features)
- Validates competition types
- Handles missing race features gracefully