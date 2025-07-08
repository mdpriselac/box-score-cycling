# Race Kind Method Comparison Report

**Percentile**: 90th
**Generated**: 2025-07-08 11:09:17
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 10
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.204 | 4 | 0.201 | -0.003 |
| hierarchical | 0.157 | 3 | 0.191 | +0.034 |
| gaussian_mixture | 0.116 | 3 | 0.122 | +0.006 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.479 | 3 | 0.468 | -0.011 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.204

**Cluster Distribution**:

- Cluster 0: 44 races (7.9%)
- Cluster 1: 314 races (56.3%)
- Cluster 2: 75 races (13.4%)
- Cluster 3: 125 races (22.4%)

**Evaluation Performance**:

- Training score: 0.204
- Evaluation score: 0.201
- Score difference: -0.003
- Evaluation races: 1445
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.157

**Cluster Distribution**:

- Cluster 0: 147 races (26.3%)
- Cluster 1: 90 races (16.1%)
- Cluster 2: 321 races (57.5%)

**Evaluation Performance**:

- Training score: 0.157
- Evaluation score: 0.191
- Score difference: +0.034
- Evaluation races: 1445
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.116
- **BIC**: 9357.3
- **AIC**: 8505.4

**Evaluation Performance**:

- Training score: 0.116
- Evaluation score: 0.122
- Score difference: +0.006
- Evaluation races: 1445
### Feature Based

- **Error**: Missing required features: ['gini_coefficient', 'std_deviation_normalized', 'time_gap_evenness_metric', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 1.868
- **Best min_samples**: 3
- **Silhouette score**: 0.479
- **Clusters found**: 3
- **Noise points**: 20
- **Noise ratio**: 3.6%

**Evaluation Performance**:

- Training score: 0.479
- Evaluation score: 0.468
- Score difference: -0.011
- Evaluation races: 1445

## Selected Features

1. biggest_group_metric
2. largest_group_position
3. total_finishers
4. proportion_in_groups
5. abandon_ratio
6. variance_absolute
7. 50th_percentile_gap
8. largest_group_size
9. selection_metric
10. avg_group_size

## Recommendations

1. **Best performing method**: dbscan (score: 0.479)
2. **Best generalization**: kmeans (score difference: -0.003)
