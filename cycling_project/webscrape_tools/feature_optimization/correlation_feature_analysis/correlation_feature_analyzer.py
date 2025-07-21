"""
Correlation Feature Analyzer - Aligned with Race Type Analyzer approach.

This module provides comprehensive analysis of correlation features across percentiles,
following the sophisticated approach of race_feature_n_analysis.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from .blob_data_loader import BlobCorrelationDataLoader
from .statistics_calculator import CorrelationStatisticsCalculator
from .pattern_classifier import CorrelationPatternClassifier
from .quality_scorer import CorrelationQualityScorer
from . import config


class CorrelationFeatureAnalyzer:
    """Main analyzer class for correlation feature analysis"""
    
    def __init__(self, db_path: str = None, percentiles: List[int] = None):
        """
        Initialize the correlation feature analyzer.
        
        Args:
            db_path: Path to the database
            percentiles: List of percentiles to analyze
        """
        self.db_path = db_path or config.DEFAULT_DB_PATH
        self.percentiles = percentiles or config.PERCENTILES
        
        # Initialize components
        self.blob_loader = BlobCorrelationDataLoader(self.db_path)
        self.stats_calculator = CorrelationStatisticsCalculator()
        self.pattern_classifier = CorrelationPatternClassifier(
            stability_threshold=config.PATTERN_THRESHOLDS['stability_threshold'],
            trend_slope_threshold=config.PATTERN_THRESHOLDS['trend_slope_threshold'],
            trend_r_threshold=config.PATTERN_THRESHOLDS['trend_r_threshold']
        )
        self.quality_scorer = CorrelationQualityScorer()
        
        # Define competition type configurations (race-type-first approach)
        self.competition_type_configs = {
            'gc': {
                'description': 'General Classification races',
                'relevant_correlations': ['same_type']
            },
            'stage': {
                'description': 'Stage races',
                'relevant_correlations': ['same_type', 'stage_one_days']
            },
            'one_day': {
                'description': 'One-day races',
                'relevant_correlations': ['same_type', 'stage_one_days']
            }
        }
        
        # Keep correlation type info for reference
        self.correlation_type_info = {
            'same_type': 'Same race type correlations',
            'stage_one_days': 'Stage + One-day correlations', 
            'all_races': 'All races correlations'
        }
    
    def analyze_single_competition_type(self, competition_type: str) -> Dict:
        """
        Analyze a single competition type with its relevant correlation types.
        
        Args:
            competition_type: Competition type to analyze (gc, stage, one_day)
            
        Returns:
            Comprehensive analysis results for the competition type
        """
        config_info = self.competition_type_configs.get(competition_type, {})
        relevant_correlations = config_info.get('relevant_correlations', [])
        
        print(f"\n{'='*80}")
        print(f"ANALYZING COMPETITION TYPE: {config_info.get('description', competition_type)}")
        print(f"Relevant correlations: {relevant_correlations}")
        print(f"{'='*80}\n")
        
        competition_results = {}
        
        # Analyze each relevant correlation type for this competition type
        for correlation_type in relevant_correlations:
            print(f"\n  → Analyzing {correlation_type} correlations for {competition_type} races...")
            
            try:
                # Load and filter data for this correlation type and competition type
                correlation_result = self._analyze_correlation_for_competition(
                    correlation_type, competition_type
                )
                competition_results[correlation_type] = correlation_result
                
            except Exception as e:
                print(f"    ✗ Error analyzing {correlation_type}: {e}")
                competition_results[correlation_type] = {
                    'error': str(e),
                    'correlation_type': correlation_type,
                    'competition_type': competition_type
                }
        
        # Generate competition-level recommendations
        print("Generating competition-type recommendations...")
        competition_recommendations = self._generate_competition_recommendations(
            competition_results, competition_type
        )
        
        # Compile results
        results = {
            'metadata': {
                'competition_type': competition_type,
                'competition_type_description': config_info.get('description', ''),
                'analysis_date': datetime.now().isoformat(),
                'relevant_correlations': relevant_correlations,
                'percentiles': self.percentiles
            },
            'correlation_analyses': competition_results,
            'competition_recommendations': competition_recommendations
        }
        
        print(f"\nAnalysis complete for {competition_type}")
        return results
    
    def _load_complete_data(self, correlation_type: str) -> pd.DataFrame:
        """Load complete data for analysis"""
        print(f"Loading complete correlation dataset: {correlation_type}")
        complete_data = self.blob_loader.load_complete_correlation_data(correlation_type)
        print(f"Loaded {len(complete_data):,} total correlation values")
        return complete_data
    
    def _calculate_all_statistics_optimized(self, complete_data: pd.DataFrame) -> pd.DataFrame:
        """Calculate statistics for all features efficiently using vectorized operations"""
        print("Calculating feature statistics (optimized)...")
        
        # Group by feature and percentile for vectorized calculations
        grouped = complete_data.groupby(['feature_name', 'percentile'])['correlation_value']
        
        # Calculate all statistics at once
        stats_agg = grouped.agg([
            'count', 'mean', 'std', 'median', 'min', 'max',
            lambda x: x.quantile(0.25),
            lambda x: x.quantile(0.75)
        ]).reset_index()
        
        # Rename columns to match expected format
        stats_agg.columns = [
            'feature_name', 'percentile', 'sample_size', 'mean_correlation',
            'std_correlation', 'median_correlation', 'min_correlation', 
            'max_correlation', 'percentile_25', 'percentile_75'
        ]
        
        # Calculate coefficient of variation
        stats_agg['cv'] = stats_agg.apply(
            lambda row: abs(row['std_correlation'] / row['mean_correlation']) 
            if abs(row['mean_correlation']) > 0.01 else 0, axis=1
        )
        
        # Add required fields
        stats_agg['null_percentage'] = 0.0  # We filtered out nulls during blob loading
        
        print(f"✓ Calculated statistics for {len(stats_agg)} feature-percentile combinations")
        
        return stats_agg
    
    def _analyze_patterns(self, stats_df: pd.DataFrame) -> Tuple[Dict, Dict]:
        """Analyze patterns for all features"""
        # Calculate trends
        trend_results = {}
        for feature in stats_df['feature_name'].unique():
            feature_stats = stats_df[stats_df['feature_name'] == feature].sort_values('percentile')
            if len(feature_stats) >= 4:
                trend = self.stats_calculator.calculate_trend(
                    feature_stats['percentile'].values,
                    feature_stats['mean_correlation'].values
                )
                stability = self.stats_calculator.calculate_stability_metrics(feature_stats)
                trend_results[feature] = {**trend, **stability}
        
        # Classify patterns
        patterns = self.pattern_classifier.analyze_all_patterns(stats_df, trend_results)
        
        return patterns, trend_results
    
    def _calculate_quality_scores(self, patterns: Dict, stats_df: pd.DataFrame, 
                                trend_results: Dict) -> Tuple[Dict, Dict]:
        """Calculate quality scores and assign tiers"""
        # Calculate average null percentage per feature
        feature_null_stats = {}
        for feature in patterns.keys():
            feature_stats = stats_df[stats_df['feature_name'] == feature]
            # In this implementation, null percentage is 0 since we only have available data
            feature_null_stats[feature] = 0
        
        # Score all features
        quality_scores = self.quality_scorer.score_all_features(
            patterns, feature_null_stats, trend_results
        )
        
        # Assign tiers
        quality_scores, tiers = self.quality_scorer.assign_quality_tiers(quality_scores)
        
        return quality_scores, tiers
    
    def _group_features(self, patterns: Dict, tiers: Dict) -> Dict:
        """Group features by pattern and quality tier"""
        # Pattern groups
        pattern_groups = {}
        for feature, pattern_info in patterns.items():
            pattern_type = pattern_info['pattern_classification']
            if pattern_type not in pattern_groups:
                pattern_groups[pattern_type] = []
            pattern_groups[pattern_type].append(feature)
        
        # Sort features within each pattern group
        for pattern_type in pattern_groups:
            pattern_groups[pattern_type].sort()
        
        return {
            'pattern_groups': pattern_groups,
            'quality_tiers': tiers
        }
    
    def _recommend_percentiles(self, patterns: Dict, quality_scores: Dict, 
                             stats_df: pd.DataFrame) -> Dict:
        """Generate sophisticated percentile recommendations"""
        # Collect detailed scores for each percentile
        percentile_detailed_scores = {p: {'peak_features': [], 'strong_features': [], 
                                         'all_scores': []} for p in self.percentiles}
        
        elite_features = []  # Features that prefer lower percentiles
        inclusive_features = []  # Features that prefer higher percentiles
        stable_features = []  # Features stable across percentiles
        
        for feature, pattern_info in patterns.items():
            if feature not in quality_scores:
                continue
                
            optimal_p = pattern_info.get('optimal_percentile', 0)
            pattern_type = pattern_info['pattern_classification']
            quality_score = quality_scores[feature]['overall_score']
            
            # Categorize features
            if pattern_type == 'dilution' or (optimal_p <= 40 and pattern_type != 'stable'):
                elite_features.append(feature)
            elif pattern_type == 'concentration' or (optimal_p >= 80 and pattern_type != 'stable'):
                inclusive_features.append(feature)
            elif pattern_type == 'stable':
                stable_features.append(feature)
            
            # Record scores for each percentile
            feature_stats = stats_df[stats_df['feature_name'] == feature]
            for _, row in feature_stats.iterrows():
                p = row['percentile']
                score = abs(row['mean_correlation'])
                percentile_detailed_scores[p]['all_scores'].append(score)
                
                # Track peak and strong features
                if p == optimal_p:
                    percentile_detailed_scores[p]['peak_features'].append(feature)
                elif score >= 0.85 * quality_scores[feature].get('optimal_strength', 0):
                    percentile_detailed_scores[p]['strong_features'].append(feature)
        
        # Calculate percentile-level statistics
        percentile_analysis = {}
        for p in self.percentiles:
            scores = percentile_detailed_scores[p]['all_scores']
            if scores:
                percentile_analysis[p] = {
                    'peak_count': len(percentile_detailed_scores[p]['peak_features']),
                    'strong_count': len(percentile_detailed_scores[p]['strong_features']),
                    'mean_score': np.mean(scores),
                    'score_consistency': 1 - (np.std(scores) / np.mean(scores)) if np.mean(scores) > 0 else 0,
                    'peak_features': percentile_detailed_scores[p]['peak_features'][:5],
                    'strong_features': percentile_detailed_scores[p]['strong_features'][:5]
                }
            else:
                percentile_analysis[p] = {
                    'peak_count': 0, 'strong_count': 0, 'mean_score': 0,
                    'score_consistency': 0, 'peak_features': [], 'strong_features': []
                }
        
        # Create nuanced recommendations
        recommendations = {
            'analysis_type_recommendations': {
                'elite_performance_analysis': {
                    'recommended_percentiles': [30, 40],
                    'reasoning': f'Best for analyzing competitive dynamics among top performers. '
                               f'{len(elite_features)} features show strong preference for elite focus.',
                    'key_features': elite_features[:5]
                },
                'balanced_performance_analysis': {
                    'recommended_percentiles': [50, 60, 70],
                    'reasoning': 'Good compromise between competitive signal and field representation. '
                               'Ideal for general performance characterization.',
                    'key_features': stable_features[:5]
                },
                'inclusive_performance_analysis': {
                    'recommended_percentiles': [80, 90, 100],
                    'reasoning': f'Best for understanding full field dynamics. '
                               f'{len(inclusive_features)} features perform optimally with broader inclusion.',
                    'key_features': inclusive_features[:5]
                },
                'comparative_analysis': {
                    'recommended_percentiles': [30, 60, 90],
                    'reasoning': 'Strategic sampling across competitive levels for comparative studies.'
                }
            },
            
            'statistical_recommendations': {
                'highest_peak_performance': sorted(
                    percentile_analysis.keys(), 
                    key=lambda p: percentile_analysis[p]['peak_count'], 
                    reverse=True
                )[:3],
                'most_consistent_performance': sorted(
                    percentile_analysis.keys(), 
                    key=lambda p: percentile_analysis[p]['score_consistency'], 
                    reverse=True
                )[:3],
                'highest_average_correlations': sorted(
                    percentile_analysis.keys(), 
                    key=lambda p: percentile_analysis[p]['mean_score'], 
                    reverse=True
                )[:3]
            },
            
            'feature_behavior_summary': {
                'elite_preferring_features': len(elite_features),
                'inclusive_preferring_features': len(inclusive_features),
                'stable_across_percentiles_features': len(stable_features),
                'total_features_analyzed': len(patterns)
            },
            
            'traditional_sets': {
                'minimal_set': [30, 50, 80],
                'balanced_set': [30, 40, 60, 80, 90],
                'comprehensive_set': self.percentiles
            },
            
            'percentile_level_analysis': percentile_analysis
        }
        
        return recommendations
    
    def analyze_all_competition_types(self, output_dir: str = "./correlation_analysis_results",
                                    competition_types: List[str] = None) -> Dict[str, Dict]:
        """
        Run analysis for all competition types (race-type-first approach).
        
        Args:
            output_dir: Directory to save results
            competition_types: List of competition types to analyze
            
        Returns:
            Dictionary of all results
        """
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        all_results = {}
        
        print("="*80)
        print("CORRELATION FEATURE ANALYSIS - BATCH RUN (Race Type First)")
        print("="*80)
        print(f"Output directory: {output_path.absolute()}")
        
        # Use default competition types if not specified
        if competition_types is None:
            competition_types = list(self.competition_type_configs.keys())
            
        print(f"Competition types to analyze: {competition_types}")
        
        # Analyze each competition type
        for competition_type in competition_types:
            try:
                results = self.analyze_single_competition_type(competition_type)
                all_results[competition_type] = results
                
                # Save results
                self._save_results(results, output_path, competition_type)
                
            except Exception as e:
                print(f"\n✗ Error analyzing {competition_type}: {e}")
                import traceback
                traceback.print_exc()
        
        # Generate comparison report if multiple analyses
        if len(all_results) > 1:
            comparison_report = self._generate_comparison_report(all_results)
            comparison_filename = f"correlation_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(output_path / comparison_filename, 'w') as f:
                f.write(comparison_report)
            print(f"\n✓ Comparison report saved: {comparison_filename}")
        
        print("\n" + "="*80)
        print("CORRELATION FEATURE ANALYSIS COMPLETED (Race Type First)")
        print("="*80)
        
        return all_results
    
    def _analyze_correlation_for_competition(self, correlation_type: str, competition_type: str) -> Dict:
        """Analyze a specific correlation type for a specific competition type"""
        # Load complete data for the correlation type
        complete_data = self._load_complete_data(correlation_type)
        
        # Filter by competition type
        filtered_data = self.blob_loader.filter_by_competition_type(complete_data, competition_type)
        
        print(f"    Filtered to {len(filtered_data):,} correlation values")
        
        if len(filtered_data) == 0:
            return {
                'error': 'No data found',
                'correlation_type': correlation_type,
                'competition_type': competition_type
            }
        
        # Calculate statistics
        stats_df = self._calculate_all_statistics_optimized(filtered_data)
        
        # Analyze patterns
        patterns, trend_results = self._analyze_patterns(stats_df)
        
        # Calculate quality scores
        quality_scores, tiers = self._calculate_quality_scores(patterns, stats_df, trend_results)
        
        # Group features
        feature_groups = self._group_features(patterns, tiers)
        
        # Generate recommendations
        percentile_recommendations = self._recommend_percentiles(patterns, quality_scores, stats_df)
        
        return {
            'metadata': {
                'correlation_type': correlation_type,
                'competition_type': competition_type,
                'correlation_description': self.correlation_type_info.get(correlation_type, ''),
                'n_features_analyzed': len(patterns),
                'percentiles': self.percentiles
            },
            'feature_groups': feature_groups,
            'percentile_recommendations': percentile_recommendations,
            'patterns': patterns,
            'quality_scores': quality_scores,
            'trend_results': trend_results
        }
    
    def _generate_competition_recommendations(self, competition_results: Dict, competition_type: str) -> Dict:
        """Generate recommendations across correlation types for a competition type"""
        recommendations = {
            'best_correlation_type': None,
            'feature_overlap': {},
            'combined_recommendations': {}
        }
        
        # Find which correlation type has the most high-quality features
        best_score = 0
        for correlation_type, results in competition_results.items():
            if 'error' in results:
                continue
                
            tier_1_count = len(results.get('feature_groups', {}).get('quality_tiers', {}).get('tier_1_high_quality', []))
            if tier_1_count > best_score:
                best_score = tier_1_count
                recommendations['best_correlation_type'] = correlation_type
        
        # Analyze feature overlap between correlation types
        all_tier_1_features = {}
        for correlation_type, results in competition_results.items():
            if 'error' in results:
                continue
            tier_1_features = results.get('feature_groups', {}).get('quality_tiers', {}).get('tier_1_high_quality', [])
            all_tier_1_features[correlation_type] = set(tier_1_features)
        
        # Find overlapping high-quality features
        if len(all_tier_1_features) > 1:
            correlation_types = list(all_tier_1_features.keys())
            overlap = all_tier_1_features[correlation_types[0]]
            for ct in correlation_types[1:]:
                overlap = overlap.intersection(all_tier_1_features[ct])
            recommendations['feature_overlap']['high_quality_overlap'] = list(overlap)
        
        return recommendations
    
    def _save_results(self, results: Dict, output_path: Path, analysis_key: str):
        """Save analysis results"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON
        json_filename = f"correlation_analysis_{analysis_key}_{timestamp}.json"
        with open(output_path / json_filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save markdown report
        report_filename = f"correlation_analysis_{analysis_key}_report_{timestamp}.md"
        report = self._generate_summary_report(results)
        with open(output_path / report_filename, 'w') as f:
            f.write(report)
        
        print(f"\n✓ Completed analysis for {analysis_key}")
        print(f"  - JSON saved: {json_filename}")
        print(f"  - Report saved: {report_filename}")
    
    def _generate_summary_report(self, results: Dict) -> str:
        """Generate a summary report for race-type-first structure"""
        report = []
        metadata = results.get('metadata', {})
        
        # Header
        competition_type = metadata.get('competition_type', 'Unknown')
        competition_desc = metadata.get('competition_type_description', competition_type)
        report.append(f"# Correlation Feature Analysis: {competition_desc}")
        report.append(f"\nAnalysis Date: {metadata.get('analysis_date', 'Unknown')}")
        report.append(f"Competition Type: {competition_type}")
        report.append(f"Relevant Correlation Types: {metadata.get('relevant_correlations', [])}")
        report.append(f"Percentiles: {metadata.get('percentiles', [])}")
        
        # Process each correlation analysis
        correlation_analyses = results.get('correlation_analyses', {})
        
        for correlation_type, analysis_result in correlation_analyses.items():
            if 'error' in analysis_result:
                report.append(f"\n## {correlation_type.replace('_', ' ').title()} Correlations")
                report.append(f"❌ Error: {analysis_result['error']}")
                continue
                
            analysis_metadata = analysis_result.get('metadata', {})
            n_features = analysis_metadata.get('n_features_analyzed', 0)
            
            report.append(f"\n## {correlation_type.replace('_', ' ').title()} Correlations")
            report.append(f"**Description**: {analysis_metadata.get('correlation_description', '')}")
            report.append(f"**Features Analyzed**: {n_features}")
            
            # Get quality scores from the analysis result
            quality_scores = analysis_result.get('quality_scores', {})
            if quality_scores:
                # Top features by quality
                report.append(f"\n### Top 10 Features by Quality Score")
                sorted_features = sorted(quality_scores.items(), 
                                       key=lambda x: x[1].get('overall_score', 0), 
                                       reverse=True)[:10]
                
                for i, (feature, scores) in enumerate(sorted_features):
                    overall_score = scores.get('overall_score', 0)
                    report.append(f"{i+1}. {feature}: {overall_score:.3f}")
            
            # Feature patterns
            feature_groups = analysis_result.get('feature_groups', {})
            if 'pattern_groups' in feature_groups:
                report.append(f"\n### Feature Behavior Patterns")
                pattern_groups = feature_groups['pattern_groups']
                for pattern, features in pattern_groups.items():
                    if features:
                        report.append(f"\n**{pattern.capitalize()} Features ({len(features)})**")
                        report.append(f"{', '.join(sorted(features)[:10])}")
            
            # Percentile recommendations
            p_recs = analysis_result.get('percentile_recommendations', {})
            if 'analysis_type_recommendations' in p_recs:
                report.append(f"\n### Percentile Recommendations by Analysis Type")
                
                for analysis_type, rec in p_recs['analysis_type_recommendations'].items():
                    analysis_name = analysis_type.replace('_', ' ').title()
                    report.append(f"\n**{analysis_name}**")
                    report.append(f"- Recommended percentiles: {rec['recommended_percentiles']}")
                    report.append(f"- Reasoning: {rec['reasoning']}")
                    if rec.get('key_features'):
                        report.append(f"- Key features: {', '.join(rec['key_features'])}")
            
            if 'feature_behavior_summary' in p_recs:
                summary = p_recs['feature_behavior_summary']
                report.append(f"\n### Feature Behavior Summary")
                report.append(f"- **Elite-preferring features**: {summary.get('elite_preferring_features', 0)}")
                report.append(f"- **Inclusive-preferring features**: {summary.get('inclusive_preferring_features', 0)}")
                report.append(f"- **Stable across percentiles**: {summary.get('stable_across_percentiles_features', 0)}")
                report.append(f"- **Total features analyzed**: {summary.get('total_features_analyzed', 0)}")
            
            # Quality tiers
            if 'quality_tiers' in feature_groups:
                report.append(f"\n### Feature Quality Tiers")
                tiers = feature_groups['quality_tiers']
                for tier, features in tiers.items():
                    if features:
                        tier_display = tier.replace('_', ' ').title()
                        report.append(f"\n**{tier_display} ({len(features)} features)**")
                        report.append(f"{', '.join(sorted(features)[:15])}")
        
        # Competition-level recommendations
        comp_recs = results.get('competition_recommendations', {})
        if comp_recs:
            report.append(f"\n## Competition-Level Recommendations")
            
            best_correlation_type = comp_recs.get('best_correlation_type')
            if best_correlation_type:
                report.append(f"- **Best correlation type**: {best_correlation_type} (highest number of high-quality features)")
            
            feature_overlap = comp_recs.get('feature_overlap', {})
            if feature_overlap.get('high_quality_overlap'):
                overlap_features = feature_overlap['high_quality_overlap']
                report.append(f"- **High-quality feature overlap**: {len(overlap_features)} features consistently high-quality across correlation types")
                if overlap_features:
                    report.append(f"  - {', '.join(overlap_features[:10])}")
        
        return "\n".join(report)
    
    def _generate_comparison_report(self, all_results: Dict[str, Dict]) -> str:
        """Generate a comparison report across analyses"""
        report = []
        report.append("# Correlation Feature Analysis Comparison")
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Overview table
        report.append("\n## Analysis Overview")
        report.append("| Analysis Key | Features Analyzed | Top Quality Feature | Top Quality Score |")
        report.append("|--------------|-------------------|--------------------|--------------------|")
        
        for key, results in all_results.items():
            metadata = results.get('metadata', {})
            n_features = metadata.get('n_features_analyzed', 0)
            
            # Find top quality feature
            feature_keys = [k for k in results.keys() if k not in ['feature_groups', 'percentile_recommendations', 'metadata']]
            if feature_keys:
                quality_scores = [(f, results[f].get('quality_score', 0)) for f in feature_keys]
                quality_scores.sort(key=lambda x: x[1], reverse=True)
                top_feature, top_score = quality_scores[0]
            else:
                top_feature, top_score = "None", 0
            
            report.append(f"| {key} | {n_features} | {top_feature} | {top_score:.3f} |")
        
        # Pattern distribution comparison
        report.append("\n## Feature Pattern Distribution")
        
        # Collect all pattern types
        all_patterns = set()
        for results in all_results.values():
            if 'feature_groups' in results and 'pattern_groups' in results['feature_groups']:
                all_patterns.update(results['feature_groups']['pattern_groups'].keys())
        
        for pattern in sorted(all_patterns):
            report.append(f"\n### {pattern.capitalize()} Features")
            report.append("| Analysis Key | Count | Example Features |")
            report.append("|--------------|-------|------------------|")
            
            for key, results in all_results.items():
                if 'feature_groups' in results and 'pattern_groups' in results['feature_groups']:
                    pattern_features = results['feature_groups']['pattern_groups'].get(pattern, [])
                    count = len(pattern_features)
                    examples = ", ".join(pattern_features[:3])
                else:
                    count = 0
                    examples = ""
                
                report.append(f"| {key} | {count} | {examples} |")
        
        return "\n".join(report)
    
    def close(self):
        """Close database connection"""
        self.blob_loader.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()