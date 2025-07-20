"""
Quality scorer module for correlation feature analysis.

Calculates quality scores and assigns features to tiers.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List


class CorrelationQualityScorer:
    """Calculates quality scores and assigns tiers"""
    
    def __init__(self, quality_weights: Dict[str, float] = None):
        """
        Initialize quality scorer with weights.
        
        Args:
            quality_weights: Dictionary of component weights (default: strength=0.4, stability=0.3, availability=0.3)
        """
        self.quality_weights = quality_weights or {
            'strength': 0.4,
            'stability': 0.3,
            'availability': 0.3
        }
    
    def calculate_quality_score(self, feature_pattern: Dict, 
                               avg_null_percentage: float) -> Dict:
        """
        Calculate multi-component quality score for a feature.
        
        Args:
            feature_pattern: Pattern analysis results for the feature
            avg_null_percentage: Average percentage of NULL values
            
        Returns:
            Dictionary with quality score components and overall score
        """
        # Strength score based on optimal correlation strength
        optimal_strength = feature_pattern.get('optimal_strength', 0)
        strength_score = min(optimal_strength * 2, 1.0)  # Scale to 0-1
        
        # Stability score
        stability_score = feature_pattern.get('correlation_stability', 0)
        
        # Availability score (inverse of null percentage)
        availability_score = 1 - avg_null_percentage
        
        # Pattern-based penalty
        pattern_class = feature_pattern.get('pattern_classification', 'unknown')
        if pattern_class == 'highly_variable':
            pattern_penalty = 0.7
        elif pattern_class == 'insufficient_data':
            pattern_penalty = 0.5
        elif pattern_class == 'complex':
            pattern_penalty = 0.9
        else:
            pattern_penalty = 1.0
        
        # Calculate weighted overall score
        overall_score = (
            self.quality_weights['strength'] * strength_score + 
            self.quality_weights['stability'] * stability_score + 
            self.quality_weights['availability'] * availability_score
        ) * pattern_penalty
        
        return {
            'overall_score': overall_score,
            'strength_score': strength_score,
            'stability_score': stability_score,
            'availability_score': availability_score,
            'pattern_penalty': pattern_penalty,
            'pattern': pattern_class,
            'optimal_percentile': feature_pattern.get('optimal_percentile', 0)
        }
    
    def score_all_features(self, patterns: Dict[str, Dict], 
                          feature_null_stats: Dict[str, float]) -> Dict[str, Dict]:
        """
        Calculate quality scores for all features.
        
        Args:
            patterns: Pattern analysis results for all features
            feature_null_stats: Dictionary mapping features to avg null percentages
            
        Returns:
            Dictionary mapping features to quality scores
        """
        quality_scores = {}
        
        for feature, pattern in patterns.items():
            avg_null_percentage = feature_null_stats.get(feature, 0)
            quality_scores[feature] = self.calculate_quality_score(pattern, avg_null_percentage)
        
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
            
            tier_stats[tier_name] = {
                'feature_count': len(features),
                'avg_overall_score': np.mean(scores),
                'min_overall_score': np.min(scores),
                'max_overall_score': np.max(scores),
                'avg_strength': np.mean(strength_scores),
                'avg_stability': np.mean(stability_scores),
                'avg_availability': np.mean(availability_scores),
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
            criteria = ['overall', 'strength', 'stability']
        
        top_features = {}
        
        for criterion in criteria:
            if criterion == 'overall':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['overall_score'],
                    reverse=True
                )
            elif criterion == 'strength':
                sorted_features = sorted(
                    quality_scores.items(),
                    key=lambda x: x[1]['strength_score'],
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