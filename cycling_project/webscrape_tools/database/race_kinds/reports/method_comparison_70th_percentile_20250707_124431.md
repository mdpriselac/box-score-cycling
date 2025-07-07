# Race Kind Method Comparison Report

**Percentile**: 70th
**Generated**: 2025-07-07 12:44:31
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 15
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.439 | 3 | 0.403 | -0.036 |
| hierarchical | 0.431 | 3 | 0.381 | -0.050 |
| gaussian_mixture | 0.294 | 4 | 0.203 | -0.092 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.417 | 3 | 0.269 | -0.148 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.439

**Cluster Distribution**:

- Cluster 0: 2786 races (68.1%)
- Cluster 1: 530 races (13.0%)
- Cluster 2: 775 races (18.9%)

**Evaluation Performance**:

- Training score: 0.439
- Evaluation score: 0.403
- Score difference: -0.036
- Evaluation races: 7333
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.431

**Cluster Distribution**:

- Cluster 0: 2674 races (65.4%)
- Cluster 1: 634 races (15.5%)
- Cluster 2: 783 races (19.1%)

**Evaluation Performance**:

- Training score: 0.431
- Evaluation score: 0.381
- Score difference: -0.050
- Evaluation races: 7333
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.294
- **BIC**: -93294.0
- **AIC**: -96723.9

**Evaluation Performance**:

- Training score: 0.294
- Evaluation score: 0.203
- Score difference: -0.092
- Evaluation races: 7333
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.280
- **Best min_samples**: 10
- **Silhouette score**: 0.417
- **Clusters found**: 3
- **Noise points**: 211
- **Noise ratio**: 5.2%

**Evaluation Performance**:

- Training score: 0.417
- Evaluation score: 0.269
- Score difference: -0.148
- Evaluation races: 7333

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. avg_group_size
4. shannon_entropy_absolute
5. selection_metric
6. gini_coefficient
7. largest_group_size
8. std_group_size
9. std_deviation_normalized
10. total_race_duration
11. 50th_percentile_gap
12. total_groups
13. time_gap_evenness_metric
14. variance_absolute
15. skewness_absolute

## Recommendations

1. **Best performing method**: kmeans (score: 0.439)
2. **Best generalization**: kmeans (score difference: -0.036)
