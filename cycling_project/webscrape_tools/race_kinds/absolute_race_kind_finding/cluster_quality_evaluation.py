"""
Cluster Quality Evaluation and Reporting System for Absolute Race Kind Clustering.

This module analyzes clustering results from both breakdown and no-breakdown populations
to provide comprehensive quality evaluation and reporting.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')


class ClusterQualityEvaluator:
    """Comprehensive evaluation of clustering results quality."""
    
    def __init__(self):
        """Initialize evaluator with paths to clustering results."""
        self.base_dir = Path(__file__).parent
        self.breakdown_dir = self.base_dir / "clustering_results_with_breakdown"
        self.no_breakdown_dir = self.base_dir / "clustering_results_no_breakdown"
        
        # Load results
        self.breakdown_results = self._load_results("with_breakdown")
        self.no_breakdown_results = self._load_results("no_breakdown")
        self.breakdown_summary = self._load_summary("with_breakdown")
        self.no_breakdown_summary = self._load_summary("no_breakdown")
        
    def _load_results(self, population_type: str) -> Dict:
        """Load clustering results for a population."""
        if population_type == "with_breakdown":
            results_file = self.breakdown_dir / "absolute_clustering_results.json"
        else:
            results_file = self.no_breakdown_dir / "absolute_clustering_results.json"
        
        try:
            with open(results_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: No results found for {population_type} population")
            return {}
    
    def _load_summary(self, population_type: str) -> Dict:
        """Load clustering summary for a population."""
        if population_type == "with_breakdown":
            summary_file = self.breakdown_dir / "clustering_summary.json"
        else:
            summary_file = self.no_breakdown_dir / "clustering_summary.json"
        
        try:
            with open(summary_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: No summary found for {population_type} population")
            return {}
    
    def analyze_optimal_cluster_counts(self) -> Dict:
        """Analyze optimal cluster counts across percentiles for both populations."""
        analysis = {
            'with_breakdown': {},
            'no_breakdown': {},
            'comparison': {}
        }
        
        # Analyze breakdown population
        if self.breakdown_summary and 'best_k_by_percentile' in self.breakdown_summary:
            for percentile, metrics in self.breakdown_summary['best_k_by_percentile'].items():
                analysis['with_breakdown'][percentile] = {
                    'best_k_silhouette': metrics['by_silhouette'],
                    'best_k_calinski': metrics['by_calinski'],
                    'best_k_davies_bouldin': metrics['by_davies_bouldin'],
                    'consensus_score': self._calculate_consensus_score(metrics),
                    'race_count': self.breakdown_summary['total_races_by_percentile'].get(percentile, 0)
                }
        
        # Analyze no-breakdown population
        if self.no_breakdown_summary and 'best_k_by_percentile' in self.no_breakdown_summary:
            for percentile, metrics in self.no_breakdown_summary['best_k_by_percentile'].items():
                analysis['no_breakdown'][percentile] = {
                    'best_k_silhouette': metrics['by_silhouette'],
                    'best_k_calinski': metrics['by_calinski'],
                    'best_k_davies_bouldin': metrics['by_davies_bouldin'],
                    'consensus_score': self._calculate_consensus_score(metrics),
                    'race_count': self.no_breakdown_summary['total_races_by_percentile'].get(percentile, 0)
                }
        
        # Compare populations
        analysis['comparison'] = self._compare_optimal_k_across_populations()
        
        return analysis
    
    def _calculate_consensus_score(self, metrics: Dict) -> float:
        """Calculate consensus score when multiple metrics agree on optimal K."""
        k_values = [metrics['by_silhouette'], metrics['by_calinski'], metrics['by_davies_bouldin']]
        k_counts = Counter(k_values)
        max_agreement = max(k_counts.values())
        return max_agreement / 3.0  # 1.0 = all agree, 0.33 = no agreement
    
    def _compare_optimal_k_across_populations(self) -> Dict:
        """Compare optimal K values between populations."""
        comparison = {}
        
        # Find common percentiles
        breakdown_percentiles = set(self.breakdown_summary.get('best_k_by_percentile', {}).keys())
        no_breakdown_percentiles = set(self.no_breakdown_summary.get('best_k_by_percentile', {}).keys())
        common_percentiles = breakdown_percentiles.intersection(no_breakdown_percentiles)
        
        for percentile in sorted(common_percentiles, key=int):
            breakdown_k = self.breakdown_summary['best_k_by_percentile'][percentile]['by_silhouette']
            no_breakdown_k = self.no_breakdown_summary['best_k_by_percentile'][percentile]['by_silhouette']
            
            comparison[percentile] = {
                'breakdown_optimal_k': breakdown_k,
                'no_breakdown_optimal_k': no_breakdown_k,
                'k_difference': abs(breakdown_k - no_breakdown_k),
                'populations_agree': breakdown_k == no_breakdown_k
            }
        
        return comparison
    
    def analyze_clustering_quality_trends(self) -> Dict:
        """Analyze how clustering quality changes across percentiles."""
        trends = {
            'with_breakdown': self._analyze_population_trends('with_breakdown'),
            'no_breakdown': self._analyze_population_trends('no_breakdown')
        }
        
        return trends
    
    def _analyze_population_trends(self, population_type: str) -> Dict:
        """Analyze quality trends for a specific population."""
        if population_type == 'with_breakdown':
            summary = self.breakdown_summary
        else:
            summary = self.no_breakdown_summary
        
        if not summary or 'metrics_summary' not in summary:
            return {}
        
        trends = {
            'silhouette_scores': {},
            'calinski_scores': {},
            'davies_bouldin_scores': {},
            'percentile_analysis': {}
        }
        
        for percentile, k_results in summary['metrics_summary'].items():
            # Get best K based on silhouette
            best_k = summary['best_k_by_percentile'][percentile]['by_silhouette']
            best_metrics = k_results[str(best_k)]
            
            trends['silhouette_scores'][percentile] = best_metrics['silhouette_score']
            trends['calinski_scores'][percentile] = best_metrics['calinski_harabasz_score']
            trends['davies_bouldin_scores'][percentile] = best_metrics['davies_bouldin_score']
            
            # Analyze this percentile
            trends['percentile_analysis'][percentile] = self._analyze_percentile_quality(
                percentile, k_results, best_k
            )
        
        return trends
    
    def _analyze_percentile_quality(self, percentile: str, k_results: Dict, best_k: int) -> Dict:
        """Analyze clustering quality for a specific percentile."""
        analysis = {
            'best_k': best_k,
            'quality_assessment': '',
            'k_stability': 0,
            'metric_ranges': {}
        }
        
        # Calculate metric ranges across different K values
        silhouette_scores = [k_results[k]['silhouette_score'] for k in k_results.keys()]
        calinski_scores = [k_results[k]['calinski_harabasz_score'] for k in k_results.keys()]
        davies_bouldin_scores = [k_results[k]['davies_bouldin_score'] for k in k_results.keys()]
        
        analysis['metric_ranges'] = {
            'silhouette_range': max(silhouette_scores) - min(silhouette_scores),
            'silhouette_max': max(silhouette_scores),
            'silhouette_min': min(silhouette_scores),
            'calinski_range': max(calinski_scores) - min(calinski_scores),
            'davies_bouldin_range': max(davies_bouldin_scores) - min(davies_bouldin_scores)
        }
        
        # Assess quality based on best silhouette score
        best_silhouette = k_results[str(best_k)]['silhouette_score']
        if best_silhouette >= 0.7:
            analysis['quality_assessment'] = 'Excellent'
        elif best_silhouette >= 0.5:
            analysis['quality_assessment'] = 'Good'
        elif best_silhouette >= 0.25:
            analysis['quality_assessment'] = 'Moderate'
        else:
            analysis['quality_assessment'] = 'Poor'
        
        # Calculate K stability (how consistent metrics are across K values)
        analysis['k_stability'] = 1.0 - (analysis['metric_ranges']['silhouette_range'] / 
                                        (analysis['metric_ranges']['silhouette_max'] + 1e-10))
        
        return analysis
    
    def analyze_feature_importance_patterns(self) -> Dict:
        """Analyze feature importance patterns across percentiles and populations."""
        patterns = {
            'with_breakdown': self._analyze_feature_patterns('with_breakdown'),
            'no_breakdown': self._analyze_feature_patterns('no_breakdown'),
            'cross_population_comparison': {}
        }
        
        # Compare patterns between populations
        patterns['cross_population_comparison'] = self._compare_feature_patterns(
            patterns['with_breakdown'], patterns['no_breakdown']
        )
        
        return patterns
    
    def _analyze_feature_patterns(self, population_type: str) -> Dict:
        """Analyze feature importance patterns for a population."""
        if population_type == 'with_breakdown':
            results = self.breakdown_results
            summary = self.breakdown_summary
        else:
            results = self.no_breakdown_results
            summary = self.no_breakdown_summary
        
        if not results or not summary:
            return {}
        
        patterns = {
            'top_features_by_percentile': {},
            'consistent_important_features': [],
            'feature_stability_scores': {},
            'percentile_feature_counts': {}
        }
        
        all_feature_importances = defaultdict(list)
        
        for percentile, percentile_results in results.items():
            if not percentile_results:
                continue
            
            # Get best K for this percentile
            best_k = str(summary['best_k_by_percentile'][percentile]['by_silhouette'])
            
            if best_k in percentile_results:
                importances = percentile_results[best_k]['feature_importances']['overall']
                
                # Store top features for this percentile
                sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
                patterns['top_features_by_percentile'][percentile] = sorted_features[:10]
                patterns['percentile_feature_counts'][percentile] = len(importances)
                
                # Collect all importances for stability analysis
                for feature, importance in importances.items():
                    all_feature_importances[feature].append(importance)
        
        # Calculate feature stability scores (consistency across percentiles)
        for feature, importance_list in all_feature_importances.items():
            if len(importance_list) > 1:
                patterns['feature_stability_scores'][feature] = {
                    'mean_importance': np.mean(importance_list),
                    'std_importance': np.std(importance_list),
                    'coefficient_of_variation': np.std(importance_list) / (np.mean(importance_list) + 1e-10),
                    'percentiles_present': len(importance_list)
                }
        
        # Find consistently important features (high mean, low variability)
        if patterns['feature_stability_scores']:
            stable_features = sorted(patterns['feature_stability_scores'].items(),
                                   key=lambda x: (x[1]['mean_importance'], -x[1]['coefficient_of_variation']),
                                   reverse=True)
            patterns['consistent_important_features'] = stable_features[:15]
        
        return patterns
    
    def _compare_feature_patterns(self, breakdown_patterns: Dict, no_breakdown_patterns: Dict) -> Dict:
        """Compare feature importance patterns between populations."""
        comparison = {}
        
        if not breakdown_patterns or not no_breakdown_patterns:
            return comparison
        
        # Compare consistent important features
        breakdown_top = {f[0]: f[1]['mean_importance'] 
                        for f in breakdown_patterns.get('consistent_important_features', [])}
        no_breakdown_top = {f[0]: f[1]['mean_importance'] 
                           for f in no_breakdown_patterns.get('consistent_important_features', [])}
        
        # Find common important features
        common_features = set(breakdown_top.keys()).intersection(set(no_breakdown_top.keys()))
        unique_to_breakdown = set(breakdown_top.keys()) - set(no_breakdown_top.keys())
        unique_to_no_breakdown = set(no_breakdown_top.keys()) - set(breakdown_top.keys())
        
        comparison['feature_overlap'] = {
            'common_important_features': list(common_features),
            'unique_to_breakdown': list(unique_to_breakdown),
            'unique_to_no_breakdown': list(unique_to_no_breakdown),
            'overlap_ratio': len(common_features) / (len(breakdown_top) + len(no_breakdown_top) - len(common_features) + 1e-10)
        }
        
        return comparison
    
    def generate_quality_summary_report(self) -> Dict:
        """Generate comprehensive quality summary report."""
        optimal_k_analysis = self.analyze_optimal_cluster_counts()
        quality_trends = self.analyze_clustering_quality_trends()
        feature_patterns = self.analyze_feature_importance_patterns()
        
        report = {
            'executive_summary': self._create_executive_summary(
                optimal_k_analysis, quality_trends, feature_patterns
            ),
            'optimal_cluster_analysis': optimal_k_analysis,
            'quality_trends': quality_trends,
            'feature_importance_analysis': feature_patterns,
            'recommendations': self._generate_recommendations(
                optimal_k_analysis, quality_trends, feature_patterns
            )
        }
        
        return report
    
    def _create_executive_summary(self, k_analysis: Dict, quality_trends: Dict, 
                                feature_patterns: Dict) -> Dict:
        """Create executive summary of clustering quality."""
        summary = {
            'total_percentiles_analyzed': 0,
            'populations_analyzed': [],
            'average_clustering_quality': {},
            'optimal_k_consensus': {},
            'feature_consistency': {}
        }
        
        # Count analyzed populations
        if k_analysis.get('with_breakdown'):
            summary['populations_analyzed'].append('with_breakdown')
            summary['total_percentiles_analyzed'] = len(k_analysis['with_breakdown'])
        
        if k_analysis.get('no_breakdown'):
            summary['populations_analyzed'].append('no_breakdown')
            if not summary['total_percentiles_analyzed']:
                summary['total_percentiles_analyzed'] = len(k_analysis['no_breakdown'])
        
        # Calculate average quality metrics
        for population in summary['populations_analyzed']:
            if population in quality_trends:
                silhouette_scores = list(quality_trends[population].get('silhouette_scores', {}).values())
                if silhouette_scores:
                    summary['average_clustering_quality'][population] = {
                        'mean_silhouette': np.mean(silhouette_scores),
                        'quality_category': self._categorize_quality(np.mean(silhouette_scores))
                    }
        
        # Analyze K consensus
        for population in summary['populations_analyzed']:
            if population in k_analysis:
                consensus_scores = [data['consensus_score'] 
                                  for data in k_analysis[population].values()]
                if consensus_scores:
                    summary['optimal_k_consensus'][population] = {
                        'mean_consensus': np.mean(consensus_scores),
                        'high_consensus_percentiles': sum(1 for score in consensus_scores if score >= 0.67)
                    }
        
        return summary
    
    def _categorize_quality(self, silhouette_score: float) -> str:
        """Categorize clustering quality based on silhouette score."""
        if silhouette_score >= 0.7:
            return 'Excellent'
        elif silhouette_score >= 0.5:
            return 'Good'
        elif silhouette_score >= 0.25:
            return 'Moderate'
        else:
            return 'Poor'
    
    def _generate_recommendations(self, k_analysis: Dict, quality_trends: Dict, 
                                feature_patterns: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Analyze clustering quality
        for population in ['with_breakdown', 'no_breakdown']:
            if population in quality_trends and 'silhouette_scores' in quality_trends[population]:
                scores = list(quality_trends[population]['silhouette_scores'].values())
                if scores:
                    avg_score = np.mean(scores)
                    pop_name = population.replace('_', ' ')
                    
                    if avg_score < 0.25:
                        recommendations.append(
                            f"Consider revisiting feature selection for {pop_name} population - "
                            f"clustering quality is poor (avg silhouette: {avg_score:.3f})"
                        )
                    elif avg_score < 0.5:
                        recommendations.append(
                            f"Moderate clustering quality for {pop_name} population "
                            f"(avg silhouette: {avg_score:.3f}) - consider alternative clustering approaches"
                        )
        
        # Analyze K consensus
        for population in ['with_breakdown', 'no_breakdown']:
            if population in k_analysis:
                consensus_scores = [data['consensus_score'] for data in k_analysis[population].values()]
                low_consensus = sum(1 for score in consensus_scores if score < 0.5)
                if low_consensus > len(consensus_scores) * 0.3:
                    pop_name = population.replace('_', ' ')
                    recommendations.append(
                        f"Low metric consensus on optimal K for {pop_name} population in "
                        f"{low_consensus} percentiles - consider additional evaluation metrics"
                    )
        
        # Feature analysis recommendations
        if 'cross_population_comparison' in feature_patterns:
            overlap_ratio = feature_patterns['cross_population_comparison'].get(
                'feature_overlap', {}
            ).get('overlap_ratio', 0)
            
            if overlap_ratio < 0.3:
                recommendations.append(
                    f"Low feature overlap between populations ({overlap_ratio:.2f}) - "
                    "populations may have fundamentally different clustering characteristics"
                )
            elif overlap_ratio > 0.7:
                recommendations.append(
                    f"High feature overlap between populations ({overlap_ratio:.2f}) - "
                    "consider unified clustering approach across populations"
                )
        
        if not recommendations:
            recommendations.append("Clustering quality analysis looks good - no major issues identified")
        
        return recommendations
    
    def save_quality_report(self, output_dir: Optional[Path] = None):
        """Save comprehensive quality report to files."""
        if output_dir is None:
            output_dir = self.base_dir / "cluster_quality_reports"
        
        output_dir.mkdir(exist_ok=True)
        
        # Generate full report
        report = self.generate_quality_summary_report()
        
        # Save main report
        report_file = output_dir / "cluster_quality_summary.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"Quality summary report saved to {report_file}")
        
        # Save detailed analysis files
        optimal_k_file = output_dir / "optimal_k_analysis.json"
        with open(optimal_k_file, 'w') as f:
            json.dump(report['optimal_cluster_analysis'], f, indent=2)
        
        quality_trends_file = output_dir / "quality_trends_analysis.json"
        with open(quality_trends_file, 'w') as f:
            json.dump(report['quality_trends'], f, indent=2)
        
        feature_patterns_file = output_dir / "feature_importance_patterns.json"
        with open(feature_patterns_file, 'w') as f:
            json.dump(report['feature_importance_analysis'], f, indent=2)
        
        # Create human-readable summary
        self._create_readable_summary(report, output_dir)
        
        print(f"Detailed analysis files saved to {output_dir}")
    
    def _create_readable_summary(self, report: Dict, output_dir: Path):
        """Create human-readable summary report."""
        summary_file = output_dir / "quality_summary_readable.txt"
        
        with open(summary_file, 'w') as f:
            f.write("ABSOLUTE RACE KIND CLUSTERING - QUALITY EVALUATION REPORT\n")
            f.write("=" * 60 + "\n\n")
            
            # Executive Summary
            exec_summary = report['executive_summary']
            f.write("EXECUTIVE SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(f"Populations Analyzed: {', '.join(exec_summary['populations_analyzed'])}\n")
            f.write(f"Total Percentiles: {exec_summary['total_percentiles_analyzed']}\n\n")
            
            # Quality by Population
            f.write("CLUSTERING QUALITY BY POPULATION\n")
            f.write("-" * 35 + "\n")
            for population, quality in exec_summary.get('average_clustering_quality', {}).items():
                pop_name = population.replace('_', ' ').title()
                f.write(f"{pop_name}:\n")
                f.write(f"  Average Silhouette Score: {quality['mean_silhouette']:.3f}\n")
                f.write(f"  Quality Category: {quality['quality_category']}\n\n")
            
            # Optimal K Consensus
            f.write("OPTIMAL K CONSENSUS\n")
            f.write("-" * 20 + "\n")
            for population, consensus in exec_summary.get('optimal_k_consensus', {}).items():
                pop_name = population.replace('_', ' ').title()
                f.write(f"{pop_name}:\n")
                f.write(f"  Mean Consensus Score: {consensus['mean_consensus']:.3f}\n")
                f.write(f"  High Consensus Percentiles: {consensus['high_consensus_percentiles']}\n\n")
            
            # Recommendations
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 15 + "\n")
            for i, rec in enumerate(report.get('recommendations', []), 1):
                f.write(f"{i}. {rec}\n\n")
        
        print(f"Human-readable summary saved to {summary_file}")


def main():
    """Run cluster quality evaluation."""
    print("=" * 60)
    print("ABSOLUTE RACE KIND CLUSTERING - QUALITY EVALUATION")
    print("=" * 60)
    
    evaluator = ClusterQualityEvaluator()
    
    # Generate and save quality report
    evaluator.save_quality_report()
    
    print("\n" + "=" * 60)
    print("Quality evaluation complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()