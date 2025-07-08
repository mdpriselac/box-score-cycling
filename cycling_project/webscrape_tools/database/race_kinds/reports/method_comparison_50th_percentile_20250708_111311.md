# Race Kind Method Comparison Report

**Percentile**: 50th
**Generated**: 2025-07-08 11:13:11
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 15
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.446 | 3 | N/A | N/A |
| hierarchical | 0.514 | 3 | N/A | N/A |
| gaussian_mixture | 0.225 | 4 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.560 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.446

**Cluster Distribution**:

- Cluster 0: 171 races (13.7%)
- Cluster 1: 1075 races (86.1%)
- Cluster 2: 3 races (0.2%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.514

**Cluster Distribution**:

- Cluster 0: 1142 races (91.4%)
- Cluster 1: 105 races (8.4%)
- Cluster 2: 2 races (0.2%)
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.225
- **BIC**: 8313.1
- **AIC**: 5527.4
### Feature Based

- **Error**: Missing required features: ['std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.284
- **Best min_samples**: 10
- **Silhouette score**: 0.560
- **Clusters found**: 2
- **Noise points**: 359
- **Noise ratio**: 28.7%

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. shannon_entropy_absolute
4. selection_metric
5. avg_group_size
6. gini_coefficient
7. std_group_size
8. largest_group_size
9. 50th_percentile_gap
10. proportion_in_groups
11. total_race_duration
12. variance_absolute
13. total_groups
14. time_gap_evenness_metric
15. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.560)
