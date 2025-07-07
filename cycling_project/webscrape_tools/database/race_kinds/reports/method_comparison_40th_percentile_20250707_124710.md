# Race Kind Method Comparison Report

**Percentile**: 40th
**Generated**: 2025-07-07 12:47:10
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.729 | 3 | 0.730 | +0.001 |
| hierarchical | 0.770 | 3 | 0.777 | +0.007 |
| gaussian_mixture | 0.247 | 7 | 0.079 | -0.168 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.371 | 5 | 0.414 | +0.043 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.729

**Cluster Distribution**:

- Cluster 0: 316 races (7.9%)
- Cluster 1: 53 races (1.3%)
- Cluster 2: 3620 races (90.7%)

**Evaluation Performance**:

- Training score: 0.729
- Evaluation score: 0.730
- Score difference: +0.001
- Evaluation races: 6854
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.770

**Cluster Distribution**:

- Cluster 0: 3806 races (95.4%)
- Cluster 1: 44 races (1.1%)
- Cluster 2: 139 races (3.5%)

**Evaluation Performance**:

- Training score: 0.770
- Evaluation score: 0.777
- Score difference: +0.007
- Evaluation races: 6854
### Gaussian Mixture

- **Best number of components**: 7
- **Silhouette score**: 0.247
- **BIC**: -176734.2
- **AIC**: -182012.6

**Evaluation Performance**:

- Training score: 0.247
- Evaluation score: 0.079
- Score difference: -0.168
- Evaluation races: 6854
### Feature Based

- **Error**: Missing required features: ['abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.083
- **Best min_samples**: 10
- **Silhouette score**: 0.371
- **Clusters found**: 5
- **Noise points**: 768
- **Noise ratio**: 19.3%

**Evaluation Performance**:

- Training score: 0.371
- Evaluation score: 0.414
- Score difference: +0.043
- Evaluation races: 6854

## Selected Features

1. clumpiness_score
2. biggest_group_metric
3. avg_group_size
4. selection_metric
5. gini_coefficient
6. std_group_size
7. proportion_in_groups
8. time_gap_evenness_metric
9. total_groups
10. std_deviation_normalized
11. total_race_duration
12. 50th_percentile_gap
13. variance_absolute
14. skewness_normalized

## Recommendations

1. **Best performing method**: hierarchical (score: 0.770)
2. **Best generalization**: kmeans (score difference: +0.001)
