# Feature Selection Module

This module provides systematic feature selection for race kind analysis by analyzing features across multiple dimensions and selecting the most informative subset.

## Class: FeatureSelector

### Constructor
```python
FeatureSelector(db_path: str)
```
- `db_path`: Path to the SQLite database containing race features

### Methods

#### get_all_feature_columns
```python
get_all_feature_columns(table_name: str) -> List[str]
```
Extract all numeric feature columns from a race features table.
- `table_name`: Name of the race features table
- Returns: List of all numeric feature column names

#### load_data
```python
load_data(table_name: str, competition_type: Optional[str] = None, race_category: Optional[str] = None, min_finishers: int = 30) -> pd.DataFrame
```
Load race data for feature analysis.
- `table_name`: Name of the race features table
- `competition_type`: Filter by type ('gc', 'stage', 'one_day', 'stage_one_day')
- `race_category`: Filter by category ('wt', 'pro', 'd1')
- `min_finishers`: Minimum number of finishers required
- Returns: DataFrame with race features

#### analyze_correlations
```python
analyze_correlations(threshold: float = 0.95) -> Tuple[pd.DataFrame, Set[str]]
```
Analyze feature correlations and identify highly correlated pairs.
- `threshold`: Correlation threshold for removal (default: 0.95)
- Returns: (correlation matrix, set of features to remove)

#### analyze_variance
```python
analyze_variance(threshold: float = 0.01) -> Tuple[pd.Series, Set[str]]
```
Analyze feature variance and identify low-variance features.
- `threshold`: Normalized variance threshold (default: 0.01)
- Returns: (variance series, set of low-variance features to remove)

#### analyze_distributions
```python
analyze_distributions() -> pd.DataFrame
```
Analyze feature distributions for normality, skewness, and kurtosis.
- Returns: DataFrame with distribution statistics for each feature

#### analyze_clustering_power
```python
analyze_clustering_power(n_clusters: int = 4, n_iterations: int = 10) -> pd.Series
```
Analyze how well each feature contributes to clustering.
- `n_clusters`: Number of clusters to test
- `n_iterations`: Number of iterations for stability
- Returns: Series with clustering power scores (0-1)

#### analyze_feature_importance
```python
analyze_feature_importance(target_clusters: Optional[np.ndarray] = None) -> pd.Series
```
Analyze feature importance using Random Forest.
- `target_clusters`: Target cluster labels (auto-generated if None)
- Returns: Series with feature importance scores

#### analyze_redundancy
```python
analyze_redundancy() -> Tuple[Dict[str, List[str]], Set[str]]
```
Analyze feature redundancy using hierarchical clustering.
- Returns: (feature clusters dictionary, set of redundant features to remove)

#### select_features
```python
select_features(correlation_threshold: float = 0.95, variance_threshold: float = 0.01, min_clustering_power: float = 0.1, min_rf_importance: float = 0.01, max_features: Optional[int] = None, custom_weights: Optional[Dict[str, float]] = None) -> List[str]
```
Select optimal features based on multiple criteria.
- `correlation_threshold`: Maximum correlation allowed between features
- `variance_threshold`: Minimum variance required
- `min_clustering_power`: Minimum clustering power score
- `min_rf_importance`: Minimum Random Forest importance
- `max_features`: Maximum number of features to select (None = auto)
- `custom_weights`: Custom weights for scoring components
- Returns: List of selected feature names

Default weights:
- clustering_power: 0.3
- rf_importance: 0.3
- distribution_quality: 0.2
- uniqueness: 0.2

#### generate_feature_report
```python
generate_feature_report(output_path: str = 'database/race_kinds/reports/feature_selection_report.md') -> str
```
Generate a comprehensive feature selection report.
- `output_path`: Path for the output report
- Returns: Path to the generated report

#### visualize_features
```python
visualize_features(output_dir: str = 'database/race_kinds/reports')
```
Create visualizations of feature analysis.
- `output_dir`: Directory for output plots
- Generates: correlation heatmap and feature score plots

## Example Usage

```python
from feature_selection import FeatureSelector

# Initialize selector
selector = FeatureSelector(db_path)

# Load data from 70th percentile table for stage races
data = selector.load_data(
    'race_features_70',
    competition_type='stage',
    race_category='wt'
)

# Select optimal features
selected_features = selector.select_features(
    correlation_threshold=0.9,
    variance_threshold=0.01,
    min_clustering_power=0.15,
    max_features=15
)

print(f"Selected {len(selected_features)} features:")
for feature in selected_features:
    print(f"  - {feature}")

# Generate report
report_path = selector.generate_feature_report()

# Create visualizations
selector.visualize_features()
```

## Feature Analysis Criteria

1. **Correlation Analysis**
   - Removes features with correlation > threshold
   - Keeps feature with higher variance from correlated pairs

2. **Variance Analysis**
   - Removes features with very low variance
   - Uses standardized variance for fair comparison

3. **Distribution Analysis**
   - Tests for normality (Shapiro-Wilk/normal test)
   - Calculates skewness and kurtosis
   - Tracks zero ratios and unique values

4. **Clustering Power**
   - Tests how well individual features separate data
   - Normalized against full feature set performance

5. **Random Forest Importance**
   - Uses ensemble method to assess feature contribution
   - Robust to feature interactions

6. **Redundancy Analysis**
   - Hierarchical clustering to find feature groups
   - Keeps most informative feature from each group

## Output Files

- **feature_selection_report.md**: Detailed analysis report
- **selected_features_correlation.png**: Correlation heatmap
- **feature_selection_scores.png**: Feature score visualization

## Integration with Race Kind Analysis

The selected features can be directly used in `RaceKindAnalyzer`:

```python
# Get optimal features
selector = FeatureSelector(db_path)
selector.load_data('race_features_70', competition_type='stage')
selected_features = selector.select_features()

# Use in race kind analysis
from race_kind_analysis import RaceKindAnalyzer
analyzer = RaceKindAnalyzer(db_path)
analyzer.feature_columns = selected_features  # Override default features
analyzer.load_data('race_features_70', competition_type='stage')
analyzer.prepare_features()
results = analyzer.kmeans_clustering()
```