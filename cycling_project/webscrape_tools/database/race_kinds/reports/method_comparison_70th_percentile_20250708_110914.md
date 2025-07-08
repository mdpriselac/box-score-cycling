# Race Kind Method Comparison Report

**Percentile**: 70th
**Generated**: 2025-07-08 11:09:14
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 14
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.248 | 3 | 0.248 | -0.000 |
| hierarchical | 0.352 | 3 | 0.202 | -0.149 |
| gaussian_mixture | 0.222 | 3 | 0.206 | -0.016 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.763 | 2 | 0.605 | -0.158 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.248

**Cluster Distribution**:

- Cluster 0: 226 races (41.9%)
- Cluster 1: 11 races (2.0%)
- Cluster 2: 303 races (56.1%)

**Evaluation Performance**:

- Training score: 0.248
- Evaluation score: 0.248
- Score difference: -0.000
- Evaluation races: 1399
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.352

**Cluster Distribution**:

- Cluster 0: 450 races (83.3%)
- Cluster 1: 11 races (2.0%)
- Cluster 2: 79 races (14.6%)

**Evaluation Performance**:

- Training score: 0.352
- Evaluation score: 0.202
- Score difference: -0.149
- Evaluation races: 1399
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.222
- **BIC**: 8006.5
- **AIC**: 6465.8

**Evaluation Performance**:

- Training score: 0.222
- Evaluation score: 0.206
- Score difference: -0.016
- Evaluation races: 1399
### Feature Based

- **Error**: Missing required features: ['selection_metric', 'std_deviation_normalized', 'abandon_ratio', 'clumpiness_score', 'variance_normalized']
### Dbscan

- **Best eps**: 2.130
- **Best min_samples**: 5
- **Silhouette score**: 0.763
- **Clusters found**: 2
- **Noise points**: 20
- **Noise ratio**: 3.7%

**Evaluation Performance**:

- Training score: 0.763
- Evaluation score: 0.605
- Score difference: -0.158
- Evaluation races: 1399

## Selected Features

1. biggest_group_metric
2. largest_group_position
3. total_finishers
4. avg_group_size
5. proportion_in_groups
6. std_group_size
7. shannon_entropy_normalized
8. shannon_entropy_absolute
9. largest_group_size
10. gini_coefficient
11. 50th_percentile_gap
12. time_gap_evenness_metric
13. total_race_duration
14. variance_absolute

## Recommendations

1. **Best performing method**: dbscan (score: 0.763)
2. **Best generalization**: kmeans (score difference: -0.000)
