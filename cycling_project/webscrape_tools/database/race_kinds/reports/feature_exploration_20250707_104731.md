# Feature Selection Exploration Report

Generated: 2025-07-07 10:47:36

## Executive Summary

- **Total scenarios analyzed**: 12
- **Max features per scenario**: 20
- **Total races analyzed**: 2,896
- **Average features selected**: 9.8

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| variance_absolute | 12 | 100.0% |
| riders_in_groups | 12 | 100.0% |
| largest_group_size | 11 | 91.7% |
| total_groups | 9 | 75.0% |
| time_gap_evenness_metric | 8 | 66.7% |
| biggest_group_metric | 7 | 58.3% |
| gini_coefficient | 6 | 50.0% |
| shannon_entropy_normalized | 6 | 50.0% |
| total_race_duration | 6 | 50.0% |
| variance_normalized | 5 | 41.7% |
| clumpiness_score | 5 | 41.7% |
| shannon_entropy_absolute | 4 | 33.3% |
| skewness_absolute | 4 | 33.3% |
| skewness_normalized | 4 | 33.3% |
| selection_metric | 3 | 25.0% |

### Feature Removal Patterns

- **High correlation removals**: 240 (avg 20.0 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 227 (avg 18.9 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - gc - wt

- **Races analyzed**: 195
- **Features available**: 37
- **Features selected**: 6

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 4.998 | 15.519 | 0.105 |
| variance_normalized | 4.930 | 15.794 | 0.006 |
| largest_group_size | 4.718 | 15.088 | 0.009 |
| selection_metric | 4.665 | 14.723 | 0.006 |
| riders_in_groups | 4.643 | 14.746 | 0.008 |
| gini_coefficient | 4.319 | 13.418 | 0.005 |

#### Removed Features by Reason

**Low Score** (10 features):
- abandon_ratio
- biggest_group_metric
- clumpiness_score
- kurtosis_normalized
- largest_group_position
- skewness_absolute
- std_group_size
- time_gap_evenness_metric
- total_finishers
- total_groups

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

**Redundant** (20 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- 5th_percentile_gap
- avg_group_size
- ... and 10 more

---

### Scenario 2: 30th percentile - gc - pro

- **Races analyzed**: 204
- **Features available**: 37
- **Features selected**: 13

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.597 | 21.268 | 0.018 |
| 50th_percentile_gap | 6.235 | 19.761 | 0.046 |
| 10th_percentile_gap | 6.213 | 19.667 | 0.025 |
| riders_in_groups | 6.208 | 19.805 | 0.033 |
| shannon_entropy_normalized | 6.186 | 19.603 | 0.006 |
| total_race_duration | 6.157 | 19.496 | 0.031 |
| largest_group_size | 6.156 | 19.674 | 0.042 |
| kurtosis_absolute | 6.140 | 19.563 | 0.017 |
| total_groups | 6.091 | 19.348 | 0.007 |
| time_gap_evenness_metric | 6.072 | 19.184 | 0.073 |
| shannon_entropy_absolute | 6.065 | 19.128 | 0.012 |
| winning_time | 5.995 | 18.856 | 0.006 |
| skewness_absolute | 5.688 | 17.751 | 0.006 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- biggest_group_metric
- gini_coefficient
- largest_group_position
- selection_metric
- total_finishers

**High Correlation** (17 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- clumpiness_score
- included_finishers
- ... and 7 more

**Redundant** (17 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- avg_group_size
- clumpiness_score
- included_finishers
- ... and 7 more

---

### Scenario 3: 40th percentile - gc - wt

- **Races analyzed**: 216
- **Features available**: 37
- **Features selected**: 9

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 4.454 | 13.811 | 0.048 |
| variance_normalized | 4.430 | 14.071 | 0.015 |
| biggest_group_metric | 4.301 | 13.436 | 0.006 |
| largest_group_size | 4.247 | 13.480 | 0.005 |
| time_gap_evenness_metric | 4.212 | 13.191 | 0.006 |
| clumpiness_score | 4.212 | 13.047 | 0.052 |
| total_groups | 4.201 | 13.073 | 0.050 |
| riders_in_groups | 4.161 | 13.086 | 0.090 |
| selection_metric | 4.157 | 12.993 | 0.008 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- gini_coefficient
- largest_group_position
- skewness_normalized
- std_group_size
- total_finishers

**High Correlation** (22 features):
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
- ... and 12 more

**Redundant** (20 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- avg_group_size
- ... and 10 more

---

### Scenario 4: 40th percentile - gc - pro

- **Races analyzed**: 269
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.388 | 20.651 | 0.010 |
| kurtosis_absolute | 6.162 | 19.779 | 0.007 |
| largest_group_size | 6.003 | 19.138 | 0.053 |
| shannon_entropy_normalized | 5.996 | 18.958 | 0.009 |
| riders_in_groups | 5.983 | 19.020 | 0.054 |
| time_gap_evenness_metric | 5.926 | 18.711 | 0.056 |
| total_race_duration | 5.912 | 18.709 | 0.010 |
| 50th_percentile_gap | 5.898 | 18.623 | 0.056 |
| total_groups | 5.855 | 18.556 | 0.005 |
| winning_time | 5.819 | 18.262 | 0.007 |
| gini_coefficient | 5.621 | 17.584 | 0.007 |

#### Removed Features by Reason

**Low Score** (7 features):
- abandon_ratio
- biggest_group_metric
- largest_group_position
- selection_metric
- shannon_entropy_absolute
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
- avg_group_size
- clumpiness_score
- ... and 8 more

**Redundant** (17 features):
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- avg_group_size
- clumpiness_score
- ... and 7 more

---

### Scenario 5: 50th percentile - gc - wt

- **Races analyzed**: 218
- **Features available**: 37
- **Features selected**: 9

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.810 | 11.646 | 0.069 |
| variance_normalized | 3.761 | 11.898 | 0.010 |
| largest_group_size | 3.690 | 11.584 | 0.007 |
| clumpiness_score | 3.634 | 11.114 | 0.035 |
| time_gap_evenness_metric | 3.621 | 11.200 | 0.009 |
| selection_metric | 3.599 | 11.119 | 0.011 |
| riders_in_groups | 3.579 | 11.128 | 0.086 |
| total_groups | 3.575 | 11.001 | 0.040 |
| skewness_absolute | 3.516 | 10.830 | 0.011 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- biggest_group_metric
- gini_coefficient
- largest_group_position
- std_group_size
- total_finishers

**High Correlation** (22 features):
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
- ... and 12 more

**Redundant** (21 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 50th_percentile_gap
- avg_group_size
- ... and 11 more

---

### Scenario 6: 50th percentile - gc - pro

- **Races analyzed**: 282
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.461 | 20.918 | 0.011 |
| kurtosis_normalized | 6.246 | 20.125 | 0.008 |
| biggest_group_metric | 6.122 | 19.285 | 0.006 |
| shannon_entropy_normalized | 6.053 | 19.201 | 0.009 |
| 50th_percentile_gap | 6.048 | 19.136 | 0.035 |
| riders_in_groups | 6.036 | 19.165 | 0.043 |
| 5th_percentile_gap | 6.029 | 19.072 | 0.007 |
| largest_group_size | 6.023 | 19.205 | 0.029 |
| time_gap_evenness_metric | 5.980 | 18.915 | 0.038 |
| total_race_duration | 5.973 | 18.856 | 0.018 |
| total_groups | 5.916 | 18.737 | 0.006 |
| shannon_entropy_absolute | 5.704 | 17.904 | 0.006 |
| gini_coefficient | 5.614 | 17.601 | 0.007 |
| skewness_normalized | 5.289 | 16.616 | 0.008 |

#### Removed Features by Reason

**Low Score** (5 features):
- abandon_ratio
- largest_group_position
- selection_metric
- total_finishers
- winning_time

**High Correlation** (18 features):
- 10th_percentile_gap
- 15th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- avg_group_size
- clumpiness_score
- ... and 8 more

**Redundant** (16 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- avg_group_size
- clumpiness_score
- included_finishers
- ... and 6 more

---

### Scenario 7: 60th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 8

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.664 | 11.203 | 0.050 |
| variance_normalized | 3.614 | 11.415 | 0.009 |
| biggest_group_metric | 3.552 | 10.857 | 0.006 |
| clumpiness_score | 3.479 | 10.618 | 0.020 |
| riders_in_groups | 3.459 | 10.670 | 0.050 |
| skewness_normalized | 3.396 | 10.517 | 0.013 |
| total_groups | 3.391 | 10.446 | 0.016 |
| gini_coefficient | 3.350 | 10.147 | 0.008 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- largest_group_position
- largest_group_size
- total_finishers

**High Correlation** (23 features):
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
- ... and 13 more

**Redundant** (22 features):
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
- ... and 12 more

---

### Scenario 8: 60th percentile - gc - pro

- **Races analyzed**: 284
- **Features available**: 37
- **Features selected**: 8

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.302 | 20.399 | 0.007 |
| shannon_entropy_normalized | 5.888 | 18.699 | 0.025 |
| riders_in_groups | 5.872 | 18.656 | 0.034 |
| largest_group_size | 5.863 | 18.736 | 0.030 |
| total_race_duration | 5.843 | 18.430 | 0.015 |
| time_gap_evenness_metric | 5.771 | 18.249 | 0.076 |
| shannon_entropy_absolute | 5.606 | 17.602 | 0.014 |
| skewness_normalized | 5.390 | 16.989 | 0.007 |

#### Removed Features by Reason

**Low Score** (8 features):
- abandon_ratio
- biggest_group_metric
- gini_coefficient
- largest_group_position
- selection_metric
- total_finishers
- total_groups
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
- 50th_percentile_gap
- avg_group_size
- ... and 9 more

**Redundant** (16 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- avg_group_size
- clumpiness_score
- ... and 6 more

---

### Scenario 9: 70th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 8

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.574 | 10.921 | 0.045 |
| largest_group_size | 3.517 | 10.985 | 0.006 |
| biggest_group_metric | 3.474 | 10.654 | 0.007 |
| riders_in_groups | 3.387 | 10.444 | 0.078 |
| clumpiness_score | 3.369 | 10.258 | 0.021 |
| total_groups | 3.366 | 10.316 | 0.059 |
| skewness_normalized | 3.352 | 10.367 | 0.010 |
| gini_coefficient | 3.258 | 9.854 | 0.006 |

#### Removed Features by Reason

**Low Score** (4 features):
- abandon_ratio
- largest_group_position
- total_finishers
- variance_normalized

**High Correlation** (23 features):
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
- ... and 13 more

**Redundant** (25 features):
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
- ... and 15 more

---

### Scenario 10: 70th percentile - gc - pro

- **Races analyzed**: 284
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.428 | 20.822 | 0.011 |
| largest_group_position | 6.213 | 19.626 | 0.005 |
| std_deviation_absolute | 6.123 | 19.615 | 0.012 |
| largest_group_size | 6.092 | 19.492 | 0.008 |
| biggest_group_metric | 6.041 | 19.029 | 0.007 |
| riders_in_groups | 5.991 | 19.036 | 0.025 |
| total_race_duration | 5.925 | 18.713 | 0.011 |
| time_gap_evenness_metric | 5.876 | 18.579 | 0.013 |
| shannon_entropy_normalized | 5.837 | 18.475 | 0.008 |
| total_groups | 5.817 | 18.419 | 0.006 |
| skewness_absolute | 5.598 | 17.687 | 0.005 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- gini_coefficient
- selection_metric
- shannon_entropy_absolute
- total_finishers
- winning_time

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
- avg_group_size
- ... and 8 more

**Redundant** (15 features):
- 15th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- 5th_percentile_gap
- avg_group_size
- clumpiness_score
- included_finishers
- ... and 5 more

---

### Scenario 11: 80th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 6

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.587 | 10.852 | 0.074 |
| variance_normalized | 3.516 | 11.071 | 0.007 |
| largest_group_size | 3.461 | 10.843 | 0.009 |
| largest_group_position | 3.453 | 10.484 | 0.021 |
| biggest_group_metric | 3.424 | 10.547 | 0.012 |
| riders_in_groups | 3.363 | 10.440 | 0.006 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- clumpiness_score
- gini_coefficient
- skewness_normalized
- total_finishers
- total_groups

**High Correlation** (23 features):
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
- ... and 13 more

**Redundant** (24 features):
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
- ... and 14 more

---

### Scenario 12: 80th percentile - gc - pro

- **Races analyzed**: 284
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 6.633 | 21.466 | 0.009 |
| largest_group_size | 6.341 | 20.327 | 0.022 |
| std_deviation_absolute | 6.232 | 19.907 | 0.015 |
| biggest_group_metric | 6.218 | 19.600 | 0.007 |
| 5th_percentile_gap | 6.195 | 19.661 | 0.018 |
| riders_in_groups | 6.191 | 19.709 | 0.036 |
| clumpiness_score | 6.097 | 19.303 | 0.028 |
| total_groups | 6.076 | 19.293 | 0.005 |
| total_race_duration | 6.049 | 19.141 | 0.020 |
| time_gap_evenness_metric | 6.040 | 19.100 | 0.062 |
| shannon_entropy_normalized | 6.038 | 19.176 | 0.019 |
| gini_coefficient | 5.891 | 18.540 | 0.013 |
| shannon_entropy_absolute | 5.732 | 18.060 | 0.013 |
| skewness_absolute | 5.696 | 18.037 | 0.005 |

#### Removed Features by Reason

**Low Score** (6 features):
- abandon_ratio
- largest_group_position
- selection_metric
- std_deviation_normalized
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
- avg_group_size
- ... and 7 more

**Redundant** (14 features):
- 10th_percentile_gap
- 20th_percentile_gap
- 25th_percentile_gap
- 30th_percentile_gap
- 35th_percentile_gap
- 40th_percentile_gap
- 45th_percentile_gap
- avg_group_size
- included_finishers
- kurtosis_normalized
- ... and 4 more

---

