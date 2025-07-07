# Feature Selection Exploration Report

Generated: 2025-07-07 08:39:38

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 15
- **Total races analyzed**: 56,066
- **Average features selected**: 14.3

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| avg_group_size | 18 | 100.0% |
| clumpiness_score | 18 | 100.0% |
| largest_group_size | 17 | 94.4% |
| std_group_size | 16 | 88.9% |
| gini_coefficient | 16 | 88.9% |
| biggest_group_metric | 15 | 83.3% |
| variance_absolute | 15 | 83.3% |
| selection_metric | 14 | 77.8% |
| proportion_in_groups | 12 | 66.7% |
| time_gap_evenness_metric | 12 | 66.7% |
| total_groups | 12 | 66.7% |
| shannon_entropy_absolute | 11 | 61.1% |
| shannon_entropy_normalized | 10 | 55.6% |
| largest_group_position | 10 | 55.6% |
| total_race_duration | 9 | 50.0% |

### Feature Removal Patterns

- **High correlation removals**: 288 (avg 16.0 per scenario)
- **Low variance removals**: 3 (avg 0.2 per scenario)
- **Redundancy removals**: 277 (avg 15.4 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 50th percentile - stage

- **Races analyzed**: 6897
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.876 | 18.523 | 0.076 |
| avg_group_size | 5.821 | 18.255 | 0.194 |
| selection_metric | 5.769 | 18.210 | 0.062 |
| clumpiness_score | 5.765 | 18.117 | 0.011 |
| proportion_in_groups | 5.761 | 18.215 | 0.010 |
| time_gap_evenness_metric | 5.696 | 17.997 | 0.064 |
| std_group_size | 5.676 | 17.847 | 0.018 |
| total_groups | 5.625 | 17.785 | 0.043 |
| total_race_duration | 5.582 | 17.780 | 0.039 |
| variance_absolute | 5.502 | 18.682 | 0.055 |
| variance_normalized | 5.250 | 19.039 | 0.011 |

#### Removed Features by Reason

**Low Score** (8 features):
- abandon_ratio
- gini_coefficient
- kurtosis_normalized
- largest_group_position
- riders_in_groups
- skewness_absolute
- total_finishers
- winning_time

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (16 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- included_finishers
- ... and 6 more

---

### Scenario 2: 50th percentile - gc

- **Races analyzed**: 998
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.864 | 18.924 | 0.020 |
| variance_normalized | 5.824 | 19.236 | 0.007 |
| winning_time | 5.811 | 18.340 | 0.019 |
| clumpiness_score | 5.654 | 17.757 | 0.051 |
| avg_group_size | 5.629 | 17.958 | 0.026 |
| riders_in_groups | 5.594 | 17.606 | 0.132 |
| total_finishers | 5.583 | 17.397 | 0.005 |
| time_gap_evenness_metric | 5.575 | 17.570 | 0.021 |
| shannon_entropy_normalized | 5.566 | 17.599 | 0.007 |
| total_groups | 5.563 | 17.498 | 0.032 |
| std_group_size | 5.539 | 17.582 | 0.036 |
| largest_group_size | 5.528 | 17.579 | 0.041 |
| selection_metric | 5.355 | 16.833 | 0.011 |
| gini_coefficient | 5.296 | 16.497 | 0.005 |
| skewness_absolute | 5.007 | 15.517 | 0.007 |

#### Removed Features by Reason

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Low Score** (5 features):
- abandon_ratio
- biggest_group_metric
- kurtosis_absolute
- largest_group_position
- shannon_entropy_absolute

---

### Scenario 3: 50th percentile - one_day

- **Races analyzed**: 1249
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.709 | 21.265 | 0.050 |
| biggest_group_metric | 6.652 | 21.130 | 0.029 |
| largest_group_position | 6.491 | 20.632 | 0.006 |
| shannon_entropy_absolute | 6.477 | 20.624 | 0.020 |
| selection_metric | 6.448 | 20.483 | 0.028 |
| avg_group_size | 6.438 | 20.525 | 0.020 |
| gini_coefficient | 6.423 | 20.250 | 0.054 |
| total_finishers | 6.391 | 20.130 | 0.007 |
| std_group_size | 6.362 | 20.078 | 0.028 |
| total_race_duration | 6.311 | 20.062 | 0.026 |
| largest_group_size | 6.304 | 20.060 | 0.032 |
| proportion_in_groups | 6.288 | 19.979 | 0.012 |
| variance_absolute | 6.282 | 20.101 | 0.038 |
| 50th_percentile_gap | 6.273 | 19.902 | 0.091 |
| total_groups | 6.206 | 19.766 | 0.027 |

#### Removed Features by Reason

**High Correlation** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- ... and 6 more

**Redundant** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- skewness_normalized
- time_gap_evenness_metric
- winning_time

---

### Scenario 4: 60th percentile - stage

- **Races analyzed**: 6946
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.852 | 18.430 | 0.082 |
| avg_group_size | 5.773 | 18.191 | 0.097 |
| clumpiness_score | 5.769 | 18.114 | 0.015 |
| selection_metric | 5.750 | 18.151 | 0.030 |
| proportion_in_groups | 5.743 | 18.111 | 0.022 |
| largest_group_position | 5.728 | 18.041 | 0.009 |
| gini_coefficient | 5.680 | 17.773 | 0.099 |
| std_group_size | 5.665 | 17.811 | 0.021 |
| largest_group_size | 5.662 | 17.873 | 0.022 |
| time_gap_evenness_metric | 5.648 | 17.849 | 0.017 |
| total_groups | 5.581 | 17.654 | 0.010 |
| variance_absolute | 5.554 | 18.353 | 0.038 |
| total_race_duration | 5.524 | 17.552 | 0.029 |
| variance_normalized | 5.248 | 18.958 | 0.074 |
| skewness_absolute | 5.084 | 15.752 | 0.022 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Redundant** (16 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- included_finishers
- ... and 6 more

---

### Scenario 5: 60th percentile - gc

- **Races analyzed**: 1019
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.774 | 18.479 | 0.025 |
| winning_time | 5.733 | 18.112 | 0.013 |
| avg_group_size | 5.612 | 17.992 | 0.025 |
| clumpiness_score | 5.538 | 17.388 | 0.060 |
| time_gap_evenness_metric | 5.527 | 17.415 | 0.111 |
| riders_in_groups | 5.482 | 17.335 | 0.079 |
| largest_group_size | 5.477 | 17.493 | 0.056 |
| shannon_entropy_normalized | 5.457 | 17.354 | 0.013 |
| std_group_size | 5.457 | 17.382 | 0.049 |
| kurtosis_normalized | 5.332 | 17.117 | 0.005 |
| shannon_entropy_absolute | 5.040 | 15.831 | 0.008 |

#### Removed Features by Reason

**Low Score** (9 features):
- abandon_ratio
- biggest_group_metric
- gini_coefficient
- largest_group_position
- selection_metric
- skewness_normalized
- total_finishers
- total_groups
- variance_normalized

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

---

### Scenario 6: 60th percentile - one_day

- **Races analyzed**: 1341
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.897 | 21.901 | 0.057 |
| clumpiness_score | 6.878 | 21.810 | 0.037 |
| largest_group_position | 6.713 | 21.336 | 0.008 |
| avg_group_size | 6.600 | 21.058 | 0.022 |
| total_finishers | 6.594 | 20.790 | 0.022 |
| gini_coefficient | 6.593 | 20.795 | 0.041 |
| selection_metric | 6.589 | 20.945 | 0.025 |
| shannon_entropy_absolute | 6.562 | 20.893 | 0.005 |
| 50th_percentile_gap | 6.554 | 20.825 | 0.069 |
| std_group_size | 6.537 | 20.683 | 0.048 |
| kurtosis_normalized | 6.531 | 20.811 | 0.006 |
| proportion_in_groups | 6.523 | 20.751 | 0.006 |
| total_race_duration | 6.517 | 20.720 | 0.023 |
| largest_group_size | 6.506 | 20.687 | 0.051 |
| variance_absolute | 6.437 | 20.545 | 0.028 |

#### Removed Features by Reason

**High Correlation** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Redundant** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Low Score** (5 features):
- abandon_ratio
- skewness_normalized
- time_gap_evenness_metric
- total_groups
- winning_time

---

### Scenario 7: 70th percentile - stage

- **Races analyzed**: 6948
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.912 | 18.556 | 0.145 |
| clumpiness_score | 5.822 | 18.264 | 0.030 |
| avg_group_size | 5.796 | 18.311 | 0.043 |
| proportion_in_groups | 5.789 | 18.272 | 0.013 |
| largest_group_position | 5.784 | 18.223 | 0.010 |
| selection_metric | 5.762 | 18.187 | 0.018 |
| gini_coefficient | 5.705 | 17.835 | 0.071 |
| largest_group_size | 5.683 | 17.935 | 0.031 |
| time_gap_evenness_metric | 5.678 | 17.927 | 0.021 |
| std_group_size | 5.672 | 17.840 | 0.019 |
| variance_absolute | 5.613 | 18.235 | 0.041 |
| total_groups | 5.584 | 17.649 | 0.009 |
| total_race_duration | 5.569 | 17.700 | 0.018 |
| variance_normalized | 5.283 | 19.111 | 0.030 |
| skewness_absolute | 5.171 | 16.079 | 0.025 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Redundant** (16 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- included_finishers
- ... and 6 more

---

### Scenario 8: 70th percentile - gc

- **Races analyzed**: 1020
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.661 | 17.962 | 0.018 |
| winning_time | 5.652 | 17.812 | 0.014 |
| variance_normalized | 5.648 | 18.689 | 0.010 |
| avg_group_size | 5.561 | 17.803 | 0.016 |
| largest_group_size | 5.431 | 17.283 | 0.032 |
| clumpiness_score | 5.427 | 17.008 | 0.038 |
| std_group_size | 5.420 | 17.221 | 0.041 |
| time_gap_evenness_metric | 5.412 | 17.043 | 0.030 |
| riders_in_groups | 5.411 | 16.988 | 0.120 |
| shannon_entropy_normalized | 5.401 | 17.092 | 0.022 |
| kurtosis_absolute | 5.396 | 17.357 | 0.006 |
| total_groups | 5.391 | 16.934 | 0.015 |
| selection_metric | 5.143 | 16.107 | 0.006 |
| gini_coefficient | 5.050 | 15.668 | 0.007 |
| shannon_entropy_absolute | 5.041 | 15.787 | 0.007 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- biggest_group_metric
- largest_group_position
- skewness_absolute
- total_finishers

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

---

### Scenario 9: 70th percentile - one_day

- **Races analyzed**: 1399
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.029 | 22.335 | 0.050 |
| clumpiness_score | 7.002 | 22.212 | 0.020 |
| largest_group_position | 6.859 | 21.794 | 0.009 |
| avg_group_size | 6.762 | 21.590 | 0.026 |
| total_finishers | 6.704 | 21.171 | 0.014 |
| abandon_ratio | 6.683 | 21.070 | 0.006 |
| shannon_entropy_absolute | 6.671 | 21.215 | 0.009 |
| gini_coefficient | 6.668 | 21.046 | 0.033 |
| total_race_duration | 6.665 | 21.184 | 0.026 |
| selection_metric | 6.664 | 21.174 | 0.019 |
| kurtosis_normalized | 6.643 | 21.136 | 0.008 |
| proportion_in_groups | 6.638 | 21.118 | 0.009 |
| 50th_percentile_gap | 6.629 | 21.039 | 0.083 |
| largest_group_size | 6.618 | 21.020 | 0.071 |
| std_group_size | 6.606 | 20.930 | 0.054 |

#### Removed Features by Reason

**High Correlation** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Redundant** (14 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 4 more

**Low Score** (5 features):
- skewness_normalized
- time_gap_evenness_metric
- total_groups
- variance_absolute
- winning_time

---

### Scenario 10: 80th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.994 | 18.826 | 0.156 |
| selection_metric | 5.882 | 18.583 | 0.016 |
| proportion_in_groups | 5.878 | 18.569 | 0.008 |
| largest_group_position | 5.867 | 18.494 | 0.010 |
| clumpiness_score | 5.855 | 18.383 | 0.014 |
| avg_group_size | 5.843 | 18.475 | 0.036 |
| shannon_entropy_absolute | 5.825 | 18.438 | 0.021 |
| gini_coefficient | 5.758 | 17.986 | 0.068 |
| time_gap_evenness_metric | 5.745 | 18.149 | 0.020 |
| largest_group_size | 5.742 | 18.147 | 0.016 |
| std_group_size | 5.733 | 18.057 | 0.019 |
| kurtosis_normalized | 5.718 | 18.162 | 0.005 |
| variance_absolute | 5.664 | 18.221 | 0.023 |
| total_groups | 5.653 | 17.866 | 0.008 |
| total_race_duration | 5.624 | 17.878 | 0.009 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- riders_in_groups
- skewness_normalized
- total_finishers
- variance_normalized
- winning_time

**High Correlation** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Redundant** (14 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 4 more

---

### Scenario 11: 80th percentile - gc

- **Races analyzed**: 1021
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.623 | 17.742 | 0.022 |
| variance_absolute | 5.561 | 17.563 | 0.022 |
| avg_group_size | 5.554 | 17.777 | 0.054 |
| std_group_size | 5.410 | 17.200 | 0.032 |
| largest_group_size | 5.409 | 17.225 | 0.055 |
| clumpiness_score | 5.394 | 16.937 | 0.042 |
| shannon_entropy_normalized | 5.393 | 17.096 | 0.023 |
| time_gap_evenness_metric | 5.373 | 16.899 | 0.072 |
| riders_in_groups | 5.363 | 16.869 | 0.103 |
| total_groups | 5.358 | 16.841 | 0.008 |
| biggest_group_metric | 5.357 | 16.848 | 0.005 |
| shannon_entropy_absolute | 5.089 | 15.989 | 0.011 |
| gini_coefficient | 5.004 | 15.523 | 0.006 |
| skewness_absolute | 4.997 | 15.683 | 0.006 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- largest_group_position
- selection_metric
- total_finishers
- variance_normalized

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

---

### Scenario 12: 80th percentile - one_day

- **Races analyzed**: 1431
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.168 | 22.841 | 0.021 |
| clumpiness_score | 7.081 | 22.449 | 0.043 |
| largest_group_position | 7.034 | 22.369 | 0.007 |
| avg_group_size | 6.863 | 21.927 | 0.065 |
| total_finishers | 6.852 | 21.662 | 0.005 |
| 50th_percentile_gap | 6.815 | 21.658 | 0.080 |
| shannon_entropy_normalized | 6.813 | 21.716 | 0.027 |
| total_race_duration | 6.789 | 21.595 | 0.031 |
| gini_coefficient | 6.754 | 21.352 | 0.011 |
| proportion_in_groups | 6.749 | 21.496 | 0.007 |
| largest_group_size | 6.735 | 21.465 | 0.033 |
| selection_metric | 6.715 | 21.344 | 0.015 |
| kurtosis_normalized | 6.685 | 21.445 | 0.007 |
| shannon_entropy_absolute | 6.677 | 21.215 | 0.023 |
| std_group_size | 6.665 | 21.180 | 0.027 |

#### Removed Features by Reason

**High Correlation** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Redundant** (12 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- skewness_absolute
- ... and 2 more

**Low Score** (6 features):
- abandon_ratio
- skewness_normalized
- time_gap_evenness_metric
- total_groups
- variance_absolute
- winning_time

---

### Scenario 13: 90th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.011 | 18.867 | 0.190 |
| selection_metric | 5.893 | 18.622 | 0.007 |
| proportion_in_groups | 5.889 | 18.645 | 0.008 |
| largest_group_position | 5.881 | 18.532 | 0.016 |
| clumpiness_score | 5.835 | 18.312 | 0.007 |
| avg_group_size | 5.794 | 18.308 | 0.050 |
| time_gap_evenness_metric | 5.747 | 18.176 | 0.024 |
| std_group_size | 5.734 | 18.097 | 0.027 |
| largest_group_size | 5.733 | 18.135 | 0.020 |
| shannon_entropy_absolute | 5.714 | 18.081 | 0.009 |
| gini_coefficient | 5.679 | 17.804 | 0.035 |
| kurtosis_normalized | 5.679 | 18.017 | 0.026 |
| variance_absolute | 5.651 | 18.142 | 0.008 |
| total_race_duration | 5.571 | 17.743 | 0.006 |
| 5th_percentile_gap | 5.459 | 17.417 | 0.011 |

#### Removed Features by Reason

**Low Score** (7 features):
- abandon_ratio
- riders_in_groups
- skewness_absolute
- total_finishers
- total_groups
- variance_normalized
- winning_time

**High Correlation** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- included_finishers
- ... and 5 more

**Redundant** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- included_finishers
- ... and 5 more

---

### Scenario 14: 90th percentile - gc

- **Races analyzed**: 1021
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.595 | 17.665 | 0.021 |
| avg_group_size | 5.570 | 17.839 | 0.035 |
| variance_absolute | 5.519 | 17.408 | 0.026 |
| std_group_size | 5.382 | 17.112 | 0.051 |
| shannon_entropy_normalized | 5.372 | 17.033 | 0.013 |
| largest_group_size | 5.368 | 17.086 | 0.061 |
| clumpiness_score | 5.363 | 16.857 | 0.036 |
| biggest_group_metric | 5.331 | 16.770 | 0.008 |
| time_gap_evenness_metric | 5.331 | 16.774 | 0.064 |
| total_groups | 5.326 | 16.760 | 0.005 |
| riders_in_groups | 5.302 | 16.701 | 0.081 |
| skewness_absolute | 5.161 | 16.308 | 0.006 |
| gini_coefficient | 4.989 | 15.511 | 0.007 |

#### Removed Features by Reason

**Low Score** (7 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
- selection_metric
- shannon_entropy_absolute
- total_finishers
- variance_normalized

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

---

### Scenario 15: 90th percentile - one_day

- **Races analyzed**: 1445
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.272 | 23.184 | 0.029 |
| largest_group_position | 7.133 | 22.695 | 0.006 |
| clumpiness_score | 7.126 | 22.615 | 0.032 |
| avg_group_size | 6.944 | 22.237 | 0.059 |
| 50th_percentile_gap | 6.933 | 22.039 | 0.086 |
| proportion_in_groups | 6.852 | 21.816 | 0.008 |
| largest_group_size | 6.836 | 21.783 | 0.044 |
| gini_coefficient | 6.810 | 21.563 | 0.014 |
| shannon_entropy_normalized | 6.783 | 21.628 | 0.021 |
| std_group_size | 6.771 | 21.528 | 0.037 |
| kurtosis_normalized | 6.736 | 21.618 | 0.006 |
| selection_metric | 6.720 | 21.345 | 0.009 |
| variance_absolute | 6.683 | 21.311 | 0.034 |
| total_groups | 6.682 | 21.275 | 0.012 |
| shannon_entropy_absolute | 6.618 | 21.005 | 0.010 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- skewness_normalized
- total_finishers
- winning_time

**High Correlation** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Redundant** (14 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- skewness_absolute
- ... and 4 more

---

### Scenario 16: 100th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.409 | 16.922 | 0.118 |
| proportion_in_groups | 5.339 | 16.744 | 0.096 |
| winning_time | 5.261 | 16.588 | 0.043 |
| shannon_entropy_normalized | 5.225 | 16.391 | 0.086 |
| clumpiness_score | 5.220 | 16.262 | 0.010 |
| gini_coefficient | 5.192 | 16.240 | 0.046 |
| riders_in_groups | 5.177 | 16.132 | 0.083 |
| largest_group_size | 5.174 | 16.230 | 0.074 |
| selection_metric | 5.156 | 16.122 | 0.006 |
| shannon_entropy_absolute | 5.134 | 16.099 | 0.030 |
| time_gap_evenness_metric | 5.133 | 16.153 | 0.022 |
| variance_absolute | 5.119 | 16.311 | 0.011 |
| avg_group_size | 5.067 | 15.956 | 0.034 |
| total_groups | 5.042 | 15.809 | 0.005 |
| skewness_normalized | 5.027 | 15.739 | 0.039 |

#### Removed Features by Reason

**High Correlation** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- kurtosis_absolute
- ... and 6 more

**Redundant** (15 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- ... and 5 more

**Low Variance** (1 features):
- abandon_ratio

**Low Score** (3 features):
- 5th_percentile_gap
- largest_group_position
- variance_normalized

---

### Scenario 17: 100th percentile - gc

- **Races analyzed**: 1021
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.329 | 16.777 | 0.019 |
| avg_group_size | 5.324 | 17.029 | 0.026 |
| kurtosis_normalized | 5.263 | 16.842 | 0.014 |
| variance_absolute | 5.263 | 16.572 | 0.007 |
| largest_group_size | 5.146 | 16.387 | 0.035 |
| std_group_size | 5.109 | 16.251 | 0.023 |
| clumpiness_score | 5.097 | 15.975 | 0.023 |
| shannon_entropy_normalized | 5.083 | 16.037 | 0.037 |
| time_gap_evenness_metric | 5.074 | 15.912 | 0.051 |
| biggest_group_metric | 5.066 | 15.899 | 0.011 |
| riders_in_groups | 5.029 | 15.785 | 0.077 |
| skewness_normalized | 4.846 | 15.272 | 0.017 |
| gini_coefficient | 4.803 | 14.939 | 0.006 |

#### Removed Features by Reason

**High Correlation** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Redundant** (17 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 7 more

**Low Variance** (1 features):
- abandon_ratio

**Low Score** (5 features):
- largest_group_position
- selection_metric
- shannon_entropy_absolute
- total_groups
- variance_normalized

---

### Scenario 18: 100th percentile - one_day

- **Races analyzed**: 1457
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.059 | 22.456 | 0.017 |
| largest_group_position | 6.908 | 21.919 | 0.011 |
| clumpiness_score | 6.840 | 21.648 | 0.006 |
| 10th_percentile_gap | 6.755 | 21.560 | 0.009 |
| riders_in_groups | 6.732 | 21.238 | 0.050 |
| 50th_percentile_gap | 6.708 | 21.324 | 0.050 |
| avg_group_size | 6.638 | 21.265 | 0.010 |
| gini_coefficient | 6.630 | 20.966 | 0.032 |
| largest_group_size | 6.615 | 21.017 | 0.032 |
| proportion_in_groups | 6.608 | 21.003 | 0.008 |
| shannon_entropy_normalized | 6.558 | 20.843 | 0.008 |
| kurtosis_normalized | 6.549 | 20.844 | 0.021 |
| total_groups | 6.526 | 20.706 | 0.009 |
| selection_metric | 6.500 | 20.536 | 0.010 |
| winning_time | 6.456 | 20.439 | 0.005 |

#### Removed Features by Reason

**High Correlation** (14 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- skewness_absolute
- ... and 4 more

**Redundant** (15 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- skewness_absolute
- ... and 5 more

**Low Variance** (1 features):
- abandon_ratio

**Low Score** (3 features):
- shannon_entropy_absolute
- skewness_normalized
- variance_absolute

---

