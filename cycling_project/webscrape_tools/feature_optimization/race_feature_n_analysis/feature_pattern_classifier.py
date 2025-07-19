import numpy as np
import pandas as pd
from scipy import stats
import sqlite3
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .feature_variability_analyzer import FeatureVariabilityAnalyzer
from .monotonicity_analyzer import MonotonicityAnalyzer


@dataclass
class FeaturePattern:
    is_stable: bool
    shows_dilution: bool
    shows_concentration: bool
    has_threshold: bool
    threshold_n: Optional[int]
    bimodality_pattern: Dict[int, bool]
    primary_pattern: str


class FeaturePatternClassifier:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        self.variability_analyzer = FeatureVariabilityAnalyzer(db_path)
        self.monotonicity_analyzer = MonotonicityAnalyzer(db_path)
    
    def get_feature_stats_across_n(self, feature_name: str) -> Dict[int, Dict[str, float]]:
        stats_by_n = {}
        quoted_name = self.variability_analyzer.quote_column(feature_name)
        
        for n in self.n_levels:
            table_name = f"race_features_{n}"
            query = f"""
            SELECT 
                {quoted_name} as value
            FROM {table_name}
            WHERE {quoted_name} IS NOT NULL
            """
            
            conn = self.variability_analyzer.get_connection()
            df = pd.read_sql_query(query, conn)
                
            if len(df) > 0:
                values = df['value'].values
                
                # Calculate entropy
                hist, _ = np.histogram(values, bins=20)
                hist_normalized = hist / np.sum(hist) + 1e-10
                entropy = -np.sum(hist_normalized * np.log(hist_normalized))
                
                stats_by_n[n] = {
                    'mean': np.mean(values),
                    'variance': np.var(values),
                    'std': np.std(values),
                    'cv': np.std(values) / np.mean(values) if np.mean(values) != 0 else 0,
                    'entropy': entropy,
                    'skewness': stats.skew(values),
                    'kurtosis': stats.kurtosis(values)
                }
        
        return stats_by_n
    
    def calculate_trend(self, values: List[float]) -> Dict[str, float]:
        if len(values) < 2:
            return {'slope': 0, 'r2': 0}
        
        x = list(range(len(values)))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, values)
        
        return {
            'slope': slope,
            'r2': r_value ** 2,
            'p_value': p_value
        }
    
    def detect_threshold(self, stats_by_n: Dict[int, Dict[str, float]]) -> Optional[int]:
        n_values = sorted(stats_by_n.keys())
        
        if len(n_values) < 3:
            return None
        
        # Look for sudden changes in mean or variance
        means = [stats_by_n[n]['mean'] for n in n_values]
        variances = [stats_by_n[n]['variance'] for n in n_values]
        
        # Calculate relative changes
        mean_changes = []
        var_changes = []
        
        for i in range(1, len(n_values)):
            mean_change = abs(means[i] - means[i-1]) / abs(means[i-1]) if means[i-1] != 0 else 0
            var_change = abs(variances[i] - variances[i-1]) / abs(variances[i-1]) if variances[i-1] != 0 else 0
            
            mean_changes.append((n_values[i], mean_change))
            var_changes.append((n_values[i], var_change))
        
        # Find maximum change
        max_mean_change = max(mean_changes, key=lambda x: x[1])
        max_var_change = max(var_changes, key=lambda x: x[1])
        
        # If change is significant (> 30%), consider it a threshold
        threshold_candidates = []
        if max_mean_change[1] > 0.3:
            threshold_candidates.append(max_mean_change[0])
        if max_var_change[1] > 0.3:
            threshold_candidates.append(max_var_change[0])
        
        if threshold_candidates:
            # Return the most common threshold or the earliest one
            return min(threshold_candidates)
        
        return None
    
    def test_bimodality(self, feature_name: str, n: int) -> bool:
        values = self.variability_analyzer.get_feature_values(feature_name, n)
        
        if len(values) < 30:
            return False
        
        # Hartigan's dip test approximation
        # For simplicity, we'll use a heuristic based on the histogram
        hist, bin_edges = np.histogram(values, bins=30)
        
        # Find peaks in the histogram
        peaks = []
        for i in range(1, len(hist) - 1):
            if hist[i] > hist[i-1] and hist[i] > hist[i+1]:
                peaks.append(i)
        
        # If we have 2 or more prominent peaks with a valley between them
        if len(peaks) >= 2:
            # Check if there's a significant valley between the two highest peaks
            peak_values = [(i, hist[i]) for i in peaks]
            peak_values.sort(key=lambda x: x[1], reverse=True)
            
            if len(peak_values) >= 2:
                peak1_idx, peak1_val = peak_values[0]
                peak2_idx, peak2_val = peak_values[1]
                
                # Check valley between peaks
                min_idx = min(peak1_idx, peak2_idx)
                max_idx = max(peak1_idx, peak2_idx)
                
                if max_idx - min_idx > 1:
                    valley_min = min(hist[min_idx+1:max_idx])
                    # If valley is less than 60% of the smaller peak, consider it bimodal
                    if valley_min < 0.6 * min(peak1_val, peak2_val):
                        return True
        
        return False
    
    def determine_primary_pattern(self, is_stable: bool, shows_dilution: bool, 
                                 shows_concentration: bool, threshold_n: Optional[int]) -> str:
        if is_stable:
            return "stable"
        elif shows_dilution:
            return "dilution"
        elif shows_concentration:
            return "concentration"
        elif threshold_n is not None:
            return f"threshold_at_{threshold_n}"
        else:
            return "complex"
    
    def classify_feature_behavior(self, feature_name: str) -> FeaturePattern:
        # Get feature statistics across N
        stats_by_n = self.get_feature_stats_across_n(feature_name)
        
        if len(stats_by_n) < 2:
            return FeaturePattern(False, False, False, False, None, {}, "unknown")
        
        # Pattern 1: Stable features (low variation across N)
        cv_values = [stats_by_n[n]['cv'] for n in sorted(stats_by_n.keys())]
        is_stable = np.std(cv_values) < 0.1
        
        # Pattern 2: Dilution features (variance increases with N)
        variance_values = [stats_by_n[n]['variance'] for n in sorted(stats_by_n.keys())]
        variance_trend = self.calculate_trend(variance_values)
        shows_dilution = variance_trend['slope'] > 0 and variance_trend['r2'] > 0.7
        
        # Pattern 3: Concentration features (become more concentrated as N increases)
        entropy_values = [stats_by_n[n]['entropy'] for n in sorted(stats_by_n.keys())]
        entropy_trend = self.calculate_trend(entropy_values)
        shows_concentration = entropy_trend['slope'] < 0 and entropy_trend['r2'] > 0.7
        
        # Pattern 4: Threshold features (sudden change at specific N)
        threshold_n = self.detect_threshold(stats_by_n)
        
        # Pattern 5: Bimodal features
        bimodality_by_n = {}
        for n in [30, 50, 70, 90]:
            try:
                bimodality_by_n[n] = self.test_bimodality(feature_name, n)
            except:
                bimodality_by_n[n] = False
        
        primary_pattern = self.determine_primary_pattern(is_stable, shows_dilution, 
                                                        shows_concentration, threshold_n)
        
        return FeaturePattern(
            is_stable=is_stable,
            shows_dilution=shows_dilution,
            shows_concentration=shows_concentration,
            has_threshold=threshold_n is not None,
            threshold_n=threshold_n,
            bimodality_pattern=bimodality_by_n,
            primary_pattern=primary_pattern
        )
    
    def analyze_pattern_transitions(self, feature_name: str) -> Dict[str, any]:
        stats_by_n = self.get_feature_stats_across_n(feature_name)
        
        transitions = {
            'skewness_transition': [],
            'kurtosis_transition': [],
            'cv_transition': []
        }
        
        n_values = sorted(stats_by_n.keys())
        
        for i in range(len(n_values) - 1):
            n1, n2 = n_values[i], n_values[i+1]
            
            # Track sign changes in skewness
            if stats_by_n[n1]['skewness'] * stats_by_n[n2]['skewness'] < 0:
                transitions['skewness_transition'].append(f"{n1}->{n2}")
            
            # Track significant changes in kurtosis
            kurt_change = abs(stats_by_n[n2]['kurtosis'] - stats_by_n[n1]['kurtosis'])
            if kurt_change > 1.0:
                transitions['kurtosis_transition'].append(f"{n1}->{n2}")
            
            # Track CV jumps
            cv_change = abs(stats_by_n[n2]['cv'] - stats_by_n[n1]['cv'])
            if cv_change > 0.2:
                transitions['cv_transition'].append(f"{n1}->{n2}")
        
        return transitions
    
    def classify_all_features(self) -> Dict[str, FeaturePattern]:
        results = {}
        
        for feature in self.variability_analyzer.feature_columns:
            print(f"Classifying pattern for {feature}...")
            results[feature] = self.classify_feature_behavior(feature)
        
        return results
    
    def group_features_by_pattern(self, classifications: Dict[str, FeaturePattern]) -> Dict[str, List[str]]:
        pattern_groups = {
            'stable': [],
            'dilution': [],
            'concentration': [],
            'threshold': [],
            'bimodal': [],
            'complex': []
        }
        
        for feature, pattern in classifications.items():
            # Primary classification
            if pattern.primary_pattern.startswith('threshold'):
                pattern_groups['threshold'].append(feature)
            else:
                pattern_groups[pattern.primary_pattern].append(feature)
            
            # Secondary classification for bimodal features
            if any(pattern.bimodality_pattern.values()):
                pattern_groups['bimodal'].append(feature)
        
        return pattern_groups
    
    def __del__(self):
        # Close connections in sub-analyzers
        if hasattr(self, 'variability_analyzer'):
            self.variability_analyzer.close_connection()
        if hasattr(self, 'monotonicity_analyzer'):
            self.monotonicity_analyzer.close_connection()