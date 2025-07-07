# Race Feature Database Module

This module provides functions for building and managing a comprehensive race feature database.

## Database Functions

### get_competition_ids(db_path: str, year: Optional[int] = None, category: Optional[str] = None, competition_type: Optional[str] = None, min_finishers: int = 30) -> List[int]
Retrieves competition IDs based on filtering criteria.
- **Input**:
  - `db_path` - Path to SQLite database
  - `year` - Filter by year (optional)
  - `category` - Filter by race category: 'wt', 'pro', or 'd1' (optional)
  - `competition_type` - Filter by type: 'one_day', 'stage', or 'gc' (optional)
  - `min_finishers` - Minimum number of finishers required (default: 30)
- **Output**: List of competition IDs matching criteria
- **Example**: `comp_ids = get_competition_ids("database/cycling_races.db", year=2024, category='wt')`

### create_feature_table(db_path: str, table_name: str = "race_features")
Creates a table to store extracted race features.
- **Input**:
  - `db_path` - Path to SQLite database
  - `table_name` - Name for the feature table (default: "race_features")
- **Output**: None (creates table in database)
- **Example**: `create_feature_table("database/cycling_races.db")`

### insert_features_to_db(features: Dict, db_path: str, table_name: str = "race_features")
Inserts extracted features into the database.
- **Input**:
  - `features` - Dictionary of features from extract_race_features
  - `db_path` - Path to SQLite database
  - `table_name` - Name of the feature table
- **Output**: None (inserts data)
- **Example**: `insert_features_to_db(features_dict, "database/cycling_races.db")`

### process_competitions_batch(competition_ids: List[int], percentile: float, db_path: str, table_name: str = "race_features", n_threads: int = 4) -> Tuple[int, int]
Processes multiple competitions in parallel.
- **Input**:
  - `competition_ids` - List of competition IDs to process
  - `percentile` - Percentile cutoff for analysis
  - `db_path` - Path to SQLite database
  - `table_name` - Name of the feature table
  - `n_threads` - Number of parallel threads (default: 4)
- **Output**: Tuple of (successful_count, failed_count)
- **Example**: `success, failed = process_competitions_batch([123, 124, 125], 0.5, "database/cycling_races.db")`

### build_feature_database(db_path: str, years: Optional[List[int]] = None, categories: Optional[List[str]] = None, competition_types: Optional[List[str]] = None, percentiles: List[float] = [0.25, 0.5, 0.75, 1.0], table_name: str = "race_features", n_threads: int = 4, rebuild: bool = False)
Builds a comprehensive feature database for specified races.
- **Input**:
  - `db_path` - Path to SQLite database
  - `years` - List of years to process (None = all)
  - `categories` - List of categories to process (None = all)
  - `competition_types` - List of types to process (None = all)
  - `percentiles` - List of percentile cutoffs (default: [0.25, 0.5, 0.75, 1.0])
  - `table_name` - Name for the feature table
  - `n_threads` - Number of parallel threads
  - `rebuild` - Whether to rebuild existing table
- **Output**: Summary DataFrame of processing results
- **Example**: 
  ```python
  summary = build_feature_database(
      "database/cycling_races.db",
      years=[2023, 2024],
      percentiles=[0.25, 0.5, 0.75, 1.0]
  )
  ```

### get_feature_summary(db_path: str, table_name: str = "race_features") -> pd.DataFrame
Gets summary statistics of the feature database.
- **Input**:
  - `db_path` - Path to SQLite database
  - `table_name` - Name of the feature table
- **Output**: DataFrame with summary by year, category, type, and percentile
- **Example**: `summary = get_feature_summary("database/cycling_races.db")`

### load_features_for_analysis(db_path: str, table_name: str = "race_features", year: Optional[int] = None, category: Optional[str] = None, competition_type: Optional[str] = None, percentile: Optional[float] = None) -> pd.DataFrame
Loads features from database with optional filters.
- **Input**:
  - `db_path` - Path to SQLite database
  - `table_name` - Name of the feature table
  - `year` - Filter by year (optional)
  - `category` - Filter by category (optional)
  - `competition_type` - Filter by type (optional)
  - `percentile` - Filter by percentile (optional)
- **Output**: DataFrame with requested features
- **Example**: 
  ```python
  features_df = load_features_for_analysis(
      "database/cycling_races.db",
      year=2024,
      category='wt',
      percentile=0.5
  )
  ```

## Utility Functions

### table_exists(db_path: str, table_name: str) -> bool
Checks if a table exists in the database.
- **Input**:
  - `db_path` - Path to SQLite database
  - `table_name` - Name of table to check
- **Output**: Boolean indicating if table exists
- **Example**: `exists = table_exists("database/cycling_races.db", "race_features")`

## Feature Table Schema

The created feature table includes:
- **Metadata**: competition/race IDs, names, types, dates
- **Basic Statistics**: finisher counts, abandon ratio, race duration
- **Statistical Features**: variance, std deviation, skewness, kurtosis, Gini coefficient, Shannon entropy
- **Percentile Gaps**: 5th through 50th percentile gaps
- **Engineered Features**: group metrics, evenness, clumpiness, selection metrics