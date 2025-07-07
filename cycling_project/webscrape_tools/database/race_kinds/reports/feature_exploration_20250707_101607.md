# Feature Selection Exploration Report

Generated: 2025-07-07 10:16:54

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
| biggest_group_metric | 5.976 | 18.838 | 0.026 |
| avg_group_size | 5.921 | 18.602 | 0.117 |
| clumpiness_score | 5.836 | 18.345 | 0.014 |
| time_gap_evenness_metric | 5.822 | 18.389 | 0.034 |
| gini_coefficient | 5.796 | 18.265 | 0.067 |
| std_group_size | 5.774 | 18.186 | 0.006 |
| kurtosis_normalized | 5.736 | 18.143 | 0.005 |
| total_groups | 5.724 | 18.102 | 0.026 |
| total_race_duration | 5.713 | 18.207 | 0.053 |
| std_deviation_absolute | 5.534 | 18.058 | 0.046 |
| variance_absolute | 5.398 | 19.263 | 0.059 |
| variance_normalized | 5.360 | 19.316 | 0.019 |
| skewness_normalized | 5.229 | 16.324 | 0.011 |

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
| biggest_group_metric | 5.972 | 18.860 | 0.026 |
| avg_group_size | 5.924 | 18.631 | 0.121 |
| proportion_in_groups | 5.847 | 18.482 | 0.008 |
| time_gap_evenness_metric | 5.822 | 18.429 | 0.041 |
| clumpiness_score | 5.820 | 18.282 | 0.008 |
| gini_coefficient | 5.779 | 18.231 | 0.057 |
| total_groups | 5.741 | 18.172 | 0.027 |
| kurtosis_absolute | 5.730 | 18.134 | 0.005 |
| total_race_duration | 5.701 | 18.182 | 0.052 |
| std_deviation_absolute | 5.582 | 18.204 | 0.048 |
| variance_absolute | 5.436 | 19.261 | 0.061 |
| variance_normalized | 5.401 | 19.313 | 0.019 |
| skewness_absolute | 5.230 | 16.339 | 0.009 |

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
| clumpiness_score | 6.236 | 19.716 | 0.043 |
| variance_absolute | 6.121 | 19.964 | 0.031 |
| gini_coefficient | 6.087 | 19.197 | 0.043 |
| avg_group_size | 6.054 | 19.171 | 0.070 |
| std_group_size | 6.031 | 18.953 | 0.056 |
| largest_group_position | 5.988 | 19.020 | 0.011 |
| proportion_in_groups | 5.916 | 18.782 | 0.008 |
| time_gap_evenness_metric | 5.884 | 18.703 | 0.013 |
| total_groups | 5.856 | 18.595 | 0.056 |
| largest_group_size | 5.816 | 18.445 | 0.025 |
| 50th_percentile_gap | 5.806 | 18.476 | 0.058 |
| total_race_duration | 5.759 | 18.282 | 0.054 |
| std_deviation_absolute | 5.677 | 18.146 | 0.035 |
| riders_in_groups | 5.568 | 17.556 | 0.005 |
| skewness_normalized | 5.559 | 17.387 | 0.010 |

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
| biggest_group_metric | 5.982 | 18.889 | 0.021 |
| clumpiness_score | 5.902 | 18.531 | 0.036 |
| avg_group_size | 5.890 | 18.566 | 0.093 |
| proportion_in_groups | 5.882 | 18.559 | 0.071 |
| selection_metric | 5.876 | 18.573 | 0.048 |
| gini_coefficient | 5.810 | 18.280 | 0.080 |
| time_gap_evenness_metric | 5.802 | 18.369 | 0.031 |
| std_group_size | 5.789 | 18.217 | 0.019 |
| total_groups | 5.749 | 18.182 | 0.027 |
| total_race_duration | 5.694 | 18.186 | 0.033 |
| riders_in_groups | 5.641 | 17.755 | 0.009 |
| variance_absolute | 5.460 | 19.254 | 0.056 |
| std_deviation_absolute | 5.408 | 17.420 | 0.033 |
| variance_normalized | 5.323 | 19.434 | 0.025 |
| skewness_normalized | 5.221 | 16.267 | 0.012 |

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
| biggest_group_metric | 6.057 | 19.138 | 0.025 |
| avg_group_size | 5.972 | 18.830 | 0.095 |
| proportion_in_groups | 5.955 | 18.812 | 0.067 |
| selection_metric | 5.950 | 18.810 | 0.048 |
| clumpiness_score | 5.934 | 18.652 | 0.027 |
| time_gap_evenness_metric | 5.885 | 18.651 | 0.030 |
| std_group_size | 5.875 | 18.494 | 0.035 |
| gini_coefficient | 5.873 | 18.501 | 0.077 |
| winning_time | 5.868 | 18.650 | 0.005 |
| total_groups | 5.821 | 18.416 | 0.023 |
| total_race_duration | 5.761 | 18.414 | 0.037 |
| riders_in_groups | 5.718 | 18.027 | 0.010 |
| std_deviation_absolute | 5.579 | 17.985 | 0.033 |
| variance_absolute | 5.569 | 19.468 | 0.058 |
| variance_normalized | 5.447 | 19.649 | 0.017 |
| skewness_absolute | 5.277 | 16.457 | 0.014 |

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
| selection_metric | 6.325 | 20.100 | 0.044 |
| gini_coefficient | 6.233 | 19.660 | 0.054 |
| avg_group_size | 6.218 | 19.786 | 0.031 |
| std_group_size | 6.110 | 19.218 | 0.047 |
| largest_group_size | 6.039 | 19.190 | 0.023 |
| proportion_in_groups | 6.034 | 19.156 | 0.011 |
| variance_absolute | 6.012 | 19.396 | 0.031 |
| total_race_duration | 6.008 | 19.080 | 0.043 |
| total_groups | 5.993 | 19.069 | 0.036 |
| 50th_percentile_gap | 5.974 | 18.952 | 0.092 |
| time_gap_evenness_metric | 5.967 | 18.953 | 0.012 |
| skewness_normalized | 5.644 | 17.676 | 0.010 |

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
| biggest_group_metric | 5.961 | 18.816 | 0.040 |
| clumpiness_score | 5.894 | 18.526 | 0.022 |
| avg_group_size | 5.881 | 18.542 | 0.090 |
| proportion_in_groups | 5.870 | 18.487 | 0.065 |
| selection_metric | 5.848 | 18.489 | 0.026 |
| largest_group_position | 5.819 | 18.366 | 0.007 |
| gini_coefficient | 5.782 | 18.161 | 0.076 |
| time_gap_evenness_metric | 5.768 | 18.234 | 0.028 |
| std_group_size | 5.749 | 18.076 | 0.020 |
| total_groups | 5.688 | 18.002 | 0.024 |
| total_race_duration | 5.675 | 18.069 | 0.038 |
| variance_absolute | 5.569 | 19.005 | 0.057 |
| variance_normalized | 5.299 | 19.394 | 0.047 |
| skewness_normalized | 5.172 | 16.069 | 0.018 |

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
| biggest_group_metric | 5.891 | 18.574 | 0.076 |
| avg_group_size | 5.836 | 18.305 | 0.194 |
| selection_metric | 5.784 | 18.261 | 0.062 |
| clumpiness_score | 5.780 | 18.167 | 0.011 |
| proportion_in_groups | 5.776 | 18.265 | 0.010 |
| time_gap_evenness_metric | 5.711 | 18.047 | 0.064 |
| std_group_size | 5.691 | 17.897 | 0.018 |
| total_groups | 5.640 | 17.837 | 0.043 |
| total_race_duration | 5.597 | 17.830 | 0.039 |
| variance_absolute | 5.504 | 18.688 | 0.055 |
| variance_normalized | 5.266 | 19.092 | 0.011 |

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
| clumpiness_score | 6.710 | 21.265 | 0.050 |
| biggest_group_metric | 6.652 | 21.131 | 0.029 |
| largest_group_position | 6.490 | 20.629 | 0.006 |
| shannon_entropy_absolute | 6.477 | 20.625 | 0.020 |
| selection_metric | 6.433 | 20.434 | 0.028 |
| avg_group_size | 6.425 | 20.481 | 0.020 |
| gini_coefficient | 6.424 | 20.251 | 0.054 |
| total_finishers | 6.391 | 20.131 | 0.007 |
| std_group_size | 6.362 | 20.079 | 0.028 |
| total_race_duration | 6.312 | 20.065 | 0.026 |
| largest_group_size | 6.303 | 20.055 | 0.032 |
| proportion_in_groups | 6.289 | 19.982 | 0.012 |
| 50th_percentile_gap | 6.287 | 19.948 | 0.091 |
| variance_absolute | 6.267 | 20.053 | 0.038 |
| total_groups | 6.194 | 19.726 | 0.027 |
| time_gap_evenness_metric | 6.122 | 19.444 | 0.013 |
| skewness_normalized | 5.766 | 18.056 | 0.014 |

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
| clumpiness_score | 5.899 | 18.541 | 0.017 |
| avg_group_size | 5.876 | 18.545 | 0.082 |
| proportion_in_groups | 5.847 | 18.435 | 0.048 |
| selection_metric | 5.834 | 18.428 | 0.023 |
| largest_group_position | 5.830 | 18.376 | 0.011 |
| gini_coefficient | 5.770 | 18.086 | 0.069 |
| std_group_size | 5.751 | 18.093 | 0.018 |
| largest_group_size | 5.748 | 18.170 | 0.009 |
| time_gap_evenness_metric | 5.739 | 18.129 | 0.034 |
| total_groups | 5.666 | 17.926 | 0.020 |
| total_race_duration | 5.643 | 17.960 | 0.029 |
| variance_absolute | 5.634 | 18.702 | 0.044 |
| variance_normalized | 5.290 | 19.373 | 0.049 |
| skewness_absolute | 5.142 | 15.947 | 0.019 |

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
| avg_group_size | 5.745 | 18.097 | 0.097 |
| clumpiness_score | 5.734 | 18.000 | 0.015 |
| selection_metric | 5.720 | 18.054 | 0.030 |
| proportion_in_groups | 5.714 | 18.016 | 0.022 |
| largest_group_position | 5.700 | 17.948 | 0.009 |
| gini_coefficient | 5.653 | 17.681 | 0.099 |
| std_group_size | 5.637 | 17.719 | 0.021 |
| largest_group_size | 5.634 | 17.780 | 0.022 |
| time_gap_evenness_metric | 5.620 | 17.757 | 0.017 |
| total_groups | 5.549 | 17.550 | 0.010 |
| total_race_duration | 5.518 | 17.534 | 0.029 |
| variance_absolute | 5.511 | 18.211 | 0.038 |
| variance_normalized | 5.219 | 18.860 | 0.074 |
| skewness_absolute | 5.060 | 15.671 | 0.022 |

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
| biggest_group_metric | 6.930 | 22.012 | 0.057 |
| clumpiness_score | 6.911 | 21.922 | 0.037 |
| largest_group_position | 6.749 | 21.458 | 0.008 |
| avg_group_size | 6.646 | 21.212 | 0.022 |
| total_finishers | 6.625 | 20.894 | 0.022 |
| gini_coefficient | 6.625 | 20.900 | 0.041 |
| selection_metric | 6.621 | 21.051 | 0.025 |
| shannon_entropy_absolute | 6.594 | 20.998 | 0.005 |
| 50th_percentile_gap | 6.585 | 20.928 | 0.069 |
| total_race_duration | 6.567 | 20.888 | 0.023 |
| std_group_size | 6.567 | 20.785 | 0.048 |
| kurtosis_normalized | 6.563 | 20.916 | 0.006 |
| proportion_in_groups | 6.555 | 20.856 | 0.006 |
| largest_group_size | 6.538 | 20.793 | 0.051 |
| variance_absolute | 6.468 | 20.649 | 0.028 |
| total_groups | 6.417 | 20.452 | 0.013 |
| time_gap_evenness_metric | 6.318 | 20.063 | 0.015 |
| skewness_normalized | 6.035 | 18.941 | 0.016 |

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
| biggest_group_metric | 6.075 | 19.124 | 0.120 |
| clumpiness_score | 6.015 | 18.916 | 0.029 |
| avg_group_size | 5.957 | 18.862 | 0.043 |
| largest_group_position | 5.947 | 18.766 | 0.011 |
| proportion_in_groups | 5.946 | 18.803 | 0.012 |
| shannon_entropy_absolute | 5.945 | 18.857 | 0.014 |
| selection_metric | 5.899 | 18.643 | 0.020 |
| gini_coefficient | 5.858 | 18.333 | 0.073 |
| largest_group_size | 5.835 | 18.459 | 0.024 |
| time_gap_evenness_metric | 5.822 | 18.407 | 0.028 |
| std_group_size | 5.820 | 18.313 | 0.030 |
| variance_absolute | 5.771 | 18.813 | 0.045 |
| total_groups | 5.731 | 18.148 | 0.011 |
| total_race_duration | 5.724 | 18.227 | 0.022 |
| variance_normalized | 5.394 | 19.747 | 0.022 |
| skewness_absolute | 5.286 | 16.450 | 0.023 |

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
| biggest_group_metric | 5.970 | 18.751 | 0.145 |
| clumpiness_score | 5.863 | 18.401 | 0.030 |
| avg_group_size | 5.854 | 18.504 | 0.043 |
| proportion_in_groups | 5.847 | 18.464 | 0.013 |
| largest_group_position | 5.843 | 18.417 | 0.010 |
| selection_metric | 5.820 | 18.378 | 0.018 |
| gini_coefficient | 5.761 | 18.023 | 0.071 |
| largest_group_size | 5.740 | 18.124 | 0.031 |
| time_gap_evenness_metric | 5.735 | 18.116 | 0.021 |
| std_group_size | 5.728 | 18.028 | 0.019 |
| variance_absolute | 5.671 | 18.425 | 0.041 |
| total_groups | 5.659 | 17.900 | 0.009 |
| total_race_duration | 5.624 | 17.886 | 0.018 |
| variance_normalized | 5.344 | 19.312 | 0.030 |
| skewness_absolute | 5.135 | 15.959 | 0.025 |

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
| biggest_group_metric | 7.027 | 22.328 | 0.050 |
| clumpiness_score | 7.000 | 22.206 | 0.020 |
| largest_group_position | 6.858 | 21.789 | 0.009 |
| avg_group_size | 6.760 | 21.584 | 0.026 |
| total_finishers | 6.703 | 21.167 | 0.014 |
| abandon_ratio | 6.683 | 21.070 | 0.006 |
| shannon_entropy_absolute | 6.669 | 21.209 | 0.009 |
| gini_coefficient | 6.666 | 21.040 | 0.033 |
| total_race_duration | 6.664 | 21.178 | 0.026 |
| selection_metric | 6.662 | 21.168 | 0.019 |
| kurtosis_normalized | 6.643 | 21.134 | 0.008 |
| proportion_in_groups | 6.636 | 21.111 | 0.009 |
| 50th_percentile_gap | 6.616 | 20.995 | 0.083 |
| largest_group_size | 6.611 | 20.995 | 0.071 |
| std_group_size | 6.605 | 20.926 | 0.054 |
| total_groups | 6.538 | 20.834 | 0.008 |
| time_gap_evenness_metric | 6.379 | 20.238 | 0.015 |
| variance_absolute | 6.352 | 20.239 | 0.024 |
| skewness_normalized | 6.198 | 19.470 | 0.018 |

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
| biggest_group_metric | 6.179 | 19.530 | 0.046 |
| clumpiness_score | 6.108 | 19.225 | 0.020 |
| proportion_in_groups | 6.089 | 19.243 | 0.064 |
| largest_group_position | 6.077 | 19.182 | 0.011 |
| selection_metric | 6.076 | 19.172 | 0.045 |
| avg_group_size | 6.056 | 19.165 | 0.060 |
| shannon_entropy_absolute | 6.043 | 19.066 | 0.101 |
| winning_time | 6.003 | 19.085 | 0.006 |
| gini_coefficient | 5.938 | 18.604 | 0.009 |
| largest_group_size | 5.936 | 18.801 | 0.015 |
| time_gap_evenness_metric | 5.932 | 18.756 | 0.039 |
| std_group_size | 5.923 | 18.673 | 0.023 |
| variance_absolute | 5.873 | 19.007 | 0.010 |
| total_finishers | 5.844 | 18.265 | 0.005 |
| total_race_duration | 5.813 | 18.539 | 0.014 |
| total_groups | 5.808 | 18.365 | 0.022 |
| variance_normalized | 5.524 | 20.187 | 0.010 |

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
| biggest_group_metric | 6.047 | 19.002 | 0.156 |
| selection_metric | 5.935 | 18.758 | 0.016 |
| proportion_in_groups | 5.930 | 18.743 | 0.008 |
| largest_group_position | 5.917 | 18.662 | 0.010 |
| clumpiness_score | 5.917 | 18.588 | 0.014 |
| avg_group_size | 5.883 | 18.605 | 0.036 |
| shannon_entropy_absolute | 5.877 | 18.611 | 0.021 |
| gini_coefficient | 5.808 | 18.155 | 0.068 |
| time_gap_evenness_metric | 5.796 | 18.319 | 0.020 |
| largest_group_size | 5.793 | 18.319 | 0.016 |
| std_group_size | 5.783 | 18.225 | 0.019 |
| kurtosis_normalized | 5.766 | 18.322 | 0.005 |
| variance_absolute | 5.740 | 18.477 | 0.023 |
| total_groups | 5.698 | 18.016 | 0.008 |
| total_race_duration | 5.674 | 18.045 | 0.009 |
| variance_normalized | 5.432 | 19.585 | 0.042 |
| skewness_normalized | 5.212 | 16.290 | 0.018 |

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
| biggest_group_metric | 7.169 | 22.845 | 0.021 |
| clumpiness_score | 7.073 | 22.424 | 0.043 |
| largest_group_position | 7.035 | 22.373 | 0.007 |
| avg_group_size | 6.864 | 21.932 | 0.065 |
| total_finishers | 6.855 | 21.671 | 0.005 |
| shannon_entropy_normalized | 6.815 | 21.721 | 0.027 |
| 50th_percentile_gap | 6.800 | 21.607 | 0.080 |
| total_race_duration | 6.769 | 21.527 | 0.031 |
| gini_coefficient | 6.755 | 21.357 | 0.011 |
| proportion_in_groups | 6.747 | 21.492 | 0.007 |
| largest_group_size | 6.737 | 21.473 | 0.033 |
| selection_metric | 6.717 | 21.349 | 0.015 |
| kurtosis_normalized | 6.686 | 21.449 | 0.007 |
| shannon_entropy_absolute | 6.679 | 21.220 | 0.023 |
| std_group_size | 6.672 | 21.202 | 0.027 |
| total_groups | 6.612 | 21.062 | 0.015 |
| time_gap_evenness_metric | 6.499 | 20.638 | 0.020 |
| variance_absolute | 6.495 | 20.690 | 0.036 |
| skewness_normalized | 6.115 | 19.220 | 0.007 |

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

