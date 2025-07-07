# Cross-Percentile Race Kind Analysis Module

This module analyzes race kinds across different percentile levels to find stable patterns and understand how race characteristics change with field depth.

## Class: CrossPercentileAnalyzer

### Constructor
```python
CrossPercentileAnalyzer(db_path: str)
```
- `db_path`: Path to the SQLite database containing race features

### Methods

#### find_common_competitions
```python
find_common_competitions(min_percentile_coverage: float = 0.8, competition_type: Optional[str] = None) -> Set[int]
```
Find competitions that appear across multiple percentile tables.
- `min_percentile_coverage`: Minimum fraction of tables a competition must appear in (0.8 = 80%)
- `competition_type`: Filter by type ('gc', 'stage', 'one_day', 'stage_one_day')
- Returns: Set of competition IDs meeting the coverage requirement

#### extract_feature_trajectories
```python
extract_feature_trajectories(features: List[str] = None, competition_ids: Set[int] = None) -> pd.DataFrame
```
Extract how features change across percentiles for each competition.
- `features`: List of features to track (default: key features)
- `competition_ids`: Set of competition IDs to analyze (default: common competitions)
- Returns: DataFrame with feature values at each percentile level

#### analyze_feature_stability
```python
analyze_feature_stability() -> Dict[str, Dict[str, float]]
```
Analyze how stable each feature is across percentiles.
- Returns: Dictionary with stability metrics for each feature:
  - `mean_cv`: Mean coefficient of variation
  - `std_cv`: Standard deviation of CV
  - `median_cv`: Median CV
  - `stability_score`: Overall stability (0-1, higher is more stable)

#### find_percentile_invariant_kinds
```python
find_percentile_invariant_kinds(n_clusters: int = 4, stability_threshold: float = 0.7) -> Dict[str, Any]
```
Find race kinds that remain consistent across percentiles.
- `n_clusters`: Number of clusters to find
- `stability_threshold`: Minimum stability score for features to use
- Returns: Dictionary with:
  - `stable_features`: Features used for clustering
  - `invariant_competitions`: Races with consistent classification
  - `clusters_by_percentile`: Cluster assignments at each level

#### analyze_percentile_effects
```python
analyze_percentile_effects(features: List[str] = None) -> pd.DataFrame
```
Analyze how race characteristics change with percentile depth.
- `features`: Features to analyze (default: all numeric features)
- Returns: DataFrame with:
  - Correlation with percentile
  - Trend direction (increasing/decreasing/stable)
  - Values at key percentiles (30th, 70th, 100th)
  - Relative change from 30th to 100th percentile

#### create_race_kind_trajectories
```python
create_race_kind_trajectories(method: str = 'kmeans', n_kinds: int = 4) -> Dict[str, Any]
```
Track how races move between kinds as percentile changes.
- `method`: Clustering method to use
- `n_kinds`: Number of race kinds
- Returns: Dictionary with:
  - `trajectories`: Race assignments at each percentile
  - `transitions`: List of kind transitions
  - `transition_matrix`: Probability matrix of transitions
  - `n_stable_races`: Count of races that don't change kinds
  - `n_transitioning_races`: Count of races that change kinds

#### generate_cross_percentile_report
```python
generate_cross_percentile_report(output_path: str = 'database/race_kinds/reports/cross_percentile_analysis.md') -> str
```
Generate a comprehensive cross-percentile analysis report.
- `output_path`: Path for the output report
- Returns: Path to the generated report

## Example Usage

```python
# Initialize analyzer
analyzer = CrossPercentileAnalyzer(db_path)

# Find competitions present in at least 80% of percentile tables
common_comps = analyzer.find_common_competitions(min_percentile_coverage=0.8)
print(f"Found {len(common_comps)} common competitions")

# Extract feature trajectories
trajectories = analyzer.extract_feature_trajectories()

# Analyze feature stability
stability = analyzer.analyze_feature_stability()
print("Most stable features:")
for feature, metrics in sorted(stability.items(), key=lambda x: x[1]['stability_score'], reverse=True)[:3]:
    print(f"  {feature}: {metrics['stability_score']:.3f}")

# Find invariant race kinds
invariant_kinds = analyzer.find_percentile_invariant_kinds(n_clusters=4)
print(f"Found {len(invariant_kinds['invariant_competitions'])} invariant races")

# Analyze percentile effects
effects = analyzer.analyze_percentile_effects()
print("\nFeatures that change with percentile:")
for _, row in effects[effects['trend'] != 'stable'].iterrows():
    print(f"  {row['feature']}: {row['trend']} (r={row['correlation_with_percentile']:.3f})")

# Track race trajectories
trajectories = analyzer.create_race_kind_trajectories()
print(f"\nStable races: {trajectories['n_stable_races']}")
print(f"Transitioning races: {trajectories['n_transitioning_races']}")

# Generate full report
report_path = analyzer.generate_cross_percentile_report()
```

## Key Concepts

### Feature Stability
Features are considered stable if they maintain consistent values for the same race across different percentile cutoffs. Stability is measured using coefficient of variation (CV).

### Percentile-Invariant Kinds
These are race groupings that remain consistent regardless of how much of the field is included in the analysis. These represent fundamental race types.

### Feature Trajectories
How race characteristics change as we include more riders (deeper percentiles). Some features may increase (e.g., time gaps) while others decrease (e.g., group cohesion).

### Race Transitions
Some races may change classification as percentile changes. For example, a race might look like a sprint at the 30th percentile but reveal selective characteristics when analyzing the full field.

## Report Sections

The generated report includes:

1. **Feature Stability Analysis**
   - Ranking of features by cross-percentile stability
   - Identification of most reliable features

2. **Percentile Effects**
   - Features that increase/decrease with field depth
   - Magnitude of changes

3. **Invariant Race Kinds**
   - Races that maintain consistent classification
   - Examples of each invariant kind

4. **Race Trajectories**
   - Transition patterns between kinds
   - Stability statistics

5. **Key Findings**
   - Most stable features for classification
   - Overall patterns in race characteristics
   - Recommendations for analysis