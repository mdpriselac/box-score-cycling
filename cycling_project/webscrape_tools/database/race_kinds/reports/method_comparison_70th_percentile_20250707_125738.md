# Race Kind Method Comparison Report

**Percentile**: 70th
**Generated**: 2025-07-07 12:57:38
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 8
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.824 | 3 | 0.829 | +0.005 |
| hierarchical | 0.814 | 3 | 0.857 | +0.043 |
| gaussian_mixture | 0.824 | 3 | 0.847 | +0.023 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.891 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.824

**Cluster Distribution**:

- Cluster 0: 447 races (88.7%)
- Cluster 1: 46 races (9.1%)
- Cluster 2: 11 races (2.2%)

**Evaluation Performance**:

- Training score: 0.824
- Evaluation score: 0.829
- Score difference: +0.005
- Evaluation races: 1020
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.814

**Cluster Distribution**:

- Cluster 0: 46 races (9.1%)
- Cluster 1: 451 races (89.5%)
- Cluster 2: 7 races (1.4%)

**Evaluation Performance**:

- Training score: 0.814
- Evaluation score: 0.857
- Score difference: +0.043
- Evaluation races: 1020
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.824
- **BIC**: 7171.2
- **AIC**: 6605.4

**Evaluation Performance**:

- Training score: 0.824
- Evaluation score: 0.847
- Score difference: +0.023
- Evaluation races: 1020
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.116
- **Best min_samples**: 5
- **Silhouette score**: 0.891
- **Clusters found**: 2
- **Noise points**: 124
- **Noise ratio**: 24.6%

## Selected Features

1. winning_time
2. variance_absolute
3. largest_group_size
4. time_gap_evenness_metric
5. clumpiness_score
6. total_groups
7. riders_in_groups
8. skewness_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.891)
2. **Best generalization**: kmeans (score difference: +0.005)
