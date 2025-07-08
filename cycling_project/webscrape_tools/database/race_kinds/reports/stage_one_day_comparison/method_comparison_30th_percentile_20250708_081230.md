# Race Kind Method Comparison Report

**Percentile**: 30th
**Generated**: 2025-07-08 08:12:30
**Competition Type**: stage_one_day
**Feature Selection**: Yes
**Features Selected**: 10
**Feature Selection Categories**: ['wt', 'pro']
**Analysis Categories**: ['wt', 'pro']
**Evaluation Categories**: ['wt', 'pro', 'd1']

## Method Performance Summary

| Method | Best Score | Clusters/Types | Eval Score | Score Diff |
|--------|------------|----------------|------------|------------|
| kmeans | 0.846 | 3 | 0.838 | -0.008 |
| hierarchical | 0.761 | 4 | 0.816 | +0.055 |
| gaussian_mixture | 0.372 | 7 | 0.313 | -0.059 |
| feature_based | 0.000 | N/A | N/A | N/A |
| dbscan | -inf | Failed | N/A | N/A |

## Detailed Method Results

### Kmeans

- **Best number of clusters**: 3
- **Silhouette score**: 0.846

**Cluster Distribution**:

- Cluster 0: 3494 races (93.8%)
- Cluster 1: 195 races (5.2%)
- Cluster 2: 35 races (0.9%)

**Evaluation Performance**:

- Training score: 0.846
- Evaluation score: 0.838
- Score difference: -0.008
- Evaluation races: 5773
### Hierarchical

- **Best number of clusters**: 4
- **Silhouette score**: 0.761

**Cluster Distribution**:

- Cluster 0: 397 races (10.7%)
- Cluster 1: 48 races (1.3%)
- Cluster 2: 3269 races (87.8%)
- Cluster 3: 10 races (0.3%)

**Evaluation Performance**:

- Training score: 0.761
- Evaluation score: 0.816
- Score difference: +0.055
- Evaluation races: 5773
### Gaussian Mixture

- **Best number of components**: 7
- **Silhouette score**: 0.372
- **BIC**: -127948.8
- **AIC**: -130817.4

**Evaluation Performance**:

- Training score: 0.372
- Evaluation score: 0.313
- Score difference: -0.059
- Evaluation races: 5773
### Feature Based

- **Error**: Missing required features: ['proportion_in_groups', 'abandon_ratio', 'time_gap_evenness_metric', 'variance_normalized']
### Dbscan

- **Status**: Failed to find suitable parameters

## Selected Features

1. biggest_group_metric
2. clumpiness_score
3. avg_group_size
4. selection_metric
5. gini_coefficient
6. std_deviation_normalized
7. total_race_duration
8. 50th_percentile_gap
9. variance_absolute
10. skewness_normalized

## Recommendations

1. **Best performing method**: kmeans (score: 0.846)
2. **Best generalization**: kmeans (score difference: -0.008)
