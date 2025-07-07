# Race Kind Evaluation Module

This module provides a comprehensive framework for evaluating different race kind identification methods across multiple percentile tables.

## Class: RaceKindEvaluator

### Constructor
```python
RaceKindEvaluator(db_path: str)
```
- `db_path`: Path to the SQLite database containing race features

### Methods

#### get_available_percentile_tables
```python
get_available_percentile_tables() -> List[str]
```
Get list of available race_features tables in the database.
- Returns: List of table names (e.g., ['race_features_30', 'race_features_40', ...])

#### evaluate_single_percentile
```python
evaluate_single_percentile(table_name: str, competition_type: Optional[str] = None, methods: List[str] = None, verbose: bool = True) -> Dict[str, Any]
```
Evaluate all methods on a single percentile table.
- `table_name`: Name of the percentile table (e.g., 'race_features_70')
- `competition_type`: Filter by competition type ('gc', 'stage', 'one_day')
- `methods`: List of methods to evaluate (default: all available)
- `verbose`: Print progress messages
- Returns: Dictionary with evaluation results for each method

Available methods:
- 'kmeans': K-means clustering
- 'hierarchical': Hierarchical clustering
- 'dbscan': Density-based clustering
- 'gaussian_mixture': Gaussian Mixture Models
- 'pca': Principal Component Analysis
- 'feature_based': Custom feature-based scoring

#### evaluate_all_percentiles
```python
evaluate_all_percentiles(competition_type: Optional[str] = None, methods: List[str] = None, tables: List[str] = None) -> Dict[str, Any]
```
Evaluate methods across all percentile tables.
- `competition_type`: Filter by competition type
- `methods`: List of methods to evaluate
- `tables`: List of tables to evaluate (None for all)
- Returns: Dictionary with all evaluation results

#### compare_method_performance
```python
compare_method_performance() -> pd.DataFrame
```
Create a comparison table of method performance across percentiles.
- Returns: DataFrame with performance metrics including:
  - Silhouette scores
  - Stability metrics
  - Optimal cluster numbers
  - Method-specific metrics

#### evaluate_cross_percentile_stability
```python
evaluate_cross_percentile_stability(method: str = 'kmeans') -> Dict[str, Any]
```
Evaluate how stable race groupings are across different percentiles.
- `method`: Clustering method to use for stability analysis
- Returns: Dictionary with consistency scores and statistics

#### generate_report
```python
generate_report(output_dir: str = 'database/race_kinds/reports', include_plots: bool = True) -> str
```
Generate a comprehensive evaluation report with:
- Performance summaries for each method
- Detailed results by percentile
- Cross-percentile stability analysis
- Recommendations
- Visualization plots (optional)

Outputs:
- Markdown report (.md)
- Detailed JSON results (.json)
- Comparison CSV table (.csv)
- Visualization plots (.png)

Returns: Path to the main report file

## Example Usage

```python
# Initialize evaluator
evaluator = RaceKindEvaluator(db_path)

# Evaluate all percentiles for stage and one-day races
results = evaluator.evaluate_all_percentiles(
    competition_type='stage_one_day',
    methods=['kmeans', 'hierarchical', 'feature_based']
)

# Compare method performance
comparison_df = evaluator.compare_method_performance()

# Check cross-percentile stability
stability = evaluator.evaluate_cross_percentile_stability(method='kmeans')

# Generate comprehensive report
report_path = evaluator.generate_report(
    output_dir='database/race_kinds/reports',
    include_plots=True
)
```

## Report Contents

The generated report includes:

1. **Summary Statistics**
   - Number of percentile tables evaluated
   - Methods tested
   - Total evaluations performed

2. **Method Performance Summary**
   - Mean silhouette scores
   - Stability metrics
   - Typical cluster numbers

3. **Detailed Results by Percentile**
   - Best performing method for each percentile
   - Cluster characteristics and examples
   - Top distinguishing features

4. **Cross-Percentile Stability**
   - How consistent race groupings are across percentiles
   - Mean and standard deviation of consistency scores

5. **Recommendations**
   - Best overall clustering method
   - Most stable method
   - Optimal percentile for analysis
   - Suggestions for combining approaches

## Evaluation Metrics

- **Silhouette Score**: Measures how similar a race is to its own cluster vs other clusters (-1 to 1, higher is better)
- **Calinski-Harabasz Score**: Ratio of between-cluster to within-cluster variance (higher is better)
- **Davies-Bouldin Score**: Average similarity between each cluster and its most similar cluster (lower is better)
- **Stability Score**: Consistency of clustering when using different data subsamples (0 to 1, higher is better)
- **AIC/BIC**: Information criteria for Gaussian Mixture Models (lower is better)