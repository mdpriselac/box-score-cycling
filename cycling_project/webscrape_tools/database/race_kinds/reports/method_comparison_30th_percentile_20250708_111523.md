# Race Kind Method Comparison Report

**Percentile**: 30th
**Generated**: 2025-07-08 11:15:23
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 12
**Feature Selection Categories**: ['wt', 'pro', 'd1']
**Analysis Categories**: ['wt', 'pro', 'd1']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.973 | 3 | N/A | N/A |
| hierarchical | 0.973 | 3 | N/A | N/A |
| gaussian_mixture | 0.282 | 7 | N/A | N/A |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.574 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.973

**Cluster Distribution**:

- Cluster 0: 673 races (99.7%)
- Cluster 1: 1 races (0.1%)
- Cluster 2: 1 races (0.1%)
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.973

**Cluster Distribution**:

- Cluster 0: 673 races (99.7%)
- Cluster 1: 1 races (0.1%)
- Cluster 2: 1 races (0.1%)
### Gaussian Mixture

- **Best number of components**: 7
- **Silhouette score**: 0.282
- **BIC**: -15448.6
- **AIC**: -18319.9
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.253
- **Best min_samples**: 10
- **Silhouette score**: 0.574
- **Clusters found**: 2
- **Noise points**: 157
- **Noise ratio**: 23.3%

## Selected Features

1. clumpiness_score
2. variance_absolute
3. gini_coefficient
4. avg_group_size
5. std_group_size
6. time_gap_evenness_metric
7. total_groups
8. largest_group_size
9. 50th_percentile_gap
10. total_race_duration
11. std_deviation_absolute
12. skewness_normalized

## Recommendations

1. **Best performing method**: kmeans (score: 0.973)
