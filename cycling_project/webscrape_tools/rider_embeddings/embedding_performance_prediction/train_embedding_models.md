# train_embedding_models.py

CLI script for training embedding-based performance prediction models with year-based train/test splitting.

## Usage

### Basic Usage
```bash
# Train all race type models for 2023
python train_embedding_models.py --year 2023

# Train only GC model for 2023
python train_embedding_models.py --year 2023 --race-type gc

# Train and save models
python train_embedding_models.py --year 2023 --save-models
```

### Advanced Usage
```bash
# Custom paths and directories
python train_embedding_models.py \
    --year 2023 \
    --db-path /path/to/database.db \
    --embedding-path /path/to/embeddings \
    --model-dir /path/to/save/models \
    --report-dir /path/to/save/reports \
    --save-models
```

## Command Line Arguments

- `--year` (required): Year to use for testing (trains on all years before this)
- `--race-type`: Specific race type to train ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
- `--db-path`: Path to cycling database (default: "database/database/cycling_races.db")
- `--embedding-path`: Path to embedding data folder (default: "race_type_optimized_data")
- `--save-models`: Save trained models to disk
- `--model-dir`: Directory to save models (default: "models")
- `--report-dir`: Directory to save reports (default: "reports")

## Functions

### `train_single_race_type(race_type: str, test_year: int, prep: EmbeddingDataPreparation, reporter: ModelReporter, save_model: bool = False, model_dir: str = "models") -> Dict`
Train model for a single race type.

**Parameters:**
- `race_type` (str): Race type to train
- `test_year` (int): Year to use for testing
- `prep` (EmbeddingDataPreparation): Data preparation instance
- `reporter` (ModelReporter): Model reporter instance
- `save_model` (bool): Whether to save the trained model
- `model_dir` (str): Directory to save models

**Returns:**
- `Dict`: Training results with status, performance metrics, and dataset info

## Output Structure

### Reports
Generated in the report directory:
- `{race_type}_model_report_{year}.json`: Individual model reports
- `all_models_report_{year}.json`: Consolidated report (if training multiple)
- `{race_type}_feature_importance_*.csv`: Feature importance files

### Models
If `--save-models` is used:
- `{race_type}_model_{year}_classifier.txt`: LightGBM classifier
- `{race_type}_model_{year}_regressor.txt`: LightGBM regressor
- `{race_type}_model_{year}_metadata.json`: Model metadata

## Example Output

```
Training models for year 2023
Race types: gc, stage, one_day, stage_one_day, all
Database: database/database/cycling_races.db
Embeddings: race_type_optimized_data

============================================================
Training GC Model
============================================================

Preparing data for gc...
Loaded 15000 embeddings for gc
Train set: 12000 samples (years < 2023)
Test set: 3000 samples (year = 2023)

Training gc model...
Training samples: 12000
Validation samples: 3000
Training zero rate: 85.2%
Number of features: 45
  - Embedding features: 20
  - Database features: 25

Stage 1: Training classifier...
[100]    valid_0's binary_logloss: 0.2543

Stage 2: Training regressor on non-zero samples...
Non-zero training samples: 1776
Non-zero validation samples: 444

Training complete!
Overall RMSE: 0.1234
Non-zero RMSE: 0.3456
Classification AUC: 0.8901

Report saved to: reports/gc_model_report_2023.json
✅ Model saved to: models/gc_model_2023

[... continues for other race types ...]

============================================================
TRAINING SUMMARY
============================================================

Total models: 5
✅ Successful: 5
❌ Failed: 0
⚠️  Skipped: 0

Reports saved to: reports/
Models saved to: models/

✨ Training complete!
```

## Error Handling

The script handles:
- Missing database or embedding files
- Insufficient training/test data (skips models with <100 train or <10 test samples)
- Invalid year inputs
- Training failures (reports errors and continues with other models)