# Race Kind Method Comparison Report

**Percentile**: 40th
**Generated**: 2025-07-08 11:09:09
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 17
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.747 | 3 | 0.676 | -0.071 |
| hierarchical | 0.793 | 3 | 0.703 | -0.090 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.451 | 2 | 0.257 | -0.194 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.747

**Cluster Distribution**:

- Cluster 0: 442 races (96.3%)
- Cluster 1: 2 races (0.4%)
- Cluster 2: 15 races (3.3%)

**Evaluation Performance**:

- Training score: 0.747
- Evaluation score: 0.676
- Score difference: -0.071
- Evaluation races: 1060
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.793

**Cluster Distribution**:

- Cluster 0: 449 races (97.8%)
- Cluster 1: 2 races (0.4%)
- Cluster 2: 8 races (1.7%)

**Evaluation Performance**:

- Training score: 0.793
- Evaluation score: 0.703
- Score difference: -0.090
- Evaluation races: 1060
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'variance_normalized']
### Dbscan

- **Best eps**: 1.682
- **Best min_samples**: 5
- **Silhouette score**: 0.451
- **Clusters found**: 2
- **Noise points**: 110
- **Noise ratio**: 24.0%

**Evaluation Performance**:

- Training score: 0.451
- Evaluation score: 0.257
- Score difference: -0.194
- Evaluation races: 1060

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. largest_group_position
4. selection_metric
5. kurtosis_normalized
6. variance_absolute
7. avg_group_size
8. total_finishers
9. gini_coefficient
10. largest_group_size
11. std_group_size
12. std_deviation_absolute
13. 50th_percentile_gap
14. total_groups
15. total_race_duration
16. riders_in_groups
17. skewness_normalized

## Recommendations

1. **Best performing method**: hierarchical (score: 0.793)
2. **Best generalization**: kmeans (score difference: -0.071)
