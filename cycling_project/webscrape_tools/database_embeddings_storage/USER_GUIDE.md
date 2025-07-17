# Rider Correlation Database Storage System - User Guide

## Overview

This system calculates and stores correlation matrices between rider performance and race features. It handles missing data gracefully by tracking which percentiles are available for each competition and storing NULL values for missing correlations.

## Key Features

- **Per-percentile missing data handling**: If a competition doesn't have enough riders for the 30th percentile but has data for 50th-100th percentiles, correlations are calculated for the available percentiles
- **Data quality tracking**: Comprehensive metadata about what data was available vs missing
- **Feature identification**: Each correlation includes both feature index and feature name
- **Resume capability**: Processing can be stopped and resumed at any time

## Database Schema

### Main Tables

#### `rider_correlations_denorm`
The primary table for accessing correlation data. One row per correlation value.

```sql
CREATE TABLE rider_correlations_denorm (
    rider_result_id INTEGER NOT NULL,      -- Links to rider_results table
    competition_id INTEGER NOT NULL,       -- Competition this correlation applies to
    rider_id INTEGER NOT NULL,             -- Rider ID
    correlation_type TEXT NOT NULL,        -- 'all_races', 'same_type', 'stage_one_days'
    percentile INTEGER NOT NULL,           -- 30, 40, 50, 60, 70, 80, 90, 100
    feature_idx INTEGER NOT NULL,          -- 0-36 (index into RACE_FEATURES array)
    feature_name TEXT NOT NULL,            -- e.g., 'abandon_ratio', 'winning_time'
    correlation_value REAL,                -- NULL if percentile unavailable
    race_count INTEGER NOT NULL,           -- Number of races with features used
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, feature_idx)
);
```

#### `correlation_data_quality`
Tracks data completeness for each correlation calculation.

```sql
CREATE TABLE correlation_data_quality (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    total_races INTEGER NOT NULL,          -- Total races in rider's history
    races_with_features INTEGER NOT NULL,  -- Races that had race features
    missing_competition_ids TEXT,          -- JSON array of missing competition IDs
    percentile_availability TEXT,          -- JSON array: [0,0,1,1,1,1,1,1] = 30%,40% missing
    data_completeness REAL NOT NULL,       -- races_with_features / total_races
    
    PRIMARY KEY (rider_result_id, correlation_type)
);
```

#### `rider_correlations_blob`
Backup storage with compressed numpy arrays for analysis.

```sql
CREATE TABLE rider_correlations_blob (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    correlation_matrix BLOB NOT NULL,      -- Compressed 8x37 numpy array
    race_count INTEGER NOT NULL,
    
    UNIQUE(rider_result_id, correlation_type)
);
```

## Correlation Types

### 1. `all_races`
- Uses rider's entire racing history regardless of race type
- Minimum threshold: 13 total races (top 90% of riders)

### 2. `same_type` 
- Uses only races of the same type (GC races for GC results, stage races for stage results, etc.)
- Minimum thresholds:
  - GC races: 6 races (top 75% of riders)
  - Stage races: 33 races (top 75% of riders)  
  - One-day races: 6 races (top 80% of riders)

### 3. `stage_one_days`
- Uses combined stage races + one-day races (excludes GC races)
- Only calculated for stage and one-day race results
- Minimum threshold: 28 combined races (top 80% of riders)

## Race Features (37 total)

The system tracks correlations against these race features:

### Basic Race Statistics
- `total_finishers`, `included_finishers`, `abandon_ratio`
- `winning_time`, `total_race_duration`

### Performance Distribution
- `variance_absolute`, `variance_normalized`
- `std_deviation_absolute`, `std_deviation_normalized`  
- `skewness_absolute`, `skewness_normalized`
- `kurtosis_absolute`, `kurtosis_normalized`
- `gini_coefficient`
- `shannon_entropy_absolute`, `shannon_entropy_normalized`

### Time Gap Analysis
- `5th_percentile_gap` through `50th_percentile_gap` (10 features)

### Group Dynamics
- `total_groups`, `riders_in_groups`, `proportion_in_groups`
- `largest_group_size`, `largest_group_position`
- `avg_group_size`, `std_group_size`
- `biggest_group_metric`, `time_gap_evenness_metric`
- `clumpiness_score`, `selection_metric`

## How to Use This Data

### 1. Basic Query: Get All Correlations for a Rider

```sql
SELECT 
    rd.correlation_type,
    rd.percentile,
    rd.feature_name,
    rd.correlation_value,
    rd.race_count,
    dq.data_completeness
FROM rider_correlations_denorm rd
JOIN correlation_data_quality dq 
    ON rd.rider_result_id = dq.rider_result_id 
    AND rd.correlation_type = dq.correlation_type
WHERE rd.rider_id = ?
ORDER BY rd.correlation_type, rd.percentile, rd.feature_idx;
```

### 2. Get Correlations for a Specific Feature

```sql
SELECT 
    rd.rider_id,
    rd.correlation_type,
    rd.percentile,
    rd.correlation_value,
    dq.data_completeness
FROM rider_correlations_denorm rd
JOIN correlation_data_quality dq 
    ON rd.rider_result_id = dq.rider_result_id 
    AND rd.correlation_type = dq.correlation_type
WHERE rd.feature_name = 'abandon_ratio'
    AND rd.correlation_value IS NOT NULL
ORDER BY ABS(rd.correlation_value) DESC;
```

### 3. Check Data Quality for a Competition

```sql
SELECT 
    dq.rider_result_id,
    dq.correlation_type,
    dq.total_races,
    dq.races_with_features,
    dq.data_completeness,
    dq.percentile_availability
FROM correlation_data_quality dq
JOIN rider_results rr ON dq.rider_result_id = rr.id
WHERE rr.competition_id = ?
ORDER BY dq.data_completeness DESC;
```

### 4. Find Riders with High-Quality Data

```sql
SELECT 
    rd.rider_id,
    rd.correlation_type,
    dq.data_completeness,
    dq.races_with_features
FROM rider_correlations_denorm rd
JOIN correlation_data_quality dq 
    ON rd.rider_result_id = dq.rider_result_id 
    AND rd.correlation_type = dq.correlation_type
WHERE dq.data_completeness >= 0.9  -- 90% or more races have features
    AND dq.races_with_features >= 20  -- At least 20 races with features
GROUP BY rd.rider_id, rd.correlation_type;
```

## Understanding Missing Data

### Percentile Availability
The `percentile_availability` field in `correlation_data_quality` is a JSON array showing which percentiles had data:
- `[1,1,1,1,1,1,1,1]` = All percentiles available
- `[0,0,1,1,1,1,1,1]` = 30% and 40% percentiles missing (not enough riders)
- `[0,0,0,1,1,1,1,1]` = 30%, 40%, 50% percentiles missing

### NULL Values in Correlations
- `correlation_value` is NULL when that percentile wasn't available for any race in the rider's history
- This preserves the structure while indicating missing data

### Data Completeness
- `data_completeness` = `races_with_features` / `total_races`
- 1.0 = All races in rider's history had race features
- 0.8 = 80% of races had race features, 20% were missing

## Performance Considerations

### Indexes
The system includes optimized indexes for common access patterns:
- `idx_lookup`: (competition_id, rider_id, correlation_type)
- `idx_rider_comp_type`: (rider_id, competition_id, correlation_type)  
- `idx_competition_access`: (competition_id, correlation_type)
- `idx_feature_name`: (feature_name, correlation_type)

### Storage Size
- Denormalized table: ~2-3GB for full dataset
- Each rider result with 3 correlation types = 888 rows (8 percentiles × 37 features × 3 types)
- BLOB backup: ~500MB compressed

## Common Use Cases

### 1. Machine Learning Features
```sql
-- Get correlation features for a specific rider result
SELECT 
    feature_name,
    correlation_value
FROM rider_correlations_denorm
WHERE rider_result_id = ?
    AND correlation_type = 'all_races'
    AND percentile = 50  -- Use 50th percentile features
    AND correlation_value IS NOT NULL;
```

### 2. Data Quality Analysis
```sql
-- Check overall data quality statistics
SELECT 
    correlation_type,
    AVG(data_completeness) as avg_completeness,
    AVG(races_with_features) as avg_races_with_features,
    COUNT(*) as total_correlations
FROM correlation_data_quality
GROUP BY correlation_type;
```

### 3. Feature Importance Analysis
```sql
-- Find features with strongest correlations across all riders
SELECT 
    feature_name,
    correlation_type,
    percentile,
    AVG(ABS(correlation_value)) as avg_abs_correlation,
    COUNT(*) as sample_size
FROM rider_correlations_denorm
WHERE correlation_value IS NOT NULL
GROUP BY feature_name, correlation_type, percentile
HAVING sample_size >= 100
ORDER BY avg_abs_correlation DESC;
```

## Running the System

### Initial Setup
```bash
cd database_embeddings_storage
uv run sqlite3 ../database/database/cycling_races.db < create_correlation_tables.sql
```

### Full Processing
```bash
uv run python main.py
```

### Resume Processing
The system automatically resumes from the last checkpoint. To start fresh:
```bash
# Clear existing data
uv run sqlite3 ../database/database/cycling_races.db "DELETE FROM rider_correlations_denorm; DELETE FROM correlation_data_quality; DELETE FROM processing_checkpoint;"

# Run processing  
uv run python main.py
```

### Monitoring Progress
```bash
# Check processing status
uv run python monitor.py

# Or query directly
sqlite3 ../database/database/cycling_races.db "SELECT * FROM processing_log ORDER BY created_at DESC LIMIT 10;"
```

## Important Notes

1. **NULL vs 0**: NULL values indicate missing data, not zero correlations
2. **Data Quality**: Always check `data_completeness` before using correlations
3. **Percentile Filtering**: Lower percentiles (30%, 40%) have more missing data
4. **Memory Usage**: System uses ~8GB RAM during processing
5. **Processing Time**: Full processing takes 2-3 hours on M1 Pro

## Troubleshooting

### Common Issues
- **Out of memory**: Reduce `COMPETITION_BATCH_SIZE` in config.py
- **Slow performance**: Check if indexes were created properly
- **Missing correlations**: Check `correlation_data_quality` for data availability

### Log Files
Processing logs are saved as `correlation_processing_YYYYMMDD_HHMMSS.log` and contain detailed information about missing competitions and processing progress.