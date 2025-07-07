# Feature Selection Exploration Report

Generated: 2025-07-07 10:35:57

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 20
- **Total races analyzed**: 28,478
- **Average features selected**: 15.7

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| biggest_group_metric | 18 | 100.0% |
| variance_absolute | 18 | 100.0% |
| avg_group_size | 18 | 100.0% |
| clumpiness_score | 18 | 100.0% |
| time_gap_evenness_metric | 18 | 100.0% |
| total_groups | 18 | 100.0% |
| gini_coefficient | 17 | 94.4% |
| selection_metric | 16 | 88.9% |
| std_group_size | 16 | 88.9% |
| largest_group_size | 14 | 77.8% |
| variance_normalized | 12 | 66.7% |
| winning_time | 12 | 66.7% |
| largest_group_position | 11 | 61.1% |
| riders_in_groups | 10 | 55.6% |
| skewness_absolute | 9 | 50.0% |

### Feature Removal Patterns

- **High correlation removals**: 313 (avg 17.4 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 285 (avg 15.8 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage_one_day - wt

- **Races analyzed**: 2283
- **Features available**: 37
- **Features selected**: 10

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.421 | 16.948 | 0.104 |
| variance_absolute | 5.411 | 17.115 | 0.064 |
| avg_group_size | 5.379 | 16.843 | 0.130 |
| clumpiness_score | 5.253 | 16.426 | 0.013 |
| time_gap_evenness_metric | 5.228 | 16.439 | 0.023 |
| kurtosis_normalized | 5.217 | 16.449 | 0.009 |
| total_groups | 5.199 | 16.409 | 0.026 |
| gini_coefficient | 5.185 | 16.293 | 0.013 |
| variance_normalized | 5.112 | 17.413 | 0.022 |
| skewness_normalized | 4.759 | 14.773 | 0.037 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- largest_group_position
- riders_in_groups
- std_group_size
- total_finishers

**High Correlation** (20 features):
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
- ... and 10 more

**Redundant** (18 features):
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
- ... and 8 more

---

### Scenario 2: 30th percentile - stage - wt

- **Races analyzed**: 2120
- **Features available**: 37
- **Features selected**: 10

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.348 | 16.725 | 0.089 |
| variance_absolute | 5.338 | 16.864 | 0.068 |
| avg_group_size | 5.316 | 16.641 | 0.123 |
| time_gap_evenness_metric | 5.173 | 16.241 | 0.043 |
| clumpiness_score | 5.168 | 16.156 | 0.006 |
| kurtosis_absolute | 5.156 | 16.252 | 0.014 |
| total_groups | 5.155 | 16.268 | 0.026 |
| gini_coefficient | 5.116 | 16.073 | 0.016 |
| variance_normalized | 5.051 | 17.156 | 0.023 |
| skewness_absolute | 4.647 | 14.421 | 0.028 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- largest_group_position
- riders_in_groups
- std_group_size
- total_finishers

**High Correlation** (20 features):
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
- ... and 10 more

**Redundant** (18 features):
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
- ... and 8 more

---

### Scenario 3: 30th percentile - one_day - wt

- **Races analyzed**: 163
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.468 | 20.761 | 0.019 |
| selection_metric | 6.353 | 20.135 | 0.023 |
| kurtosis_normalized | 6.340 | 20.109 | 0.005 |
| clumpiness_score | 6.312 | 19.967 | 0.024 |
| biggest_group_metric | 6.290 | 19.880 | 0.045 |
| avg_group_size | 6.273 | 19.906 | 0.055 |
| std_deviation_absolute | 6.252 | 19.950 | 0.033 |
| 50th_percentile_gap | 6.223 | 19.761 | 0.059 |
| largest_group_size | 6.138 | 19.493 | 0.079 |
| total_race_duration | 6.109 | 19.374 | 0.020 |
| proportion_in_groups | 6.106 | 19.374 | 0.006 |
| total_finishers | 6.035 | 19.013 | 0.010 |
| std_group_size | 6.008 | 18.845 | 0.088 |
| gini_coefficient | 6.002 | 18.852 | 0.014 |
| total_groups | 5.981 | 18.957 | 0.041 |
| time_gap_evenness_metric | 5.792 | 18.279 | 0.013 |
| riders_in_groups | 5.784 | 18.294 | 0.015 |
| skewness_normalized | 5.747 | 17.969 | 0.005 |

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

### Scenario 4: 40th percentile - stage_one_day - wt

- **Races analyzed**: 2371
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.365 | 16.933 | 0.011 |
| biggest_group_metric | 5.352 | 16.784 | 0.054 |
| variance_absolute | 5.340 | 16.926 | 0.037 |
| avg_group_size | 5.324 | 16.690 | 0.102 |
| largest_group_position | 5.262 | 16.516 | 0.008 |
| selection_metric | 5.245 | 16.458 | 0.046 |
| proportion_in_groups | 5.241 | 16.456 | 0.045 |
| clumpiness_score | 5.227 | 16.322 | 0.021 |
| std_group_size | 5.207 | 16.256 | 0.038 |
| gini_coefficient | 5.165 | 16.108 | 0.082 |
| time_gap_evenness_metric | 5.153 | 16.211 | 0.030 |
| total_groups | 5.149 | 16.217 | 0.021 |
| riders_in_groups | 5.079 | 15.920 | 0.013 |
| variance_normalized | 5.066 | 17.254 | 0.026 |
| skewness_normalized | 4.679 | 14.466 | 0.013 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- kurtosis_normalized
- total_finishers

**High Correlation** (19 features):
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
- ... and 9 more

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

### Scenario 5: 40th percentile - stage - wt

- **Races analyzed**: 2163
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.288 | 16.649 | 0.010 |
| biggest_group_metric | 5.274 | 16.515 | 0.047 |
| variance_absolute | 5.256 | 16.600 | 0.055 |
| avg_group_size | 5.248 | 16.424 | 0.101 |
| largest_group_position | 5.187 | 16.259 | 0.009 |
| selection_metric | 5.183 | 16.240 | 0.047 |
| std_group_size | 5.143 | 16.034 | 0.047 |
| clumpiness_score | 5.130 | 15.997 | 0.025 |
| time_gap_evenness_metric | 5.086 | 15.962 | 0.035 |
| gini_coefficient | 5.083 | 15.844 | 0.075 |
| total_groups | 5.066 | 15.942 | 0.018 |
| riders_in_groups | 5.014 | 15.675 | 0.041 |
| variance_normalized | 4.994 | 16.945 | 0.024 |
| total_finishers | 4.928 | 15.236 | 0.007 |
| skewness_normalized | 4.593 | 14.176 | 0.015 |

#### Removed Features by Reason

**High Correlation** (20 features):
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
- ... and 10 more

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

**Low Score** (2 features):
- abandon_ratio
- kurtosis_normalized

---

### Scenario 6: 40th percentile - one_day - wt

- **Races analyzed**: 208
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.389 | 20.495 | 0.028 |
| biggest_group_metric | 6.370 | 20.144 | 0.024 |
| kurtosis_normalized | 6.341 | 20.157 | 0.011 |
| clumpiness_score | 6.322 | 19.991 | 0.027 |
| selection_metric | 6.242 | 19.788 | 0.013 |
| avg_group_size | 6.225 | 19.786 | 0.040 |
| 50th_percentile_gap | 6.169 | 19.530 | 0.065 |
| total_race_duration | 6.136 | 19.447 | 0.021 |
| std_group_size | 6.132 | 19.319 | 0.021 |
| gini_coefficient | 6.072 | 19.049 | 0.056 |
| total_finishers | 6.067 | 19.073 | 0.019 |
| largest_group_size | 6.054 | 19.234 | 0.049 |
| std_deviation_absolute | 6.035 | 19.164 | 0.017 |
| proportion_in_groups | 6.031 | 19.107 | 0.011 |
| riders_in_groups | 5.963 | 18.825 | 0.037 |
| total_groups | 5.956 | 18.904 | 0.009 |
| time_gap_evenness_metric | 5.870 | 18.529 | 0.012 |
| skewness_normalized | 5.832 | 18.350 | 0.018 |

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

### Scenario 7: 50th percentile - stage_one_day - wt

- **Races analyzed**: 2389
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.296 | 16.718 | 0.011 |
| biggest_group_metric | 5.294 | 16.574 | 0.088 |
| avg_group_size | 5.270 | 16.444 | 0.173 |
| variance_absolute | 5.256 | 16.666 | 0.023 |
| selection_metric | 5.185 | 16.273 | 0.033 |
| largest_group_size | 5.178 | 16.212 | 0.102 |
| clumpiness_score | 5.176 | 16.166 | 0.009 |
| proportion_in_groups | 5.164 | 16.243 | 0.015 |
| kurtosis_normalized | 5.141 | 16.220 | 0.005 |
| std_group_size | 5.120 | 15.989 | 0.026 |
| time_gap_evenness_metric | 5.086 | 15.952 | 0.072 |
| total_groups | 5.069 | 15.929 | 0.051 |
| variance_normalized | 4.999 | 17.034 | 0.028 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- gini_coefficient
- largest_group_position
- riders_in_groups
- skewness_absolute
- total_finishers

**High Correlation** (18 features):
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
- ... and 8 more

**Redundant** (17 features):
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
- ... and 7 more

---

### Scenario 8: 50th percentile - stage - wt

- **Races analyzed**: 2168
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.300 | 16.531 | 0.150 |
| winning_time | 5.288 | 16.655 | 0.010 |
| variance_absolute | 5.249 | 16.573 | 0.056 |
| avg_group_size | 5.224 | 16.407 | 0.057 |
| selection_metric | 5.187 | 16.304 | 0.016 |
| largest_group_position | 5.182 | 16.235 | 0.009 |
| largest_group_size | 5.154 | 16.176 | 0.044 |
| clumpiness_score | 5.147 | 16.052 | 0.031 |
| std_group_size | 5.119 | 15.978 | 0.034 |
| gini_coefficient | 5.084 | 15.813 | 0.084 |
| time_gap_evenness_metric | 5.067 | 15.928 | 0.013 |
| total_groups | 5.062 | 15.932 | 0.020 |
| riders_in_groups | 5.028 | 15.719 | 0.010 |
| variance_normalized | 5.005 | 16.951 | 0.052 |
| skewness_normalized | 4.525 | 13.893 | 0.028 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- kurtosis_normalized
- total_finishers

**High Correlation** (19 features):
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
- ... and 9 more

**Redundant** (17 features):
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
- ... and 7 more

---

### Scenario 9: 50th percentile - one_day - wt

- **Races analyzed**: 221
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.708 | 21.238 | 0.077 |
| variance_absolute | 6.695 | 21.408 | 0.019 |
| clumpiness_score | 6.665 | 21.146 | 0.015 |
| avg_group_size | 6.575 | 21.011 | 0.017 |
| largest_group_position | 6.559 | 20.814 | 0.010 |
| 50th_percentile_gap | 6.555 | 20.786 | 0.069 |
| kurtosis_absolute | 6.546 | 20.865 | 0.007 |
| selection_metric | 6.513 | 20.680 | 0.019 |
| total_race_duration | 6.474 | 20.534 | 0.021 |
| total_finishers | 6.459 | 20.322 | 0.011 |
| shannon_entropy_normalized | 6.438 | 20.498 | 0.015 |
| largest_group_size | 6.390 | 20.376 | 0.029 |
| gini_coefficient | 6.361 | 20.014 | 0.050 |
| shannon_entropy_absolute | 6.343 | 20.149 | 0.018 |
| proportion_in_groups | 6.337 | 20.095 | 0.009 |
| std_group_size | 6.326 | 19.993 | 0.020 |
| time_gap_evenness_metric | 6.242 | 19.766 | 0.006 |
| total_groups | 6.242 | 19.874 | 0.006 |
| skewness_absolute | 5.967 | 18.722 | 0.024 |

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

### Scenario 10: 60th percentile - stage_one_day - wt

- **Races analyzed**: 2396
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.410 | 16.886 | 0.146 |
| winning_time | 5.399 | 17.033 | 0.008 |
| variance_absolute | 5.367 | 16.984 | 0.036 |
| avg_group_size | 5.324 | 16.750 | 0.039 |
| largest_group_position | 5.314 | 16.641 | 0.011 |
| selection_metric | 5.294 | 16.640 | 0.006 |
| clumpiness_score | 5.277 | 16.463 | 0.042 |
| largest_group_size | 5.233 | 16.441 | 0.035 |
| std_group_size | 5.213 | 16.297 | 0.041 |
| gini_coefficient | 5.176 | 16.082 | 0.069 |
| time_gap_evenness_metric | 5.156 | 16.204 | 0.011 |
| riders_in_groups | 5.138 | 16.069 | 0.010 |
| total_groups | 5.130 | 16.148 | 0.009 |
| variance_normalized | 5.099 | 17.353 | 0.032 |
| skewness_absolute | 4.649 | 14.324 | 0.019 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
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
- ... and 7 more

---

### Scenario 11: 60th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.333 | 16.632 | 0.152 |
| winning_time | 5.317 | 16.757 | 0.006 |
| variance_absolute | 5.285 | 16.693 | 0.045 |
| avg_group_size | 5.245 | 16.473 | 0.053 |
| largest_group_position | 5.242 | 16.407 | 0.010 |
| selection_metric | 5.232 | 16.435 | 0.018 |
| clumpiness_score | 5.180 | 16.145 | 0.038 |
| largest_group_size | 5.158 | 16.196 | 0.031 |
| std_group_size | 5.141 | 16.073 | 0.026 |
| gini_coefficient | 5.107 | 15.867 | 0.062 |
| time_gap_evenness_metric | 5.087 | 15.978 | 0.013 |
| riders_in_groups | 5.075 | 15.875 | 0.006 |
| total_groups | 5.070 | 15.948 | 0.012 |
| variance_normalized | 5.034 | 17.055 | 0.038 |
| skewness_absolute | 4.546 | 13.981 | 0.023 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- kurtosis_absolute
- total_finishers

**High Correlation** (18 features):
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
- ... and 8 more

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
- included_finishers
- ... and 7 more

---

### Scenario 12: 60th percentile - one_day - wt

- **Races analyzed**: 224
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.877 | 21.868 | 0.018 |
| clumpiness_score | 6.753 | 21.407 | 0.012 |
| variance_absolute | 6.739 | 21.465 | 0.037 |
| 50th_percentile_gap | 6.700 | 21.296 | 0.044 |
| kurtosis_absolute | 6.688 | 21.363 | 0.019 |
| total_race_duration | 6.668 | 21.191 | 0.036 |
| avg_group_size | 6.611 | 21.170 | 0.019 |
| selection_metric | 6.558 | 20.850 | 0.010 |
| std_group_size | 6.514 | 20.705 | 0.012 |
| shannon_entropy_normalized | 6.504 | 20.668 | 0.082 |
| largest_group_size | 6.489 | 20.721 | 0.030 |
| gini_coefficient | 6.485 | 20.485 | 0.005 |
| total_groups | 6.424 | 20.454 | 0.010 |
| shannon_entropy_absolute | 6.253 | 19.831 | 0.042 |
| time_gap_evenness_metric | 6.173 | 19.529 | 0.010 |
| skewness_absolute | 6.120 | 19.231 | 0.029 |

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

### Scenario 13: 70th percentile - stage_one_day - wt

- **Races analyzed**: 2399
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.491 | 17.145 | 0.160 |
| winning_time | 5.477 | 17.302 | 0.005 |
| variance_absolute | 5.451 | 17.245 | 0.043 |
| largest_group_position | 5.400 | 16.915 | 0.015 |
| selection_metric | 5.392 | 16.947 | 0.011 |
| avg_group_size | 5.390 | 16.974 | 0.028 |
| proportion_in_groups | 5.364 | 16.898 | 0.006 |
| shannon_entropy_absolute | 5.349 | 16.857 | 0.016 |
| clumpiness_score | 5.349 | 16.709 | 0.022 |
| largest_group_size | 5.289 | 16.625 | 0.047 |
| std_group_size | 5.254 | 16.447 | 0.035 |
| gini_coefficient | 5.231 | 16.233 | 0.052 |
| time_gap_evenness_metric | 5.228 | 16.450 | 0.016 |
| riders_in_groups | 5.208 | 16.335 | 0.007 |
| total_groups | 5.185 | 16.308 | 0.007 |
| variance_normalized | 5.185 | 17.630 | 0.027 |
| total_finishers | 5.095 | 15.804 | 0.005 |
| skewness_absolute | 4.716 | 14.614 | 0.020 |

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

**Low Score** (2 features):
- abandon_ratio
- kurtosis_absolute

---

### Scenario 14: 70th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.349 | 16.692 | 0.156 |
| winning_time | 5.343 | 16.835 | 0.010 |
| variance_absolute | 5.310 | 16.774 | 0.037 |
| largest_group_position | 5.264 | 16.485 | 0.010 |
| selection_metric | 5.258 | 16.540 | 0.006 |
| avg_group_size | 5.245 | 16.489 | 0.044 |
| shannon_entropy_absolute | 5.216 | 16.433 | 0.014 |
| clumpiness_score | 5.193 | 16.201 | 0.024 |
| largest_group_size | 5.153 | 16.183 | 0.039 |
| std_group_size | 5.127 | 16.028 | 0.029 |
| gini_coefficient | 5.111 | 15.852 | 0.053 |
| riders_in_groups | 5.103 | 15.968 | 0.006 |
| time_gap_evenness_metric | 5.103 | 16.034 | 0.012 |
| total_groups | 5.062 | 15.921 | 0.010 |
| variance_normalized | 5.060 | 17.131 | 0.037 |
| skewness_absolute | 4.624 | 14.327 | 0.017 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- kurtosis_absolute
- total_finishers

**High Correlation** (18 features):
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
- ... and 8 more

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

### Scenario 15: 70th percentile - one_day - wt

- **Races analyzed**: 227
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.155 | 22.915 | 0.007 |
| biggest_group_metric | 7.104 | 22.606 | 0.027 |
| largest_group_position | 7.003 | 22.276 | 0.008 |
| 50th_percentile_gap | 6.922 | 21.996 | 0.057 |
| clumpiness_score | 6.914 | 21.914 | 0.006 |
| winning_time | 6.870 | 21.689 | 0.007 |
| avg_group_size | 6.841 | 21.876 | 0.063 |
| total_race_duration | 6.822 | 21.691 | 0.013 |
| variance_absolute | 6.790 | 21.601 | 0.010 |
| std_group_size | 6.747 | 21.424 | 0.035 |
| abandon_ratio | 6.663 | 21.059 | 0.005 |
| gini_coefficient | 6.657 | 21.034 | 0.022 |
| largest_group_size | 6.637 | 21.150 | 0.049 |
| shannon_entropy_normalized | 6.623 | 21.081 | 0.024 |
| selection_metric | 6.618 | 20.985 | 0.006 |
| total_groups | 6.583 | 20.930 | 0.028 |
| proportion_in_groups | 6.529 | 20.726 | 0.010 |
| shannon_entropy_absolute | 6.504 | 20.644 | 0.012 |
| skewness_absolute | 6.471 | 20.458 | 0.013 |
| time_gap_evenness_metric | 6.331 | 20.016 | 0.031 |

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

### Scenario 16: 80th percentile - stage_one_day - wt

- **Races analyzed**: 2401
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.533 | 17.264 | 0.191 |
| winning_time | 5.517 | 17.425 | 0.007 |
| variance_absolute | 5.479 | 17.355 | 0.018 |
| selection_metric | 5.438 | 17.076 | 0.041 |
| largest_group_position | 5.434 | 17.030 | 0.019 |
| proportion_in_groups | 5.422 | 17.066 | 0.010 |
| avg_group_size | 5.414 | 17.025 | 0.060 |
| kurtosis_normalized | 5.353 | 16.964 | 0.009 |
| clumpiness_score | 5.340 | 16.692 | 0.005 |
| shannon_entropy_absolute | 5.325 | 16.740 | 0.051 |
| largest_group_size | 5.301 | 16.679 | 0.024 |
| std_group_size | 5.274 | 16.536 | 0.029 |
| time_gap_evenness_metric | 5.260 | 16.543 | 0.016 |
| variance_normalized | 5.221 | 17.766 | 0.013 |
| gini_coefficient | 5.216 | 16.244 | 0.013 |
| total_groups | 5.186 | 16.311 | 0.010 |
| skewness_normalized | 4.839 | 15.131 | 0.008 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- riders_in_groups
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

### Scenario 17: 80th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.450 | 17.024 | 0.158 |
| winning_time | 5.446 | 17.176 | 0.043 |
| variance_absolute | 5.391 | 17.082 | 0.013 |
| selection_metric | 5.361 | 16.864 | 0.008 |
| avg_group_size | 5.325 | 16.752 | 0.062 |
| shannon_entropy_absolute | 5.250 | 16.522 | 0.029 |
| clumpiness_score | 5.244 | 16.392 | 0.010 |
| largest_group_size | 5.240 | 16.435 | 0.084 |
| riders_in_groups | 5.217 | 16.323 | 0.052 |
| std_group_size | 5.212 | 16.315 | 0.045 |
| time_gap_evenness_metric | 5.190 | 16.332 | 0.019 |
| gini_coefficient | 5.164 | 16.052 | 0.007 |
| variance_normalized | 5.161 | 17.483 | 0.019 |
| total_groups | 5.131 | 16.081 | 0.063 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
- skewness_normalized
- total_finishers

**High Correlation** (18 features):
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
- ... and 8 more

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

### Scenario 18: 80th percentile - one_day - wt

- **Races analyzed**: 229
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.147 | 22.938 | 0.005 |
| biggest_group_metric | 7.121 | 22.641 | 0.032 |
| largest_group_position | 6.996 | 22.225 | 0.013 |
| 50th_percentile_gap | 6.925 | 21.970 | 0.071 |
| clumpiness_score | 6.918 | 21.926 | 0.007 |
| avg_group_size | 6.905 | 22.157 | 0.009 |
| winning_time | 6.872 | 21.691 | 0.010 |
| total_finishers | 6.813 | 21.469 | 0.069 |
| abandon_ratio | 6.779 | 21.434 | 0.011 |
| shannon_entropy_normalized | 6.769 | 21.557 | 0.012 |
| std_group_size | 6.720 | 21.322 | 0.006 |
| variance_absolute | 6.697 | 21.241 | 0.024 |
| gini_coefficient | 6.602 | 20.834 | 0.030 |
| total_groups | 6.577 | 20.911 | 0.018 |
| proportion_in_groups | 6.570 | 20.869 | 0.006 |
| skewness_absolute | 6.546 | 20.785 | 0.014 |
| largest_group_size | 6.522 | 20.790 | 0.015 |
| selection_metric | 6.433 | 20.358 | 0.005 |
| time_gap_evenness_metric | 6.391 | 20.229 | 0.008 |

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

