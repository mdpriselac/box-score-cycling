# Race Kind Method Comparison Report

**Percentile**: 50th
**Generated**: 2025-07-07 12:57:36
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 8
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.841 | 4 | 0.765 | -0.076 |
| hierarchical | 0.842 | 4 | 0.661 | -0.182 |
| gaussian_mixture | 0.841 | 4 | 0.899 | +0.058 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.892 | 2 | 0.685 | -0.207 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.841

**Cluster Distribution**:

- Cluster 0: 443 races (88.6%)
- Cluster 1: 1 races (0.2%)
- Cluster 2: 45 races (9.0%)
- Cluster 3: 11 races (2.2%)

**Evaluation Performance**:

- Training score: 0.841
- Evaluation score: 0.765
- Score difference: -0.076
- Evaluation races: 998
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.842

**Cluster Distribution**:

- Cluster 0: 445 races (89.0%)
- Cluster 1: 9 races (1.8%)
- Cluster 2: 45 races (9.0%)
- Cluster 3: 1 races (0.2%)

**Evaluation Performance**:

- Training score: 0.842
- Evaluation score: 0.661
- Score difference: -0.182
- Evaluation races: 998
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.841
- **BIC**: 5094.1
- **AIC**: 4339.7

**Evaluation Performance**:

- Training score: 0.841
- Evaluation score: 0.899
- Score difference: +0.058
- Evaluation races: 998
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.115
- **Best min_samples**: 5
- **Silhouette score**: 0.892
- **Clusters found**: 2
- **Noise points**: 97
- **Noise ratio**: 19.4%

**Evaluation Performance**:

- Training score: 0.892
- Evaluation score: 0.685
- Score difference: -0.207
- Evaluation races: 998

## Selected Features

1. variance_absolute
2. winning_time
3. std_deviation_absolute
4. largest_group_size
5. clumpiness_score
6. time_gap_evenness_metric
7. riders_in_groups
8. total_groups

## Recommendations

1. **Best performing method**: dbscan (score: 0.892)
2. **Best generalization**: gaussian_mixture (score difference: +0.058)
