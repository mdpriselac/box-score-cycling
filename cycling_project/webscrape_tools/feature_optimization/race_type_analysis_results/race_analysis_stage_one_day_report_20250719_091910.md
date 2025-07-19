# Race Feature Analysis: Stage + One Day Races

Analysis Date: 2025-07-19T09:19:10.405837
Race Type Filter: ['stage', 'one_day']
Features Analyzed: 37
N Levels: [30, 40, 50, 60, 70, 80, 90, 100]

## Top 10 Features by Quality Score
1. biggest_group_metric: 0.705
2. gini_coefficient: 0.672
3. largest_group_size: 0.663
4. clumpiness_score: 0.660
5. shannon_entropy_normalized: 0.658
6. largest_group_position: 0.657
7. riders_in_groups: 0.648
8. selection_metric: 0.648
9. shannon_entropy_absolute: 0.647
10. included_finishers: 0.637

## Feature Behavior Patterns

### Stable Features (15)
total_finishers, included_finishers, abandon_ratio, winning_time, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, clumpiness_score

### Dilution Features (13)
total_race_duration, variance_absolute, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size

### Concentration Features (1)
avg_group_size

### Threshold Features (3)
variance_normalized, skewness_absolute, skewness_normalized

### Bimodal Features (25)
abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric

### Complex Features (5)
gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric, selection_metric

## N-Level Recommendations by Analysis Type

### Elite Competition Analysis
**Recommended N levels**: [30, 40]
**Reasoning**: Best for analyzing competitive dynamics among top performers. 17 features show strong preference for elite focus.
**Key features**: abandon_ratio, variance_absolute, std_deviation_absolute, std_deviation_normalized, gini_coefficient

### Balanced Field Analysis
**Recommended N levels**: [50, 60, 70]
**Reasoning**: Good compromise between competitive signal and field representation.
**Key features**: winning_time, skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized

### Inclusive Field Analysis
**Recommended N levels**: [80, 90, 100]
**Reasoning**: Best for understanding full field dynamics. 0 features perform optimally with broader inclusion.

### Comparative Analysis
**Recommended N levels**: [30, 60, 90]
**Reasoning**: Strategic sampling across competitive levels for comparative studies.

## Feature Behavior Summary
- **Elite-preferring features**: 17
- **Inclusive-preferring features**: 0
- **Stable across N features**: 15
- **Total features analyzed**: 37

## Traditional N-Level Sets
- **Minimal Set**: [30, 50, 80] (strategic sampling)
- **Balanced Set**: [30, 40, 60, 80, 90] (comprehensive coverage)
- **Comprehensive Set**: All N levels

## Statistical Performance Rankings
- **Best peak performance**: [30, 40, 50]
- **Most consistent**: [90, 80, 70]
- **Highest average scores**: [30, 40, 50]

## Feature Quality Tiers

### tier_1_high_quality (12 features)
biggest_group_metric, gini_coefficient, largest_group_size, clumpiness_score, shannon_entropy_normalized, largest_group_position, riders_in_groups, selection_metric, shannon_entropy_absolute, included_finishers, total_groups, 15th_percentile_gap

### tier_2_medium_quality (12 features)
5th_percentile_gap, 10th_percentile_gap, 20th_percentile_gap, variance_normalized, winning_time, 25th_percentile_gap, std_group_size, abandon_ratio, 30th_percentile_gap, 35th_percentile_gap, std_deviation_normalized, 40th_percentile_gap

### tier_3_low_quality (13 features)
45th_percentile_gap, 50th_percentile_gap, std_deviation_absolute, total_finishers, total_race_duration, variance_absolute, kurtosis_absolute, kurtosis_normalized, time_gap_evenness_metric, avg_group_size, proportion_in_groups, skewness_normalized, skewness_absolute