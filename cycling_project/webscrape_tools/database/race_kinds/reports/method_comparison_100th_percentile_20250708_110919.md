# Race Kind Method Comparison Report

**Percentile**: 100th
**Generated**: 2025-07-08 11:09:19
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 13
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.292 | 3 | 0.291 | -0.001 |
| hierarchical | 0.303 | 3 | 0.225 | -0.079 |
| gaussian_mixture | 0.203 | 3 | 0.178 | -0.024 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.490 | 3 | 0.388 | -0.102 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.292

**Cluster Distribution**:

- Cluster 0: 65 races (11.6%)
- Cluster 1: 377 races (67.3%)
- Cluster 2: 118 races (21.1%)

**Evaluation Performance**:

- Training score: 0.292
- Evaluation score: 0.291
- Score difference: -0.001
- Evaluation races: 1457
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.303

**Cluster Distribution**:

- Cluster 0: 80 races (14.3%)
- Cluster 1: 90 races (16.1%)
- Cluster 2: 390 races (69.6%)

**Evaluation Performance**:

- Training score: 0.303
- Evaluation score: 0.225
- Score difference: -0.079
- Evaluation races: 1457
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.203
- **BIC**: 11329.8
- **AIC**: 9970.9

**Evaluation Performance**:

- Training score: 0.203
- Evaluation score: 0.178
- Score difference: -0.024
- Evaluation races: 1457
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'abandon_ratio', 'time_gap_evenness_metric', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 2.161
- **Best min_samples**: 3
- **Silhouette score**: 0.490
- **Clusters found**: 3
- **Noise points**: 37
- **Noise ratio**: 6.6%

**Evaluation Performance**:

- Training score: 0.490
- Evaluation score: 0.388
- Score difference: -0.102
- Evaluation races: 1457

## Selected Features

1. largest_group_position
2. 10th_percentile_gap
3. riders_in_groups
4. proportion_in_groups
5. std_deviation_normalized
6. kurtosis_normalized
7. gini_coefficient
8. variance_absolute
9. 50th_percentile_gap
10. shannon_entropy_normalized
11. largest_group_size
12. selection_metric
13. skewness_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.490)
2. **Best generalization**: kmeans (score difference: -0.001)
