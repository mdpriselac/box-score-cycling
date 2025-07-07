# Integrated Race Analysis

This module demonstrates the complete workflow from feature selection to race kind identification.

## Script: integrated_race_analysis.py

### Functions

#### analyze_with_feature_selection
```python
analyze_with_feature_selection(table_name: str, competition_type: str = None, race_category: str = None, max_features: int = 12, db_path: str = DB_PATH)
```
Run complete analysis with automatic feature selection.
- `table_name`: Race features table name (e.g., 'race_features_70')
- `competition_type`: Filter by type ('gc', 'stage', 'one_day')
- `race_category`: Filter by category ('wt', 'pro', 'd1')
- `max_features`: Maximum number of features to select
- `db_path`: Path to database

**Workflow:**
1. **Feature Selection**: Analyzes all available features and selects optimal subset
2. **Race Kind Analysis**: Uses selected features for clustering and scoring
3. **Method Comparison**: Tests multiple clustering approaches
4. **Detailed Analysis**: Provides cluster characteristics and examples
5. **Report Generation**: Creates feature selection reports and visualizations

#### compare_feature_sets
```python
compare_feature_sets(table_name: str, competition_type: str = None, db_path: str = DB_PATH)
```
Compare analysis results using default features vs automatically selected features.
- Shows quantitative improvement from feature selection
- Demonstrates the value of systematic feature selection

## Usage Examples

### Basic Integrated Analysis
```bash
python database/race_kinds/integrated_race_analysis.py
```

### Programmatic Usage
```python
from integrated_race_analysis import analyze_with_feature_selection

# Analyze World Tour stage races at 70th percentile
results = analyze_with_feature_selection(
    'race_features_70',
    competition_type='stage',
    race_category='wt',
    max_features=10
)

print(f"Selected features: {results['selected_features']}")
print(f"Best method: {results['best_method']}")
```

### Feature Selection Integration
```python
from feature_selection import FeatureSelector
from race_kind_analysis import RaceKindAnalyzer

# Step 1: Select optimal features
selector = FeatureSelector(db_path)
selector.load_data('race_features_70', competition_type='stage')
selected_features = selector.select_features(max_features=12)

# Step 2: Use selected features for analysis
analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
analyzer.load_data('race_features_70', competition_type='stage')
analyzer.prepare_features()
results = analyzer.kmeans_clustering()
```

## Workflow Steps

### 1. Feature Selection Analysis
- **Correlation removal**: Eliminates highly correlated features (>0.9)
- **Variance filtering**: Removes low-variance features
- **Distribution analysis**: Assesses normality, skewness, and zero ratios
- **Clustering power**: Tests individual feature discriminative ability
- **Random Forest importance**: Evaluates feature contribution in ensemble
- **Redundancy analysis**: Groups similar features using hierarchical clustering

### 2. Feature Scoring and Selection
Features are scored using weighted combination of:
- **Clustering power** (30%): How well feature separates data
- **RF importance** (30%): Contribution in ensemble model
- **Distribution quality** (20%): Normality and uniqueness
- **Uniqueness** (20%): Low correlation with other features

### 3. Race Kind Analysis
- **K-means clustering**: Tests 2-7 clusters with silhouette scoring
- **Hierarchical clustering**: Alternative clustering approach
- **Feature-based scoring**: Domain-specific race type identification
- **Cluster characterization**: Top distinguishing features and examples

### 4. Results and Reporting
- **Performance comparison**: Selected vs default features
- **Cluster analysis**: Detailed characteristics of each race kind
- **Feature importance**: Which features drive the clustering
- **Example races**: Concrete examples of each race type

## Expected Outputs

### Console Output
```
🔍 STEP 1: FEATURE SELECTION
----------------------------------------
Loaded 145 races from race_features_70
Available features: 27

Selected 10 optimal features:
   1. selection_metric
   2. biggest_group_metric
   3. gini_coefficient
   4. clumpiness_score
   5. proportion_in_groups
   ...

🏁 STEP 2: RACE KIND ANALYSIS
----------------------------------------
Testing K-means clustering...
  Best k=4, silhouette=0.312
Testing hierarchical clustering...
  Best k=4, silhouette=0.298

📊 STEP 3: DETAILED ANALYSIS OF BEST METHOD
--------------------------------------------------
Best clustering method: kmeans
Silhouette score: 0.312

Cluster Analysis (4 clusters):
  🏆 Cluster 0 (45 races, 31.0%)
    Top distinguishing features:
      ↑ biggest_group_metric: 0.823 (avg: 0.456)
      ↓ selection_metric: 0.124 (avg: 0.398)
    Main type: stage (40 races)
    Example races:
      - Tour de France - Stage: 03
      - Giro d'Italia - Stage: 21
```

### Generated Files
- **Feature selection report** (.md): Detailed analysis of feature selection process
- **Correlation heatmap** (.png): Visualization of selected feature relationships
- **Feature scores plot** (.png): Ranking of all features by selection criteria

## Integration Benefits

1. **Data-Driven**: Uses statistical analysis rather than manual feature selection
2. **Customizable**: Adjustable thresholds and scoring weights
3. **Transparent**: Detailed reporting of selection criteria and results
4. **Comparable**: Quantifies improvement from feature selection
5. **Scalable**: Works across different percentiles and race types

## Best Practices

1. **Start with feature selection** before race kind analysis
2. **Adjust max_features** based on data size (typically 8-15 features)
3. **Compare results** with default features to validate improvement
4. **Consider race context** when interpreting clusters
5. **Generate reports** for documentation and reproducibility