# Race Type Analysis Usage Guide

## Overview

The race type analysis extends the original feature N-analysis to examine how cycling race features behave differently across specific race types. This allows you to understand whether feature patterns are consistent across all race types or vary by competitive format.

## Available Race Types

Based on your database, the following race types are available:

- **`gc`**: Grand Tour/General Classification races (998 races)
- **`stage`**: Stage races (5,903 races) 
- **`one_day`**: One-day races (1,249 races)
- **`stage_one_day`**: Combined stage + one-day races (7,152 races)
- **`all_types`**: All race types combined (no filter)

## Running Race Type Analysis

### Single Race Type Analysis

Analyze features for just one race type:

```bash
cd feature_optimization
uv run python run_race_type_analysis.py --race-types gc
```

This will:
- Analyze all 37 features for GC races only
- Generate JSON results file: `race_analysis_gc_YYYYMMDD_HHMMSS.json`
- Generate markdown report: `race_analysis_gc_report_YYYYMMDD_HHMMSS.md`
- Display summary in console

### Multiple Race Type Analysis

Analyze and compare across multiple race types:

```bash
uv run python run_race_type_analysis.py --race-types gc stage one_day
```

This will:
- Run separate analysis for each race type
- Generate individual results and reports for each
- Create a comparison report: `race_type_comparison_YYYYMMDD_HHMMSS.md`

### Complete Analysis

Run analysis for all race type configurations:

```bash
uv run python run_race_type_analysis.py
```

This analyzes: `gc`, `stage`, `one_day`, `stage_one_day`, `all_types`

## Understanding Race Type Results

### Key Differences to Look For

1. **Feature Quality Rankings**: Do the same features rank highly across all race types?

2. **Behavior Pattern Changes**: 
   - A feature might be "stable" for GC races but show "dilution" for one-day races
   - Different race types may have different threshold N-levels

3. **N-Level Recommendations**:
   - Elite-focused race types (GC) might have different optimal N ranges than mass participation events

4. **Information Content**:
   - Features that distinguish well between GC races might be less informative for stage races

### Example Interpretations

**If `abandon_ratio` is Tier 1 for GC races but Tier 3 for stage races:**
- Abandonment patterns are highly informative for distinguishing between different GC events
- Stage races have more consistent abandonment patterns, making this feature less discriminative

**If `selection_metric` shows threshold behavior at N=40 for one-day races but N=70 for stage races:**
- One-day races have a sharper competitive divide at the 40th percentile
- Stage races maintain competitive selection deeper into the field

## Output Files Structure

```
race_type_analysis_results/
├── race_analysis_gc_YYYYMMDD_HHMMSS.json
├── race_analysis_gc_report_YYYYMMDD_HHMMSS.md
├── race_analysis_stage_YYYYMMDD_HHMMSS.json
├── race_analysis_stage_report_YYYYMMDD_HHMMSS.md
├── race_analysis_one_day_YYYYMMDD_HHMMSS.json
├── race_analysis_one_day_report_YYYYMMDD_HHMMSS.md
├── race_analysis_stage_one_day_YYYYMMDD_HHMMSS.json
├── race_analysis_stage_one_day_report_YYYYMMDD_HHMMSS.md
├── race_analysis_all_types_YYYYMMDD_HHMMSS.json
├── race_analysis_all_types_report_YYYYMMDD_HHMMSS.md
└── race_type_comparison_YYYYMMDD_HHMMSS.md
```

## Command Line Options

```bash
usage: run_race_type_analysis.py [-h] [--db-path DB_PATH] [--output-dir OUTPUT_DIR] 
                                 [--race-types {gc,stage,one_day,stage_one_day,all_types} [...]]

optional arguments:
  -h, --help            show this help message and exit
  --db-path DB_PATH     Path to the SQLite database (default: ../database/database/cycling_races.db)
  --output-dir OUTPUT_DIR
                        Directory to save analysis results (default: ./race_type_analysis_results)
  --race-types {gc,stage,one_day,stage_one_day,all_types} [...]
                        Race types to analyze (default: all)
```

## Performance Considerations

- **GC races**: Fast analysis (998 races)
- **One-day races**: Moderate (1,249 races)  
- **Stage races**: Slower (5,903 races)
- **Combined/All types**: Slowest but most comprehensive

For initial exploration, start with GC races for fastest results, then expand to other types.

## Technical Implementation

The race type analysis works by:

1. **Filtered Analyzers**: Each analyzer class has been extended with race type filtering
2. **SQL Query Modification**: Database queries include `WHERE competition_type = 'race_type'` conditions
3. **Batch Processing**: The `RaceTypeAnalyzer` coordinates multiple filtered analyses
4. **Comparison Generation**: Results are automatically compared across race types

**Code Location**: 
- Main coordinator: `race_type_analyzer.py`
- Filtered analyzers: `race_type_filtered_analyzer.py` 
- Batch runner: `run_race_type_analysis.py`

This approach maintains full compatibility with the original analysis while adding race type specificity.