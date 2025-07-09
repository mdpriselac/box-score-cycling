# rider_history.py

Module for creating rider history up to a certain date. Collects all rider results and their features for training/prediction purposes.

## Classes

### RiderHistory

Creates comprehensive rider history including all features up to a specified date.

#### Methods

##### `__init__(db_path: str)`
Initialize the rider history collector.

**Parameters:**
- `db_path` (str): Path to the SQLite database

##### `get_rider_history(rider_id: int, cutoff_date: str) -> pd.DataFrame`
Get all results and features for a rider up to a specific date.

**Parameters:**
- `rider_id` (int): The rider ID
- `cutoff_date` (str): Date cutoff in 'YYYY-MM-DD' format

**Returns:**
- `pd.DataFrame`: DataFrame containing all rider results with features up to cutoff date

**DataFrame columns include all columns from RiderResultFeatures plus sorted by competition_date**

##### `get_all_rider_histories(cutoff_date: str, min_results: int = 1) -> pd.DataFrame`
Get histories for all riders up to a specific date.

**Parameters:**
- `cutoff_date` (str): Date cutoff in 'YYYY-MM-DD' format
- `min_results` (int): Minimum number of results required for a rider to be included (default: 1)

**Returns:**
- `pd.DataFrame`: DataFrame containing all rider results with features up to cutoff date

**Notes:**
- Processes all riders in batches with progress updates
- Filters out riders with fewer than min_results races
- Results are sorted by rider_id and competition_date

##### `get_rider_summary_stats(rider_id: int, cutoff_date: str) -> Dict`
Get summary statistics for a rider's career up to a specific date.

**Parameters:**
- `rider_id` (int): The rider ID
- `cutoff_date` (str): Date cutoff in 'YYYY-MM-DD' format

**Returns:**
- `Dict`: Dictionary containing rider career statistics

**Dictionary keys:**
- `rider_id`: The rider ID
- `total_races`: Total number of races
- `gc_races`, `stage_races`, `one_day_races`: Counts by competition type
- `wt_races`, `pro_races`, `d1_races`: Counts by race category
- `wt_proportion`: Proportion of races that were WT level
- `total_uci_points_actual`, `total_uci_points_proportional`: Total UCI points earned
- `avg_place`, `best_place`: Average and best finishing place
- `career_start_date`, `career_end_date`: Career span dates
- `years_active`: Number of years with racing activity

##### `get_recent_form(rider_id: int, cutoff_date: str, months_back: int = 6) -> Dict`
Get rider's recent form over specified number of months.

**Parameters:**
- `rider_id` (int): The rider ID
- `cutoff_date` (str): Date cutoff in 'YYYY-MM-DD' format
- `months_back` (int): Number of months to look back (default: 6)

**Returns:**
- `Dict`: Dictionary containing recent form statistics

**Dictionary keys:**
- `rider_id`: The rider ID
- `form_period_months`: Number of months analyzed
- `form_races`: Number of races in the period
- `form_avg_place`, `form_best_place`: Average and best place in period
- `form_uci_points_actual`, `form_uci_points_proportional`: UCI points earned in period

## Usage Examples

### Single Rider History
```python
from rider_history import RiderHistory

db_path = "database/database/cycling_races.db"
history = RiderHistory(db_path)

# Get all results for a rider up to a specific date
rider_df = history.get_rider_history(rider_id=1000, cutoff_date="2023-12-31")

print(f"Found {len(rider_df)} results")
print(f"Date range: {rider_df['competition_date'].min()} to {rider_df['competition_date'].max()}")

# Access all features for machine learning
feature_columns = [col for col in rider_df.columns if col.startswith(('rf_', 'rkf_'))]
X = rider_df[feature_columns]
y = rider_df['uci_points_actual']
```

### Rider Summary Statistics
```python
# Get career summary
stats = history.get_rider_summary_stats(rider_id=1000, cutoff_date="2023-12-31")

print(f"Total races: {stats['total_races']}")
print(f"WT proportion: {stats['wt_proportion']:.2%}")
print(f"Total UCI points: {stats['total_uci_points_actual']}")
print(f"Average place: {stats['avg_place']:.1f}")
print(f"Years active: {stats['years_active']}")
```

### Recent Form Analysis
```python
# Get recent form (last 6 months)
form = history.get_recent_form(rider_id=1000, cutoff_date="2023-12-31", months_back=6)

print(f"Recent races: {form['form_races']}")
print(f"Recent average place: {form['form_avg_place']:.1f}")
print(f"Recent UCI points: {form['form_uci_points_actual']}")
```

### All Riders Dataset
```python
# Get dataset for all riders with at least 10 results
all_riders_df = history.get_all_rider_histories(
    cutoff_date="2023-12-31", 
    min_results=10
)

print(f"Total results: {len(all_riders_df)}")
print(f"Unique riders: {all_riders_df['rider_id'].nunique()}")

# Split into training data by competition type
gc_data = all_riders_df[all_riders_df['competition_type'] == 'gc']
stage_one_day_data = all_riders_df[all_riders_df['competition_type'].isin(['stage', 'one_day'])]
```

## Integration with RiderResultFeatures

The RiderHistory class uses the RiderResultFeatures class internally to collect features for each result. This means:

- All features are automatically configured based on the latest race kind model configuration
- Race features are correctly routed to the appropriate percentile tables
- Both actual and proportional UCI points are calculated
- Race kind features are included from the unified table

## Performance Considerations

- Processing all riders can take significant time (6000+ riders)
- Progress updates are provided during batch processing
- Results are processed sequentially to avoid memory issues
- Consider using smaller date ranges or higher min_results thresholds for testing

## Error Handling

- Missing race IDs in UCI points calculation are handled with warnings
- Empty results return appropriate empty DataFrames or default values
- Database connection errors are properly handled with try/finally blocks