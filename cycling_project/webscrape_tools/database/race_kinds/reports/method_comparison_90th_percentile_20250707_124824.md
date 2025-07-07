# Race Kind Method Comparison Report

**Percentile**: 90th
**Generated**: 2025-07-07 12:48:24
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 16
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.334 | 4 | 0.323 | -0.010 |
| hierarchical | 0.312 | 3 | 0.287 | -0.025 |
| gaussian_mixture | 0.276 | 3 | 0.242 | -0.034 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.602 | 3 | 0.384 | -0.218 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.334

**Cluster Distribution**:

- Cluster 0: 673 races (16.4%)
- Cluster 1: 850 races (20.7%)
- Cluster 2: 2313 races (56.3%)
- Cluster 3: 273 races (6.6%)

**Evaluation Performance**:

- Training score: 0.334
- Evaluation score: 0.323
- Score difference: -0.010
- Evaluation races: 7381
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.312

**Cluster Distribution**:

- Cluster 0: 2222 races (54.1%)
- Cluster 1: 272 races (6.6%)
- Cluster 2: 1615 races (39.3%)

**Evaluation Performance**:

- Training score: 0.312
- Evaluation score: 0.287
- Score difference: -0.025
- Evaluation races: 7381
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.276
- **BIC**: 6005.5
- **AIC**: 3110.5

**Evaluation Performance**:

- Training score: 0.276
- Evaluation score: 0.242
- Score difference: -0.034
- Evaluation races: 7381
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.181
- **Best min_samples**: 10
- **Silhouette score**: 0.602
- **Clusters found**: 3
- **Noise points**: 343
- **Noise ratio**: 8.3%

**Evaluation Performance**:

- Training score: 0.602
- Evaluation score: 0.384
- Score difference: -0.218
- Evaluation races: 7381

## Selected Features

1. biggest_group_metric
2. largest_group_position
3. selection_metric
4. clumpiness_score
5. avg_group_size
6. largest_group_size
7. std_deviation_normalized
8. std_group_size
9. 50th_percentile_gap
10. shannon_entropy_absolute
11. total_race_duration
12. gini_coefficient
13. time_gap_evenness_metric
14. total_groups
15. variance_absolute
16. skewness_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.602)
2. **Best generalization**: kmeans (score difference: -0.010)
