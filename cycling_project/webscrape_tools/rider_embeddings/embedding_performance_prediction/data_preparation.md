# data_preparation.py

Module for preparing embedding-based prediction model training data by combining rider embeddings with database features.

## Classes

### EmbeddingDataPreparation

Prepares data for training embedding-based prediction models by merging rider embeddings with rider_results and competition information.

#### Methods

##### `__init__(db_path: str, embedding_base_path: str = "race_type_optimized_data")`
Initialize the data preparation class.

**Parameters:**
- `db_path` (str): Path to the cycling database
- `embedding_base_path` (str): Path to folder containing optimized embedding parquet files

##### `load_embeddings(race_type: str) -> pd.DataFrame`
Load embeddings for a specific race type.

**Parameters:**
- `race_type` (str): One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']

**Returns:**
- `pd.DataFrame`: Embedding data with rider_result_id and correlation features

##### `load_rider_results_with_competition_info() -> pd.DataFrame`
Load rider results with competition information including year and tour level.

**Returns:**
- `pd.DataFrame`: Rider results with tour_level, competition_race_type, and year columns

##### `prepare_features(rider_results: pd.DataFrame) -> pd.DataFrame`
Prepare features from rider_results data, excluding metadata and encoding tour level.

**Parameters:**
- `rider_results` (pd.DataFrame): DataFrame with rider results

**Returns:**
- `pd.DataFrame`: DataFrame with prepared features (excludes place, time_gap, bib_number, etc.)

##### `combine_embeddings_with_features(embeddings: pd.DataFrame, rider_results: pd.DataFrame) -> pd.DataFrame`
Combine embedding data with rider result features.

**Parameters:**
- `embeddings` (pd.DataFrame): DataFrame with embedding correlations
- `rider_results` (pd.DataFrame): DataFrame with rider results and competition info

**Returns:**
- `pd.DataFrame`: Combined DataFrame with embeddings, features, and target

##### `prepare_race_type_data(race_type: str, min_year: Optional[int] = None, max_year: Optional[int] = None) -> pd.DataFrame`
Prepare complete dataset for a specific race type.

**Parameters:**
- `race_type` (str): One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
- `min_year` (Optional[int]): Minimum year to include (inclusive)
- `max_year` (Optional[int]): Maximum year to include (inclusive)

**Returns:**
- `pd.DataFrame`: DataFrame ready for model training

##### `split_by_year(data: pd.DataFrame, test_year: int) -> Tuple[pd.DataFrame, pd.DataFrame]`
Split data into train and test sets based on year.

**Parameters:**
- `data` (pd.DataFrame): Combined data with 'year' column
- `test_year` (int): Year to use for testing

**Returns:**
- `Tuple[pd.DataFrame, pd.DataFrame]`: (train_df, test_df) where train has years < test_year

##### `get_dataset_stats(df: pd.DataFrame) -> Dict`
Get statistics about a dataset.

**Parameters:**
- `df` (pd.DataFrame): Dataset to analyze

**Returns:**
- `Dict`: Statistics including sample count, competition count, rider count, years, and target distribution

## Key Features

- **Tour Level Encoding**: Encodes tour levels as d1=0, pro=1, wt=2
- **Feature Exclusion**: Automatically excludes metadata columns and historical '_actual' columns
- **Race Type Filtering**: Handles all race types including combined 'stage_one_day'
- **Year-based Splitting**: Supports temporal train/test splits for backtesting

## Usage Example

```python
from data_preparation import EmbeddingDataPreparation

# Initialize
prep = EmbeddingDataPreparation(
    db_path="database/database/cycling_races.db",
    embedding_base_path="race_type_optimized_data"
)

# Prepare data for GC model
gc_data = prep.prepare_race_type_data('gc')

# Split by year for backtesting
train_df, test_df = prep.split_by_year(gc_data, test_year=2023)

# Get dataset statistics
train_stats = prep.get_dataset_stats(train_df)
print(f"Training samples: {train_stats['n_samples']}")
print(f"Zero rate: {train_stats['target_stats']['zero_rate']:.2%}")
```