# Feature Selection Exploration Report

Generated: 2025-07-07 10:30:41

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
| biggest_group_metric | 6.030 | 19.016 | 0.026 |
| avg_group_size | 5.954 | 18.712 | 0.117 |
| clumpiness_score | 5.890 | 18.524 | 0.014 |
| time_gap_evenness_metric | 5.874 | 18.563 | 0.034 |
| gini_coefficient | 5.848 | 18.438 | 0.067 |
| std_group_size | 5.829 | 18.369 | 0.006 |
| kurtosis_normalized | 5.792 | 18.330 | 0.005 |
| total_groups | 5.788 | 18.313 | 0.026 |
| total_race_duration | 5.765 | 18.379 | 0.053 |
| std_deviation_absolute | 5.624 | 18.356 | 0.046 |
| variance_absolute | 5.453 | 19.447 | 0.059 |
| variance_normalized | 5.414 | 19.499 | 0.019 |
| skewness_normalized | 5.278 | 16.486 | 0.011 |

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
| biggest_group_metric | 6.002 | 18.958 | 0.026 |
| avg_group_size | 5.953 | 18.728 | 0.121 |
| proportion_in_groups | 5.876 | 18.578 | 0.008 |
| time_gap_evenness_metric | 5.851 | 18.525 | 0.041 |
| clumpiness_score | 5.849 | 18.378 | 0.008 |
| gini_coefficient | 5.807 | 18.325 | 0.057 |
| total_groups | 5.761 | 18.240 | 0.027 |
| kurtosis_absolute | 5.753 | 18.209 | 0.005 |
| total_race_duration | 5.730 | 18.277 | 0.052 |
| std_deviation_absolute | 5.611 | 18.299 | 0.048 |
| variance_absolute | 5.467 | 19.362 | 0.061 |
| variance_normalized | 5.431 | 19.414 | 0.019 |
| skewness_absolute | 5.255 | 16.425 | 0.009 |

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
| clumpiness_score | 6.279 | 19.860 | 0.043 |
| variance_absolute | 6.165 | 20.109 | 0.031 |
| gini_coefficient | 6.131 | 19.341 | 0.043 |
| std_group_size | 6.074 | 19.096 | 0.056 |
| avg_group_size | 6.068 | 19.216 | 0.070 |
| largest_group_position | 6.036 | 19.181 | 0.011 |
| proportion_in_groups | 5.957 | 18.919 | 0.008 |
| time_gap_evenness_metric | 5.925 | 18.839 | 0.013 |
| total_groups | 5.875 | 18.658 | 0.056 |
| largest_group_size | 5.857 | 18.583 | 0.025 |
| 50th_percentile_gap | 5.841 | 18.594 | 0.058 |
| total_race_duration | 5.797 | 18.409 | 0.054 |
| std_deviation_absolute | 5.700 | 18.222 | 0.035 |
| riders_in_groups | 5.636 | 17.786 | 0.005 |
| skewness_normalized | 5.585 | 17.474 | 0.010 |

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
| biggest_group_metric | 5.950 | 18.785 | 0.021 |
| clumpiness_score | 5.871 | 18.429 | 0.036 |
| avg_group_size | 5.859 | 18.463 | 0.093 |
| proportion_in_groups | 5.852 | 18.456 | 0.071 |
| selection_metric | 5.846 | 18.470 | 0.048 |
| gini_coefficient | 5.780 | 18.179 | 0.080 |
| time_gap_evenness_metric | 5.771 | 18.268 | 0.031 |
| std_group_size | 5.760 | 18.118 | 0.019 |
| total_groups | 5.690 | 17.988 | 0.027 |
| total_race_duration | 5.629 | 17.970 | 0.033 |
| riders_in_groups | 5.612 | 17.657 | 0.009 |
| std_deviation_absolute | 5.478 | 17.655 | 0.033 |
| variance_absolute | 5.427 | 19.145 | 0.056 |
| variance_normalized | 5.291 | 19.327 | 0.025 |
| skewness_normalized | 5.196 | 16.186 | 0.012 |

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
| biggest_group_metric | 5.905 | 18.631 | 0.025 |
| avg_group_size | 5.822 | 18.332 | 0.095 |
| proportion_in_groups | 5.805 | 18.314 | 0.067 |
| selection_metric | 5.800 | 18.311 | 0.048 |
| clumpiness_score | 5.780 | 18.139 | 0.027 |
| time_gap_evenness_metric | 5.736 | 18.156 | 0.030 |
| std_group_size | 5.728 | 18.002 | 0.035 |
| gini_coefficient | 5.726 | 18.010 | 0.077 |
| winning_time | 5.720 | 18.155 | 0.005 |
| total_groups | 5.677 | 17.936 | 0.023 |
| total_race_duration | 5.614 | 17.925 | 0.037 |
| riders_in_groups | 5.575 | 17.551 | 0.010 |
| variance_absolute | 5.413 | 18.948 | 0.058 |
| std_deviation_absolute | 5.402 | 17.395 | 0.033 |
| variance_normalized | 5.291 | 19.128 | 0.017 |
| skewness_absolute | 5.148 | 16.027 | 0.014 |

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
| clumpiness_score | 6.521 | 20.667 | 0.055 |
| biggest_group_metric | 6.478 | 20.551 | 0.025 |
| selection_metric | 6.412 | 20.389 | 0.044 |
| gini_coefficient | 6.317 | 19.943 | 0.054 |
| avg_group_size | 6.304 | 20.071 | 0.031 |
| std_group_size | 6.193 | 19.495 | 0.047 |
| largest_group_size | 6.124 | 19.474 | 0.023 |
| variance_absolute | 6.120 | 19.754 | 0.031 |
| proportion_in_groups | 6.116 | 19.431 | 0.011 |
| total_race_duration | 6.091 | 19.355 | 0.043 |
| total_groups | 6.085 | 19.373 | 0.036 |
| 50th_percentile_gap | 6.060 | 19.237 | 0.092 |
| time_gap_evenness_metric | 6.049 | 19.228 | 0.012 |
| skewness_normalized | 5.727 | 17.951 | 0.010 |

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
| biggest_group_metric | 5.945 | 18.761 | 0.040 |
| clumpiness_score | 5.877 | 18.472 | 0.022 |
| avg_group_size | 5.865 | 18.488 | 0.090 |
| proportion_in_groups | 5.854 | 18.434 | 0.065 |
| selection_metric | 5.832 | 18.435 | 0.026 |
| largest_group_position | 5.803 | 18.313 | 0.007 |
| gini_coefficient | 5.767 | 18.109 | 0.076 |
| time_gap_evenness_metric | 5.753 | 18.182 | 0.028 |
| std_group_size | 5.734 | 18.024 | 0.020 |
| total_groups | 5.675 | 17.960 | 0.024 |
| total_race_duration | 5.660 | 18.016 | 0.038 |
| variance_absolute | 5.552 | 18.950 | 0.057 |
| variance_normalized | 5.282 | 19.337 | 0.047 |
| skewness_normalized | 5.131 | 15.934 | 0.018 |

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
| biggest_group_metric | 5.914 | 18.650 | 0.076 |
| avg_group_size | 5.858 | 18.380 | 0.194 |
| clumpiness_score | 5.810 | 18.267 | 0.011 |
| selection_metric | 5.807 | 18.337 | 0.062 |
| proportion_in_groups | 5.798 | 18.339 | 0.010 |
| time_gap_evenness_metric | 5.733 | 18.120 | 0.064 |
| std_group_size | 5.713 | 17.971 | 0.018 |
| total_groups | 5.669 | 17.934 | 0.043 |
| total_race_duration | 5.579 | 17.769 | 0.039 |
| variance_absolute | 5.533 | 18.787 | 0.055 |
| variance_normalized | 5.289 | 19.170 | 0.011 |

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
| clumpiness_score | 6.667 | 21.122 | 0.050 |
| biggest_group_metric | 6.610 | 20.989 | 0.029 |
| largest_group_position | 6.446 | 20.483 | 0.006 |
| shannon_entropy_absolute | 6.435 | 20.486 | 0.020 |
| selection_metric | 6.407 | 20.346 | 0.028 |
| avg_group_size | 6.394 | 20.380 | 0.020 |
| gini_coefficient | 6.383 | 20.114 | 0.054 |
| total_finishers | 6.349 | 19.990 | 0.007 |
| std_group_size | 6.322 | 19.946 | 0.028 |
| total_race_duration | 6.268 | 19.918 | 0.026 |
| largest_group_size | 6.256 | 19.900 | 0.032 |
| proportion_in_groups | 6.248 | 19.847 | 0.012 |
| 50th_percentile_gap | 6.248 | 19.818 | 0.091 |
| variance_absolute | 6.241 | 19.963 | 0.038 |
| total_groups | 6.142 | 19.556 | 0.027 |
| time_gap_evenness_metric | 6.083 | 19.313 | 0.013 |
| skewness_normalized | 5.735 | 17.953 | 0.014 |

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
| biggest_group_metric | 5.956 | 18.782 | 0.062 |
| clumpiness_score | 5.907 | 18.567 | 0.017 |
| avg_group_size | 5.876 | 18.546 | 0.082 |
| proportion_in_groups | 5.847 | 18.435 | 0.048 |
| selection_metric | 5.834 | 18.429 | 0.023 |
| largest_group_position | 5.830 | 18.376 | 0.011 |
| gini_coefficient | 5.771 | 18.086 | 0.069 |
| std_group_size | 5.751 | 18.094 | 0.018 |
| largest_group_size | 5.747 | 18.169 | 0.009 |
| time_gap_evenness_metric | 5.739 | 18.129 | 0.034 |
| total_groups | 5.662 | 17.911 | 0.020 |
| variance_absolute | 5.649 | 18.751 | 0.044 |
| total_race_duration | 5.620 | 17.886 | 0.029 |
| variance_normalized | 5.290 | 19.373 | 0.049 |
| skewness_absolute | 5.179 | 16.073 | 0.019 |

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
| biggest_group_metric | 5.824 | 18.334 | 0.082 |
| avg_group_size | 5.744 | 18.097 | 0.097 |
| clumpiness_score | 5.740 | 18.021 | 0.015 |
| selection_metric | 5.722 | 18.059 | 0.030 |
| proportion_in_groups | 5.715 | 18.018 | 0.022 |
| largest_group_position | 5.700 | 17.949 | 0.009 |
| gini_coefficient | 5.653 | 17.681 | 0.099 |
| std_group_size | 5.637 | 17.719 | 0.021 |
| largest_group_size | 5.634 | 17.780 | 0.022 |
| time_gap_evenness_metric | 5.620 | 17.756 | 0.017 |
| total_groups | 5.542 | 17.525 | 0.010 |
| variance_absolute | 5.519 | 18.236 | 0.038 |
| total_race_duration | 5.475 | 17.389 | 0.029 |
| variance_normalized | 5.219 | 18.860 | 0.074 |
| skewness_absolute | 5.059 | 15.670 | 0.022 |

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
| biggest_group_metric | 6.979 | 22.174 | 0.057 |
| clumpiness_score | 6.960 | 22.084 | 0.037 |
| largest_group_position | 6.793 | 21.604 | 0.008 |
| avg_group_size | 6.685 | 21.339 | 0.022 |
| total_finishers | 6.673 | 21.052 | 0.022 |
| gini_coefficient | 6.671 | 21.055 | 0.041 |
| selection_metric | 6.668 | 21.207 | 0.025 |
| shannon_entropy_absolute | 6.640 | 21.153 | 0.005 |
| 50th_percentile_gap | 6.632 | 21.084 | 0.069 |
| total_race_duration | 6.614 | 21.042 | 0.023 |
| std_group_size | 6.611 | 20.933 | 0.048 |
| kurtosis_normalized | 6.609 | 21.071 | 0.006 |
| proportion_in_groups | 6.601 | 21.010 | 0.006 |
| largest_group_size | 6.582 | 20.942 | 0.051 |
| variance_absolute | 6.514 | 20.802 | 0.028 |
| total_groups | 6.469 | 20.626 | 0.013 |
| time_gap_evenness_metric | 6.363 | 20.211 | 0.015 |
| skewness_normalized | 6.097 | 19.145 | 0.016 |

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
| biggest_group_metric | 6.003 | 18.886 | 0.120 |
| clumpiness_score | 5.944 | 18.679 | 0.029 |
| largest_group_position | 5.876 | 18.531 | 0.011 |
| avg_group_size | 5.876 | 18.594 | 0.043 |
| proportion_in_groups | 5.876 | 18.568 | 0.012 |
| shannon_entropy_absolute | 5.874 | 18.621 | 0.014 |
| selection_metric | 5.830 | 18.411 | 0.020 |
| gini_coefficient | 5.789 | 18.102 | 0.073 |
| largest_group_size | 5.766 | 18.229 | 0.024 |
| time_gap_evenness_metric | 5.753 | 18.177 | 0.028 |
| std_group_size | 5.751 | 18.084 | 0.030 |
| variance_absolute | 5.707 | 18.600 | 0.045 |
| total_groups | 5.659 | 17.905 | 0.011 |
| total_race_duration | 5.656 | 17.999 | 0.022 |
| variance_normalized | 5.320 | 19.500 | 0.022 |
| skewness_absolute | 5.145 | 15.978 | 0.023 |

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
| biggest_group_metric | 5.982 | 18.790 | 0.145 |
| clumpiness_score | 5.875 | 18.439 | 0.030 |
| avg_group_size | 5.865 | 18.542 | 0.043 |
| proportion_in_groups | 5.858 | 18.502 | 0.013 |
| largest_group_position | 5.853 | 18.453 | 0.010 |
| selection_metric | 5.831 | 18.416 | 0.018 |
| gini_coefficient | 5.773 | 18.060 | 0.071 |
| largest_group_size | 5.752 | 18.163 | 0.031 |
| time_gap_evenness_metric | 5.746 | 18.153 | 0.021 |
| std_group_size | 5.740 | 18.068 | 0.019 |
| variance_absolute | 5.675 | 18.441 | 0.041 |
| total_groups | 5.654 | 17.883 | 0.009 |
| total_race_duration | 5.636 | 17.923 | 0.018 |
| variance_normalized | 5.356 | 19.352 | 0.030 |
| skewness_absolute | 5.188 | 16.137 | 0.025 |

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
| biggest_group_metric | 7.028 | 22.329 | 0.050 |
| clumpiness_score | 7.000 | 22.206 | 0.020 |
| largest_group_position | 6.854 | 21.776 | 0.009 |
| avg_group_size | 6.760 | 21.584 | 0.026 |
| total_finishers | 6.702 | 21.165 | 0.014 |
| abandon_ratio | 6.684 | 21.072 | 0.006 |
| shannon_entropy_absolute | 6.669 | 21.208 | 0.009 |
| gini_coefficient | 6.666 | 21.040 | 0.033 |
| total_race_duration | 6.663 | 21.177 | 0.026 |
| selection_metric | 6.662 | 21.167 | 0.019 |
| kurtosis_normalized | 6.647 | 21.148 | 0.008 |
| proportion_in_groups | 6.636 | 21.111 | 0.009 |
| 50th_percentile_gap | 6.616 | 20.996 | 0.083 |
| largest_group_size | 6.612 | 20.998 | 0.071 |
| std_group_size | 6.605 | 20.926 | 0.054 |
| total_groups | 6.434 | 20.488 | 0.008 |
| time_gap_evenness_metric | 6.379 | 20.240 | 0.015 |
| variance_absolute | 6.357 | 20.257 | 0.024 |
| skewness_normalized | 6.203 | 19.485 | 0.018 |

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
| biggest_group_metric | 6.136 | 19.387 | 0.046 |
| clumpiness_score | 6.068 | 19.091 | 0.020 |
| proportion_in_groups | 6.047 | 19.102 | 0.064 |
| largest_group_position | 6.035 | 19.041 | 0.011 |
| selection_metric | 6.034 | 19.032 | 0.045 |
| avg_group_size | 6.023 | 19.056 | 0.060 |
| shannon_entropy_absolute | 6.001 | 18.927 | 0.101 |
| winning_time | 5.961 | 18.945 | 0.006 |
| gini_coefficient | 5.897 | 18.469 | 0.009 |
| largest_group_size | 5.896 | 18.667 | 0.015 |
| time_gap_evenness_metric | 5.890 | 18.619 | 0.039 |
| std_group_size | 5.882 | 18.537 | 0.023 |
| variance_absolute | 5.856 | 18.951 | 0.010 |
| total_finishers | 5.803 | 18.130 | 0.005 |
| total_groups | 5.791 | 18.308 | 0.022 |
| total_race_duration | 5.772 | 18.404 | 0.014 |
| variance_normalized | 5.480 | 20.040 | 0.010 |

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
| biggest_group_metric | 5.992 | 18.818 | 0.156 |
| selection_metric | 5.880 | 18.576 | 0.016 |
| proportion_in_groups | 5.876 | 18.562 | 0.008 |
| clumpiness_score | 5.870 | 18.434 | 0.014 |
| largest_group_position | 5.865 | 18.487 | 0.010 |
| avg_group_size | 5.845 | 18.479 | 0.036 |
| shannon_entropy_absolute | 5.823 | 18.431 | 0.021 |
| gini_coefficient | 5.755 | 17.979 | 0.068 |
| time_gap_evenness_metric | 5.743 | 18.142 | 0.020 |
| largest_group_size | 5.739 | 18.138 | 0.016 |
| std_group_size | 5.731 | 18.049 | 0.019 |
| kurtosis_normalized | 5.714 | 18.149 | 0.005 |
| variance_absolute | 5.693 | 18.318 | 0.023 |
| total_groups | 5.636 | 17.809 | 0.008 |
| total_race_duration | 5.622 | 17.870 | 0.009 |
| variance_normalized | 5.375 | 19.395 | 0.042 |
| skewness_normalized | 5.182 | 16.189 | 0.018 |

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
| biggest_group_metric | 7.196 | 22.934 | 0.021 |
| clumpiness_score | 7.099 | 22.510 | 0.043 |
| largest_group_position | 7.061 | 22.461 | 0.007 |
| avg_group_size | 6.894 | 22.030 | 0.065 |
| total_finishers | 6.878 | 21.748 | 0.005 |
| 50th_percentile_gap | 6.842 | 21.747 | 0.080 |
| shannon_entropy_normalized | 6.840 | 21.805 | 0.027 |
| total_race_duration | 6.816 | 21.684 | 0.031 |
| gini_coefficient | 6.780 | 21.440 | 0.011 |
| proportion_in_groups | 6.766 | 21.555 | 0.007 |
| largest_group_size | 6.762 | 21.556 | 0.033 |
| selection_metric | 6.740 | 21.429 | 0.015 |
| kurtosis_normalized | 6.711 | 21.533 | 0.007 |
| shannon_entropy_absolute | 6.703 | 21.302 | 0.023 |
| std_group_size | 6.682 | 21.237 | 0.027 |
| total_groups | 6.613 | 21.066 | 0.015 |
| variance_absolute | 6.550 | 20.872 | 0.036 |
| time_gap_evenness_metric | 6.523 | 20.718 | 0.020 |
| skewness_normalized | 6.135 | 19.289 | 0.007 |

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

