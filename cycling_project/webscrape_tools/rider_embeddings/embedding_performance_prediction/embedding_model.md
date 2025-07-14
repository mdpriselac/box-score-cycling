# embedding_model.py

Two-stage LightGBM model for rider performance prediction using embeddings.

## Classes

### EmbeddingPerformanceModel

Two-stage model (classification + regression) for predicting UCI points using rider embeddings.

#### Methods

##### `__init__(race_type: str, random_state: int = 42)`
Initialize the embedding performance model.

**Parameters:**
- `race_type` (str): One of ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
- `random_state` (int): Random seed for reproducibility

##### `train(train_df: pd.DataFrame, valid_df: Optional[pd.DataFrame] = None, target_col: str = 'uci_points_proportional', num_boost_round: int = 1000, early_stopping_rounds: int = 50, verbose: bool = True) -> Dict`
Train the two-stage model.

**Parameters:**
- `train_df` (pd.DataFrame): Training DataFrame from data preparation
- `valid_df` (Optional[pd.DataFrame]): Validation DataFrame (if None, uses 20% split)
- `target_col` (str): Target column name
- `num_boost_round` (int): Maximum number of boosting rounds
- `early_stopping_rounds` (int): Early stopping patience
- `verbose` (bool): Whether to print training progress

**Returns:**
- `Dict`: Training metrics and model information including RMSE, MAE, AUC, feature counts

##### `predict(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray`
Make predictions using the two-stage model.

**Parameters:**
- `X` (Union[pd.DataFrame, np.ndarray]): Feature matrix

**Returns:**
- `np.ndarray`: Predicted UCI points (non-negative)

##### `predict_proba_nonzero(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray`
Predict probability of earning non-zero points.

**Parameters:**
- `X` (Union[pd.DataFrame, np.ndarray]): Feature matrix

**Returns:**
- `np.ndarray`: Probability of non-zero points

##### `get_feature_importance(stage: str = 'both', n_features: Optional[int] = None) -> pd.DataFrame`
Get feature importance.

**Parameters:**
- `stage` (str): 'classifier', 'regressor', or 'both'
- `n_features` (Optional[int]): Number of top features to return (None for all)

**Returns:**
- `pd.DataFrame`: DataFrame with columns: feature, importance, stage, is_embedding

##### `save(filepath: str)`
Save the model to disk.

**Parameters:**
- `filepath` (str): Path to save the model (without extension)

**Files created:**
- `{filepath}_classifier.txt`: LightGBM classifier model
- `{filepath}_regressor.txt`: LightGBM regressor model
- `{filepath}_metadata.json`: Model metadata and configuration

##### `load(filepath: str)`
Load the model from disk.

**Parameters:**
- `filepath` (str): Path to load the model from (without extension)

## Model Architecture

### Two-Stage Approach
1. **Classification Stage**: Predicts probability of earning non-zero points
   - Binary objective with `is_unbalance=True`
   - Conservative parameters (num_leaves=31)
   
2. **Regression Stage**: Predicts actual point values for non-zero cases
   - Trained only on non-zero samples
   - Higher capacity (num_leaves=63) with regularization

3. **Final Prediction**: `final_pred = prob > 0.5 ? regressor_pred : 0`

### Key Features
- Separates embedding features (corr_*, n_races) from database features
- Handles zero-inflated UCI points distribution
- Tracks comprehensive performance metrics
- Supports model persistence with metadata

## Usage Example

```python
from embedding_model import EmbeddingPerformanceModel
from data_preparation import EmbeddingDataPreparation

# Prepare data
prep = EmbeddingDataPreparation(db_path, embedding_path)
gc_data = prep.prepare_race_type_data('gc')
train_df, test_df = prep.split_by_year(gc_data, test_year=2023)

# Train model
model = EmbeddingPerformanceModel(race_type='gc')
training_info = model.train(
    train_df=train_df,
    valid_df=test_df,
    verbose=True
)

# Get feature importance
importance = model.get_feature_importance(stage='both', n_features=20)
print(importance)

# Save model
model.save("models/gc_embedding_model_2023")
```