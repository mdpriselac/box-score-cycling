# Race Kind Method Comparison Report

**Percentile**: 30th
**Generated**: 2025-07-08 11:09:08
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 12
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.948 | 3 | 0.867 | -0.081 |
| hierarchical | 0.948 | 3 | 0.975 | +0.027 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.529 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.948

**Cluster Distribution**:

- Cluster 0: 334 races (99.4%)
- Cluster 1: 1 races (0.3%)
- Cluster 2: 1 races (0.3%)

**Evaluation Performance**:

- Training score: 0.948
- Evaluation score: 0.867
- Score difference: -0.081
- Evaluation races: 675
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.948

**Cluster Distribution**:

- Cluster 0: 334 races (99.4%)
- Cluster 1: 1 races (0.3%)
- Cluster 2: 1 races (0.3%)

**Evaluation Performance**:

- Training score: 0.948
- Evaluation score: 0.975
- Score difference: +0.027
- Evaluation races: 675
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.230
- **Best min_samples**: 7
- **Silhouette score**: 0.529
- **Clusters found**: 2
- **Noise points**: 77
- **Noise ratio**: 22.9%

## Selected Features

1. selection_metric
2. variance_absolute
3. clumpiness_score
4. biggest_group_metric
5. avg_group_size
6. gini_coefficient
7. std_group_size
8. 50th_percentile_gap
9. total_groups
10. time_gap_evenness_metric
11. total_race_duration
12. std_deviation_absolute

## Recommendations

1. **Best performing method**: kmeans (score: 0.948)
2. **Best generalization**: hierarchical (score difference: +0.027)
