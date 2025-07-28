-- Create race_feature_gradients table with comprehensive schema
-- This table stores gradient metrics for how race features evolve across percentiles

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
    variance_zero_percentile INTEGER,  -- Percentile where variance hits zero
    kurtosis_null_percentile INTEGER,  -- Percentile where kurtosis becomes null
    monotonicity_break_percentile INTEGER,  -- Where features lose monotonic behavior
    
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
    
    -- Skewness gradients (with imputation flags)
    skewness_absolute_values TEXT,
    skewness_absolute_imputed_flags TEXT,  -- JSON array of booleans
    skewness_absolute_slope REAL,
    skewness_absolute_volatility REAL,
    skewness_absolute_monotonicity REAL,
    skewness_absolute_directional_changes INTEGER,
    
    skewness_normalized_values TEXT,
    skewness_normalized_imputed_flags TEXT,
    skewness_normalized_slope REAL,
    skewness_normalized_volatility REAL,
    skewness_normalized_monotonicity REAL,
    skewness_normalized_directional_changes INTEGER,
    
    -- Kurtosis gradients (with imputation flags)
    kurtosis_absolute_values TEXT,
    kurtosis_absolute_imputed_flags TEXT,
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
    
    -- Selectivity point analysis
    selectivity_point INTEGER,  -- Percentile where variance < threshold
    selectivity_sharpness REAL,  -- How suddenly variance drops
    pre_selectivity_slope REAL,  -- Variance trend before SP
    post_selectivity_slope REAL,  -- Variance trend after SP
    
    -- Post-selectivity metrics
    post_sp_spread REAL,  -- Std dev of gaps after SP
    post_sp_group_count INTEGER,  -- Number of groups after SP
    post_sp_isolation_ratio REAL,  -- Proportion riding alone
    post_sp_largest_group REAL,  -- Size of biggest group
    
    -- Gradient-derived features for race classification
    feature_stability_score REAL,  -- How stable features are across percentiles
    early_selection_indicator REAL,  -- How much selection happens in top percentiles
    progressive_selection_score REAL,  -- Gradual vs sudden selection
    racing_intensity_score REAL,  -- How much of field is racing vs riding
    attrition_pattern TEXT,  -- GROUPED/SCATTERED/MULTI_GROUP
    selectivity_type TEXT,  -- NONE/EARLY/PROGRESSIVE/LATE
    
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
CREATE INDEX IF NOT EXISTS idx_gradients_selectivity_type ON race_feature_gradients(selectivity_type);
CREATE INDEX IF NOT EXISTS idx_gradients_attrition_pattern ON race_feature_gradients(attrition_pattern);
CREATE INDEX IF NOT EXISTS idx_gradients_racing_intensity ON race_feature_gradients(racing_intensity_score);
CREATE INDEX IF NOT EXISTS idx_gradients_coverage ON race_feature_gradients(percentile_coverage_ratio);