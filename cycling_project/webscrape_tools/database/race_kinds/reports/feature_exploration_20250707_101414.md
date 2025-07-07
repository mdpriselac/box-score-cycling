# Feature Selection Exploration Report

Generated: 2025-07-07 10:15:01

## Executive Summary

- **Total scenarios analyzed**: 18
- **Max features per scenario**: 15
- **Total races analyzed**: 94,790
- **Average features selected**: 14.4

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| avg_group_size | 18 | 100.0% |
| clumpiness_score | 18 | 100.0% |
| biggest_group_metric | 17 | 94.4% |
| gini_coefficient | 17 | 94.4% |
| std_group_size | 17 | 94.4% |
| total_race_duration | 17 | 94.4% |
| proportion_in_groups | 17 | 94.4% |
| total_groups | 16 | 88.9% |
| variance_absolute | 15 | 83.3% |
| selection_metric | 15 | 83.3% |
| time_gap_evenness_metric | 14 | 77.8% |
| largest_group_position | 12 | 66.7% |
| largest_group_size | 12 | 66.7% |
| variance_normalized | 10 | 55.6% |
| shannon_entropy_absolute | 7 | 38.9% |

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
| biggest_group_metric | 6.033 | 19.026 | 0.026 |
| avg_group_size | 5.976 | 18.788 | 0.117 |
| clumpiness_score | 5.892 | 18.534 | 0.014 |
| time_gap_evenness_metric | 5.877 | 18.573 | 0.034 |
| gini_coefficient | 5.851 | 18.448 | 0.067 |
| std_group_size | 5.831 | 18.378 | 0.006 |
| total_groups | 5.783 | 18.297 | 0.026 |
| kurtosis_normalized | 5.775 | 18.273 | 0.005 |
| total_race_duration | 5.745 | 18.312 | 0.053 |
| std_deviation_absolute | 5.588 | 18.239 | 0.046 |
| variance_absolute | 5.454 | 19.451 | 0.059 |
| variance_normalized | 5.418 | 19.509 | 0.019 |
| skewness_normalized | 5.280 | 16.495 | 0.011 |

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
| biggest_group_metric | 5.986 | 18.907 | 0.026 |
| avg_group_size | 5.937 | 18.677 | 0.121 |
| proportion_in_groups | 5.861 | 18.528 | 0.008 |
| time_gap_evenness_metric | 5.836 | 18.474 | 0.041 |
| clumpiness_score | 5.835 | 18.331 | 0.008 |
| gini_coefficient | 5.792 | 18.276 | 0.057 |
| total_groups | 5.750 | 18.204 | 0.027 |
| kurtosis_absolute | 5.732 | 18.142 | 0.005 |
| total_race_duration | 5.726 | 18.265 | 0.052 |
| std_deviation_absolute | 5.596 | 18.250 | 0.048 |
| variance_absolute | 5.450 | 19.307 | 0.061 |
| variance_normalized | 5.416 | 19.361 | 0.019 |
| skewness_absolute | 5.238 | 16.369 | 0.009 |

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
| clumpiness_score | 6.212 | 19.636 | 0.043 |
| variance_absolute | 6.097 | 19.882 | 0.031 |
| gini_coefficient | 6.065 | 19.123 | 0.043 |
| avg_group_size | 6.030 | 19.090 | 0.070 |
| std_group_size | 6.009 | 18.881 | 0.056 |
| largest_group_position | 5.977 | 18.984 | 0.011 |
| proportion_in_groups | 5.893 | 18.705 | 0.008 |
| time_gap_evenness_metric | 5.861 | 18.627 | 0.013 |
| total_groups | 5.819 | 18.470 | 0.056 |
| largest_group_size | 5.789 | 18.356 | 0.025 |
| 50th_percentile_gap | 5.782 | 18.398 | 0.058 |
| total_race_duration | 5.731 | 18.189 | 0.054 |
| std_deviation_absolute | 5.639 | 18.019 | 0.035 |
| riders_in_groups | 5.567 | 17.553 | 0.005 |
| skewness_normalized | 5.536 | 17.312 | 0.010 |

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
| clumpiness_score | 5.897 | 18.516 | 0.036 |
| avg_group_size | 5.889 | 18.565 | 0.093 |
| proportion_in_groups | 5.882 | 18.559 | 0.071 |
| selection_metric | 5.876 | 18.573 | 0.048 |
| gini_coefficient | 5.810 | 18.281 | 0.080 |
| time_gap_evenness_metric | 5.802 | 18.370 | 0.031 |
| std_group_size | 5.790 | 18.218 | 0.019 |
| total_groups | 5.745 | 18.169 | 0.027 |
| total_race_duration | 5.694 | 18.186 | 0.033 |
| riders_in_groups | 5.641 | 17.754 | 0.009 |
| variance_absolute | 5.457 | 19.244 | 0.056 |
| std_deviation_absolute | 5.408 | 17.420 | 0.033 |
| variance_normalized | 5.323 | 19.434 | 0.025 |
| skewness_normalized | 5.216 | 16.251 | 0.012 |

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
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.091 | 19.250 | 0.025 |
| avg_group_size | 6.005 | 18.941 | 0.095 |
| proportion_in_groups | 5.987 | 18.921 | 0.067 |
| selection_metric | 5.983 | 18.920 | 0.048 |
| clumpiness_score | 5.961 | 18.742 | 0.027 |
| time_gap_evenness_metric | 5.917 | 18.759 | 0.030 |
| winning_time | 5.917 | 18.811 | 0.005 |
| std_group_size | 5.907 | 18.601 | 0.035 |
| gini_coefficient | 5.905 | 18.608 | 0.077 |
| total_groups | 5.861 | 18.551 | 0.023 |
| total_race_duration | 5.793 | 18.521 | 0.037 |
| riders_in_groups | 5.750 | 18.132 | 0.010 |
| variance_absolute | 5.599 | 19.568 | 0.058 |
| std_deviation_absolute | 5.505 | 17.740 | 0.033 |
| variance_normalized | 5.481 | 19.763 | 0.017 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- largest_group_position
- skewness_absolute
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
| clumpiness_score | 6.578 | 20.856 | 0.055 |
| biggest_group_metric | 6.534 | 20.740 | 0.025 |
| selection_metric | 6.470 | 20.583 | 0.044 |
| gini_coefficient | 6.372 | 20.126 | 0.054 |
| avg_group_size | 6.359 | 20.254 | 0.031 |
| std_group_size | 6.247 | 19.673 | 0.047 |
| largest_group_size | 6.176 | 19.648 | 0.023 |
| proportion_in_groups | 6.170 | 19.610 | 0.011 |
| variance_absolute | 6.164 | 19.901 | 0.031 |
| total_race_duration | 6.144 | 19.533 | 0.043 |
| total_groups | 6.127 | 19.514 | 0.036 |
| 50th_percentile_gap | 6.107 | 19.395 | 0.092 |
| time_gap_evenness_metric | 6.102 | 19.404 | 0.012 |
| skewness_normalized | 5.783 | 18.141 | 0.010 |

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
| biggest_group_metric | 6.026 | 19.031 | 0.040 |
| clumpiness_score | 5.963 | 18.756 | 0.022 |
| avg_group_size | 5.944 | 18.753 | 0.090 |
| proportion_in_groups | 5.933 | 18.699 | 0.065 |
| selection_metric | 5.911 | 18.700 | 0.026 |
| largest_group_position | 5.881 | 18.574 | 0.007 |
| gini_coefficient | 5.845 | 18.368 | 0.076 |
| time_gap_evenness_metric | 5.831 | 18.443 | 0.028 |
| std_group_size | 5.811 | 18.282 | 0.020 |
| total_race_duration | 5.737 | 18.275 | 0.038 |
| total_groups | 5.733 | 18.152 | 0.024 |
| variance_absolute | 5.641 | 19.245 | 0.057 |
| variance_normalized | 5.366 | 19.615 | 0.047 |
| skewness_normalized | 5.213 | 16.208 | 0.018 |

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
| avg_group_size | 5.836 | 18.306 | 0.194 |
| selection_metric | 5.786 | 18.267 | 0.062 |
| clumpiness_score | 5.784 | 18.180 | 0.011 |
| proportion_in_groups | 5.776 | 18.265 | 0.010 |
| time_gap_evenness_metric | 5.711 | 18.047 | 0.064 |
| std_group_size | 5.691 | 17.897 | 0.018 |
| total_groups | 5.649 | 17.867 | 0.043 |
| total_race_duration | 5.597 | 17.830 | 0.039 |
| variance_absolute | 5.511 | 18.711 | 0.055 |
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
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| clumpiness_score | 6.667 | 21.123 | 0.050 |
| biggest_group_metric | 6.610 | 20.989 | 0.029 |
| largest_group_position | 6.448 | 20.490 | 0.006 |
| shannon_entropy_absolute | 6.436 | 20.487 | 0.020 |
| selection_metric | 6.407 | 20.347 | 0.028 |
| avg_group_size | 6.400 | 20.397 | 0.020 |
| gini_coefficient | 6.383 | 20.115 | 0.054 |
| total_finishers | 6.349 | 19.990 | 0.007 |
| std_group_size | 6.322 | 19.946 | 0.028 |
| total_race_duration | 6.267 | 19.913 | 0.026 |
| largest_group_size | 6.259 | 19.908 | 0.032 |
| proportion_in_groups | 6.249 | 19.849 | 0.012 |
| variance_absolute | 6.242 | 19.967 | 0.038 |
| 50th_percentile_gap | 6.238 | 19.785 | 0.091 |
| total_groups | 6.144 | 19.562 | 0.027 |

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

**Low Score** (5 features):
- abandon_ratio
- kurtosis_normalized
- skewness_normalized
- time_gap_evenness_metric
- winning_time

---

### Scenario 10: 60th percentile - stage_one_day

- **Races analyzed**: 8287
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.032 | 19.036 | 0.062 |
| clumpiness_score | 5.982 | 18.818 | 0.017 |
| avg_group_size | 5.951 | 18.796 | 0.082 |
| proportion_in_groups | 5.922 | 18.684 | 0.048 |
| selection_metric | 5.909 | 18.678 | 0.023 |
| largest_group_position | 5.904 | 18.623 | 0.011 |
| gini_coefficient | 5.844 | 18.330 | 0.069 |
| std_group_size | 5.824 | 18.338 | 0.018 |
| largest_group_size | 5.821 | 18.415 | 0.009 |
| time_gap_evenness_metric | 5.813 | 18.374 | 0.034 |
| total_groups | 5.738 | 18.166 | 0.020 |
| variance_absolute | 5.717 | 18.979 | 0.044 |
| total_race_duration | 5.693 | 18.127 | 0.029 |
| variance_normalized | 5.368 | 19.635 | 0.049 |
| skewness_absolute | 5.184 | 16.089 | 0.019 |

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
| clumpiness_score | 5.740 | 18.021 | 0.015 |
| selection_metric | 5.719 | 18.049 | 0.030 |
| proportion_in_groups | 5.715 | 18.018 | 0.022 |
| largest_group_position | 5.699 | 17.947 | 0.009 |
| gini_coefficient | 5.653 | 17.681 | 0.099 |
| std_group_size | 5.637 | 17.719 | 0.021 |
| largest_group_size | 5.634 | 17.781 | 0.022 |
| time_gap_evenness_metric | 5.621 | 17.757 | 0.017 |
| total_groups | 5.553 | 17.564 | 0.010 |
| variance_absolute | 5.518 | 18.235 | 0.038 |
| total_race_duration | 5.518 | 17.533 | 0.029 |
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
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.895 | 21.895 | 0.057 |
| clumpiness_score | 6.877 | 21.806 | 0.037 |
| largest_group_position | 6.717 | 21.349 | 0.008 |
| avg_group_size | 6.606 | 21.077 | 0.022 |
| total_finishers | 6.593 | 20.786 | 0.022 |
| gini_coefficient | 6.591 | 20.790 | 0.041 |
| selection_metric | 6.588 | 20.940 | 0.025 |
| shannon_entropy_absolute | 6.561 | 20.888 | 0.005 |
| 50th_percentile_gap | 6.552 | 20.819 | 0.069 |
| std_group_size | 6.534 | 20.675 | 0.048 |
| total_race_duration | 6.534 | 20.777 | 0.023 |
| kurtosis_normalized | 6.529 | 20.806 | 0.006 |
| proportion_in_groups | 6.522 | 20.746 | 0.006 |
| largest_group_size | 6.507 | 20.691 | 0.051 |
| total_groups | 6.411 | 20.433 | 0.013 |

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

**Low Score** (5 features):
- abandon_ratio
- skewness_normalized
- time_gap_evenness_metric
- variance_absolute
- winning_time

---

### Scenario 13: 70th percentile - stage_one_day

- **Races analyzed**: 8347
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.003 | 18.885 | 0.120 |
| clumpiness_score | 5.934 | 18.646 | 0.029 |
| avg_group_size | 5.881 | 18.610 | 0.043 |
| largest_group_position | 5.876 | 18.530 | 0.011 |
| proportion_in_groups | 5.875 | 18.568 | 0.012 |
| shannon_entropy_absolute | 5.874 | 18.621 | 0.014 |
| selection_metric | 5.829 | 18.410 | 0.020 |
| gini_coefficient | 5.789 | 18.103 | 0.073 |
| largest_group_size | 5.766 | 18.228 | 0.024 |
| time_gap_evenness_metric | 5.753 | 18.177 | 0.028 |
| std_group_size | 5.751 | 18.083 | 0.030 |
| variance_absolute | 5.707 | 18.599 | 0.045 |
| total_groups | 5.667 | 17.933 | 0.011 |
| total_race_duration | 5.656 | 17.998 | 0.022 |
| variance_normalized | 5.319 | 19.500 | 0.022 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- kurtosis_absolute
- riders_in_groups
- skewness_absolute
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
| clumpiness_score | 5.827 | 18.279 | 0.030 |
| avg_group_size | 5.809 | 18.354 | 0.043 |
| proportion_in_groups | 5.802 | 18.315 | 0.013 |
| largest_group_position | 5.797 | 18.265 | 0.010 |
| selection_metric | 5.775 | 18.230 | 0.018 |
| gini_coefficient | 5.717 | 17.876 | 0.071 |
| largest_group_size | 5.696 | 17.979 | 0.031 |
| time_gap_evenness_metric | 5.691 | 17.969 | 0.021 |
| std_group_size | 5.684 | 17.880 | 0.019 |
| variance_absolute | 5.620 | 18.256 | 0.041 |
| total_groups | 5.616 | 17.759 | 0.009 |
| total_race_duration | 5.581 | 17.741 | 0.018 |
| variance_normalized | 5.297 | 19.156 | 0.030 |
| skewness_absolute | 5.139 | 15.974 | 0.025 |

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
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.029 | 22.335 | 0.050 |
| clumpiness_score | 7.002 | 22.212 | 0.020 |
| largest_group_position | 6.857 | 21.788 | 0.009 |
| avg_group_size | 6.762 | 21.590 | 0.026 |
| total_finishers | 6.704 | 21.169 | 0.014 |
| abandon_ratio | 6.690 | 21.090 | 0.006 |
| shannon_entropy_absolute | 6.671 | 21.213 | 0.009 |
| gini_coefficient | 6.668 | 21.045 | 0.033 |
| total_race_duration | 6.665 | 21.183 | 0.026 |
| selection_metric | 6.664 | 21.173 | 0.019 |
| kurtosis_normalized | 6.644 | 21.139 | 0.008 |
| proportion_in_groups | 6.638 | 21.117 | 0.009 |
| 50th_percentile_gap | 6.628 | 21.038 | 0.083 |
| largest_group_size | 6.615 | 21.010 | 0.071 |
| std_group_size | 6.607 | 20.931 | 0.054 |

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

**Low Score** (5 features):
- skewness_normalized
- time_gap_evenness_metric
- total_groups
- variance_absolute
- winning_time

---

### Scenario 16: 80th percentile - stage_one_day

- **Races analyzed**: 8382
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.108 | 19.295 | 0.046 |
| clumpiness_score | 6.040 | 19.001 | 0.020 |
| proportion_in_groups | 6.020 | 19.012 | 0.064 |
| largest_group_position | 6.008 | 18.951 | 0.011 |
| selection_metric | 6.007 | 18.941 | 0.045 |
| avg_group_size | 5.987 | 18.934 | 0.060 |
| shannon_entropy_absolute | 5.974 | 18.837 | 0.101 |
| winning_time | 5.934 | 18.856 | 0.006 |
| gini_coefficient | 5.871 | 18.381 | 0.009 |
| largest_group_size | 5.870 | 18.579 | 0.015 |
| time_gap_evenness_metric | 5.864 | 18.530 | 0.039 |
| std_group_size | 5.856 | 18.450 | 0.023 |
| variance_absolute | 5.814 | 18.811 | 0.010 |
| total_finishers | 5.778 | 18.045 | 0.005 |
| total_groups | 5.753 | 18.184 | 0.022 |

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

**Low Score** (6 features):
- abandon_ratio
- kurtosis_normalized
- riders_in_groups
- skewness_normalized
- total_race_duration
- variance_normalized

---

### Scenario 17: 80th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.003 | 18.856 | 0.156 |
| selection_metric | 5.891 | 18.613 | 0.016 |
| proportion_in_groups | 5.887 | 18.599 | 0.008 |
| clumpiness_score | 5.882 | 18.473 | 0.014 |
| largest_group_position | 5.869 | 18.502 | 0.010 |
| avg_group_size | 5.852 | 18.502 | 0.036 |
| shannon_entropy_absolute | 5.834 | 18.468 | 0.021 |
| gini_coefficient | 5.766 | 18.015 | 0.068 |
| time_gap_evenness_metric | 5.754 | 18.178 | 0.020 |
| largest_group_size | 5.750 | 18.175 | 0.016 |
| std_group_size | 5.742 | 18.086 | 0.019 |
| kurtosis_normalized | 5.722 | 18.175 | 0.005 |
| variance_absolute | 5.680 | 18.277 | 0.023 |
| total_groups | 5.645 | 17.841 | 0.008 |
| total_race_duration | 5.633 | 17.907 | 0.009 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- riders_in_groups
- skewness_normalized
- total_finishers
- variance_normalized
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
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 7.215 | 22.998 | 0.021 |
| clumpiness_score | 7.128 | 22.604 | 0.043 |
| largest_group_position | 7.081 | 22.526 | 0.007 |
| avg_group_size | 6.915 | 22.100 | 0.065 |
| total_finishers | 6.897 | 21.812 | 0.005 |
| 50th_percentile_gap | 6.860 | 21.808 | 0.080 |
| shannon_entropy_normalized | 6.858 | 21.866 | 0.027 |
| gini_coefficient | 6.798 | 21.499 | 0.011 |
| proportion_in_groups | 6.791 | 21.637 | 0.007 |
| total_race_duration | 6.790 | 21.599 | 0.031 |
| largest_group_size | 6.780 | 21.617 | 0.033 |
| selection_metric | 6.759 | 21.489 | 0.015 |
| kurtosis_normalized | 6.729 | 21.592 | 0.007 |
| shannon_entropy_absolute | 6.721 | 21.361 | 0.023 |
| std_group_size | 6.710 | 21.330 | 0.027 |

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

**Low Score** (6 features):
- abandon_ratio
- skewness_normalized
- time_gap_evenness_metric
- total_groups
- variance_absolute
- winning_time

---

