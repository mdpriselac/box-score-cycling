# Feature Selection Exploration Report

Generated: 2025-07-07 11:49:35

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 20
- **Total races analyzed**: 48,074
- **Average features selected**: 16.4

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| clumpiness_score | 18 | 100.0% |
| avg_group_size | 18 | 100.0% |
| selection_metric | 18 | 100.0% |
| std_group_size | 18 | 100.0% |
| gini_coefficient | 18 | 100.0% |
| total_race_duration | 18 | 100.0% |
| 50th_percentile_gap | 18 | 100.0% |
| variance_absolute | 18 | 100.0% |
| biggest_group_metric | 17 | 94.4% |
| proportion_in_groups | 14 | 77.8% |
| total_groups | 14 | 77.8% |
| time_gap_evenness_metric | 14 | 77.8% |
| largest_group_size | 13 | 72.2% |
| std_deviation_normalized | 12 | 66.7% |
| skewness_normalized | 11 | 61.1% |

### Feature Removal Patterns

- **High correlation removals**: 260 (avg 14.4 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 247 (avg 13.7 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3388
- **Features available**: 37
- **Features selected**: 12

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.963 | 18.770 | 0.123 |
| clumpiness_score | 5.916 | 18.686 | 0.030 |
| avg_group_size | 5.870 | 18.520 | 0.091 |
| selection_metric | 5.800 | 18.445 | 0.041 |
| std_group_size | 5.738 | 18.085 | 0.007 |
| gini_coefficient | 5.736 | 18.164 | 0.036 |
| kurtosis_absolute | 5.728 | 18.146 | 0.009 |
| std_deviation_normalized | 5.683 | 18.062 | 0.024 |
| total_race_duration | 5.604 | 17.808 | 0.048 |
| 50th_percentile_gap | 5.539 | 17.609 | 0.028 |
| variance_absolute | 5.473 | 17.455 | 0.029 |
| skewness_absolute | 5.206 | 16.255 | 0.032 |

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

**Redundant** (16 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- included_finishers
- kurtosis_normalized
- largest_group_size
- ... and 6 more

---

### Scenario 2: 30th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 336
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| selection_metric | 6.187 | 19.544 | 0.084 |
| clumpiness_score | 6.185 | 19.509 | 0.042 |
| variance_absolute | 6.179 | 19.924 | 0.021 |
| biggest_group_metric | 6.115 | 19.313 | 0.043 |
| kurtosis_normalized | 6.081 | 19.249 | 0.006 |
| winning_time | 6.010 | 18.982 | 0.005 |
| avg_group_size | 6.005 | 19.012 | 0.057 |
| gini_coefficient | 5.937 | 18.638 | 0.032 |
| proportion_in_groups | 5.923 | 18.767 | 0.009 |
| std_group_size | 5.895 | 18.515 | 0.039 |
| 50th_percentile_gap | 5.831 | 18.491 | 0.043 |
| total_groups | 5.824 | 18.451 | 0.041 |
| largest_group_size | 5.821 | 18.485 | 0.007 |
| time_gap_evenness_metric | 5.741 | 18.160 | 0.014 |
| total_race_duration | 5.717 | 18.106 | 0.029 |
| std_deviation_absolute | 5.697 | 18.151 | 0.018 |
| riders_in_groups | 5.656 | 17.862 | 0.009 |
| skewness_normalized | 5.539 | 17.301 | 0.009 |

#### Removed Features by Reason

**Low Score** (3 features):
- abandon_ratio
- largest_group_position
- total_finishers

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
- kurtosis_absolute
- ... and 5 more

---

### Scenario 3: 30th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 3724
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.020 | 18.928 | 0.138 |
| clumpiness_score | 5.988 | 18.888 | 0.041 |
| avg_group_size | 5.921 | 18.693 | 0.073 |
| selection_metric | 5.862 | 18.600 | 0.071 |
| gini_coefficient | 5.798 | 18.341 | 0.025 |
| std_group_size | 5.791 | 18.237 | 0.009 |
| kurtosis_normalized | 5.768 | 18.267 | 0.008 |
| std_deviation_normalized | 5.735 | 18.225 | 0.018 |
| total_race_duration | 5.653 | 17.963 | 0.048 |
| 50th_percentile_gap | 5.586 | 17.760 | 0.036 |
| variance_absolute | 5.544 | 17.686 | 0.031 |
| 5th_percentile_gap | 5.442 | 17.332 | 0.007 |
| skewness_normalized | 5.259 | 16.423 | 0.029 |

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

**Redundant** (15 features):
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
- ... and 5 more

---

### Scenario 4: 40th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3530
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.930 | 18.703 | 0.058 |
| biggest_group_metric | 5.917 | 18.753 | 0.022 |
| avg_group_size | 5.837 | 18.499 | 0.033 |
| selection_metric | 5.798 | 18.456 | 0.030 |
| largest_group_position | 5.782 | 18.361 | 0.005 |
| gini_coefficient | 5.761 | 18.181 | 0.074 |
| std_group_size | 5.756 | 18.091 | 0.023 |
| proportion_in_groups | 5.720 | 18.111 | 0.015 |
| std_deviation_normalized | 5.667 | 18.003 | 0.047 |
| total_race_duration | 5.626 | 17.903 | 0.030 |
| 50th_percentile_gap | 5.528 | 17.586 | 0.028 |
| variance_absolute | 5.368 | 17.113 | 0.043 |
| skewness_normalized | 5.183 | 16.164 | 0.016 |

#### Removed Features by Reason

**Low Score** (6 features):
- 5th_percentile_gap
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
- included_finishers
- kurtosis_absolute
- ... and 6 more

**Redundant** (16 features):
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
- ... and 6 more

---

### Scenario 5: 40th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 459
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.664 | 21.074 | 0.041 |
| biggest_group_metric | 6.656 | 21.067 | 0.082 |
| largest_group_position | 6.552 | 20.816 | 0.012 |
| selection_metric | 6.536 | 20.737 | 0.022 |
| kurtosis_normalized | 6.531 | 20.775 | 0.012 |
| variance_absolute | 6.457 | 20.777 | 0.017 |
| avg_group_size | 6.432 | 20.463 | 0.027 |
| total_finishers | 6.401 | 20.176 | 0.012 |
| gini_coefficient | 6.395 | 20.118 | 0.063 |
| proportion_in_groups | 6.369 | 20.242 | 0.005 |
| largest_group_size | 6.299 | 20.025 | 0.046 |
| std_group_size | 6.288 | 19.830 | 0.050 |
| std_deviation_absolute | 6.241 | 19.862 | 0.019 |
| 50th_percentile_gap | 6.223 | 19.756 | 0.066 |
| total_groups | 6.207 | 19.723 | 0.021 |
| riders_in_groups | 6.189 | 19.582 | 0.019 |
| total_race_duration | 6.184 | 19.651 | 0.013 |
| time_gap_evenness_metric | 6.180 | 19.591 | 0.009 |
| skewness_normalized | 5.918 | 18.588 | 0.019 |

#### Removed Features by Reason

**High Correlation** (13 features):
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
- ... and 3 more

**Redundant** (14 features):
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
- ... and 4 more

**Low Score** (2 features):
- abandon_ratio
- winning_time

---

### Scenario 6: 40th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 3989
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.961 | 18.799 | 0.058 |
| biggest_group_metric | 5.937 | 18.817 | 0.022 |
| avg_group_size | 5.859 | 18.564 | 0.057 |
| selection_metric | 5.802 | 18.468 | 0.033 |
| gini_coefficient | 5.780 | 18.230 | 0.073 |
| std_group_size | 5.767 | 18.119 | 0.021 |
| proportion_in_groups | 5.726 | 18.145 | 0.013 |
| time_gap_evenness_metric | 5.722 | 18.172 | 0.026 |
| total_groups | 5.709 | 18.175 | 0.032 |
| std_deviation_normalized | 5.685 | 18.060 | 0.044 |
| total_race_duration | 5.641 | 17.941 | 0.032 |
| 50th_percentile_gap | 5.555 | 17.650 | 0.043 |
| variance_absolute | 5.401 | 17.205 | 0.048 |
| skewness_normalized | 5.205 | 16.233 | 0.014 |

#### Removed Features by Reason

**Low Score** (7 features):
- 5th_percentile_gap
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

### Scenario 7: 50th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3547
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.967 | 18.810 | 0.054 |
| avg_group_size | 5.872 | 18.616 | 0.027 |
| selection_metric | 5.848 | 18.606 | 0.018 |
| largest_group_position | 5.837 | 18.515 | 0.007 |
| gini_coefficient | 5.802 | 18.253 | 0.072 |
| std_group_size | 5.767 | 18.124 | 0.015 |
| total_groups | 5.715 | 18.179 | 0.027 |
| proportion_in_groups | 5.715 | 18.099 | 0.008 |
| time_gap_evenness_metric | 5.698 | 18.071 | 0.025 |
| std_deviation_normalized | 5.694 | 18.090 | 0.038 |
| total_race_duration | 5.677 | 18.048 | 0.035 |
| 50th_percentile_gap | 5.628 | 17.898 | 0.039 |
| 10th_percentile_gap | 5.410 | 17.203 | 0.016 |
| variance_absolute | 5.387 | 17.133 | 0.047 |
| skewness_normalized | 5.144 | 15.992 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
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
- kurtosis_absolute
- shannon_entropy_absolute
- ... and 4 more

**Redundant** (15 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- biggest_group_metric
- included_finishers
- kurtosis_absolute
- ... and 5 more

---

### Scenario 8: 50th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 505
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.824 | 21.619 | 0.036 |
| biggest_group_metric | 6.800 | 21.591 | 0.036 |
| largest_group_position | 6.666 | 21.181 | 0.006 |
| avg_group_size | 6.583 | 20.999 | 0.027 |
| total_finishers | 6.559 | 20.674 | 0.010 |
| shannon_entropy_absolute | 6.550 | 20.843 | 0.014 |
| selection_metric | 6.519 | 20.679 | 0.025 |
| variance_absolute | 6.513 | 20.848 | 0.019 |
| proportion_in_groups | 6.510 | 20.696 | 0.015 |
| gini_coefficient | 6.487 | 20.452 | 0.046 |
| std_group_size | 6.485 | 20.516 | 0.028 |
| largest_group_size | 6.472 | 20.616 | 0.031 |
| 50th_percentile_gap | 6.373 | 20.220 | 0.074 |
| total_race_duration | 6.370 | 20.229 | 0.021 |
| total_groups | 6.321 | 20.132 | 0.013 |
| time_gap_evenness_metric | 6.279 | 19.922 | 0.012 |
| skewness_normalized | 5.843 | 18.320 | 0.017 |

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
- shannon_entropy_normalized
- ... and 3 more

**Low Score** (3 features):
- abandon_ratio
- kurtosis_normalized
- winning_time

---

### Scenario 9: 50th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 4052
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.982 | 18.852 | 0.052 |
| biggest_group_metric | 5.946 | 18.852 | 0.032 |
| avg_group_size | 5.872 | 18.634 | 0.026 |
| largest_group_position | 5.829 | 18.496 | 0.009 |
| selection_metric | 5.827 | 18.531 | 0.019 |
| gini_coefficient | 5.795 | 18.210 | 0.070 |
| largest_group_size | 5.765 | 18.273 | 0.009 |
| std_group_size | 5.757 | 18.078 | 0.020 |
| proportion_in_groups | 5.705 | 18.071 | 0.009 |
| std_deviation_normalized | 5.697 | 18.090 | 0.041 |
| total_groups | 5.696 | 18.121 | 0.032 |
| time_gap_evenness_metric | 5.680 | 18.021 | 0.023 |
| total_race_duration | 5.672 | 18.022 | 0.034 |
| 50th_percentile_gap | 5.621 | 17.875 | 0.032 |
| 10th_percentile_gap | 5.427 | 17.259 | 0.011 |
| variance_absolute | 5.395 | 17.145 | 0.053 |
| skewness_normalized | 5.191 | 16.137 | 0.015 |

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

**Redundant** (13 features):
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
- ... and 3 more

---

### Scenario 10: 60th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3551
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.831 | 18.382 | 0.045 |
| biggest_group_metric | 5.827 | 18.461 | 0.042 |
| avg_group_size | 5.753 | 18.242 | 0.037 |
| selection_metric | 5.752 | 18.294 | 0.013 |
| largest_group_position | 5.740 | 18.182 | 0.008 |
| gini_coefficient | 5.685 | 17.840 | 0.063 |
| std_group_size | 5.656 | 17.754 | 0.030 |
| largest_group_size | 5.648 | 17.871 | 0.029 |
| std_deviation_normalized | 5.593 | 17.758 | 0.029 |
| total_race_duration | 5.579 | 17.697 | 0.034 |
| total_groups | 5.569 | 17.702 | 0.028 |
| time_gap_evenness_metric | 5.558 | 17.615 | 0.018 |
| 50th_percentile_gap | 5.529 | 17.539 | 0.052 |
| variance_absolute | 5.290 | 16.767 | 0.041 |
| skewness_absolute | 5.034 | 15.625 | 0.015 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- proportion_in_groups
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

### Scenario 11: 60th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 525
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.113 | 22.618 | 0.031 |
| clumpiness_score | 7.016 | 22.241 | 0.012 |
| kurtosis_normalized | 6.887 | 22.027 | 0.007 |
| total_finishers | 6.810 | 21.502 | 0.013 |
| variance_normalized | 6.809 | 21.745 | 0.026 |
| proportion_in_groups | 6.796 | 21.652 | 0.013 |
| avg_group_size | 6.795 | 21.719 | 0.019 |
| std_group_size | 6.727 | 21.343 | 0.048 |
| gini_coefficient | 6.715 | 21.223 | 0.016 |
| variance_absolute | 6.695 | 21.443 | 0.021 |
| largest_group_size | 6.689 | 21.315 | 0.036 |
| selection_metric | 6.688 | 21.249 | 0.018 |
| 50th_percentile_gap | 6.684 | 21.255 | 0.063 |
| shannon_entropy_absolute | 6.604 | 20.972 | 0.019 |
| total_race_duration | 6.575 | 20.921 | 0.017 |
| time_gap_evenness_metric | 6.552 | 20.792 | 0.021 |
| skewness_normalized | 6.163 | 19.382 | 0.008 |

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
- kurtosis_absolute
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

**Low Score** (4 features):
- abandon_ratio
- largest_group_position
- total_groups
- winning_time

---

### Scenario 12: 60th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 4076
- **Features available**: 37
- **Features selected**: 16

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 5.979 | 18.855 | 0.042 |
| biggest_group_metric | 5.966 | 18.903 | 0.053 |
| avg_group_size | 5.891 | 18.696 | 0.033 |
| largest_group_position | 5.863 | 18.585 | 0.007 |
| selection_metric | 5.854 | 18.612 | 0.017 |
| gini_coefficient | 5.804 | 18.212 | 0.061 |
| largest_group_size | 5.773 | 18.295 | 0.019 |
| std_group_size | 5.767 | 18.128 | 0.025 |
| std_deviation_normalized | 5.719 | 18.162 | 0.026 |
| total_race_duration | 5.693 | 18.075 | 0.029 |
| proportion_in_groups | 5.686 | 18.008 | 0.007 |
| total_groups | 5.679 | 18.073 | 0.019 |
| time_gap_evenness_metric | 5.671 | 17.989 | 0.015 |
| 50th_percentile_gap | 5.655 | 17.956 | 0.049 |
| variance_absolute | 5.422 | 17.195 | 0.047 |
| skewness_absolute | 5.179 | 16.096 | 0.013 |

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
- kurtosis_absolute
- ... and 4 more

---

### Scenario 13: 70th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3551
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.897 | 18.671 | 0.064 |
| clumpiness_score | 5.876 | 18.526 | 0.020 |
| largest_group_position | 5.801 | 18.385 | 0.008 |
| avg_group_size | 5.785 | 18.347 | 0.025 |
| shannon_entropy_absolute | 5.784 | 18.379 | 0.013 |
| gini_coefficient | 5.742 | 17.959 | 0.065 |
| selection_metric | 5.739 | 18.241 | 0.009 |
| largest_group_size | 5.680 | 17.987 | 0.022 |
| std_group_size | 5.673 | 17.817 | 0.021 |
| std_deviation_normalized | 5.662 | 17.964 | 0.031 |
| total_race_duration | 5.633 | 17.868 | 0.024 |
| total_groups | 5.606 | 17.825 | 0.017 |
| proportion_in_groups | 5.606 | 17.743 | 0.006 |
| 50th_percentile_gap | 5.605 | 17.787 | 0.054 |
| time_gap_evenness_metric | 5.581 | 17.689 | 0.010 |
| 10th_percentile_gap | 5.401 | 17.152 | 0.009 |
| variance_absolute | 5.392 | 17.043 | 0.058 |
| skewness_absolute | 5.155 | 16.084 | 0.016 |

#### Removed Features by Reason

**Low Score** (5 features):
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

### Scenario 14: 70th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 540
- **Features available**: 37
- **Features selected**: 20

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.376 | 23.505 | 0.023 |
| clumpiness_score | 7.289 | 23.138 | 0.008 |
| largest_group_position | 7.285 | 23.186 | 0.011 |
| winning_time | 7.213 | 22.979 | 0.006 |
| total_finishers | 7.084 | 22.423 | 0.017 |
| avg_group_size | 7.061 | 22.596 | 0.050 |
| proportion_in_groups | 7.040 | 22.455 | 0.015 |
| abandon_ratio | 7.001 | 22.158 | 0.008 |
| std_group_size | 6.993 | 22.200 | 0.072 |
| largest_group_size | 6.935 | 22.077 | 0.081 |
| shannon_entropy_normalized | 6.934 | 22.099 | 0.011 |
| shannon_entropy_absolute | 6.929 | 22.048 | 0.010 |
| gini_coefficient | 6.898 | 21.835 | 0.012 |
| 50th_percentile_gap | 6.881 | 21.903 | 0.048 |
| time_gap_evenness_metric | 6.847 | 21.778 | 0.026 |
| total_race_duration | 6.847 | 21.784 | 0.017 |
| total_groups | 6.838 | 21.811 | 0.005 |
| selection_metric | 6.828 | 21.685 | 0.006 |
| variance_absolute | 6.730 | 21.539 | 0.017 |
| skewness_absolute | 6.435 | 20.279 | 0.006 |

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
- kurtosis_normalized
- ... and 5 more

**Redundant** (13 features):
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
- ... and 3 more

**Low Score** (1 features):
- kurtosis_absolute

---

### Scenario 15: 70th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 4091
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.052 | 19.152 | 0.059 |
| clumpiness_score | 6.032 | 19.040 | 0.011 |
| avg_group_size | 5.967 | 18.884 | 0.084 |
| shannon_entropy_absolute | 5.945 | 18.826 | 0.079 |
| selection_metric | 5.873 | 18.645 | 0.019 |
| gini_coefficient | 5.846 | 18.353 | 0.011 |
| largest_group_size | 5.835 | 18.453 | 0.069 |
| std_deviation_normalized | 5.806 | 18.409 | 0.026 |
| std_group_size | 5.800 | 18.240 | 0.028 |
| kurtosis_absolute | 5.794 | 18.413 | 0.010 |
| total_race_duration | 5.774 | 18.293 | 0.032 |
| 50th_percentile_gap | 5.744 | 18.220 | 0.040 |
| proportion_in_groups | 5.733 | 18.146 | 0.009 |
| total_groups | 5.727 | 18.176 | 0.038 |
| time_gap_evenness_metric | 5.717 | 18.113 | 0.018 |
| riders_in_groups | 5.652 | 17.713 | 0.005 |
| variance_absolute | 5.529 | 17.501 | 0.028 |
| skewness_absolute | 5.196 | 16.209 | 0.020 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- largest_group_position
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

### Scenario 16: 80th percentile - stage - ['wt', 'pro']

- **Races analyzed**: 3551
- **Features available**: 37
- **Features selected**: 19

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.004 | 18.982 | 0.097 |
| clumpiness_score | 5.928 | 18.663 | 0.014 |
| selection_metric | 5.918 | 18.811 | 0.012 |
| largest_group_position | 5.889 | 18.662 | 0.008 |
| avg_group_size | 5.871 | 18.618 | 0.018 |
| shannon_entropy_absolute | 5.807 | 18.428 | 0.013 |
| gini_coefficient | 5.792 | 18.122 | 0.057 |
| kurtosis_normalized | 5.786 | 18.394 | 0.006 |
| std_deviation_normalized | 5.756 | 18.242 | 0.039 |
| largest_group_size | 5.746 | 18.196 | 0.020 |
| std_group_size | 5.734 | 18.039 | 0.028 |
| 50th_percentile_gap | 5.712 | 18.133 | 0.037 |
| total_race_duration | 5.712 | 18.102 | 0.019 |
| proportion_in_groups | 5.676 | 17.958 | 0.005 |
| time_gap_evenness_metric | 5.642 | 17.858 | 0.011 |
| total_groups | 5.635 | 17.897 | 0.014 |
| variance_absolute | 5.510 | 17.416 | 0.039 |
| 5th_percentile_gap | 5.424 | 17.243 | 0.005 |
| skewness_normalized | 5.194 | 16.271 | 0.030 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
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

### Scenario 17: 80th percentile - one_day - ['wt', 'pro']

- **Races analyzed**: 554
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.421 | 23.635 | 0.038 |
| clumpiness_score | 7.319 | 23.221 | 0.011 |
| total_finishers | 7.124 | 22.554 | 0.011 |
| proportion_in_groups | 7.067 | 22.536 | 0.016 |
| kurtosis_absolute | 6.984 | 22.408 | 0.010 |
| largest_group_size | 6.940 | 22.140 | 0.046 |
| shannon_entropy_normalized | 6.935 | 22.116 | 0.021 |
| avg_group_size | 6.919 | 22.194 | 0.025 |
| gini_coefficient | 6.903 | 21.871 | 0.021 |
| 50th_percentile_gap | 6.895 | 21.959 | 0.040 |
| total_groups | 6.884 | 21.944 | 0.008 |
| variance_absolute | 6.871 | 22.005 | 0.011 |
| total_race_duration | 6.866 | 21.850 | 0.018 |
| shannon_entropy_absolute | 6.834 | 21.718 | 0.008 |
| std_group_size | 6.797 | 21.619 | 0.051 |
| selection_metric | 6.764 | 21.476 | 0.008 |
| skewness_absolute | 6.352 | 20.057 | 0.011 |

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
- kurtosis_normalized
- ... and 5 more

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

**Low Score** (3 features):
- abandon_ratio
- largest_group_position
- winning_time

---

### Scenario 18: 80th percentile - stage_one_day - ['wt', 'pro']

- **Races analyzed**: 4105
- **Features available**: 37
- **Features selected**: 18

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.179 | 19.531 | 0.116 |
| clumpiness_score | 6.097 | 19.231 | 0.009 |
| selection_metric | 6.058 | 19.261 | 0.011 |
| largest_group_position | 6.051 | 19.180 | 0.009 |
| avg_group_size | 6.032 | 19.158 | 0.016 |
| shannon_entropy_absolute | 5.960 | 18.930 | 0.013 |
| kurtosis_normalized | 5.940 | 18.921 | 0.005 |
| gini_coefficient | 5.928 | 18.580 | 0.044 |
| largest_group_size | 5.916 | 18.757 | 0.029 |
| std_deviation_normalized | 5.903 | 18.727 | 0.021 |
| std_group_size | 5.886 | 18.544 | 0.035 |
| 50th_percentile_gap | 5.876 | 18.637 | 0.053 |
| total_race_duration | 5.868 | 18.599 | 0.022 |
| time_gap_evenness_metric | 5.791 | 18.341 | 0.010 |
| total_groups | 5.783 | 18.378 | 0.007 |
| riders_in_groups | 5.751 | 18.013 | 0.006 |
| variance_absolute | 5.677 | 17.965 | 0.035 |
| skewness_normalized | 5.319 | 16.688 | 0.023 |

#### Removed Features by Reason

**Low Score** (5 features):
- 5th_percentile_gap
- abandon_ratio
- proportion_in_groups
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
- shannon_entropy_normalized
- ... and 3 more

---

