# Race Kind Method Comparison Report

**Percentile**: 30th
**Generated**: 2025-07-07 12:57:34
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 9
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.989 | 3 | 0.993 | +0.004 |
| hierarchical | 0.989 | 3 | 0.993 | +0.004 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.908 | 2 | 0.676 | -0.232 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.989

**Cluster Distribution**:

- Cluster 0: 397 races (99.5%)
- Cluster 1: 1 races (0.3%)
- Cluster 2: 1 races (0.3%)

**Evaluation Performance**:

- Training score: 0.989
- Evaluation score: 0.993
- Score difference: +0.004
- Evaluation races: 676
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.989

**Cluster Distribution**:

- Cluster 0: 397 races (99.5%)
- Cluster 1: 1 races (0.3%)
- Cluster 2: 1 races (0.3%)

**Evaluation Performance**:

- Training score: 0.989
- Evaluation score: 0.993
- Score difference: +0.004
- Evaluation races: 676
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric']
### Dbscan

- **Best eps**: 1.086
- **Best min_samples**: 5
- **Silhouette score**: 0.908
- **Clusters found**: 2
- **Noise points**: 87
- **Noise ratio**: 21.8%

**Evaluation Performance**:

- Training score: 0.908
- Evaluation score: 0.676
- Score difference: -0.232
- Evaluation races: 676

## Selected Features

1. variance_normalized
2. variance_absolute
3. winning_time
4. std_deviation_absolute
5. clumpiness_score
6. total_groups
7. std_group_size
8. largest_group_size
9. riders_in_groups

## Recommendations

1. **Best performing method**: kmeans (score: 0.989)
2. **Best generalization**: kmeans (score difference: +0.004)
