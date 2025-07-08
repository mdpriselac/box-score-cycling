# Rider Performance Data Access Instructions

## Overview

This document provides complete instructions for accessing and understanding the cycling race database structure, specifically for building rider performance prediction models. The database contains race features, race kind classifications, and all necessary data for predicting rider performance using UCI points as the target variable.

## Database Location

**Database Path:** `database/database/cycling_races.db` (SQLite)
**Database Type:** SQLite

## Key Tables and Structure

### 1. Competition and Race Information

#### Main Race Tables
- **Purpose:** Basic information about races and competitions
- **Key Columns:**
  - `competition_id`: Unique identifier for each competition
  - `competition_name`: Name of the competition (e.g., "Stage: 01", "GC")
  - `competition_type`: Type of competition (`gc`, `stage`, `one_day`)
  - `race_id`: Identifier for the overall race event
  - `race_name`: Name of the race (e.g., "Tour de France", "Milano-Sanremo")
  - `race_category`: Race category (`wt`, `pro`, `d1`)
  - `race_year`: Year of the race
  - `race_date`: Date of the competition

### 2. Race Features Tables

#### Table Naming Convention
- `race_features_N` where N is the percentile (30, 40, 50, 60, 70, 80, 90, 100)
- Example: `race_features_70` contains features calculated using top 70th percentile finishers

#### Key Race Feature Columns
**Statistical Measures:**
- `variance_normalized`, `variance_absolute`: Time variance measures
- `std_deviation_normalized`, `std_deviation_absolute`: Standard deviation measures
- `skewness_absolute`, `skewness_normalized`: Distribution skewness
- `kurtosis_absolute`, `kurtosis_normalized`: Distribution kurtosis
- `gini_coefficient`: Inequality measure
- `shannon_entropy_normalized`, `shannon_entropy_absolute`: Information measures

**Engineered Metrics:**
- `biggest_group_metric`: Largest finishing group characteristics
- `time_gap_evenness_metric`: Distribution of time gaps
- `clumpiness_score`: How grouped/spread finishers are
- `selection_metric`: Race selectivity measure
- `proportion_in_groups`: Proportion of riders finishing in groups
- `avg_group_size`: Average size of finishing groups

**Percentile Gap Measures:**
- `10th_percentile_gap`, `25th_percentile_gap`, `50th_percentile_gap`: Time gaps at different percentiles

**Administrative Columns:**
- `included_finishers`: Number of finishers included in calculations
- All competition/race metadata columns (same as above)

### 3. Race Kind Features Table

#### Table: `race_kind_features_unified`

**Purpose:** Contains clustering-based race classification features for all competitions.

**Key Columns:**
- `competition_id`: Links to competition tables
- `cluster_label`: Assigned cluster (0, 1, 2)
- `local_density`: How typical the race is within its cluster
- `boundary_distance`: Distance to nearest different cluster

**Cluster Membership (One-hot encoded):**
- `cluster_0`, `cluster_1`, `cluster_2`: Binary indicators (1 if race belongs to cluster, 0 otherwise)

**Distance Features:**
- `distance_to_cluster_0`, `distance_to_cluster_1`, `distance_to_cluster_2`: Euclidean distances to each cluster center

**Important Notes:**
- **All models currently produce 3 clusters** (0, 1, 2)
- **GC races:** Use hierarchical clustering with 70th percentile data
- **Stage and One-day races:** Use hierarchical clustering with 40th percentile data
- **Table structure dynamically determined** from actual models used

### 4. Rider and Results Tables

#### Rider Results Table
- **Purpose:** Individual rider performance in each competition
- **Key Columns:**
  - `competition_id`: Links to competitions
  - `rider_id`: Unique rider identifier
  - Place and time information
  - UCI points earned (target variable for prediction)

## Model Information and Feature Selection

### Race Kind Models Used

**Note:** The specific models and features shown below are examples. Always refer to the latest configuration JSON in `race_kind_feature_guide/` for current model information.

#### Current General Pattern (as of latest configuration)

**GC Competitions:**
- **Algorithm:** Hierarchical clustering
- **Source Data:** Higher percentile data (e.g., 70th percentile)
- **Training Data:** WT and Pro races
- **Features:** Typically include variance, group size, and time distribution metrics

**Stage and One-Day Competitions:**
- **Algorithm:** Hierarchical clustering  
- **Source Data:** Lower percentile data (e.g., 40th percentile)
- **Training Data:** WT and Pro races
- **Features:** Typically include clumpiness, group metrics, and selection measures

**Dynamic Properties:**
- **Cluster count:** Automatically determined from models (currently 3 clusters)
- **Feature sets:** Vary based on feature selection and model optimization
- **Table structure:** Adapts to accommodate the maximum clusters across all models

### Finding Model Features

#### Method 1: Latest Configuration JSON (RECOMMENDED)
The most current model information is always available in the latest configuration JSON file in `database/race_kinds/race_kind_feature_guide/`. These files are automatically generated when new race kind feature tables are created with updated models.

**Finding the Latest Configuration:**
```python
import os
import json
from pathlib import Path

# Find the latest configuration file
config_dir = Path("database/race_kinds/race_kind_feature_guide")
config_files = list(config_dir.glob("config_*.json"))
latest_config = max(config_files, key=os.path.getctime) if config_files else None

if latest_config:
    with open(latest_config) as f:
        config = json.load(f)
    print(f"Using configuration from: {latest_config.name}")
    print(f"Table name: {config['metadata']['table_name']}")
    print(f"Models used: {list(config['metadata']['model_configurations'].keys())}")
else:
    print("No configuration files found in race_kind_feature_guide/")
```

**Configuration File Naming Convention:**
- Format: `config_YYYYMMDD_HHMMSS_description.json`
- Example: `config_20250708_114515_initial.json`
- Files are ordered by creation time, with latest being most current

**Configuration File Contents:**
- **Model configurations**: Exact models used for each competition type
- **Feature columns**: Complete list of features used by each model
- **Table schema**: Full column definitions and data types
- **Usage instructions**: SQL join patterns and feature descriptions
- **Statistics**: Distribution of races across clusters and competition types
- **Sample data**: Example records for validation
- **Timestamp**: When the configuration was generated

#### Method 2: Model Metadata Files
```bash
# Check saved model metadata
ls database/race_kinds/models/*_metadata.json
cat database/race_kinds/models/hierarchical_70th_*_metadata.json
cat database/race_kinds/models/hierarchical_40th_*_metadata.json
```

The `feature_columns` field in the metadata shows exactly which features were used.

#### Method 3: Database Metadata Table
```sql
-- Check race kind features metadata
SELECT * FROM race_kind_features_unified_metadata WHERE key = 'feature_columns';
```

#### Method 4: Python Code Access
```python
from race_kind_models import RaceKindModelManager

manager = RaceKindModelManager(db_path)
models = manager.list_saved_models()

# Find the models
for model in models:
    if model['algorithm'] == 'hierarchical' and model['percentile'] == 70:
        print("GC Model Features:", model['feature_columns'])
    elif model['algorithm'] == 'hierarchical' and model['percentile'] == 40:
        print("Stage/One-day Model Features:", model['feature_columns'])
```

## Data Access Patterns

### Complete Competition Data Query
```sql
-- Get all data for a competition
SELECT 
    -- Basic competition info
    rf.competition_id,
    rf.competition_name,
    rf.competition_type,
    rf.race_name,
    rf.race_category,
    rf.race_year,
    rf.race_date,
    
    -- Race features (example - adjust based on actual features used)
    rf.variance_normalized,
    rf.std_deviation_normalized,
    rf.skewness_absolute,
    rf.kurtosis_absolute,
    rf.gini_coefficient,
    rf.biggest_group_metric,
    rf.time_gap_evenness_metric,
    rf.clumpiness_score,
    
    -- Race kind features
    rkf.cluster_label,
    rkf.local_density,
    rkf.boundary_distance,
    rkf.cluster_0,
    rkf.cluster_1,
    rkf.cluster_2,
    rkf.distance_to_cluster_0,
    rkf.distance_to_cluster_1,
    rkf.distance_to_cluster_2

FROM race_kind_features_unified rkf
-- Join with appropriate race features table based on competition type
LEFT JOIN race_features_70 rf70 ON rkf.competition_id = rf70.competition_id 
    AND rf70.competition_type = 'gc'
LEFT JOIN race_features_40 rf40 ON rkf.competition_id = rf40.competition_id 
    AND rf40.competition_type IN ('stage', 'one_day')

-- Combine the results
SELECT 
    COALESCE(rf70.competition_id, rf40.competition_id) as competition_id,
    COALESCE(rf70.competition_name, rf40.competition_name) as competition_name,
    COALESCE(rf70.competition_type, rf40.competition_type) as competition_type,
    -- ... other fields
FROM (previous query)
WHERE rf70.competition_id IS NOT NULL OR rf40.competition_id IS NOT NULL;
```

### Competition Type-Specific Queries

#### GC Races Only
```sql
SELECT rf.*, rkf.*
FROM race_features_70 rf
JOIN race_kind_features_unified rkf ON rf.competition_id = rkf.competition_id
WHERE rf.competition_type = 'gc';
```

#### Stage Races Only
```sql
SELECT rf.*, rkf.*
FROM race_features_40 rf
JOIN race_kind_features_unified rkf ON rf.competition_id = rkf.competition_id
WHERE rf.competition_type = 'stage';
```

#### One-Day Races Only
```sql
SELECT rf.*, rkf.*
FROM race_features_40 rf
JOIN race_kind_features_unified rkf ON rf.competition_id = rkf.competition_id
WHERE rf.competition_type = 'one_day';
```

## Prediction Model Architecture Recommendations

### Target Variable
- **Primary Target:** UCI points earned by riders
- **Alternative Target:** Proportional UCI points (see `database/uci_points.py`)

### Feature Categories for Rider Models

#### 1. Rider Historical Features
- Career UCI earnings
- Total races by level
- Normalized races by level (proportions)
- Age
- Recent performance history (3 months, 6 months, 1 year, 2 years)

#### 2. Race Characteristics (from race features tables)
- Use the specific features that were selected for the clustering models
- Different features for GC vs Stage/One-day races

#### 3. Race Kind Features (from race_kind_features_unified)
- Cluster membership (categorical or one-hot)
- Distances to cluster centers
- Local density and boundary distance

#### 4. Future Enhancements
- Strength of field metrics
- Field composition by rider specialties
- Weather and course data (if available)

## Important Considerations

### Data Consistency
- **Competition type routing:** Each competition type uses its designated model and source table
- **Percentile tables:** Models automatically determine source tables based on their training percentile
- **Training data:** Models are typically trained on WT and Pro races
- **Evaluation:** Models are typically evaluated on WT, Pro, and D1 races
- **Cluster count:** Determined dynamically from the models in use (check latest configuration)

### Missing Data Handling
- Race features with NULL values are filled with 0 during model application
- Some races may have missing race features due to insufficient finishers
- **Table structure automatically adapts** to the number of clusters in the models used

### Model Performance
- Check clustering evaluation reports in `database/race_kinds/reports/` for model quality metrics
- Both models use hierarchical clustering with robust feature scaling
- Feature selection was performed using WT and Pro races

## File Locations

### Code Files
- **Model management:** `database/race_kinds/race_kind_models.py`
- **Race analysis:** `database/race_kinds/race_kind_analysis.py`
- **Feature selection:** `database/race_kinds/feature_selection.py`
- **Main analysis:** `database/race_kinds/find_race_kinds.py`

### Model Files
- **Saved models:** `database/race_kinds/models/`
- **Model metadata:** `database/race_kinds/models/*_metadata.json`
- **Evaluation reports:** `database/race_kinds/reports/`

### Database Schema
- **Schema documentation:** `db_migration_update_1.md`

## Creating Race Kind Features for New Models

### Generalized Race Kind Features Creation

The `create_race_kind_features.py` script allows you to create race kind features using any combination of models for different competition types. **Always export the configuration to the guide folder** for rider performance model integration:

```bash
# Create race kind features with updated models
python database/race_kinds/create_race_kind_features.py \
  --one-day-model "database/race_kinds/models/your_one_day_model.pkl" \
  --stage-model "database/race_kinds/models/your_stage_model.pkl" \
  --gc-model "database/race_kinds/models/your_gc_model.pkl" \
  --output-table "race_kind_features_unified" \
  --export-path "database/race_kinds/race_kind_feature_guide/config_$(date +%Y%m%d_%H%M%S).json"
```

**Workflow for Model Updates:**
1. **Train new models** using improved algorithms or features
2. **Save models** using `RaceKindModelManager`
3. **Create new race kind features** with the script above
4. **Export configuration** to `race_kind_feature_guide/` folder
5. **Update production table** (typically `race_kind_features_unified`)
6. **Rider performance models** automatically use the latest configuration

**Key Features:**
- **Flexible model assignment**: Use any saved model for any competition type
- **Dynamic cluster detection**: Automatically determines cluster count from models
- **Unified table creation**: Combines all competition types in one table
- **Complete documentation**: Exports JSON with all configuration details
- **Version tracking**: Timestamped configurations track model evolution
- **Validation**: Shows sample results and statistics

**Requirements:**
- Models must be saved using `RaceKindModelManager`
- Models automatically determine source tables based on percentile
- All models must be compatible with the feature calculation pipeline
- **Always export configuration** to guide folder for integration

## Next Steps for Rider Performance Models

### Initial Setup
1. **Load Latest Configuration**: Use the code above to find and load the latest configuration JSON from `race_kind_feature_guide/`
2. **Review Configuration**: Examine the configuration to understand:
   - Current models used for each competition type
   - Feature columns and table schema
   - Join patterns and usage instructions
   - Cluster distributions and statistics
3. **Setup Data Pipeline**: Configure your data access using the table name and schema from the configuration

### Development Workflow
4. **Data Exploration:** Query the database to understand rider result distributions and UCI point patterns
5. **Feature Engineering:** Create rider historical features and performance profiles using the current configuration
6. **Model Development:** Build prediction models using the complete feature set
7. **Validation:** Test models across different race categories and time periods
8. **Deployment:** Create pipeline for real-time predictions on new races

### Staying Current with Model Updates
- **Monitor configuration folder**: Check `race_kind_feature_guide/` for new configuration files
- **Automatic updates**: Design your pipeline to automatically use the latest configuration
- **Version tracking**: Keep track of which configuration version your models were trained on
- **Regression testing**: Test your rider performance models when race kind models are updated

### Configuration-Driven Development
Your rider performance models should be **configuration-driven**, reading table names, feature columns, and join patterns from the latest JSON configuration rather than hardcoding them. This ensures compatibility as the race kind models evolve.

## Contact Information

For questions about the race kind classification system or database structure, refer to the documentation in the `database/race_kinds/` directory or examine the code files listed above.