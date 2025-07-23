# Race Feature Gradients Design

## Overview

The race feature gradients system analyzes how race characteristics change as we move from analyzing the full field (100th percentile) to just the top performers (10th percentile). This gradient analysis will help identify distinct race "kinds" based on how features evolve across percentiles.

## Key Objectives

1. **Track Feature Evolution**: Monitor how each statistical and engineered feature changes across percentiles
2. **Handle Missing Data**: Gracefully manage competitions that don't meet minimum requirements at restrictive percentiles
3. **Impute Null Values**: Strategic imputation for metrics like kurtosis that can become null
4. **Enable Race Classification**: Create gradient-based features that distinguish different types of races

## Data Architecture

### Primary Table: `race_feature_gradients`

```sql
CREATE TABLE race_feature_gradients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    competition_id INTEGER NOT NULL,
    
    -- Metadata
    extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    valid_percentiles TEXT,  -- JSON array of percentiles with valid data [10,15,20,...,100]
    missing_percentiles TEXT,  -- JSON array of percentiles with no data
    
    -- Coverage metrics
    percentile_coverage_ratio REAL,  -- % of percentiles with valid data
    lowest_valid_percentile INTEGER,  -- Lowest percentile with valid data
    
    -- For each feature, store gradient metrics
    -- Pattern: {feature_name}_{metric_type}
    
    -- Variance gradients
    variance_absolute_values TEXT,  -- JSON array of values at each percentile
    variance_absolute_slope REAL,  -- Overall slope from 100 to lowest valid
    variance_absolute_volatility REAL,  -- Standard deviation of step changes
    variance_absolute_monotonicity REAL,  -- Degree of monotonic behavior (-1 to 1)
    
    variance_normalized_values TEXT,
    variance_normalized_slope REAL,
    variance_normalized_volatility REAL,
    variance_normalized_monotonicity REAL,
    
    -- Skewness gradients (with imputation flags)
    skewness_absolute_values TEXT,
    skewness_absolute_imputed_flags TEXT,  -- JSON array of booleans
    skewness_absolute_slope REAL,
    skewness_absolute_volatility REAL,
    skewness_absolute_monotonicity REAL,
    
    skewness_normalized_values TEXT,
    skewness_normalized_imputed_flags TEXT,
    skewness_normalized_slope REAL,
    skewness_normalized_volatility REAL,
    skewness_normalized_monotonicity REAL,
    
    -- Kurtosis gradients (with imputation flags)
    kurtosis_absolute_values TEXT,
    kurtosis_absolute_imputed_flags TEXT,
    kurtosis_absolute_slope REAL,
    kurtosis_absolute_volatility REAL,
    kurtosis_absolute_monotonicity REAL,
    
    kurtosis_normalized_values TEXT,
    kurtosis_normalized_imputed_flags TEXT,
    kurtosis_normalized_slope REAL,
    kurtosis_normalized_volatility REAL,
    kurtosis_normalized_monotonicity REAL,
    
    -- Other statistical features
    gini_coefficient_values TEXT,
    gini_coefficient_slope REAL,
    gini_coefficient_volatility REAL,
    gini_coefficient_monotonicity REAL,
    
    -- Engineered metrics gradients
    clumpiness_score_values TEXT,
    clumpiness_score_slope REAL,
    clumpiness_score_volatility REAL,
    clumpiness_score_monotonicity REAL,
    
    selection_metric_values TEXT,
    selection_metric_slope REAL,
    selection_metric_volatility REAL,
    selection_metric_monotonicity REAL,
    
    biggest_group_metric_values TEXT,
    biggest_group_metric_slope REAL,
    biggest_group_metric_volatility REAL,
    biggest_group_metric_monotonicity REAL,
    
    -- Gradient-derived features for race classification
    feature_stability_score REAL,  -- How stable features are across percentiles
    early_selection_indicator REAL,  -- How much selection happens in top percentiles
    progressive_selection_score REAL,  -- Gradual vs sudden selection
    
    UNIQUE(competition_id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id)
);
```

## Gradient Metrics Explained

For each feature, we calculate:

1. **values**: JSON array storing the feature value at each percentile [10, 15, 20, ..., 100]
2. **slope**: Overall trend from 100th to lowest valid percentile
3. **volatility**: Standard deviation of step-to-step changes (measures smoothness)
4. **monotonicity**: Score from -1 to 1:
   - 1.0 = perfectly increasing
   - -1.0 = perfectly decreasing  
   - 0.0 = no consistent direction

## Imputation Strategy

### For Kurtosis/Skewness Nulls

1. **Local Linear Interpolation**: When a value is null between two valid values
2. **Endpoint Extension**: When nulls occur at extremes, use nearest valid neighbor
3. **Global Feature Median**: When sparse data, use median from same percentile across similar races
4. **Zero Imputation**: Last resort for cases with no variance

### Imputation Priority
```python
def impute_value(feature, percentile, competition_id):
    # 1. Try linear interpolation from adjacent percentiles
    if has_adjacent_valid_values():
        return linear_interpolate()
    
    # 2. Try similar race median at same percentile
    similar_races = find_similar_races(competition_id)  # Same category, type
    if similar_race_median := get_median(similar_races, feature, percentile):
        return similar_race_median
    
    # 3. Use endpoint extension
    if nearest_valid := find_nearest_valid_percentile():
        return values[nearest_valid]
    
    # 4. Default to 0 (indicates no distribution shape)
    return 0.0
```

## Handling Missing Data

### Coverage Requirements

- Minimum 3 valid percentiles to create gradient entry
- Must include 100th percentile (baseline)
- Track `percentile_coverage_ratio` for quality assessment

### Missing Data Patterns

1. **Sparse Coverage**: Competition only valid at high percentiles (90, 95, 100)
   - Still calculate gradients but flag as "limited coverage"
   
2. **Gap Patterns**: Valid at 100, 90, 80, missing at 70, valid at 60
   - Interpolate across gaps for gradient calculation
   
3. **Truncated Series**: Valid from 100 down to some threshold
   - Natural pattern for smaller races
   - Calculate gradients only on valid range

## Gradient Calculation Methodology

### Basic Gradient Calculation
```python
def calculate_gradient_metrics(values, percentiles):
    # Remove None values and align percentiles
    valid_pairs = [(p, v) for p, v in zip(percentiles, values) if v is not None]
    
    if len(valid_pairs) < 3:
        return None  # Insufficient data
    
    percentiles, values = zip(*valid_pairs)
    
    # Overall slope (using linear regression)
    slope, intercept = np.polyfit(percentiles, values, 1)
    
    # Step-to-step volatility
    steps = np.diff(values)
    volatility = np.std(steps) if len(steps) > 0 else 0
    
    # Monotonicity score
    increasing = sum(1 for s in steps if s > 0)
    decreasing = sum(1 for s in steps if s < 0)
    total_steps = len(steps)
    
    if total_steps > 0:
        monotonicity = (increasing - decreasing) / total_steps
    else:
        monotonicity = 0
    
    return {
        'slope': slope,
        'volatility': volatility,
        'monotonicity': monotonicity
    }
```

## Gradient-Derived Features

### 1. Feature Stability Score
Measures how consistently features behave across percentiles
```python
stability = 1 / (1 + avg_volatility_across_features)
```

### 2. Early Selection Indicator  
Measures how much the race changes in top percentiles (10-30%) vs rest
```python
early_changes = sum(abs_changes for 10-30%)
total_changes = sum(abs_changes for 10-100%)
early_selection = early_changes / total_changes if total_changes > 0 else 0
```

### 3. Progressive Selection Score
Distinguishes gradual vs sudden selection
```python
# High score = gradual/progressive selection
# Low score = sudden selection at specific points
progressive_score = 1 - (max_step_change / total_range) if total_range > 0 else 0
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create gradient table schema
2. Build gradient calculation functions
3. Implement basic imputation strategies

### Phase 2: Data Population
1. Process all competitions with sufficient percentile coverage
2. Handle edge cases and missing data patterns
3. Validate gradient calculations

### Phase 3: Feature Engineering
1. Calculate gradient-derived features
2. Analyze patterns across race types
3. Identify discriminative gradients for race classification

### Phase 4: Integration
1. Connect gradients to race kind classification
2. Create visualization tools for gradient patterns
3. Build API for gradient-based queries

## Example Usage

```python
# Calculate gradients for a competition
gradients = calculate_race_gradients(competition_id=1234)

# Query races with similar gradient patterns
similar_races = find_races_by_gradient_pattern(
    reference_competition=1234,
    features=['variance_normalized', 'clumpiness_score'],
    similarity_threshold=0.85
)

# Classify race based on gradients
race_kind = classify_race_by_gradients(competition_id=1234)
```

## Success Metrics

1. **Coverage**: >90% of competitions have gradient data
2. **Imputation Quality**: <10% of gradient values are imputed
3. **Classification Power**: Gradient features improve race classification accuracy by >15%
4. **Stability**: Gradient calculations are reproducible and stable

## Next Steps

1. Review and refine the design
2. Create prototype implementation
3. Test on sample competitions
4. Iterate based on findings