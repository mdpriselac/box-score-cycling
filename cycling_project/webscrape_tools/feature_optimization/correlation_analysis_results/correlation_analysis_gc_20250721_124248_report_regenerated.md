# Correlation Feature Analysis: General Classification races

Analysis Date: 2025-07-21T12:42:48.803707
Competition Type: gc
Relevant Correlation Types: ['same_type']
Percentiles: [30, 40, 50, 60, 70, 80, 90, 100]

## Same Type Correlations
**Description**: Same race type correlations
**Features Analyzed**: 27

### Top 10 Features by Quality Score
1. gini_coefficient: 0.230
2. skewness_normalized: 0.227
3. skewness_absolute: 0.227
4. std_deviation_normalized: 0.221
5. variance_normalized: 0.215
6. riders_in_groups: 0.195
7. proportion_in_groups: 0.194
8. total_race_duration: 0.192
9. std_deviation_absolute: 0.187
10. selection_metric: 0.179

### Feature Behavior Patterns

**Threshold Features (11)**
abandon_ratio, gini_coefficient, kurtosis_absolute, kurtosis_normalized, largest_group_position, selection_metric, shannon_entropy_absolute, shannon_entropy_normalized, skewness_absolute, skewness_normalized

**Complex Features (12)**
avg_group_size, biggest_group_metric, clumpiness_score, included_finishers, largest_group_size, riders_in_groups, std_deviation_normalized, std_group_size, total_finishers, total_groups

**Stable Features (4)**
proportion_in_groups, std_deviation_absolute, variance_absolute, winning_time

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 15 features show strong preference for elite focus.
- Key features: abandon_ratio, avg_group_size, clumpiness_score, included_finishers, kurtosis_absolute

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.
- Key features: proportion_in_groups, std_deviation_absolute, variance_absolute, winning_time

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 7 features perform optimally with broader inclusion.
- Key features: biggest_group_metric, gini_coefficient, shannon_entropy_normalized, skewness_absolute, skewness_normalized

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 15
- **Inclusive-preferring features**: 7
- **Stable across percentiles**: 4
- **Total features analyzed**: 27

### Feature Quality Tiers

**Tier 1 High Quality (9 features)**
gini_coefficient, proportion_in_groups, riders_in_groups, skewness_absolute, skewness_normalized, std_deviation_absolute, std_deviation_normalized, total_race_duration, variance_normalized

**Tier 2 Medium Quality (9 features)**
kurtosis_absolute, kurtosis_normalized, largest_group_position, largest_group_size, selection_metric, shannon_entropy_normalized, std_group_size, variance_absolute, winning_time

**Tier 3 Low Quality (9 features)**
abandon_ratio, avg_group_size, biggest_group_metric, clumpiness_score, included_finishers, shannon_entropy_absolute, time_gap_evenness_metric, total_finishers, total_groups

## Competition-Level Recommendations
- **Best correlation type**: same_type (highest number of high-quality features)