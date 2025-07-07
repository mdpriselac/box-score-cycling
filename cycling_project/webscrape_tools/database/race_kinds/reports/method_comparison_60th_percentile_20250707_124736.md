# Race Kind Method Comparison Report

**Percentile**: 60th
**Generated**: 2025-07-07 12:47:36
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.428 | 7 | 0.399 | -0.029 |
| hierarchical | 0.405 | 7 | 0.329 | -0.076 |
| gaussian_mixture | 0.264 | 4 | 0.136 | -0.128 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.421 | 5 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 7
- **Silhouette score**: 0.428

**Cluster Distribution**:

- Cluster 0: 1752 races (43.0%)
- Cluster 1: 37 races (0.9%)
- Cluster 2: 203 races (5.0%)
- Cluster 3: 488 races (12.0%)
- Cluster 4: 139 races (3.4%)
- Cluster 5: 895 races (22.0%)
- Cluster 6: 562 races (13.8%)

**Evaluation Performance**:

- Training score: 0.428
- Evaluation score: 0.399
- Score difference: -0.029
- Evaluation races: 7274
### Hierarchical

- **Best number of clusters**: 7
- **Silhouette score**: 0.405

**Cluster Distribution**:

- Cluster 0: 39 races (1.0%)
- Cluster 1: 1926 races (47.3%)
- Cluster 2: 283 races (6.9%)
- Cluster 3: 121 races (3.0%)
- Cluster 4: 482 races (11.8%)
- Cluster 5: 352 races (8.6%)
- Cluster 6: 873 races (21.4%)

**Evaluation Performance**:

- Training score: 0.405
- Evaluation score: 0.329
- Score difference: -0.076
- Evaluation races: 7274
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.264
- **BIC**: -120000.4
- **AIC**: -123024.3

**Evaluation Performance**:

- Training score: 0.264
- Evaluation score: 0.136
- Score difference: -0.128
- Evaluation races: 7274
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.644
- **Best min_samples**: 7
- **Silhouette score**: 0.421
- **Clusters found**: 5
- **Noise points**: 66
- **Noise ratio**: 1.6%

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. avg_group_size
4. selection_metric
5. gini_coefficient
6. largest_group_size
7. std_group_size
8. std_deviation_normalized
9. total_race_duration
10. total_groups
11. time_gap_evenness_metric
12. 50th_percentile_gap
13. variance_absolute
14. skewness_absolute

## Recommendations

1. **Best performing method**: kmeans (score: 0.428)
2. **Best generalization**: kmeans (score difference: -0.029)
