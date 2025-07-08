# Race Kind Method Comparison Report

**Percentile**: 100th
**Generated**: 2025-07-08 08:14:09
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 16
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.295 | 6 | 0.286 | -0.010 |
| hierarchical | 0.285 | 5 | 0.254 | -0.031 |
| gaussian_mixture | 0.138 | 3 | 0.226 | +0.088 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.687 | 2 | 0.622 | -0.065 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 6
- **Silhouette score**: 0.295

**Cluster Distribution**:

- Cluster 0: 759 races (18.5%)
- Cluster 1: 469 races (11.4%)
- Cluster 2: 1992 races (48.5%)
- Cluster 3: 44 races (1.1%)
- Cluster 4: 89 races (2.2%)
- Cluster 5: 758 races (18.4%)

**Evaluation Performance**:

- Training score: 0.295
- Evaluation score: 0.286
- Score difference: -0.010
- Evaluation races: 7393
### Hierarchical

- **Best number of clusters**: 5
- **Silhouette score**: 0.285

**Cluster Distribution**:

- Cluster 0: 1175 races (28.6%)
- Cluster 1: 410 races (10.0%)
- Cluster 2: 2431 races (59.1%)
- Cluster 3: 63 races (1.5%)
- Cluster 4: 32 races (0.8%)

**Evaluation Performance**:

- Training score: 0.285
- Evaluation score: 0.254
- Score difference: -0.031
- Evaluation races: 7393
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.138
- **BIC**: 27022.3
- **AIC**: 24127.1

**Evaluation Performance**:

- Training score: 0.138
- Evaluation score: 0.226
- Score difference: +0.088
- Evaluation races: 7393
### Feature Based

- **Error**: Missing required features: ['abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.358
- **Best min_samples**: 10
- **Silhouette score**: 0.687
- **Clusters found**: 2
- **Noise points**: 387
- **Noise ratio**: 9.4%

**Evaluation Performance**:

- Training score: 0.687
- Evaluation score: 0.622
- Score difference: -0.065
- Evaluation races: 7393

## Selected Features

1. biggest_group_metric
2. largest_group_position
3. clumpiness_score
4. shannon_entropy_normalized
5. gini_coefficient
6. 50th_percentile_gap
7. largest_group_size
8. std_deviation_normalized
9. selection_metric
10. shannon_entropy_absolute
11. kurtosis_normalized
12. proportion_in_groups
13. avg_group_size
14. variance_absolute
15. time_gap_evenness_metric
16. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.687)
2. **Best generalization**: kmeans (score difference: -0.010)
