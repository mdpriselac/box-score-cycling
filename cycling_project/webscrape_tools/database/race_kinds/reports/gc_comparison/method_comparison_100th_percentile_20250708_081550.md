# Race Kind Method Comparison Report

**Percentile**: 100th
**Generated**: 2025-07-08 08:15:50
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 11
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.755 | 4 | 0.779 | +0.024 |
| hierarchical | 0.748 | 5 | 0.606 | -0.143 |
| gaussian_mixture | 0.744 | 3 | 0.772 | +0.029 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.828 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 4
- **Silhouette score**: 0.755

**Cluster Distribution**:

- Cluster 0: 447 races (88.7%)
- Cluster 1: 7 races (1.4%)
- Cluster 2: 46 races (9.1%)
- Cluster 3: 4 races (0.8%)

**Evaluation Performance**:

- Training score: 0.755
- Evaluation score: 0.779
- Score difference: +0.024
- Evaluation races: 1021
### Hierarchical

- **Best number of clusters**: 5
- **Silhouette score**: 0.748

**Cluster Distribution**:

- Cluster 0: 433 races (85.9%)
- Cluster 1: 7 races (1.4%)
- Cluster 2: 49 races (9.7%)
- Cluster 3: 13 races (2.6%)
- Cluster 4: 2 races (0.4%)

**Evaluation Performance**:

- Training score: 0.748
- Evaluation score: 0.606
- Score difference: -0.143
- Evaluation races: 1021
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.744
- **BIC**: 8874.2
- **AIC**: 7890.3

**Evaluation Performance**:

- Training score: 0.744
- Evaluation score: 0.772
- Score difference: +0.029
- Evaluation races: 1021
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 1.666
- **Best min_samples**: 10
- **Silhouette score**: 0.828
- **Clusters found**: 2
- **Noise points**: 95
- **Noise ratio**: 18.8%

## Selected Features

1. winning_time
2. variance_absolute
3. largest_group_size
4. shannon_entropy_normalized
5. std_group_size
6. time_gap_evenness_metric
7. total_groups
8. riders_in_groups
9. clumpiness_score
10. skewness_normalized
11. gini_coefficient

## Recommendations

1. **Best performing method**: dbscan (score: 0.828)
2. **Best generalization**: kmeans (score difference: +0.024)
