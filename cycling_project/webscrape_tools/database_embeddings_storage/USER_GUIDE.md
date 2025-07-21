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
Primary storage with compressed numpy arrays containing the full correlation matrices.

```sql
CREATE TABLE rider_correlations_blob (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    correlation_matrix BLOB NOT NULL,      -- Compressed 8x37 numpy array
    race_count INTEGER NOT NULL,
    
    UNIQUE(rider_result_id, correlation_type)
);
```

The correlation matrix is stored as a compressed numpy array with dimensions 8x37:
- 8 rows: one for each percentile (30, 40, 50, 60, 70, 80, 90, 100)
- 37 columns: one for each race feature
- Values are correlation coefficients between -1 and 1, or NaN if data unavailable

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

### 1. Basic Query: Get Correlation Data Quality for a Rider

```sql
SELECT 
    rb.correlation_type,
    rb.race_count,
    dq.data_completeness,
    dq.percentile_availability
FROM rider_correlations_blob rb
JOIN correlation_data_quality dq 
    ON rb.rider_result_id = dq.rider_result_id 
    AND rb.correlation_type = dq.correlation_type
WHERE rb.rider_id = ?
ORDER BY rb.correlation_type;
```

Note: To access the actual correlation values, you'll need to load and decompress the BLOB data using Python/numpy.

### 2. Load Correlation Matrix in Python

```python
import sqlite3
import numpy as np
import gzip

# Load correlation matrix for a specific rider result
conn = sqlite3.connect('cycling_races.db')
cursor = conn.execute("""
    SELECT correlation_matrix 
    FROM rider_correlations_blob 
    WHERE rider_result_id = ? AND correlation_type = ?
""", [rider_result_id, 'all_races'])

result = cursor.fetchone()
if result:
    # Decompress and reshape the matrix
    compressed_data = result[0]
    matrix_bytes = gzip.decompress(compressed_data)
    correlation_matrix = np.frombuffer(matrix_bytes).reshape(8, 37)
    
    # Access specific correlations
    # e.g., 50th percentile (index 2) vs abandon_ratio (index 2)
    correlation_value = correlation_matrix[2, 2]
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
    rb.rider_id,
    rb.correlation_type,
    dq.data_completeness,
    dq.races_with_features
FROM rider_correlations_blob rb
JOIN correlation_data_quality dq 
    ON rb.rider_result_id = dq.rider_result_id 
    AND rb.correlation_type = dq.correlation_type
WHERE dq.data_completeness >= 0.9  -- 90% or more races have features
    AND dq.races_with_features >= 20  -- At least 20 races with features
GROUP BY rb.rider_id, rb.correlation_type;
```

## Understanding Missing Data

### Percentile Availability
The `percentile_availability` field in `correlation_data_quality` is a JSON array showing which percentiles had data:
- `[1,1,1,1,1,1,1,1]` = All percentiles available
- `[0,0,1,1,1,1,1,1]` = 30% and 40% percentiles missing (not enough riders)
- `[0,0,0,1,1,1,1,1]` = 30%, 40%, 50% percentiles missing

### NaN Values in Correlations
- In the correlation matrix, NaN values indicate when that percentile wasn't available for any race in the rider's history
- This preserves the matrix structure while indicating missing data

### Data Completeness
- `data_completeness` = `races_with_features` / `total_races`
- 1.0 = All races in rider's history had race features
- 0.8 = 80% of races had race features, 20% were missing

## Performance Considerations

### Indexes
The blob table has indexes on its primary key fields for efficient access.

### Storage Size
- BLOB table: ~500MB compressed for full dataset
- Each rider result stores 3 compressed matrices (one per correlation type)
- Significant space savings compared to denormalized storage

## Common Use Cases

### 1. Machine Learning Features
```python
# Get correlation features for a specific rider result
import sqlite3
import numpy as np
import gzip

conn = sqlite3.connect('cycling_races.db')

# Load the correlation matrix
cursor = conn.execute("""
    SELECT rb.correlation_matrix, dq.percentile_availability
    FROM rider_correlations_blob rb
    JOIN correlation_data_quality dq ON rb.rider_result_id = dq.rider_result_id 
        AND rb.correlation_type = dq.correlation_type
    WHERE rb.rider_result_id = ? AND rb.correlation_type = 'all_races'
""", [rider_result_id])

result = cursor.fetchone()
if result:
    # Decompress matrix
    matrix = np.frombuffer(gzip.decompress(result[0])).reshape(8, 37)
    percentile_availability = json.loads(result[1])
    
    # Get 50th percentile features (index 2) if available
    if percentile_availability[2] == 1:
        features = matrix[2, :]  # 50th percentile row
        # Filter out NaN values
        valid_features = [(i, v) for i, v in enumerate(features) if not np.isnan(v)]
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
```python
# Analyze feature importance across all riders
# This requires loading and processing multiple correlation matrices
# Consider using a batch processing approach or specialized analysis script
# for large-scale feature importance analysis
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
uv run sqlite3 ../database/database/cycling_races.db "DELETE FROM rider_correlations_blob; DELETE FROM correlation_data_quality; DELETE FROM processing_checkpoint;"

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
- **Slow performance**: Check database connections and batch size
- **Missing correlations**: Check `correlation_data_quality` for data availability
- **BLOB decompression errors**: Ensure gzip is properly imported and data isn't corrupted

### Log Files
Processing logs are saved as `correlation_processing_YYYYMMDD_HHMMSS.log` and contain detailed information about missing competitions and processing progress.