# Race Kind Method Comparison Report

**Percentile**: 90th
**Generated**: 2025-07-08 08:15:49
**Competition Type**: gc
**Feature Selection**: Yes
**Features Selected**: 7
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.797 | 3 | 0.831 | +0.034 |
| hierarchical | 0.793 | 3 | 0.831 | +0.038 |
| gaussian_mixture | 0.798 | 3 | 0.834 | +0.036 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | 0.878 | 2 | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.797

**Cluster Distribution**:

- Cluster 0: 454 races (90.1%)
- Cluster 1: 46 races (9.1%)
- Cluster 2: 4 races (0.8%)

**Evaluation Performance**:

- Training score: 0.797
- Evaluation score: 0.831
- Score difference: +0.034
- Evaluation races: 1021
### Hierarchical

- **Best number of clusters**: 3
- **Silhouette score**: 0.793

**Cluster Distribution**:

- Cluster 0: 456 races (90.5%)
- Cluster 1: 46 races (9.1%)
- Cluster 2: 2 races (0.4%)

**Evaluation Performance**:

- Training score: 0.793
- Evaluation score: 0.831
- Score difference: +0.038
- Evaluation races: 1021
### Gaussian Mixture

- **Best number of components**: 3
- **Silhouette score**: 0.798
- **BIC**: 8152.4
- **AIC**: 7700.5

**Evaluation Performance**:

- Training score: 0.798
- Evaluation score: 0.834
- Score difference: +0.036
- Evaluation races: 1021
### Feature Based

- **Error**: Missing required features: ['biggest_group_metric', 'selection_metric', 'proportion_in_groups', 'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio', 'variance_normalized']
### Dbscan

- **Best eps**: 0.863
- **Best min_samples**: 7
- **Silhouette score**: 0.878
- **Clusters found**: 2
- **Noise points**: 133
- **Noise ratio**: 26.4%

## Selected Features

1. winning_time
2. variance_absolute
3. std_group_size
4. time_gap_evenness_metric
5. total_groups
6. riders_in_groups
7. clumpiness_score

## Recommendations

1. **Best performing method**: dbscan (score: 0.878)
2. **Best generalization**: kmeans (score difference: +0.034)
