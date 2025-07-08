# Race Kind Method Comparison Report

**Percentile**: 90th
**Generated**: 2025-07-08 11:15:42
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 10
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.277 | 3 | N/A | N/A |
| hierarchical | 0.218 | 3 | N/A | N/A |
| gaussian_mixture | 0.203 | 3 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.823 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.277

**Cluster Distribution**:

- Cluster 0: 984 races (68.1%)
- Cluster 1: 443 races (30.7%)
- Cluster 2: 18 races (1.2%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.218

**Cluster Distribution**:

- Cluster 0: 914 races (63.3%)
- Cluster 1: 16 races (1.1%)
- Cluster 2: 515 races (35.6%)
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.203
- **BIC**: 17843.6
- **AIC**: 16804.3
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 1.223
- **Best min_samples**: 5
- **Silhouette score**: 0.823
- **Clusters found**: 2
- **Noise points**: 133
- **Noise ratio**: 9.2%

## Selected Features

1. biggest_group_metric
2. total_finishers
3. 50th_percentile_gap
4. avg_group_size
5. largest_group_size
6. gini_coefficient
7. std_group_size
8. selection_metric
9. variance_absolute
10. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.823)
