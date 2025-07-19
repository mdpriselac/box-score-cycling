# Race Feature Analysis: All Race Types

Analysis Date: 2025-07-19T09:21:52.206468
Race Type Filter: None
Features Analyzed: 37
N Levels: [30, 40, 50, 60, 70, 80, 90, 100]

## Top 10 Features by Quality Score
1. biggest_group_metric: 0.705
2. largest_group_position: 0.702
3. proportion_in_groups: 0.693
4. 30th_percentile_gap: 0.677
5. gini_coefficient: 0.673
6. largest_group_size: 0.666
7. clumpiness_score: 0.659
8. 25th_percentile_gap: 0.659
9. riders_in_groups: 0.649
10. selection_metric: 0.647

## Feature Behavior Patterns

### Stable Features (13)
total_finishers, included_finishers, abandon_ratio, winning_time, 5th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, time_gap_evenness_metric, clumpiness_score

### Dilution Features (14)
total_race_duration, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size

### Concentration Features (1)
avg_group_size

### Threshold Features (5)
variance_absolute, variance_normalized, std_deviation_normalized, skewness_absolute, skewness_normalized

### Bimodal Features (25)
abandon_ratio, winning_time, total_race_duration, variance_absolute, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric

### Complex Features (4)
gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, selection_metric

## N-Level Recommendations by Analysis Type

### Elite Competition Analysis
**Recommended N levels**: [30, 40]
**Reasoning**: Best for analyzing competitive dynamics among top performers. 17 features show strong preference for elite focus.
**Key features**: abandon_ratio, variance_absolute, variance_normalized, std_deviation_normalized, skewness_absolute

### Balanced Field Analysis
**Recommended N levels**: [50, 60, 70]
**Reasoning**: Good compromise between competitive signal and field representation.
**Key features**: winning_time, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 10th_percentile_gap

### Inclusive Field Analysis
**Recommended N levels**: [80, 90, 100]
**Reasoning**: Best for understanding full field dynamics. 0 features perform optimally with broader inclusion.

### Comparative Analysis
**Recommended N levels**: [30, 60, 90]
**Reasoning**: Strategic sampling across competitive levels for comparative studies.

## Feature Behavior Summary
- **Elite-preferring features**: 17
- **Inclusive-preferring features**: 0
- **Stable across N features**: 16
- **Total features analyzed**: 37

## Traditional N-Level Sets
- **Minimal Set**: [30, 50, 80] (strategic sampling)
- **Balanced Set**: [30, 40, 60, 80, 90] (comprehensive coverage)
- **Comprehensive Set**: All N levels

## Statistical Performance Rankings
- **Best peak performance**: [30, 60, 40]
- **Most consistent**: [80, 90, 70]
- **Highest average scores**: [30, 40, 60]

## Feature Quality Tiers

### tier_1_high_quality (12 features)
biggest_group_metric, largest_group_position, proportion_in_groups, 30th_percentile_gap, gini_coefficient, largest_group_size, clumpiness_score, 25th_percentile_gap, riders_in_groups, selection_metric, shannon_entropy_absolute, shannon_entropy_normalized

### tier_2_medium_quality (12 features)
included_finishers, total_groups, 5th_percentile_gap, 10th_percentile_gap, 35th_percentile_gap, abandon_ratio, 20th_percentile_gap, std_group_size, 40th_percentile_gap, 15th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap

### tier_3_low_quality (13 features)
std_deviation_absolute, total_finishers, total_race_duration, variance_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, winning_time, avg_group_size, time_gap_evenness_metric, variance_normalized, skewness_normalized, skewness_absolute