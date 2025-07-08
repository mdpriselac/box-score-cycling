# Race Kind Method Comparison Report

**Percentile**: 60th
**Generated**: 2025-07-08 11:13:14
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 13
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.446 | 3 | N/A | N/A |
| hierarchical | 0.401 | 3 | N/A | N/A |
| gaussian_mixture | 0.187 | 3 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.587 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.446

**Cluster Distribution**:

- Cluster 0: 1069 races (79.7%)
- Cluster 1: 163 races (12.2%)
- Cluster 2: 109 races (8.1%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.401

**Cluster Distribution**:

- Cluster 0: 196 races (14.6%)
- Cluster 1: 109 races (8.1%)
- Cluster 2: 1036 races (77.3%)
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.187
- **BIC**: 15508.0
- **AIC**: 13874.8
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.426
- **Best min_samples**: 10
- **Silhouette score**: 0.587
- **Clusters found**: 2
- **Noise points**: 216
- **Noise ratio**: 16.1%

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. avg_group_size
4. selection_metric
5. total_finishers
6. gini_coefficient
7. 50th_percentile_gap
8. std_group_size
9. total_race_duration
10. largest_group_size
11. variance_absolute
12. time_gap_evenness_metric
13. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.587)
