"""
Report generator module for correlation feature analysis.

Generates reports and visualizations.
"""

import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class CorrelationReportGenerator:
    """Generates reports and visualizations"""
    
    def __init__(self, output_dir: str = "correlation_analysis_output"):
        """
        Initialize report generator.
        
        Args:
            output_dir: Directory to save reports and visualizations
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_summary(self, 
                        correlation_type: str,
                        patterns: Dict,
                        quality_scores: Dict,
                        tiers: Dict,
                        stats_df: pd.DataFrame,
                        data_availability: Dict,
                        percentiles: List[int]) -> Dict:
        """
        Generate comprehensive summary report.
        
        Args:
            correlation_type: Type of correlation analyzed
            patterns: Pattern analysis results
            quality_scores: Quality scores for all features
            tiers: Tier assignments
            stats_df: DataFrame with feature statistics
            data_availability: Data availability analysis
            percentiles: List of percentiles analyzed
            
        Returns:
            Dictionary containing the complete report
        """
        # Count pattern distribution
        pattern_counts = {}
        for feature, pattern in patterns.items():
            p = pattern['pattern_classification']
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
        
        # Get top features by different criteria
        top_features = self._get_top_features(quality_scores, tiers)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(patterns, quality_scores, percentiles)
        
        summary = {
            'analysis_date': datetime.now().isoformat(),
            'correlation_type': correlation_type,
            'total_features': len(patterns),
            'percentiles_analyzed': percentiles,
            
            'pattern_distribution': pattern_counts,
            'tier_distribution': {
                tier_name: len(features) 
                for tier_name, features in tiers.items()
            },
            
            'top_features': top_features,
            'feature_details': quality_scores,
            'quality_tiers': tiers,
            'pattern_details': patterns,
            
            'data_availability': data_availability,
            'recommendations': recommendations,
            
            'summary_statistics': self._calculate_summary_statistics(stats_df)
        }
        
        return summary
    
    def _get_top_features(self, quality_scores: Dict, tiers: Dict, n: int = 10) -> Dict:
        """Get top features by different criteria"""
        # Overall quality
        sorted_by_quality = sorted(
            quality_scores.items(),
            key=lambda x: x[1]['overall_score'],
            reverse=True
        )[:n]
        
        # Correlation strength
        sorted_by_strength = sorted(
            quality_scores.items(),
            key=lambda x: x[1]['strength_score'],
            reverse=True
        )[:n]
        
        # Stability
        sorted_by_stability = sorted(
            quality_scores.items(),
            key=lambda x: x[1]['stability_score'],
            reverse=True
        )[:n]
        
        return {
            'by_overall_quality': [f[0] for f in sorted_by_quality],
            'by_correlation_strength': [f[0] for f in sorted_by_strength],
            'by_stability': [f[0] for f in sorted_by_stability],
            'tier_1_features': list(tiers.get('tier_1_high_quality', []))[:n]
        }
    
    def _generate_recommendations(self, patterns: Dict, quality_scores: Dict, 
                                percentiles: List[int]) -> Dict:
        """Generate recommendations based on analysis"""
        recommendations = {
            'high_quality_features': [],
            'percentile_specific_features': {},
            'avoid_features': [],
            'general_insights': []
        }
        
        # Good pattern types
        good_patterns = ['highly_stable', 'stable', 'elite_focused', 'mass_inclusive']
        
        # High quality features
        for feature, score in quality_scores.items():
            if score.get('tier', 3) == 1 and patterns[feature]['pattern_classification'] in good_patterns:
                recommendations['high_quality_features'].append({
                    'feature': feature,
                    'reason': f"{patterns[feature]['pattern_classification']} pattern with {score['overall_score']:.3f} quality score",
                    'optimal_percentile': score.get('optimal_percentile', 0)
                })
        
        # Features to avoid
        for feature, score in quality_scores.items():
            if score.get('tier', 3) == 3 or patterns[feature]['pattern_classification'] == 'highly_variable':
                recommendations['avoid_features'].append({
                    'feature': feature,
                    'reason': f"Low quality score ({score['overall_score']:.3f}) or highly variable pattern"
                })
        
        # Percentile-specific recommendations
        for percentile in percentiles:
            best_at_percentile = [
                f for f, s in quality_scores.items() 
                if s.get('optimal_percentile', 0) == percentile and s.get('tier', 3) <= 2
            ][:5]
            
            if best_at_percentile:
                recommendations['percentile_specific_features'][percentile] = best_at_percentile
        
        # General insights
        stable_count = sum(1 for p in patterns.values() if p['pattern_classification'] in ['highly_stable', 'stable'])
        recommendations['general_insights'].append(
            f"{stable_count} features ({stable_count/len(patterns)*100:.1f}%) show stable correlation patterns"
        )
        
        return recommendations
    
    def _calculate_summary_statistics(self, stats_df: pd.DataFrame) -> Dict:
        """Calculate summary statistics across all features and percentiles"""
        return {
            'avg_correlation_strength': float(stats_df['mean_correlation'].abs().mean()),
            'avg_stability': float(1 - stats_df['std_correlation'].mean()),
            'avg_sample_size': float(stats_df['sample_size'].mean()),
            'total_null_percentage': float(stats_df['null_percentage'].mean()),
            'features_with_high_nulls': int((stats_df.groupby('feature_name')['null_percentage'].mean() > 0.5).sum())
        }
    
    def save_report(self, report: Dict, format: str = 'json'):
        """
        Save report in specified format.
        
        Args:
            report: Report dictionary to save
            format: Output format ('json' or 'markdown')
        """
        correlation_type = report['correlation_type']
        
        if format == 'json':
            json_path = self.output_dir / f"correlation_quality_report_{correlation_type}.json"
            with open(json_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"JSON report saved to {json_path}")
        
        elif format == 'markdown':
            md_path = self.output_dir / f"correlation_quality_report_{correlation_type}.md"
            with open(md_path, 'w') as f:
                f.write(self._generate_markdown_report(report))
            print(f"Markdown report saved to {md_path}")
    
    def _generate_markdown_report(self, report: Dict) -> str:
        """Generate markdown version of the report"""
        md = f"# Correlation Quality Analysis Report\n\n"
        md += f"**Analysis Date:** {report['analysis_date']}\n"
        md += f"**Correlation Type:** {report['correlation_type']}\n"
        md += f"**Total Features:** {report['total_features']}\n\n"
        
        # Pattern distribution
        md += "## Pattern Distribution\n\n"
        for pattern, count in report['pattern_distribution'].items():
            md += f"- {pattern}: {count} features\n"
        
        # Tier distribution
        md += "\n## Quality Tier Distribution\n\n"
        for tier, count in report['tier_distribution'].items():
            md += f"- {tier}: {count} features\n"
        
        # Top features
        md += "\n## Top Features\n\n"
        md += "### By Overall Quality\n"
        for i, feature in enumerate(report['top_features']['by_overall_quality'][:10], 1):
            score = report['feature_details'][feature]['overall_score']
            md += f"{i}. {feature} (score: {score:.3f})\n"
        
        # Recommendations
        md += "\n## Recommendations\n\n"
        md += "### High Quality Features\n"
        for rec in report['recommendations']['high_quality_features'][:10]:
            md += f"- **{rec['feature']}**: {rec['reason']}\n"
        
        # Summary statistics
        md += "\n## Summary Statistics\n\n"
        stats = report['summary_statistics']
        md += f"- Average correlation strength: {stats['avg_correlation_strength']:.3f}\n"
        md += f"- Average stability: {stats['avg_stability']:.3f}\n"
        md += f"- Average sample size: {stats['avg_sample_size']:.0f}\n"
        md += f"- Average null percentage: {stats['total_null_percentage']:.2%}\n"
        
        return md
    
    def create_visualizations(self, report: Dict):
        """
        Create visualization plots for the report.
        
        Args:
            report: Report dictionary with analysis results
        """
        correlation_type = report['correlation_type']
        
        # Set style
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 1. Pattern distribution pie chart
        self._create_pattern_distribution_plot(report, correlation_type)
        
        # 2. Top features by quality score
        self._create_top_features_plot(report, correlation_type)
        
        # 3. Quality score distribution by tier
        self._create_tier_distribution_plot(report, correlation_type)
        
        # 4. Correlation strength heatmap
        self._create_correlation_heatmap(report, correlation_type)
        
        print(f"Visualizations saved to {self.output_dir}")
    
    def _create_pattern_distribution_plot(self, report: Dict, correlation_type: str):
        """Create pattern distribution pie chart"""
        plt.figure(figsize=(10, 8))
        pattern_dist = report['pattern_distribution']
        
        # Create pie chart
        plt.pie(pattern_dist.values(), labels=pattern_dist.keys(), autopct='%1.1f%%',
                startangle=90, colors=plt.cm.Set3.colors)
        plt.title(f"Correlation Pattern Distribution - {correlation_type}")
        
        # Save
        plt.tight_layout()
        plt.savefig(self.output_dir / f"pattern_distribution_{correlation_type}.png", dpi=300)
        plt.close()
    
    def _create_top_features_plot(self, report: Dict, correlation_type: str):
        """Create bar plot of top features"""
        plt.figure(figsize=(12, 8))
        
        # Get top 15 features
        top_features = report['top_features']['by_overall_quality'][:15]
        scores = [report['feature_details'][f]['overall_score'] for f in top_features]
        
        # Create horizontal bar plot
        y_pos = np.arange(len(top_features))
        plt.barh(y_pos, scores, color='skyblue')
        plt.yticks(y_pos, top_features)
        plt.xlabel('Quality Score')
        plt.title(f'Top 15 Features by Quality Score - {correlation_type}')
        plt.grid(axis='x', alpha=0.3)
        
        # Save
        plt.tight_layout()
        plt.savefig(self.output_dir / f"top_features_{correlation_type}.png", dpi=300)
        plt.close()
    
    def _create_tier_distribution_plot(self, report: Dict, correlation_type: str):
        """Create quality score distribution by tier"""
        plt.figure(figsize=(10, 6))
        
        # Collect scores by tier
        tier_scores = {}
        for feature, details in report['feature_details'].items():
            tier = details.get('tier_name', 'unknown')
            if tier not in tier_scores:
                tier_scores[tier] = []
            tier_scores[tier].append(details['overall_score'])
        
        # Create box plot
        data = []
        labels = []
        for tier in sorted(tier_scores.keys()):
            if tier_scores[tier]:
                data.append(tier_scores[tier])
                labels.append(tier.replace('_', ' ').title())
        
        plt.boxplot(data, labels=labels)
        plt.ylabel('Quality Score')
        plt.title(f'Quality Score Distribution by Tier - {correlation_type}')
        plt.grid(axis='y', alpha=0.3)
        
        # Save
        plt.tight_layout()
        plt.savefig(self.output_dir / f"tier_distribution_{correlation_type}.png", dpi=300)
        plt.close()
    
    def _create_correlation_heatmap(self, report: Dict, correlation_type: str):
        """Create heatmap of correlation strengths across percentiles"""
        # This would require the full stats_df, so we'll create a simplified version
        plt.figure(figsize=(12, 10))
        
        # Get top 20 features
        top_features = report['top_features']['by_overall_quality'][:20]
        
        # Create a matrix of pattern types
        patterns = []
        for feature in top_features:
            pattern = report['pattern_details'][feature]['pattern_classification']
            patterns.append(pattern)
        
        # Create a simple visualization showing pattern types
        pattern_types = list(set(patterns))
        pattern_matrix = np.zeros((len(top_features), len(pattern_types)))
        
        for i, feature in enumerate(top_features):
            pattern = report['pattern_details'][feature]['pattern_classification']
            j = pattern_types.index(pattern)
            pattern_matrix[i, j] = 1
        
        # Create heatmap
        sns.heatmap(pattern_matrix, 
                   xticklabels=pattern_types,
                   yticklabels=top_features,
                   cmap='YlOrRd',
                   cbar_kws={'label': 'Pattern Type'})
        
        plt.title(f'Feature Pattern Types - Top 20 Features - {correlation_type}')
        plt.xlabel('Pattern Type')
        plt.ylabel('Feature')
        
        # Save
        plt.tight_layout()
        plt.savefig(self.output_dir / f"pattern_heatmap_{correlation_type}.png", dpi=300)
        plt.close()