# Feature Optimization System

This package provides comprehensive analysis of cycling race features through two aligned components:

1. **Race Feature N Analysis** - Analyzes race features across different percentile thresholds (N levels)
2. **Correlation Feature Analysis** - Analyzes rider performance correlations with race features

## System Overview

### Race Feature N Analysis
Analyzes how race features behave as the field size changes by examining features at different percentile cutoffs (top 30%, 40%, 50%, etc.). This helps identify which features are robust indicators regardless of field strength.

### Correlation Feature Analysis  
Analyzes correlations between individual rider performance and race features across percentiles and race types. Uses pre-computed correlation matrices stored in blob format for efficient processing. **Now aligned with Race Feature N Analysis approach** for consistent pattern detection, quality scoring, and reporting.

## Quick Start

### Race Feature N Analysis
```bash
# Analyze all race types
uv run python run_race_type_analysis.py

# Analyze specific race types
uv run python run_race_type_analysis.py --race-types gc stage

# Analyze single race type
uv run python run_race_type_analysis.py --race-types gc
```

### Correlation Feature Analysis
```bash
# Analyze all correlation types
uv run python run_correlation_analysis.py

# Analyze specific correlation types
uv run python run_correlation_analysis.py --correlation-types same_type stage_one_days

# Analyze with competition type filters
uv run python run_correlation_analysis.py --correlation-types same_type --competition-types gc stage

# Analyze single correlation type
uv run python run_correlation_analysis.py --correlation-types same_type
```

## Available Analysis Types

### Race Types
- `gc`: General Classification races (998 races)
- `stage`: Stage races (5,903 races)  
- `one_day`: One-day races (1,249 races)
- `stage_one_day`: Combined stage + one-day (7,152 races)
- `all_types`: All race types (no filter - race feature analysis only)

### Correlation Types (for correlation analysis)
- `same_type`: Correlations using races of same type (GC with GC, stage with stage, etc.)
- `stage_one_days`: Combined stage + one-day races (excludes GC races)
- `all_races`: All race types combined

### Competition Type Filters (optional)
- `gc`: General Classification races
- `stage`: Stage races  
- `one_day`: One-day races

## Output Structure

### Race Feature N Analysis
- Individual JSON results for each race type
- Markdown summary reports 
- Comparison report across race types
- Feature behavior categorization and quality rankings

### Correlation Feature Analysis
- Individual JSON results for each correlation type
- Markdown summary reports following race feature N format
- Comparison report across correlation types/competition types
- Feature behavior categorization and sophisticated percentile recommendations

## Percentile Analysis

Both systems analyze across percentiles **[30, 40, 50, 60, 70, 80, 90, 100]**, showing:
- How features behave as field strength changes
- Which percentiles provide the most reliable signals
- Stability and trend patterns across the percentile range
- Optimal percentile recommendations per feature

## Components and Architecture

### Race Feature N Analysis (`race_feature_n_analysis/`)
- **Core analyzers**: Variability, monotonicity, distinctiveness, pattern classification
- **Race type filtering**: Analyze by specific race formats
- **Batch processing**: Compare across multiple race types
- **Reporting**: Generate comprehensive analysis reports

### Correlation Feature Analysis (`correlation_feature_analysis/`)
- **CorrelationFeatureAnalyzer**: Main analysis engine aligned with race feature N approach
- **BlobCorrelationDataLoader**: Efficient loading of pre-computed correlation matrices
- **Pattern analysis**: 6 pattern types (Stable, Dilution, Concentration, Threshold, Bimodal, Complex)
- **Quality scoring**: 3-component scoring system (correlation strength, information value, stability)
- **Report generation**: Sophisticated recommendations matching race feature N structure

## Data Sources

### Race Feature Analysis
- Uses `race_features_{percentile}` tables directly from the database
- Real-time calculation of feature statistics and relationships

### Correlation Analysis  
- Uses `rider_correlations_blob` table with pre-computed gzip-compressed correlation matrices
- Each blob contains 8×37 matrix (8 percentiles × 37 features)
- Joins with `rider_results` for competition and rider metadata

## Advanced Usage

### Competition Type Filtering
```bash
# Analyze specific competition types
uv run python run_correlation_analysis.py --correlation-types same_type --competition-types gc

# Compare across multiple competition types
uv run python run_correlation_analysis.py --competition-types gc stage one_day
```

### Output Directory Control
```bash
# Custom output location
uv run python run_correlation_analysis.py --output-dir ./my_analysis_results

# Race feature analysis with custom output
uv run python run_race_type_analysis.py --output-dir ./race_feature_results
```

### Database Path Configuration
```bash
# Custom database path
uv run python run_correlation_analysis.py --db-path /path/to/cycling_races.db
```

## Understanding the Reports

### Quality Tiers (Correlation Analysis)
- **Tier 1**: Highest quality features with strong, stable correlations
- **Tier 2**: Moderate quality features with acceptable reliability  
- **Tier 3**: Lower quality features with limited reliability

### Pattern Classifications (Both Systems)
- **Stable**: Consistent behavior across percentiles (race features) / correlations (correlation analysis)
- **Dilution**: Performance weakens as more riders included (elite-focused patterns)
- **Concentration**: Performance strengthens with broader inclusion (mass-participation patterns)  
- **Threshold**: Sudden changes at specific percentiles
- **Bimodal**: Shows distinct peaks or distribution shifts
- **Complex**: Multiple patterns or irregular behavior

### Key Metrics (Both Systems)
- **Strength Score**: Maximum predictive power or correlation strength
- **Information Value**: Discriminative ability and monotonicity
- **Stability Score**: Consistency across percentiles
- **Overall Quality**: Equal-weighted average of three components
- **Optimal Level**: N-level (race features) or percentile (correlations) with best performance

## Documentation References

### Race Feature N Analysis
- **Feature Categories & Quality Explanations**: `race_feature_n_analysis/race_feature_N_analysis_explanations.md`
- **Race Type Analysis Usage**: `race_feature_n_analysis/race_type_analysis_usage.md`
- **Design Documents**: 
  - `race_feature_n_analysis/race_feature_N_analysis_design.md` - Core analysis design
  - `feature_optimization_design.md` - Overall optimization framework
  - `race_feature_n_analysis/feature_analysis_reporter_design.md` - Reporting system design

### Correlation Feature Analysis
- **Pattern & Quality Explanations**: `correlation_feature_analysis/correlation_feature_analysis_explanations.md`
- **Blob Storage System**: `../database_embeddings_storage/USER_GUIDE.md` - Complete guide to correlation data storage
- **Design Document**: `correlation_feature_analysis/correlation_analysis_design.md` - Analysis methodology
- **Configuration**: `correlation_feature_analysis/config.py` - All analysis parameters and thresholds

## Performance Notes

- **Race Feature Analysis**: Direct database queries, moderate memory usage
- **Correlation Analysis**: Blob-based loading for 13x performance improvement, ~8GB RAM recommended
- **Blob Decompression**: Handles gzip-compressed numpy arrays efficiently
- **Aligned Architecture**: Both systems now use consistent pattern detection and quality scoring
- **Reporting**: Both systems generate comparable markdown reports with sophisticated recommendations