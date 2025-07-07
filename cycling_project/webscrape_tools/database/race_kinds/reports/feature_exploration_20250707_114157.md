# Feature Selection Exploration Report

Generated: 2025-07-07 11:42:02

## Executive Summary

- **Total scenarios analyzed**: 6
- **Max features per scenario**: 20
- **Total races analyzed**: 5,670
- **Average features selected**: 14.3

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| variance_absolute | 6 | 100.0% |
| winning_time | 6 | 100.0% |
| clumpiness_score | 6 | 100.0% |
| shannon_entropy_normalized | 6 | 100.0% |
| std_group_size | 6 | 100.0% |
| riders_in_groups | 6 | 100.0% |
| avg_group_size | 6 | 100.0% |
| largest_group_size | 6 | 100.0% |
| time_gap_evenness_metric | 6 | 100.0% |
| gini_coefficient | 5 | 83.3% |
| variance_normalized | 4 | 66.7% |
| selection_metric | 4 | 66.7% |
| shannon_entropy_absolute | 4 | 66.7% |
| kurtosis_normalized | 3 | 50.0% |
| total_groups | 3 | 50.0% |

### Feature Removal Patterns

- **High correlation removals**: 100 (avg 16.7 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 98 (avg 16.3 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - gc

- **Races analyzed**: 676
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.993 | 19.531 | 0.058 |
| variance_normalized | 5.986 | 19.580 | 0.016 |
| winning_time | 5.957 | 18.806 | 0.050 |
| std_deviation_absolute | 5.887 | 18.737 | 0.062 |
| clumpiness_score | 5.800 | 18.300 | 0.028 |
| shannon_entropy_normalized | 5.698 | 18.078 | 0.010 |
| std_group_size | 5.679 | 18.061 | 0.053 |
| riders_in_groups | 5.663 | 17.986 | 0.051 |
| avg_group_size | 5.663 | 17.989 | 0.094 |
| largest_group_size | 5.643 | 17.975 | 0.087 |
| time_gap_evenness_metric | 5.614 | 17.698 | 0.071 |
| kurtosis_normalized | 5.604 | 17.808 | 0.013 |
| selection_metric | 5.580 | 17.608 | 0.033 |
| gini_coefficient | 5.358 | 16.760 | 0.025 |

#### Removed Features by Reason

**Low Score** (7 features):
- abandon_ratio
- biggest_group_metric
- largest_group_position
- shannon_entropy_absolute
- skewness_normalized
- total_finishers
- total_groups

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

### Scenario 2: 40th percentile - gc

- **Races analyzed**: 936
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.891 | 19.191 | 0.051 |
| variance_normalized | 5.868 | 19.353 | 0.012 |
| winning_time | 5.857 | 18.472 | 0.037 |
| std_deviation_absolute | 5.775 | 18.284 | 0.058 |
| clumpiness_score | 5.715 | 17.930 | 0.077 |
| std_group_size | 5.659 | 17.963 | 0.076 |
| avg_group_size | 5.613 | 17.894 | 0.046 |
| riders_in_groups | 5.612 | 17.733 | 0.087 |
| time_gap_evenness_metric | 5.594 | 17.620 | 0.056 |
| shannon_entropy_normalized | 5.591 | 17.719 | 0.008 |
| largest_group_size | 5.590 | 17.795 | 0.064 |
| selection_metric | 5.468 | 17.228 | 0.018 |
| kurtosis_normalized | 5.336 | 16.948 | 0.006 |
| shannon_entropy_absolute | 5.314 | 16.711 | 0.006 |
| gini_coefficient | 5.313 | 16.571 | 0.008 |
| skewness_normalized | 5.102 | 15.824 | 0.008 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- biggest_group_metric
- largest_group_position
- total_finishers
- total_groups

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

### Scenario 3: 50th percentile - gc

- **Races analyzed**: 998
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.866 | 18.929 | 0.020 |
| variance_normalized | 5.834 | 19.269 | 0.007 |
| winning_time | 5.820 | 18.371 | 0.019 |
| clumpiness_score | 5.662 | 17.783 | 0.051 |
| avg_group_size | 5.653 | 18.041 | 0.026 |
| riders_in_groups | 5.603 | 17.637 | 0.132 |
| total_finishers | 5.594 | 17.433 | 0.005 |
| time_gap_evenness_metric | 5.583 | 17.599 | 0.021 |
| shannon_entropy_normalized | 5.575 | 17.629 | 0.007 |
| total_groups | 5.572 | 17.530 | 0.032 |
| largest_group_size | 5.554 | 17.663 | 0.041 |
| std_group_size | 5.553 | 17.629 | 0.036 |
| selection_metric | 5.365 | 16.865 | 0.011 |
| gini_coefficient | 5.304 | 16.525 | 0.005 |
| skewness_absolute | 5.014 | 15.540 | 0.007 |

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

### Scenario 4: 60th percentile - gc

- **Races analyzed**: 1019
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 5.800 | 18.566 | 0.025 |
| winning_time | 5.777 | 18.257 | 0.013 |
| avg_group_size | 5.639 | 18.083 | 0.025 |
| clumpiness_score | 5.581 | 17.532 | 0.060 |
| time_gap_evenness_metric | 5.569 | 17.556 | 0.111 |
| largest_group_size | 5.527 | 17.660 | 0.056 |
| riders_in_groups | 5.518 | 17.454 | 0.079 |
| std_group_size | 5.512 | 17.564 | 0.049 |
| shannon_entropy_normalized | 5.499 | 17.493 | 0.013 |
| kurtosis_normalized | 5.364 | 17.225 | 0.005 |
| shannon_entropy_absolute | 5.091 | 15.998 | 0.008 |

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

### Scenario 5: 70th percentile - gc

- **Races analyzed**: 1020
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.637 | 17.761 | 0.014 |
| variance_absolute | 5.634 | 17.874 | 0.018 |
| variance_normalized | 5.632 | 18.636 | 0.010 |
| avg_group_size | 5.494 | 17.581 | 0.016 |
| largest_group_size | 5.417 | 17.237 | 0.032 |
| clumpiness_score | 5.410 | 16.952 | 0.038 |
| time_gap_evenness_metric | 5.397 | 16.994 | 0.030 |
| riders_in_groups | 5.396 | 16.941 | 0.120 |
| std_group_size | 5.396 | 17.140 | 0.041 |
| shannon_entropy_normalized | 5.386 | 17.043 | 0.022 |
| total_groups | 5.379 | 16.895 | 0.015 |
| kurtosis_absolute | 5.332 | 17.146 | 0.006 |
| selection_metric | 5.126 | 16.051 | 0.006 |
| gini_coefficient | 5.058 | 15.694 | 0.007 |
| shannon_entropy_absolute | 5.040 | 15.781 | 0.007 |
| skewness_absolute | 4.664 | 14.435 | 0.007 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- biggest_group_metric
- largest_group_position
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

### Scenario 6: 80th percentile - gc

- **Races analyzed**: 1021
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.621 | 17.734 | 0.022 |
| variance_absolute | 5.569 | 17.590 | 0.022 |
| avg_group_size | 5.543 | 17.740 | 0.054 |
| largest_group_size | 5.418 | 17.253 | 0.055 |
| std_group_size | 5.411 | 17.204 | 0.032 |
| clumpiness_score | 5.392 | 16.930 | 0.042 |
| shannon_entropy_normalized | 5.390 | 17.086 | 0.023 |
| time_gap_evenness_metric | 5.372 | 16.893 | 0.072 |
| riders_in_groups | 5.363 | 16.869 | 0.103 |
| biggest_group_metric | 5.355 | 16.838 | 0.005 |
| total_groups | 5.351 | 16.818 | 0.008 |
| shannon_entropy_absolute | 5.087 | 15.982 | 0.011 |
| skewness_absolute | 5.017 | 15.750 | 0.006 |
| gini_coefficient | 5.000 | 15.511 | 0.006 |

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

