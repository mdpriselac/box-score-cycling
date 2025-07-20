# correlation_quality_analyzer.py

import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

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

class CorrelationQualityAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.percentiles = [30, 40, 50, 60, 70, 80, 90, 100]
        self.correlation_types = ['all_races', 'same_type', 'stage_one_days']
        
    def analyze_all_features(self, correlation_type: str = 'all_races') -> pd.DataFrame:
        """Get comprehensive statistics for all features"""
        
        print(f"Analyzing correlation data for type: {correlation_type}")
        
        # Query to get all correlation data efficiently
        query = """
        WITH feature_data AS (
            SELECT 
                feature_name,
                percentile,
                correlation_value,
                COUNT(*) OVER (PARTITION BY feature_name, percentile) as total_count,
                SUM(CASE WHEN correlation_value IS NULL THEN 1 ELSE 0 END) 
                    OVER (PARTITION BY feature_name, percentile) as null_count
            FROM rider_correlations_denorm
            WHERE correlation_type = ?
        )
        SELECT * FROM feature_data
        WHERE correlation_value IS NOT NULL
        ORDER BY feature_name, percentile
        """
        
        # Load data in chunks to manage memory
        chunk_size = 100000
        chunks = []
        
        for chunk in pd.read_sql_query(query, self.conn, params=[correlation_type], chunksize=chunk_size):
            chunks.append(chunk)
            
        df = pd.concat(chunks, ignore_index=True)
        
        # Calculate statistics for each feature-percentile combination
        results = []
        
        for feature in df['feature_name'].unique():
            for percentile in self.percentiles:
                feature_data = df[(df['feature_name'] == feature) & (df['percentile'] == percentile)]
                
                if len(feature_data) > 0:
                    stats = self._calculate_correlation_stats(
                        feature, percentile, correlation_type, feature_data
                    )
                    results.append(stats)
        
        return pd.DataFrame(results)
    
    def _calculate_correlation_stats(self, feature: str, percentile: int, 
                                   correlation_type: str, data: pd.DataFrame) -> dict:
        """Calculate comprehensive statistics for a feature-percentile combination"""
        
        correlations = data['correlation_value'].dropna()
        total_count = data['total_count'].iloc[0] if len(data) > 0 else 0
        null_count = data['null_count'].iloc[0] if len(data) > 0 else 0
        
        if len(correlations) == 0:
            return None
            
        stats = {
            'feature_name': feature,
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
            'null_count': null_count,
            'null_percentage': null_count / total_count if total_count > 0 else 0,
            'skewness': correlations.skew(),
            'kurtosis': correlations.kurtosis()
        }
        
        return stats
    
    def analyze_feature_patterns(self, stats_df: pd.DataFrame) -> Dict:
        """Analyze patterns in how features behave across percentiles"""
        
        patterns = {}
        
        for feature in stats_df['feature_name'].unique():
            feature_stats = stats_df[stats_df['feature_name'] == feature].sort_values('percentile')
            
            if len(feature_stats) < 4:  # Need at least 4 percentiles
                continue
                
            # Analyze correlation strength trend
            mean_corrs = feature_stats['mean_correlation'].values
            percentiles = feature_stats['percentile'].values
            
            # Calculate trend
            slope, intercept, r_value, p_value, std_err = stats.linregress(percentiles, mean_corrs)
            
            # Analyze stability
            correlation_stability = 1 - feature_stats['std_correlation'].mean()
            
            # Find optimal percentile (highest absolute mean correlation)
            optimal_idx = feature_stats['mean_correlation'].abs().idxmax()
            optimal_percentile = feature_stats.loc[optimal_idx, 'percentile']
            optimal_strength = abs(feature_stats.loc[optimal_idx, 'mean_correlation'])
            
            # Data availability
            avg_null_percentage = feature_stats['null_percentage'].mean()
            
            patterns[feature] = {
                'trend_slope': slope,
                'trend_r2': r_value ** 2,
                'trend_p_value': p_value,
                'correlation_stability': correlation_stability,
                'optimal_percentile': optimal_percentile,
                'optimal_strength': optimal_strength,
                'avg_null_percentage': avg_null_percentage,
                'percentile_coverage': len(feature_stats),
                'pattern_classification': self._classify_pattern(
                    slope, r_value, mean_corrs, correlation_stability
                )
            }
            
        return patterns
    
    def _classify_pattern(self, slope: float, r_value: float, 
                         correlations: np.ndarray, stability: float) -> str:
        """Classify the correlation pattern"""
        
        # Very stable across percentiles
        if np.std(correlations) < 0.02:
            return 'highly_stable'
        
        # Stable with minor variation
        elif stability > 0.8:
            return 'stable'
        
        # Clear decreasing trend (elite-focused)
        elif slope < -0.001 and r_value < -0.7:
            return 'elite_focused'
        
        # Clear increasing trend (mass-inclusive)  
        elif slope > 0.001 and r_value > 0.7:
            return 'mass_inclusive'
        
        # Peak in middle percentiles
        peak_idx = np.argmax(np.abs(correlations))
        if 1 < peak_idx < len(correlations) - 2:
            return 'middle_peak'
        
        # High variability
        elif stability < 0.5:
            return 'highly_variable'
        
        return 'complex'
    
    def create_quality_tiers(self, patterns: Dict) -> Dict:
        """Assign features to quality tiers based on their patterns"""
        
        # Calculate quality scores
        quality_scores = {}
        
        for feature, pattern in patterns.items():
            # Components of quality
            strength_score = min(pattern['optimal_strength'] * 2, 1.0)  # Scale to 0-1
            stability_score = pattern['correlation_stability']
            availability_score = 1 - pattern['avg_null_percentage']
            
            # Penalize highly variable patterns
            if pattern['pattern_classification'] == 'highly_variable':
                pattern_penalty = 0.7
            else:
                pattern_penalty = 1.0
            
            # Combined score
            quality_score = (
                0.4 * strength_score + 
                0.3 * stability_score + 
                0.3 * availability_score
            ) * pattern_penalty
            
            quality_scores[feature] = {
                'overall_score': quality_score,
                'strength_score': strength_score,
                'stability_score': stability_score,
                'availability_score': availability_score,
                'pattern': pattern['pattern_classification'],
                'optimal_percentile': pattern['optimal_percentile']
            }
        
        # Sort by quality score
        sorted_features = sorted(quality_scores.items(), key=lambda x: x[1]['overall_score'], reverse=True)
        
        # Assign tiers
        n_features = len(sorted_features)
        tier_size = n_features // 3
        
        tiers = {
            'tier_1_high_quality': [f[0] for f in sorted_features[:tier_size]],
            'tier_2_medium_quality': [f[0] for f in sorted_features[tier_size:2*tier_size]],
            'tier_3_low_quality': [f[0] for f in sorted_features[2*tier_size:]]
        }
        
        # Add tier assignment to quality scores
        for tier_name, features in tiers.items():
            tier_number = int(tier_name.split('_')[1])
            for feature in features:
                quality_scores[feature]['tier'] = tier_number
        
        return quality_scores, tiers
    
    def generate_summary_report(self, correlation_type: str = 'all_races') -> Dict:
        """Generate comprehensive summary report"""
        
        print("Generating correlation quality report...")
        
        # Get base statistics
        stats_df = self.analyze_all_features(correlation_type)
        
        # Analyze patterns
        patterns = self.analyze_feature_patterns(stats_df)
        
        # Create quality tiers
        quality_scores, tiers = self.create_quality_tiers(patterns)
        
        # Generate summary statistics
        summary = {
            'analysis_date': datetime.now().isoformat(),
            'correlation_type': correlation_type,
            'total_features': len(patterns),
            'percentiles_analyzed': self.percentiles,
            
            'pattern_distribution': {},
            'tier_distribution': {
                'tier_1': len(tiers['tier_1_high_quality']),
                'tier_2': len(tiers['tier_2_medium_quality']), 
                'tier_3': len(tiers['tier_3_low_quality'])
            },
            
            'top_features': {},
            'feature_details': quality_scores,
            'quality_tiers': tiers,
            'pattern_details': patterns,
            
            'data_availability': self._analyze_data_availability(stats_df),
            'recommendations': self._generate_recommendations(patterns, quality_scores)
        }
        
        # Count pattern distribution
        pattern_counts = {}
        for feature, pattern in patterns.items():
            p = pattern['pattern_classification']
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
        summary['pattern_distribution'] = pattern_counts
        
        # Get top features by different criteria
        sorted_by_strength = sorted(
            quality_scores.items(), 
            key=lambda x: x[1]['strength_score'], 
            reverse=True
        )[:10]
        
        sorted_by_stability = sorted(
            quality_scores.items(),
            key=lambda x: x[1]['stability_score'],
            reverse=True
        )[:10]
        
        summary['top_features'] = {
            'by_correlation_strength': [f[0] for f in sorted_by_strength],
            'by_stability': [f[0] for f in sorted_by_stability],
            'by_overall_quality': list(tiers['tier_1_high_quality'])[:10]
        }
        
        return summary
    
    def _analyze_data_availability(self, stats_df: pd.DataFrame) -> Dict:
        """Analyze data availability across percentiles"""
        
        availability = {}
        
        for percentile in self.percentiles:
            p_stats = stats_df[stats_df['percentile'] == percentile]
            
            availability[f'percentile_{percentile}'] = {
                'avg_null_percentage': p_stats['null_percentage'].mean(),
                'features_with_data': len(p_stats[p_stats['null_percentage'] < 0.5]),
                'features_mostly_null': len(p_stats[p_stats['null_percentage'] > 0.8]),
                'avg_sample_size': p_stats['sample_size'].mean()
            }
        
        return availability
    
    def _generate_recommendations(self, patterns: Dict, quality_scores: Dict) -> Dict:
        """Generate recommendations based on analysis"""
        
        recommendations = {
            'high_quality_features': [],
            'percentile_specific_features': {},
            'avoid_features': [],
            'general_insights': []
        }
        
        # High quality features (tier 1 with good patterns)
        good_patterns = ['highly_stable', 'stable', 'elite_focused', 'mass_inclusive']
        
        for feature, score in quality_scores.items():
            if score['tier'] == 1 and patterns[feature]['pattern_classification'] in good_patterns:
                recommendations['high_quality_features'].append({
                    'feature': feature,
                    'reason': f"{patterns[feature]['pattern_classification']} pattern with {score['overall_score']:.3f} quality score",
                    'optimal_percentile': score['optimal_percentile']
                })
        
        # Features to avoid
        for feature, score in quality_scores.items():
            if score['tier'] == 3 or patterns[feature]['pattern_classification'] == 'highly_variable':
                recommendations['avoid_features'].append({
                    'feature': feature,
                    'reason': f"Low quality score ({score['overall_score']:.3f}) or highly variable pattern"
                })
        
        # Percentile-specific recommendations
        for percentile in self.percentiles:
            best_at_percentile = [
                f for f, s in quality_scores.items() 
                if s['optimal_percentile'] == percentile and s['tier'] <= 2
            ][:5]
            
            if best_at_percentile:
                recommendations['percentile_specific_features'][percentile] = best_at_percentile
        
        return recommendations
    
    def save_report(self, report: Dict, output_dir: str = "correlation_analysis_output"):
        """Save report as JSON and generate visualizations"""
        
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save JSON report
        json_path = output_path / f"correlation_quality_report_{report['correlation_type']}.json"
        with open(json_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Report saved to {json_path}")
        
        # Generate visualizations
        self._create_visualizations(report, output_path)
    
    def _create_visualizations(self, report: Dict, output_path: Path):
        """Create visualization plots"""
        
        # 1. Pattern distribution pie chart
        plt.figure(figsize=(10, 6))
        pattern_dist = report['pattern_distribution']
        plt.pie(pattern_dist.values(), labels=pattern_dist.keys(), autopct='%1.1f%%')
        plt.title(f"Correlation Pattern Distribution - {report['correlation_type']}")
        plt.savefig(output_path / "pattern_distribution.png")
        plt.close()
        
        # 2. Top features by quality score
        top_features = list(report['quality_tiers']['tier_1_high_quality'])[:15]
        scores = [report['feature_details'][f]['overall_score'] for f in top_features]
        
        plt.figure(figsize=(12, 8))
        plt.barh(top_features, scores)
        plt.xlabel('Quality Score')
        plt.title('Top 15 Features by Quality Score')
        plt.tight_layout()
        plt.savefig(output_path / "top_features_quality.png")
        plt.close()
        
        print("Visualizations saved")

# Usage example
if __name__ == "__main__":
    analyzer = CorrelationQualityAnalyzer("../database/database/cycling_races.db")
    
    # Generate report for each correlation type
    for corr_type in ['all_races', 'same_type', 'stage_one_days']:
        report = analyzer.generate_summary_report(corr_type)
        analyzer.save_report(report)
        
        # Print summary
        print(f"\n=== {corr_type} Summary ===")
        print(f"Total features analyzed: {report['total_features']}")
        print(f"Tier distribution: {report['tier_distribution']}")
        print(f"Top 5 features: {report['top_features']['by_overall_quality'][:5]}")