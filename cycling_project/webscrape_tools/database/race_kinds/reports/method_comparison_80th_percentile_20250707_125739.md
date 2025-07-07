# Race Kind Method Comparison Report

**Percentile**: 80th
**Generated**: 2025-07-07 12:57:39
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 5
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.838 | 3 | 0.848 | +0.010 |
| hierarchical | 0.838 | 3 | 0.809 | -0.029 |
| gaussian_mixture | 0.828 | 3 | 0.759 | -0.070 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.898 | 2 | 0.616 | -0.282 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.838

**Cluster Distribution**:

- Cluster 0: 447 races (88.7%)
- Cluster 1: 46 races (9.1%)
- Cluster 2: 11 races (2.2%)

**Evaluation Performance**:

- Training score: 0.838
- Evaluation score: 0.848
- Score difference: +0.010
- Evaluation races: 1021
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.838

**Cluster Distribution**:

- Cluster 0: 46 races (9.1%)
- Cluster 1: 11 races (2.2%)
- Cluster 2: 447 races (88.7%)

**Evaluation Performance**:

- Training score: 0.838
- Evaluation score: 0.809
- Score difference: -0.029
- Evaluation races: 1021
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.828
- **BIC**: 5779.5
- **AIC**: 5517.7

**Evaluation Performance**:

- Training score: 0.828
- Evaluation score: 0.759
- Score difference: -0.070
- Evaluation races: 1021
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'variance_normalized']
### Dbscan

- **Best eps**: 0.900
- **Best min_samples**: 5
- **Silhouette score**: 0.898
- **Clusters found**: 2
- **Noise points**: 90
- **Noise ratio**: 17.9%

**Evaluation Performance**:

- Training score: 0.898
- Evaluation score: 0.616
- Score difference: -0.282
- Evaluation races: 1021

## Selected Features

1. winning_time
2. variance_absolute
3. largest_group_size
4. clumpiness_score
5. riders_in_groups

## Recommendations

1. **Best performing method**: dbscan (score: 0.898)
2. **Best generalization**: kmeans (score difference: +0.010)
