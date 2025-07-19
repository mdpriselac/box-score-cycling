# Race Feature Analysis: Gc Races

Analysis Date: 2025-07-19T09:15:10.433056
Race Type Filter: gc
Features Analyzed: 37
N Levels: [30, 40, 50, 60, 70, 80, 90, 100]

## Top 10 Features by Quality Score
1. shannon_entropy_absolute: 0.733
2. proportion_in_groups: 0.714
3. kurtosis_absolute: 0.695
4. kurtosis_normalized: 0.695
5. 25th_percentile_gap: 0.688
6. 5th_percentile_gap: 0.686
7. 30th_percentile_gap: 0.669
8. riders_in_groups: 0.657
9. selection_metric: 0.657
10. gini_coefficient: 0.656

## Feature Behavior Patterns

### Stable Features (15)
total_finishers, included_finishers, abandon_ratio, winning_time, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric

### Dilution Features (16)
total_race_duration, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, largest_group_size, largest_group_position, avg_group_size

### Concentration Features (1)
std_group_size

### Threshold Features (5)
variance_absolute, variance_normalized, std_deviation_normalized, skewness_absolute, skewness_normalized

### Bimodal Features (30)
total_finishers, included_finishers, abandon_ratio, total_race_duration, variance_absolute, std_deviation_absolute, skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, avg_group_size, std_group_size, biggest_group_metric, clumpiness_score, selection_metric

## N-Level Recommendations by Analysis Type

### Elite Competition Analysis
**Recommended N levels**: [30, 40]
**Reasoning**: Best for analyzing competitive dynamics among top performers. 10 features show strong preference for elite focus.
**Key features**: abandon_ratio, variance_absolute, variance_normalized, kurtosis_absolute, kurtosis_normalized

### Balanced Field Analysis
**Recommended N levels**: [50, 60, 70]
**Reasoning**: Good compromise between competitive signal and field representation.
**Key features**: winning_time, total_race_duration, std_deviation_absolute, std_deviation_normalized, skewness_absolute

### Inclusive Field Analysis
**Recommended N levels**: [80, 90, 100]
**Reasoning**: Best for understanding full field dynamics. 0 features perform optimally with broader inclusion.

### Comparative Analysis
**Recommended N levels**: [30, 60, 90]
**Reasoning**: Strategic sampling across competitive levels for comparative studies.

## Feature Behavior Summary
- **Elite-preferring features**: 10
- **Inclusive-preferring features**: 0
- **Stable across N features**: 25
- **Total features analyzed**: 37

## Traditional N-Level Sets
- **Minimal Set**: [30, 50, 80] (strategic sampling)
- **Balanced Set**: [30, 40, 60, 80, 90] (comprehensive coverage)
- **Comprehensive Set**: All N levels

## Statistical Performance Rankings
- **Best peak performance**: [30, 80, 90]
- **Most consistent**: [90, 80, 70]
- **Highest average scores**: [30, 40, 50]

## Feature Quality Tiers

### tier_1_high_quality (12 features)
shannon_entropy_absolute, proportion_in_groups, kurtosis_absolute, kurtosis_normalized, 25th_percentile_gap, 5th_percentile_gap, 30th_percentile_gap, riders_in_groups, selection_metric, gini_coefficient, included_finishers, total_groups

### tier_2_medium_quality (12 features)
20th_percentile_gap, 35th_percentile_gap, largest_group_position, abandon_ratio, 40th_percentile_gap, 10th_percentile_gap, largest_group_size, 45th_percentile_gap, 50th_percentile_gap, 15th_percentile_gap, std_deviation_absolute, total_race_duration

### tier_3_low_quality (13 features)
time_gap_evenness_metric, avg_group_size, winning_time, total_finishers, clumpiness_score, variance_absolute, biggest_group_metric, shannon_entropy_normalized, skewness_absolute, skewness_normalized, std_group_size, std_deviation_normalized, variance_normalized