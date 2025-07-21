# Correlation Feature Analysis: One-day races

Analysis Date: 2025-07-21T12:30:35.108709
Competition Type: one_day
Relevant Correlation Types: ['same_type', 'stage_one_days']
Percentiles: [30, 40, 50, 60, 70, 80, 90, 100]

## Same Type Correlations
**Description**: Same race type correlations
**Features Analyzed**: 27

### Top 10 Features by Quality Score
1. shannon_entropy_absolute: 0.258
2. avg_group_size: 0.254
3. total_groups: 0.252
4. clumpiness_score: 0.250
5. largest_group_size: 0.245
6. time_gap_evenness_metric: 0.241
7. proportion_in_groups: 0.240
8. total_race_duration: 0.232
9. selection_metric: 0.223
10. std_deviation_normalized: 0.222

### Feature Behavior Patterns

**Threshold Features (22)**
abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, gini_coefficient, included_finishers, kurtosis_absolute, kurtosis_normalized, largest_group_position, largest_group_size

**Dilution Features (1)**
proportion_in_groups

**Complex Features (3)**
std_deviation_absolute, variance_absolute, winning_time

**Concentration Features (1)**
total_race_duration

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 23 features show strong preference for elite focus.
- Key features: abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, included_finishers

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 3 features perform optimally with broader inclusion.
- Key features: gini_coefficient, skewness_absolute, skewness_normalized

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 23
- **Inclusive-preferring features**: 3
- **Stable across percentiles**: 0
- **Total features analyzed**: 27

### Feature Quality Tiers

**Tier 1 High Quality (9 features)**
avg_group_size, clumpiness_score, largest_group_size, proportion_in_groups, selection_metric, shannon_entropy_absolute, time_gap_evenness_metric, total_groups, total_race_duration

**Tier 2 Medium Quality (9 features)**
biggest_group_metric, included_finishers, largest_group_position, riders_in_groups, shannon_entropy_normalized, std_deviation_absolute, std_deviation_normalized, total_finishers, variance_normalized

**Tier 3 Low Quality (9 features)**
abandon_ratio, gini_coefficient, kurtosis_absolute, kurtosis_normalized, skewness_absolute, skewness_normalized, std_group_size, variance_absolute, winning_time

## Stage One Days Correlations
**Description**: Stage + One-day correlations
**Features Analyzed**: 27

### Top 10 Features by Quality Score
1. skewness_normalized: 0.194
2. skewness_absolute: 0.194
3. clumpiness_score: 0.193
4. std_group_size: 0.178
5. winning_time: 0.167
6. gini_coefficient: 0.164
7. kurtosis_normalized: 0.144
8. kurtosis_absolute: 0.144
9. largest_group_position: 0.083
10. abandon_ratio: 0.080

### Feature Behavior Patterns

**Threshold Features (24)**
abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, gini_coefficient, included_finishers, kurtosis_absolute, kurtosis_normalized, largest_group_position, riders_in_groups

**Complex Features (3)**
largest_group_size, proportion_in_groups, time_gap_evenness_metric

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 16 features show strong preference for elite focus.
- Key features: abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, gini_coefficient

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 2 features perform optimally with broader inclusion.
- Key features: kurtosis_absolute, kurtosis_normalized

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 16
- **Inclusive-preferring features**: 2
- **Stable across percentiles**: 0
- **Total features analyzed**: 27

### Feature Quality Tiers

**Tier 1 High Quality (9 features)**
clumpiness_score, gini_coefficient, kurtosis_absolute, kurtosis_normalized, largest_group_position, skewness_absolute, skewness_normalized, std_group_size, winning_time

**Tier 2 Medium Quality (9 features)**
abandon_ratio, avg_group_size, biggest_group_metric, largest_group_size, proportion_in_groups, shannon_entropy_absolute, total_groups, total_race_duration, variance_normalized

**Tier 3 Low Quality (9 features)**
included_finishers, riders_in_groups, selection_metric, shannon_entropy_normalized, std_deviation_absolute, std_deviation_normalized, time_gap_evenness_metric, total_finishers, variance_absolute

## Competition-Level Recommendations
- **Best correlation type**: same_type (highest number of high-quality features)
- **High-quality feature overlap**: 1 features consistently high-quality across correlation types
  - clumpiness_score