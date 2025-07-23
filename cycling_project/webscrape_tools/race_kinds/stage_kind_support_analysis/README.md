# Stage Race Kind Support Analysis

This folder contains the analysis of how well gradient features support separating stage races into different kinds.

## Files

### Scripts
- **`analyze_stage_separability.py`** - Main analysis script that processes stage competitions and evaluates feature separability potential

### Results
- **`stage_separability_analysis.json`** - Complete machine-readable analysis results with all metrics and natural tiers
- **`stage_separability_report.txt`** - Human-readable summary report with key findings and recommendations
- **`stage_competitions_data.csv`** - Raw dataset of stage competitions used in analysis (5,935 races)

## Key Findings

### Natural Feature Quality Tiers
- **Excellent (4 features)**: variance_normalized, kurtosis_breakdown_point, nth_percentile_gap_5, nth_percentile_gap_25
- **Very Good (1 feature)**: nth_percentile_gap_50  
- **Good (5 features)**: variance_absolute, variance_breakdown_point, kurtosis metrics, biggest_group_metric
- **Fair (5 features)**: skewness, gini, clumpiness, selection metrics

### Top Features for Race Classification
1. **variance_normalized** (2.54) - How variance evolves across percentiles
2. **kurtosis_breakdown_point** (2.46) - When statistical complexity breaks down
3. **nth_percentile_gap_5** (2.32) - 5th percentile time gap evolution
4. **nth_percentile_gap_25** (1.84) - 25th percentile time gap evolution

## Usage

To regenerate the analysis:

```bash
cd /path/to/stage_kind_support_analysis
uv run python analyze_stage_separability.py
```

## Analysis Criteria

- **Dataset**: 5,935 stage competitions with winning_time > 90 minutes (filters out time trials)
- **Features**: 15 total (13 gradient features + 2 quality indicators)
- **Metrics**: Natural breakpoint analysis, entropy-based separability scores
- **Coverage**: 100% data completeness across all features

## Next Steps

1. Use top 4 "Excellent" tier features for clustering analysis
2. Validate clusters against known race characteristics  
3. Develop machine learning classifier using selected features
4. Test classification accuracy on held-out data