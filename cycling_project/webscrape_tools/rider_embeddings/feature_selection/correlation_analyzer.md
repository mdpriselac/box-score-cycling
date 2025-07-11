# CorrelationQualityAnalyzer

Class for analyzing the quality of correlation data across different race_features_N percentiles.

## Class: CorrelationQualityAnalyzer

### Constructor
```python
CorrelationQualityAnalyzer()
```
No parameters required.

### Main Methods

#### analyze_percentile_quality
```python
analyze_percentile_quality(correlation_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]
```
Analyze correlation quality across different percentiles.

**Arguments:**
- `correlation_results`: List of results from CorrelationCalculator

**Returns:**
Dictionary mapping percentile names to quality metrics:
- `mean_abs_correlation`: Average absolute correlation strength
- `correlation_variance`: Variance in correlation values (higher = more discriminative)
- `non_null_rate`: Percentage of valid correlations
- `dynamic_range`: Spread of correlation values
- `signal_strength`: Combined metric of strength and consistency
- `feature_coverage`: Proportion of features with multiple rider correlations

#### analyze_feature_quality
```python
analyze_feature_quality(correlation_results: List[Dict[str, Any]], percentile: str) -> Dict[str, Dict[str, float]]
```
Analyze quality metrics for individual features within a percentile.

**Arguments:**
- `correlation_results`: List of correlation results
- `percentile`: Specific percentile to analyze (e.g., 'race_features_100')

**Returns:**
Dictionary mapping feature names to metrics:
- `mean_abs_correlation`: Average absolute correlation for this feature
- `correlation_std`: Standard deviation of correlations
- `sample_size`: Number of riders with valid correlations
- `dynamic_range`: Range of correlation values
- `discriminative_power`: Combined metric for distinguishing riders

#### rank_percentiles
```python
rank_percentiles(quality_metrics: Dict[str, Dict[str, float]], weights: Dict[str, float] = None) -> List[Tuple[str, float]]
```
Rank percentiles by overall quality score.

**Arguments:**
- `quality_metrics`: Output from analyze_percentile_quality
- `weights`: Optional weights for different metrics

**Returns:**
List of (percentile_name, score) tuples sorted by score (descending)

#### rank_features
```python
rank_features(feature_metrics: Dict[str, Dict[str, float]], weights: Dict[str, float] = None) -> List[Tuple[str, float]]
```
Rank features by overall quality score within a percentile.

#### generate_summary_report
```python
generate_summary_report(correlation_results: List[Dict[str, Any]]) -> Dict[str, Any]
```
Generate a comprehensive summary report including:
- Percentile quality analysis and rankings
- Feature analysis for top 3 percentiles
- Recommendations for best percentiles and features