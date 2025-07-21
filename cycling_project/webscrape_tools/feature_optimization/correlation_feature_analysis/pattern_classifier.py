"""
Pattern classifier module for correlation feature analysis.

Classifies correlation patterns across percentiles.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class CorrelationPatternClassifier:
    """Classifies correlation patterns across percentiles following race feature N approach"""
    
    def __init__(self, stability_threshold: float = 0.02,
                 trend_slope_threshold: float = 0.001,
                 trend_r_threshold: float = 0.7,
                 threshold_change_pct: float = 0.3,
                 bimodal_valley_ratio: float = 0.6):
        """
        Initialize pattern classifier with thresholds.
        
        Args:
            stability_threshold: Threshold for considering pattern highly stable
            trend_slope_threshold: Minimum slope for trend detection
            trend_r_threshold: Minimum r-value for trend significance
            threshold_change_pct: Minimum relative change to detect threshold
            bimodal_valley_ratio: Valley depth ratio for bimodality detection
        """
        self.stability_threshold = stability_threshold
        self.trend_slope_threshold = trend_slope_threshold
        self.trend_r_threshold = trend_r_threshold
        self.threshold_change_pct = threshold_change_pct
        self.bimodal_valley_ratio = bimodal_valley_ratio
    
    def detect_threshold(self, correlations: np.ndarray, percentiles: np.ndarray) -> Tuple[bool, int]:
        """
        Detect if there's a threshold effect in the correlation pattern.
        
        Args:
            correlations: Array of mean correlations across percentiles
            percentiles: Array of percentile values
            
        Returns:
            Tuple of (has_threshold, threshold_percentile)
        """
        if len(correlations) < 3:
            return False, 0
        
        # Calculate relative changes between consecutive percentiles
        relative_changes = []
        for i in range(1, len(correlations)):
            if abs(correlations[i-1]) > 0.01:  # Avoid division by very small numbers
                rel_change = abs((correlations[i] - correlations[i-1]) / correlations[i-1])
                relative_changes.append((rel_change, percentiles[i]))
        
        if not relative_changes:
            return False, 0
        
        # Find the maximum relative change
        max_change, threshold_percentile = max(relative_changes, key=lambda x: x[0])
        
        # Check if it's significant enough to be a threshold
        if max_change > self.threshold_change_pct:
            return True, int(threshold_percentile)
        
        return False, 0
    
    def test_bimodality(self, correlations: np.ndarray) -> bool:
        """
        Test if the correlation pattern shows bimodality.
        
        Args:
            correlations: Array of mean correlations across percentiles
            
        Returns:
            True if pattern appears bimodal
        """
        if len(correlations) < 5:
            return False
        
        abs_corrs = np.abs(correlations)
        
        # Find peaks (local maxima)
        peaks = []
        for i in range(1, len(abs_corrs) - 1):
            if abs_corrs[i] > abs_corrs[i-1] and abs_corrs[i] > abs_corrs[i+1]:
                peaks.append((i, abs_corrs[i]))
        
        if len(peaks) < 2:
            return False
        
        # Check if there's a significant valley between peaks
        for i in range(len(peaks) - 1):
            peak1_idx, peak1_val = peaks[i]
            peak2_idx, peak2_val = peaks[i+1]
            
            # Find minimum between peaks
            valley_region = abs_corrs[peak1_idx:peak2_idx+1]
            if len(valley_region) > 2:
                valley_min = np.min(valley_region)
                smaller_peak = min(peak1_val, peak2_val)
                
                # Check if valley is deep enough
                if valley_min < smaller_peak * self.bimodal_valley_ratio:
                    return True
        
        return False
    
    def classify_pattern(self, slope: float, r_value: float,
                        correlations: np.ndarray, percentiles: np.ndarray,
                        stability: float, cv_values: np.ndarray = None) -> str:
        """
        Classify the correlation pattern for a feature following race feature N patterns.
        
        Pattern types:
        1. Stable - Consistent across percentiles
        2. Dilution - Weakens as more riders included
        3. Concentration - Strengthens as more riders included
        4. Threshold - Sudden change at specific percentile
        5. Bimodal - Shows two distinct peaks
        6. Complex - Multiple patterns or unclear
        
        Args:
            slope: Trend slope from linear regression
            r_value: Correlation coefficient of the trend
            correlations: Array of mean correlations across percentiles
            percentiles: Array of percentile values
            stability: Stability score (0-1)
            cv_values: Coefficient of variation values (optional)
            
        Returns:
            Pattern classification string
        """
        # 1. Check for Stable pattern (low variation)
        if cv_values is not None:
            cv_stability = np.std(cv_values)
            is_stable = cv_stability < 0.1
        else:
            is_stable = np.std(correlations) < self.stability_threshold
        
        if is_stable:
            return 'stable'
        
        # 2. Check for Threshold pattern
        has_threshold, threshold_percentile = self.detect_threshold(correlations, percentiles)
        if has_threshold:
            return 'threshold'
        
        # 3. Check for Bimodal pattern
        if self.test_bimodality(correlations):
            return 'bimodal'
        
        # 4. Check for Dilution pattern (correlation weakens with more riders)
        # This corresponds to decreasing correlation strength
        if slope < -self.trend_slope_threshold and r_value < -self.trend_r_threshold:
            return 'dilution'
        
        # 5. Check for Concentration pattern (correlation strengthens with more riders)
        # This corresponds to increasing correlation strength
        if slope > self.trend_slope_threshold and r_value > self.trend_r_threshold:
            return 'concentration'
        
        # 6. Default to Complex pattern
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
            percentiles = feature_stats['percentile'].values
            correlation_stability = trend_info.get('correlation_stability', 0)
            cv_values = feature_stats['cv'].values if 'cv' in feature_stats.columns else None
            
            # Calculate correlation range for information value
            correlation_range = np.max(np.abs(mean_corrs)) - np.min(np.abs(mean_corrs))
            
            # Find optimal percentile (where correlation is strongest)
            optimal_idx = np.argmax(np.abs(mean_corrs))
            optimal_percentile = int(percentiles[optimal_idx])
            optimal_strength = mean_corrs[optimal_idx]
            
            # Classify the pattern
            pattern = self.classify_pattern(slope, r_value, mean_corrs, percentiles, 
                                          correlation_stability, cv_values)
            
            # Detect threshold if pattern is threshold
            threshold_percentile = None
            if pattern == 'threshold':
                _, threshold_percentile = self.detect_threshold(mean_corrs, percentiles)
            
            patterns[feature] = {
                'pattern_classification': pattern,
                'percentile_coverage': len(feature_stats),
                'trend_slope': slope,
                'trend_r2': r_value ** 2,
                'correlation_stability': correlation_stability,
                'correlation_range': correlation_range,
                'optimal_percentile': optimal_percentile,
                'optimal_strength': optimal_strength,
                'threshold_percentile': threshold_percentile,
                'cv_stability': np.std(cv_values) if cv_values is not None else None
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
                
                # Only include if pattern is reasonable (exclude complex and insufficient data)
                pattern = patterns.get(feature, {}).get('pattern_classification', 'unknown')
                if pattern not in ['complex', 'insufficient_data']:
                    percentile_features[percentile].append((feature, correlation))
            
            # Sort by correlation strength
            percentile_features[percentile].sort(key=lambda x: x[1], reverse=True)
        
        return percentile_features