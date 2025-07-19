# Race Feature Analysis: One Day Races

Analysis Date: 2025-07-19T09:16:58.546457
Race Type Filter: one_day
Features Analyzed: 37
N Levels: [30, 40, 50, 60, 70, 80, 90, 100]

## Top 10 Features by Quality Score
1. proportion_in_groups: 0.704
2. gini_coefficient: 0.677
3. largest_group_size: 0.660
4. avg_group_size: 0.660
5. biggest_group_metric: 0.653
6. selection_metric: 0.653
7. std_group_size: 0.640
8. riders_in_groups: 0.625
9. included_finishers: 0.622
10. largest_group_position: 0.617

## Feature Behavior Patterns

### Stable Features (12)
total_finishers, included_finishers, abandon_ratio, winning_time, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, std_group_size, biggest_group_metric, clumpiness_score

### Dilution Features (15)
total_race_duration, variance_absolute, variance_normalized, std_deviation_absolute, std_deviation_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap

### Concentration Features (1)
avg_group_size

### Threshold Features (4)
skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized

### Bimodal Features (28)
included_finishers, abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, proportion_in_groups, avg_group_size, std_group_size, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric

### Complex Features (5)
gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric, selection_metric

## N-Level Recommendations by Analysis Type

### Elite Competition Analysis
**Recommended N levels**: [30, 40]
**Reasoning**: Best for analyzing competitive dynamics among top performers. 15 features show strong preference for elite focus.
**Key features**: skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized, gini_coefficient

### Balanced Field Analysis
**Recommended N levels**: [50, 60, 70]
**Reasoning**: Good compromise between competitive signal and field representation.
**Key features**: winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_absolute

### Inclusive Field Analysis
**Recommended N levels**: [80, 90, 100]
**Reasoning**: Best for understanding full field dynamics. 0 features perform optimally with broader inclusion.

### Comparative Analysis
**Recommended N levels**: [30, 60, 90]
**Reasoning**: Strategic sampling across competitive levels for comparative studies.

## Feature Behavior Summary
- **Elite-preferring features**: 15
- **Inclusive-preferring features**: 0
- **Stable across N features**: 19
- **Total features analyzed**: 37

## Traditional N-Level Sets
- **Minimal Set**: [30, 50, 80] (strategic sampling)
- **Balanced Set**: [30, 40, 60, 80, 90] (comprehensive coverage)
- **Comprehensive Set**: All N levels

## Statistical Performance Rankings
- **Best peak performance**: [30, 40, 90]
- **Most consistent**: [90, 70, 80]
- **Highest average scores**: [30, 40, 50]

## Feature Quality Tiers

### tier_1_high_quality (12 features)
proportion_in_groups, gini_coefficient, largest_group_size, avg_group_size, biggest_group_metric, selection_metric, std_group_size, riders_in_groups, included_finishers, largest_group_position, total_groups, 10th_percentile_gap

### tier_2_medium_quality (12 features)
clumpiness_score, 20th_percentile_gap, 15th_percentile_gap, shannon_entropy_absolute, 5th_percentile_gap, 25th_percentile_gap, abandon_ratio, 30th_percentile_gap, 35th_percentile_gap, 45th_percentile_gap, 40th_percentile_gap, 50th_percentile_gap

### tier_3_low_quality (13 features)
total_finishers, shannon_entropy_normalized, std_deviation_normalized, std_deviation_absolute, total_race_duration, skewness_absolute, skewness_normalized, winning_time, variance_normalized, variance_absolute, time_gap_evenness_metric, kurtosis_normalized, kurtosis_absolute