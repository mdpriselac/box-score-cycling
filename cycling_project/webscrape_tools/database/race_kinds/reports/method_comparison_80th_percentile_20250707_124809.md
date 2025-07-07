# Race Kind Method Comparison Report

**Percentile**: 80th
**Generated**: 2025-07-07 12:48:09
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 13
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.449 | 3 | 0.451 | +0.002 |
| hierarchical | 0.410 | 4 | 0.385 | -0.025 |
| gaussian_mixture | 0.257 | 3 | 0.204 | -0.053 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.517 | 5 | 0.368 | -0.149 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.449

**Cluster Distribution**:

- Cluster 0: 701 races (17.1%)
- Cluster 1: 2861 races (69.7%)
- Cluster 2: 543 races (13.2%)

**Evaluation Performance**:

- Training score: 0.449
- Evaluation score: 0.451
- Score difference: +0.002
- Evaluation races: 7367
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.410

**Cluster Distribution**:

- Cluster 0: 949 races (23.1%)
- Cluster 1: 179 races (4.4%)
- Cluster 2: 2495 races (60.8%)
- Cluster 3: 482 races (11.7%)

**Evaluation Performance**:

- Training score: 0.410
- Evaluation score: 0.385
- Score difference: -0.025
- Evaluation races: 7367
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.257
- **BIC**: -34644.0
- **AIC**: -36628.5

**Evaluation Performance**:

- Training score: 0.257
- Evaluation score: 0.204
- Score difference: -0.053
- Evaluation races: 7367
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 1.251
- **Best min_samples**: 10
- **Silhouette score**: 0.517
- **Clusters found**: 5
- **Noise points**: 174
- **Noise ratio**: 4.2%

**Evaluation Performance**:

- Training score: 0.517
- Evaluation score: 0.368
- Score difference: -0.149
- Evaluation races: 7367

## Selected Features

1. biggest_group_metric
2. selection_metric
3. avg_group_size
4. shannon_entropy_absolute
5. gini_coefficient
6. largest_group_size
7. std_deviation_normalized
8. std_group_size
9. 50th_percentile_gap
10. total_race_duration
11. time_gap_evenness_metric
12. variance_absolute
13. skewness_normalized

## Recommendations

1. **Best performing method**: dbscan (score: 0.517)
2. **Best generalization**: kmeans (score difference: +0.002)
