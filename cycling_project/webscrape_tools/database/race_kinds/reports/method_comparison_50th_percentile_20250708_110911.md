# Race Kind Method Comparison Report

**Percentile**: 50th
**Generated**: 2025-07-08 11:09:11
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 16
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.409 | 3 | 0.360 | -0.049 |
| hierarchical | 0.504 | 3 | 0.401 | -0.103 |
| gaussian_mixture | 0.323 | 3 | 0.289 | -0.034 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.564 | 2 | 0.378 | -0.187 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.409

**Cluster Distribution**:

- Cluster 0: 431 races (85.3%)
- Cluster 1: 3 races (0.6%)
- Cluster 2: 71 races (14.1%)

**Evaluation Performance**:

- Training score: 0.409
- Evaluation score: 0.360
- Score difference: -0.049
- Evaluation races: 1249
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.504

**Cluster Distribution**:

- Cluster 0: 471 races (93.3%)
- Cluster 1: 3 races (0.6%)
- Cluster 2: 31 races (6.1%)

**Evaluation Performance**:

- Training score: 0.504
- Evaluation score: 0.401
- Score difference: -0.103
- Evaluation races: 1249
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.323
- **BIC**: 9266.3
- **AIC**: 7331.4

**Evaluation Performance**:

- Training score: 0.323
- Evaluation score: 0.289
- Score difference: -0.034
- Evaluation races: 1249
### Feature Based

- **Error**: Missing required features: ['std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.704
- **Best min_samples**: 5
- **Silhouette score**: 0.564
- **Clusters found**: 2
- **Noise points**: 84
- **Noise ratio**: 16.6%

**Evaluation Performance**:

- Training score: 0.564
- Evaluation score: 0.378
- Score difference: -0.187
- Evaluation races: 1249

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. avg_group_size
4. total_finishers
5. shannon_entropy_absolute
6. variance_absolute
7. selection_metric
8. proportion_in_groups
9. std_group_size
10. largest_group_size
11. gini_coefficient
12. total_race_duration
13. 50th_percentile_gap
14. total_groups
15. time_gap_evenness_metric
16. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.564)
2. **Best generalization**: gaussian_mixture (score difference: -0.034)
