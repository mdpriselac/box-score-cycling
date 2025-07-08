# Race Kind Method Comparison Report

**Percentile**: 80th
**Generated**: 2025-07-08 11:13:21
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.281 | 4 | N/A | N/A |
| hierarchical | 0.413 | 3 | N/A | N/A |
| gaussian_mixture | 0.220 | 3 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.794 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.281

**Cluster Distribution**:

- Cluster 0: 328 races (22.9%)
- Cluster 1: 882 races (61.6%)
- Cluster 2: 190 races (13.3%)
- Cluster 3: 31 races (2.2%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.413

**Cluster Distribution**:

- Cluster 0: 1243 races (86.9%)
- Cluster 1: 162 races (11.3%)
- Cluster 2: 26 races (1.8%)
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.220
- **BIC**: 20926.8
- **AIC**: 19036.3
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.441
- **Best min_samples**: 10
- **Silhouette score**: 0.794
- **Clusters found**: 2
- **Noise points**: 272
- **Noise ratio**: 19.0%

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. avg_group_size
4. 50th_percentile_gap
5. shannon_entropy_normalized
6. total_race_duration
7. gini_coefficient
8. largest_group_size
9. selection_metric
10. std_group_size
11. shannon_entropy_absolute
12. total_groups
13. variance_absolute
14. time_gap_evenness_metric

## Recommendations

1. **Best performing method**: dbscan (score: 0.794)
