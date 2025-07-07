# Statistical Measures Module

This module provides statistical functions for analyzing race finishing time distributions.

## Functions

### calculate_gini_coefficient(values: List[float]) -> float
Calculates the Gini coefficient to measure inequality in a distribution.
- **Input**: `values` - List of time gaps (non-negative values)
- **Output**: Float between 0 and 1 (0 = perfect equality, 1 = maximum inequality)
- **Example**: `gini = calculate_gini_coefficient([0, 10, 20, 30, 100])`

### calculate_shannon_entropy(values: List[float], bins: int = None) -> Tuple[float, float]
Calculates Shannon entropy to measure unpredictability of finishing times.
- **Input**: 
  - `values` - List of time gaps or finishing times
  - `bins` - Number of histogram bins (optional, auto-calculated if None)
- **Output**: Tuple of (absolute_entropy, normalized_entropy)
- **Example**: `abs_entropy, norm_entropy = calculate_shannon_entropy(time_gaps)`

### calculate_variance_and_std(values: List[float], normalize_by: float = None) -> Tuple[float, float]
Calculates variance and standard deviation with optional normalization.
- **Input**:
  - `values` - List of values to analyze
  - `normalize_by` - Optional normalization factor (e.g., winning time)
- **Output**: Tuple of (variance, standard_deviation)
- **Example**: `var, std = calculate_variance_and_std(time_gaps, normalize_by=winning_time)`

### calculate_skewness(values: List[float], normalize_by: float = None) -> float
Calculates skewness to measure distribution asymmetry.
- **Input**:
  - `values` - List of values to analyze
  - `normalize_by` - Optional normalization factor
- **Output**: Skewness value (negative = left tail, positive = right tail)
- **Example**: `skew = calculate_skewness(time_gaps)`

### calculate_kurtosis(values: List[float], normalize_by: float = None) -> float
Calculates excess kurtosis to measure distribution "tailedness".
- **Input**:
  - `values` - List of values to analyze
  - `normalize_by` - Optional normalization factor
- **Output**: Excess kurtosis (0 = normal distribution)
- **Example**: `kurt = calculate_kurtosis(time_gaps)`

### calculate_percentile_gaps(values: List[float], percentiles: List[int] = None) -> dict
Calculates gap values at specified percentiles.
- **Input**:
  - `values` - List of time gaps from winner
  - `percentiles` - List of percentiles (default: [5, 10, 15, ..., 50])
- **Output**: Dictionary mapping percentile names to gap values
- **Example**: `gaps = calculate_percentile_gaps(time_gaps, [10, 25, 50, 75, 90])`