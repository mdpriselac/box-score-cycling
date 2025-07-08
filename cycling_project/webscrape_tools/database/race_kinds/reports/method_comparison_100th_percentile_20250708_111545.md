# Race Kind Method Comparison Report

**Percentile**: 100th
**Generated**: 2025-07-08 11:15:45
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 12
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.351 | 3 | N/A | N/A |
| hierarchical | 0.388 | 3 | N/A | N/A |
| gaussian_mixture | 0.156 | 3 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.632 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.351

**Cluster Distribution**:

- Cluster 0: 220 races (15.1%)
- Cluster 1: 1114 races (76.5%)
- Cluster 2: 123 races (8.4%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.388

**Cluster Distribution**:

- Cluster 0: 69 races (4.7%)
- Cluster 1: 1223 races (83.9%)
- Cluster 2: 165 races (11.3%)
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.156
- **BIC**: 22751.6
- **AIC**: 21314.3
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 1.818
- **Best min_samples**: 5
- **Silhouette score**: 0.632
- **Clusters found**: 2
- **Noise points**: 102
- **Noise ratio**: 7.0%

## Selected Features

1. biggest_group_metric
2. largest_group_position
3. 10th_percentile_gap
4. riders_in_groups
5. 50th_percentile_gap
6. avg_group_size
7. largest_group_size
8. gini_coefficient
9. kurtosis_normalized
10. selection_metric
11. variance_absolute
12. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.632)
