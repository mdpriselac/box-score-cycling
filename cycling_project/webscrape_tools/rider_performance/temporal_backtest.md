# temporal_backtest.py

Temporal backtesting system for rider performance models with proper temporal train/test splits.

## Overview

This module provides a complete training and evaluation loop:
- Given a test year (e.g., 2022), trains on all prior years (up to 2021-12-31)
- Tests/predicts on the given year (2022-01-01 to 2022-12-31)  
- Uses proper temporal cutoffs to prevent data leakage
- Provides comprehensive evaluation metrics and visualizations

## Classes

### TemporalBacktester

Handles temporal backtesting of rider performance models with proper data isolation.

#### Methods

##### `__init__(db_path: str, output_dir: str = "rider_performance/backtest_results")`
Initialize the temporal backtester.

**Parameters:**
- `db_path` (str): Path to the SQLite database
- `output_dir` (str): Directory to save results, models, and plots

##### `run_temporal_backtest(test_year: int, min_results: int = 10, target_variable: str = 'uci_points_actual', num_boost_round: int = 1000, early_stopping_rounds: int = 50, save_models: bool = True, verbose: bool = True) -> Dict`
Run complete temporal backtest for a given year.

**Parameters:**
- `test_year` (int): Year to test on (e.g., 2022)
- `min_results` (int): Minimum results per rider for inclusion (default: 10)
- `target_variable` (str): 'uci_points_actual' or 'uci_points_proportional'
- `num_boost_round` (int): Max boosting rounds for training (default: 1000)
- `early_stopping_rounds` (int): Early stopping patience (default: 50)
- `save_models` (bool): Whether to save trained models (default: True)
- `verbose` (bool): Whether to print progress (default: True)

**Returns:**
- `Dict`: Complete results including models, predictions, metrics, and feature importance

**Data Split:**
- **Training**: All data up to `{test_year-1}-12-31`
- **Testing**: Data from `{test_year}-01-01` to `{test_year}-12-31`
- **Experience Calculation**: Uses training cutoff date for all test predictions

## Functions

### `run_multiple_years(db_path: str, test_years: List[int] = [2022, 2023, 2024], target_variable: str = 'uci_points_actual', min_results: int = 10) -> Dict`
Run backtests for multiple years.

**Parameters:**
- `db_path` (str): Path to database
- `test_years` (List[int]): List of years to test
- `target_variable` (str): Target variable to use
- `min_results` (int): Minimum results per rider

**Returns:**
- `Dict`: Dictionary with results for all years

## Usage Examples

### Single Year Backtest
```python
from temporal_backtest import TemporalBacktester

db_path = "database/database/cycling_races.db"
backtester = TemporalBacktester(db_path)

# Test 2023: trains on all data up to 2022-12-31, tests on 2023
results = backtester.run_temporal_backtest(
    test_year=2023,
    min_results=10,
    target_variable='uci_points_actual',
    save_models=True,
    verbose=True
)

print(f"GC Model RMSE: {results['metrics']['gc']['rmse_overall']:.4f}")
print(f"Stage/One-day Model RMSE: {results['metrics']['stage_one_day']['rmse_overall']:.4f}")
```

### Multiple Year Evaluation
```python
from temporal_backtest import run_multiple_years

# Run backtests for 2022, 2023, and 2024
all_results = run_multiple_years(
    db_path=db_path,
    test_years=[2022, 2023, 2024],
    target_variable='uci_points_actual',
    min_results=15
)

# Compare performance across years
for year, results in all_results.items():
    if 'error' not in results:
        gc_rmse = results['metrics']['gc']['rmse_overall']
        print(f"{year} GC RMSE: {gc_rmse:.4f}")
```

### Analyzing Results
```python
# Access detailed predictions
gc_predictions = results['predictions']['gc']
y_true = gc_predictions['y_true']
y_pred = gc_predictions['y_pred']
rider_ids = gc_predictions['rider_ids']

# Create custom analysis
import pandas as pd
pred_df = pd.DataFrame({
    'rider_id': rider_ids,
    'actual': y_true,
    'predicted': y_pred,
    'competition': gc_predictions['competition_names']
})

# Find best/worst predictions
pred_df['error'] = pred_df['predicted'] - pred_df['actual']
worst_predictions = pred_df.nlargest(10, 'error')
```

### Comparing Point Schemes
```python
# Run with both point schemes
actual_results = backtester.run_temporal_backtest(
    test_year=2023,
    target_variable='uci_points_actual'
)

proportional_results = backtester.run_temporal_backtest(
    test_year=2023,
    target_variable='uci_points_proportional'
)

# Compare performance
print("Actual UCI Points:")
print(f"  GC RMSE: {actual_results['metrics']['gc']['rmse_overall']:.4f}")

print("Proportional UCI Points:")
print(f"  GC RMSE: {proportional_results['metrics']['gc']['rmse_overall']:.4f}")
```

## Output Structure

### File Organization
```
rider_performance/backtest_results/
├── models/
│   ├── gc_model_2023_uci_points_actual_classifier.txt
│   ├── gc_model_2023_uci_points_actual_regressor.txt
│   ├── gc_model_2023_uci_points_actual_metadata.json
│   └── stage_one_day_model_2023_uci_points_actual_*
├── results/
│   ├── backtest_2022_uci_points_actual.json
│   ├── backtest_2023_uci_points_actual.json
│   └── backtest_2024_uci_points_actual.json
└── plots/
    ├── gc_backtest_2023_uci_points_actual.png
    └── stage_one_day_backtest_2023_uci_points_actual.png
```

### Results Dictionary Structure
```python
{
    'test_year': 2023,
    'train_cutoff': '2022-12-31',
    'target_variable': 'uci_points_actual',
    'data_stats': {
        'gc_dataset': {
            'train_samples': 50000,
            'test_samples': 15000,
            'train_riders': 2500,
            'test_riders': 2200
        }
    },
    'metrics': {
        'gc': {
            'rmse_overall': 12.45,
            'rmse_nonzero': 45.23,
            'auc_classification': 0.85,
            'zero_prediction_accuracy': 0.92,
            'points_ratio': 0.98
        }
    },
    'predictions': {
        'gc': {
            'y_true': [0, 25, 0, 15, ...],
            'y_pred': [0, 23, 0, 18, ...],
            'y_prob_nonzero': [0.1, 0.8, 0.05, 0.7, ...],
            'rider_ids': [1234, 5678, ...],
            'competition_names': ['Tour de France GC', ...]
        }
    },
    'feature_importance': {
        'gc': [
            {'feature': 'total_prior_races', 'importance': 1250.5},
            {'feature': 'rf_variance_absolute', 'importance': 890.2}
        ]
    }
}
```

## Evaluation Metrics

### Comprehensive Metrics Calculated

1. **Sample Distribution**:
   - `n_total`, `n_zeros`, `n_nonzeros`
   - `zero_percentage`

2. **Overall Regression**:
   - `rmse_overall`: RMSE on all samples
   - `mae_overall`: MAE on all samples

3. **Non-Zero Regression**:
   - `rmse_nonzero`: RMSE on samples with points
   - `mae_nonzero`: MAE on samples with points
   - `r2_nonzero`: R² on samples with points

4. **Classification Performance**:
   - `auc_classification`: AUC for 0 vs non-0 classification
   - `accuracy_50/30/70`: Accuracy with different probability thresholds

5. **Points Distribution**:
   - `total_true_points`, `total_pred_points`
   - `points_ratio`: Ratio of predicted to actual total points

6. **Percentile Analysis**:
   - Distribution of high-value predictions vs reality

## Visualization

Each backtest generates evaluation plots:

1. **Predicted vs Actual**: Scatter plot for non-zero samples
2. **Probability Distribution**: Histogram of classification probabilities
3. **Residuals Plot**: Residuals vs actual values
4. **Feature Importance**: Top 10 most important features

## Key Features

1. **Proper Temporal Isolation**: No data leakage between train/test
2. **Experience Calculation**: Uses training cutoff for rider experience features
3. **Comprehensive Evaluation**: Multiple metrics for different aspects
4. **Model Persistence**: Saves trained models for later use
5. **Visualization**: Automatic generation of evaluation plots
6. **Batch Processing**: Support for multiple years
7. **Error Handling**: Graceful handling of missing data or errors

## Best Practices

1. **Minimum Results**: Use `min_results >= 10` for stable evaluation
2. **Multiple Years**: Test on multiple years to assess consistency
3. **Both Point Schemes**: Compare actual vs proportional UCI points
4. **Feature Analysis**: Review feature importance across years
5. **Error Analysis**: Examine worst predictions for insights

## Important Notes

- Only riders with sufficient pre-test history are included in test sets
- Experience features use the training cutoff date for realistic evaluation
- Models are trained separately for GC and Stage/One-day races
- Results are automatically saved for later analysis
- Early stopping prevents overfitting during training