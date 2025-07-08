# Race Kind Method Comparison Report

**Percentile**: 60th
**Generated**: 2025-07-08 11:09:12
**Competition Type**: one_day
**Feature Selection**: Yes
**Features Selected**: 15
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.405 | 3 | 0.416 | +0.011 |
| hierarchical | 0.293 | 4 | 0.369 | +0.076 |
| gaussian_mixture | 0.271 | 3 | 0.271 | +0.000 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.592 | 3 | 0.327 | -0.265 |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.405

**Cluster Distribution**:

- Cluster 0: 421 races (80.2%)
- Cluster 1: 66 races (12.6%)
- Cluster 2: 38 races (7.2%)

**Evaluation Performance**:

- Training score: 0.405
- Evaluation score: 0.416
- Score difference: +0.011
- Evaluation races: 1341
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.293

**Cluster Distribution**:

- Cluster 0: 136 races (25.9%)
- Cluster 1: 4 races (0.8%)
- Cluster 2: 369 races (70.3%)
- Cluster 3: 16 races (3.0%)

**Evaluation Performance**:

- Training score: 0.293
- Evaluation score: 0.369
- Score difference: +0.076
- Evaluation races: 1341
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.271
- **BIC**: 8730.7
- **AIC**: 6995.4

**Evaluation Performance**:

- Training score: 0.271
- Evaluation score: 0.271
- Score difference: +0.000
- Evaluation races: 1341
### Feature Based

- **Error**: Missing required features: ['std_deviation_normalized', 'abandon_ratio']
### Dbscan

- **Best eps**: 1.590
- **Best min_samples**: 5
- **Silhouette score**: 0.592
- **Clusters found**: 3
- **Noise points**: 95
- **Noise ratio**: 18.1%

**Evaluation Performance**:

- Training score: 0.592
- Evaluation score: 0.327
- Score difference: -0.265
- Evaluation races: 1341

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. variance_normalized
4. total_finishers
5. avg_group_size
6. proportion_in_groups
7. gini_coefficient
8. std_group_size
9. variance_absolute
10. selection_metric
11. 50th_percentile_gap
12. largest_group_size
13. shannon_entropy_absolute
14. total_race_duration
15. time_gap_evenness_metric

## Recommendations

1. **Best performing method**: dbscan (score: 0.592)
2. **Best generalization**: gaussian_mixture (score difference: +0.000)
