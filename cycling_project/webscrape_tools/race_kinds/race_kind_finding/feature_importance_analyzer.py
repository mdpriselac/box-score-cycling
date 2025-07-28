"""
Feature Importance Analyzer for Clustering Results

This module provides sophisticated analysis of feature importance for each cluster,
identifying natural tiers of discriminatory features and their statistical significance.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from scipy import stats
import json


@dataclass
class FeatureImportance:
    """Container for feature importance metrics"""
    feature_name: str
    cluster_mean: float
    population_mean: float
    other_clusters_mean: float
    std_from_population: float
    std_from_others: float
    effect_size_population: float  # Cohen's d vs population
    effect_size_others: float     # Cohen's d vs other clusters
    statistical_significance: float  # p-value from t-test
    importance_score: float       # Combined importance metric
    tier: str
    interpretation: str


class FeatureImportanceAnalyzer:
    """Analyze feature importance for clustering results with natural tier identification"""
    
    def __init__(self, clustering_data: pd.DataFrame, feature_names: List[str]):
        """
        Initialize analyzer with clustering data
        
        Args:
            clustering_data: DataFrame with cluster assignments and features
            feature_names: List of feature column names to analyze
        """
        self.data = clustering_data
        self.feature_names = feature_names
        self.population_stats = self._calculate_population_stats()
        
    def _calculate_population_stats(self) -> Dict[str, Dict[str, float]]:
        """Calculate population-level statistics for all features"""
        stats = {}
        for feature in self.feature_names:
            if feature in self.data.columns:
                feature_data = self.data[feature].dropna()
                stats[feature] = {
                    'mean': feature_data.mean(),
                    'std': feature_data.std(),
                    'median': feature_data.median(),
                    'q25': feature_data.quantile(0.25),
                    'q75': feature_data.quantile(0.75)
                }
        return stats
    
    def _calculate_effect_size(self, group1: np.ndarray, group2: np.ndarray) -> float:
        """Calculate Cohen's d effect size between two groups"""
        if len(group1) == 0 or len(group2) == 0:
            return 0.0
        
        mean1, mean2 = np.mean(group1), np.mean(group2)
        std1, std2 = np.std(group1, ddof=1), np.std(group2, ddof=1)
        n1, n2 = len(group1), len(group2)
        
        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        
        if pooled_std == 0:
            return 0.0
        
        return abs(mean1 - mean2) / pooled_std
    
    def _calculate_statistical_significance(self, cluster_data: np.ndarray, 
                                          other_data: np.ndarray) -> float:
        """Calculate statistical significance using t-test"""
        if len(cluster_data) < 2 or len(other_data) < 2:
            return 1.0
        
        try:
            _, p_value = stats.ttest_ind(cluster_data, other_data, equal_var=False)
            return p_value
        except:
            return 1.0
    
    def _calculate_importance_score(self, effect_size_pop: float, effect_size_others: float,
                                  p_value: float, cluster_size_ratio: float) -> float:
        """
        Calculate combined importance score
        
        Combines effect sizes, statistical significance, and cluster representativeness
        """
        # Significance weight (higher for more significant)
        sig_weight = max(0, -np.log10(max(p_value, 1e-10)))
        
        # Effect size weight (geometric mean of both effect sizes)
        effect_weight = np.sqrt(effect_size_pop * effect_size_others)
        
        # Size adjustment (slight penalty for very small clusters)
        size_adjustment = min(1.0, cluster_size_ratio / 0.05)  # Penalty if <5% of data
        
        return effect_weight * (1 + sig_weight * 0.1) * size_adjustment
    
    def _find_natural_tiers(self, importance_scores: List[float]) -> List[float]:
        """
        Find natural breakpoints in importance scores using multiple methods
        
        Returns list of breakpoints in descending order
        """
        if len(importance_scores) < 3:
            return []
        
        scores = np.array(sorted(importance_scores, reverse=True))
        
        # Method 1: Look for large gaps between consecutive scores
        gaps = np.diff(scores)
        gap_sizes = np.abs(gaps)
        
        # Find gaps larger than 1.5 * median gap
        median_gap = np.median(gap_sizes) if len(gap_sizes) > 0 else 0
        large_gap_threshold = median_gap * 1.5
        large_gaps = gap_sizes > large_gap_threshold
        
        breakpoints = []
        
        if np.any(large_gaps):
            # Use gap-based method
            gap_indices = np.where(large_gaps)[0]
            for gap_idx in gap_indices[:3]:  # Use up to 3 major gaps
                breakpoints.append(float(scores[gap_idx + 1]))
        
        # Method 2: Statistical breakpoints based on score distribution
        if len(breakpoints) == 0:
            score_std = np.std(scores)
            score_mean = np.mean(scores)
            
            # Define breakpoints based on standard deviations from mean
            potential_breaks = [
                score_mean + score_std,      # High importance
                score_mean,                   # Medium importance  
                score_mean - 0.5 * score_std # Low importance
            ]
            
            breakpoints = [bp for bp in potential_breaks if np.min(scores) < bp < np.max(scores)]
        
        # Method 3: Quantile-based as fallback
        if len(breakpoints) == 0:
            breakpoints = [
                np.percentile(scores, 75),
                np.percentile(scores, 50),
                np.percentile(scores, 25)
            ]
        
        # Remove breakpoints that are too close together
        final_breakpoints = []
        for bp in sorted(breakpoints, reverse=True):
            if not final_breakpoints or (final_breakpoints[-1] - bp) > (np.std(scores) * 0.2):
                final_breakpoints.append(bp)
        
        return final_breakpoints
    
    def _assign_tier(self, importance_score: float, breakpoints: List[float]) -> str:
        """Assign tier based on importance score and breakpoints"""
        tier_names = ['Critical', 'High', 'Moderate', 'Low', 'Minimal']
        
        tier_level = 0
        for bp in breakpoints:
            if importance_score >= bp:
                break
            tier_level += 1
        
        return tier_names[min(tier_level, len(tier_names) - 1)]
    
    def _generate_interpretation(self, feature_importance: FeatureImportance) -> str:
        """Generate human-readable interpretation of feature importance"""
        cluster_val = feature_importance.cluster_mean
        pop_val = feature_importance.population_mean
        others_val = feature_importance.other_clusters_mean
        
        # Determine direction and magnitude
        pop_diff_pct = ((cluster_val - pop_val) / abs(pop_val)) * 100 if pop_val != 0 else 0
        others_diff_pct = ((cluster_val - others_val) / abs(others_val)) * 100 if others_val != 0 else 0
        
        # Direction
        direction_pop = "higher" if cluster_val > pop_val else "lower"
        direction_others = "higher" if cluster_val > others_val else "lower"
        
        # Magnitude description
        def magnitude_desc(pct):
            abs_pct = abs(pct)
            if abs_pct > 200: return "extremely"
            elif abs_pct > 100: return "dramatically"
            elif abs_pct > 50: return "substantially"
            elif abs_pct > 25: return "moderately"
            elif abs_pct > 10: return "slightly"
            else: return "marginally"
        
        pop_magnitude = magnitude_desc(pop_diff_pct)
        others_magnitude = magnitude_desc(others_diff_pct)
        
        # Statistical confidence
        sig_level = feature_importance.statistical_significance
        confidence = "highly significant" if sig_level < 0.001 else \
                    "significant" if sig_level < 0.01 else \
                    "marginally significant" if sig_level < 0.05 else \
                    "not significant"
        
        interpretation = f"{pop_magnitude} {direction_pop} than population average " \
                        f"({pop_diff_pct:+.1f}%), {others_magnitude} {direction_others} " \
                        f"than other clusters ({others_diff_pct:+.1f}%) - {confidence}"
        
        return interpretation
    
    def analyze_cluster_features(self, cluster_id: int) -> List[FeatureImportance]:
        """
        Analyze feature importance for a specific cluster
        
        Returns list of FeatureImportance objects sorted by importance
        """
        if 'cluster' not in self.data.columns:
            raise ValueError("Data must contain 'cluster' column")
        
        cluster_data = self.data[self.data['cluster'] == cluster_id]
        other_clusters_data = self.data[self.data['cluster'] != cluster_id]
        
        if len(cluster_data) == 0:
            return []
        
        cluster_size_ratio = len(cluster_data) / len(self.data)
        feature_importances = []
        
        for feature in self.feature_names:
            if feature not in self.data.columns:
                continue
            
            # Get feature data for cluster and comparisons
            cluster_feature = cluster_data[feature].dropna()
            other_clusters_feature = other_clusters_data[feature].dropna()
            population_feature = self.data[feature].dropna()
            
            if len(cluster_feature) == 0:
                continue
            
            # Calculate means
            cluster_mean = cluster_feature.mean()
            population_mean = self.population_stats[feature]['mean']
            other_clusters_mean = other_clusters_feature.mean() if len(other_clusters_feature) > 0 else population_mean
            
            # Calculate effect sizes
            effect_size_pop = self._calculate_effect_size(cluster_feature.values, population_feature.values)
            effect_size_others = self._calculate_effect_size(cluster_feature.values, other_clusters_feature.values)
            
            # Statistical significance
            p_value = self._calculate_statistical_significance(cluster_feature.values, other_clusters_feature.values)
            
            # Combined importance score
            importance_score = self._calculate_importance_score(
                effect_size_pop, effect_size_others, p_value, cluster_size_ratio
            )
            
            # Standard deviations from means
            pop_std = self.population_stats[feature]['std']
            std_from_pop = (cluster_mean - population_mean) / pop_std if pop_std > 0 else 0
            
            others_std = other_clusters_feature.std() if len(other_clusters_feature) > 1 else pop_std
            std_from_others = (cluster_mean - other_clusters_mean) / others_std if others_std > 0 else 0
            
            feature_importance = FeatureImportance(
                feature_name=feature,
                cluster_mean=cluster_mean,
                population_mean=population_mean,
                other_clusters_mean=other_clusters_mean,
                std_from_population=std_from_pop,
                std_from_others=std_from_others,
                effect_size_population=effect_size_pop,
                effect_size_others=effect_size_others,
                statistical_significance=p_value,
                importance_score=importance_score,
                tier="",  # Will be assigned later
                interpretation=""  # Will be generated later
            )
            
            feature_importances.append(feature_importance)
        
        # Sort by importance score
        feature_importances.sort(key=lambda x: x.importance_score, reverse=True)
        
        # Find natural tiers
        importance_scores = [fi.importance_score for fi in feature_importances if fi.importance_score > 0]
        breakpoints = self._find_natural_tiers(importance_scores)
        
        # Assign tiers and generate interpretations
        for fi in feature_importances:
            fi.tier = self._assign_tier(fi.importance_score, breakpoints)
            fi.interpretation = self._generate_interpretation(fi)
        
        return feature_importances
    
    def analyze_all_clusters(self) -> Dict[int, List[FeatureImportance]]:
        """Analyze feature importance for all clusters"""
        results = {}
        
        unique_clusters = sorted(self.data['cluster'].unique())
        for cluster_id in unique_clusters:
            if cluster_id != -1:  # Skip noise cluster for DBSCAN
                results[cluster_id] = self.analyze_cluster_features(cluster_id)
        
        return results
    
    def generate_summary_report(self, cluster_analyses: Dict[int, List[FeatureImportance]]) -> str:
        """Generate a summary report of feature importance across all clusters"""
        report = []
        report.append("FEATURE IMPORTANCE ANALYSIS SUMMARY")
        report.append("=" * 50)
        
        for cluster_id, features in cluster_analyses.items():
            report.append(f"\nCLUSTER {cluster_id}")
            report.append("-" * 20)
            
            # Group by tier
            tier_groups = {}
            for feature in features:
                if feature.tier not in tier_groups:
                    tier_groups[feature.tier] = []
                tier_groups[feature.tier].append(feature)
            
            # Report by tier
            tier_order = ['Critical', 'High', 'Moderate', 'Low', 'Minimal']
            for tier in tier_order:
                if tier in tier_groups:
                    report.append(f"\n{tier} Importance ({len(tier_groups[tier])} features):")
                    for feature in tier_groups[tier]:
                        report.append(f"  • {feature.feature_name}")
                        report.append(f"    Score: {feature.importance_score:.3f}")
                        report.append(f"    {feature.interpretation}")
                        report.append("")
        
        return "\n".join(report)
    
    def export_results(self, cluster_analyses: Dict[int, List[FeatureImportance]], 
                      output_path: str) -> None:
        """Export results to JSON file"""
        export_data = {}
        
        for cluster_id, features in cluster_analyses.items():
            export_data[str(cluster_id)] = []
            for feature in features:
                export_data[str(cluster_id)].append({
                    'feature_name': feature.feature_name,
                    'cluster_mean': feature.cluster_mean,
                    'population_mean': feature.population_mean,
                    'other_clusters_mean': feature.other_clusters_mean,
                    'effect_size_population': feature.effect_size_population,
                    'effect_size_others': feature.effect_size_others,
                    'statistical_significance': feature.statistical_significance,
                    'importance_score': feature.importance_score,
                    'tier': feature.tier,
                    'interpretation': feature.interpretation
                })
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)


def demonstrate_usage():
    """Demonstrate how to use the FeatureImportanceAnalyzer"""
    # This would typically be called from the evaluation scripts
    # Example usage:
    
    # Load your clustering data
    # data = pd.read_csv('clustering_data_with_features.csv')
    # feature_names = ['feature1', 'feature2', 'feature3', ...]
    
    # analyzer = FeatureImportanceAnalyzer(data, feature_names)
    # all_analyses = analyzer.analyze_all_clusters()
    
    # Generate reports
    # summary_report = analyzer.generate_summary_report(all_analyses)
    # print(summary_report)
    
    # Export results
    # analyzer.export_results(all_analyses, 'feature_importance_results.json')
    
    pass


if __name__ == "__main__":
    demonstrate_usage()