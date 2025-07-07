# Feature Selection Exploration Report

Generated: 2025-07-07 10:38:44

## Executive Summary

- **Total scenarios analyzed**: 36
- **Max features per scenario**: 20
- **Total races analyzed**: 53,844
- **Average features selected**: 16.4

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| variance_absolute | 36 | 100.0% |
| avg_group_size | 36 | 100.0% |
| clumpiness_score | 36 | 100.0% |
| total_groups | 36 | 100.0% |
| biggest_group_metric | 35 | 97.2% |
| gini_coefficient | 35 | 97.2% |
| selection_metric | 33 | 91.7% |
| time_gap_evenness_metric | 32 | 88.9% |
| std_group_size | 32 | 88.9% |
| largest_group_size | 25 | 69.4% |
| variance_normalized | 24 | 66.7% |
| total_race_duration | 23 | 63.9% |
| riders_in_groups | 21 | 58.3% |
| skewness_normalized | 20 | 55.6% |
| 50th_percentile_gap | 20 | 55.6% |

### Feature Removal Patterns

- **High correlation removals**: 577 (avg 16.0 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 518 (avg 14.4 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage_one_day - wt

- **Races analyzed**: 2283
- **Features available**: 37
- **Features selected**: 10

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.421 | 16.948 | 0.104 |
| variance_absolute | 5.399 | 17.076 | 0.064 |
| avg_group_size | 5.384 | 16.860 | 0.130 |
| clumpiness_score | 5.249 | 16.415 | 0.013 |
| time_gap_evenness_metric | 5.229 | 16.440 | 0.023 |
| total_groups | 5.218 | 16.471 | 0.026 |
| kurtosis_normalized | 5.216 | 16.445 | 0.009 |
| gini_coefficient | 5.185 | 16.293 | 0.013 |
| variance_normalized | 5.112 | 17.413 | 0.022 |
| skewness_normalized | 4.744 | 14.721 | 0.037 |

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

### Scenario 2: 30th percentile - stage_one_day - pro

- **Races analyzed**: 1839
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.950 | 18.809 | 0.033 |
| avg_group_size | 5.891 | 18.554 | 0.131 |
| clumpiness_score | 5.836 | 18.373 | 0.019 |
| selection_metric | 5.828 | 18.491 | 0.060 |
| std_group_size | 5.804 | 18.303 | 0.027 |
| gini_coefficient | 5.789 | 18.326 | 0.055 |
| variance_absolute | 5.704 | 19.255 | 0.029 |
| total_groups | 5.670 | 17.956 | 0.044 |
| 50th_percentile_gap | 5.623 | 17.840 | 0.025 |
| total_race_duration | 5.567 | 17.657 | 0.037 |
| riders_in_groups | 5.529 | 17.455 | 0.006 |
| std_deviation_normalized | 5.520 | 17.749 | 0.024 |
| skewness_normalized | 5.228 | 16.316 | 0.005 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
- total_finishers
- winning_time

**High Correlation** (19 features):
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
- ... and 9 more

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

---

### Scenario 3: 30th percentile - stage - wt

- **Races analyzed**: 2120
- **Features available**: 37
- **Features selected**: 10

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.362 | 16.774 | 0.089 |
| variance_absolute | 5.341 | 16.875 | 0.068 |
| avg_group_size | 5.325 | 16.670 | 0.123 |
| clumpiness_score | 5.193 | 16.239 | 0.006 |
| time_gap_evenness_metric | 5.187 | 16.288 | 0.043 |
| kurtosis_absolute | 5.168 | 16.293 | 0.014 |
| total_groups | 5.151 | 16.252 | 0.026 |
| gini_coefficient | 5.130 | 16.120 | 0.016 |
| variance_normalized | 5.066 | 17.206 | 0.023 |
| skewness_absolute | 4.697 | 14.589 | 0.028 |

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

### Scenario 4: 30th percentile - stage - pro

- **Races analyzed**: 1666
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| avg_group_size | 6.013 | 18.965 | 0.076 |
| selection_metric | 5.944 | 18.827 | 0.062 |
| clumpiness_score | 5.923 | 18.622 | 0.028 |
| std_group_size | 5.904 | 18.653 | 0.010 |
| gini_coefficient | 5.896 | 18.664 | 0.048 |
| abandon_ratio | 5.860 | 18.312 | 0.008 |
| variance_absolute | 5.828 | 19.599 | 0.030 |
| total_groups | 5.808 | 18.391 | 0.022 |
| total_finishers | 5.724 | 17.845 | 0.062 |
| 50th_percentile_gap | 5.722 | 18.141 | 0.016 |
| total_race_duration | 5.675 | 17.996 | 0.024 |
| riders_in_groups | 5.664 | 17.833 | 0.066 |
| std_deviation_normalized | 5.612 | 18.023 | 0.016 |
| skewness_normalized | 5.326 | 16.637 | 0.010 |

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
- 5th_percentile_gap
- biggest_group_metric
- ... and 10 more

**Redundant** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- biggest_group_metric
- included_finishers
- ... and 6 more

**Low Score** (3 features):
- kurtosis_normalized
- largest_group_position
- winning_time

---

### Scenario 5: 30th percentile - one_day - wt

- **Races analyzed**: 163
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.475 | 20.785 | 0.019 |
| selection_metric | 6.360 | 20.160 | 0.023 |
| kurtosis_normalized | 6.351 | 20.145 | 0.005 |
| clumpiness_score | 6.309 | 19.957 | 0.024 |
| biggest_group_metric | 6.298 | 19.904 | 0.045 |
| avg_group_size | 6.262 | 19.869 | 0.055 |
| std_deviation_absolute | 6.261 | 19.978 | 0.033 |
| 50th_percentile_gap | 6.224 | 19.765 | 0.059 |
| largest_group_size | 6.145 | 19.517 | 0.079 |
| total_race_duration | 6.121 | 19.412 | 0.020 |
| proportion_in_groups | 6.113 | 19.398 | 0.006 |
| total_groups | 6.042 | 19.161 | 0.041 |
| total_finishers | 6.037 | 19.019 | 0.010 |
| std_group_size | 6.011 | 18.856 | 0.088 |
| gini_coefficient | 6.007 | 18.868 | 0.014 |
| time_gap_evenness_metric | 5.810 | 18.339 | 0.013 |
| riders_in_groups | 5.809 | 18.376 | 0.015 |
| skewness_normalized | 5.746 | 17.966 | 0.005 |

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

### Scenario 6: 30th percentile - one_day - pro

- **Races analyzed**: 173
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.815 | 18.267 | 0.051 |
| selection_metric | 5.794 | 18.300 | 0.034 |
| variance_absolute | 5.790 | 18.551 | 0.037 |
| biggest_group_metric | 5.744 | 18.053 | 0.101 |
| largest_group_position | 5.640 | 17.819 | 0.046 |
| gini_coefficient | 5.638 | 17.677 | 0.043 |
| avg_group_size | 5.624 | 17.757 | 0.054 |
| std_group_size | 5.595 | 17.530 | 0.037 |
| 50th_percentile_gap | 5.574 | 17.707 | 0.097 |
| total_finishers | 5.555 | 17.475 | 0.009 |
| time_gap_evenness_metric | 5.528 | 17.492 | 0.010 |
| std_deviation_normalized | 5.514 | 17.435 | 0.019 |
| total_groups | 5.465 | 17.256 | 0.055 |
| largest_group_size | 5.418 | 17.149 | 0.006 |
| total_race_duration | 5.383 | 17.079 | 0.022 |
| riders_in_groups | 5.344 | 16.861 | 0.017 |
| skewness_normalized | 5.206 | 16.226 | 0.024 |

#### Removed Features by Reason

**High Correlation** (13 features):
- 10th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- shannon_entropy_normalized
- ... and 3 more

**Redundant** (13 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 3 more

**Low Score** (4 features):
- abandon_ratio
- kurtosis_normalized
- proportion_in_groups
- winning_time

---

### Scenario 7: 40th percentile - stage_one_day - wt

- **Races analyzed**: 2371
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.367 | 16.938 | 0.011 |
| biggest_group_metric | 5.352 | 16.784 | 0.054 |
| variance_absolute | 5.333 | 16.902 | 0.037 |
| avg_group_size | 5.325 | 16.691 | 0.102 |
| largest_group_position | 5.262 | 16.516 | 0.008 |
| selection_metric | 5.245 | 16.457 | 0.046 |
| proportion_in_groups | 5.241 | 16.456 | 0.045 |
| clumpiness_score | 5.228 | 16.324 | 0.021 |
| std_group_size | 5.207 | 16.255 | 0.038 |
| gini_coefficient | 5.165 | 16.109 | 0.082 |
| time_gap_evenness_metric | 5.153 | 16.210 | 0.030 |
| total_groups | 5.146 | 16.207 | 0.021 |
| riders_in_groups | 5.078 | 15.917 | 0.013 |
| variance_normalized | 5.066 | 17.254 | 0.026 |
| skewness_normalized | 4.680 | 14.469 | 0.013 |

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

### Scenario 8: 40th percentile - stage_one_day - pro

- **Races analyzed**: 2101
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.108 | 19.366 | 0.026 |
| clumpiness_score | 6.071 | 19.083 | 0.065 |
| avg_group_size | 6.053 | 19.184 | 0.071 |
| proportion_in_groups | 6.012 | 19.080 | 0.021 |
| selection_metric | 6.005 | 19.035 | 0.095 |
| gini_coefficient | 5.962 | 18.844 | 0.062 |
| time_gap_evenness_metric | 5.942 | 18.927 | 0.010 |
| variance_absolute | 5.876 | 19.897 | 0.034 |
| total_groups | 5.833 | 18.508 | 0.041 |
| riders_in_groups | 5.747 | 18.185 | 0.010 |
| total_race_duration | 5.724 | 18.198 | 0.030 |
| 50th_percentile_gap | 5.604 | 17.832 | 0.017 |
| std_deviation_normalized | 5.550 | 17.682 | 0.020 |
| skewness_absolute | 5.396 | 16.875 | 0.007 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- largest_group_position
- std_group_size
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

### Scenario 9: 40th percentile - stage - wt

- **Races analyzed**: 2163
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.317 | 16.745 | 0.010 |
| biggest_group_metric | 5.302 | 16.607 | 0.047 |
| avg_group_size | 5.280 | 16.529 | 0.101 |
| variance_absolute | 5.272 | 16.655 | 0.055 |
| largest_group_position | 5.214 | 16.351 | 0.009 |
| selection_metric | 5.208 | 16.323 | 0.047 |
| std_group_size | 5.170 | 16.124 | 0.047 |
| clumpiness_score | 5.157 | 16.087 | 0.025 |
| total_groups | 5.126 | 16.142 | 0.018 |
| time_gap_evenness_metric | 5.112 | 16.048 | 0.035 |
| gini_coefficient | 5.109 | 15.932 | 0.075 |
| riders_in_groups | 5.042 | 15.770 | 0.041 |
| variance_normalized | 5.022 | 17.040 | 0.024 |
| total_finishers | 4.950 | 15.310 | 0.007 |
| skewness_normalized | 4.616 | 14.252 | 0.015 |

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

### Scenario 10: 40th percentile - stage - pro

- **Races analyzed**: 1850
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.049 | 19.149 | 0.028 |
| avg_group_size | 5.983 | 18.957 | 0.053 |
| clumpiness_score | 5.956 | 18.772 | 0.013 |
| selection_metric | 5.922 | 18.813 | 0.044 |
| time_gap_evenness_metric | 5.902 | 18.754 | 0.024 |
| std_group_size | 5.899 | 18.602 | 0.020 |
| gini_coefficient | 5.898 | 18.651 | 0.077 |
| variance_absolute | 5.832 | 19.630 | 0.065 |
| total_groups | 5.770 | 18.313 | 0.017 |
| riders_in_groups | 5.700 | 18.010 | 0.007 |
| total_race_duration | 5.682 | 18.026 | 0.037 |
| 50th_percentile_gap | 5.553 | 17.611 | 0.043 |
| std_deviation_normalized | 5.478 | 17.435 | 0.023 |
| skewness_normalized | 5.314 | 16.605 | 0.010 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
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
- kurtosis_absolute
- ... and 5 more

---

### Scenario 11: 40th percentile - one_day - wt

- **Races analyzed**: 208
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.457 | 20.722 | 0.028 |
| biggest_group_metric | 6.438 | 20.371 | 0.024 |
| kurtosis_normalized | 6.422 | 20.426 | 0.011 |
| clumpiness_score | 6.381 | 20.185 | 0.027 |
| selection_metric | 6.309 | 20.011 | 0.013 |
| avg_group_size | 6.288 | 19.995 | 0.040 |
| 50th_percentile_gap | 6.240 | 19.768 | 0.065 |
| total_race_duration | 6.204 | 19.671 | 0.021 |
| std_group_size | 6.198 | 19.537 | 0.021 |
| gini_coefficient | 6.133 | 19.254 | 0.056 |
| total_finishers | 6.132 | 19.290 | 0.019 |
| largest_group_size | 6.123 | 19.463 | 0.049 |
| std_deviation_absolute | 6.100 | 19.382 | 0.017 |
| proportion_in_groups | 6.095 | 19.318 | 0.011 |
| total_groups | 5.976 | 18.971 | 0.009 |
| riders_in_groups | 5.944 | 18.760 | 0.037 |
| time_gap_evenness_metric | 5.936 | 18.748 | 0.012 |
| skewness_normalized | 5.886 | 18.530 | 0.018 |

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

### Scenario 12: 40th percentile - one_day - pro

- **Races analyzed**: 251
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.655 | 21.073 | 0.010 |
| variance_absolute | 6.614 | 21.339 | 0.011 |
| biggest_group_metric | 6.609 | 20.952 | 0.044 |
| selection_metric | 6.531 | 20.675 | 0.090 |
| kurtosis_absolute | 6.513 | 20.711 | 0.010 |
| variance_normalized | 6.505 | 20.815 | 0.011 |
| shannon_entropy_absolute | 6.502 | 20.641 | 0.064 |
| gini_coefficient | 6.421 | 20.230 | 0.018 |
| proportion_in_groups | 6.405 | 20.389 | 0.012 |
| std_group_size | 6.394 | 20.207 | 0.019 |
| 10th_percentile_gap | 6.380 | 20.377 | 0.020 |
| 50th_percentile_gap | 6.378 | 20.373 | 0.068 |
| avg_group_size | 6.377 | 20.288 | 0.029 |
| total_groups | 6.325 | 20.142 | 0.020 |
| largest_group_size | 6.268 | 19.969 | 0.017 |
| time_gap_evenness_metric | 6.254 | 19.858 | 0.037 |
| std_deviation_normalized | 6.228 | 19.801 | 0.028 |
| riders_in_groups | 6.189 | 19.613 | 0.007 |
| total_race_duration | 6.160 | 19.664 | 0.020 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- largest_group_position
- skewness_absolute
- total_finishers
- winning_time

**High Correlation** (10 features):
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- skewness_normalized
- std_deviation_absolute

**Redundant** (12 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- shannon_entropy_normalized
- ... and 2 more

---

### Scenario 13: 50th percentile - stage_one_day - wt

- **Races analyzed**: 2389
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| winning_time | 5.328 | 16.824 | 0.011 |
| biggest_group_metric | 5.326 | 16.682 | 0.088 |
| avg_group_size | 5.311 | 16.581 | 0.173 |
| variance_absolute | 5.285 | 16.761 | 0.023 |
| selection_metric | 5.211 | 16.361 | 0.033 |
| clumpiness_score | 5.210 | 16.279 | 0.009 |
| largest_group_size | 5.210 | 16.318 | 0.102 |
| proportion_in_groups | 5.196 | 16.348 | 0.015 |
| kurtosis_normalized | 5.158 | 16.279 | 0.005 |
| std_group_size | 5.151 | 16.093 | 0.026 |
| time_gap_evenness_metric | 5.117 | 16.056 | 0.072 |
| total_groups | 5.103 | 16.041 | 0.051 |
| variance_normalized | 5.032 | 17.144 | 0.028 |

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

### Scenario 14: 50th percentile - stage_one_day - pro

- **Races analyzed**: 2161
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.141 | 19.394 | 0.054 |
| clumpiness_score | 6.098 | 19.199 | 0.013 |
| avg_group_size | 6.065 | 19.209 | 0.031 |
| proportion_in_groups | 6.043 | 19.143 | 0.015 |
| selection_metric | 6.002 | 19.022 | 0.034 |
| gini_coefficient | 5.985 | 18.841 | 0.070 |
| std_group_size | 5.965 | 18.799 | 0.013 |
| time_gap_evenness_metric | 5.962 | 18.896 | 0.034 |
| variance_absolute | 5.888 | 19.968 | 0.056 |
| total_groups | 5.870 | 18.599 | 0.016 |
| total_race_duration | 5.750 | 18.241 | 0.036 |
| std_deviation_absolute | 5.730 | 18.836 | 0.054 |
| 50th_percentile_gap | 5.723 | 18.195 | 0.018 |
| 5th_percentile_gap | 5.719 | 18.172 | 0.008 |
| variance_normalized | 5.692 | 18.791 | 0.045 |
| std_deviation_normalized | 5.543 | 17.568 | 0.029 |
| skewness_normalized | 5.272 | 16.411 | 0.013 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
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
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 3 more

---

### Scenario 15: 50th percentile - stage - wt

- **Races analyzed**: 2168
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.268 | 16.422 | 0.150 |
| winning_time | 5.256 | 16.548 | 0.010 |
| variance_absolute | 5.220 | 16.476 | 0.056 |
| avg_group_size | 5.200 | 16.328 | 0.057 |
| selection_metric | 5.156 | 16.198 | 0.016 |
| largest_group_position | 5.151 | 16.133 | 0.009 |
| largest_group_size | 5.122 | 16.072 | 0.044 |
| clumpiness_score | 5.116 | 15.948 | 0.031 |
| std_group_size | 5.087 | 15.872 | 0.034 |
| gini_coefficient | 5.053 | 15.709 | 0.084 |
| time_gap_evenness_metric | 5.036 | 15.824 | 0.013 |
| total_groups | 5.033 | 15.836 | 0.020 |
| riders_in_groups | 4.998 | 15.622 | 0.010 |
| variance_normalized | 4.972 | 16.839 | 0.052 |
| skewness_normalized | 4.512 | 13.849 | 0.028 |

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

### Scenario 16: 50th percentile - stage - pro

- **Races analyzed**: 1877
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.076 | 19.203 | 0.043 |
| clumpiness_score | 6.015 | 18.938 | 0.012 |
| avg_group_size | 6.011 | 19.021 | 0.040 |
| selection_metric | 5.962 | 18.906 | 0.033 |
| gini_coefficient | 5.937 | 18.698 | 0.071 |
| time_gap_evenness_metric | 5.917 | 18.748 | 0.027 |
| std_group_size | 5.914 | 18.630 | 0.014 |
| largest_group_position | 5.880 | 18.599 | 0.006 |
| variance_absolute | 5.845 | 19.717 | 0.061 |
| total_groups | 5.818 | 18.435 | 0.023 |
| total_race_duration | 5.707 | 18.076 | 0.040 |
| std_deviation_absolute | 5.690 | 18.652 | 0.056 |
| 50th_percentile_gap | 5.676 | 18.010 | 0.029 |
| 5th_percentile_gap | 5.655 | 17.950 | 0.006 |
| variance_normalized | 5.637 | 18.560 | 0.045 |
| std_deviation_normalized | 5.490 | 17.412 | 0.026 |
| skewness_normalized | 5.343 | 16.647 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
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
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 3 more

---

### Scenario 17: 50th percentile - one_day - wt

- **Races analyzed**: 221
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.650 | 21.043 | 0.077 |
| variance_absolute | 6.636 | 21.212 | 0.019 |
| clumpiness_score | 6.607 | 20.952 | 0.015 |
| avg_group_size | 6.526 | 20.848 | 0.017 |
| largest_group_position | 6.496 | 20.605 | 0.010 |
| 50th_percentile_gap | 6.492 | 20.577 | 0.069 |
| kurtosis_absolute | 6.488 | 20.671 | 0.007 |
| selection_metric | 6.456 | 20.490 | 0.019 |
| total_race_duration | 6.409 | 20.317 | 0.021 |
| total_finishers | 6.404 | 20.138 | 0.011 |
| shannon_entropy_normalized | 6.385 | 20.322 | 0.015 |
| largest_group_size | 6.323 | 20.154 | 0.029 |
| gini_coefficient | 6.307 | 19.835 | 0.050 |
| proportion_in_groups | 6.300 | 19.972 | 0.009 |
| shannon_entropy_absolute | 6.288 | 19.964 | 0.018 |
| std_group_size | 6.259 | 19.772 | 0.020 |
| total_groups | 6.203 | 19.746 | 0.006 |
| time_gap_evenness_metric | 6.188 | 19.585 | 0.006 |
| skewness_absolute | 5.883 | 18.443 | 0.024 |

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

### Scenario 18: 50th percentile - one_day - pro

- **Races analyzed**: 284
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 7.108 | 22.537 | 0.045 |
| biggest_group_metric | 7.055 | 22.410 | 0.039 |
| kurtosis_normalized | 6.946 | 22.218 | 0.006 |
| variance_absolute | 6.942 | 22.336 | 0.019 |
| proportion_in_groups | 6.885 | 21.947 | 0.015 |
| shannon_entropy_absolute | 6.861 | 21.865 | 0.017 |
| variance_normalized | 6.826 | 21.863 | 0.026 |
| total_finishers | 6.815 | 21.547 | 0.008 |
| std_group_size | 6.810 | 21.601 | 0.020 |
| avg_group_size | 6.778 | 21.637 | 0.018 |
| gini_coefficient | 6.755 | 21.345 | 0.039 |
| total_groups | 6.714 | 21.431 | 0.013 |
| largest_group_size | 6.713 | 21.418 | 0.028 |
| selection_metric | 6.699 | 21.286 | 0.027 |
| 50th_percentile_gap | 6.633 | 21.138 | 0.071 |
| time_gap_evenness_metric | 6.590 | 20.960 | 0.016 |
| total_race_duration | 6.521 | 20.774 | 0.024 |
| skewness_normalized | 6.036 | 18.943 | 0.025 |

#### Removed Features by Reason

**High Correlation** (14 features):
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
- ... and 4 more

**Redundant** (11 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- skewness_absolute
- ... and 1 more

**Low Score** (3 features):
- abandon_ratio
- largest_group_position
- winning_time

---

### Scenario 19: 60th percentile - stage_one_day - wt

- **Races analyzed**: 2396
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.395 | 16.836 | 0.146 |
| winning_time | 5.380 | 16.970 | 0.008 |
| variance_absolute | 5.352 | 16.934 | 0.036 |
| avg_group_size | 5.307 | 16.694 | 0.039 |
| largest_group_position | 5.299 | 16.593 | 0.011 |
| selection_metric | 5.279 | 16.591 | 0.006 |
| clumpiness_score | 5.266 | 16.425 | 0.042 |
| largest_group_size | 5.219 | 16.393 | 0.035 |
| std_group_size | 5.198 | 16.244 | 0.041 |
| gini_coefficient | 5.162 | 16.035 | 0.069 |
| time_gap_evenness_metric | 5.142 | 16.155 | 0.011 |
| riders_in_groups | 5.123 | 16.020 | 0.010 |
| total_groups | 5.120 | 16.114 | 0.009 |
| variance_normalized | 5.084 | 17.302 | 0.032 |
| skewness_absolute | 4.637 | 14.282 | 0.019 |

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

### Scenario 20: 60th percentile - stage_one_day - pro

- **Races analyzed**: 2182
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.183 | 19.553 | 0.052 |
| clumpiness_score | 6.157 | 19.386 | 0.017 |
| avg_group_size | 6.102 | 19.331 | 0.040 |
| proportion_in_groups | 6.089 | 19.280 | 0.015 |
| selection_metric | 6.066 | 19.235 | 0.019 |
| largest_group_position | 6.040 | 19.102 | 0.007 |
| gini_coefficient | 6.039 | 18.990 | 0.062 |
| std_group_size | 6.016 | 18.978 | 0.012 |
| largest_group_size | 5.997 | 18.992 | 0.015 |
| time_gap_evenness_metric | 5.987 | 18.981 | 0.019 |
| kurtosis_normalized | 5.955 | 18.912 | 0.005 |
| variance_absolute | 5.941 | 20.120 | 0.051 |
| total_groups | 5.903 | 18.714 | 0.019 |
| 50th_percentile_gap | 5.800 | 18.403 | 0.049 |
| total_race_duration | 5.798 | 18.371 | 0.037 |
| std_deviation_absolute | 5.718 | 18.560 | 0.048 |
| std_deviation_normalized | 5.668 | 17.938 | 0.027 |
| variance_normalized | 5.617 | 18.223 | 0.048 |
| skewness_normalized | 5.436 | 16.934 | 0.016 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- riders_in_groups
- total_finishers
- winning_time

**High Correlation** (13 features):
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
- ... and 3 more

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
- kurtosis_absolute
- ... and 3 more

---

### Scenario 21: 60th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.316 | 16.574 | 0.152 |
| winning_time | 5.300 | 16.700 | 0.006 |
| variance_absolute | 5.277 | 16.667 | 0.045 |
| largest_group_position | 5.225 | 16.349 | 0.010 |
| avg_group_size | 5.224 | 16.404 | 0.053 |
| selection_metric | 5.215 | 16.378 | 0.018 |
| clumpiness_score | 5.169 | 16.110 | 0.038 |
| largest_group_size | 5.142 | 16.144 | 0.031 |
| std_group_size | 5.123 | 16.014 | 0.026 |
| gini_coefficient | 5.090 | 15.812 | 0.062 |
| time_gap_evenness_metric | 5.071 | 15.923 | 0.013 |
| riders_in_groups | 5.058 | 15.819 | 0.006 |
| total_groups | 5.044 | 15.863 | 0.012 |
| variance_normalized | 5.017 | 16.996 | 0.038 |
| skewness_absolute | 4.574 | 14.073 | 0.023 |

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

### Scenario 22: 60th percentile - stage - pro

- **Races analyzed**: 1881
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.025 | 19.039 | 0.048 |
| clumpiness_score | 5.992 | 18.848 | 0.014 |
| avg_group_size | 5.964 | 18.879 | 0.039 |
| selection_metric | 5.948 | 18.849 | 0.022 |
| largest_group_position | 5.902 | 18.647 | 0.007 |
| gini_coefficient | 5.892 | 18.526 | 0.063 |
| std_group_size | 5.889 | 18.549 | 0.018 |
| time_gap_evenness_metric | 5.857 | 18.552 | 0.020 |
| variance_absolute | 5.800 | 19.554 | 0.053 |
| total_groups | 5.769 | 18.267 | 0.020 |
| riders_in_groups | 5.713 | 17.983 | 0.007 |
| total_race_duration | 5.669 | 17.936 | 0.043 |
| 50th_percentile_gap | 5.659 | 17.924 | 0.061 |
| std_deviation_absolute | 5.585 | 18.102 | 0.051 |
| std_deviation_normalized | 5.523 | 17.474 | 0.023 |
| variance_normalized | 5.460 | 17.687 | 0.048 |
| skewness_absolute | 5.300 | 16.491 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
- 5th_percentile_gap
- abandon_ratio
- kurtosis_absolute
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
- kurtosis_normalized
- ... and 5 more

**Redundant** (13 features):
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
- ... and 3 more

---

### Scenario 23: 60th percentile - one_day - wt

- **Races analyzed**: 224
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.862 | 21.817 | 0.018 |
| clumpiness_score | 6.744 | 21.375 | 0.012 |
| variance_absolute | 6.727 | 21.426 | 0.037 |
| 50th_percentile_gap | 6.723 | 21.373 | 0.044 |
| kurtosis_absolute | 6.681 | 21.338 | 0.019 |
| total_race_duration | 6.656 | 21.152 | 0.036 |
| avg_group_size | 6.603 | 21.145 | 0.019 |
| selection_metric | 6.547 | 20.813 | 0.010 |
| std_group_size | 6.503 | 20.667 | 0.012 |
| shannon_entropy_normalized | 6.497 | 20.648 | 0.082 |
| largest_group_size | 6.486 | 20.710 | 0.030 |
| gini_coefficient | 6.473 | 20.445 | 0.005 |
| total_groups | 6.418 | 20.432 | 0.010 |
| shannon_entropy_absolute | 6.225 | 19.740 | 0.042 |
| time_gap_evenness_metric | 6.143 | 19.431 | 0.010 |
| skewness_absolute | 6.058 | 19.023 | 0.029 |

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

### Scenario 24: 60th percentile - one_day - pro

- **Races analyzed**: 301
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.366 | 23.408 | 0.061 |
| clumpiness_score | 7.290 | 23.133 | 0.031 |
| proportion_in_groups | 7.134 | 22.739 | 0.032 |
| variance_absolute | 7.111 | 22.895 | 0.014 |
| variance_normalized | 7.037 | 22.528 | 0.025 |
| avg_group_size | 7.027 | 22.422 | 0.066 |
| abandon_ratio | 7.019 | 22.207 | 0.005 |
| total_finishers | 7.001 | 22.173 | 0.005 |
| gini_coefficient | 6.976 | 22.099 | 0.013 |
| std_group_size | 6.974 | 22.174 | 0.020 |
| shannon_entropy_absolute | 6.968 | 22.156 | 0.039 |
| largest_group_size | 6.910 | 22.035 | 0.042 |
| total_groups | 6.862 | 21.876 | 0.021 |
| selection_metric | 6.834 | 21.731 | 0.010 |
| 50th_percentile_gap | 6.809 | 21.696 | 0.075 |
| total_race_duration | 6.773 | 21.589 | 0.032 |
| skewness_normalized | 6.294 | 19.838 | 0.006 |

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
- riders_in_groups
- ... and 4 more

**Redundant** (12 features):
- 10th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- shannon_entropy_normalized
- ... and 2 more

**Low Score** (3 features):
- kurtosis_normalized
- largest_group_position
- winning_time

---

### Scenario 25: 70th percentile - stage_one_day - wt

- **Races analyzed**: 2399
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.444 | 16.987 | 0.160 |
| winning_time | 5.430 | 17.145 | 0.005 |
| variance_absolute | 5.407 | 17.100 | 0.043 |
| largest_group_position | 5.354 | 16.761 | 0.015 |
| selection_metric | 5.345 | 16.791 | 0.011 |
| avg_group_size | 5.344 | 16.822 | 0.028 |
| proportion_in_groups | 5.318 | 16.743 | 0.006 |
| shannon_entropy_absolute | 5.303 | 16.702 | 0.016 |
| clumpiness_score | 5.295 | 16.528 | 0.022 |
| largest_group_size | 5.243 | 16.471 | 0.047 |
| std_group_size | 5.209 | 16.297 | 0.035 |
| gini_coefficient | 5.186 | 16.084 | 0.052 |
| time_gap_evenness_metric | 5.183 | 16.298 | 0.016 |
| riders_in_groups | 5.164 | 16.186 | 0.007 |
| total_groups | 5.138 | 16.150 | 0.007 |
| variance_normalized | 5.136 | 17.467 | 0.027 |
| total_finishers | 5.036 | 15.606 | 0.005 |
| skewness_absolute | 4.659 | 14.424 | 0.020 |

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

### Scenario 26: 70th percentile - stage_one_day - pro

- **Races analyzed**: 2194
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.279 | 19.863 | 0.058 |
| clumpiness_score | 6.266 | 19.736 | 0.015 |
| avg_group_size | 6.198 | 19.679 | 0.017 |
| proportion_in_groups | 6.188 | 19.612 | 0.017 |
| largest_group_position | 6.160 | 19.466 | 0.011 |
| gini_coefficient | 6.121 | 19.219 | 0.062 |
| kurtosis_normalized | 6.116 | 19.457 | 0.006 |
| std_group_size | 6.087 | 19.215 | 0.020 |
| largest_group_size | 6.069 | 19.241 | 0.018 |
| time_gap_evenness_metric | 6.059 | 19.211 | 0.020 |
| variance_absolute | 6.038 | 20.405 | 0.050 |
| selection_metric | 5.981 | 18.939 | 0.017 |
| riders_in_groups | 5.960 | 18.800 | 0.008 |
| total_groups | 5.945 | 18.852 | 0.009 |
| total_race_duration | 5.858 | 18.552 | 0.040 |
| std_deviation_normalized | 5.852 | 18.509 | 0.032 |
| std_deviation_absolute | 5.755 | 18.521 | 0.041 |
| variance_normalized | 5.662 | 18.136 | 0.037 |
| skewness_normalized | 5.473 | 17.085 | 0.025 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- total_finishers
- winning_time

**High Correlation** (13 features):
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
- ... and 3 more

**Redundant** (13 features):
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
- ... and 3 more

---

### Scenario 27: 70th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.345 | 16.679 | 0.156 |
| winning_time | 5.338 | 16.820 | 0.010 |
| variance_absolute | 5.306 | 16.760 | 0.037 |
| largest_group_position | 5.260 | 16.472 | 0.010 |
| selection_metric | 5.254 | 16.527 | 0.006 |
| avg_group_size | 5.244 | 16.484 | 0.044 |
| shannon_entropy_absolute | 5.212 | 16.421 | 0.014 |
| clumpiness_score | 5.186 | 16.180 | 0.024 |
| largest_group_size | 5.151 | 16.175 | 0.039 |
| std_group_size | 5.122 | 16.014 | 0.029 |
| gini_coefficient | 5.109 | 15.846 | 0.053 |
| riders_in_groups | 5.100 | 15.957 | 0.006 |
| time_gap_evenness_metric | 5.100 | 16.022 | 0.012 |
| total_groups | 5.062 | 15.920 | 0.010 |
| variance_normalized | 5.056 | 17.119 | 0.037 |
| skewness_absolute | 4.594 | 14.225 | 0.017 |

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

### Scenario 28: 70th percentile - stage - pro

- **Races analyzed**: 1881
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.018 | 18.997 | 0.066 |
| clumpiness_score | 5.986 | 18.813 | 0.014 |
| avg_group_size | 5.948 | 18.834 | 0.031 |
| largest_group_position | 5.898 | 18.608 | 0.009 |
| gini_coefficient | 5.887 | 18.438 | 0.082 |
| kurtosis_normalized | 5.862 | 18.606 | 0.008 |
| std_group_size | 5.853 | 18.437 | 0.019 |
| time_gap_evenness_metric | 5.828 | 18.445 | 0.009 |
| largest_group_size | 5.823 | 18.415 | 0.023 |
| variance_absolute | 5.787 | 19.467 | 0.048 |
| selection_metric | 5.772 | 18.254 | 0.022 |
| total_groups | 5.741 | 18.189 | 0.009 |
| riders_in_groups | 5.731 | 18.034 | 0.007 |
| total_race_duration | 5.634 | 17.796 | 0.038 |
| std_deviation_normalized | 5.601 | 17.691 | 0.028 |
| std_deviation_absolute | 5.528 | 17.752 | 0.033 |
| variance_normalized | 5.427 | 17.342 | 0.042 |
| skewness_normalized | 5.292 | 16.489 | 0.027 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
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
- 50th_percentile_gap
- included_finishers
- ... and 4 more

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
- kurtosis_absolute
- ... and 3 more

---

### Scenario 29: 70th percentile - one_day - wt

- **Races analyzed**: 227
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.073 | 22.641 | 0.007 |
| biggest_group_metric | 7.023 | 22.338 | 0.027 |
| largest_group_position | 6.923 | 22.012 | 0.008 |
| 50th_percentile_gap | 6.843 | 21.735 | 0.057 |
| clumpiness_score | 6.833 | 21.645 | 0.006 |
| winning_time | 6.794 | 21.436 | 0.007 |
| avg_group_size | 6.792 | 21.712 | 0.063 |
| total_race_duration | 6.740 | 21.418 | 0.013 |
| variance_absolute | 6.713 | 21.344 | 0.010 |
| std_group_size | 6.679 | 21.196 | 0.035 |
| abandon_ratio | 6.590 | 20.815 | 0.005 |
| gini_coefficient | 6.564 | 20.724 | 0.022 |
| largest_group_size | 6.561 | 20.897 | 0.049 |
| selection_metric | 6.543 | 20.736 | 0.006 |
| shannon_entropy_normalized | 6.539 | 20.800 | 0.024 |
| total_groups | 6.487 | 20.609 | 0.028 |
| proportion_in_groups | 6.471 | 20.532 | 0.010 |
| shannon_entropy_absolute | 6.404 | 20.310 | 0.012 |
| skewness_absolute | 6.345 | 20.036 | 0.013 |
| time_gap_evenness_metric | 6.262 | 19.786 | 0.031 |

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

### Scenario 30: 70th percentile - one_day - pro

- **Races analyzed**: 313
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.436 | 23.686 | 0.016 |
| clumpiness_score | 7.405 | 23.521 | 0.008 |
| variance_absolute | 7.268 | 23.391 | 0.031 |
| proportion_in_groups | 7.217 | 23.047 | 0.017 |
| variance_normalized | 7.214 | 23.059 | 0.018 |
| kurtosis_absolute | 7.198 | 22.978 | 0.006 |
| total_finishers | 7.134 | 22.598 | 0.027 |
| shannon_entropy_absolute | 7.078 | 22.534 | 0.012 |
| 50th_percentile_gap | 7.062 | 22.544 | 0.062 |
| avg_group_size | 7.061 | 22.612 | 0.018 |
| abandon_ratio | 7.053 | 22.340 | 0.007 |
| shannon_entropy_normalized | 7.045 | 22.459 | 0.014 |
| std_group_size | 7.025 | 22.309 | 0.076 |
| gini_coefficient | 7.010 | 22.197 | 0.022 |
| time_gap_evenness_metric | 6.978 | 22.239 | 0.014 |
| largest_group_size | 6.977 | 22.256 | 0.050 |
| total_groups | 6.948 | 22.170 | 0.005 |
| selection_metric | 6.872 | 21.841 | 0.013 |
| total_race_duration | 6.838 | 21.790 | 0.017 |
| skewness_absolute | 6.585 | 20.772 | 0.013 |

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
- included_finishers
- kurtosis_normalized
- ... and 4 more

**Redundant** (11 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_normalized
- skewness_normalized
- ... and 1 more

**Low Score** (2 features):
- largest_group_position
- winning_time

---

### Scenario 31: 80th percentile - stage_one_day - wt

- **Races analyzed**: 2401
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.535 | 17.271 | 0.191 |
| winning_time | 5.521 | 17.439 | 0.007 |
| variance_absolute | 5.481 | 17.361 | 0.018 |
| selection_metric | 5.440 | 17.083 | 0.041 |
| largest_group_position | 5.434 | 17.030 | 0.019 |
| proportion_in_groups | 5.424 | 17.073 | 0.010 |
| avg_group_size | 5.412 | 17.019 | 0.060 |
| kurtosis_normalized | 5.355 | 16.970 | 0.009 |
| clumpiness_score | 5.347 | 16.714 | 0.005 |
| shannon_entropy_absolute | 5.327 | 16.747 | 0.051 |
| largest_group_size | 5.303 | 16.684 | 0.024 |
| std_group_size | 5.275 | 16.543 | 0.029 |
| time_gap_evenness_metric | 5.261 | 16.549 | 0.016 |
| variance_normalized | 5.223 | 17.773 | 0.013 |
| gini_coefficient | 5.218 | 16.250 | 0.013 |
| total_groups | 5.185 | 16.310 | 0.010 |
| skewness_normalized | 4.847 | 15.155 | 0.008 |

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

### Scenario 32: 80th percentile - stage_one_day - pro

- **Races analyzed**: 2206
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.219 | 19.647 | 0.086 |
| clumpiness_score | 6.173 | 19.430 | 0.018 |
| proportion_in_groups | 6.137 | 19.438 | 0.023 |
| avg_group_size | 6.132 | 19.470 | 0.013 |
| largest_group_position | 6.127 | 19.359 | 0.010 |
| selection_metric | 6.101 | 19.329 | 0.016 |
| shannon_entropy_absolute | 6.083 | 19.313 | 0.019 |
| gini_coefficient | 6.035 | 18.900 | 0.064 |
| kurtosis_normalized | 6.014 | 19.142 | 0.007 |
| largest_group_size | 5.999 | 19.009 | 0.032 |
| time_gap_evenness_metric | 5.983 | 18.968 | 0.011 |
| std_group_size | 5.981 | 18.878 | 0.022 |
| variance_absolute | 5.959 | 20.089 | 0.038 |
| riders_in_groups | 5.911 | 18.639 | 0.010 |
| total_groups | 5.851 | 18.538 | 0.008 |
| std_deviation_normalized | 5.846 | 18.481 | 0.019 |
| total_race_duration | 5.742 | 18.172 | 0.029 |
| std_deviation_absolute | 5.637 | 18.019 | 0.036 |
| variance_normalized | 5.620 | 17.844 | 0.038 |
| skewness_normalized | 5.365 | 16.767 | 0.031 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- total_finishers
- winning_time

**High Correlation** (13 features):
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
- ... and 3 more

**Redundant** (12 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 2 more

---

### Scenario 33: 80th percentile - stage - wt

- **Races analyzed**: 2172
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.430 | 16.956 | 0.158 |
| winning_time | 5.426 | 17.109 | 0.043 |
| variance_absolute | 5.374 | 17.025 | 0.013 |
| selection_metric | 5.341 | 16.798 | 0.008 |
| avg_group_size | 5.305 | 16.682 | 0.062 |
| shannon_entropy_absolute | 5.230 | 16.456 | 0.029 |
| clumpiness_score | 5.222 | 16.317 | 0.010 |
| largest_group_size | 5.220 | 16.369 | 0.084 |
| riders_in_groups | 5.198 | 16.259 | 0.052 |
| std_group_size | 5.192 | 16.251 | 0.045 |
| time_gap_evenness_metric | 5.170 | 16.267 | 0.019 |
| gini_coefficient | 5.145 | 15.989 | 0.007 |
| variance_normalized | 5.140 | 17.414 | 0.019 |
| total_groups | 5.115 | 16.029 | 0.063 |

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

### Scenario 34: 80th percentile - stage - pro

- **Races analyzed**: 1881
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.072 | 19.176 | 0.078 |
| clumpiness_score | 6.020 | 18.927 | 0.010 |
| selection_metric | 6.004 | 19.025 | 0.018 |
| largest_group_position | 5.989 | 18.917 | 0.008 |
| avg_group_size | 5.988 | 18.983 | 0.023 |
| shannon_entropy_absolute | 5.958 | 18.906 | 0.018 |
| gini_coefficient | 5.924 | 18.533 | 0.072 |
| kurtosis_normalized | 5.888 | 18.716 | 0.009 |
| time_gap_evenness_metric | 5.873 | 18.595 | 0.009 |
| std_group_size | 5.870 | 18.500 | 0.029 |
| largest_group_size | 5.867 | 18.570 | 0.033 |
| variance_absolute | 5.840 | 19.573 | 0.052 |
| riders_in_groups | 5.792 | 18.240 | 0.010 |
| total_groups | 5.745 | 18.201 | 0.007 |
| std_deviation_normalized | 5.710 | 18.042 | 0.022 |
| total_race_duration | 5.629 | 17.795 | 0.022 |
| std_deviation_absolute | 5.533 | 17.652 | 0.041 |
| variance_normalized | 5.475 | 17.374 | 0.029 |
| skewness_normalized | 5.255 | 16.413 | 0.027 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
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
- 50th_percentile_gap
- included_finishers
- ... and 4 more

**Redundant** (12 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- ... and 2 more

---

### Scenario 35: 80th percentile - one_day - wt

- **Races analyzed**: 229
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| kurtosis_absolute | 7.044 | 22.594 | 0.005 |
| biggest_group_metric | 7.020 | 22.303 | 0.032 |
| largest_group_position | 6.899 | 21.901 | 0.013 |
| 50th_percentile_gap | 6.826 | 21.641 | 0.071 |
| clumpiness_score | 6.815 | 21.581 | 0.007 |
| avg_group_size | 6.805 | 21.824 | 0.009 |
| winning_time | 6.768 | 21.342 | 0.010 |
| total_finishers | 6.716 | 21.147 | 0.069 |
| abandon_ratio | 6.684 | 21.120 | 0.011 |
| variance_absolute | 6.614 | 20.964 | 0.024 |
| std_group_size | 6.594 | 20.901 | 0.006 |
| shannon_entropy_normalized | 6.543 | 20.806 | 0.012 |
| gini_coefficient | 6.478 | 20.418 | 0.030 |
| proportion_in_groups | 6.471 | 20.540 | 0.006 |
| total_groups | 6.460 | 20.523 | 0.018 |
| skewness_absolute | 6.452 | 20.471 | 0.014 |
| largest_group_size | 6.431 | 20.489 | 0.015 |
| selection_metric | 6.366 | 20.136 | 0.005 |
| time_gap_evenness_metric | 6.298 | 19.920 | 0.008 |

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

### Scenario 36: 80th percentile - one_day - pro

- **Races analyzed**: 325
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.475 | 23.816 | 0.029 |
| clumpiness_score | 7.424 | 23.571 | 0.011 |
| proportion_in_groups | 7.220 | 22.995 | 0.068 |
| variance_absolute | 7.198 | 23.170 | 0.007 |
| total_finishers | 7.176 | 22.761 | 0.013 |
| abandon_ratio | 7.155 | 22.684 | 0.006 |
| largest_group_size | 7.070 | 22.549 | 0.052 |
| std_deviation_normalized | 7.048 | 22.421 | 0.012 |
| kurtosis_normalized | 7.036 | 22.442 | 0.020 |
| 50th_percentile_gap | 7.008 | 22.373 | 0.061 |
| total_groups | 6.999 | 22.311 | 0.005 |
| gini_coefficient | 6.979 | 22.114 | 0.019 |
| shannon_entropy_normalized | 6.943 | 22.118 | 0.012 |
| shannon_entropy_absolute | 6.933 | 22.005 | 0.008 |
| total_race_duration | 6.904 | 22.017 | 0.008 |
| avg_group_size | 6.838 | 21.828 | 0.064 |
| skewness_absolute | 6.583 | 20.780 | 0.025 |

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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (12 features):
- 20th_percentile_gap
- 25th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- included_finishers
- kurtosis_absolute
- skewness_normalized
- std_deviation_absolute
- ... and 2 more

**Low Score** (3 features):
- largest_group_position
- selection_metric
- winning_time

---

