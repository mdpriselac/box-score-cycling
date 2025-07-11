# FeatureSelectionPipeline

Integrated pipeline for comprehensive feature selection analysis combining correlation quality, clustering quality, and redundancy analysis.

## Class: FeatureSelectionPipeline

### Constructor
```python
FeatureSelectionPipeline(
    correlation_threshold: float = 0.8,
    random_state: int = 42
)
```
- `correlation_threshold`: Threshold for redundancy analysis
- `random_state`: Random state for clustering analysis

### Main Methods

#### analyze_all
```python
analyze_all(
    correlation_results: List[Dict[str, Any]],
    percentiles: List[str] = None,
    k_range: List[int] = None,
    max_features: int = None
) -> Dict[str, Any]
```
Run complete feature selection analysis pipeline.

**Arguments:**
- `correlation_results`: List of correlation results from CorrelationCalculator
- `percentiles`: List of percentiles to analyze (if None, analyzes all available)
- `k_range`: Range of k values for clustering analysis
- `max_features`: Maximum number of features to recommend

**Returns:**
Comprehensive analysis results including:
- `analysis_metadata`: Timestamp, data info, and analysis parameters
- `correlation_quality_analysis`: Percentile quality metrics and rankings
- `clustering_analysis`: Clustering quality comparison across percentiles
- `feature_analysis`: Feature quality analysis for top percentiles
- `redundancy_analysis`: Feature redundancy and selection recommendations
- `recommendations`: Integrated recommendations for percentiles and features

#### save_results
```python
save_results(
    results: Dict[str, Any], 
    output_path: str,
    include_raw_data: bool = False
) -> None
```
Save analysis results to JSON file.

**Arguments:**
- `results`: Output from analyze_all
- `output_path`: Path to save results
- `include_raw_data`: Whether to include detailed raw analysis data

#### generate_report
```python
generate_report(results: Dict[str, Any]) -> str
```
Generate a human-readable report from analysis results.

**Returns:** Formatted text report with key findings and recommendations

### Analysis Components

The pipeline integrates three main analysis components:

1. **Correlation Quality Analysis**
   - Evaluates signal strength, variance, and coverage across percentiles
   - Ranks percentiles by correlation informativeness

2. **Clustering Analysis**
   - Tests clustering separability for different percentiles
   - Uses silhouette score, Calinski-Harabasz, and Davies-Bouldin metrics
   - Includes PCA analysis for dimensionality assessment

3. **Redundancy Analysis**
   - Identifies highly correlated features within percentiles
   - Groups redundant features using connected components
   - Provides feature selection recommendations based on quality scores

### Recommendations Structure

The pipeline generates:
- **Percentile Recommendations**: Best percentiles based on different criteria
- **Feature Recommendations**: Optimal feature sets for top percentiles
- **Summary**: Final recommendations with justification

### Usage Pattern
```python
pipeline = FeatureSelectionPipeline(correlation_threshold=0.8)
results = pipeline.analyze_all(correlation_results, max_features=20)
report = pipeline.generate_report(results)
pipeline.save_results(results, "feature_selection_results.json")
```