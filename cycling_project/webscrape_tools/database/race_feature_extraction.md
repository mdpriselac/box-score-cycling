# Race Feature Extraction Module

This module provides comprehensive race feature extraction from the cycling database.

## Main Functions

### trim_race_results_by_percentile(competition_id: int, percentile: float, db_path: str) -> Tuple[List[float], List[float], int, float]
Trims race results to analyze only the top N percentile of finishers.
- **Input**:
  - `competition_id` - Database ID of the competition
  - `percentile` - Cutoff percentile (0.5 = top 50%)
  - `db_path` - Path to SQLite database
- **Output**: Tuple of (finishing_times, time_gaps, total_finishers, winning_time)
- **Example**: `times, gaps, total, win_time = trim_race_results_by_percentile(123, 0.5, "database/cycling_races.db")`

### calculate_statistical_features(finishing_times: List[float], time_gaps: List[float], winning_time: float) -> Dict[str, float]
Calculates all statistical measures for the race.
- **Input**:
  - `finishing_times` - List of finishing times in seconds
  - `time_gaps` - List of gaps from winner in seconds
  - `winning_time` - Winner's time in seconds
- **Output**: Dictionary with statistical features including:
  - Variance (absolute and normalized)
  - Standard deviation (absolute and normalized)
  - Skewness (absolute and normalized)
  - Kurtosis (absolute and normalized)
  - Gini coefficient
  - Shannon entropy (absolute and normalized)
  - Percentile gaps (5th through 50th)
- **Example**: `stats = calculate_statistical_features(times, gaps, 14400)`

### calculate_engineered_features(finishing_times: List[float], time_gaps: List[float], winning_time: float, total_finishers: int, abandon_ratio: float) -> Dict[str, float]
Calculates engineered metrics for race characterization.
- **Input**:
  - `finishing_times` - List of finishing times in seconds
  - `time_gaps` - List of gaps from winner in seconds
  - `winning_time` - Winner's time in seconds
  - `total_finishers` - Total number of finishers
  - `abandon_ratio` - Ratio of non-finishers
- **Output**: Dictionary with engineered features including:
  - Group statistics (count, sizes, positions)
  - Biggest group metric
  - Time gap evenness metric
  - Clumpiness score
  - Selection metric
- **Example**: `eng_features = calculate_engineered_features(times, gaps, 14400, 150, 0.15)`

### extract_race_features(competition_id: int, percentile: float, db_path: str) -> Dict[str, Union[float, int, str]]
Main function to extract all features for a competition.
- **Input**:
  - `competition_id` - Database ID of the competition
  - `percentile` - Percentile cutoff for analysis
  - `db_path` - Path to SQLite database
- **Output**: Complete feature dictionary including metadata, statistics, and engineered metrics
- **Example**: `features = extract_race_features(123, 0.5, "database/cycling_races.db")`

### extract_features_for_percentile_range(competition_id: int, db_path: str, start_percentile: float = 0.25, end_percentile: float = 1.0, step: float = 0.05) -> pd.DataFrame
Extracts features across multiple percentile cutoffs.
- **Input**:
  - `competition_id` - Database ID of the competition
  - `db_path` - Path to SQLite database
  - `start_percentile` - Starting percentile (default 0.25)
  - `end_percentile` - Ending percentile (default 1.0)
  - `step` - Step between percentiles (default 0.05)
- **Output**: DataFrame with features for each percentile
- **Example**: `df = extract_features_for_percentile_range(123, "database/cycling_races.db")`

### batch_extract_features(competition_ids: List[int], percentile: float, db_path: str) -> pd.DataFrame
Extracts features for multiple competitions at once.
- **Input**:
  - `competition_ids` - List of competition IDs
  - `percentile` - Percentile cutoff for analysis
  - `db_path` - Path to SQLite database
- **Output**: DataFrame with features for all competitions
- **Example**: `df = batch_extract_features([123, 124, 125], 0.5, "database/cycling_races.db")`

## Feature Categories

### Metadata Features
- Competition and race identifiers
- Names, types, categories
- Dates and years
- Analysis parameters

### Basic Statistics
- Total finishers
- Included finishers (after trimming)
- Abandon ratio
- Winning time
- Total race duration

### Statistical Features
- Variance and standard deviation (absolute and normalized)
- Skewness (distribution asymmetry)
- Kurtosis (distribution tail weight)
- Gini coefficient (inequality measure)
- Shannon entropy (unpredictability)
- Percentile gaps (5th through 50th)

### Engineered Features
- Group dynamics (sizes, counts, positions)
- Biggest group metric (0-1)
- Time gap evenness metric (0-1)
- Clumpiness score (0-1)
- Selection metric (0-1)