# Race Type Pipeline Adapter

Module for running race type correlation results through the existing feature selection pipeline and generating comprehensive meta-reports.

## Classes

### RaceTypeCorrelationAdapter

Main adapter class for processing race type correlation results through the existing pipeline.

#### Constructor

```python
RaceTypeCorrelationAdapter()
```

Creates a new adapter instance with an internal FeatureSelectionPipeline.

#### Methods

##### extract_race_type_data

```python
extract_race_type_data(
    race_type_results: List[Dict[str, Any]], 
    race_type: str
) -> List[Dict[str, Any]]
```

Extracts data for a specific race type and reformats it to match the original pipeline structure.

**Parameters:**
- `race_type_results`: Results from RaceTypeCorrelationCalculator
- `race_type`: Race type to extract ('gc', 'stage', 'one_day', 'stage_one_day', 'all')

**Returns:**
List of correlation results formatted for the original pipeline

##### run_pipeline_for_race_type

```python
run_pipeline_for_race_type(
    race_type_results: List[Dict[str, Any]],
    race_type: str,
    max_features: int = 25,
    k_range: List[int] = None
) -> Dict[str, Any]
```

Runs the feature selection pipeline for a specific race type.

**Parameters:**
- `race_type_results`: Results from RaceTypeCorrelationCalculator
- `race_type`: Race type to analyze
- `max_features`: Maximum features to recommend (default: 25)
- `k_range`: Range of k values for clustering analysis

**Returns:**
Feature selection results for the specified race type

##### run_all_race_types

```python
run_all_race_types(
    race_type_results: List[Dict[str, Any]],
    race_types: List[str] = None,
    max_features: int = 25,
    k_range: List[int] = None
) -> Dict[str, Dict[str, Any]]
```

Runs the pipeline for all specified race types.

**Parameters:**
- `race_type_results`: Results from RaceTypeCorrelationCalculator
- `race_types`: List of race types to analyze (default: all)
- `max_features`: Maximum features per race type
- `k_range`: Range of k values for clustering

**Returns:**
Dictionary mapping race_type to analysis results

##### generate_meta_report

```python
generate_meta_report(
    all_results: Dict[str, Dict[str, Any]],
    output_dir: str = "race_type_analysis"
) -> str
```

Generates a comprehensive meta-report combining all race type results.

**Parameters:**
- `all_results`: Dictionary of race_type → analysis results
- `output_dir`: Directory to save reports and results

**Returns:**
Path to the meta-report file

**Outputs:**
- Individual race type analysis results (JSON)
- Individual race type reports (TXT)
- Meta-analysis report (TXT)
- Meta-analysis summary (JSON)

### RaceTypeDataGenerator

Extended data generator that handles race type correlation results with proper flattening for parquet storage.

#### Constructor

```python
RaceTypeDataGenerator(
    db_path: str,
    output_dir: str = "race_type_correlation_data",
    batch_size: int = 100,
    min_races_all: int = 35,
    min_races_stage: int = 25,
    min_races_one_day: int = 15,
    min_races_gc: int = 10
)
```

**Parameters:**
- `db_path`: Path to the cycling database
- `output_dir`: Directory for output files
- `batch_size`: Number of riders per batch
- `min_races_all`: Minimum races for all-race correlations
- `min_races_stage`: Minimum races for stage correlations
- `min_races_one_day`: Minimum races for one-day correlations
- `min_races_gc`: Minimum races for GC correlations

## Usage Examples

### Basic Usage - Analyze All Race Types

```python
from rider_embeddings.race_type_pipeline_adapter import RaceTypeCorrelationAdapter
from rider_embeddings.performance_feature_link import RaceTypeCorrelationCalculator

# Generate race type correlations
calculator = RaceTypeCorrelationCalculator("database/cycling_races.db")

# Get correlations for multiple riders
rider_results = [12345, 12346, 12347]  # rider_result_ids
feature_tables = ['race_features_70', 'race_features_80', 'race_features_90']

race_type_results = []
for rr_id in rider_results:
    result = calculator.calculate_feature_relationships(
        rr_id, 
        "2023-06-01",  # lookback date
        feature_tables
    )
    race_type_results.append(result)

# Run through adapter
adapter = RaceTypeCorrelationAdapter()
all_results = adapter.run_all_race_types(
    race_type_results,
    max_features=25
)

# Generate meta-report
report_path = adapter.generate_meta_report(all_results)
```

### Advanced Usage - Custom Race Type Selection

```python
# Analyze only specific race types
selected_types = ['gc', 'one_day']
results = adapter.run_all_race_types(
    race_type_results,
    race_types=selected_types,
    max_features=30,
    k_range=[3, 4, 5, 6]
)

# Process individual race type
gc_results = adapter.run_pipeline_for_race_type(
    race_type_results,
    'gc',
    max_features=20
)
```

### Data Generation with Race Types

```python
from rider_embeddings.race_type_pipeline_adapter import RaceTypeDataGenerator

# Generate correlation data with race types
generator = RaceTypeDataGenerator(
    db_path="database/cycling_races.db",
    output_dir="race_type_data",
    min_races_gc=8,  # Lower threshold for GC
    min_races_all=40  # Higher threshold for all races
)

# Generate sample
generator.generate_sample(
    sample_size=500,
    feature_tables=['race_features_70', 'race_features_80']
)
```

## Meta-Report Structure

The meta-report includes:

1. **Summary Table**: Overview of recommendations for each race type
   - Best percentile
   - Number of features
   - Optimal clusters
   - Silhouette score
   - Number of riders

2. **Feature Comparisons**:
   - Total unique features across all race types
   - Features common to all race types
   - Race type specific features

3. **Clustering Quality Comparison**:
   - Ranked by silhouette score
   - Cluster sizes and quality interpretation

4. **Feature Overlap Analysis**:
   - Pairwise overlap between race types
   - Common feature identification

## Output Files

```
race_type_analysis/
├── gc_analysis_results.json          # Detailed GC analysis
├── gc_analysis_report.txt            # Human-readable GC report
├── stage_analysis_results.json       # Detailed stage analysis
├── stage_analysis_report.txt         # Human-readable stage report
├── one_day_analysis_results.json     # Detailed one-day analysis
├── one_day_analysis_report.txt       # Human-readable one-day report
├── stage_one_day_analysis_results.json
├── stage_one_day_analysis_report.txt
├── all_analysis_results.json
├── all_analysis_report.txt
├── meta_analysis_report.txt          # Comprehensive comparison
└── meta_analysis_summary.json        # Structured summary data
```

## Key Benefits

1. **Reuses Existing Pipeline**: No need to modify the core feature selection logic
2. **Comprehensive Analysis**: Analyzes each race type independently
3. **Comparative Insights**: Meta-report highlights differences between race types
4. **Flexible**: Can analyze any subset of race types
5. **Production Ready**: Handles errors gracefully and provides detailed logging