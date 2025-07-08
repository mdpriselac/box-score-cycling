# Race Kind Method Comparison Report

**Percentile**: 40th
**Generated**: 2025-07-08 11:13:08
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 11
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.730 | 3 | N/A | N/A |
| hierarchical | 0.726 | 3 | N/A | N/A |
| gaussian_mixture | 0.233 | 7 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.405 | 5 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.730

**Cluster Distribution**:

- Cluster 0: 993 races (93.7%)
- Cluster 1: 2 races (0.2%)
- Cluster 2: 65 races (6.1%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.726

**Cluster Distribution**:

- Cluster 0: 68 races (6.4%)
- Cluster 1: 2 races (0.2%)
- Cluster 2: 990 races (93.4%)
### Gaussian Mixture

- **Best number of components**: 7
- **Silhouette score**: 0.233
- **BIC**: -4854.9
- **AIC**: -7561.4
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'variance_normalized']
### Dbscan

- **Best eps**: 1.171
- **Best min_samples**: 7
- **Silhouette score**: 0.405
- **Clusters found**: 5
- **Noise points**: 159
- **Noise ratio**: 15.0%

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. selection_metric
4. avg_group_size
5. gini_coefficient
6. std_group_size
7. variance_absolute
8. total_race_duration
9. 50th_percentile_gap
10. total_groups
11. skewness_normalized

## Recommendations

1. **Best performing method**: kmeans (score: 0.730)
