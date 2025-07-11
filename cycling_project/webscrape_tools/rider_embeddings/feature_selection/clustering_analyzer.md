# ClusteringQualityAnalyzer

Class for analyzing clustering quality of rider correlation data across percentiles.

## Class: ClusteringQualityAnalyzer

### Constructor
```python
ClusteringQualityAnalyzer(random_state: int = 42)
```
- `random_state`: Random state for reproducible results

### Main Methods

#### prepare_correlation_matrix
```python
prepare_correlation_matrix(
    correlation_results: List[Dict[str, Any]], 
    percentile: str,
    min_features: int = 5
) -> Tuple[np.ndarray, List[int], List[str]]
```
Convert correlation results to a matrix suitable for clustering.

**Returns:** Tuple of (correlation_matrix, rider_result_ids, feature_names)

#### analyze_clustering_quality
```python
analyze_clustering_quality(
    correlation_results: List[Dict[str, Any]], 
    percentile: str,
    k_range: List[int] = None,
    scale_features: bool = True
) -> Dict[str, Any]
```
Analyze clustering quality for a specific percentile.

**Arguments:**
- `correlation_results`: List of correlation results
- `percentile`: Percentile to analyze (e.g., 'race_features_100')
- `k_range`: Range of k values to test (default: [2,3,4,5,6,7,8])
- `scale_features`: Whether to standardize features before clustering

**Returns:**
Dictionary containing:
- `clustering_results`: Quality metrics for each k value
- `optimal_k`: Best number of clusters
- `pca_analysis`: Principal component analysis results
- `data_shape`: Shape of correlation matrix

**Quality Metrics:**
- `silhouette_score`: Cluster separation quality (higher is better)
- `calinski_harabasz_score`: Cluster density ratio (higher is better)
- `davies_bouldin_score`: Average cluster similarity (lower is better)
- `size_balance`: Cluster size uniformity (lower is better)

#### compare_percentiles
```python
compare_percentiles(
    correlation_results: List[Dict[str, Any]],
    percentiles: List[str] = None,
    k_range: List[int] = None
) -> Dict[str, Any]
```
Compare clustering quality across multiple percentiles.

**Returns:**
- `percentile_analyses`: Full analysis for each percentile
- `percentile_scores`: Composite quality scores
- `ranked_percentiles`: Percentiles ranked by clustering quality
- `best_percentile`: Percentile with best clustering performance

#### get_cluster_characteristics
```python
get_cluster_characteristics(
    correlation_results: List[Dict[str, Any]], 
    percentile: str,
    k: int = None
) -> Dict[str, Any]
```
Analyze characteristics of clusters for optimal interpretation.

**Returns:**
Dictionary with detailed cluster analysis including:
- `cluster_characteristics`: Statistics and top features for each cluster
- `feature_names`: List of all features used
- `silhouette_score`: Overall clustering quality

### Key Features
- Uses multiple clustering quality metrics for robust evaluation
- Automatically finds optimal number of clusters
- Provides PCA analysis for dimensionality assessment
- Handles missing correlation data gracefully
- Standardizes features for fair comparison
- Generates interpretable cluster characteristics