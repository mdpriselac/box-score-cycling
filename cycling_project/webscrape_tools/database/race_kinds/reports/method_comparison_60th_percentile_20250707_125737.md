# Race Kind Method Comparison Report

**Percentile**: 60th
**Generated**: 2025-07-07 12:57:37
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 9
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.809 | 4 | 0.804 | -0.005 |
| hierarchical | 0.807 | 4 | 0.719 | -0.088 |
| gaussian_mixture | 0.809 | 4 | 0.685 | -0.124 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.861 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.809

**Cluster Distribution**:

- Cluster 0: 444 races (88.1%)
- Cluster 1: 1 races (0.2%)
- Cluster 2: 14 races (2.8%)
- Cluster 3: 45 races (8.9%)

**Evaluation Performance**:

- Training score: 0.809
- Evaluation score: 0.804
- Score difference: -0.005
- Evaluation races: 1019
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.807

**Cluster Distribution**:

- Cluster 0: 448 races (88.9%)
- Cluster 1: 10 races (2.0%)
- Cluster 2: 1 races (0.2%)
- Cluster 3: 45 races (8.9%)

**Evaluation Performance**:

- Training score: 0.807
- Evaluation score: 0.719
- Score difference: -0.088
- Evaluation races: 1019
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.809
- **BIC**: 7089.0
- **AIC**: 6164.3

**Evaluation Performance**:

- Training score: 0.809
- Evaluation score: 0.685
- Score difference: -0.124
- Evaluation races: 1019
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.326
- **Best min_samples**: 7
- **Silhouette score**: 0.861
- **Clusters found**: 2
- **Noise points**: 111
- **Noise ratio**: 22.0%

## Selected Features

1. variance_absolute
2. winning_time
3. largest_group_size
4. std_group_size
5. time_gap_evenness_metric
6. clumpiness_score
7. riders_in_groups
8. total_groups
9. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.861)
2. **Best generalization**: kmeans (score difference: -0.005)
