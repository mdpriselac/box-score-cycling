# Feature Selection Exploration Report

Generated: 2025-07-07 11:50:03

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 20
- **Total races analyzed**: 25,910
- **Average features selected**: 16.2

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| clumpiness_score | 18 | 100.0% |
| avg_group_size | 18 | 100.0% |
| selection_metric | 18 | 100.0% |
| std_group_size | 18 | 100.0% |
| gini_coefficient | 18 | 100.0% |
| variance_absolute | 18 | 100.0% |
| 50th_percentile_gap | 18 | 100.0% |
| biggest_group_metric | 17 | 94.4% |
| largest_group_size | 14 | 77.8% |
| total_groups | 14 | 77.8% |
| proportion_in_groups | 13 | 72.2% |
| std_deviation_normalized | 12 | 66.7% |
| largest_group_position | 12 | 66.7% |
| time_gap_evenness_metric | 11 | 61.1% |
| skewness_absolute | 10 | 55.6% |

### Feature Removal Patterns

- **High correlation removals**: 274 (avg 15.2 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 258 (avg 14.3 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage - ['wt']

- **Races analyzed**: 1925
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.848 | 18.406 | 0.057 |
| biggest_group_metric | 5.843 | 18.504 | 0.015 |
| avg_group_size | 5.802 | 18.367 | 0.058 |
| selection_metric | 5.715 | 18.155 | 0.048 |
| std_group_size | 5.698 | 17.907 | 0.023 |
| proportion_in_groups | 5.676 | 17.974 | 0.021 |
| gini_coefficient | 5.639 | 17.788 | 0.074 |
| std_deviation_normalized | 5.632 | 17.891 | 0.029 |
| total_race_duration | 5.575 | 17.729 | 0.033 |
| variance_absolute | 5.555 | 17.659 | 0.036 |
| 50th_percentile_gap | 5.491 | 17.426 | 0.038 |
| riders_in_groups | 5.486 | 17.342 | 0.011 |
| skewness_absolute | 5.149 | 16.065 | 0.017 |

#### Removed Features by Reason

**Low Score** (6 features):
- 5th_percentile_gap
- abandon_ratio
- kurtosis_absolute
- largest_group_position
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
- included_finishers
- kurtosis_normalized
- ... and 6 more

**Redundant** (15 features):
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
- ... and 5 more

---

### Scenario 2: 30th percentile - one_day - ['wt']

- **Races analyzed**: 163
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.525 | 20.952 | 0.019 |
| selection_metric | 6.409 | 20.322 | 0.023 |
| kurtosis_normalized | 6.398 | 20.304 | 0.005 |
| clumpiness_score | 6.345 | 20.075 | 0.024 |
| biggest_group_metric | 6.345 | 20.060 | 0.045 |
| avg_group_size | 6.319 | 20.059 | 0.055 |
| std_deviation_absolute | 6.307 | 20.134 | 0.033 |
| 50th_percentile_gap | 6.249 | 19.849 | 0.059 |
| largest_group_size | 6.192 | 19.673 | 0.079 |
| proportion_in_groups | 6.160 | 19.552 | 0.006 |
| total_race_duration | 6.116 | 19.398 | 0.020 |
| total_finishers | 6.077 | 19.154 | 0.010 |
| std_group_size | 6.058 | 19.012 | 0.088 |
| gini_coefficient | 6.049 | 19.007 | 0.014 |
| total_groups | 6.044 | 19.167 | 0.041 |
| riders_in_groups | 5.861 | 18.552 | 0.015 |
| time_gap_evenness_metric | 5.855 | 18.489 | 0.013 |
| skewness_normalized | 5.798 | 18.138 | 0.005 |

#### Removed Features by Reason

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (15 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
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
- largest_group_position
- winning_time

---

### Scenario 3: 30th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2088
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.883 | 18.517 | 0.050 |
| biggest_group_metric | 5.873 | 18.575 | 0.020 |
| avg_group_size | 5.823 | 18.419 | 0.057 |
| selection_metric | 5.739 | 18.210 | 0.053 |
| std_group_size | 5.713 | 17.941 | 0.021 |
| proportion_in_groups | 5.701 | 18.034 | 0.017 |
| gini_coefficient | 5.672 | 17.868 | 0.070 |
| std_deviation_normalized | 5.666 | 17.973 | 0.045 |
| total_race_duration | 5.595 | 17.787 | 0.032 |
| variance_absolute | 5.563 | 17.681 | 0.041 |
| 50th_percentile_gap | 5.519 | 17.520 | 0.038 |
| 5th_percentile_gap | 5.380 | 17.092 | 0.005 |
| skewness_normalized | 5.163 | 16.105 | 0.012 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- largest_group_size
- ... and 6 more

---

### Scenario 4: 40th percentile - stage - ['wt']

- **Races analyzed**: 1948
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.778 | 18.176 | 0.053 |
| biggest_group_metric | 5.767 | 18.268 | 0.026 |
| avg_group_size | 5.723 | 18.137 | 0.040 |
| largest_group_position | 5.671 | 17.991 | 0.005 |
| selection_metric | 5.664 | 17.993 | 0.033 |
| std_group_size | 5.640 | 17.684 | 0.036 |
| gini_coefficient | 5.587 | 17.571 | 0.066 |
| proportion_in_groups | 5.574 | 17.655 | 0.015 |
| std_deviation_normalized | 5.557 | 17.653 | 0.022 |
| time_gap_evenness_metric | 5.547 | 17.602 | 0.013 |
| total_race_duration | 5.532 | 17.566 | 0.030 |
| 50th_percentile_gap | 5.467 | 17.339 | 0.037 |
| variance_absolute | 5.467 | 17.321 | 0.054 |
| riders_in_groups | 5.404 | 17.040 | 0.014 |
| skewness_normalized | 5.049 | 15.703 | 0.013 |

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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (15 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- largest_group_size
- ... and 5 more

---

### Scenario 5: 40th percentile - one_day - ['wt']

- **Races analyzed**: 208
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.496 | 20.851 | 0.028 |
| biggest_group_metric | 6.475 | 20.493 | 0.024 |
| kurtosis_normalized | 6.433 | 20.465 | 0.011 |
| clumpiness_score | 6.421 | 20.321 | 0.027 |
| selection_metric | 6.345 | 20.131 | 0.013 |
| avg_group_size | 6.320 | 20.102 | 0.040 |
| 50th_percentile_gap | 6.270 | 19.868 | 0.065 |
| total_race_duration | 6.237 | 19.784 | 0.021 |
| std_group_size | 6.206 | 19.565 | 0.021 |
| total_finishers | 6.170 | 19.417 | 0.019 |
| gini_coefficient | 6.167 | 19.369 | 0.056 |
| largest_group_size | 6.156 | 19.575 | 0.049 |
| std_deviation_absolute | 6.135 | 19.498 | 0.017 |
| proportion_in_groups | 6.125 | 19.421 | 0.011 |
| riders_in_groups | 6.079 | 19.210 | 0.037 |
| total_groups | 6.043 | 19.192 | 0.009 |
| time_gap_evenness_metric | 5.970 | 18.860 | 0.012 |
| skewness_normalized | 5.927 | 18.667 | 0.018 |

#### Removed Features by Reason

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (15 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
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
- largest_group_position
- winning_time

---

### Scenario 6: 40th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2156
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.869 | 18.558 | 0.027 |
| clumpiness_score | 5.867 | 18.494 | 0.035 |
| avg_group_size | 5.824 | 18.406 | 0.079 |
| selection_metric | 5.753 | 18.227 | 0.063 |
| kurtosis_normalized | 5.708 | 18.095 | 0.012 |
| std_group_size | 5.701 | 17.911 | 0.009 |
| gini_coefficient | 5.656 | 17.843 | 0.014 |
| std_deviation_normalized | 5.653 | 17.931 | 0.026 |
| total_groups | 5.626 | 17.867 | 0.031 |
| total_race_duration | 5.618 | 17.817 | 0.039 |
| 50th_percentile_gap | 5.552 | 17.593 | 0.041 |
| variance_absolute | 5.546 | 17.579 | 0.048 |
| skewness_normalized | 5.085 | 15.853 | 0.016 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- largest_group_position
- proportion_in_groups
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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (15 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- largest_group_size
- ... and 5 more

---

### Scenario 7: 50th percentile - stage - ['wt']

- **Races analyzed**: 1951
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.750 | 18.090 | 0.046 |
| biggest_group_metric | 5.745 | 18.195 | 0.027 |
| avg_group_size | 5.682 | 17.996 | 0.041 |
| selection_metric | 5.655 | 17.962 | 0.016 |
| largest_group_position | 5.642 | 17.867 | 0.007 |
| largest_group_size | 5.608 | 17.767 | 0.016 |
| std_group_size | 5.582 | 17.515 | 0.031 |
| gini_coefficient | 5.556 | 17.431 | 0.060 |
| proportion_in_groups | 5.531 | 17.499 | 0.009 |
| std_deviation_normalized | 5.522 | 17.506 | 0.033 |
| 50th_percentile_gap | 5.488 | 17.391 | 0.031 |
| variance_absolute | 5.470 | 17.303 | 0.046 |
| riders_in_groups | 5.359 | 16.858 | 0.011 |
| skewness_normalized | 4.977 | 15.435 | 0.011 |

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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (15 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 5 more

---

### Scenario 8: 50th percentile - one_day - ['wt']

- **Races analyzed**: 221
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.664 | 21.090 | 0.077 |
| variance_absolute | 6.650 | 21.258 | 0.019 |
| clumpiness_score | 6.621 | 20.997 | 0.015 |
| kurtosis_absolute | 6.549 | 20.872 | 0.007 |
| avg_group_size | 6.540 | 20.893 | 0.017 |
| largest_group_position | 6.527 | 20.708 | 0.010 |
| 50th_percentile_gap | 6.505 | 20.620 | 0.069 |
| selection_metric | 6.470 | 20.535 | 0.019 |
| total_race_duration | 6.423 | 20.364 | 0.021 |
| total_finishers | 6.417 | 20.182 | 0.011 |
| shannon_entropy_normalized | 6.396 | 20.360 | 0.015 |
| largest_group_size | 6.343 | 20.218 | 0.029 |
| gini_coefficient | 6.323 | 19.889 | 0.050 |
| proportion_in_groups | 6.305 | 19.991 | 0.009 |
| shannon_entropy_absolute | 6.288 | 19.964 | 0.018 |
| std_group_size | 6.275 | 19.825 | 0.020 |
| total_groups | 6.204 | 19.747 | 0.006 |
| time_gap_evenness_metric | 6.201 | 19.627 | 0.006 |
| skewness_absolute | 5.939 | 18.627 | 0.024 |

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

**Redundant** (13 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- ... and 3 more

**Low Score** (2 features):
- abandon_ratio
- winning_time

---

### Scenario 9: 50th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.842 | 18.390 | 0.049 |
| biggest_group_metric | 5.825 | 18.456 | 0.030 |
| avg_group_size | 5.766 | 18.284 | 0.040 |
| largest_group_position | 5.720 | 18.123 | 0.008 |
| selection_metric | 5.709 | 18.138 | 0.011 |
| largest_group_size | 5.685 | 18.019 | 0.026 |
| std_group_size | 5.644 | 17.727 | 0.023 |
| gini_coefficient | 5.627 | 17.661 | 0.052 |
| std_deviation_normalized | 5.601 | 17.760 | 0.028 |
| proportion_in_groups | 5.595 | 17.710 | 0.008 |
| total_groups | 5.566 | 17.689 | 0.024 |
| 50th_percentile_gap | 5.565 | 17.625 | 0.043 |
| variance_absolute | 5.550 | 17.551 | 0.052 |
| riders_in_groups | 5.467 | 17.197 | 0.010 |
| skewness_absolute | 4.973 | 15.408 | 0.017 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- kurtosis_normalized
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
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 4 more

---

### Scenario 10: 60th percentile - stage - ['wt']

- **Races analyzed**: 1953
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.725 | 18.106 | 0.041 |
| clumpiness_score | 5.699 | 17.911 | 0.046 |
| avg_group_size | 5.647 | 17.881 | 0.028 |
| largest_group_position | 5.642 | 17.836 | 0.007 |
| selection_metric | 5.635 | 17.886 | 0.005 |
| largest_group_size | 5.566 | 17.600 | 0.031 |
| std_group_size | 5.554 | 17.418 | 0.043 |
| gini_coefficient | 5.529 | 17.290 | 0.056 |
| std_deviation_normalized | 5.500 | 17.416 | 0.028 |
| 50th_percentile_gap | 5.476 | 17.317 | 0.064 |
| total_groups | 5.459 | 17.305 | 0.028 |
| variance_absolute | 5.453 | 17.227 | 0.043 |
| riders_in_groups | 5.320 | 16.674 | 0.005 |
| 10th_percentile_gap | 5.292 | 16.744 | 0.011 |
| skewness_absolute | 4.935 | 15.312 | 0.012 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (14 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_absolute
- ... and 4 more

---

### Scenario 11: 60th percentile - one_day - ['wt']

- **Races analyzed**: 224
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.887 | 21.899 | 0.018 |
| clumpiness_score | 6.754 | 21.411 | 0.012 |
| variance_absolute | 6.745 | 21.485 | 0.037 |
| kurtosis_absolute | 6.710 | 21.437 | 0.019 |
| 50th_percentile_gap | 6.703 | 21.307 | 0.044 |
| total_race_duration | 6.673 | 21.210 | 0.036 |
| avg_group_size | 6.599 | 21.129 | 0.019 |
| selection_metric | 6.563 | 20.866 | 0.010 |
| shannon_entropy_normalized | 6.530 | 20.755 | 0.082 |
| std_group_size | 6.529 | 20.752 | 0.012 |
| largest_group_size | 6.506 | 20.777 | 0.030 |
| gini_coefficient | 6.490 | 20.502 | 0.005 |
| total_groups | 6.443 | 20.516 | 0.010 |
| shannon_entropy_absolute | 6.242 | 19.795 | 0.042 |
| time_gap_evenness_metric | 6.196 | 19.606 | 0.010 |
| skewness_absolute | 6.124 | 19.244 | 0.029 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- largest_group_position
- proportion_in_groups
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
- included_finishers
- ... and 6 more

**Redundant** (13 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- ... and 3 more

---

### Scenario 12: 60th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2177
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.841 | 18.488 | 0.040 |
| clumpiness_score | 5.827 | 18.334 | 0.040 |
| avg_group_size | 5.767 | 18.276 | 0.032 |
| largest_group_position | 5.748 | 18.190 | 0.010 |
| selection_metric | 5.722 | 18.164 | 0.011 |
| largest_group_size | 5.682 | 17.980 | 0.031 |
| std_group_size | 5.655 | 17.756 | 0.038 |
| gini_coefficient | 5.633 | 17.622 | 0.061 |
| std_deviation_normalized | 5.614 | 17.789 | 0.029 |
| 50th_percentile_gap | 5.578 | 17.668 | 0.055 |
| variance_absolute | 5.562 | 17.598 | 0.035 |
| proportion_in_groups | 5.554 | 17.555 | 0.005 |
| total_groups | 5.551 | 17.625 | 0.018 |
| 10th_percentile_gap | 5.404 | 17.123 | 0.010 |
| skewness_absolute | 5.027 | 15.614 | 0.012 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (14 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_absolute
- ... and 4 more

---

### Scenario 13: 70th percentile - stage - ['wt']

- **Races analyzed**: 1953
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.800 | 18.363 | 0.051 |
| clumpiness_score | 5.748 | 18.097 | 0.010 |
| selection_metric | 5.725 | 18.193 | 0.011 |
| largest_group_position | 5.717 | 18.091 | 0.008 |
| avg_group_size | 5.711 | 18.106 | 0.022 |
| shannon_entropy_absolute | 5.670 | 17.988 | 0.020 |
| largest_group_size | 5.620 | 17.801 | 0.024 |
| gini_coefficient | 5.594 | 17.469 | 0.054 |
| std_group_size | 5.590 | 17.561 | 0.026 |
| std_deviation_normalized | 5.585 | 17.685 | 0.040 |
| 50th_percentile_gap | 5.569 | 17.638 | 0.041 |
| variance_absolute | 5.534 | 17.471 | 0.043 |
| total_groups | 5.477 | 17.385 | 0.012 |
| time_gap_evenness_metric | 5.470 | 17.306 | 0.008 |
| riders_in_groups | 5.397 | 16.923 | 0.006 |
| 10th_percentile_gap | 5.346 | 16.920 | 0.008 |
| skewness_absolute | 5.065 | 15.824 | 0.010 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (14 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 4 more

---

### Scenario 14: 70th percentile - one_day - ['wt']

- **Races analyzed**: 227
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.184 | 23.010 | 0.007 |
| biggest_group_metric | 7.128 | 22.687 | 0.027 |
| largest_group_position | 7.028 | 22.359 | 0.008 |
| clumpiness_score | 6.928 | 21.961 | 0.006 |
| 50th_percentile_gap | 6.910 | 21.958 | 0.057 |
| winning_time | 6.887 | 21.746 | 0.007 |
| avg_group_size | 6.856 | 21.926 | 0.063 |
| total_race_duration | 6.841 | 21.755 | 0.013 |
| variance_absolute | 6.814 | 21.680 | 0.010 |
| std_group_size | 6.778 | 21.527 | 0.035 |
| abandon_ratio | 6.693 | 21.157 | 0.005 |
| gini_coefficient | 6.684 | 21.124 | 0.022 |
| largest_group_size | 6.656 | 21.212 | 0.049 |
| selection_metric | 6.641 | 21.063 | 0.006 |
| shannon_entropy_normalized | 6.640 | 21.136 | 0.024 |
| total_groups | 6.623 | 21.060 | 0.028 |
| proportion_in_groups | 6.558 | 20.824 | 0.010 |
| shannon_entropy_absolute | 6.499 | 20.629 | 0.012 |
| skewness_absolute | 6.494 | 20.532 | 0.013 |
| time_gap_evenness_metric | 6.341 | 20.048 | 0.031 |

#### Removed Features by Reason

**Low Score** (1 features):
- total_finishers

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

**Redundant** (14 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- ... and 4 more

---

### Scenario 15: 70th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2180
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.929 | 18.772 | 0.066 |
| clumpiness_score | 5.885 | 18.544 | 0.020 |
| avg_group_size | 5.840 | 18.536 | 0.024 |
| selection_metric | 5.836 | 18.555 | 0.011 |
| largest_group_position | 5.836 | 18.487 | 0.010 |
| shannon_entropy_absolute | 5.783 | 18.374 | 0.012 |
| largest_group_size | 5.739 | 18.189 | 0.026 |
| std_group_size | 5.708 | 17.948 | 0.024 |
| std_deviation_normalized | 5.699 | 18.063 | 0.034 |
| gini_coefficient | 5.686 | 17.799 | 0.040 |
| 50th_percentile_gap | 5.684 | 18.015 | 0.047 |
| variance_absolute | 5.652 | 17.867 | 0.038 |
| total_groups | 5.606 | 17.811 | 0.013 |
| time_gap_evenness_metric | 5.581 | 17.667 | 0.008 |
| 10th_percentile_gap | 5.468 | 17.326 | 0.010 |
| skewness_absolute | 5.177 | 16.192 | 0.018 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (13 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 3 more

---

### Scenario 16: 80th percentile - stage - ['wt']

- **Races analyzed**: 1953
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| selection_metric | 5.890 | 18.683 | 0.042 |
| largest_group_position | 5.884 | 18.621 | 0.015 |
| clumpiness_score | 5.840 | 18.367 | 0.005 |
| avg_group_size | 5.839 | 18.509 | 0.024 |
| kurtosis_normalized | 5.808 | 18.477 | 0.009 |
| shannon_entropy_absolute | 5.753 | 18.212 | 0.046 |
| largest_group_size | 5.737 | 18.173 | 0.019 |
| 50th_percentile_gap | 5.730 | 18.147 | 0.044 |
| std_deviation_normalized | 5.724 | 18.143 | 0.018 |
| std_group_size | 5.712 | 17.995 | 0.020 |
| variance_absolute | 5.689 | 17.982 | 0.020 |
| gini_coefficient | 5.678 | 17.812 | 0.010 |
| proportion_in_groups | 5.647 | 17.858 | 0.005 |
| total_groups | 5.599 | 17.771 | 0.011 |
| time_gap_evenness_metric | 5.582 | 17.648 | 0.017 |
| 5th_percentile_gap | 5.426 | 17.194 | 0.008 |
| skewness_normalized | 5.247 | 16.518 | 0.011 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
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
- biggest_group_metric
- included_finishers
- ... and 6 more

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
- shannon_entropy_normalized
- ... and 4 more

---

### Scenario 17: 80th percentile - one_day - ['wt']

- **Races analyzed**: 229
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.095 | 22.763 | 0.005 |
| biggest_group_metric | 7.070 | 22.471 | 0.032 |
| largest_group_position | 6.948 | 22.065 | 0.013 |
| 50th_percentile_gap | 6.874 | 21.802 | 0.071 |
| clumpiness_score | 6.870 | 21.767 | 0.007 |
| avg_group_size | 6.870 | 22.040 | 0.009 |
| winning_time | 6.827 | 21.540 | 0.010 |
| total_finishers | 6.764 | 21.306 | 0.069 |
| abandon_ratio | 6.725 | 21.256 | 0.011 |
| shannon_entropy_normalized | 6.719 | 21.393 | 0.012 |
| variance_absolute | 6.659 | 21.115 | 0.024 |
| std_group_size | 6.650 | 21.088 | 0.006 |
| gini_coefficient | 6.560 | 20.692 | 0.030 |
| total_groups | 6.556 | 20.841 | 0.018 |
| proportion_in_groups | 6.507 | 20.661 | 0.006 |
| skewness_absolute | 6.503 | 20.641 | 0.014 |
| largest_group_size | 6.481 | 20.656 | 0.015 |
| selection_metric | 6.431 | 20.351 | 0.005 |
| time_gap_evenness_metric | 6.337 | 20.049 | 0.008 |

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
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- ... and 5 more

**Low Score** (1 features):
- shannon_entropy_absolute

---

### Scenario 18: 80th percentile - stage_one_day - ['wt']

- **Races analyzed**: 2182
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.105 | 19.288 | 0.119 |
| selection_metric | 5.998 | 19.047 | 0.009 |
| largest_group_position | 5.992 | 18.978 | 0.010 |
| clumpiness_score | 5.989 | 18.843 | 0.009 |
| avg_group_size | 5.975 | 18.961 | 0.020 |
| largest_group_size | 5.865 | 18.592 | 0.031 |
| shannon_entropy_absolute | 5.860 | 18.587 | 0.009 |
| 50th_percentile_gap | 5.846 | 18.505 | 0.060 |
| std_deviation_normalized | 5.833 | 18.487 | 0.019 |
| std_group_size | 5.826 | 18.373 | 0.027 |
| variance_absolute | 5.809 | 18.363 | 0.031 |
| gini_coefficient | 5.797 | 18.149 | 0.046 |
| proportion_in_groups | 5.745 | 18.190 | 0.005 |
| total_groups | 5.698 | 18.093 | 0.008 |
| time_gap_evenness_metric | 5.685 | 17.993 | 0.010 |
| riders_in_groups | 5.659 | 17.789 | 0.008 |
| total_finishers | 5.643 | 17.616 | 0.007 |
| 5th_percentile_gap | 5.559 | 17.629 | 0.007 |
| skewness_normalized | 5.356 | 16.833 | 0.021 |

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
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 4 more

**Low Score** (3 features):
- abandon_ratio
- kurtosis_normalized
- winning_time

---

