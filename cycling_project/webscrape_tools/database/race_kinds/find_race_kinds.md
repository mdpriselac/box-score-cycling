# Find Race Kinds - Main Script

This is the main entry point for finding and analyzing race kinds in the cycling database.

## Command Line Usage

### Quick Demo
Run a quick demonstration of race kind analysis:
```bash
python database/race_kinds/find_race_kinds.py --mode quick
```

### Single Percentile Analysis
Analyze a specific percentile table with a chosen method:
```bash
python database/race_kinds/find_race_kinds.py --mode single --percentile 70 --method kmeans
```

With automatic feature selection:
```bash
python database/race_kinds/find_race_kinds.py --mode single --percentile 70 --method kmeans --use-feature-selection --max-features 10
```

### Full Evaluation
Run comprehensive evaluation across all percentiles and methods:
```bash
python database/race_kinds/find_race_kinds.py --mode evaluate --output-dir reports
```

## Command Line Arguments

- `--mode`: Analysis mode
  - `quick`: Quick demo showing different methods
  - `single`: Analyze a single percentile table
  - `evaluate`: Full evaluation across all tables

- `--percentile`: Percentile table to analyze (30, 40, 50, 60, 70, 80, 90, 100)
  - Only used in 'single' mode
  - Default: 70

- `--method`: Clustering method to use
  - Options: kmeans, hierarchical, dbscan, gaussian_mixture, feature_based
  - Only used in 'single' mode
  - Default: kmeans

- `--competition-type`: Filter by competition type
  - Options: gc, stage, one_day, stage_one_day
  - `stage_one_day` analyzes both stage and one-day races together
  - Optional filter for all modes

- `--db-path`: Path to SQLite database
  - Default: uses project database path

- `--output-dir`: Directory for output reports
  - Only used in 'evaluate' mode
  - Default: database/race_kinds/reports

- `--use-feature-selection`: Use automatic feature selection
  - Only used in 'single' mode
  - Runs feature analysis before race kind analysis

- `--max-features`: Maximum features to select
  - Only used with --use-feature-selection
  - Default: 12

- `--feature-selection-categories`: Race categories for feature selection
  - Options: wt, pro, d1 (can specify multiple: wt pro)
  - Only used with --use-feature-selection
  - Used to train feature selection on broader or cleaner datasets

- `--analysis-categories`: Race categories for race kind analysis
  - Options: wt, pro, d1 (can specify multiple: wt pro)
  - Controls which races are used for the actual clustering/scoring
  - Can be different from feature selection categories

## Functions

### analyze_single_percentile
```python
analyze_single_percentile(percentile: int, competition_type: str = None, method: str = 'kmeans', use_feature_selection: bool = False, max_features: int = 12, feature_selection_categories: list = None, analysis_categories: list = None, db_path: str = DB_PATH)
```
Analyze race kinds for a single percentile table using specified method.
- `use_feature_selection`: Whether to run automatic feature selection first
- `max_features`: Maximum number of features to select
- `feature_selection_categories`: Race categories for feature selection training
- `analysis_categories`: Race categories for race kind analysis

### evaluate_all_methods
```python
evaluate_all_methods(competition_type: str = None, analysis_categories: list = None, db_path: str = DB_PATH, output_dir: str = 'database/race_kinds/reports')
```
Run comprehensive evaluation of all methods across all percentiles and generate report.
- `analysis_categories`: Race categories for evaluation

### quick_analysis
```python
quick_analysis(db_path: str = DB_PATH)
```
Run a quick demonstration showing different analysis methods.

## Example Outputs

### K-means Clustering Output
```
Best number of clusters: 4
Silhouette score: 0.312

Cluster Characteristics:

  Cluster 0 (45 races, 32.1%):
    Top features:
      - biggest_group_metric: 0.823
      - selection_metric: 0.124
      - proportion_in_groups: 0.756
    Competition types: {'stage': 40, 'one_day': 5}
    Example races:
      - Tour de France - Stage: 01
      - Giro d'Italia - Stage: 21
      - Milano-Sanremo - Milano-Sanremo
```

### Feature-based Scoring Output
```
Race Type Distribution:
  sprint: 67 races (47.9%)
  selective: 42 races (30.0%)
  balanced: 21 races (15.0%)
  attritional: 10 races (7.1%)

Example races by type:

  SPRINT:
    - Tour de France - Stage: 03
    - Vuelta a España - Stage: 04
    - Scheldeprijs - Scheldeprijs
```

## Workflow Examples

### 1. Initial Exploration
```bash
# Quick demo to see what's possible
python database/race_kinds/find_race_kinds.py --mode quick

# Analyze just stage races at 70th percentile
python database/race_kinds/find_race_kinds.py --mode single --percentile 70 --competition-type stage
```

### 2. Method Comparison
```bash
# Compare different methods on same data
python database/race_kinds/find_race_kinds.py --mode single --percentile 50 --method kmeans
python database/race_kinds/find_race_kinds.py --mode single --percentile 50 --method hierarchical
python database/race_kinds/find_race_kinds.py --mode single --percentile 50 --method feature_based
```

### 3. Full Analysis
```bash
# Run complete evaluation and generate reports
python database/race_kinds/find_race_kinds.py --mode evaluate --competition-type stage_one_day

# Analyze GC races separately
python database/race_kinds/find_race_kinds.py --mode evaluate --competition-type gc
```

## Integration with Other Tools

The results from this script can be:
1. Used to add race kind labels back to the database
2. Incorporated into prediction models as features
3. Used for race selection in analytics
4. Exported for visualization in other tools