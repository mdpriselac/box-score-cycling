# create_race_kind_features.py

Generalized script to create race kind features using configurable models for different competition types.

## Main Functions

### `create_race_kind_features(one_day_model_path: str, stage_model_path: str, gc_model_path: str, output_table: str = "race_kind_features_unified", export_path: Optional[str] = None)`

Create race kind features for different competition types using specified models.

**Parameters:**
- `one_day_model_path`: Path to model for one-day races
- `stage_model_path`: Path to model for stage races  
- `gc_model_path`: Path to model for GC races
- `output_table`: Name of the output table (default: "race_kind_features_unified")
- `export_path`: Optional path to export key table information JSON

**Note:** The maximum number of clusters is automatically determined from the models.

**Returns:** None

**Raises:** `FileNotFoundError` if model files don't exist

### `get_source_table_for_model(model_path: str, model_manager: RaceKindModelManager) -> str`

Determine the appropriate source table based on model's percentile.

**Parameters:**
- `model_path`: Path to the model file
- `model_manager`: RaceKindModelManager instance

**Returns:** Source table name (e.g., 'race_features_70')

### `export_key_table_info(table_name: str, export_path: str, model_configs: Dict, max_clusters: int)`

Export key table information for the rider performance system.

**Parameters:**
- `table_name`: Name of the race kind features table
- `export_path`: Path to export the information
- `model_configs`: Dictionary of model configurations
- `max_clusters`: Maximum number of clusters determined from models

**Returns:** None

### `show_sample_results(table_name: str)`

Show sample results from the created table.

**Parameters:**
- `table_name`: Name of the table to sample from

**Returns:** None

### `main()`

Main function with command line interface.

**Returns:** None

## Command Line Usage

```bash
python create_race_kind_features.py \
    --one-day-model /path/to/one_day_model.pkl \
    --stage-model /path/to/stage_model.pkl \
    --gc-model /path/to/gc_model.pkl \
    --output-table race_kind_features_unified \
    --export-path /path/to/export_info.json
```

## Required Arguments

- `--one-day-model`: Path to model for one-day races
- `--stage-model`: Path to model for stage races
- `--gc-model`: Path to model for GC races

## Optional Arguments

- `--output-table`: Name of the output table (default: race_kind_features_unified)
- `--export-path`: Path to export key table information JSON file (default: auto-generated as `race_kind_feature_guide/config_YYYYMMDD_HHMMSS.json`)

**Note:** The number of clusters is automatically determined from the loaded models.

## Export Format

The script exports a JSON file containing:

- `metadata`: Table name, database path, timestamp, model configurations
- `schema`: Column information and primary key
- `usage_instructions`: SQL join patterns, key features descriptions, competition type models
- `statistics`: Statistics by competition type and cluster
- `sample_data`: Sample records from the table

## Dependencies

- `race_kind_models.RaceKindModelManager`
- `pandas`
- `sqlite3`
- `json`
- `argparse`
- `os`
- `sys`