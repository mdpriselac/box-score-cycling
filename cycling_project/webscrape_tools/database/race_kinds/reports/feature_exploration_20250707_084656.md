# Feature Selection Exploration Report

Generated: 2025-07-07 08:47:19

## Executive Summary

- **Total scenarios analyzed**: 6
- **Max features per scenario**: 15
- **Total races analyzed**: 49,966
- **Average features selected**: 14.8

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| biggest_group_metric | 6 | 100.0% |
| clumpiness_score | 6 | 100.0% |
| avg_group_size | 6 | 100.0% |
| proportion_in_groups | 6 | 100.0% |
| largest_group_position | 6 | 100.0% |
| gini_coefficient | 6 | 100.0% |
| time_gap_evenness_metric | 6 | 100.0% |
| variance_absolute | 6 | 100.0% |
| selection_metric | 5 | 83.3% |
| std_group_size | 5 | 83.3% |
| total_groups | 5 | 83.3% |
| largest_group_size | 5 | 83.3% |
| shannon_entropy_absolute | 4 | 66.7% |
| total_race_duration | 3 | 50.0% |
| variance_normalized | 3 | 50.0% |

### Feature Removal Patterns

- **High correlation removals**: 96 (avg 16.0 per scenario)
- **Low variance removals**: 1 (avg 0.2 per scenario)
- **Redundancy removals**: 92 (avg 15.3 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 50th percentile - stage_one_day

- **Races analyzed**: 8146
- **Features available**: 37
- **Features selected**: 14

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.945 | 18.761 | 0.040 |
| clumpiness_score | 5.866 | 18.436 | 0.022 |
| avg_group_size | 5.865 | 18.488 | 0.090 |
| proportion_in_groups | 5.854 | 18.434 | 0.065 |
| selection_metric | 5.832 | 18.435 | 0.026 |
| largest_group_position | 5.803 | 18.313 | 0.007 |
| gini_coefficient | 5.767 | 18.109 | 0.076 |
| time_gap_evenness_metric | 5.753 | 18.182 | 0.028 |
| std_group_size | 5.734 | 18.024 | 0.020 |
| total_groups | 5.675 | 17.961 | 0.024 |
| total_race_duration | 5.660 | 18.017 | 0.038 |
| variance_absolute | 5.552 | 18.950 | 0.057 |
| variance_normalized | 5.282 | 19.337 | 0.047 |
| skewness_normalized | 5.185 | 16.111 | 0.018 |

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

### Scenario 2: 60th percentile - stage_one_day

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
| largest_group_position | 5.830 | 18.375 | 0.011 |
| gini_coefficient | 5.770 | 18.086 | 0.069 |
| std_group_size | 5.751 | 18.094 | 0.018 |
| largest_group_size | 5.747 | 18.169 | 0.009 |
| time_gap_evenness_metric | 5.739 | 18.129 | 0.034 |
| total_groups | 5.673 | 17.948 | 0.020 |
| variance_absolute | 5.649 | 18.751 | 0.044 |
| total_race_duration | 5.643 | 17.961 | 0.029 |
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

### Scenario 3: 70th percentile - stage_one_day

- **Races analyzed**: 8347
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.062 | 19.082 | 0.120 |
| clumpiness_score | 5.993 | 18.841 | 0.029 |
| avg_group_size | 5.940 | 18.804 | 0.043 |
| largest_group_position | 5.935 | 18.725 | 0.011 |
| proportion_in_groups | 5.934 | 18.763 | 0.012 |
| shannon_entropy_absolute | 5.933 | 18.816 | 0.014 |
| selection_metric | 5.872 | 18.552 | 0.020 |
| gini_coefficient | 5.847 | 18.294 | 0.073 |
| largest_group_size | 5.824 | 18.420 | 0.024 |
| time_gap_evenness_metric | 5.810 | 18.367 | 0.028 |
| std_group_size | 5.808 | 18.272 | 0.030 |
| variance_absolute | 5.771 | 18.815 | 0.045 |
| total_groups | 5.714 | 18.090 | 0.011 |
| total_race_duration | 5.713 | 18.187 | 0.022 |
| variance_normalized | 5.381 | 19.704 | 0.022 |

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

### Scenario 4: 80th percentile - stage_one_day

- **Races analyzed**: 8382
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.149 | 19.429 | 0.046 |
| clumpiness_score | 6.080 | 19.131 | 0.020 |
| proportion_in_groups | 6.059 | 19.143 | 0.064 |
| largest_group_position | 6.048 | 19.082 | 0.011 |
| selection_metric | 6.046 | 19.073 | 0.045 |
| avg_group_size | 6.022 | 19.051 | 0.060 |
| shannon_entropy_absolute | 6.013 | 18.968 | 0.101 |
| winning_time | 6.004 | 19.088 | 0.006 |
| gini_coefficient | 5.909 | 18.508 | 0.009 |
| largest_group_size | 5.909 | 18.709 | 0.015 |
| time_gap_evenness_metric | 5.903 | 18.660 | 0.039 |
| std_group_size | 5.894 | 18.578 | 0.023 |
| variance_absolute | 5.825 | 18.847 | 0.010 |
| total_finishers | 5.816 | 18.172 | 0.005 |
| total_groups | 5.799 | 18.334 | 0.022 |

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

### Scenario 5: 90th percentile - stage_one_day

- **Races analyzed**: 8396
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.080 | 19.171 | 0.065 |
| proportion_in_groups | 5.993 | 18.929 | 0.061 |
| clumpiness_score | 5.976 | 18.736 | 0.042 |
| largest_group_position | 5.976 | 18.823 | 0.009 |
| selection_metric | 5.962 | 18.792 | 0.010 |
| avg_group_size | 5.899 | 18.617 | 0.067 |
| winning_time | 5.882 | 18.689 | 0.006 |
| largest_group_size | 5.832 | 18.421 | 0.038 |
| shannon_entropy_absolute | 5.828 | 18.345 | 0.076 |
| time_gap_evenness_metric | 5.828 | 18.406 | 0.039 |
| std_group_size | 5.819 | 18.357 | 0.027 |
| riders_in_groups | 5.782 | 18.195 | 0.005 |
| kurtosis_normalized | 5.759 | 18.278 | 0.008 |
| gini_coefficient | 5.752 | 18.028 | 0.008 |
| variance_absolute | 5.743 | 18.489 | 0.006 |

#### Removed Features by Reason

**Low Score** (7 features):
- 5th_percentile_gap
- abandon_ratio
- skewness_absolute
- total_finishers
- total_groups
- total_race_duration
- variance_normalized

**High Correlation** (15 features):
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

---

### Scenario 6: 100th percentile - stage_one_day

- **Races analyzed**: 8408
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.561 | 17.503 | 0.061 |
| proportion_in_groups | 5.506 | 17.303 | 0.087 |
| largest_group_position | 5.468 | 17.167 | 0.005 |
| clumpiness_score | 5.425 | 16.906 | 0.038 |
| winning_time | 5.401 | 17.107 | 0.008 |
| shannon_entropy_normalized | 5.378 | 16.910 | 0.089 |
| gini_coefficient | 5.331 | 16.730 | 0.036 |
| largest_group_size | 5.329 | 16.780 | 0.034 |
| variance_absolute | 5.297 | 16.962 | 0.008 |
| time_gap_evenness_metric | 5.295 | 16.644 | 0.068 |
| shannon_entropy_absolute | 5.280 | 16.579 | 0.041 |
| kurtosis_normalized | 5.277 | 16.665 | 0.014 |
| avg_group_size | 5.247 | 16.524 | 0.072 |
| total_groups | 5.202 | 16.348 | 0.011 |
| skewness_normalized | 5.146 | 16.176 | 0.026 |

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
- kurtosis_absolute
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
- included_finishers
- kurtosis_absolute
- ... and 5 more

**Low Variance** (1 features):
- abandon_ratio

**Low Score** (4 features):
- 5th_percentile_gap
- riders_in_groups
- selection_metric
- variance_normalized

---

