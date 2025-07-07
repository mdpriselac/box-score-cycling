# Race Feature Extraction System

A comprehensive system for extracting and analyzing features from cycling race data to support race classification and prediction models.

## Overview

This system provides tools to:
- Extract statistical and engineered features from race finishing time distributions
- Analyze races at different percentile cutoffs (e.g., top 25%, 50%, full field)
- Build a feature database for large-scale analysis
- Support race classification and rider performance modeling

## Key Components

### 1. Statistical Measures (`statistical_measures.py`)
- **Gini Coefficient**: Measures inequality in time gaps
- **Shannon Entropy**: Quantifies unpredictability of results
- **Variance & Standard Deviation**: Both absolute and normalized
- **Skewness & Kurtosis**: Distribution shape characteristics
- **Percentile Gaps**: Time gaps at key percentiles

### 2. Engineered Metrics (`engineered_metrics.py`)
- **Group Identification**: Finds riders finishing together
- **Biggest Group Metric**: Size and influence of largest group (0-1)
- **Time Gap Evenness**: How evenly spread the field is (0-1)
- **Clumpiness Score**: Multiple distinct groups indicator (0-1)
- **Selection Metric**: How selective/difficult the race was (0-1)

### 3. Feature Extraction (`race_feature_extraction.py`)
- **Percentile Trimming**: Analyze top N% of finishers
- **Complete Feature Set**: ~46 features per race
- **Batch Processing**: Handle multiple competitions efficiently

### 4. Database Integration (`race_feature_database.py`)
- **Feature Storage**: SQLite table for extracted features
- **Parallel Processing**: Multi-threaded extraction
- **Flexible Queries**: Filter by year, category, race type

## Quick Start

```python
from race_feature_extraction import extract_race_features
from race_feature_database import get_competition_ids, build_feature_database

# Database path
DB_PATH = "database/cycling_races.db"

# Extract features for a single competition
features = extract_race_features(competition_id=123, percentile=0.5, db_path=DB_PATH)

# Build feature database for multiple years
summary = build_feature_database(
    db_path=DB_PATH,
    years=[2023, 2024],
    percentiles=[0.25, 0.5, 0.75, 1.0],
    table_name="race_features"
)
```

## Feature Categories

### Metadata
- Competition/race identifiers, names, types, dates

### Basic Statistics
- Total/included finishers, abandon ratio, race duration

### Statistical Features
- Variance, standard deviation (absolute & normalized)
- Skewness, kurtosis, Gini coefficient, Shannon entropy
- Percentile gaps (5th through 50th)

### Engineered Features
- Group dynamics (counts, sizes, positions)
- Race characterization metrics (0-1 scale)

## Usage Examples

See `example_usage.py` for complete examples including:
1. Single competition analysis
2. Percentile sensitivity analysis
3. Batch processing
4. Race type comparisons

## Testing

Run comprehensive tests with:
```bash
uv run python test_race_features.py
```

## Next Steps

With this feature extraction system, you can:
1. **Develop Race Classifications**: Use clustering on features to identify race types
2. **Optimize Percentile Selection**: Find which percentile best distinguishes race types
3. **Build Prediction Models**: Use features to predict race outcomes
4. **Create Rider Profiles**: Analyze rider performance by race characteristics
5. **Historical Analysis**: Track how races change over time

## Performance Notes

- Minimum 30 finishers recommended for reliable statistics
- Processing speed: ~10-20 competitions/second
- Feature extraction is parallelizable
- Results cached in database for reuse