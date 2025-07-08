# Race Kind Method Comparison Report

**Percentile**: 70th
**Generated**: 2025-07-08 11:15:35
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.359 | 3 | N/A | N/A |
| hierarchical | 0.315 | 3 | N/A | N/A |
| gaussian_mixture | 0.230 | 4 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.667 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.359

**Cluster Distribution**:

- Cluster 0: 244 races (17.4%)
- Cluster 1: 1026 races (73.3%)
- Cluster 2: 129 races (9.2%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.315

**Cluster Distribution**:

- Cluster 0: 1025 races (73.3%)
- Cluster 1: 74 races (5.3%)
- Cluster 2: 300 races (21.4%)
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.230
- **BIC**: 12476.3
- **AIC**: 9964.7
### Feature Based

- **Error**: Missing required features: ['std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.375
- **Best min_samples**: 10
- **Silhouette score**: 0.667
- **Clusters found**: 2
- **Noise points**: 278
- **Noise ratio**: 19.9%

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. avg_group_size
4. gini_coefficient
5. shannon_entropy_absolute
6. total_race_duration
7. selection_metric
8. proportion_in_groups
9. 50th_percentile_gap
10. largest_group_size
11. std_group_size
12. total_groups
13. time_gap_evenness_metric
14. variance_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.667)
