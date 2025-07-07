# Race Kind Analysis Module

This module provides comprehensive tools for identifying and categorizing cycling races into different kinds based on their statistical and engineered features.

## Class: RaceKindAnalyzer

### Constructor
```python
RaceKindAnalyzer(db_path: str, feature_columns: Optional[List[str]] = None)
```
- `db_path`: Path to the SQLite database containing race features
- `feature_columns`: List of feature columns to use (None for default set)

### Methods

#### set_feature_columns
```python
set_feature_columns(feature_columns: List[str])
```
Set the feature columns to use for analysis.
- `feature_columns`: List of feature column names

#### load_data
```python
load_data(table_name: str, competition_type: Optional[str] = None, race_category: Optional[str] = None, min_finishers: int = 30) -> pd.DataFrame
```
Load race feature data from a specific percentile table.
- `table_name`: Name of the percentile table (e.g., 'race_features_70')
- `competition_type`: Filter by type ('gc', 'stage', 'one_day', 'stage_one_day' for both stage and one-day races)
- `race_category`: Filter by category ('wt', 'pro', 'd1')
- `min_finishers`: Minimum number of finishers required

#### prepare_features
```python
prepare_features(scaling_method: str = 'standard') -> np.ndarray
```
Prepare and scale features for analysis.
- `scaling_method`: 'standard' for StandardScaler, 'robust' for RobustScaler
- Returns: Scaled feature array

#### kmeans_clustering
```python
kmeans_clustering(n_clusters_range: range = range(2, 11), random_state: int = 42) -> Dict[str, Any]
```
Perform K-means clustering with evaluation metrics.
- `n_clusters_range`: Range of cluster numbers to try
- `random_state`: Random seed for reproducibility
- Returns: Dictionary with clustering results, evaluation metrics, and best parameters

#### hierarchical_clustering
```python
hierarchical_clustering(n_clusters_range: range = range(2, 11), linkage_method: str = 'ward') -> Dict[str, Any]
```
Perform hierarchical clustering.
- `n_clusters_range`: Range of cluster numbers to try
- `linkage_method`: Linkage method ('ward', 'complete', 'average', 'single')
- Returns: Dictionary with clustering results and evaluation metrics

#### dbscan_clustering
```python
dbscan_clustering(eps_range: List[float] = None, min_samples_range: List[int] = None) -> Dict[str, Any]
```
Perform DBSCAN clustering for density-based clustering.
- `eps_range`: Range of epsilon values (auto-calculated if None)
- `min_samples_range`: Range of min_samples values (default: [3, 5, 7, 10])
- Returns: Dictionary with parameter sweep results

#### gaussian_mixture_clustering
```python
gaussian_mixture_clustering(n_components_range: range = range(2, 11), random_state: int = 42) -> Dict[str, Any]
```
Perform Gaussian Mixture Model clustering.
- `n_components_range`: Range of component numbers to try
- `random_state`: Random seed
- Returns: Dictionary with GMM results including AIC/BIC scores

#### pca_analysis
```python
pca_analysis(n_components: int = None) -> Dict[str, Any]
```
Perform PCA for dimensionality reduction and feature importance analysis.
- `n_components`: Number of components (None for all)
- Returns: Dictionary with transformed features, variance explained, and feature importance

#### feature_based_scoring
```python
feature_based_scoring() -> Dict[str, Any]
```
Create custom scoring systems based on cycling race characteristics:
- Sprint Finish Score: High group sizes, low selection
- Selective Race Score: High selection, high spread
- Attritional Race Score: High abandons, large time gaps
- Balanced Race Score: Even gaps, medium selection
- Returns: Dictionary with scores and dominant race types

#### evaluate_clustering_stability
```python
evaluate_clustering_stability(method_results: Dict[str, Any], n_iterations: int = 10, subsample_ratio: float = 0.8) -> Dict[str, float]
```
Evaluate clustering stability through subsampling.
- `method_results`: Results from a clustering method
- `n_iterations`: Number of subsampling iterations
- `subsample_ratio`: Ratio of data to use in each iteration
- Returns: Stability metrics (mean, std, min, max)

#### get_cluster_characteristics
```python
get_cluster_characteristics(labels: np.ndarray, top_n_features: int = 5) -> Dict[int, Dict[str, Any]]
```
Get detailed characteristics of each cluster.
- `labels`: Cluster labels from any clustering method
- `top_n_features`: Number of top distinguishing features to return
- Returns: Dictionary with cluster sizes, top features, race types, and example races

## Example Usage

```python
# Initialize analyzer
analyzer = RaceKindAnalyzer(db_path)

# Load data from 70th percentile table
data = analyzer.load_data('race_features_70', competition_type='stage_one_day')

# Prepare features
scaled_features = analyzer.prepare_features(scaling_method='robust')

# Try different clustering methods
kmeans_results = analyzer.kmeans_clustering(range(2, 8))
hierarchical_results = analyzer.hierarchical_clustering(range(2, 8))
gmm_results = analyzer.gaussian_mixture_clustering(range(2, 8))

# Get feature-based scoring
scoring_results = analyzer.feature_based_scoring()

# Analyze best clustering
best_k = kmeans_results['best_n_clusters']
best_labels = kmeans_results['cluster_results'][best_k]['labels']
cluster_chars = analyzer.get_cluster_characteristics(best_labels)

# Evaluate stability
stability = analyzer.evaluate_clustering_stability(kmeans_results)
```

## Features Used

The analyzer uses these key features:
- Statistical: variance, standard deviation, skewness, kurtosis, gini coefficient, entropy
- Engineered: group metrics, time gap evenness, clumpiness, selection metric
- Percentile gaps: 10th, 25th, 50th percentile time gaps
- Group characteristics: proportion in groups, average group size