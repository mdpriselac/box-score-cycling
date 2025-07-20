"""
Statistics calculator module for correlation feature analysis.

Calculates statistical measures for correlations.
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class CorrelationStats:
    """Statistics for a feature at a specific percentile"""
    feature_name: str
    percentile: int
    correlation_type: str
    mean_correlation: float
    std_correlation: float
    median_correlation: float
    percentile_25: float
    percentile_75: float
    iqr: float
    min_correlation: float
    max_correlation: float
    sample_size: int
    null_count: int
    null_percentage: float
    skewness: float
    kurtosis: float


class CorrelationStatisticsCalculator:
    """Calculates statistical measures for correlations"""
    
    @staticmethod
    def calculate_feature_stats(feature_name: str, percentile: int, 
                              correlation_type: str, data: pd.DataFrame) -> Optional[Dict]:
        """
        Calculate comprehensive stats for a feature-percentile combination.
        
        Args:
            feature_name: Name of the feature
            percentile: Percentile level (30, 40, ..., 100)
            correlation_type: Type of correlation
            data: DataFrame with correlation values
            
        Returns:
            Dictionary of statistics or None if no data
        """
        correlations = data['correlation_value'].dropna()
        
        if len(correlations) == 0:
            return None
        
        total_count = data['total_count'].iloc[0] if len(data) > 0 else 0
        null_count = data['null_count'].iloc[0] if len(data) > 0 else 0
        
        stats_dict = {
            'feature_name': feature_name,
            'percentile': percentile,
            'correlation_type': correlation_type,
            'mean_correlation': correlations.mean(),
            'std_correlation': correlations.std(),
            'median_correlation': correlations.median(),
            'percentile_25': correlations.quantile(0.25),
            'percentile_75': correlations.quantile(0.75),
            'iqr': correlations.quantile(0.75) - correlations.quantile(0.25),
            'min_correlation': correlations.min(),
            'max_correlation': correlations.max(),
            'sample_size': len(correlations),
            'null_count': int(null_count),
            'null_percentage': null_count / total_count if total_count > 0 else 0,
            'skewness': correlations.skew(),
            'kurtosis': correlations.kurtosis()
        }
        
        return stats_dict
    
    @staticmethod
    def calculate_trend(percentiles: np.ndarray, values: np.ndarray) -> Dict:
        """
        Calculate trend statistics for values across percentiles.
        
        Args:
            percentiles: Array of percentile values
            values: Array of corresponding values (e.g., mean correlations)
            
        Returns:
            Dictionary with trend statistics
        """
        if len(percentiles) < 2:
            return {
                'slope': 0,
                'intercept': 0,
                'r_value': 0,
                'p_value': 1,
                'std_err': 0,
                'r_squared': 0
            }
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(percentiles, values)
        
        return {
            'slope': slope,
            'intercept': intercept,
            'r_value': r_value,
            'p_value': p_value,
            'std_err': std_err,
            'r_squared': r_value ** 2
        }
    
    @staticmethod
    def calculate_stability_metrics(feature_stats: pd.DataFrame) -> Dict:
        """
        Calculate stability metrics for a feature across percentiles.
        
        Args:
            feature_stats: DataFrame with stats for one feature across percentiles
            
        Returns:
            Dictionary with stability metrics
        """
        if len(feature_stats) == 0:
            return {
                'mean_std': 0,
                'correlation_stability': 0,
                'cv_mean': 0,
                'range_mean': 0
            }
        
        # Average standard deviation across percentiles
        mean_std = feature_stats['std_correlation'].mean()
        
        # Stability score (inverse of average std)
        correlation_stability = 1 - mean_std if mean_std < 1 else 0
        
        # Coefficient of variation for mean correlations
        mean_corrs = feature_stats['mean_correlation'].values
        cv_mean = np.std(mean_corrs) / np.mean(np.abs(mean_corrs)) if np.mean(np.abs(mean_corrs)) > 0 else 0
        
        # Range of mean correlations
        range_mean = np.max(mean_corrs) - np.min(mean_corrs)
        
        return {
            'mean_std': mean_std,
            'correlation_stability': correlation_stability,
            'cv_mean': cv_mean,
            'range_mean': range_mean
        }
    
    @staticmethod
    def find_optimal_percentile(feature_stats: pd.DataFrame) -> Tuple[int, float]:
        """
        Find the percentile with the strongest correlation for a feature.
        
        Args:
            feature_stats: DataFrame with stats for one feature across percentiles
            
        Returns:
            Tuple of (optimal_percentile, optimal_strength)
        """
        if len(feature_stats) == 0:
            return (0, 0.0)
        
        # Find percentile with highest absolute mean correlation
        abs_means = feature_stats['mean_correlation'].abs()
        optimal_idx = abs_means.idxmax()
        
        optimal_percentile = int(feature_stats.loc[optimal_idx, 'percentile'])
        optimal_strength = float(abs_means.loc[optimal_idx])
        
        return (optimal_percentile, optimal_strength)
    
    @staticmethod
    def calculate_percentile_coverage(feature_stats: pd.DataFrame, 
                                    expected_percentiles: List[int]) -> float:
        """
        Calculate what percentage of expected percentiles have data.
        
        Args:
            feature_stats: DataFrame with stats for one feature
            expected_percentiles: List of expected percentile values
            
        Returns:
            Coverage percentage (0-1)
        """
        actual_percentiles = set(feature_stats['percentile'].values)
        expected_set = set(expected_percentiles)
        
        if len(expected_set) == 0:
            return 0.0
        
        return len(actual_percentiles.intersection(expected_set)) / len(expected_set)