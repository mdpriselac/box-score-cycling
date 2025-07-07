# Race Kinds Analysis System

This directory contains a comprehensive system for identifying and analyzing different kinds of cycling races based on their statistical characteristics.

## Overview

The race kinds analysis system provides multiple approaches to categorize races with advanced feature selection and evaluation capabilities:
- **Clustering methods**: K-means, hierarchical, DBSCAN, Gaussian mixture models
- **Feature-based scoring**: Domain-specific race type identification  
- **Systematic feature selection**: Automated optimal feature selection
- **Cross-category evaluation**: Training/evaluation on different race categories
- **Cross-percentile analysis**: Understanding how race characteristics change with field depth

## Components

### 1. Feature Selection (`feature_selection.py`)
Systematic feature selection module that analyzes all available features and selects the optimal subset for race kind analysis.

**Key capabilities:**
- **Correlation analysis**: Removes highly correlated features
- **Variance filtering**: Eliminates low-variance features
- **Distribution analysis**: Normality, skewness, kurtosis assessment
- **Clustering power**: Tests how well features separate races
- **Random Forest importance**: Machine learning-based feature importance
- **Redundancy analysis**: Hierarchical clustering to remove redundant features
- **Race category filtering**: Select features using specific tour levels

### 2. Race Kind Analysis (`race_kind_analysis.py`) 
Core module for analyzing races at a single percentile level with multiple clustering algorithms.

**Clustering methods:**
- **K-means**: Fast, effective for spherical clusters
- **Hierarchical**: Reveals cluster relationships, good interpretability
- **DBSCAN**: Density-based, finds irregular clusters and outliers
- **Gaussian Mixture**: Probabilistic clustering with soft assignments
- **Feature-based**: Domain-knowledge scoring systems

**Additional features:**
- **PCA analysis**: Dimensionality reduction and visualization
- **Cluster stability**: Cross-validation stability testing
- **Model persistence**: Saves trained models for evaluation

### 3. Race Kind Evaluation (`race_kind_evaluation.py`)
Framework for evaluating and comparing different methods across percentile tables.

**Key features:**
- **Comprehensive method comparison**: All methods on same data
- **Performance metrics**: Silhouette scores, stability, cluster quality
- **Cross-percentile stability**: How consistent are race classifications
- **Detailed report generation**: Markdown reports with recommendations
- **Visualization support**: Performance plots and comparisons

### 4. Find Race Kinds (`find_race_kinds.py`) - **Main Entry Point**
Comprehensive command-line interface providing three analysis modes with full feature control.

**Analysis modes:**
- **`quick`**: Demo of different analysis methods
- **`single`**: Analyze specific percentile with chosen method
- **`evaluate`**: Compare all methods on single or multiple percentiles

**Advanced features:**
- **Feature selection integration**: `--use-feature-selection` with `--max-features`
- **Race category control**: Separate categories for feature selection, training, and evaluation
- **Cross-category evaluation**: Train on clean data (WT/Pro), evaluate on broader data (WT/Pro/D1)
- **Comprehensive reporting**: Detailed markdown reports with performance comparisons

### 5. Feature Exploration (`feature_exploration.py`)
Systematic exploration of feature selection across different scenarios.

**Key features:**
- **Multi-scenario analysis**: Different percentiles, competition types, race categories
- **Feature frequency analysis**: Most commonly selected features
- **Detailed reporting**: Feature selection patterns and removal reasons
- **Combined category support**: Analyze WT+Pro together instead of separately

### 6. Cross-Percentile Analysis (`cross_percentile_analysis.py`)
Analyzes race patterns across different percentile levels.

**Key features:**
- **Feature stability analysis**: Which features are stable across percentiles  
- **Race trajectory tracking**: How individual races change across percentiles
- **Percentile-invariant identification**: Find races with consistent characteristics

### 7. Test Script (`test_race_kinds.py`)
Basic functionality tests for all components.

## Quick Start

### 1. Basic Analysis
```bash
# Quick demo of all methods
python database/race_kinds/find_race_kinds.py --mode quick

# Single percentile analysis with default features
python database/race_kinds/find_race_kinds.py --mode single --percentile 70 --competition-type stage_one_day --method kmeans
```

### 2. Advanced Analysis with Feature Selection
```bash
# Automatic feature selection on WT+Pro data, analyze WT+Pro races
python database/race_kinds/find_race_kinds.py --mode single --percentile 50 \
  --competition-type stage_one_day \
  --use-feature-selection --max-features 20 \
  --feature-selection-categories wt pro \
  --analysis-categories wt pro

# Cross-category evaluation: train on WT+Pro, evaluate on WT+Pro+D1  
python database/race_kinds/find_race_kinds.py --mode single --percentile 50 \
  --competition-type stage_one_day \
  --use-feature-selection --max-features 20 \
  --feature-selection-categories wt pro \
  --analysis-categories wt pro \
  --eval-categories wt pro d1
```

### 3. Comprehensive Method Evaluation
```bash
# Evaluate all methods on single percentile
python database/race_kinds/find_race_kinds.py --mode evaluate --percentile 50 \
  --competition-type stage_one_day \
  --use-feature-selection --max-features 20 \
  --feature-selection-categories wt pro \
  --analysis-categories wt pro \
  --eval-categories wt pro d1

# Evaluate all methods across ALL percentiles (30-100)
python database/race_kinds/find_race_kinds.py --mode evaluate \
  --competition-type stage_one_day \
  --use-feature-selection --max-features 20 \
  --feature-selection-categories wt pro \
  --analysis-categories wt pro \
  --eval-categories wt pro d1
```

### 4. Feature Exploration
```bash
# Explore feature selection across percentiles
python database/race_kinds/feature_exploration.py \
  --percentiles 50 70 90 \
  --competition-types stage_one_day \
  --race-categories wt pro
```

## Command Line Arguments

### Core Arguments
- `--mode {quick,single,evaluate}`: Analysis mode
- `--percentile {30,40,50,60,70,80,90,100}`: Percentile table (single mode default: 70, evaluate mode default: all)
- `--competition-type {gc,stage,one_day,stage_one_day}`: Race types to analyze
- `--method {kmeans,hierarchical,dbscan,gaussian_mixture,feature_based}`: Clustering method (single mode only)

### Feature Selection Arguments  
- `--use-feature-selection`: Enable automatic feature selection
- `--max-features N`: Maximum features to select (default: 20)
- `--feature-selection-categories {wt,pro,d1}`: Categories for feature selection training

### Race Category Arguments
- `--analysis-categories {wt,pro,d1}`: Categories for model training
- `--eval-categories {wt,pro,d1}`: Categories for evaluation (enables cross-category analysis)

### Output Arguments
- `--output-dir PATH`: Directory for reports (default: database/race_kinds/reports)

## Race Categories and Competition Types

### Race Categories (Tour Levels)
- **`wt`**: World Tour (highest level, cleanest data)
- **`pro`**: Pro Series (professional level)  
- **`d1`**: Division 1 (can be noisier data)

### Competition Types
- **`gc`**: General Classification (overall tour results)
- **`stage`**: Individual stages from multi-day races
- **`one_day`**: Single-day races (classics, etc.)
- **`stage_one_day`**: Combined stages and one-day races (most common analysis)

## Cross-Category Evaluation Workflow

A powerful feature allows training on clean data and evaluating on broader datasets:

1. **Feature Selection**: Train on high-quality data (e.g., WT+Pro races)
2. **Model Training**: Train clustering on same high-quality data  
3. **Evaluation**: Test how well the model generalizes to broader data (e.g., WT+Pro+D1)

This helps identify whether patterns found in elite races generalize to lower-level racing.

## Output Files

### Single Percentile Evaluation
```
database/race_kinds/reports/
└── method_comparison_50th_percentile_YYYYMMDD_HHMMSS.md
```

### Multi-Percentile Evaluation  
```
database/race_kinds/reports/
├── method_comparison_30th_percentile_YYYYMMDD_HHMMSS.md
├── method_comparison_40th_percentile_YYYYMMDD_HHMMSS.md
├── method_comparison_50th_percentile_YYYYMMDD_HHMMSS.md
├── ... (one per percentile)
├── method_comparison_100th_percentile_YYYYMMDD_HHMMSS.md
└── cross_percentile_summary_YYYYMMDD_HHMMSS.md  ← Master summary
```

### Feature Exploration
```
database/race_kinds/reports/
├── feature_exploration_YYYYMMDD_HHMMSS.md
└── feature_comparison_YYYYMMDD_HHMMSS.csv
```

## Report Contents

### Method Comparison Reports
- **Performance Summary Table**: Silhouette scores, cluster counts, evaluation metrics
- **Detailed Method Results**: Cluster characteristics, distributions, parameters
- **Evaluation Performance**: Training vs evaluation score comparisons
- **Selected Features**: List of features chosen by automatic selection
- **Recommendations**: Best performing methods and generalization analysis

### Cross-Percentile Summary
- **Method Performance Across Percentiles**: Mean scores, best/worst percentiles
- **Consistency Analysis**: Which methods are most stable
- **Links to Individual Reports**: Easy navigation to detailed results

## Key Findings from System Development

### Optimal Feature Selection
The system consistently selects these core features:
1. **Group formation features**: `biggest_group_metric`, `clumpiness_score`, `avg_group_size`
2. **Selection metrics**: `selection_metric`, `gini_coefficient`
3. **Time gap features**: `50th_percentile_gap`, `variance_absolute`
4. **Race dynamics**: `time_gap_evenness_metric`, `std_deviation_normalized`

### Method Performance Insights
- **K-means**: Most consistent, good generalization across categories
- **Hierarchical**: Often highest silhouette scores, reveals race relationships
- **Gaussian Mixture**: Good probabilistic clustering, handles overlapping groups
- **DBSCAN**: Effective at finding outlier races, variable performance
- **Feature-based**: Most interpretable but requires complete feature set

### Cross-Category Evaluation Results  
Training on WT/Pro and evaluating on WT/Pro/D1 typically shows:
- **Small score differences** (+/- 0.05) indicate good generalization
- **Large negative differences** suggest overfitting to elite racing patterns
- **Large positive differences** suggest the model benefits from more diverse data

## Python Usage Example

```python
from race_kind_analysis import RaceKindAnalyzer
from feature_selection import FeatureSelector

# Advanced workflow with feature selection
selector = FeatureSelector(db_path)
selector.load_data('race_features_70', competition_type='stage_one_day', race_category='wt')
selected_features = selector.select_features(max_features=15)

# Analysis with selected features
analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
data = analyzer.load_data('race_features_70', competition_type='stage_one_day', race_category='wt')
analyzer.prepare_features()
results = analyzer.kmeans_clustering(range(2, 8))

# Cross-category evaluation
eval_analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
eval_data = analyzer.load_data('race_features_70', competition_type='stage_one_day', race_category='pro')
eval_analyzer.prepare_features()
trained_model = results['cluster_results'][results['best_n_clusters']]['model']
eval_labels = trained_model.predict(eval_analyzer.scaled_features)
```

## Dependencies

- pandas >= 1.3.0
- numpy >= 1.21.0  
- scikit-learn >= 1.0.0
- scipy >= 1.7.0
- matplotlib >= 3.4.0
- seaborn >= 0.11.0

All dependencies should be available through `uv` in the project environment.

## Next Steps

1. **Apply Classifications**: Add race kind labels back to the main database
2. **Prediction Integration**: Use race kinds as features in rider/team performance models
3. **Time Series Analysis**: Track how race kinds evolve over years and rule changes
4. **Domain Validation**: Work with cycling experts to validate and refine categories
5. **Real-time Classification**: Apply models to classify new races as they're added