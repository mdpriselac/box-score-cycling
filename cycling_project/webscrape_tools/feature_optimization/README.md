# Feature Optimization - Race Feature N Analysis

This package provides comprehensive analysis of cycling race features across different percentile thresholds (N levels) and race types.

## Quick Start

```bash
# Analyze all race types
uv run python run_race_type_analysis.py

# Analyze specific race types
uv run python run_race_type_analysis.py --race-types gc stage

# Analyze single race type
uv run python run_race_type_analysis.py --race-types gc
```

## Output

The analysis generates:
- Individual JSON results for each race type
- Markdown summary reports 
- Comparison report across race types
- Feature behavior categorization and quality rankings

## Documentation

- **Feature Categories & Quality Explanations**: `race_feature_n_analysis/race_feature_N_analysis_explanations.md`
- **Race Type Analysis Usage**: `race_feature_n_analysis/race_type_analysis_usage.md`
- **Original Design Documents**: 
  - `race_feature_N_analysis_design.md` - Core analysis design
  - `feature_optimization_design.md` - Overall optimization framework
  - `feature_analysis_reporter_design.md` - Reporting system design

## Available Race Types

- `gc`: General Classification races (998 races)
- `stage`: Stage races (5,903 races)  
- `one_day`: One-day races (1,249 races)
- `stage_one_day`: Combined stage + one-day (7,152 races)
- `all_types`: All race types (no filter)

## Components

All analysis components are in the `race_feature_n_analysis/` subfolder:

- **Core analyzers**: Variability, monotonicity, distinctiveness, pattern classification
- **Race type filtering**: Analyze by specific race formats
- **Batch processing**: Compare across multiple race types
- **Reporting**: Generate comprehensive analysis reports