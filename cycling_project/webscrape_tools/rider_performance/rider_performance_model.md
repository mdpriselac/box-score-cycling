# rider_performance_model.py

LightGBM-based global models for rider performance prediction with two-stage approach to handle zero-inflated UCI points.

## Overview

This module implements two global models:
1. **GC Model**: For General Classification races
2. **Stage/One-day Model**: For Stage and One-day races

Each model uses a **two-stage approach** to handle the zero-inflated nature of UCI points:
- **Stage 1**: Classification (0 vs non-0 points) - handles the 80-90% of results with 0 points
- **Stage 2**: Regression (actual point values) - predicts points for cases likely to score

## Classes

### RiderPerformanceModel

Two-stage LightGBM model for rider performance prediction.

#### Methods

##### `__init__(model_type: str = 'gc', random_state: int = 42)`
Initialize the rider performance model.

**Parameters:**
- `model_type` (str): Either 'gc' or 'stage_one_day'
- `random_state` (int): Random seed for reproducibility

##### `train(train_df: pd.DataFrame, valid_df: Optional[pd.DataFrame] = None, target_col: str = 'uci_points_actual', num_boost_round: int = 1000, early_stopping_rounds: int = 50, verbose: bool = True) -> Dict`
Train the two-stage model.

**Parameters:**
- `train_df` (pd.DataFrame): Training DataFrame from DatasetGenerator
- `valid_df` (Optional[pd.DataFrame]): Validation DataFrame (if None, uses 20% split)
- `target_col` (str): Target column name ('uci_points_actual' or 'uci_points_proportional')
- `num_boost_round` (int): Maximum number of boosting rounds
- `early_stopping_rounds` (int): Early stopping patience
- `verbose` (bool): Whether to print training progress

**Returns:**
- `Dict`: Training metrics and model information

##### `predict(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray`
Make predictions using the two-stage model.

**Parameters:**
- `X` (Union[pd.DataFrame, np.ndarray]): Feature matrix

**Returns:**
- `np.ndarray`: Predicted UCI points

##### `predict_proba_nonzero(X: Union[pd.DataFrame, np.ndarray]) -> np.ndarray`
Predict probability of earning non-zero points.

**Parameters:**
- `X` (Union[pd.DataFrame, np.ndarray]): Feature matrix

**Returns:**
- `np.ndarray`: Probability of non-zero points

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

##### `get_top_features(n: int = 20, stage: str = 'both') -> pd.DataFrame`
Get top n most important features.

**Parameters:**
- `n` (int): Number of top features to return
- `stage` (str): 'classifier', 'regressor', or 'both'

**Returns:**
- `pd.DataFrame`: Feature names and importance scores

## Usage Examples

### Basic Training
```python
from dataset_generator import DatasetGenerator
from rider_performance_model import RiderPerformanceModel

# Generate training data
generator = DatasetGenerator(db_path)
datasets = generator.generate_datasets(
    cutoff_date="2023-12-31",
    min_results=10,
    target_variable='uci_points_actual'
)

# Train GC model
gc_model = RiderPerformanceModel(model_type='gc')
training_info = gc_model.train(
    train_df=datasets['gc_dataset'],
    target_col='uci_points_actual',
    num_boost_round=1000,
    early_stopping_rounds=50
)

print(f"Training complete! RMSE: {training_info['performance_metrics']['rmse_overall']:.4f}")
```

### Making Predictions
```python
from feature_builder import FeatureBuilder

# For individual predictions
builder = FeatureBuilder(db_path)
features = builder.get_prediction_features(
    rider_id=1234,
    competition_id=5678,
    cutoff_date="2024-06-14"
)

# Convert to feature vector
feature_df = pd.DataFrame([features])
feature_cols = gc_model.feature_columns
X = feature_df[feature_cols]

# Get predictions
predicted_points = gc_model.predict(X)[0]
prob_nonzero = gc_model.predict_proba_nonzero(X)[0]

print(f"Predicted points: {predicted_points:.1f}")
print(f"Probability of scoring: {prob_nonzero:.3f}")
```

### Train/Validation Split
```python
from sklearn.model_selection import train_test_split

# Manual train/validation split
gc_data = datasets['gc_dataset']
train_df, valid_df = train_test_split(gc_data, test_size=0.2, random_state=42)

# Train with explicit validation set
training_info = gc_model.train(
    train_df=train_df,
    valid_df=valid_df,
    target_col='uci_points_actual'
)
```

### Model Analysis
```python
# Get feature importance
top_features = gc_model.get_top_features(n=15, stage='both')
print("Top features:")
print(top_features)

# Performance metrics
metrics = gc_model.training_info['performance_metrics']
print(f"Overall RMSE: {metrics['rmse_overall']:.4f}")
print(f"Non-zero RMSE: {metrics['rmse_nonzero']:.4f}")
print(f"Classification AUC: {metrics['auc_classification']:.4f}")
```

### Saving and Loading
```python
# Save trained model
gc_model.save("models/gc_model_v1")

# Load model later
new_model = RiderPerformanceModel(model_type='gc')
new_model.load("models/gc_model_v1")

# Use loaded model
predictions = new_model.predict(test_features)
```

### Backtesting
```python
# Train on historical data, test on specific year
backtest_data = generator.generate_backtest_datasets(test_years=[2023])

# Train on data up to 2022
train_data = backtest_data[2023]['train_gc']
test_data = backtest_data[2023]['test_gc']

gc_model = RiderPerformanceModel(model_type='gc')
gc_model.train(train_df=train_data)

# Evaluate on 2023 data
test_features = gc_model.prepare_features(test_data)[0]
test_targets = test_data['uci_points_actual'].values
predictions = gc_model.predict(test_features)

# Calculate backtest metrics
from sklearn.metrics import mean_squared_error
rmse = np.sqrt(mean_squared_error(test_targets, predictions))
print(f"2023 backtest RMSE: {rmse:.4f}")
```

## Model Architecture Details

### Two-Stage Approach

1. **Classification Stage**:
   - Predicts probability of earning non-zero points
   - Uses `binary` objective with `is_unbalance=True`
   - Handles the 80-90% zero cases effectively

2. **Regression Stage**:
   - Trained only on non-zero samples
   - Predicts actual point values
   - Uses regularization to prevent overfitting

3. **Final Prediction**:
   - Combines both stages using probability threshold (default 0.5)
   - `final_pred = prob > threshold ? regressor_pred : 0`

### Parameters

**Classifier Parameters:**
- `objective`: 'binary'
- `is_unbalance`: True (important for imbalanced data)
- `num_leaves`: 31 (conservative to prevent overfitting)
- `learning_rate`: 0.05

**Regressor Parameters:**
- `objective`: 'regression'
- `num_leaves`: 63 (can be higher since non-zero samples are more homogeneous)
- `reg_alpha/lambda`: 0.1 (L1/L2 regularization)

### Performance Metrics

The model tracks multiple metrics:
- **Overall performance**: RMSE, MAE on all samples
- **Non-zero performance**: RMSE, MAE, R² on samples with points
- **Classification performance**: AUC, accuracy for 0 vs non-0
- **Zero prediction accuracy**: Percentage of correct zero predictions

## Key Features

1. **Automatic Feature Detection**: Identifies race, race kind, and experience features
2. **Missing Value Handling**: Fills missing features with 0
3. **Zero-Inflated Handling**: Two-stage approach optimized for UCI points distribution
4. **Early Stopping**: Prevents overfitting with validation-based stopping
5. **Feature Importance**: Tracks importance for both classification and regression
6. **Model Persistence**: Save/load functionality with metadata
7. **Comprehensive Metrics**: Multiple evaluation metrics for different aspects

## Best Practices

1. **Minimum Samples**: Use at least 1000+ samples for stable training
2. **Validation Strategy**: Always use validation set or cross-validation
3. **Feature Engineering**: Ensure features are properly scaled/engineered
4. **Hyperparameter Tuning**: Consider tuning `num_leaves`, `learning_rate`, threshold
5. **Threshold Optimization**: The 0.5 classification threshold can be optimized
6. **Regular Retraining**: Retrain models as new data becomes available