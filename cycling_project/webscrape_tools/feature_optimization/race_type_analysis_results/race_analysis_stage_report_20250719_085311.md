# Race Feature Analysis: Stage Races

Analysis Date: 2025-07-19T08:53:11.865735
Race Type Filter: stage
Features Analyzed: 37
N Levels: [30, 40, 50, 60, 70, 80, 90, 100]

## Top 10 Features by Quality Score
1. biggest_group_metric: 0.713
2. riders_in_groups: 0.701
3. largest_group_position: 0.677
4. largest_group_size: 0.674
5. shannon_entropy_normalized: 0.674
6. clumpiness_score: 0.673
7. gini_coefficient: 0.671
8. included_finishers: 0.666
9. shannon_entropy_absolute: 0.655
10. selection_metric: 0.650

## Feature Behavior Patterns

### Stable Features (16)
total_finishers, included_finishers, abandon_ratio, winning_time, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, clumpiness_score

### Dilution Features (12)
total_race_duration, variance_absolute, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size

### Concentration Features (1)
avg_group_size

### Threshold Features (4)
variance_normalized, skewness_absolute, skewness_normalized, selection_metric

### Bimodal Features (28)
abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, proportion_in_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric

### Complex Features (4)
gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric

## Recommended N Levels
- Minimal Set (60% coverage): [30]
- Balanced Set (85% coverage): [30]
- Comprehensive Set: [30, 40, 50, 60, 70, 80, 90, 100]

## Feature Quality Tiers

### tier_1_high_quality (12 features)
biggest_group_metric, riders_in_groups, largest_group_position, largest_group_size, shannon_entropy_normalized, clumpiness_score, gini_coefficient, included_finishers, shannon_entropy_absolute, selection_metric, total_groups, 15th_percentile_gap

### tier_2_medium_quality (12 features)
5th_percentile_gap, 10th_percentile_gap, 20th_percentile_gap, variance_normalized, 25th_percentile_gap, abandon_ratio, 30th_percentile_gap, std_deviation_normalized, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap

### tier_3_low_quality (13 features)
std_group_size, std_deviation_absolute, total_race_duration, variance_absolute, kurtosis_absolute, kurtosis_normalized, total_finishers, winning_time, skewness_normalized, skewness_absolute, time_gap_evenness_metric, avg_group_size, proportion_in_groups