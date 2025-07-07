# Feature Selection Exploration Report

Generated: 2025-07-07 08:35:52

## Executive Summary

- **Total scenarios analyzed**: 3
- **Max features per scenario**: 15
- **Total races analyzed**: 20,796
- **Average features selected**: 13.7

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| biggest_group_metric | 3 | 100.0% |
| avg_group_size | 3 | 100.0% |
| selection_metric | 3 | 100.0% |
| clumpiness_score | 3 | 100.0% |
| proportion_in_groups | 3 | 100.0% |
| time_gap_evenness_metric | 3 | 100.0% |
| std_group_size | 3 | 100.0% |
| total_race_duration | 3 | 100.0% |
| variance_absolute | 3 | 100.0% |
| total_groups | 2 | 66.7% |
| variance_normalized | 2 | 66.7% |
| largest_group_position | 2 | 66.7% |
| gini_coefficient | 2 | 66.7% |
| largest_group_size | 2 | 66.7% |
| skewness_absolute | 1 | 33.3% |

### Feature Removal Patterns

- **High correlation removals**: 48 (avg 16.0 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 47 (avg 15.7 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 50th percentile - stage

- **Races analyzed**: 6897
- **Features available**: 37
- **Features selected**: 11

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.853 | 18.448 | 0.076 |
| avg_group_size | 5.798 | 18.181 | 0.194 |
| selection_metric | 5.746 | 18.135 | 0.062 |
| clumpiness_score | 5.739 | 18.031 | 0.011 |
| proportion_in_groups | 5.738 | 18.141 | 0.010 |
| time_gap_evenness_metric | 5.674 | 17.924 | 0.064 |
| std_group_size | 5.654 | 17.776 | 0.018 |
| total_groups | 5.618 | 17.763 | 0.043 |
| total_race_duration | 5.561 | 17.708 | 0.039 |
| variance_absolute | 5.479 | 18.607 | 0.055 |
| variance_normalized | 5.227 | 18.962 | 0.011 |

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

### Scenario 2: 70th percentile - stage

- **Races analyzed**: 6948
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 5.912 | 18.556 | 0.145 |
| clumpiness_score | 5.822 | 18.264 | 0.030 |
| avg_group_size | 5.796 | 18.311 | 0.043 |
| proportion_in_groups | 5.789 | 18.272 | 0.013 |
| largest_group_position | 5.784 | 18.223 | 0.010 |
| selection_metric | 5.763 | 18.187 | 0.018 |
| gini_coefficient | 5.705 | 17.836 | 0.071 |
| largest_group_size | 5.684 | 17.936 | 0.031 |
| time_gap_evenness_metric | 5.678 | 17.927 | 0.021 |
| std_group_size | 5.672 | 17.842 | 0.019 |
| variance_absolute | 5.614 | 18.236 | 0.041 |
| total_groups | 5.593 | 17.682 | 0.009 |
| total_race_duration | 5.569 | 17.700 | 0.018 |
| variance_normalized | 5.283 | 19.111 | 0.030 |
| skewness_absolute | 5.085 | 15.793 | 0.025 |

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

### Scenario 3: 90th percentile - stage

- **Races analyzed**: 6951
- **Features available**: 37
- **Features selected**: 15

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| biggest_group_metric | 6.010 | 18.864 | 0.190 |
| selection_metric | 5.893 | 18.619 | 0.007 |
| proportion_in_groups | 5.888 | 18.643 | 0.008 |
| largest_group_position | 5.880 | 18.531 | 0.016 |
| clumpiness_score | 5.843 | 18.340 | 0.007 |
| avg_group_size | 5.792 | 18.301 | 0.050 |
| time_gap_evenness_metric | 5.746 | 18.174 | 0.024 |
| std_group_size | 5.734 | 18.095 | 0.027 |
| largest_group_size | 5.732 | 18.132 | 0.020 |
| shannon_entropy_absolute | 5.720 | 18.100 | 0.009 |
| kurtosis_normalized | 5.681 | 18.025 | 0.026 |
| gini_coefficient | 5.676 | 17.795 | 0.035 |
| variance_absolute | 5.651 | 18.145 | 0.008 |
| total_race_duration | 5.596 | 17.826 | 0.006 |
| 5th_percentile_gap | 5.458 | 17.415 | 0.011 |

#### Removed Features by Reason

**Low Score** (7 features):
- abandon_ratio
- riders_in_groups
- skewness_absolute
- total_finishers
- total_groups
- variance_normalized
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

