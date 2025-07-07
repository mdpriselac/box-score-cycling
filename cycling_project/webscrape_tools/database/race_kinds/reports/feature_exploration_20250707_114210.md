# Feature Selection Exploration Report

Generated: 2025-07-07 11:42:56

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 20
- **Total races analyzed**: 83,506
- **Average features selected**: 16.4

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| clumpiness_score | 18 | 100.0% |
| avg_group_size | 18 | 100.0% |
| gini_coefficient | 18 | 100.0% |
| std_group_size | 18 | 100.0% |
| total_groups | 18 | 100.0% |
| total_race_duration | 18 | 100.0% |
| 50th_percentile_gap | 18 | 100.0% |
| variance_absolute | 18 | 100.0% |
| biggest_group_metric | 17 | 94.4% |
| selection_metric | 17 | 94.4% |
| time_gap_evenness_metric | 16 | 88.9% |
| largest_group_position | 13 | 72.2% |
| proportion_in_groups | 13 | 72.2% |
| largest_group_size | 13 | 72.2% |
| std_deviation_normalized | 12 | 66.7% |

### Feature Removal Patterns

- **High correlation removals**: 267 (avg 14.8 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 240 (avg 13.3 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage

- **Races analyzed**: 5098
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.053 | 19.063 | 0.145 |
| clumpiness_score | 5.997 | 18.979 | 0.011 |
| avg_group_size | 5.919 | 18.762 | 0.019 |
| selection_metric | 5.897 | 18.759 | 0.054 |
| gini_coefficient | 5.831 | 18.483 | 0.036 |
| std_group_size | 5.826 | 18.372 | 0.009 |
| total_groups | 5.785 | 18.416 | 0.018 |
| std_deviation_normalized | 5.777 | 18.370 | 0.028 |
| kurtosis_absolute | 5.773 | 18.287 | 0.010 |
| total_race_duration | 5.670 | 18.041 | 0.044 |
| 50th_percentile_gap | 5.595 | 17.808 | 0.027 |
| variance_absolute | 5.557 | 17.720 | 0.063 |
| skewness_absolute | 5.297 | 16.555 | 0.030 |

#### Removed Features by Reason

**Low Score** (7 features):
- 5th_percentile_gap
- abandon_ratio
- largest_group_position
- proportion_in_groups
- riders_in_groups
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
- included_finishers
- kurtosis_normalized
- ... and 7 more

**Redundant** (14 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_absolute
- ... and 4 more

---

### Scenario 2: 30th percentile - one_day

- **Races analyzed**: 675
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.278 | 19.858 | 0.043 |
| variance_absolute | 6.164 | 20.107 | 0.031 |
| gini_coefficient | 6.130 | 19.339 | 0.043 |
| avg_group_size | 6.081 | 19.261 | 0.070 |
| std_group_size | 6.071 | 19.088 | 0.056 |
| largest_group_position | 6.044 | 19.207 | 0.011 |
| proportion_in_groups | 5.956 | 18.917 | 0.008 |
| time_gap_evenness_metric | 5.924 | 18.837 | 0.013 |
| total_groups | 5.912 | 18.779 | 0.056 |
| largest_group_size | 5.855 | 18.576 | 0.025 |
| 50th_percentile_gap | 5.846 | 18.610 | 0.058 |
| total_race_duration | 5.795 | 18.404 | 0.054 |
| std_deviation_absolute | 5.741 | 18.359 | 0.035 |
| riders_in_groups | 5.629 | 17.762 | 0.005 |
| skewness_normalized | 5.594 | 17.505 | 0.010 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- kurtosis_normalized
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
- 5th_percentile_gap
- biggest_group_metric
- ... and 6 more

**Redundant** (16 features):
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
- ... and 6 more

---

### Scenario 3: 30th percentile - stage_one_day

- **Races analyzed**: 5773
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.090 | 19.169 | 0.148 |
| clumpiness_score | 6.050 | 19.133 | 0.012 |
| avg_group_size | 5.959 | 18.873 | 0.028 |
| selection_metric | 5.946 | 18.878 | 0.081 |
| gini_coefficient | 5.890 | 18.644 | 0.033 |
| std_group_size | 5.863 | 18.480 | 0.007 |
| kurtosis_normalized | 5.835 | 18.484 | 0.005 |
| total_groups | 5.816 | 18.506 | 0.020 |
| std_deviation_normalized | 5.813 | 18.483 | 0.022 |
| total_race_duration | 5.704 | 18.146 | 0.050 |
| 50th_percentile_gap | 5.638 | 17.959 | 0.027 |
| variance_absolute | 5.589 | 17.847 | 0.050 |
| 5th_percentile_gap | 5.487 | 17.507 | 0.005 |
| skewness_normalized | 5.351 | 16.716 | 0.034 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- largest_group_position
- proportion_in_groups
- riders_in_groups
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
- included_finishers
- kurtosis_absolute
- ... and 7 more

**Redundant** (14 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 4 more

---

### Scenario 4: 40th percentile - stage

- **Races analyzed**: 5794
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.058 | 19.139 | 0.058 |
| biggest_group_metric | 6.036 | 19.159 | 0.018 |
| selection_metric | 5.927 | 18.887 | 0.042 |
| avg_group_size | 5.914 | 18.754 | 0.045 |
| gini_coefficient | 5.890 | 18.612 | 0.086 |
| std_group_size | 5.872 | 18.478 | 0.016 |
| time_gap_evenness_metric | 5.846 | 18.607 | 0.018 |
| proportion_in_groups | 5.831 | 18.500 | 0.013 |
| total_groups | 5.807 | 18.511 | 0.028 |
| std_deviation_normalized | 5.783 | 18.405 | 0.030 |
| total_race_duration | 5.738 | 18.278 | 0.033 |
| 50th_percentile_gap | 5.620 | 17.905 | 0.025 |
| variance_absolute | 5.436 | 17.342 | 0.058 |
| skewness_absolute | 5.306 | 16.570 | 0.012 |

#### Removed Features by Reason

**Low Score** (7 features):
- 5th_percentile_gap
- abandon_ratio
- kurtosis_normalized
- largest_group_position
- riders_in_groups
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

**Redundant** (13 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 3 more

---

### Scenario 5: 40th percentile - one_day

- **Races analyzed**: 1060
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.476 | 20.519 | 0.055 |
| biggest_group_metric | 6.434 | 20.404 | 0.025 |
| selection_metric | 6.369 | 20.246 | 0.044 |
| gini_coefficient | 6.274 | 19.797 | 0.054 |
| avg_group_size | 6.261 | 19.928 | 0.031 |
| std_group_size | 6.151 | 19.354 | 0.047 |
| variance_absolute | 6.088 | 19.648 | 0.031 |
| largest_group_size | 6.080 | 19.327 | 0.023 |
| proportion_in_groups | 6.075 | 19.293 | 0.011 |
| total_race_duration | 6.049 | 19.217 | 0.043 |
| total_groups | 6.049 | 19.254 | 0.036 |
| time_gap_evenness_metric | 6.008 | 19.088 | 0.012 |
| 50th_percentile_gap | 5.979 | 18.967 | 0.092 |
| skewness_normalized | 5.715 | 17.913 | 0.010 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
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
- 5th_percentile_gap
- included_finishers
- ... and 5 more

**Redundant** (16 features):
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
- ... and 6 more

---

### Scenario 6: 40th percentile - stage_one_day

- **Races analyzed**: 6854
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.130 | 19.329 | 0.141 |
| clumpiness_score | 6.111 | 19.351 | 0.015 |
| shannon_entropy_absolute | 6.062 | 19.270 | 0.059 |
| selection_metric | 5.988 | 19.052 | 0.058 |
| avg_group_size | 5.965 | 18.926 | 0.032 |
| gini_coefficient | 5.933 | 18.786 | 0.022 |
| std_group_size | 5.906 | 18.594 | 0.008 |
| time_gap_evenness_metric | 5.880 | 18.698 | 0.013 |
| kurtosis_normalized | 5.847 | 18.535 | 0.009 |
| std_deviation_normalized | 5.842 | 18.571 | 0.034 |
| total_groups | 5.827 | 18.565 | 0.023 |
| total_race_duration | 5.792 | 18.421 | 0.040 |
| 50th_percentile_gap | 5.680 | 18.076 | 0.028 |
| variance_absolute | 5.512 | 17.582 | 0.059 |
| skewness_normalized | 5.360 | 16.739 | 0.026 |

#### Removed Features by Reason

**Low Score** (7 features):
- 5th_percentile_gap
- abandon_ratio
- largest_group_position
- proportion_in_groups
- riders_in_groups
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

**Redundant** (13 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- largest_group_size
- ... and 3 more

---

### Scenario 7: 50th percentile - stage

- **Races analyzed**: 5903
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.058 | 19.134 | 0.055 |
| biggest_group_metric | 6.026 | 19.140 | 0.028 |
| selection_metric | 5.928 | 18.884 | 0.027 |
| avg_group_size | 5.909 | 18.778 | 0.016 |
| largest_group_position | 5.903 | 18.754 | 0.007 |
| gini_coefficient | 5.892 | 18.569 | 0.079 |
| std_group_size | 5.845 | 18.376 | 0.020 |
| largest_group_size | 5.821 | 18.467 | 0.009 |
| time_gap_evenness_metric | 5.788 | 18.400 | 0.028 |
| proportion_in_groups | 5.788 | 18.359 | 0.013 |
| total_groups | 5.782 | 18.429 | 0.026 |
| std_deviation_normalized | 5.780 | 18.378 | 0.040 |
| total_race_duration | 5.752 | 18.306 | 0.034 |
| 50th_percentile_gap | 5.677 | 18.081 | 0.023 |
| variance_absolute | 5.453 | 17.358 | 0.051 |
| skewness_absolute | 5.288 | 16.458 | 0.020 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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

**Redundant** (13 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 3 more

---

### Scenario 8: 50th percentile - one_day

- **Races analyzed**: 1249
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.731 | 21.337 | 0.050 |
| biggest_group_metric | 6.674 | 21.202 | 0.029 |
| largest_group_position | 6.504 | 20.675 | 0.006 |
| shannon_entropy_absolute | 6.498 | 20.695 | 0.020 |
| selection_metric | 6.461 | 20.528 | 0.028 |
| avg_group_size | 6.450 | 20.565 | 0.020 |
| gini_coefficient | 6.444 | 20.319 | 0.054 |
| total_finishers | 6.410 | 20.193 | 0.007 |
| std_group_size | 6.382 | 20.147 | 0.028 |
| total_race_duration | 6.335 | 20.140 | 0.026 |
| largest_group_size | 6.323 | 20.122 | 0.032 |
| proportion_in_groups | 6.310 | 20.051 | 0.012 |
| 50th_percentile_gap | 6.298 | 19.985 | 0.091 |
| variance_absolute | 6.288 | 20.120 | 0.038 |
| total_groups | 6.209 | 19.778 | 0.027 |
| time_gap_evenness_metric | 6.141 | 19.507 | 0.013 |
| skewness_normalized | 5.792 | 18.141 | 0.014 |

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

**Low Score** (3 features):
- abandon_ratio
- kurtosis_normalized
- winning_time

---

### Scenario 9: 50th percentile - stage_one_day

- **Races analyzed**: 7152
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.184 | 19.518 | 0.055 |
| biggest_group_metric | 6.135 | 19.474 | 0.031 |
| shannon_entropy_absolute | 6.096 | 19.396 | 0.036 |
| avg_group_size | 6.023 | 19.126 | 0.023 |
| selection_metric | 6.015 | 19.152 | 0.027 |
| largest_group_position | 5.998 | 19.057 | 0.006 |
| gini_coefficient | 5.991 | 18.865 | 0.076 |
| std_group_size | 5.925 | 18.627 | 0.022 |
| total_groups | 5.885 | 18.754 | 0.028 |
| std_deviation_normalized | 5.881 | 18.703 | 0.035 |
| proportion_in_groups | 5.877 | 18.645 | 0.010 |
| time_gap_evenness_metric | 5.861 | 18.634 | 0.016 |
| total_race_duration | 5.845 | 18.599 | 0.036 |
| 50th_percentile_gap | 5.769 | 18.377 | 0.032 |
| 5th_percentile_gap | 5.655 | 18.037 | 0.007 |
| variance_absolute | 5.546 | 17.670 | 0.054 |
| skewness_normalized | 5.388 | 16.793 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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

**Redundant** (13 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- largest_group_size
- ... and 3 more

---

### Scenario 10: 60th percentile - stage

- **Races analyzed**: 5933
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.067 | 19.171 | 0.038 |
| biggest_group_metric | 6.053 | 19.219 | 0.042 |
| shannon_entropy_absolute | 5.992 | 19.071 | 0.029 |
| selection_metric | 5.953 | 18.957 | 0.020 |
| largest_group_position | 5.941 | 18.858 | 0.008 |
| avg_group_size | 5.940 | 18.878 | 0.026 |
| gini_coefficient | 5.914 | 18.603 | 0.068 |
| std_group_size | 5.872 | 18.469 | 0.020 |
| largest_group_size | 5.834 | 18.504 | 0.020 |
| std_deviation_normalized | 5.797 | 18.423 | 0.040 |
| proportion_in_groups | 5.788 | 18.362 | 0.008 |
| total_race_duration | 5.785 | 18.391 | 0.032 |
| total_groups | 5.778 | 18.418 | 0.018 |
| time_gap_evenness_metric | 5.773 | 18.348 | 0.020 |
| 50th_percentile_gap | 5.728 | 18.214 | 0.048 |
| variance_absolute | 5.509 | 17.486 | 0.055 |
| skewness_absolute | 5.340 | 16.612 | 0.018 |

#### Removed Features by Reason

**Low Score** (6 features):
- 5th_percentile_gap
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (13 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 3 more

**Redundant** (12 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 11: 60th percentile - one_day

- **Races analyzed**: 1341
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.893 | 21.888 | 0.057 |
| clumpiness_score | 6.874 | 21.798 | 0.037 |
| largest_group_position | 6.707 | 21.317 | 0.008 |
| avg_group_size | 6.598 | 21.050 | 0.022 |
| total_finishers | 6.591 | 20.779 | 0.022 |
| gini_coefficient | 6.589 | 20.783 | 0.041 |
| selection_metric | 6.586 | 20.933 | 0.025 |
| shannon_entropy_absolute | 6.558 | 20.879 | 0.005 |
| 50th_percentile_gap | 6.550 | 20.812 | 0.069 |
| std_group_size | 6.532 | 20.667 | 0.048 |
| kurtosis_normalized | 6.527 | 20.799 | 0.006 |
| proportion_in_groups | 6.520 | 20.739 | 0.006 |
| total_race_duration | 6.513 | 20.708 | 0.023 |
| largest_group_size | 6.506 | 20.687 | 0.051 |
| total_groups | 6.406 | 20.416 | 0.013 |
| variance_absolute | 6.372 | 20.330 | 0.028 |
| time_gap_evenness_metric | 6.285 | 19.950 | 0.015 |
| skewness_normalized | 6.004 | 18.836 | 0.016 |

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

**Low Score** (2 features):
- abandon_ratio
- winning_time

---

### Scenario 12: 60th percentile - stage_one_day

- **Races analyzed**: 7274
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.191 | 19.552 | 0.042 |
| biggest_group_metric | 6.163 | 19.559 | 0.040 |
| shannon_entropy_absolute | 6.085 | 19.356 | 0.030 |
| avg_group_size | 6.053 | 19.240 | 0.018 |
| selection_metric | 6.039 | 19.213 | 0.022 |
| largest_group_position | 6.034 | 19.147 | 0.009 |
| gini_coefficient | 6.005 | 18.882 | 0.062 |
| std_group_size | 5.953 | 18.732 | 0.017 |
| largest_group_size | 5.933 | 18.823 | 0.011 |
| std_deviation_normalized | 5.904 | 18.748 | 0.050 |
| proportion_in_groups | 5.875 | 18.638 | 0.006 |
| total_race_duration | 5.874 | 18.672 | 0.034 |
| total_groups | 5.852 | 18.644 | 0.019 |
| time_gap_evenness_metric | 5.850 | 18.576 | 0.023 |
| 50th_percentile_gap | 5.820 | 18.521 | 0.042 |
| 5th_percentile_gap | 5.695 | 18.157 | 0.009 |
| variance_absolute | 5.592 | 17.773 | 0.044 |
| skewness_absolute | 5.365 | 16.697 | 0.017 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (13 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 3 more

**Redundant** (12 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 13: 70th percentile - stage

- **Races analyzed**: 5934
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.070 | 19.254 | 0.056 |
| clumpiness_score | 6.065 | 19.165 | 0.029 |
| largest_group_position | 5.963 | 18.923 | 0.009 |
| shannon_entropy_absolute | 5.960 | 18.954 | 0.025 |
| avg_group_size | 5.950 | 18.906 | 0.024 |
| selection_metric | 5.937 | 18.886 | 0.023 |
| gini_coefficient | 5.912 | 18.559 | 0.056 |
| std_group_size | 5.844 | 18.377 | 0.024 |
| largest_group_size | 5.827 | 18.478 | 0.021 |
| std_deviation_normalized | 5.805 | 18.434 | 0.036 |
| total_race_duration | 5.797 | 18.413 | 0.027 |
| total_groups | 5.757 | 18.328 | 0.018 |
| 50th_percentile_gap | 5.755 | 18.296 | 0.042 |
| time_gap_evenness_metric | 5.751 | 18.246 | 0.016 |
| variance_absolute | 5.565 | 17.637 | 0.052 |
| skewness_absolute | 5.305 | 16.545 | 0.018 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (12 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 14: 70th percentile - one_day

- **Races analyzed**: 1399
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.030 | 22.337 | 0.050 |
| clumpiness_score | 7.002 | 22.213 | 0.020 |
| largest_group_position | 6.861 | 21.798 | 0.009 |
| avg_group_size | 6.762 | 21.590 | 0.026 |
| total_finishers | 6.702 | 21.165 | 0.014 |
| abandon_ratio | 6.683 | 21.069 | 0.006 |
| shannon_entropy_absolute | 6.671 | 21.213 | 0.009 |
| gini_coefficient | 6.668 | 21.046 | 0.033 |
| total_race_duration | 6.666 | 21.185 | 0.026 |
| selection_metric | 6.664 | 21.174 | 0.019 |
| kurtosis_normalized | 6.647 | 21.148 | 0.008 |
| proportion_in_groups | 6.638 | 21.117 | 0.009 |
| 50th_percentile_gap | 6.629 | 21.039 | 0.083 |
| largest_group_size | 6.608 | 20.984 | 0.071 |
| std_group_size | 6.605 | 20.927 | 0.054 |
| total_groups | 6.501 | 20.713 | 0.008 |
| time_gap_evenness_metric | 6.380 | 20.241 | 0.015 |
| variance_absolute | 6.359 | 20.262 | 0.024 |
| skewness_normalized | 6.204 | 19.488 | 0.018 |

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

**Low Score** (1 features):
- winning_time

---

### Scenario 15: 70th percentile - stage_one_day

- **Races analyzed**: 7333
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.264 | 19.800 | 0.031 |
| biggest_group_metric | 6.250 | 19.846 | 0.047 |
| avg_group_size | 6.136 | 19.518 | 0.021 |
| largest_group_position | 6.131 | 19.474 | 0.009 |
| shannon_entropy_absolute | 6.122 | 19.482 | 0.022 |
| selection_metric | 6.083 | 19.344 | 0.027 |
| gini_coefficient | 6.074 | 19.057 | 0.075 |
| largest_group_size | 6.000 | 19.053 | 0.015 |
| std_group_size | 5.992 | 18.870 | 0.025 |
| std_deviation_normalized | 5.978 | 18.996 | 0.032 |
| total_race_duration | 5.959 | 18.944 | 0.025 |
| proportion_in_groups | 5.922 | 18.791 | 0.005 |
| 50th_percentile_gap | 5.913 | 18.819 | 0.036 |
| total_groups | 5.895 | 18.783 | 0.017 |
| time_gap_evenness_metric | 5.895 | 18.721 | 0.017 |
| variance_absolute | 5.742 | 18.228 | 0.047 |
| skewness_absolute | 5.467 | 17.067 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (12 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 16: 80th percentile - stage

- **Races analyzed**: 5936
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.226 | 19.750 | 0.069 |
| clumpiness_score | 6.184 | 19.533 | 0.020 |
| selection_metric | 6.129 | 19.508 | 0.018 |
| largest_group_position | 6.108 | 19.395 | 0.009 |
| avg_group_size | 6.081 | 19.325 | 0.017 |
| shannon_entropy_absolute | 6.049 | 19.231 | 0.021 |
| gini_coefficient | 6.034 | 18.916 | 0.073 |
| std_group_size | 5.957 | 18.784 | 0.019 |
| kurtosis_normalized | 5.956 | 18.959 | 0.006 |
| largest_group_size | 5.954 | 18.895 | 0.014 |
| std_deviation_normalized | 5.934 | 18.837 | 0.037 |
| total_race_duration | 5.930 | 18.830 | 0.019 |
| 50th_percentile_gap | 5.926 | 18.845 | 0.039 |
| time_gap_evenness_metric | 5.873 | 18.623 | 0.011 |
| total_groups | 5.865 | 18.666 | 0.010 |
| variance_absolute | 5.781 | 18.318 | 0.047 |
| skewness_normalized | 5.351 | 16.763 | 0.027 |

#### Removed Features by Reason

**Low Score** (6 features):
- 5th_percentile_gap
- abandon_ratio
- proportion_in_groups
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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

**Redundant** (12 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 17: 80th percentile - one_day

- **Races analyzed**: 1431
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.187 | 22.903 | 0.021 |
| clumpiness_score | 7.090 | 22.480 | 0.043 |
| largest_group_position | 7.051 | 22.426 | 0.007 |
| total_finishers | 6.869 | 21.720 | 0.005 |
| avg_group_size | 6.868 | 21.944 | 0.065 |
| 50th_percentile_gap | 6.833 | 21.717 | 0.080 |
| shannon_entropy_normalized | 6.831 | 21.775 | 0.027 |
| total_race_duration | 6.807 | 21.654 | 0.031 |
| gini_coefficient | 6.771 | 21.410 | 0.011 |
| largest_group_size | 6.752 | 21.523 | 0.033 |
| proportion_in_groups | 6.748 | 21.495 | 0.007 |
| selection_metric | 6.732 | 21.401 | 0.015 |
| kurtosis_normalized | 6.702 | 21.503 | 0.007 |
| shannon_entropy_absolute | 6.694 | 21.273 | 0.023 |
| std_group_size | 6.683 | 21.239 | 0.027 |
| total_groups | 6.621 | 21.093 | 0.015 |
| variance_absolute | 6.568 | 20.932 | 0.036 |
| time_gap_evenness_metric | 6.516 | 20.692 | 0.020 |
| skewness_normalized | 6.140 | 19.303 | 0.007 |

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

**Low Score** (2 features):
- abandon_ratio
- winning_time

---

### Scenario 18: 80th percentile - stage_one_day

- **Races analyzed**: 7367
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.440 | 20.439 | 0.069 |
| clumpiness_score | 6.406 | 20.255 | 0.007 |
| selection_metric | 6.319 | 20.060 | 0.065 |
| largest_group_position | 6.313 | 20.051 | 0.017 |
| avg_group_size | 6.284 | 19.972 | 0.028 |
| shannon_entropy_absolute | 6.254 | 19.837 | 0.073 |
| gini_coefficient | 6.193 | 19.493 | 0.008 |
| largest_group_size | 6.165 | 19.582 | 0.010 |
| kurtosis_normalized | 6.148 | 19.595 | 0.006 |
| std_group_size | 6.144 | 19.398 | 0.018 |
| std_deviation_normalized | 6.131 | 19.479 | 0.029 |
| total_race_duration | 6.116 | 19.444 | 0.016 |
| 50th_percentile_gap | 6.116 | 19.470 | 0.040 |
| proportion_in_groups | 6.063 | 19.237 | 0.005 |
| total_groups | 6.044 | 19.238 | 0.018 |
| time_gap_evenness_metric | 6.043 | 19.172 | 0.016 |
| variance_absolute | 5.954 | 18.923 | 0.016 |
| 5th_percentile_gap | 5.844 | 18.655 | 0.007 |
| skewness_normalized | 5.548 | 17.420 | 0.007 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
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

**Redundant** (12 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 2 more

---

