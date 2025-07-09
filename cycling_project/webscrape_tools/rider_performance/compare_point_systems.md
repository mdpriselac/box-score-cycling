# compare_point_systems.py

Module for comparing model performance between actual and proportional UCI point systems.

## Overview

This module runs temporal backtests using both UCI point schemes and generates comprehensive comparison reports to help determine which system works better for prediction.

**Key Comparisons:**
- Zero inflation reduction
- Ranking accuracy improvements
- Classification performance
- Feature importance differences

## Functions

### `compare_point_systems(db_path: str, test_year: int, min_results: int = 10, output_dir: str = "rider_performance/comparisons") -> Dict`

Run backtest with both point systems and compare results.

**Parameters:**
- `db_path` (str): Path to database
- `test_year` (int): Year to test on
- `min_results` (int): Minimum results per rider (default: 10)
- `output_dir` (str): Directory for comparison reports

**Returns:**
- `Dict`: Comparison results with metrics for both systems

### `generate_comparison_report(actual_results: Dict, proportional_results: Dict, test_year: int, output_dir: str) -> Dict`

Generate detailed markdown comparison report between the two point systems.

## Usage Example

```python
from compare_point_systems import compare_point_systems

# Compare point systems for 2023
comparison = compare_point_systems(
    db_path="database/database/cycling_races.db",
    test_year=2023,
    min_results=15
)

# Results show improvements with proportional system
for model_type, data in comparison.items():
    print(f"{model_type}: Zero inflation reduced by {data['zero_reduction']:.1f}pp")
    print(f"          Spearman improved by {data['spearman_improvement']:.4f}")
```

## Output Report Structure

The markdown report includes:

### 1. Executive Summary
- Zero inflation reduction for each model
- Ranking accuracy improvements
- Overall recommendation

### 2. Detailed Metrics Comparison

#### Zero Inflation Table
Shows the percentage of zero-point results for each system:
```
| Point System | Zero % | Non-zero Samples |
|--------------|--------|------------------|
| Actual UCI   | 89.2%  | 1,234           |
| Proportional | 45.3%  | 6,789           |
| Improvement  | 43.9pp | +5,555          |
```

#### Ranking Metrics Table
Compares all ranking-based metrics with ✅/❌ indicators

#### Classification Metrics
How well each system identifies point-scorers

#### Regression Metrics
With notes about comparability between different scales

### 3. Key Findings
- Summarizes major improvements
- Highlights where proportional system excels
- Notes any trade-offs

### 4. Recommendations
- Clear recommendation based on results
- Suggested next steps
- Areas for further investigation

## Key Insights

The proportional point system typically shows:

1. **Dramatic Zero Inflation Reduction**
   - GC/One-day: ~90% → ~40-50% zeros
   - Stages: ~95% → ~70-80% zeros

2. **Improved Ranking Metrics**
   - Better Spearman correlations
   - Higher top-K accuracy
   - Better within-race rankings

3. **More Stable Models**
   - More training signal
   - Better gradient flow
   - Less reliance on classification

## Interpreting Results

### When Proportional is Better
- ✅ Large reduction in zero inflation (>30pp)
- ✅ Positive Spearman improvement
- ✅ Better top-K accuracy
- ✅ More consistent within-race rankings

### Caveats
- RMSE values not directly comparable (different scales)
- Some races may still have high zero rates
- Stage races may need extended point coverage

## Next Steps

After running comparison:

1. **Confirm Consistency**: Run on multiple years
2. **Analyze by Race Type**: Which races benefit most?
3. **Consider Modifications**: 
   - Extend stage points to 60th place?
   - Adjust discount factors?
4. **Production Decision**: Choose system based on evidence

## Example Output

The generated markdown report provides clear visual comparison:
- Tables with color coding
- ✅/❌ indicators for improvements
- Executive summary with key takeaways
- Actionable recommendations

This makes it easy to make data-driven decisions about which point system to use in production.