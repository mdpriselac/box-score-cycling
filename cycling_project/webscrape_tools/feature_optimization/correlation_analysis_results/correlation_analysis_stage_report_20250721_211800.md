# Correlation Feature Analysis: Stage races

Analysis Date: 2025-07-21T21:18:00.045881
Competition Type: stage
Relevant Correlation Types: ['same_type', 'stage_one_days']
Percentiles: [30, 40, 50, 60, 70, 80, 90, 100]

## Same Type Correlations
**Description**: Same race type correlations
**Features Analyzed**: 37

### Top 10 Features by Quality Score
1. skewness_normalized: 0.265
2. skewness_absolute: 0.265
3. kurtosis_normalized: 0.249
4. kurtosis_absolute: 0.249
5. total_race_duration: 0.192
6. std_deviation_absolute: 0.187
7. riders_in_groups: 0.182
8. variance_absolute: 0.181
9. selection_metric: 0.178
10. 50th_percentile_gap: 0.172

### Feature Behavior Patterns

**Complex Features (15)**
10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, 5th_percentile_gap

**Threshold Features (22)**
abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, gini_coefficient, kurtosis_absolute, kurtosis_normalized, largest_group_position, largest_group_size, proportion_in_groups

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 27 features show strong preference for elite focus.
- Key features: 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 5 features perform optimally with broader inclusion.
- Key features: included_finishers, largest_group_size, riders_in_groups, std_group_size, total_finishers

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 27
- **Inclusive-preferring features**: 5
- **Stable across percentiles**: 0
- **Total features analyzed**: 37

### Feature Quality Tiers

**Tier 1 High Quality (13 features)**
45th_percentile_gap, 50th_percentile_gap, clumpiness_score, kurtosis_absolute, kurtosis_normalized, proportion_in_groups, riders_in_groups, selection_metric, skewness_absolute, skewness_normalized, std_deviation_absolute, total_race_duration, variance_absolute

**Tier 2 Medium Quality (12 features)**
25th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, biggest_group_metric, included_finishers, largest_group_size, shannon_entropy_absolute, shannon_entropy_normalized, std_deviation_normalized, time_gap_evenness_metric, total_finishers, total_groups

**Tier 3 Low Quality (12 features)**
10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 30th_percentile_gap, 5th_percentile_gap, abandon_ratio, avg_group_size, gini_coefficient, largest_group_position, std_group_size, variance_normalized, winning_time

## Stage One Days Correlations
**Description**: Stage + One-day correlations
**Features Analyzed**: 37

### Top 10 Features by Quality Score
1. kurtosis_normalized: 0.298
2. kurtosis_absolute: 0.298
3. skewness_normalized: 0.275
4. skewness_absolute: 0.275
5. total_finishers: 0.126
6. included_finishers: 0.126
7. winning_time: 0.119
8. 20th_percentile_gap: 0.087
9. 25th_percentile_gap: 0.081
10. 30th_percentile_gap: 0.080

### Feature Behavior Patterns

**Threshold Features (35)**
10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, abandon_ratio

**Complex Features (2)**
5th_percentile_gap, winning_time

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 20 features show strong preference for elite focus.
- Key features: 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 0 features perform optimally with broader inclusion.

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 20
- **Inclusive-preferring features**: 0
- **Stable across percentiles**: 0
- **Total features analyzed**: 37

### Feature Quality Tiers

**Tier 1 High Quality (13 features)**
15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, included_finishers, kurtosis_absolute, kurtosis_normalized, skewness_absolute, skewness_normalized, total_finishers, winning_time

**Tier 2 Medium Quality (12 features)**
10th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, 5th_percentile_gap, abandon_ratio, biggest_group_metric, largest_group_position, proportion_in_groups, riders_in_groups, std_deviation_normalized, time_gap_evenness_metric, variance_normalized

**Tier 3 Low Quality (12 features)**
avg_group_size, clumpiness_score, gini_coefficient, largest_group_size, selection_metric, shannon_entropy_absolute, shannon_entropy_normalized, std_deviation_absolute, std_group_size, total_groups, total_race_duration, variance_absolute

## Competition-Level Recommendations
- **Best correlation type**: same_type (highest number of high-quality features)
- **High-quality feature overlap**: 4 features consistently high-quality across correlation types
  - kurtosis_normalized, skewness_absolute, skewness_normalized, kurtosis_absolute