-- Drop existing table and create simplified version focused on gradient data
DROP TABLE IF EXISTS race_feature_gradients;

CREATE TABLE IF NOT EXISTS race_feature_gradients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL,
    
    -- Metadata
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_percentiles TEXT,  -- JSON array of percentiles with valid data [10,15,20,...,100]
    missing_percentiles TEXT,  -- JSON array of percentiles with no data
    
    -- Coverage metrics
    percentile_coverage_ratio REAL,  -- % of percentiles with valid data
    lowest_valid_percentile INTEGER,  -- Lowest percentile with valid data
    highest_null_percentile INTEGER,  -- Highest percentile where we lost all data
    
    -- Data quality indicators
    variance_zero_percentile INTEGER,  -- Highest percentile where variance hits zero (counting down from 100)
    kurtosis_null_percentile INTEGER,  -- Highest percentile where kurtosis becomes null (counting down from 100)
    
    -- For each feature, store gradient metrics
    -- Pattern: {feature_name}_{metric_type}
    
    -- Variance gradients
    variance_absolute_values TEXT,  -- JSON array of values at each percentile
    variance_absolute_slope REAL,  -- Overall slope from 100 to lowest valid
    variance_absolute_volatility REAL,  -- Standard deviation of step changes
    variance_absolute_monotonicity REAL,  -- Degree of monotonic behavior (-1 to 1)
    variance_absolute_directional_changes INTEGER,  -- Count of directional changes in gradient
    
    variance_normalized_values TEXT,
    variance_normalized_slope REAL,
    variance_normalized_volatility REAL,
    variance_normalized_monotonicity REAL,
    variance_normalized_directional_changes INTEGER,
    
    -- Skewness gradients
    skewness_absolute_values TEXT,
    skewness_absolute_slope REAL,
    skewness_absolute_volatility REAL,
    skewness_absolute_monotonicity REAL,
    skewness_absolute_directional_changes INTEGER,
    
    skewness_normalized_values TEXT,
    skewness_normalized_slope REAL,
    skewness_normalized_volatility REAL,
    skewness_normalized_monotonicity REAL,
    skewness_normalized_directional_changes INTEGER,
    
    -- Kurtosis gradients (with imputation flags)
    kurtosis_absolute_values TEXT,
    kurtosis_absolute_imputed_flags TEXT,  -- JSON array of booleans
    kurtosis_absolute_slope REAL,
    kurtosis_absolute_volatility REAL,
    kurtosis_absolute_monotonicity REAL,
    kurtosis_absolute_directional_changes INTEGER,
    
    kurtosis_normalized_values TEXT,
    kurtosis_normalized_imputed_flags TEXT,
    kurtosis_normalized_slope REAL,
    kurtosis_normalized_volatility REAL,
    kurtosis_normalized_monotonicity REAL,
    kurtosis_normalized_directional_changes INTEGER,
    
    -- Other statistical features
    gini_coefficient_values TEXT,
    gini_coefficient_slope REAL,
    gini_coefficient_volatility REAL,
    gini_coefficient_monotonicity REAL,
    gini_coefficient_directional_changes INTEGER,
    
    -- Engineered metrics gradients
    clumpiness_score_values TEXT,
    clumpiness_score_slope REAL,
    clumpiness_score_volatility REAL,
    clumpiness_score_monotonicity REAL,
    clumpiness_score_directional_changes INTEGER,
    
    selection_metric_values TEXT,
    selection_metric_slope REAL,
    selection_metric_volatility REAL,
    selection_metric_monotonicity REAL,
    selection_metric_directional_changes INTEGER,
    
    biggest_group_metric_values TEXT,
    biggest_group_metric_slope REAL,
    biggest_group_metric_volatility REAL,
    biggest_group_metric_monotonicity REAL,
    biggest_group_metric_directional_changes INTEGER,
    
    -- Nth percentile gap gradients (only valid above 20th percentile)
    nth_percentile_gap_5_values TEXT,
    nth_percentile_gap_5_slope REAL,
    nth_percentile_gap_5_volatility REAL,
    nth_percentile_gap_5_monotonicity REAL,
    nth_percentile_gap_5_directional_changes INTEGER,
    
    nth_percentile_gap_25_values TEXT,
    nth_percentile_gap_25_slope REAL,
    nth_percentile_gap_25_volatility REAL,
    nth_percentile_gap_25_monotonicity REAL,
    nth_percentile_gap_25_directional_changes INTEGER,
    
    nth_percentile_gap_50_values TEXT,
    nth_percentile_gap_50_slope REAL,
    nth_percentile_gap_50_volatility REAL,
    nth_percentile_gap_50_monotonicity REAL,
    nth_percentile_gap_50_directional_changes INTEGER,
    
    -- Competition metadata (denormalized for convenience)
    competition_name TEXT,
    competition_type TEXT,
    race_id INTEGER,
    race_name TEXT,
    race_category TEXT,
    race_year INTEGER,
    race_date DATE,
    total_finishers INTEGER,
    
    UNIQUE(competition_id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_gradients_race_category ON race_feature_gradients(race_category);
CREATE INDEX IF NOT EXISTS idx_gradients_coverage ON race_feature_gradients(percentile_coverage_ratio);
CREATE INDEX IF NOT EXISTS idx_gradients_variance_zero ON race_feature_gradients(variance_zero_percentile);
CREATE INDEX IF NOT EXISTS idx_gradients_kurtosis_null ON race_feature_gradients(kurtosis_null_percentile);