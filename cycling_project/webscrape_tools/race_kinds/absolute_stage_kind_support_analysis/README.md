# Absolute Stage Kind Support Analysis

This analysis system determines which absolute feature values and percentile levels are most effective for segmenting cycling stage races into distinct kinds/clusters. Unlike gradient analysis which looks at how features change across percentiles, this system analyzes the raw absolute values at each percentile level.

## Overview

The system analyzes 5,298 stage races (90 minutes to 8 hours) split into two fundamental groups:
- **2,743 races with kurtosis breakdowns** (51.8%) - races where statistical consistency breaks down
- **2,555 races without breakdowns** (48.2%) - races with consistent statistical properties

## Key Findings for Clustering Systems

### Primary Discriminator: Breakdown Detection
The presence or absence of kurtosis breakdowns is itself a powerful race classifier:
- 87.9% of breakdowns occur at the 10% percentile
- 11.4% occur at 15%, with rare cases at 20-25%
- This creates a natural binary split for initial race categorization

### Tier-Based Feature Quality

The system uses natural gap detection to identify quality tiers rather than arbitrary top-N lists:

#### For Breakdown Races (Excellent Tier):
- `"30th_percentile_gap"` at 30% percentile (score: 15.99)
- `"20th_percentile_gap"` at 45% percentile (score: 14.50)

#### For No-Breakdown Races (Highest Performing):
- `skewness_normalized` at 50% percentile (score: 26.51)
- `skewness_absolute` at 50% percentile (score: 26.47)

### Optimal Percentile Levels

Different race types benefit from different percentile analyses:

**Breakdown Races**: Focus on percentiles 30, 45, 15
- Early percentiles (10-30%) capture breakdown effects
- Gap-based features excel at these levels

**No-Breakdown Races**: Focus on percentiles 50, 55, 45  
- Mid-range percentiles show strongest discrimination
- Distribution shape features (skewness) perform best

## Data Structure for Clustering

### Race-Level Features
Each race can be characterized by:
1. **Breakdown Status**: Binary (has_breakdown: True/False)
2. **Breakdown Point**: Integer percentile where breakdown occurs (null if none)
3. **Feature Values**: Arrays of absolute values across percentile levels

### Feature-Percentile Combinations
The analysis identifies 578 valid feature-percentile combinations with separability scores ranging from 0.01 to 26.51.

### Quality Tiers
Natural breakpoints create meaningful quality classifications:
- **Excellent**: Score > 14.5 (2 combinations)
- **Very Good**: Score 12.6-14.5 (1 combination)  
- **Good**: Score 11.9-12.6 (1 combination)
- **Fair**: Score < 11.9 (574 combinations)

## Recommended Clustering Approaches

### Two-Stage Clustering Strategy

#### Stage 1: Binary Classification
```
if kurtosis_breakdown_point is not None:
    race_type = "breakdown"
    primary_features = ["30th_percentile_gap", "20th_percentile_gap", "15th_percentile_gap"]
    optimal_percentiles = [30, 45, 60]
else:
    race_type = "no_breakdown" 
    primary_features = ["skewness_normalized", "skewness_absolute"]
    optimal_percentiles = [50, 55, 45]
```

#### Stage 2: Within-Group Clustering
Use type-specific feature sets for finer-grained race kind discovery:

**Breakdown Races**:
- Gap-based features at early percentiles
- Variance features at 15% percentile
- Consider breakdown point as additional feature

**No-Breakdown Races**:
- Distribution shape features at mid-percentiles
- Group dynamics features (clumpiness, selection metrics)
- Time gap evenness at higher percentiles

### Universal Feature Set
For unified clustering across all races:
- Use top universal combinations that work for both groups
- Primary candidates: variance features at 100% percentile, statistical distribution features

## Feature Engineering Recommendations

### Composite Features
1. **Breakdown Signature**: Combination of breakdown point + gap pattern
2. **Distribution Profile**: Skewness + kurtosis + variance at optimal percentiles
3. **Selection Intensity**: Gap-based features + selection metrics

### Dimensionality Reduction
- Focus on Excellent/Very Good tier features first
- Use percentile-specific feature selection rather than all percentiles
- Consider breakdown status as mandatory clustering constraint

### Distance Metrics
Different race types may benefit from different distance calculations:
- **Breakdown races**: Emphasize gap-based feature differences
- **No-breakdown races**: Emphasize distribution shape similarities

## Data Files

### Analysis Results
- `absolute_breakdown_analysis.json`: Comprehensive results for breakdown races
- `absolute_no_breakdown_analysis.json`: Comprehensive results for no-breakdown races  
- `absolute_comparison_analysis.json`: Comparative analysis between groups

### Tier Classifications
- `absolute_breakdown_top_combinations.csv`: Ranked feature-percentile combinations for breakdown races
- `absolute_no_breakdown_top_combinations.csv`: Ranked combinations for no-breakdown races
- `absolute_feature_comparison.csv`: Side-by-side comparison of all combinations

### Human-Readable Reports
- `absolute_breakdown_report.txt`: Detailed analysis of breakdown races with tier breakdowns
- `absolute_no_breakdown_report.txt`: Detailed analysis of no-breakdown races
- `absolute_comparison_report.txt`: Strategic recommendations for unified vs. separate approaches

## Usage for Clustering Systems

### Quick Start
1. Load race data with absolute features across percentiles 10-100
2. Detect breakdown points using `find_kurtosis_breakdown_point.py`
3. Apply tier-based feature selection from analysis results
4. Use recommended percentile-feature combinations for clustering input

### Advanced Implementation
1. **Hierarchical Approach**: First cluster by breakdown status, then within groups
2. **Ensemble Methods**: Combine predictions from breakdown-specific and universal models
3. **Adaptive Percentiles**: Use different percentile sets based on race characteristics

### Validation Strategy
- Cross-validate using breakdown/no-breakdown splits
- Test cluster stability across different percentile selections
- Validate that clusters correspond to meaningful race characteristics

## Technical Notes

### Score Interpretation
Separability scores represent the coefficient of variation combined with entropy and distinctiveness measures. Higher scores indicate better potential for distinguishing race kinds.

### Completeness Requirements
All top-tier combinations have 100% data completeness, ensuring robust clustering inputs.

### Statistical Validity
The tier detection uses gap-based analysis to find natural breakpoints in score distributions, avoiding arbitrary cutoffs and ensuring statistically meaningful quality classifications.