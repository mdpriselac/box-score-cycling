# model_reporter.py

Generate comprehensive reports for embedding-based prediction models.

## Classes

### ModelReporter

Handles report generation and formatting for model training results.

#### Methods

##### `__init__(output_dir: str = "reports")`
Initialize the model reporter.

**Parameters:**
- `output_dir` (str): Directory to save reports

##### `generate_training_report(model, train_stats: Dict, test_stats: Dict, test_year: int, save_file: bool = True) -> Dict`
Generate comprehensive training report for a model.

**Parameters:**
- `model`: Trained EmbeddingPerformanceModel
- `train_stats` (Dict): Statistics from training data
- `test_stats` (Dict): Statistics from test data
- `test_year` (int): Year used for testing
- `save_file` (bool): Whether to save report to file

**Returns:**
- `Dict`: Full report with metadata, dataset info, performance metrics, and feature importance

##### `generate_multi_race_type_report(results: Dict[str, Dict], test_year: int, save_file: bool = True) -> Dict`
Generate report comparing multiple race type models.

**Parameters:**
- `results` (Dict[str, Dict]): Dictionary mapping race_type to training results
- `test_year` (int): Year used for testing
- `save_file` (bool): Whether to save report to file

**Returns:**
- `Dict`: Consolidated report with all race types

##### `print_training_summary(model, train_stats: Dict, test_stats: Dict)`
Print a formatted training summary to console.

**Parameters:**
- `model`: Trained EmbeddingPerformanceModel
- `train_stats` (Dict): Statistics from training data
- `test_stats` (Dict): Statistics from test data

##### `export_feature_importance_csv(model, filename: Optional[str] = None)`
Export feature importance to CSV files.

**Parameters:**
- `model`: Trained EmbeddingPerformanceModel
- `filename` (Optional[str]): Base filename for CSV exports

##### `compare_models_table(models: Dict[str, any], test_data: Dict[str, pd.DataFrame])`
Generate comparison table for multiple models.

**Parameters:**
- `models` (Dict[str, any]): Dictionary mapping race_type to trained models
- `test_data` (Dict[str, pd.DataFrame]): Dictionary mapping race_type to test dataframes

## Report Structure

### Training Report
```json
{
  "metadata": {
    "race_type": "gc",
    "test_year": 2023,
    "report_date": "2024-01-15T10:30:00"
  },
  "dataset_info": {
    "training": {
      "n_rider_results": 50000,
      "n_competitions": 500,
      "years": [2015, 2016, ..., 2022],
      "target_stats": {...}
    },
    "test": {...}
  },
  "model_performance": {
    "rmse_overall": 0.123,
    "auc_classification": 0.89,
    ...
  },
  "feature_importance": {
    "classifier": {
      "top_embedding_features": [...],
      "top_database_features": [...],
      "all_features": [...]
    },
    "regressor": {...}
  }
}
```

## Usage Example

```python
from model_reporter import ModelReporter
from embedding_model import EmbeddingPerformanceModel
from data_preparation import EmbeddingDataPreparation

# Initialize reporter
reporter = ModelReporter(output_dir="reports")

# After training a model
train_stats = prep.get_dataset_stats(train_df)
test_stats = prep.get_dataset_stats(test_df)

# Generate report
report = reporter.generate_training_report(
    model=model,
    train_stats=train_stats,
    test_stats=test_stats,
    test_year=2023
)

# Print summary
reporter.print_training_summary(model, train_stats, test_stats)

# Export feature importance
reporter.export_feature_importance_csv(model)
```