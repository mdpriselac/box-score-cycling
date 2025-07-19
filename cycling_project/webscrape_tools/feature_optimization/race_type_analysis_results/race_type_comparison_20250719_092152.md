# Race Type Comparison Analysis

Generated: 2025-07-19 09:21:52

## Analysis Overview
| Race Type | Features Analyzed | Top Quality Feature | Top Quality Score |
|-----------|-------------------|--------------------|--------------------|
| Gc Races | 37 | shannon_entropy_absolute | 0.733 |
| Stage Races | 37 | biggest_group_metric | 0.713 |
| One Day Races | 37 | proportion_in_groups | 0.704 |
| Stage + One Day Races | 37 | biggest_group_metric | 0.705 |
| All Race Types | 37 | biggest_group_metric | 0.705 |

## Feature Behavior Patterns by Race Type

### Bimodal Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 30 | total_finishers, included_finishers, abandon_ratio, total_race_duration, variance_absolute, std_deviation_absolute, skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, avg_group_size, std_group_size, biggest_group_metric, clumpiness_score, selection_metric |
| Stage Races | 28 | abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, proportion_in_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric |
| One Day Races | 28 | included_finishers, abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, proportion_in_groups, avg_group_size, std_group_size, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric |
| Stage + One Day Races | 25 | abandon_ratio, winning_time, total_race_duration, variance_absolute, variance_normalized, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric |
| All Race Types | 25 | abandon_ratio, winning_time, total_race_duration, variance_absolute, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, shannon_entropy_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, total_groups, largest_group_size, largest_group_position, avg_group_size, biggest_group_metric, clumpiness_score, selection_metric |

### Complex Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 0 |  |
| Stage Races | 4 | gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric |
| One Day Races | 5 | gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric, selection_metric |
| Stage + One Day Races | 5 | gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, time_gap_evenness_metric, selection_metric |
| All Race Types | 4 | gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, selection_metric |

### Concentration Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 1 | std_group_size |
| Stage Races | 1 | avg_group_size |
| One Day Races | 1 | avg_group_size |
| Stage + One Day Races | 1 | avg_group_size |
| All Race Types | 1 | avg_group_size |

### Dilution Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 16 | total_race_duration, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, largest_group_size, largest_group_position, avg_group_size |
| Stage Races | 12 | total_race_duration, variance_absolute, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size |
| One Day Races | 15 | total_race_duration, variance_absolute, variance_normalized, std_deviation_absolute, std_deviation_normalized, 5th_percentile_gap, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap |
| Stage + One Day Races | 13 | total_race_duration, variance_absolute, std_deviation_absolute, std_deviation_normalized, kurtosis_absolute, kurtosis_normalized, 5th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size |
| All Race Types | 14 | total_race_duration, std_deviation_absolute, kurtosis_absolute, kurtosis_normalized, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, 35th_percentile_gap, 40th_percentile_gap, 45th_percentile_gap, 50th_percentile_gap, std_group_size |

### Stable Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 15 | total_finishers, included_finishers, abandon_ratio, winning_time, gini_coefficient, shannon_entropy_absolute, shannon_entropy_normalized, 5th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric |
| Stage Races | 16 | total_finishers, included_finishers, abandon_ratio, winning_time, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, 30th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, clumpiness_score |
| One Day Races | 12 | total_finishers, included_finishers, abandon_ratio, winning_time, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, std_group_size, biggest_group_metric, clumpiness_score |
| Stage + One Day Races | 15 | total_finishers, included_finishers, abandon_ratio, winning_time, 10th_percentile_gap, 15th_percentile_gap, 20th_percentile_gap, 25th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, clumpiness_score |
| All Race Types | 13 | total_finishers, included_finishers, abandon_ratio, winning_time, 5th_percentile_gap, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, biggest_group_metric, time_gap_evenness_metric, clumpiness_score |

### Threshold Features
| Race Type | Count | Examples |
|-----------|-------|----------|
| Gc Races | 5 | variance_absolute, variance_normalized, std_deviation_normalized, skewness_absolute, skewness_normalized |
| Stage Races | 4 | variance_normalized, skewness_absolute, skewness_normalized, selection_metric |
| One Day Races | 4 | skewness_absolute, skewness_normalized, kurtosis_absolute, kurtosis_normalized |
| Stage + One Day Races | 3 | variance_normalized, skewness_absolute, skewness_normalized |
| All Race Types | 5 | variance_absolute, variance_normalized, std_deviation_normalized, skewness_absolute, skewness_normalized |