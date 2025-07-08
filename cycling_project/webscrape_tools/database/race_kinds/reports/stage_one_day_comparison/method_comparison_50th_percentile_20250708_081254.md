# Race Kind Method Comparison Report

**Percentile**: 50th
**Generated**: 2025-07-08 08:12:54
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.584 | 3 | 0.585 | +0.001 |
| hierarchical | 0.603 | 4 | 0.637 | +0.035 |
| gaussian_mixture | 0.251 | 6 | 0.127 | -0.124 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.553 | 3 | 0.462 | -0.091 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.584

**Cluster Distribution**:

- Cluster 0: 496 races (12.2%)
- Cluster 1: 80 races (2.0%)
- Cluster 2: 3476 races (85.8%)

**Evaluation Performance**:

- Training score: 0.584
- Evaluation score: 0.585
- Score difference: +0.001
- Evaluation races: 7152
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.603

**Cluster Distribution**:

- Cluster 0: 3687 races (91.0%)
- Cluster 1: 86 races (2.1%)
- Cluster 2: 277 races (6.8%)
- Cluster 3: 2 races (0.0%)

**Evaluation Performance**:

- Training score: 0.603
- Evaluation score: 0.637
- Score difference: +0.035
- Evaluation races: 7152
### Gaussian Mixture

- **Best number of components**: 6
- **Silhouette score**: 0.251
- **BIC**: -146994.5
- **AIC**: -151529.2

**Evaluation Performance**:

- Training score: 0.251
- Evaluation score: 0.127
- Score difference: -0.124
- Evaluation races: 7152
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.564
- **Best min_samples**: 10
- **Silhouette score**: 0.553
- **Clusters found**: 3
- **Noise points**: 371
- **Noise ratio**: 9.2%

**Evaluation Performance**:

- Training score: 0.553
- Evaluation score: 0.462
- Score difference: -0.091
- Evaluation races: 7152

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. avg_group_size
4. selection_metric
5. gini_coefficient
6. std_group_size
7. total_groups
8. std_deviation_normalized
9. time_gap_evenness_metric
10. total_race_duration
11. 50th_percentile_gap
12. 10th_percentile_gap
13. variance_absolute
14. skewness_normalized

## Recommendations

1. **Best performing method**: hierarchical (score: 0.603)
2. **Best generalization**: kmeans (score difference: +0.001)
