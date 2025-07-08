# Race Kind Models Module

This module provides functionality for saving, loading, and applying race clustering models, as well as calculating advanced race kind features.

## Classes

### PredictableAgglomerativeClustering
A wrapper for scikit-learn's AgglomerativeClustering that adds prediction capabilities.

**Constructor:**
```python
PredictableAgglomerativeClustering(n_clusters=4, **kwargs)
```
- `n_clusters`: Number of clusters to form
- `**kwargs`: Additional arguments passed to AgglomerativeClustering

**Methods:**
- `fit(X)`: Fit the clustering model and calculate cluster centers
- `predict(X)`: Assign new samples to nearest cluster center
- `transform(X)`: Get distances to all cluster centers
- `fit_predict(X)`: Fit and return labels

### RaceKindModelManager
Main class for managing race kind models and feature extraction.

**Constructor:**
```python
RaceKindModelManager(db_path: str, model_dir: str = "database/race_kinds/models")
```
- `db_path`: Path to the SQLite database
- `model_dir`: Directory to store saved models

## Methods

### save_model
```python
save_model(model, algorithm: str, percentile: int, feature_columns: List[str], scaler, metadata: Dict = None) -> str
```
Save a trained clustering model and its metadata.
- `model`: Trained clustering model (KMeans, PredictableAgglomerativeClustering, DBSCAN, or GaussianMixture)
- `algorithm`: Algorithm name ('kmeans', 'hierarchical', 'dbscan', 'gaussian_mixture')
- `percentile`: Percentile used for training
- `feature_columns`: List of feature column names used
- `scaler`: Fitted scaler used for feature normalization
- `metadata`: Additional metadata (scores, parameters, etc.)
- Returns: Path to saved model file

### load_model
```python
load_model(model_path: str) -> Dict
```
Load a saved model and its metadata.
- `model_path`: Path to the saved model file
- Returns: Dictionary containing model, scaler, and metadata

### calculate_race_kind_features
```python
calculate_race_kind_features(X: np.ndarray, model, algorithm: str, labels: Optional[np.ndarray] = None) -> pd.DataFrame
```
Calculate comprehensive race kind features including:
- One-hot encoded cluster membership
- Distances to all cluster centers
- Local density (average distance to k nearest neighbors in same cluster)
- Boundary distance (distance to nearest point in different cluster)
- Cluster label
- Probability scores (for Gaussian Mixture models)

### create_race_kind_features_table
```python
create_race_kind_features_table(table_name: str, algorithm: str, percentile: int, feature_columns: List[str], metadata: Dict = None)
```
Create a database table to store race kind features.
- `table_name`: Name for the new table
- `algorithm`: Algorithm used
- `percentile`: Percentile used
- `feature_columns`: List of original features used for clustering
- `metadata`: Additional metadata to store

### store_race_kind_features
```python
store_race_kind_features(table_name: str, competition_ids: List[int], features_df: pd.DataFrame)
```
Store calculated race kind features in the database.
- `table_name`: Table name to store features
- `competition_ids`: List of competition IDs
- `features_df`: DataFrame with calculated features

### predict_and_store_new_races
```python
predict_and_store_new_races(model_path: str, source_table: str, target_table: str, competition_ids: Optional[List[int]] = None, competition_type: Optional[str] = None, race_category: Optional[str] = None) -> int
```
Apply a saved model to races from the database and store results.
- `model_path`: Path to saved model
- `source_table`: Table containing race features (e.g., 'race_features_70')
- `target_table`: Table to store race kind features
- `competition_ids`: Specific competition IDs to process (if None, process all)
- `competition_type`: Filter by competition type
- `race_category`: Filter by race category
- Returns: Number of races processed

### apply_model_to_new_races
```python
apply_model_to_new_races(model_path: str, new_data: pd.DataFrame, competition_ids: List[int]) -> pd.DataFrame
```
Apply a saved model to new race data (from DataFrame).
- `model_path`: Path to saved model
- `new_data`: DataFrame with race features (must have same columns as training)
- `competition_ids`: List of competition IDs for the new races
- Returns: DataFrame with race kind features

### list_saved_models
```python
list_saved_models() -> List[Dict]
```
List all saved models with their metadata.
- Returns: List of dictionaries containing model information, sorted by timestamp (newest first)