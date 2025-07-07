# Feature Selection Exploration Report

Generated: 2025-07-07 10:47:19

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
| variance_absolute | 5.926 | 19.306 | 0.058 |
| variance_normalized | 5.918 | 19.355 | 0.016 |
| winning_time | 5.890 | 18.584 | 0.050 |
| std_deviation_absolute | 5.832 | 18.557 | 0.062 |
| clumpiness_score | 5.737 | 18.091 | 0.028 |
| shannon_entropy_normalized | 5.635 | 17.868 | 0.010 |
| std_group_size | 5.614 | 17.845 | 0.053 |
| riders_in_groups | 5.601 | 17.780 | 0.051 |
| avg_group_size | 5.595 | 17.764 | 0.094 |
| largest_group_size | 5.570 | 17.731 | 0.087 |
| time_gap_evenness_metric | 5.554 | 17.498 | 0.071 |
| kurtosis_normalized | 5.543 | 17.603 | 0.013 |
| selection_metric | 5.519 | 17.406 | 0.033 |
| gini_coefficient | 5.271 | 16.472 | 0.025 |

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
| variance_absolute | 5.845 | 19.037 | 0.051 |
| variance_normalized | 5.820 | 19.192 | 0.012 |
| winning_time | 5.811 | 18.319 | 0.037 |
| std_deviation_absolute | 5.703 | 18.045 | 0.058 |
| clumpiness_score | 5.672 | 17.788 | 0.077 |
| std_group_size | 5.614 | 17.814 | 0.076 |
| riders_in_groups | 5.579 | 17.621 | 0.087 |
| largest_group_size | 5.554 | 17.677 | 0.064 |
| time_gap_evenness_metric | 5.550 | 17.474 | 0.056 |
| shannon_entropy_normalized | 5.547 | 17.571 | 0.008 |
| avg_group_size | 5.536 | 17.639 | 0.046 |
| selection_metric | 5.425 | 17.085 | 0.018 |
| kurtosis_normalized | 5.360 | 17.026 | 0.006 |
| gini_coefficient | 5.298 | 16.519 | 0.008 |
| shannon_entropy_absolute | 5.270 | 16.563 | 0.006 |
| skewness_normalized | 5.072 | 15.726 | 0.008 |

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
| variance_absolute | 5.802 | 18.715 | 0.020 |
| variance_normalized | 5.785 | 19.105 | 0.007 |
| winning_time | 5.773 | 18.215 | 0.019 |
| clumpiness_score | 5.618 | 17.635 | 0.051 |
| avg_group_size | 5.594 | 17.844 | 0.026 |
| riders_in_groups | 5.557 | 17.483 | 0.132 |
| total_finishers | 5.549 | 17.283 | 0.005 |
| time_gap_evenness_metric | 5.539 | 17.449 | 0.021 |
| shannon_entropy_normalized | 5.530 | 17.479 | 0.007 |
| largest_group_size | 5.511 | 17.521 | 0.041 |
| total_groups | 5.507 | 17.312 | 0.032 |
| std_group_size | 5.504 | 17.466 | 0.036 |
| selection_metric | 5.322 | 16.720 | 0.011 |
| gini_coefficient | 5.262 | 16.384 | 0.005 |
| skewness_absolute | 4.975 | 15.411 | 0.007 |

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
| variance_absolute | 5.696 | 18.221 | 0.025 |
| winning_time | 5.666 | 17.889 | 0.013 |
| avg_group_size | 5.531 | 17.723 | 0.025 |
| clumpiness_score | 5.475 | 17.177 | 0.060 |
| time_gap_evenness_metric | 5.463 | 17.201 | 0.111 |
| largest_group_size | 5.421 | 17.307 | 0.056 |
| riders_in_groups | 5.415 | 17.111 | 0.079 |
| shannon_entropy_normalized | 5.393 | 17.140 | 0.013 |
| std_group_size | 5.381 | 17.128 | 0.049 |
| kurtosis_normalized | 5.260 | 16.877 | 0.005 |
| shannon_entropy_absolute | 4.989 | 15.660 | 0.008 |

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
| variance_absolute | 5.629 | 17.856 | 0.018 |
| winning_time | 5.623 | 17.714 | 0.014 |
| variance_normalized | 5.618 | 18.587 | 0.010 |
| avg_group_size | 5.493 | 17.575 | 0.016 |
| clumpiness_score | 5.393 | 16.896 | 0.038 |
| time_gap_evenness_metric | 5.383 | 16.949 | 0.030 |
| riders_in_groups | 5.383 | 16.895 | 0.120 |
| shannon_entropy_normalized | 5.373 | 16.998 | 0.022 |
| largest_group_size | 5.368 | 17.074 | 0.032 |
| total_groups | 5.367 | 16.856 | 0.015 |
| kurtosis_absolute | 5.367 | 17.261 | 0.006 |
| std_group_size | 5.358 | 17.014 | 0.041 |
| selection_metric | 5.116 | 16.019 | 0.006 |
| gini_coefficient | 5.056 | 15.687 | 0.007 |
| shannon_entropy_absolute | 4.997 | 15.639 | 0.007 |
| skewness_absolute | 4.640 | 14.355 | 0.007 |

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
| winning_time | 5.627 | 17.755 | 0.022 |
| variance_absolute | 5.613 | 17.737 | 0.022 |
| avg_group_size | 5.561 | 17.798 | 0.054 |
| largest_group_size | 5.424 | 17.273 | 0.055 |
| std_group_size | 5.420 | 17.235 | 0.032 |
| clumpiness_score | 5.398 | 16.950 | 0.042 |
| shannon_entropy_normalized | 5.396 | 17.108 | 0.023 |
| time_gap_evenness_metric | 5.378 | 16.913 | 0.072 |
| riders_in_groups | 5.367 | 16.883 | 0.103 |
| biggest_group_metric | 5.361 | 16.859 | 0.005 |
| total_groups | 5.359 | 16.846 | 0.008 |
| shannon_entropy_absolute | 5.069 | 15.925 | 0.011 |
| skewness_absolute | 5.017 | 15.751 | 0.006 |
| gini_coefficient | 4.998 | 15.502 | 0.006 |

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

