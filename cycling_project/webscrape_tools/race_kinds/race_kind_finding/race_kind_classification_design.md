# Race Kind Classification System Design

## Overview
Based on the gradient feature analysis, we need to classify non-time trial stage competitions into distinct kinds. The analysis identified 15 features with separability potential, with the top performers being:
- kurtosis_breakdown_point (score: 2.6184)
- nth_percentile_gap_5 (score: 2.4599)
- nth_percentile_gap_25 (score: 1.7974)

## Approach 1: Unsupervised Clustering

### 1.1 K-Means Clustering
- **Features**: Use top 3-5 gradient features
- **Preprocessing**: Standardize features to same scale
- **Number of clusters**: Use elbow method or silhouette analysis
- **Advantages**: Simple, fast, interpretable centroids
- **Disadvantages**: Assumes spherical clusters, sensitive to outliers

### 1.2 DBSCAN Clustering
- **Features**: Same top gradient features
- **Preprocessing**: Standardize features
- **Parameters**: eps and min_samples tuned via grid search
- **Advantages**: Can find arbitrary shaped clusters, handles outliers
- **Disadvantages**: Sensitive to parameter choice

### 1.3 Hierarchical Clustering
- **Features**: All gradient features with score > 1.0
- **Method**: Ward linkage
- **Advantages**: Produces dendrogram for interpretability
- **Disadvantages**: Computationally expensive for large datasets

## Approach 2: Rule-Based Classification

### 2.1 Breakdown Point Rules
- **Primary Rule**: kurtosis_breakdown_point presence/absence
- **Secondary Rules**: 
  - If no breakdown: classify by nth_percentile_gap_5 thresholds
  - If breakdown exists: classify by breakdown percentile value
- **Advantages**: Highly interpretable, domain-meaningful
- **Disadvantages**: May miss complex patterns

### 2.2 Gradient Threshold Rules
- **Feature Combinations**:
  - High vs Low nth_percentile_gap_5_slope
  - High vs Low volatility measures
  - Monotonicity score ranges
- **Decision Tree**: Build manual rules based on thresholds
- **Advantages**: Clear logic, easy to explain
- **Disadvantages**: Requires manual threshold tuning

## Approach 3: Hybrid Methods

### 3.1 Two-Stage Classification
1. **Stage 1**: Rule-based initial grouping (breakdown vs no-breakdown)
2. **Stage 2**: Clustering within each group
- **Advantages**: Combines interpretability with pattern discovery
- **Disadvantages**: More complex implementation

### 3.2 Feature Engineering + Clustering
- **Engineered Features**:
  - Ratio of nth_percentile_gap_5 to nth_percentile_gap_50
  - Combined breakdown indicator (variance + kurtosis)
  - Gradient stability score
- **Clustering**: Apply k-means or DBSCAN on engineered features
- **Advantages**: May capture complex relationships
- **Disadvantages**: Less interpretable

## Evaluation Framework

### Metrics for Unsupervised Classification:
1. **Internal Validation**:
   - Silhouette score
   - Calinski-Harabasz index
   - Davies-Bouldin index
   
2. **Stability Analysis**:
   - Bootstrap resampling
   - Cross-validation on time splits
   
3. **Domain Validation**:
   - Cluster size distribution
   - Feature distribution within clusters
   - Manual inspection of exemplar races

### Evaluation Process:
1. Split data temporally (80/20)
2. Apply each method to training set
3. Evaluate cluster quality metrics
4. Test stability on validation set
5. Profile clusters by examining:
   - Average feature values
   - Race characteristics (category, year, etc.)
   - Sample races from each cluster

## Recommended Implementation Order

1. **Start with K-Means** (3-5 clusters) on top 3 features
2. **Implement rule-based** using kurtosis_breakdown_point
3. **Try DBSCAN** for comparison
4. **Develop hybrid approach** if needed
5. **Create visualization tools** for cluster inspection

## Next Steps
1. Implement k-means clustering prototype
2. Create cluster evaluation functions
3. Build visualization for cluster profiles
4. Test on full dataset and iterate