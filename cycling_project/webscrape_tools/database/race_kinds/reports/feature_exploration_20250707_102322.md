# Feature Selection Exploration Report

Generated: 2025-07-07 10:24:08

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
| biggest_group_metric | 5.993 | 18.894 | 0.026 |
| avg_group_size | 5.937 | 18.658 | 0.117 |
| clumpiness_score | 5.855 | 18.410 | 0.014 |
| time_gap_evenness_metric | 5.838 | 18.444 | 0.034 |
| gini_coefficient | 5.813 | 18.320 | 0.067 |
| std_group_size | 5.790 | 18.240 | 0.006 |
| kurtosis_normalized | 5.748 | 18.185 | 0.005 |
| total_groups | 5.737 | 18.145 | 0.026 |
| total_race_duration | 5.718 | 18.223 | 0.053 |
| std_deviation_absolute | 5.588 | 18.238 | 0.046 |
| variance_absolute | 5.416 | 19.321 | 0.059 |
| variance_normalized | 5.377 | 19.374 | 0.019 |
| skewness_normalized | 5.246 | 16.380 | 0.011 |

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
| biggest_group_metric | 5.986 | 18.905 | 0.026 |
| avg_group_size | 5.937 | 18.674 | 0.121 |
| proportion_in_groups | 5.860 | 18.525 | 0.008 |
| time_gap_evenness_metric | 5.835 | 18.472 | 0.041 |
| clumpiness_score | 5.834 | 18.327 | 0.008 |
| gini_coefficient | 5.791 | 18.273 | 0.057 |
| total_groups | 5.748 | 18.198 | 0.027 |
| kurtosis_absolute | 5.746 | 18.187 | 0.005 |
| total_race_duration | 5.703 | 18.188 | 0.052 |
| std_deviation_absolute | 5.595 | 18.247 | 0.048 |
| variance_absolute | 5.449 | 19.302 | 0.061 |
| variance_normalized | 5.415 | 19.359 | 0.019 |
| skewness_absolute | 5.241 | 16.378 | 0.009 |

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
| clumpiness_score | 6.257 | 19.788 | 0.043 |
| variance_absolute | 6.143 | 20.037 | 0.031 |
| gini_coefficient | 6.109 | 19.270 | 0.043 |
| avg_group_size | 6.089 | 19.285 | 0.070 |
| std_group_size | 6.052 | 19.025 | 0.056 |
| largest_group_position | 6.009 | 19.090 | 0.011 |
| proportion_in_groups | 5.936 | 18.851 | 0.008 |
| time_gap_evenness_metric | 5.905 | 18.771 | 0.013 |
| total_groups | 5.892 | 18.714 | 0.056 |
| largest_group_size | 5.838 | 18.521 | 0.025 |
| 50th_percentile_gap | 5.826 | 18.545 | 0.058 |
| total_race_duration | 5.772 | 18.327 | 0.054 |
| std_deviation_absolute | 5.713 | 18.266 | 0.035 |
| riders_in_groups | 5.618 | 17.723 | 0.005 |
| skewness_normalized | 5.555 | 17.375 | 0.010 |

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
| avg_group_size | 5.858 | 18.462 | 0.093 |
| proportion_in_groups | 5.852 | 18.456 | 0.071 |
| selection_metric | 5.846 | 18.470 | 0.048 |
| gini_coefficient | 5.780 | 18.179 | 0.080 |
| time_gap_evenness_metric | 5.771 | 18.268 | 0.031 |
| std_group_size | 5.760 | 18.118 | 0.019 |
| total_groups | 5.711 | 18.058 | 0.027 |
| total_race_duration | 5.664 | 18.086 | 0.033 |
| riders_in_groups | 5.612 | 17.659 | 0.009 |
| std_deviation_absolute | 5.445 | 17.545 | 0.033 |
| variance_absolute | 5.431 | 19.156 | 0.056 |
| variance_normalized | 5.291 | 19.327 | 0.025 |
| skewness_normalized | 5.199 | 16.194 | 0.012 |

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
| biggest_group_metric | 5.929 | 18.711 | 0.025 |
| avg_group_size | 5.846 | 18.410 | 0.095 |
| proportion_in_groups | 5.829 | 18.391 | 0.067 |
| selection_metric | 5.824 | 18.390 | 0.048 |
| clumpiness_score | 5.809 | 18.235 | 0.027 |
| time_gap_evenness_metric | 5.760 | 18.234 | 0.030 |
| std_group_size | 5.751 | 18.079 | 0.035 |
| gini_coefficient | 5.749 | 18.087 | 0.077 |
| winning_time | 5.743 | 18.233 | 0.005 |
| total_groups | 5.709 | 18.044 | 0.023 |
| total_race_duration | 5.637 | 18.003 | 0.037 |
| riders_in_groups | 5.597 | 17.623 | 0.010 |
| variance_absolute | 5.440 | 19.038 | 0.058 |
| std_deviation_absolute | 5.424 | 17.469 | 0.033 |
| variance_normalized | 5.315 | 19.210 | 0.017 |
| skewness_absolute | 5.169 | 16.096 | 0.014 |

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
| clumpiness_score | 6.521 | 20.666 | 0.055 |
| biggest_group_metric | 6.478 | 20.551 | 0.025 |
| selection_metric | 6.412 | 20.392 | 0.044 |
| gini_coefficient | 6.317 | 19.942 | 0.054 |
| avg_group_size | 6.304 | 20.071 | 0.031 |
| std_group_size | 6.193 | 19.496 | 0.047 |
| largest_group_size | 6.123 | 19.470 | 0.023 |
| proportion_in_groups | 6.116 | 19.432 | 0.011 |
| variance_absolute | 6.114 | 19.734 | 0.031 |
| total_race_duration | 6.091 | 19.355 | 0.043 |
| total_groups | 6.072 | 19.330 | 0.036 |
| 50th_percentile_gap | 6.052 | 19.210 | 0.092 |
| time_gap_evenness_metric | 6.048 | 19.225 | 0.012 |
| skewness_normalized | 5.727 | 17.953 | 0.010 |

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
| biggest_group_metric | 5.989 | 18.907 | 0.040 |
| clumpiness_score | 5.926 | 18.634 | 0.022 |
| avg_group_size | 5.908 | 18.631 | 0.090 |
| proportion_in_groups | 5.896 | 18.577 | 0.065 |
| selection_metric | 5.874 | 18.578 | 0.026 |
| largest_group_position | 5.845 | 18.454 | 0.007 |
| gini_coefficient | 5.809 | 18.249 | 0.076 |
| time_gap_evenness_metric | 5.795 | 18.322 | 0.028 |
| std_group_size | 5.775 | 18.162 | 0.020 |
| total_groups | 5.727 | 18.134 | 0.024 |
| total_race_duration | 5.681 | 18.088 | 0.038 |
| variance_absolute | 5.596 | 19.096 | 0.057 |
| variance_normalized | 5.327 | 19.487 | 0.047 |
| skewness_normalized | 5.195 | 16.147 | 0.018 |

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
| biggest_group_metric | 5.876 | 18.523 | 0.076 |
| avg_group_size | 5.821 | 18.255 | 0.194 |
| selection_metric | 5.768 | 18.208 | 0.062 |
| proportion_in_groups | 5.760 | 18.214 | 0.010 |
| clumpiness_score | 5.757 | 18.091 | 0.011 |
| time_gap_evenness_metric | 5.696 | 17.997 | 0.064 |
| std_group_size | 5.676 | 17.847 | 0.018 |
| total_groups | 5.635 | 17.820 | 0.043 |
| total_race_duration | 5.562 | 17.714 | 0.039 |
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

### Scenario 9: 50th percentile - one_day

- **Races analyzed**: 1249
- **Features available**: 37
- **Features selected**: 17

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.755 | 21.417 | 0.050 |
| biggest_group_metric | 6.697 | 21.281 | 0.029 |
| largest_group_position | 6.531 | 20.768 | 0.006 |
| shannon_entropy_absolute | 6.521 | 20.772 | 0.020 |
| selection_metric | 6.492 | 20.630 | 0.028 |
| avg_group_size | 6.485 | 20.681 | 0.020 |
| gini_coefficient | 6.467 | 20.395 | 0.054 |
| total_finishers | 6.433 | 20.270 | 0.007 |
| std_group_size | 6.405 | 20.222 | 0.028 |
| total_race_duration | 6.351 | 20.195 | 0.026 |
| largest_group_size | 6.351 | 20.216 | 0.032 |
| proportion_in_groups | 6.332 | 20.126 | 0.012 |
| 50th_percentile_gap | 6.330 | 20.089 | 0.091 |
| variance_absolute | 6.325 | 20.246 | 0.038 |
| total_groups | 6.250 | 19.915 | 0.027 |
| time_gap_evenness_metric | 6.164 | 19.581 | 0.013 |
| skewness_normalized | 5.822 | 18.244 | 0.014 |

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
| biggest_group_metric | 5.926 | 18.682 | 0.062 |
| clumpiness_score | 5.862 | 18.417 | 0.017 |
| avg_group_size | 5.846 | 18.447 | 0.082 |
| proportion_in_groups | 5.817 | 18.337 | 0.048 |
| selection_metric | 5.804 | 18.330 | 0.023 |
| largest_group_position | 5.800 | 18.277 | 0.011 |
| gini_coefficient | 5.742 | 17.990 | 0.069 |
| std_group_size | 5.722 | 17.997 | 0.018 |
| largest_group_size | 5.719 | 18.073 | 0.009 |
| time_gap_evenness_metric | 5.710 | 18.033 | 0.034 |
| total_groups | 5.627 | 17.796 | 0.020 |
| variance_absolute | 5.618 | 18.648 | 0.044 |
| total_race_duration | 5.614 | 17.865 | 0.029 |
| variance_normalized | 5.259 | 19.270 | 0.049 |
| skewness_absolute | 5.154 | 15.987 | 0.019 |

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
| avg_group_size | 5.744 | 18.096 | 0.097 |
| clumpiness_score | 5.734 | 18.000 | 0.015 |
| selection_metric | 5.722 | 18.059 | 0.030 |
| proportion_in_groups | 5.715 | 18.018 | 0.022 |
| largest_group_position | 5.700 | 17.948 | 0.009 |
| gini_coefficient | 5.653 | 17.681 | 0.099 |
| std_group_size | 5.637 | 17.719 | 0.021 |
| largest_group_size | 5.634 | 17.782 | 0.022 |
| time_gap_evenness_metric | 5.620 | 17.757 | 0.017 |
| total_groups | 5.550 | 17.553 | 0.010 |
| variance_absolute | 5.519 | 18.236 | 0.038 |
| total_race_duration | 5.496 | 17.461 | 0.029 |
| variance_normalized | 5.219 | 18.860 | 0.074 |
| skewness_absolute | 5.079 | 15.736 | 0.022 |

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
| biggest_group_metric | 6.896 | 21.898 | 0.057 |
| clumpiness_score | 6.877 | 21.808 | 0.037 |
| largest_group_position | 6.717 | 21.351 | 0.008 |
| avg_group_size | 6.603 | 21.068 | 0.022 |
| total_finishers | 6.594 | 20.790 | 0.022 |
| gini_coefficient | 6.592 | 20.792 | 0.041 |
| selection_metric | 6.588 | 20.942 | 0.025 |
| shannon_entropy_absolute | 6.561 | 20.889 | 0.005 |
| 50th_percentile_gap | 6.553 | 20.822 | 0.069 |
| std_group_size | 6.535 | 20.676 | 0.048 |
| proportion_in_groups | 6.522 | 20.748 | 0.006 |
| total_race_duration | 6.516 | 20.717 | 0.023 |
| largest_group_size | 6.506 | 20.689 | 0.051 |
| kurtosis_normalized | 6.484 | 20.654 | 0.006 |
| variance_absolute | 6.407 | 20.445 | 0.028 |
| total_groups | 6.402 | 20.403 | 0.013 |
| time_gap_evenness_metric | 6.287 | 19.958 | 0.015 |
| skewness_normalized | 5.996 | 18.811 | 0.016 |

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
| avg_group_size | 5.911 | 18.710 | 0.043 |
| largest_group_position | 5.907 | 18.632 | 0.011 |
| proportion_in_groups | 5.906 | 18.669 | 0.012 |
| shannon_entropy_absolute | 5.904 | 18.721 | 0.014 |
| selection_metric | 5.859 | 18.509 | 0.020 |
| gini_coefficient | 5.819 | 18.202 | 0.073 |
| largest_group_size | 5.796 | 18.327 | 0.024 |
| time_gap_evenness_metric | 5.782 | 18.275 | 0.028 |
| std_group_size | 5.781 | 18.181 | 0.030 |
| variance_absolute | 5.736 | 18.697 | 0.045 |
| total_groups | 5.697 | 18.034 | 0.011 |
| total_race_duration | 5.685 | 18.095 | 0.022 |
| variance_normalized | 5.351 | 19.606 | 0.022 |
| skewness_absolute | 5.251 | 16.333 | 0.023 |

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
| biggest_group_metric | 6.045 | 18.998 | 0.145 |
| clumpiness_score | 5.936 | 18.643 | 0.030 |
| avg_group_size | 5.927 | 18.747 | 0.043 |
| proportion_in_groups | 5.920 | 18.708 | 0.013 |
| largest_group_position | 5.915 | 18.658 | 0.010 |
| selection_metric | 5.893 | 18.621 | 0.018 |
| gini_coefficient | 5.833 | 18.261 | 0.071 |
| largest_group_size | 5.813 | 18.366 | 0.031 |
| time_gap_evenness_metric | 5.806 | 18.355 | 0.021 |
| std_group_size | 5.800 | 18.267 | 0.019 |
| variance_absolute | 5.738 | 18.649 | 0.041 |
| total_groups | 5.718 | 18.098 | 0.009 |
| total_race_duration | 5.695 | 18.122 | 0.018 |
| variance_normalized | 5.420 | 19.567 | 0.030 |
| skewness_absolute | 5.286 | 16.463 | 0.025 |

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
| biggest_group_metric | 7.058 | 22.430 | 0.050 |
| clumpiness_score | 7.030 | 22.307 | 0.020 |
| largest_group_position | 6.883 | 21.874 | 0.009 |
| avg_group_size | 6.790 | 21.682 | 0.026 |
| total_finishers | 6.733 | 21.267 | 0.014 |
| abandon_ratio | 6.709 | 21.155 | 0.006 |
| shannon_entropy_absolute | 6.698 | 21.306 | 0.009 |
| gini_coefficient | 6.695 | 21.135 | 0.033 |
| total_race_duration | 6.692 | 21.273 | 0.026 |
| selection_metric | 6.691 | 21.263 | 0.019 |
| kurtosis_normalized | 6.673 | 21.236 | 0.008 |
| proportion_in_groups | 6.665 | 21.206 | 0.009 |
| largest_group_size | 6.647 | 21.116 | 0.071 |
| 50th_percentile_gap | 6.644 | 21.091 | 0.083 |
| std_group_size | 6.635 | 21.025 | 0.054 |
| total_groups | 6.530 | 20.808 | 0.008 |
| time_gap_evenness_metric | 6.407 | 20.333 | 0.015 |
| variance_absolute | 6.379 | 20.330 | 0.024 |
| skewness_normalized | 6.228 | 19.568 | 0.018 |

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
| biggest_group_metric | 6.118 | 19.326 | 0.046 |
| clumpiness_score | 6.038 | 18.993 | 0.020 |
| proportion_in_groups | 6.029 | 19.043 | 0.064 |
| largest_group_position | 6.017 | 18.981 | 0.011 |
| selection_metric | 6.016 | 18.972 | 0.045 |
| avg_group_size | 5.999 | 18.973 | 0.060 |
| shannon_entropy_absolute | 5.983 | 18.868 | 0.101 |
| winning_time | 5.974 | 18.987 | 0.006 |
| gini_coefficient | 5.880 | 18.410 | 0.009 |
| largest_group_size | 5.875 | 18.595 | 0.015 |
| time_gap_evenness_metric | 5.873 | 18.560 | 0.039 |
| std_group_size | 5.865 | 18.479 | 0.023 |
| total_finishers | 5.787 | 18.075 | 0.005 |
| variance_absolute | 5.785 | 18.715 | 0.010 |
| total_groups | 5.770 | 18.238 | 0.022 |
| total_race_duration | 5.755 | 18.346 | 0.014 |
| variance_normalized | 5.461 | 19.977 | 0.010 |

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
| biggest_group_metric | 6.029 | 18.942 | 0.156 |
| selection_metric | 5.917 | 18.698 | 0.016 |
| proportion_in_groups | 5.912 | 18.684 | 0.008 |
| largest_group_position | 5.901 | 18.608 | 0.010 |
| clumpiness_score | 5.893 | 18.509 | 0.014 |
| avg_group_size | 5.874 | 18.577 | 0.036 |
| shannon_entropy_absolute | 5.859 | 18.552 | 0.021 |
| gini_coefficient | 5.791 | 18.097 | 0.068 |
| time_gap_evenness_metric | 5.779 | 18.261 | 0.020 |
| largest_group_size | 5.775 | 18.257 | 0.016 |
| std_group_size | 5.766 | 18.168 | 0.019 |
| kurtosis_normalized | 5.753 | 18.279 | 0.005 |
| variance_absolute | 5.704 | 18.357 | 0.023 |
| total_groups | 5.678 | 17.949 | 0.008 |
| total_race_duration | 5.657 | 17.988 | 0.009 |
| variance_normalized | 5.413 | 19.523 | 0.042 |
| skewness_normalized | 5.213 | 16.296 | 0.018 |

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
| biggest_group_metric | 7.161 | 22.817 | 0.021 |
| clumpiness_score | 7.072 | 22.420 | 0.043 |
| largest_group_position | 7.028 | 22.350 | 0.007 |
| avg_group_size | 6.866 | 21.938 | 0.065 |
| total_finishers | 6.845 | 21.639 | 0.005 |
| 50th_percentile_gap | 6.808 | 21.636 | 0.080 |
| shannon_entropy_normalized | 6.806 | 21.693 | 0.027 |
| total_race_duration | 6.783 | 21.574 | 0.031 |
| gini_coefficient | 6.747 | 21.329 | 0.011 |
| proportion_in_groups | 6.739 | 21.463 | 0.007 |
| largest_group_size | 6.727 | 21.440 | 0.033 |
| selection_metric | 6.709 | 21.324 | 0.015 |
| kurtosis_normalized | 6.678 | 21.422 | 0.007 |
| shannon_entropy_absolute | 6.670 | 21.193 | 0.023 |
| std_group_size | 6.640 | 21.096 | 0.027 |
| total_groups | 6.601 | 21.028 | 0.015 |
| variance_absolute | 6.531 | 20.811 | 0.036 |
| time_gap_evenness_metric | 6.490 | 20.608 | 0.020 |
| skewness_normalized | 6.112 | 19.211 | 0.007 |

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

