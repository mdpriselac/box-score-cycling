"""
Statistical Measures for Race Analysis

This module provides statistical functions to analyze race finishing time distributions.
All formulas have been verified for correctness.
"""

import numpy as np
from scipy import stats
from typing import List, Tuple


def calculate_gini_coefficient(values: List[float]) -> float:
    """
    Calculate the Gini coefficient for a list of values.
    
    The Gini coefficient measures statistical dispersion intended to represent 
    the income or wealth distribution. In our case, it measures the inequality
    in time gaps. A value of 0 represents perfect equality (all gaps are the same),
    while 1 represents maximal inequality.
    
    Formula: G = (2 * sum(i * x[i])) / (n * sum(x[i])) - (n + 1) / n
    where x[i] are sorted values
    
    Args:
        values: List of time gaps (or other non-negative values)
        
    Returns:
        Gini coefficient between 0 and 1
    """
    # Convert to numpy array and remove any negative values
    values = np.array(values)
    values = values[values >= 0]
    
    if len(values) == 0:
        return 0.0
    
    # All values are zero
    if np.sum(values) == 0:
        return 0.0
    
    # Sort values in ascending order
    sorted_values = np.sort(values)
    n = len(sorted_values)
    
    # Calculate Gini using the formula
    # G = (2 * sum of (i * x[i])) / (n * sum of x[i]) - (n + 1) / n
    index = np.arange(1, n + 1)
    gini = (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n
    
    # Ensure result is between 0 and 1
    return np.clip(gini, 0, 1)


def calculate_shannon_entropy(values: List[float], bins: int = None) -> Tuple[float, float]:
    """
    Calculate Shannon entropy for a distribution of values.
    
    Shannon entropy measures the average information content in a message.
    For race data, it quantifies the unpredictability of finishing times.
    Higher entropy means more spread out/unpredictable results.
    
    Formula: H = -sum(p[i] * log2(p[i])) where p[i] are probabilities
    
    Args:
        values: List of time gaps or finishing times
        bins: Number of bins for histogram. If None, uses 'auto' method
        
    Returns:
        Tuple of (absolute_entropy, normalized_entropy)
        - absolute_entropy: Raw Shannon entropy value
        - normalized_entropy: Entropy normalized by log2(n) where n is number of bins
    """
    values = np.array(values)
    
    if len(values) == 0:
        return 0.0, 0.0
    
    # If all values are identical, entropy is 0
    if np.std(values) == 0:
        return 0.0, 0.0
    
    # Create histogram to get probability distribution
    if bins is None:
        # Use Freedman-Diaconis rule for optimal bin width
        q75, q25 = np.percentile(values, [75, 25])
        iqr = q75 - q25
        if iqr > 0:
            bin_width = 2 * iqr * (len(values) ** (-1/3))
            bins = int((np.max(values) - np.min(values)) / bin_width)
            bins = max(bins, 5)  # Ensure at least 5 bins
        else:
            bins = 10  # Default fallback
    
    # Get histogram
    hist, _ = np.histogram(values, bins=bins)
    
    # Convert to probabilities
    probabilities = hist / np.sum(hist)
    
    # Remove zero probabilities (log(0) is undefined)
    probabilities = probabilities[probabilities > 0]
    
    # Calculate Shannon entropy
    entropy = -np.sum(probabilities * np.log2(probabilities))
    
    # Calculate normalized entropy (0 to 1)
    # Maximum entropy occurs when all bins have equal probability
    max_entropy = np.log2(len(probabilities))
    normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
    
    return float(entropy), float(normalized_entropy)


def calculate_variance_and_std(values: List[float], normalize_by: float = None) -> Tuple[float, float]:
    """
    Calculate variance and standard deviation, optionally normalized.
    
    Args:
        values: List of values to analyze
        normalize_by: Optional value to normalize by (e.g., winning time)
        
    Returns:
        Tuple of (variance, standard_deviation)
    """
    values = np.array(values)
    
    if normalize_by is not None and normalize_by != 0:
        values = values / normalize_by
    
    variance = np.var(values)
    std_dev = np.std(values)
    
    return float(variance), float(std_dev)


def calculate_skewness(values: List[float], normalize_by: float = None) -> float:
    """
    Calculate skewness of a distribution.
    
    Skewness measures the asymmetry of the probability distribution.
    - Negative skew: tail on the left side (more riders bunched at front)
    - Positive skew: tail on the right side (more riders spread at back)
    - Zero skew: symmetric distribution
    
    Args:
        values: List of values to analyze
        normalize_by: Optional value to normalize by
        
    Returns:
        Skewness value (or 0 if no variance)
    """
    values = np.array(values)
    
    if normalize_by is not None and normalize_by != 0:
        values = values / normalize_by
    
    # Return 0 if there's no variance (all values are identical)
    if np.var(values) == 0:
        return 0.0
    
    return float(stats.skew(values))


def calculate_kurtosis(values: List[float], normalize_by: float = None) -> float:
    """
    Calculate kurtosis of a distribution.
    
    Kurtosis measures the "tailedness" of the distribution.
    - High kurtosis: heavy tails, more outliers
    - Low kurtosis: light tails, fewer outliers
    
    Uses excess kurtosis (normal distribution = 0)
    
    Args:
        values: List of values to analyze
        normalize_by: Optional value to normalize by
        
    Returns:
        Excess kurtosis value
    """
    values = np.array(values)
    
    if normalize_by is not None and normalize_by != 0:
        values = values / normalize_by
    
    # stats.kurtosis calculates excess kurtosis by default
    return float(stats.kurtosis(values))


def calculate_percentile_gaps(values: List[float], percentiles: List[int] = None) -> dict:
    """
    Calculate gaps at specific percentiles.
    
    Args:
        values: List of time gaps from winner
        percentiles: List of percentiles to calculate (default: [5, 10, 15, ..., 50])
        
    Returns:
        Dictionary mapping percentile to gap value
    """
    if percentiles is None:
        percentiles = list(range(5, 55, 5))
    
    values = np.array(values)
    result = {}
    
    for p in percentiles:
        if 0 <= p <= 100:
            result[f'{p}th_percentile_gap'] = float(np.percentile(values, p))
    
    return result