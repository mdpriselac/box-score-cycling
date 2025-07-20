"""
Pattern classifier module for correlation feature analysis.

Classifies correlation patterns across percentiles.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class CorrelationPatternClassifier:
    """Classifies correlation patterns across percentiles"""
    
    def __init__(self, stability_threshold: float = 0.02,
                 trend_slope_threshold: float = 0.001,
                 trend_r_threshold: float = 0.7):
        """
        Initialize pattern classifier with thresholds.
        
        Args:
            stability_threshold: Threshold for considering pattern highly stable
            trend_slope_threshold: Minimum slope for trend detection
            trend_r_threshold: Minimum r-value for trend significance
        """
        self.stability_threshold = stability_threshold
        self.trend_slope_threshold = trend_slope_threshold
        self.trend_r_threshold = trend_r_threshold
    
    def classify_pattern(self, slope: float, r_value: float,
                        correlations: np.ndarray, stability: float) -> str:
        """
        Classify the correlation pattern for a feature.
        
        Args:
            slope: Trend slope from linear regression
            r_value: Correlation coefficient of the trend
            correlations: Array of mean correlations across percentiles
            stability: Stability score (0-1)
            
        Returns:
            Pattern classification string
        """
        # Very stable across percentiles
        if np.std(correlations) < self.stability_threshold:
            return 'highly_stable'
        
        # Stable with minor variation
        elif stability > 0.8:
            return 'stable'
        
        # Clear decreasing trend (elite-focused)
        elif slope < -self.trend_slope_threshold and r_value < -self.trend_r_threshold:
            return 'elite_focused'
        
        # Clear increasing trend (mass-inclusive)  
        elif slope > self.trend_slope_threshold and r_value > self.trend_r_threshold:
            return 'mass_inclusive'
        
        # Peak in middle percentiles
        peak_idx = np.argmax(np.abs(correlations))
        if 1 < peak_idx < len(correlations) - 2:
            # Check if it's a clear peak (higher than neighbors)
            if peak_idx > 0 and peak_idx < len(correlations) - 1:
                peak_val = abs(correlations[peak_idx])
                left_val = abs(correlations[peak_idx - 1])
                right_val = abs(correlations[peak_idx + 1])
                if peak_val > left_val * 1.1 and peak_val > right_val * 1.1:
                    return 'middle_peak'
        
        # High variability
        elif stability < 0.5:
            return 'highly_variable'
        
        # Default to complex pattern
        return 'complex'
    
    def analyze_all_patterns(self, stats_df: pd.DataFrame,
                           trend_results: Dict[str, Dict]) -> Dict[str, Dict]:
        """
        Analyze patterns for all features.
        
        Args:
            stats_df: DataFrame with statistics for all features
            trend_results: Dictionary with trend analysis results per feature
            
        Returns:
            Dictionary mapping feature names to pattern analysis results
        """
        patterns = {}
        
        for feature in stats_df['feature_name'].unique():
            feature_stats = stats_df[stats_df['feature_name'] == feature].sort_values('percentile')
            
            if len(feature_stats) < 4:  # Need at least 4 percentiles
                patterns[feature] = {
                    'pattern_classification': 'insufficient_data',
                    'percentile_coverage': len(feature_stats),
                    'trend_slope': 0,
                    'trend_r2': 0,
                    'correlation_stability': 0
                }
                continue
            
            # Get trend info if available
            trend_info = trend_results.get(feature, {})
            slope = trend_info.get('slope', 0)
            r_value = trend_info.get('r_value', 0)
            
            # Get correlations and stability
            mean_corrs = feature_stats['mean_correlation'].values
            correlation_stability = trend_info.get('correlation_stability', 0)
            
            # Classify the pattern
            pattern = self.classify_pattern(slope, r_value, mean_corrs, correlation_stability)
            
            patterns[feature] = {
                'pattern_classification': pattern,
                'percentile_coverage': len(feature_stats),
                'trend_slope': slope,
                'trend_r2': r_value ** 2,
                'correlation_stability': correlation_stability
            }
        
        return patterns
    
    def get_pattern_summary(self, patterns: Dict[str, Dict]) -> Dict[str, List[str]]:
        """
        Summarize features by pattern type.
        
        Args:
            patterns: Dictionary of pattern analysis results
            
        Returns:
            Dictionary mapping pattern types to lists of features
        """
        pattern_summary = {}
        
        for feature, pattern_info in patterns.items():
            pattern_type = pattern_info['pattern_classification']
            
            if pattern_type not in pattern_summary:
                pattern_summary[pattern_type] = []
            
            pattern_summary[pattern_type].append(feature)
        
        return pattern_summary
    
    def get_pattern_counts(self, patterns: Dict[str, Dict]) -> Dict[str, int]:
        """
        Count features by pattern type.
        
        Args:
            patterns: Dictionary of pattern analysis results
            
        Returns:
            Dictionary mapping pattern types to counts
        """
        pattern_counts = {}
        
        for pattern_info in patterns.values():
            pattern_type = pattern_info['pattern_classification']
            pattern_counts[pattern_type] = pattern_counts.get(pattern_type, 0) + 1
        
        return pattern_counts
    
    def identify_percentile_specific_features(self, patterns: Dict[str, Dict],
                                            stats_df: pd.DataFrame,
                                            percentiles: List[int]) -> Dict[int, List[Tuple[str, float]]]:
        """
        Identify which features work best at each percentile.
        
        Args:
            patterns: Dictionary of pattern analysis results
            stats_df: DataFrame with feature statistics
            percentiles: List of percentile values to analyze
            
        Returns:
            Dictionary mapping percentiles to lists of (feature, correlation) tuples
        """
        percentile_features = {p: [] for p in percentiles}
        
        for percentile in percentiles:
            p_stats = stats_df[stats_df['percentile'] == percentile]
            
            # Get features with strong correlations at this percentile
            for _, row in p_stats.iterrows():
                feature = row['feature_name']
                correlation = abs(row['mean_correlation'])
                
                # Only include if pattern is reasonable
                pattern = patterns.get(feature, {}).get('pattern_classification', 'unknown')
                if pattern not in ['highly_variable', 'insufficient_data']:
                    percentile_features[percentile].append((feature, correlation))
            
            # Sort by correlation strength
            percentile_features[percentile].sort(key=lambda x: x[1], reverse=True)
        
        return percentile_features