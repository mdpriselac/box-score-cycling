# CorrelationDataLoader

Load correlation data from parquet files for feature selection analysis.

## Class: CorrelationDataLoader

### Constructor
```python
CorrelationDataLoader(data_dir: str = "correlation_data")
```
- `data_dir`: Directory containing parquet files

Automatically detects whether to use partitioned or batch file format.

### Main Loading Methods

#### load_for_feature_selection
```python
load_for_feature_selection(
    percentiles: Optional[List[str]] = None,
    rider_result_ids: Optional[List[int]] = None,
    min_races: int = 5,
    sample_size: Optional[int] = None
) -> List[Dict[str, Any]]
```
Load correlation data in format expected by feature selection pipeline.

**Arguments:**
- `percentiles`: Specific percentiles to load (None = all)
- `rider_result_ids`: Specific rider results to load (None = all)
- `min_races`: Minimum number of races required
- `sample_size`: Optional random sample size

**Returns:** List of correlation results matching CorrelationCalculator output format

#### load_for_specific_analysis
```python
load_for_specific_analysis(
    percentile: str,
    features: Optional[List[str]] = None,
    min_correlation_strength: Optional[float] = None
) -> pd.DataFrame
```
Load data for specific analysis needs with filtering.

**Returns:** DataFrame with filtered correlation data

### Utility Methods

#### get_available_percentiles
```python
get_available_percentiles() -> List[str]
```
Get list of available percentiles in the dataset.

#### get_data_summary
```python
get_data_summary() -> Dict[str, Any]
```
Get summary statistics about available data including:
- Generation metadata
- Available percentiles
- Data statistics (unique riders, correlation counts, etc.)
- Storage format

#### export_for_external_analysis
```python
export_for_external_analysis(
    output_file: str,
    format: str = 'csv',
    percentiles: Optional[List[str]] = None
)
```
Export correlation data for analysis in external tools.

**Supported formats:** 'csv', 'parquet', 'json'

### Usage Example
```python
# Initialize loader
loader = CorrelationDataLoader("correlation_data")

# Load data for feature selection
correlation_results = loader.load_for_feature_selection(
    percentiles=['race_features_80', 'race_features_100'],
    min_races=10,
    sample_size=1000
)

# Pass to feature selection pipeline
from rider_embeddings.feature_selection import FeatureSelectionPipeline
pipeline = FeatureSelectionPipeline()
results = pipeline.analyze_all(correlation_results)

# Export for external analysis
loader.export_for_external_analysis(
    "correlations_export.csv",
    format='csv',
    percentiles=['race_features_100']
)
```