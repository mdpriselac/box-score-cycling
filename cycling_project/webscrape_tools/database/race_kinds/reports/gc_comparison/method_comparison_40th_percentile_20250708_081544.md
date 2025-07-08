# Race Kind Method Comparison Report

**Percentile**: 40th
**Generated**: 2025-07-08 08:15:44
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 9
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.834 | 3 | 0.898 | +0.064 |
| hierarchical | 0.834 | 3 | 0.903 | +0.069 |
| gaussian_mixture | 0.834 | 3 | 0.988 | +0.154 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.869 | 5 | 0.708 | -0.162 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.834

**Cluster Distribution**:

- Cluster 0: 439 races (90.5%)
- Cluster 1: 1 races (0.2%)
- Cluster 2: 45 races (9.3%)

**Evaluation Performance**:

- Training score: 0.834
- Evaluation score: 0.898
- Score difference: +0.064
- Evaluation races: 936
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.834

**Cluster Distribution**:

- Cluster 0: 439 races (90.5%)
- Cluster 1: 1 races (0.2%)
- Cluster 2: 45 races (9.3%)

**Evaluation Performance**:

- Training score: 0.834
- Evaluation score: 0.903
- Score difference: +0.069
- Evaluation races: 936
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.834
- **BIC**: 7330.9
- **AIC**: 6644.7

**Evaluation Performance**:

- Training score: 0.834
- Evaluation score: 0.988
- Score difference: +0.154
- Evaluation races: 936
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.323
- **Best min_samples**: 5
- **Silhouette score**: 0.869
- **Clusters found**: 5
- **Noise points**: 59
- **Noise ratio**: 12.2%

**Evaluation Performance**:

- Training score: 0.869
- Evaluation score: 0.708
- Score difference: -0.162
- Evaluation races: 936

## Selected Features

1. variance_absolute
2. winning_time
3. std_deviation_absolute
4. largest_group_size
5. clumpiness_score
6. std_group_size
7. total_groups
8. time_gap_evenness_metric
9. riders_in_groups

## Recommendations

1. **Best performing method**: dbscan (score: 0.869)
2. **Best generalization**: kmeans (score difference: +0.064)
