# Race Kind Method Comparison Report

**Percentile**: 80th
**Generated**: 2025-07-08 11:09:15
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.237 | 5 | 0.230 | -0.008 |
| hierarchical | 0.192 | 4 | 0.293 | +0.101 |
| gaussian_mixture | 0.174 | 4 | 0.142 | -0.032 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.785 | 2 | 0.516 | -0.269 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 5
- **Silhouette score**: 0.237

**Cluster Distribution**:

- Cluster 0: 332 races (59.9%)
- Cluster 1: 154 races (27.8%)
- Cluster 2: 4 races (0.7%)
- Cluster 3: 4 races (0.7%)
- Cluster 4: 60 races (10.8%)

**Evaluation Performance**:

- Training score: 0.237
- Evaluation score: 0.230
- Score difference: -0.008
- Evaluation races: 1431
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.192

**Cluster Distribution**:

- Cluster 0: 307 races (55.4%)
- Cluster 1: 4 races (0.7%)
- Cluster 2: 240 races (43.3%)
- Cluster 3: 3 races (0.5%)

**Evaluation Performance**:

- Training score: 0.192
- Evaluation score: 0.293
- Score difference: +0.101
- Evaluation races: 1431
### Gaussian Mixture

- **Best number of components**: 4
- **Silhouette score**: 0.174
- **BIC**: 10467.6
- **AIC**: 8399.7

**Evaluation Performance**:

- Training score: 0.174
- Evaluation score: 0.142
- Score difference: -0.032
- Evaluation races: 1431
### Feature Based

- **Error**: Missing required features: ['selection_metric', 'std_deviation_normalized', 'abandon_ratio', 'time_gap_evenness_metric', 'variance_normalized']
### Dbscan

- **Best eps**: 2.163
- **Best min_samples**: 3
- **Silhouette score**: 0.785
- **Clusters found**: 2
- **Noise points**: 28
- **Noise ratio**: 5.1%

**Evaluation Performance**:

- Training score: 0.785
- Evaluation score: 0.516
- Score difference: -0.269
- Evaluation races: 1431

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. total_finishers
4. proportion_in_groups
5. 50th_percentile_gap
6. kurtosis_absolute
7. avg_group_size
8. largest_group_size
9. shannon_entropy_normalized
10. gini_coefficient
11. total_race_duration
12. variance_absolute
13. std_group_size
14. skewness_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.785)
2. **Best generalization**: kmeans (score difference: -0.008)
