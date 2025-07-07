# Feature Selection Exploration Report

Generated: 2025-07-07 10:29:18

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 20
- **Total races analyzed**: 94,790
- **Average features selected**: 15.5

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| avg_group_size | 18 | 100.0% |
| clumpiness_score | 18 | 100.0% |
| time_gap_evenness_metric | 18 | 100.0% |
| total_groups | 18 | 100.0% |
| total_race_duration | 18 | 100.0% |
| variance_absolute | 18 | 100.0% |
| biggest_group_metric | 17 | 94.4% |
| gini_coefficient | 17 | 94.4% |
| std_group_size | 17 | 94.4% |
| proportion_in_groups | 17 | 94.4% |
| selection_metric | 15 | 83.3% |
| variance_normalized | 12 | 66.7% |
| largest_group_position | 12 | 66.7% |
| largest_group_size | 12 | 66.7% |
| skewness_normalized | 10 | 55.6% |

### Feature Removal Patterns

- **High correlation removals**: 288 (avg 16.0 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 274 (avg 15.2 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage_one_day

- **Races analyzed**: 6447
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.031 | 19.020 | 0.026 |
| avg_group_size | 5.974 | 18.782 | 0.117 |
| clumpiness_score | 5.889 | 18.523 | 0.014 |
| time_gap_evenness_metric | 5.875 | 18.567 | 0.034 |
| gini_coefficient | 5.849 | 18.442 | 0.067 |
| std_group_size | 5.830 | 18.372 | 0.006 |
| kurtosis_normalized | 5.787 | 18.312 | 0.005 |
| total_groups | 5.762 | 18.228 | 0.026 |
| total_race_duration | 5.743 | 18.306 | 0.053 |
| std_deviation_absolute | 5.625 | 18.360 | 0.046 |
| variance_absolute | 5.454 | 19.451 | 0.059 |
| variance_normalized | 5.416 | 19.503 | 0.019 |
| skewness_normalized | 5.286 | 16.513 | 0.011 |

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
- included_finishers
- ... and 6 more

---

### Scenario 2: 30th percentile - stage

- **Races analyzed**: 5772
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.960 | 18.820 | 0.026 |
| avg_group_size | 5.912 | 18.591 | 0.121 |
| proportion_in_groups | 5.835 | 18.444 | 0.008 |
| time_gap_evenness_metric | 5.811 | 18.390 | 0.041 |
| clumpiness_score | 5.809 | 18.245 | 0.008 |
| gini_coefficient | 5.767 | 18.192 | 0.057 |
| total_groups | 5.731 | 18.141 | 0.027 |
| kurtosis_absolute | 5.719 | 18.097 | 0.005 |
| total_race_duration | 5.701 | 18.181 | 0.052 |
| std_deviation_absolute | 5.571 | 18.166 | 0.048 |
| variance_absolute | 5.424 | 19.221 | 0.061 |
| variance_normalized | 5.389 | 19.273 | 0.019 |
| skewness_absolute | 5.212 | 16.281 | 0.009 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- largest_group_position
- riders_in_groups
- std_group_size
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
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- included_finishers
- ... and 6 more

---

### Scenario 3: 30th percentile - one_day

- **Races analyzed**: 675
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.256 | 19.785 | 0.043 |
| variance_absolute | 6.142 | 20.033 | 0.031 |
| gini_coefficient | 6.108 | 19.267 | 0.043 |
| avg_group_size | 6.076 | 19.242 | 0.070 |
| std_group_size | 6.052 | 19.023 | 0.056 |
| largest_group_position | 6.017 | 19.118 | 0.011 |
| proportion_in_groups | 5.935 | 18.847 | 0.008 |
| time_gap_evenness_metric | 5.903 | 18.768 | 0.013 |
| total_groups | 5.881 | 18.678 | 0.056 |
| 50th_percentile_gap | 5.829 | 18.555 | 0.058 |
| largest_group_size | 5.828 | 18.485 | 0.025 |
| total_race_duration | 5.778 | 18.348 | 0.054 |
| std_deviation_absolute | 5.622 | 17.961 | 0.035 |
| skewness_normalized | 5.589 | 17.486 | 0.010 |
| riders_in_groups | 5.522 | 17.404 | 0.005 |

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

### Scenario 4: 40th percentile - stage_one_day

- **Races analyzed**: 7786
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.974 | 18.863 | 0.021 |
| clumpiness_score | 5.885 | 18.475 | 0.036 |
| avg_group_size | 5.882 | 18.542 | 0.093 |
| proportion_in_groups | 5.875 | 18.533 | 0.071 |
| selection_metric | 5.869 | 18.548 | 0.048 |
| gini_coefficient | 5.803 | 18.256 | 0.080 |
| time_gap_evenness_metric | 5.794 | 18.344 | 0.031 |
| std_group_size | 5.781 | 18.191 | 0.019 |
| total_groups | 5.722 | 18.095 | 0.027 |
| total_race_duration | 5.669 | 18.103 | 0.033 |
| riders_in_groups | 5.634 | 17.730 | 0.009 |
| variance_absolute | 5.453 | 19.230 | 0.056 |
| std_deviation_absolute | 5.434 | 17.507 | 0.033 |
| variance_normalized | 5.315 | 19.408 | 0.025 |
| skewness_normalized | 5.217 | 16.253 | 0.012 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
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
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Redundant** (15 features):
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
- ... and 5 more

---

### Scenario 5: 40th percentile - stage

- **Races analyzed**: 6726
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.992 | 18.923 | 0.025 |
| avg_group_size | 5.908 | 18.619 | 0.095 |
| proportion_in_groups | 5.891 | 18.599 | 0.067 |
| selection_metric | 5.887 | 18.598 | 0.048 |
| clumpiness_score | 5.877 | 18.460 | 0.027 |
| time_gap_evenness_metric | 5.821 | 18.440 | 0.030 |
| std_group_size | 5.812 | 18.284 | 0.035 |
| gini_coefficient | 5.810 | 18.292 | 0.077 |
| winning_time | 5.790 | 18.388 | 0.005 |
| total_groups | 5.761 | 18.215 | 0.023 |
| total_race_duration | 5.681 | 18.149 | 0.037 |
| riders_in_groups | 5.656 | 17.820 | 0.010 |
| variance_absolute | 5.501 | 19.243 | 0.058 |
| std_deviation_absolute | 5.449 | 17.553 | 0.033 |
| variance_normalized | 5.381 | 19.427 | 0.017 |
| skewness_absolute | 5.223 | 16.278 | 0.014 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
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
- 50th_percentile_gap
- 5th_percentile_gap
- ... and 6 more

**Redundant** (15 features):
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
- ... and 5 more

---

### Scenario 6: 40th percentile - one_day

- **Races analyzed**: 1060
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.433 | 20.373 | 0.055 |
| biggest_group_metric | 6.390 | 20.259 | 0.025 |
| selection_metric | 6.324 | 20.095 | 0.044 |
| gini_coefficient | 6.232 | 19.660 | 0.054 |
| avg_group_size | 6.218 | 19.785 | 0.031 |
| std_group_size | 6.110 | 19.218 | 0.047 |
| largest_group_size | 6.039 | 19.189 | 0.023 |
| proportion_in_groups | 6.034 | 19.156 | 0.011 |
| variance_absolute | 6.018 | 19.416 | 0.031 |
| total_groups | 6.011 | 19.129 | 0.036 |
| total_race_duration | 6.008 | 19.080 | 0.043 |
| 50th_percentile_gap | 5.989 | 19.002 | 0.092 |
| time_gap_evenness_metric | 5.967 | 18.953 | 0.012 |
| skewness_normalized | 5.644 | 17.675 | 0.010 |

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

### Scenario 7: 50th percentile - stage_one_day

- **Races analyzed**: 8146
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.058 | 19.136 | 0.040 |
| clumpiness_score | 5.988 | 18.841 | 0.022 |
| avg_group_size | 5.976 | 18.858 | 0.090 |
| proportion_in_groups | 5.964 | 18.801 | 0.065 |
| selection_metric | 5.942 | 18.803 | 0.026 |
| largest_group_position | 5.912 | 18.678 | 0.007 |
| gini_coefficient | 5.875 | 18.471 | 0.076 |
| time_gap_evenness_metric | 5.862 | 18.545 | 0.028 |
| std_group_size | 5.842 | 18.385 | 0.020 |
| total_groups | 5.787 | 18.333 | 0.024 |
| total_race_duration | 5.747 | 18.307 | 0.038 |
| variance_absolute | 5.666 | 19.328 | 0.057 |
| variance_normalized | 5.398 | 19.724 | 0.047 |
| skewness_normalized | 5.227 | 16.252 | 0.018 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
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

### Scenario 8: 50th percentile - stage

- **Races analyzed**: 6897
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.931 | 18.706 | 0.076 |
| avg_group_size | 5.875 | 18.435 | 0.194 |
| clumpiness_score | 5.826 | 18.322 | 0.011 |
| selection_metric | 5.823 | 18.390 | 0.062 |
| proportion_in_groups | 5.814 | 18.394 | 0.010 |
| time_gap_evenness_metric | 5.749 | 18.175 | 0.064 |
| std_group_size | 5.729 | 18.023 | 0.018 |
| total_groups | 5.689 | 18.000 | 0.043 |
| total_race_duration | 5.635 | 17.956 | 0.039 |
| variance_absolute | 5.557 | 18.867 | 0.055 |
| variance_normalized | 5.306 | 19.227 | 0.011 |

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

### Scenario 9: 50th percentile - one_day

- **Races analyzed**: 1249
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.667 | 21.124 | 0.050 |
| biggest_group_metric | 6.610 | 20.991 | 0.029 |
| largest_group_position | 6.451 | 20.500 | 0.006 |
| shannon_entropy_absolute | 6.436 | 20.489 | 0.020 |
| avg_group_size | 6.393 | 20.377 | 0.020 |
| gini_coefficient | 6.384 | 20.117 | 0.054 |
| selection_metric | 6.383 | 20.268 | 0.028 |
| total_finishers | 6.350 | 19.994 | 0.007 |
| std_group_size | 6.323 | 19.949 | 0.028 |
| total_race_duration | 6.272 | 19.929 | 0.026 |
| largest_group_size | 6.262 | 19.919 | 0.032 |
| 50th_percentile_gap | 6.250 | 19.825 | 0.091 |
| proportion_in_groups | 6.249 | 19.851 | 0.012 |
| variance_absolute | 6.243 | 19.971 | 0.038 |
| total_groups | 6.170 | 19.646 | 0.027 |
| time_gap_evenness_metric | 6.083 | 19.313 | 0.013 |
| skewness_normalized | 5.755 | 18.018 | 0.014 |

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

### Scenario 10: 60th percentile - stage_one_day

- **Races analyzed**: 8287
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.986 | 18.883 | 0.062 |
| clumpiness_score | 5.937 | 18.667 | 0.017 |
| avg_group_size | 5.906 | 18.645 | 0.082 |
| proportion_in_groups | 5.877 | 18.535 | 0.048 |
| selection_metric | 5.864 | 18.528 | 0.023 |
| largest_group_position | 5.859 | 18.472 | 0.011 |
| gini_coefficient | 5.800 | 18.183 | 0.069 |
| std_group_size | 5.780 | 18.191 | 0.018 |
| largest_group_size | 5.778 | 18.272 | 0.009 |
| time_gap_evenness_metric | 5.769 | 18.227 | 0.034 |
| total_groups | 5.684 | 17.987 | 0.020 |
| variance_absolute | 5.678 | 18.850 | 0.044 |
| total_race_duration | 5.672 | 18.057 | 0.029 |
| variance_normalized | 5.321 | 19.478 | 0.049 |
| skewness_absolute | 5.224 | 16.222 | 0.019 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
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

### Scenario 11: 60th percentile - stage

- **Races analyzed**: 6946
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.852 | 18.430 | 0.082 |
| avg_group_size | 5.773 | 18.191 | 0.097 |
| clumpiness_score | 5.763 | 18.094 | 0.015 |
| selection_metric | 5.751 | 18.157 | 0.030 |
| proportion_in_groups | 5.743 | 18.112 | 0.022 |
| largest_group_position | 5.728 | 18.043 | 0.009 |
| gini_coefficient | 5.680 | 17.773 | 0.099 |
| std_group_size | 5.665 | 17.811 | 0.021 |
| largest_group_size | 5.662 | 17.873 | 0.022 |
| time_gap_evenness_metric | 5.648 | 17.849 | 0.017 |
| total_groups | 5.574 | 17.633 | 0.010 |
| variance_absolute | 5.539 | 18.303 | 0.038 |
| total_race_duration | 5.524 | 17.552 | 0.029 |
| variance_normalized | 5.248 | 18.958 | 0.074 |
| skewness_absolute | 5.104 | 15.819 | 0.022 |

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

### Scenario 12: 60th percentile - one_day

- **Races analyzed**: 1341
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.893 | 21.889 | 0.057 |
| clumpiness_score | 6.874 | 21.799 | 0.037 |
| largest_group_position | 6.701 | 21.296 | 0.008 |
| avg_group_size | 6.597 | 21.048 | 0.022 |
| total_finishers | 6.591 | 20.780 | 0.022 |
| gini_coefficient | 6.590 | 20.784 | 0.041 |
| selection_metric | 6.586 | 20.934 | 0.025 |
| shannon_entropy_absolute | 6.559 | 20.882 | 0.005 |
| 50th_percentile_gap | 6.551 | 20.815 | 0.069 |
| total_race_duration | 6.532 | 20.772 | 0.023 |
| std_group_size | 6.531 | 20.664 | 0.048 |
| kurtosis_normalized | 6.528 | 20.800 | 0.006 |
| proportion_in_groups | 6.520 | 20.740 | 0.006 |
| largest_group_size | 6.505 | 20.685 | 0.051 |
| variance_absolute | 6.433 | 20.534 | 0.028 |
| total_groups | 6.384 | 20.344 | 0.013 |
| time_gap_evenness_metric | 6.285 | 19.951 | 0.015 |
| skewness_normalized | 5.994 | 18.804 | 0.016 |

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

### Scenario 13: 70th percentile - stage_one_day

- **Races analyzed**: 8347
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.033 | 18.987 | 0.120 |
| clumpiness_score | 5.974 | 18.780 | 0.029 |
| avg_group_size | 5.906 | 18.694 | 0.043 |
| largest_group_position | 5.906 | 18.630 | 0.011 |
| proportion_in_groups | 5.905 | 18.668 | 0.012 |
| shannon_entropy_absolute | 5.904 | 18.721 | 0.014 |
| selection_metric | 5.859 | 18.509 | 0.020 |
| gini_coefficient | 5.818 | 18.199 | 0.073 |
| largest_group_size | 5.795 | 18.325 | 0.024 |
| time_gap_evenness_metric | 5.782 | 18.275 | 0.028 |
| std_group_size | 5.780 | 18.181 | 0.030 |
| variance_absolute | 5.729 | 18.676 | 0.045 |
| total_race_duration | 5.685 | 18.095 | 0.022 |
| total_groups | 5.684 | 17.989 | 0.011 |
| variance_normalized | 5.351 | 19.605 | 0.022 |
| skewness_absolute | 5.251 | 16.332 | 0.023 |

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

**Redundant** (15 features):
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
- ... and 5 more

---

### Scenario 14: 70th percentile - stage

- **Races analyzed**: 6948
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.925 | 18.599 | 0.145 |
| clumpiness_score | 5.835 | 18.307 | 0.030 |
| avg_group_size | 5.809 | 18.354 | 0.043 |
| proportion_in_groups | 5.802 | 18.315 | 0.013 |
| largest_group_position | 5.797 | 18.266 | 0.010 |
| selection_metric | 5.763 | 18.190 | 0.018 |
| gini_coefficient | 5.717 | 17.876 | 0.071 |
| largest_group_size | 5.696 | 17.979 | 0.031 |
| time_gap_evenness_metric | 5.691 | 17.969 | 0.021 |
| std_group_size | 5.685 | 17.884 | 0.019 |
| variance_absolute | 5.632 | 18.296 | 0.041 |
| total_groups | 5.593 | 17.679 | 0.009 |
| total_race_duration | 5.581 | 17.741 | 0.018 |
| variance_normalized | 5.297 | 19.156 | 0.030 |
| skewness_absolute | 5.182 | 16.117 | 0.025 |

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

### Scenario 15: 70th percentile - one_day

- **Races analyzed**: 1399
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.030 | 22.339 | 0.050 |
| clumpiness_score | 7.003 | 22.215 | 0.020 |
| largest_group_position | 6.860 | 21.796 | 0.009 |
| avg_group_size | 6.763 | 21.593 | 0.026 |
| total_finishers | 6.703 | 21.168 | 0.014 |
| abandon_ratio | 6.682 | 21.065 | 0.006 |
| shannon_entropy_absolute | 6.672 | 21.218 | 0.009 |
| gini_coefficient | 6.669 | 21.049 | 0.033 |
| total_race_duration | 6.666 | 21.187 | 0.026 |
| selection_metric | 6.665 | 21.176 | 0.019 |
| kurtosis_normalized | 6.641 | 21.129 | 0.008 |
| proportion_in_groups | 6.639 | 21.120 | 0.009 |
| 50th_percentile_gap | 6.629 | 21.041 | 0.083 |
| largest_group_size | 6.624 | 21.038 | 0.071 |
| std_group_size | 6.607 | 20.934 | 0.054 |
| total_groups | 6.523 | 20.785 | 0.008 |
| time_gap_evenness_metric | 6.384 | 20.256 | 0.015 |
| variance_absolute | 6.353 | 20.243 | 0.024 |
| skewness_normalized | 6.205 | 19.494 | 0.018 |

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

### Scenario 16: 80th percentile - stage_one_day

- **Races analyzed**: 8382
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.127 | 19.357 | 0.046 |
| clumpiness_score | 6.048 | 19.025 | 0.020 |
| proportion_in_groups | 6.038 | 19.073 | 0.064 |
| largest_group_position | 6.026 | 19.011 | 0.011 |
| selection_metric | 6.025 | 19.002 | 0.045 |
| avg_group_size | 6.013 | 19.020 | 0.060 |
| shannon_entropy_absolute | 5.992 | 18.898 | 0.101 |
| winning_time | 5.968 | 18.967 | 0.006 |
| gini_coefficient | 5.889 | 18.440 | 0.009 |
| largest_group_size | 5.887 | 18.638 | 0.015 |
| time_gap_evenness_metric | 5.882 | 18.591 | 0.039 |
| std_group_size | 5.873 | 18.508 | 0.023 |
| variance_absolute | 5.825 | 18.848 | 0.010 |
| total_finishers | 5.796 | 18.105 | 0.005 |
| total_groups | 5.779 | 18.267 | 0.022 |
| total_race_duration | 5.764 | 18.376 | 0.014 |
| variance_normalized | 5.471 | 20.009 | 0.010 |

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
- 5th_percentile_gap
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
- 50th_percentile_gap
- included_finishers
- ... and 5 more

**Low Score** (4 features):
- abandon_ratio
- kurtosis_normalized
- riders_in_groups
- skewness_normalized

---

### Scenario 17: 80th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.039 | 18.973 | 0.156 |
| selection_metric | 5.926 | 18.728 | 0.016 |
| proportion_in_groups | 5.921 | 18.714 | 0.008 |
| largest_group_position | 5.910 | 18.638 | 0.010 |
| clumpiness_score | 5.901 | 18.534 | 0.014 |
| avg_group_size | 5.883 | 18.607 | 0.036 |
| shannon_entropy_absolute | 5.868 | 18.582 | 0.021 |
| gini_coefficient | 5.800 | 18.127 | 0.068 |
| time_gap_evenness_metric | 5.788 | 18.291 | 0.020 |
| largest_group_size | 5.784 | 18.287 | 0.016 |
| std_group_size | 5.775 | 18.198 | 0.019 |
| kurtosis_normalized | 5.758 | 18.294 | 0.005 |
| variance_absolute | 5.738 | 18.468 | 0.023 |
| total_groups | 5.688 | 17.983 | 0.008 |
| total_race_duration | 5.666 | 18.017 | 0.009 |
| variance_normalized | 5.423 | 19.554 | 0.042 |
| skewness_normalized | 5.239 | 16.379 | 0.018 |

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

### Scenario 18: 80th percentile - one_day

- **Races analyzed**: 1431
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.161 | 22.816 | 0.021 |
| clumpiness_score | 7.062 | 22.384 | 0.043 |
| largest_group_position | 7.027 | 22.348 | 0.007 |
| avg_group_size | 6.866 | 21.936 | 0.065 |
| total_finishers | 6.844 | 21.636 | 0.005 |
| 50th_percentile_gap | 6.808 | 21.635 | 0.080 |
| shannon_entropy_normalized | 6.806 | 21.693 | 0.027 |
| total_race_duration | 6.782 | 21.572 | 0.031 |
| gini_coefficient | 6.747 | 21.329 | 0.011 |
| proportion_in_groups | 6.733 | 21.443 | 0.007 |
| largest_group_size | 6.727 | 21.438 | 0.033 |
| selection_metric | 6.708 | 21.321 | 0.015 |
| kurtosis_normalized | 6.678 | 21.422 | 0.007 |
| shannon_entropy_absolute | 6.670 | 21.192 | 0.023 |
| std_group_size | 6.658 | 21.157 | 0.027 |
| total_groups | 6.600 | 21.024 | 0.015 |
| time_gap_evenness_metric | 6.491 | 20.611 | 0.020 |
| variance_absolute | 6.485 | 20.658 | 0.036 |
| skewness_normalized | 6.116 | 19.226 | 0.007 |

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

