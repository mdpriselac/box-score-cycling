import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import warnings


class CorrelationQualityAnalyzer:
    """
    Analyze the quality of correlation data across different percentiles.
    
    Provides metrics to determine which race_features_N percentiles 
    yield the most informative rider-feature correlations.
    """
    
    def __init__(self):
        """Initialize the correlation quality analyzer."""
        pass
    
    def analyze_percentile_quality(
        self, 
        correlation_results: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, float]]:
        """
        Analyze correlation quality across different percentiles.
        
        Args:
            correlation_results: List of results from CorrelationCalculator
            
        Returns:
            Dictionary mapping percentile names to quality metrics:
            {
                'race_features_100': {
                    'mean_abs_correlation': float,
                    'correlation_variance': float,
                    'non_null_rate': float,
                    'dynamic_range': float,
                    'signal_strength': float
                },
                ...
            }
        """
        # Filter out results with insufficient data
        valid_results = [
            r for r in correlation_results 
            if r['metadata']['n_races'] >= 5 and not r['metadata']['warnings']
        ]
        
        if not valid_results:
            raise ValueError("No valid correlation results found")
        
        # Extract percentile names from first result
        percentiles = list(valid_results[0]['feature_correlations'].keys())
        
        quality_metrics = {}
        
        for percentile in percentiles:
            metrics = self._calculate_percentile_metrics(valid_results, percentile)
            quality_metrics[percentile] = metrics
            
        return quality_metrics
    
    def _calculate_percentile_metrics(
        self, 
        results: List[Dict[str, Any]], 
        percentile: str
    ) -> Dict[str, float]:
        """Calculate quality metrics for a specific percentile."""
        
        # Extract all correlations for this percentile
        all_correlations = []
        feature_correlation_lists = defaultdict(list)
        
        for result in results:
            if percentile in result['feature_correlations']:
                correlations = result['feature_correlations'][percentile]
                
                for feature, corr in correlations.items():
                    if corr is not None and not np.isnan(corr):
                        all_correlations.append(abs(corr))
                        feature_correlation_lists[feature].append(corr)
        
        if not all_correlations:
            return {
                'mean_abs_correlation': 0.0,
                'correlation_variance': 0.0,
                'non_null_rate': 0.0,
                'dynamic_range': 0.0,
                'signal_strength': 0.0,
                'feature_coverage': 0.0
            }
        
        # Calculate total possible correlations
        total_possible = sum(
            len(result['feature_correlations'].get(percentile, {})) 
            for result in results
        )
        
        # Calculate metrics
        mean_abs_corr = np.mean(all_correlations)
        correlation_variance = np.var(all_correlations)
        non_null_rate = len(all_correlations) / max(total_possible, 1)
        dynamic_range = np.max(all_correlations) - np.min(all_correlations)
        
        # Signal strength: combination of mean strength and consistency
        signal_strength = mean_abs_corr * (1 + correlation_variance)
        
        # Feature coverage: how many features have correlations from multiple riders
        feature_coverage = sum(
            1 for feature_corrs in feature_correlation_lists.values() 
            if len(feature_corrs) >= 3
        ) / max(len(feature_correlation_lists), 1)
        
        return {
            'mean_abs_correlation': mean_abs_corr,
            'correlation_variance': correlation_variance,
            'non_null_rate': non_null_rate,
            'dynamic_range': dynamic_range,
            'signal_strength': signal_strength,
            'feature_coverage': feature_coverage
        }
    
    def analyze_feature_quality(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Analyze quality metrics for individual features within a percentile.
        
        Args:
            correlation_results: List of correlation results
            percentile: Specific percentile to analyze (e.g., 'race_features_100')
            
        Returns:
            Dictionary mapping feature names to quality metrics
        """
        feature_data = defaultdict(list)
        
        # Collect correlations for each feature
        for result in correlation_results:
            if (result['metadata']['n_races'] >= 5 and 
                not result['metadata']['warnings'] and
                percentile in result['feature_correlations']):
                
                correlations = result['feature_correlations'][percentile]
                
                for feature, corr in correlations.items():
                    if corr is not None and not np.isnan(corr):
                        feature_data[feature].append(corr)
        
        feature_metrics = {}
        
        for feature, correlations in feature_data.items():
            if len(correlations) >= 3:  # Need minimum sample
                abs_correlations = [abs(c) for c in correlations]
                
                feature_metrics[feature] = {
                    'mean_abs_correlation': np.mean(abs_correlations),
                    'correlation_std': np.std(correlations),
                    'sample_size': len(correlations),
                    'dynamic_range': np.max(correlations) - np.min(correlations),
                    'discriminative_power': np.std(correlations) * np.mean(abs_correlations)
                }
        
        return feature_metrics
    
    def rank_percentiles(
        self, 
        quality_metrics: Dict[str, Dict[str, float]],
        weights: Dict[str, float] = None
    ) -> List[Tuple[str, float]]:
        """
        Rank percentiles by overall quality score.
        
        Args:
            quality_metrics: Output from analyze_percentile_quality
            weights: Optional weights for different metrics
            
        Returns:
            List of (percentile_name, score) tuples sorted by score (descending)
        """
        if weights is None:
            weights = {
                'mean_abs_correlation': 0.3,
                'correlation_variance': 0.2,
                'non_null_rate': 0.2,
                'dynamic_range': 0.15,
                'signal_strength': 0.1,
                'feature_coverage': 0.05
            }
        
        percentile_scores = []
        
        # Normalize metrics across percentiles for fair comparison
        all_metrics = {}
        for metric in weights.keys():
            values = [
                metrics.get(metric, 0) 
                for metrics in quality_metrics.values()
            ]
            if values and max(values) > 0:
                all_metrics[metric] = {
                    'min': min(values),
                    'max': max(values),
                    'range': max(values) - min(values)
                }
            else:
                all_metrics[metric] = {'min': 0, 'max': 1, 'range': 1}
        
        for percentile, metrics in quality_metrics.items():
            score = 0
            
            for metric, weight in weights.items():
                value = metrics.get(metric, 0)
                # Normalize to 0-1 range
                if all_metrics[metric]['range'] > 0:
                    normalized = (value - all_metrics[metric]['min']) / all_metrics[metric]['range']
                else:
                    normalized = 0
                score += weight * normalized
            
            percentile_scores.append((percentile, score))
        
        return sorted(percentile_scores, key=lambda x: x[1], reverse=True)
    
    def rank_features(
        self, 
        feature_metrics: Dict[str, Dict[str, float]],
        weights: Dict[str, float] = None
    ) -> List[Tuple[str, float]]:
        """
        Rank features by overall quality score.
        
        Args:
            feature_metrics: Output from analyze_feature_quality
            weights: Optional weights for different metrics
            
        Returns:
            List of (feature_name, score) tuples sorted by score (descending)
        """
        if weights is None:
            weights = {
                'mean_abs_correlation': 0.4,
                'discriminative_power': 0.3,
                'sample_size': 0.1,
                'dynamic_range': 0.2
            }
        
        feature_scores = []
        
        # Normalize metrics
        all_metrics = {}
        for metric in weights.keys():
            values = [
                metrics.get(metric, 0) 
                for metrics in feature_metrics.values()
            ]
            if values and max(values) > 0:
                all_metrics[metric] = {
                    'min': min(values),
                    'max': max(values),
                    'range': max(values) - min(values)
                }
            else:
                all_metrics[metric] = {'min': 0, 'max': 1, 'range': 1}
        
        for feature, metrics in feature_metrics.items():
            score = 0
            
            for metric, weight in weights.items():
                value = metrics.get(metric, 0)
                # Normalize to 0-1 range
                if all_metrics[metric]['range'] > 0:
                    normalized = (value - all_metrics[metric]['min']) / all_metrics[metric]['range']
                else:
                    normalized = 0
                score += weight * normalized
            
            feature_scores.append((feature, score))
        
        return sorted(feature_scores, key=lambda x: x[1], reverse=True)
    
    def generate_summary_report(
        self, 
        correlation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary report of correlation quality analysis.
        
        Args:
            correlation_results: List of correlation results
            
        Returns:
            Dictionary containing complete analysis summary
        """
        # Analyze percentile quality
        percentile_quality = self.analyze_percentile_quality(correlation_results)
        percentile_rankings = self.rank_percentiles(percentile_quality)
        
        # Analyze top 3 percentiles in detail
        top_percentiles = [p[0] for p in percentile_rankings[:3]]
        feature_analyses = {}
        
        for percentile in top_percentiles:
            feature_metrics = self.analyze_feature_quality(correlation_results, percentile)
            feature_rankings = self.rank_features(feature_metrics)
            feature_analyses[percentile] = {
                'metrics': feature_metrics,
                'rankings': feature_rankings[:20]  # Top 20 features
            }
        
        return {
            'summary': {
                'total_rider_results': len(correlation_results),
                'valid_results': len([
                    r for r in correlation_results 
                    if r['metadata']['n_races'] >= 5 and not r['metadata']['warnings']
                ]),
                'percentiles_analyzed': list(percentile_quality.keys())
            },
            'percentile_analysis': {
                'quality_metrics': percentile_quality,
                'rankings': percentile_rankings
            },
            'feature_analysis': feature_analyses,
            'recommendations': {
                'best_percentile': percentile_rankings[0][0] if percentile_rankings else None,
                'top_3_percentiles': [p[0] for p in percentile_rankings[:3]],
                'recommended_features': {
                    percentile: analysis['rankings'][:10] 
                    for percentile, analysis in feature_analyses.items()
                }
            }
        }