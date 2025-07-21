"""
Quality scorer module for correlation feature analysis.

Calculates quality scores and assigns features to tiers.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List


class CorrelationQualityScorer:
    """Calculates quality scores and assigns tiers"""
    
    def __init__(self):
        """
        Initialize quality scorer.
        Uses equal weighting for all components following race feature N analysis approach.
        """
        # No longer using arbitrary weights - equal importance for all components
        pass
    
    def calculate_quality_score(self, feature_pattern: Dict, 
                               avg_null_percentage: float,
                               trend_data: Dict = None) -> Dict:
        """
        Calculate multi-component quality score for a feature following race feature N approach.
        
        Components:
        1. Correlation Strength Score - Maximum predictive power
        2. Information Value Score - Discriminative ability and monotonicity
        3. Stability Score - Consistency across percentiles
        
        Args:
            feature_pattern: Pattern analysis results for the feature
            avg_null_percentage: Average percentage of NULL values
            trend_data: Trend analysis results (for monotonicity calculation)
            
        Returns:
            Dictionary with quality score components and overall score
        """
        # 1. Correlation Strength Score (akin to race feature N's strength component)
        optimal_strength = abs(feature_pattern.get('optimal_strength', 0))
        # Normalize to 0-1 range (correlations already in [-1, 1])
        correlation_strength_score = optimal_strength
        
        # 2. Information Value Score (combines discriminative power and monotonicity)
        # Discriminative power based on correlation range across percentiles
        correlation_range = feature_pattern.get('correlation_range', 0)
        discriminative_power = min(correlation_range * 2, 1.0)  # Scale to 0-1
        
        # Monotonicity score (how predictably correlation changes with percentile)
        if trend_data:
            # Use R² value from trend analysis as monotonicity measure
            monotonicity = trend_data.get('r_squared', 0)
        else:
            # Fallback: use inverse of coefficient of variation as proxy
            cv_stability = feature_pattern.get('cv_stability', 1.0)
            monotonicity = max(0, 1 - cv_stability)
        
        information_value_score = (discriminative_power + monotonicity) / 2
        
        # 3. Stability Score (consistency across percentiles)
        # Lower correlation_stability (std dev) means higher stability
        correlation_stability = feature_pattern.get('correlation_stability', 1.0)
        stability_score = max(0, 1 - (correlation_stability * 5))  # Scale for sensitivity
        
        # Overall quality score - equal weighting of three components
        overall_score = np.mean([
            correlation_strength_score,
            information_value_score,
            stability_score
        ])
        
        # Apply data availability penalty (similar to race feature N's approach)
        if avg_null_percentage > 0.5:
            overall_score *= (1 - avg_null_percentage)
        
        return {
            'overall_score': overall_score,
            'correlation_strength_score': correlation_strength_score,
            'information_value_score': information_value_score,
            'stability_score': stability_score,
            'discriminative_power': discriminative_power,
            'monotonicity': monotonicity,
            'data_availability': 1 - avg_null_percentage,
            'pattern': feature_pattern.get('pattern_classification', 'unknown'),
            'optimal_percentile': feature_pattern.get('optimal_percentile', 0),
            'optimal_strength': optimal_strength
        }
    
    def score_all_features(self, patterns: Dict[str, Dict], 
                          feature_null_stats: Dict[str, float],
                          trend_results: Dict[str, Dict] = None) -> Dict[str, Dict]:
        """
        Calculate quality scores for all features.
        
        Args:
            patterns: Pattern analysis results for all features
            feature_null_stats: Dictionary mapping features to avg null percentages
            trend_results: Trend analysis results for monotonicity calculation
            
        Returns:
            Dictionary mapping features to quality scores
        """
        quality_scores = {}
        
        for feature, pattern in patterns.items():
            avg_null_percentage = feature_null_stats.get(feature, 0)
            trend_data = trend_results.get(feature, {}) if trend_results else {}
            quality_scores[feature] = self.calculate_quality_score(
                pattern, avg_null_percentage, trend_data
            )
        
        return quality_scores
    
    def assign_quality_tiers(self, quality_scores: Dict[str, Dict], 
                           n_tiers: int = 3) -> Tuple[Dict[str, Dict], Dict[str, List[str]]]:
        """
        Assign features to quality tiers based on their scores.
        
        Args:
            quality_scores: Dictionary of quality scores by feature
            n_tiers: Number of tiers to create
            
        Returns:
            Tuple of (updated quality_scores with tier info, tier assignments)
        """
        # Sort features by overall score
        sorted_features = sorted(
            quality_scores.items(), 
            key=lambda x: x[1]['overall_score'], 
            reverse=True
        )
        
        # Calculate tier sizes
        n_features = len(sorted_features)
        base_tier_size = n_features // n_tiers
        remainder = n_features % n_tiers
        
        # Create tier sizes (distribute remainder to top tiers)
        tier_sizes = []
        for i in range(n_tiers):
            size = base_tier_size + (1 if i < remainder else 0)
            tier_sizes.append(size)
        
        # Assign tiers
        tiers = {}
        tier_names = []
        for i in range(n_tiers):
            tier_name = f'tier_{i+1}_{"high" if i == 0 else "medium" if i == 1 else "low"}_quality'
            tier_names.append(tier_name)
            tiers[tier_name] = []
        
        # Distribute features to tiers
        feature_idx = 0
        for tier_idx, tier_size in enumerate(tier_sizes):
            tier_name = tier_names[tier_idx]
            for _ in range(tier_size):
                if feature_idx < len(sorted_features):
                    feature_name = sorted_features[feature_idx][0]
                    tiers[tier_name].append(feature_name)
                    quality_scores[feature_name]['tier'] = tier_idx + 1
                    quality_scores[feature_name]['tier_name'] = tier_name
                    feature_idx += 1
        
        return quality_scores, tiers
    
    def get_tier_statistics(self, quality_scores: Dict[str, Dict], 
                          tiers: Dict[str, List[str]]) -> Dict[str, Dict]:
        """
        Calculate statistics for each quality tier.
        
        Args:
            quality_scores: Dictionary of quality scores
            tiers: Tier assignments
            
        Returns:
            Dictionary with statistics for each tier
        """
        tier_stats = {}
        
        for tier_name, features in tiers.items():
            if not features:
                continue
            
            scores = [quality_scores[f]['overall_score'] for f in features]
            strength_scores = [quality_scores[f]['strength_score'] for f in features]
            stability_scores = [quality_scores[f]['stability_score'] for f in features]
            availability_scores = [quality_scores[f]['availability_score'] for f in features]
            
            # Extract new scoring components
            correlation_strength_scores = [quality_scores[f].get('correlation_strength_score', 0) for f in features]
            information_value_scores = [quality_scores[f].get('information_value_score', 0) for f in features]
            
            tier_stats[tier_name] = {
                'feature_count': len(features),
                'avg_overall_score': np.mean(scores),
                'min_overall_score': np.min(scores),
                'max_overall_score': np.max(scores),
                'avg_correlation_strength': np.mean(correlation_strength_scores),
                'avg_information_value': np.mean(information_value_scores),
                'avg_stability': np.mean(stability_scores),
                'pattern_distribution': self._get_pattern_distribution(features, quality_scores)
            }
        
        return tier_stats
    
    def _get_pattern_distribution(self, features: List[str], 
                                quality_scores: Dict[str, Dict]) -> Dict[str, int]:
        """Get distribution of patterns within a tier"""
        pattern_counts = {}
        for feature in features:
            pattern = quality_scores[feature].get('pattern', 'unknown')
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        return pattern_counts
    
    def identify_top_features(self, quality_scores: Dict[str, Dict], 
                            criteria: List[str] = None, 
                            top_n: int = 10) -> Dict[str, List[str]]:
        """
        Identify top features by different criteria.
        
        Args:
            quality_scores: Dictionary of quality scores
            criteria: List of criteria to use (default: ['overall', 'strength', 'stability'])
            top_n: Number of top features to return per criterion
            
        Returns:
            Dictionary mapping criteria to lists of top features
        """
        if criteria is None:
            criteria = ['overall', 'correlation_strength', 'information_value', 'stability']
        
        top_features = {}
        
        for criterion in criteria:
            if criterion == 'overall':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['overall_score'],
                    reverse=True
                )
            elif criterion == 'correlation_strength':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['correlation_strength_score'],
                    reverse=True
                )
            elif criterion == 'information_value':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['information_value_score'],
                    reverse=True
                )
            elif criterion == 'stability':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['stability_score'],
                    reverse=True
                )
            else:
                continue
            
            top_features[criterion] = [f[0] for f in sorted_features[:top_n]]
        
        return top_features