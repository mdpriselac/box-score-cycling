# FeatureRedundancyAnalyzer

Class for analyzing feature redundancy in rider correlation data and providing feature selection recommendations.

## Class: FeatureRedundancyAnalyzer

### Constructor
```python
FeatureRedundancyAnalyzer(correlation_threshold: float = 0.8)
```
- `correlation_threshold`: Threshold above which features are considered redundant

### Main Methods

#### calculate_feature_correlations
```python
calculate_feature_correlations(
    correlation_results: List[Dict[str, Any]], 
    percentile: str,
    method: str = 'spearman'
) -> Dict[str, Any]
```
Calculate correlations between features based on rider correlation patterns.

**Arguments:**
- `correlation_results`: List of correlation results
- `percentile`: Percentile to analyze (e.g., 'race_features_100')
- `method`: Correlation method ('pearson' or 'spearman')

**Returns:**
Dictionary containing:
- `feature_names`: List of feature names
- `correlation_matrix`: Feature-to-feature correlation matrix
- `p_value_matrix`: Statistical significance matrix
- `method`: Correlation method used
- `data_shape`: Shape of input data

#### identify_redundant_features
```python
identify_redundant_features(
    feature_correlation_data: Dict[str, Any],
    significance_level: float = 0.05
) -> Dict[str, Any]
```
Identify redundant feature pairs and groups.

**Returns:**
Dictionary containing:
- `redundant_pairs`: List of feature pairs exceeding correlation threshold
- `redundant_groups`: Connected components of redundant features
- `redundancy_stats`: Overall redundancy statistics
- `threshold_used`: Correlation threshold applied
- `significance_level`: P-value threshold used

#### recommend_feature_selection
```python
recommend_feature_selection(
    redundancy_data: Dict[str, Any],
    feature_quality_scores: Dict[str, float] = None,
    max_features: int = None
) -> Dict[str, Any]
```
Recommend which features to keep based on redundancy and quality.

**Arguments:**
- `redundancy_data`: Output from identify_redundant_features
- `feature_quality_scores`: Dictionary mapping feature names to quality scores
- `max_features`: Maximum number of features to recommend

**Returns:**
Dictionary containing:
- `group_selections`: Feature selections for each redundant group
- `features_to_keep`: List of recommended features to retain
- `features_to_remove`: List of features recommended for removal
- `reduction_stats`: Statistics on feature reduction
- `final_selection`: Final feature list if max_features specified

#### analyze_mutual_information
```python
analyze_mutual_information(
    correlation_results: List[Dict[str, Any]], 
    percentile: str,
    target_feature: str = None
) -> Dict[str, Any]
```
Calculate mutual information between features for alternative redundancy measure.

**Returns:**
Dictionary containing:
- `mutual_information_scores`: MI scores for each feature pair
- `sorted_scores`: Features sorted by MI score
- `top_10_features`: Top 10 features by mutual information

### Key Features
- Identifies redundant feature groups using graph-based connected components
- Provides multiple redundancy metrics (correlation, mutual information)
- Handles statistical significance testing
- Recommends optimal feature selection based on quality scores
- Calculates comprehensive redundancy statistics
- Supports both Pearson and Spearman correlation methods
- Gracefully handles missing correlation data