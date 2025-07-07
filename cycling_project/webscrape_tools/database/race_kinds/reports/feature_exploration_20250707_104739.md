# Feature Selection Exploration Report

Generated: 2025-07-07 10:47:41

## Executive Summary

- **Total scenarios analyzed**: 6
- **Max features per scenario**: 20
- **Total races analyzed**: 1,289
- **Average features selected**: 7.7

## Feature Selection Patterns

### Most Frequently Selected Features

| Feature | Times Selected | Frequency |
|---------|---------------|----------|
| variance_absolute | 6 | 100.0% |
| riders_in_groups | 6 | 100.0% |
| variance_normalized | 5 | 83.3% |
| largest_group_size | 5 | 83.3% |
| biggest_group_metric | 4 | 66.7% |
| clumpiness_score | 4 | 66.7% |
| total_groups | 4 | 66.7% |
| selection_metric | 3 | 50.0% |
| gini_coefficient | 3 | 50.0% |
| time_gap_evenness_metric | 2 | 33.3% |
| skewness_normalized | 2 | 33.3% |
| skewness_absolute | 1 | 16.7% |
| largest_group_position | 1 | 16.7% |

### Feature Removal Patterns

- **High correlation removals**: 133 (avg 22.2 per scenario)
- **Low variance removals**: 0 (avg 0.0 per scenario)
- **Redundancy removals**: 132 (avg 22.0 per scenario)

## Detailed Scenario Analysis

### Scenario 1: 30th percentile - gc - wt

- **Races analyzed**: 195
- **Features available**: 37
- **Features selected**: 6

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 4.783 | 14.805 | 0.105 |
| variance_normalized | 4.712 | 15.067 | 0.006 |
| largest_group_size | 4.495 | 14.344 | 0.009 |
| selection_metric | 4.466 | 14.057 | 0.006 |
| riders_in_groups | 4.443 | 14.080 | 0.008 |
| gini_coefficient | 4.129 | 12.784 | 0.005 |

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

### Scenario 2: 40th percentile - gc - wt

- **Races analyzed**: 216
- **Features available**: 37
- **Features selected**: 9

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 4.197 | 12.953 | 0.048 |
| variance_normalized | 4.168 | 13.196 | 0.015 |
| biggest_group_metric | 4.050 | 12.599 | 0.006 |
| largest_group_size | 4.013 | 12.702 | 0.005 |
| clumpiness_score | 3.974 | 12.255 | 0.052 |
| time_gap_evenness_metric | 3.963 | 12.360 | 0.006 |
| total_groups | 3.952 | 12.245 | 0.050 |
| riders_in_groups | 3.927 | 12.304 | 0.090 |
| selection_metric | 3.915 | 12.186 | 0.008 |

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

### Scenario 3: 50th percentile - gc - wt

- **Races analyzed**: 218
- **Features available**: 37
- **Features selected**: 9

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 4.009 | 12.307 | 0.069 |
| variance_normalized | 3.974 | 12.608 | 0.010 |
| largest_group_size | 3.890 | 12.251 | 0.007 |
| clumpiness_score | 3.833 | 11.776 | 0.035 |
| time_gap_evenness_metric | 3.825 | 11.880 | 0.009 |
| selection_metric | 3.790 | 11.754 | 0.011 |
| riders_in_groups | 3.780 | 11.799 | 0.086 |
| total_groups | 3.779 | 11.684 | 0.040 |
| skewness_absolute | 3.711 | 11.482 | 0.011 |

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

### Scenario 4: 60th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 8

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.442 | 10.464 | 0.050 |
| variance_normalized | 3.383 | 10.646 | 0.009 |
| biggest_group_metric | 3.342 | 10.160 | 0.006 |
| clumpiness_score | 3.264 | 9.904 | 0.020 |
| riders_in_groups | 3.229 | 9.902 | 0.050 |
| skewness_normalized | 3.184 | 9.809 | 0.013 |
| total_groups | 3.177 | 9.732 | 0.016 |
| gini_coefficient | 3.113 | 9.359 | 0.008 |

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

### Scenario 5: 70th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 8

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.620 | 11.073 | 0.045 |
| largest_group_size | 3.547 | 11.087 | 0.006 |
| biggest_group_metric | 3.518 | 10.802 | 0.007 |
| riders_in_groups | 3.430 | 10.586 | 0.078 |
| clumpiness_score | 3.418 | 10.422 | 0.021 |
| total_groups | 3.392 | 10.403 | 0.059 |
| skewness_normalized | 3.382 | 10.470 | 0.010 |
| gini_coefficient | 3.273 | 9.901 | 0.006 |

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

### Scenario 6: 80th percentile - gc - wt

- **Races analyzed**: 220
- **Features available**: 37
- **Features selected**: 6

#### Selected Features

| Feature | Final Score | Clustering Power | RF Importance |
|---------|------------|-----------------|---------------|
| variance_absolute | 3.338 | 10.021 | 0.074 |
| variance_normalized | 3.266 | 10.236 | 0.007 |
| largest_group_size | 3.230 | 10.072 | 0.009 |
| largest_group_position | 3.216 | 9.694 | 0.021 |
| biggest_group_metric | 3.186 | 9.753 | 0.012 |
| riders_in_groups | 3.111 | 9.601 | 0.006 |

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

