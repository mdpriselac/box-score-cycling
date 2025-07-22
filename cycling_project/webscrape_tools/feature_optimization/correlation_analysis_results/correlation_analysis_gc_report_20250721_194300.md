# Correlation Feature Analysis: General Classification races

Analysis Date: 2025-07-21T19:43:00.427948
Competition Type: gc
Relevant Correlation Types: ['same_type']
Percentiles: [30, 40, 50, 60, 70, 80, 90, 100]

## Same Type Correlations
**Description**: Same race type correlations
**Features Analyzed**: 37

### Top 10 Features by Quality Score
1. gini_coefficient: 0.230
2. skewness_normalized: 0.227
3. skewness_absolute: 0.227
4. std_deviation_normalized: 0.221
5. variance_normalized: 0.215
6. 30th_percentile_gap: 0.207
7. 25th_percentile_gap: 0.200
8. 35th_percentile_gap: 0.196
9. riders_in_groups: 0.195
10. 20th_percentile_gap: 0.194

### Feature Behavior Patterns

**Complex Features (22)**
10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, 5th_percentile_gap

**Threshold Features (11)**
abandon_ratio, gini_coefficient, kurtosis_absolute, kurtosis_normalized, largest_group_position, selection_metric, shannon_entropy_absolute, shannon_entropy_normalized, skewness_absolute, skewness_normalized

**Stable Features (4)**
proportion_in_groups, std_deviation_absolute, variance_absolute, winning_time

### Percentile Recommendations by Analysis Type

**Elite Performance Analysis**
- Recommended percentiles: [30, 40]
- Reasoning: Best for analyzing competitive dynamics among top performers. 17 features show strong preference for elite focus.
- Key features: 45th_percentile_gap, 50th_percentile_gap, abandon_ratio, avg_group_size, clumpiness_score

**Balanced Performance Analysis**
- Recommended percentiles: [50, 60, 70]
- Reasoning: Good compromise between competitive signal and field representation. Ideal for general performance characterization.
- Key features: proportion_in_groups, std_deviation_absolute, variance_absolute, winning_time

**Inclusive Performance Analysis**
- Recommended percentiles: [80, 90, 100]
- Reasoning: Best for understanding full field dynamics. 15 features perform optimally with broader inclusion.
- Key features: 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap

**Comparative Analysis**
- Recommended percentiles: [30, 60, 90]
- Reasoning: Strategic sampling across competitive levels for comparative studies.

### Feature Behavior Summary
- **Elite-preferring features**: 17
- **Inclusive-preferring features**: 15
- **Stable across percentiles**: 4
- **Total features analyzed**: 37

### Feature Quality Tiers

**Tier 1 High Quality (13 features)**
20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, gini_coefficient, proportion_in_groups, riders_in_groups, skewness_absolute, skewness_normalized, std_deviation_absolute, std_deviation_normalized, total_race_duration, variance_normalized

**Tier 2 Medium Quality (12 features)**
10th_percentile_gap, 15th_percentile_gap, biggest_group_metric, kurtosis_absolute, kurtosis_normalized, largest_group_position, largest_group_size, selection_metric, shannon_entropy_normalized, std_group_size, variance_absolute, winning_time

**Tier 3 Low Quality (12 features)**
40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, 5th_percentile_gap, abandon_ratio, avg_group_size, clumpiness_score, included_finishers, shannon_entropy_absolute, time_gap_evenness_metric, total_finishers, total_groups

## Competition-Level Recommendations
- **Best correlation type**: same_type (highest number of high-quality features)