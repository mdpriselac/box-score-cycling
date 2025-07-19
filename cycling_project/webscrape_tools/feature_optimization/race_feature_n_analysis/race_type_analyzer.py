import numpy as np
import pandas as pd
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path

from .race_type_filtered_analyzer import (
    RaceTypeFilteredVariabilityAnalyzer,
    RaceTypeFilteredMonotonicityAnalyzer, 
    RaceTypeFilteredDistinctivenessAnalyzer,
    RaceTypeFilteredPatternClassifier
)


class RaceTypeAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        
        # Define race type configurations
        self.race_type_configs = {
            'gc': 'gc',
            'stage': 'stage', 
            'one_day': 'one_day',
            'stage_one_day': ['stage', 'one_day'],  # Combined category
            'all_types': None  # No filter = all races
        }
    
    def _get_race_type_description(self, race_type_key: str) -> str:
        """Get a human-readable description of the race type filter"""
        config = self.race_type_configs[race_type_key]
        
        if config is None:
            return "All Race Types"
        elif isinstance(config, str):
            return f"{config.replace('_', ' ').title()} Races"
        elif isinstance(config, list):
            return f"{' + '.join([t.replace('_', ' ').title() for t in config])} Races"
        else:
            return str(config)
    
    def analyze_single_race_type(self, race_type_key: str) -> Dict:
        """Run analysis for a single race type configuration"""
        race_type_filter = self.race_type_configs[race_type_key]
        
        print(f"\n{'='*60}")
        print(f"Analyzing: {self._get_race_type_description(race_type_key)}")
        print(f"Filter: {race_type_filter}")
        print(f"{'='*60}")
        
        # Initialize analyzers with race type filter
        variability_analyzer = RaceTypeFilteredVariabilityAnalyzer(self.db_path, race_type_filter)
        monotonicity_analyzer = RaceTypeFilteredMonotonicityAnalyzer(self.db_path, race_type_filter)
        distinctiveness_analyzer = RaceTypeFilteredDistinctivenessAnalyzer(self.db_path, race_type_filter)
        pattern_classifier = RaceTypeFilteredPatternClassifier(self.db_path, race_type_filter)
        
        feature_columns = variability_analyzer.feature_columns
        results = {}
        
        print(f"Analyzing {len(feature_columns)} features across N levels: {self.n_levels}")
        
        # Analyze each feature
        for i, feature in enumerate(feature_columns):
            print(f"\nAnalyzing feature {i+1}/{len(feature_columns)}: {feature}")
            
            try:
                # Check if we have enough data for this race type
                sample_data = variability_analyzer.get_feature_values(feature, 50)
                if len(sample_data) < 10:
                    print(f"  ! Skipping {feature} - insufficient data ({len(sample_data)} samples)")
                    continue
                
                # Variability analysis
                print(f"  - Running variability analysis...")
                variability_metrics, variability_trends = variability_analyzer.analyze_feature_across_n(feature)
                
                # Monotonicity analysis
                print(f"  - Running monotonicity analysis...")
                monotonicity_results = {
                    'monotonicity': monotonicity_analyzer.analyze_monotonicity(feature),
                    'trajectories': monotonicity_analyzer.analyze_feature_trajectories(feature)
                }
                
                # Distinctiveness analysis
                print(f"  - Running distinctiveness analysis...")
                distinctiveness_results = distinctiveness_analyzer.analyze_feature_discriminative_power(feature)
                
                # Pattern classification
                print(f"  - Classifying behavior patterns...")
                pattern_results = pattern_classifier.classify_feature_behavior(feature)
                
                # Calculate scores using the same logic as the original analyzer
                stability_score = self._calculate_stability_score(variability_metrics, variability_trends)
                information_score = self._calculate_information_score(distinctiveness_results)
                quality_score = self._calculate_quality_score(stability_score, information_score, monotonicity_results)
                
                # Compile results
                results[feature] = {
                    'variability_analysis': (variability_metrics, variability_trends),
                    'monotonicity': monotonicity_results,
                    'distinctiveness': distinctiveness_results,
                    'behavior_pattern': pattern_results,
                    'stability_score': stability_score,
                    'information_score': information_score,
                    'quality_score': quality_score
                }
                
            except Exception as e:
                print(f"  ! Error analyzing {feature}: {e}")
                continue
        
        # Group-level analyses
        print("\nPerforming group-level analyses...")
        
        # Pattern groups
        pattern_classifications = {}
        for feature, result in results.items():
            if 'behavior_pattern' in result:
                pattern_classifications[feature] = result['behavior_pattern']
        
        pattern_groups = self._group_features_by_pattern(pattern_classifications)
        
        # Quality tiers
        quality_tiers = self._create_quality_tiers(results)
        
        # N-level recommendations
        n_recommendations = self._recommend_n_levels(results)
        
        # Add group results
        results['feature_groups'] = {
            'pattern_groups': pattern_groups,
            'quality_tiers': quality_tiers
        }
        
        results['n_recommendations'] = n_recommendations
        
        # Add metadata
        results['metadata'] = {
            'analysis_date': datetime.now().isoformat(),
            'race_type_key': race_type_key,
            'race_type_filter': race_type_filter,
            'race_type_description': self._get_race_type_description(race_type_key),
            'n_features_analyzed': len([k for k in results.keys() if k not in ['feature_groups', 'n_recommendations', 'metadata']]),
            'n_levels': self.n_levels,
            'db_path': self.db_path
        }
        
        # Clean up connections
        variability_analyzer.close_connection()
        monotonicity_analyzer.close_connection()
        distinctiveness_analyzer.close_connection()
        
        return results
    
    def _calculate_stability_score(self, metrics, trends):
        """Calculate stability score like the original analyzer"""
        if not metrics:
            return 0
        
        cv_values = [m.cv for m in metrics.values()]
        cv_stability = 1 - (np.std(cv_values) / (np.mean(cv_values) + 1e-10))
        
        mean_values = [m.mean for m in metrics.values()]
        mean_stability = 1 - (np.std(mean_values) / (np.mean(mean_values) + 1e-10))
        
        trend_stability = 1 - trends.get('cv_r2', 0)
        
        return np.mean([cv_stability, mean_stability, trend_stability])
    
    def _calculate_information_score(self, distinctiveness_results):
        """Calculate information score like the original analyzer"""
        if not distinctiveness_results or 'information_gain' not in distinctiveness_results:
            return 0
        
        ig_scores = []
        for target_results in distinctiveness_results['information_gain'].values():
            if 'mean_ig' in target_results:
                ig_scores.append(target_results['mean_ig'])
        
        if not ig_scores:
            return 0
        
        mean_distinctiveness = distinctiveness_results['distinctiveness'].get('mean_distinctiveness', 0)
        mean_ig = np.mean(ig_scores)
        
        return (mean_distinctiveness + mean_ig) / 2
    
    def _calculate_quality_score(self, stability_score, information_score, monotonicity_results):
        """Calculate overall quality score"""
        quality_components = [stability_score, information_score]
        
        if 'monotonicity' in monotonicity_results and 'monotonicity' in monotonicity_results:
            mono = monotonicity_results['monotonicity']
            monotonicity_score = abs(mono.spearman_correlation) * mono.linearity_r2
            quality_components.append(monotonicity_score)
        
        return np.mean(quality_components) if quality_components else 0
    
    def _group_features_by_pattern(self, pattern_classifications):
        """Group features by their behavior patterns"""
        pattern_groups = {
            'stable': [],
            'dilution': [],
            'concentration': [],
            'threshold': [],
            'bimodal': [],
            'complex': []
        }
        
        for feature, pattern in pattern_classifications.items():
            if pattern.primary_pattern.startswith('threshold'):
                pattern_groups['threshold'].append(feature)
            else:
                pattern_groups[pattern.primary_pattern].append(feature)
            
            if any(pattern.bimodality_pattern.values()):
                pattern_groups['bimodal'].append(feature)
        
        return pattern_groups
    
    def _create_quality_tiers(self, results):
        """Create quality-based tiers"""
        quality_scores = []
        
        for feature in results.keys():
            if feature not in ['feature_groups', 'n_recommendations', 'metadata']:
                score = results[feature].get('quality_score', 0)
                quality_scores.append((feature, score))
        
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        
        n_features = len(quality_scores)
        tier_size = n_features // 3
        
        tiers = {
            'tier_1_high_quality': [f[0] for f in quality_scores[:tier_size]],
            'tier_2_medium_quality': [f[0] for f in quality_scores[tier_size:2*tier_size]],
            'tier_3_low_quality': [f[0] for f in quality_scores[2*tier_size:]]
        }
        
        return tiers
    
    def _recommend_n_levels(self, results):
        """Recommend optimal N levels with nuanced interpretation"""
        
        # Collect detailed scores for each N level
        n_detailed_scores = {n: {'peak_features': [], 'strong_features': [], 'all_scores': []} 
                            for n in self.n_levels}
        
        elite_features = []  # Features that strongly prefer lower N
        inclusive_features = []  # Features that prefer higher N
        stable_features = []  # Features that work well across N levels
        
        feature_count = len([k for k in results.keys() if k not in ['feature_groups', 'n_recommendations', 'metadata']])
        
        for feature, feature_results in results.items():
            if feature not in ['feature_groups', 'n_recommendations', 'metadata']:
                if 'distinctiveness' in feature_results:
                    combined_scores = feature_results['distinctiveness'].get('combined_scores', {})
                    optimal_n = feature_results['distinctiveness'].get('optimal_n')
                    
                    if combined_scores:
                        # Find peak and analyze score distribution
                        max_score = max(combined_scores.values())
                        min_score = min(combined_scores.values())
                        score_range = max_score - min_score
                        
                        # Categorize feature behavior
                        if optimal_n and optimal_n <= 40 and score_range > 0.05:
                            elite_features.append(feature)
                        elif optimal_n and optimal_n >= 80 and score_range > 0.05:
                            inclusive_features.append(feature)
                        elif score_range <= 0.05:  # Very stable across N
                            stable_features.append(feature)
                        
                        # Record detailed scores
                        for n, score in combined_scores.items():
                            n_detailed_scores[n]['all_scores'].append(score)
                            
                            # Count as "peak" if within 5% of max score
                            if score >= 0.95 * max_score:
                                n_detailed_scores[n]['peak_features'].append(feature)
                            
                            # Count as "strong" if within 15% of max score
                            elif score >= 0.85 * max_score:
                                n_detailed_scores[n]['strong_features'].append(feature)
        
        # Calculate summary statistics
        n_analysis = {}
        for n in self.n_levels:
            scores = n_detailed_scores[n]['all_scores']
            if scores:
                n_analysis[n] = {
                    'peak_count': len(n_detailed_scores[n]['peak_features']),
                    'strong_count': len(n_detailed_scores[n]['strong_features']),
                    'mean_score': np.mean(scores),
                    'score_consistency': 1 - (np.std(scores) / np.mean(scores)) if np.mean(scores) > 0 else 0,
                    'peak_features': n_detailed_scores[n]['peak_features'][:5],  # Top 5 for reporting
                    'strong_features': n_detailed_scores[n]['strong_features'][:5]
                }
            else:
                n_analysis[n] = {
                    'peak_count': 0, 'strong_count': 0, 'mean_score': 0, 
                    'score_consistency': 0, 'peak_features': [], 'strong_features': []
                }
        
        # Create nuanced recommendations
        recommendations = {
            'analysis_type_recommendations': {
                'elite_competition_analysis': {
                    'recommended_n': [30, 40],
                    'reasoning': f'Best for analyzing competitive dynamics among top performers. {len(elite_features)} features show strong preference for elite focus.',
                    'key_features': elite_features[:5]
                },
                'balanced_field_analysis': {
                    'recommended_n': [50, 60, 70],
                    'reasoning': 'Good compromise between competitive signal and field representation.',
                    'key_features': stable_features[:5]
                },
                'inclusive_field_analysis': {
                    'recommended_n': [80, 90, 100],
                    'reasoning': f'Best for understanding full field dynamics. {len(inclusive_features)} features perform optimally with broader inclusion.',
                    'key_features': inclusive_features[:5]
                },
                'comparative_analysis': {
                    'recommended_n': [30, 60, 90],
                    'reasoning': 'Strategic sampling across competitive levels for comparative studies.'
                }
            },
            
            'statistical_recommendations': {
                'highest_peak_performance': sorted(n_analysis.keys(), key=lambda n: n_analysis[n]['peak_count'], reverse=True)[:3],
                'most_consistent_performance': sorted(n_analysis.keys(), key=lambda n: n_analysis[n]['score_consistency'], reverse=True)[:3],
                'highest_average_scores': sorted(n_analysis.keys(), key=lambda n: n_analysis[n]['mean_score'], reverse=True)[:3]
            },
            
            'feature_behavior_summary': {
                'elite_preferring_features': len(elite_features),
                'inclusive_preferring_features': len(inclusive_features),
                'stable_across_n_features': len(stable_features),
                'total_features_analyzed': feature_count
            },
            
            'traditional_sets': {
                'minimal_set': [30, 50, 80],  # Strategic sampling
                'balanced_set': [30, 40, 60, 80, 90],  # More comprehensive
                'comprehensive_set': self.n_levels
            },
            
            'n_level_analysis': n_analysis
        }
        
        return recommendations
    
    def analyze_all_race_types(self, output_dir: str = "./race_type_analysis_results") -> Dict[str, Dict]:
        """Run analysis for all race type configurations"""
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        all_results = {}
        
        print("="*80)
        print("RACE TYPE ANALYSIS - BATCH RUN")
        print("="*80)
        print(f"Output directory: {output_path.absolute()}")
        print(f"Race type configurations: {list(self.race_type_configs.keys())}")
        
        for race_type_key in self.race_type_configs.keys():
            try:
                # Run analysis for this race type
                results = self.analyze_single_race_type(race_type_key)
                all_results[race_type_key] = results
                
                # Save individual results
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                json_filename = f"race_analysis_{race_type_key}_{timestamp}.json"
                report_filename = f"race_analysis_{race_type_key}_report_{timestamp}.md"
                
                # Save JSON
                self._save_results(results, output_path / json_filename)
                
                # Save markdown report
                report = self._generate_summary_report(results)
                with open(output_path / report_filename, 'w') as f:
                    f.write(report)
                
                print(f"\n✓ Completed analysis for {race_type_key}")
                print(f"  - JSON saved: {json_filename}")
                print(f"  - Report saved: {report_filename}")
                
            except Exception as e:
                print(f"\n✗ Error analyzing {race_type_key}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Generate comparison report
        if len(all_results) > 1:
            comparison_report = self._generate_comparison_report(all_results)
            comparison_filename = f"race_type_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(output_path / comparison_filename, 'w') as f:
                f.write(comparison_report)
            print(f"\n✓ Comparison report saved: {comparison_filename}")
        
        print("\n" + "="*80)
        print("RACE TYPE ANALYSIS COMPLETED")
        print("="*80)
        
        return all_results
    
    def _save_results(self, results: Dict, output_path: Path):
        """Save results to JSON with proper serialization"""
        def convert_to_serializable(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif hasattr(obj, '__dict__') and not isinstance(obj, type):
                try:
                    return {k: convert_to_serializable(v) for k, v in obj.__dict__.items() 
                           if not k.startswith('_') and not callable(v)}
                except:
                    return str(obj)
            elif isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_to_serializable(item) for item in obj]
            elif callable(obj):
                return None
            else:
                try:
                    json.dumps(obj)
                    return obj
                except:
                    return str(obj)
        
        serializable_results = convert_to_serializable(results)
        
        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
    
    def _generate_summary_report(self, results: Dict) -> str:
        """Generate a summary report for a single race type"""
        report = []
        metadata = results.get('metadata', {})
        
        report.append(f"# Race Feature Analysis: {metadata.get('race_type_description', 'Unknown')}")
        report.append(f"\nAnalysis Date: {metadata.get('analysis_date', 'Unknown')}")
        report.append(f"Race Type Filter: {metadata.get('race_type_filter', 'None')}")
        report.append(f"Features Analyzed: {metadata.get('n_features_analyzed', 0)}")
        report.append(f"N Levels: {metadata.get('n_levels', [])}")
        
        # Get feature list (excluding metadata keys)
        feature_keys = [k for k in results.keys() if k not in ['feature_groups', 'n_recommendations', 'metadata']]
        
        # Top features by quality
        report.append("\n## Top 10 Features by Quality Score")
        quality_scores = [(f, results[f].get('quality_score', 0)) for f in feature_keys]
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        
        for i, (feature, score) in enumerate(quality_scores[:10]):
            report.append(f"{i+1}. {feature}: {score:.3f}")
        
        # Feature patterns
        if 'feature_groups' in results and 'pattern_groups' in results['feature_groups']:
            report.append("\n## Feature Behavior Patterns")
            pattern_groups = results['feature_groups']['pattern_groups']
            for pattern, features in pattern_groups.items():
                if features:  # Only show patterns that have features
                    report.append(f"\n### {pattern.capitalize()} Features ({len(features)})")
                    report.append(", ".join(features))
        
        # N-level recommendations
        if 'n_recommendations' in results:
            n_recs = results['n_recommendations']
            
            report.append("\n## N-Level Recommendations by Analysis Type")
            
            if 'analysis_type_recommendations' in n_recs:
                for analysis_type, rec in n_recs['analysis_type_recommendations'].items():
                    analysis_name = analysis_type.replace('_', ' ').title()
                    report.append(f"\n### {analysis_name}")
                    report.append(f"**Recommended N levels**: {rec['recommended_n']}")
                    report.append(f"**Reasoning**: {rec['reasoning']}")
                    if rec.get('key_features'):
                        report.append(f"**Key features**: {', '.join(rec['key_features'])}")
            
            if 'feature_behavior_summary' in n_recs:
                summary = n_recs['feature_behavior_summary']
                report.append(f"\n## Feature Behavior Summary")
                report.append(f"- **Elite-preferring features**: {summary['elite_preferring_features']}")
                report.append(f"- **Inclusive-preferring features**: {summary['inclusive_preferring_features']}")
                report.append(f"- **Stable across N features**: {summary['stable_across_n_features']}")
                report.append(f"- **Total features analyzed**: {summary['total_features_analyzed']}")
            
            if 'traditional_sets' in n_recs:
                trad = n_recs['traditional_sets']
                report.append(f"\n## Traditional N-Level Sets")
                report.append(f"- **Minimal Set**: {trad.get('minimal_set', [])} (strategic sampling)")
                report.append(f"- **Balanced Set**: {trad.get('balanced_set', [])} (comprehensive coverage)")
                report.append(f"- **Comprehensive Set**: All N levels")
            
            if 'statistical_recommendations' in n_recs:
                stats_recs = n_recs['statistical_recommendations']
                report.append(f"\n## Statistical Performance Rankings")
                report.append(f"- **Best peak performance**: {stats_recs.get('highest_peak_performance', [])}")
                report.append(f"- **Most consistent**: {stats_recs.get('most_consistent_performance', [])}")
                report.append(f"- **Highest average scores**: {stats_recs.get('highest_average_scores', [])}")
        
        # Quality tiers
        if 'feature_groups' in results and 'quality_tiers' in results['feature_groups']:
            report.append("\n## Feature Quality Tiers")
            tiers = results['feature_groups']['quality_tiers']
            for tier, features in tiers.items():
                if features:  # Only show tiers that have features
                    report.append(f"\n### {tier} ({len(features)} features)")
                    report.append(", ".join(features))
        
        return "\n".join(report)
    
    def _generate_comparison_report(self, all_results: Dict[str, Dict]) -> str:
        """Generate a comparison report across race types"""
        report = []
        report.append("# Race Type Comparison Analysis")
        report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Overview table
        report.append("\n## Analysis Overview")
        report.append("| Race Type | Features Analyzed | Top Quality Feature | Top Quality Score |")
        report.append("|-----------|-------------------|--------------------|--------------------|")
        
        for race_type, results in all_results.items():
            metadata = results.get('metadata', {})
            n_features = metadata.get('n_features_analyzed', 0)
            description = metadata.get('race_type_description', race_type)
            
            # Find top quality feature
            feature_keys = [k for k in results.keys() if k not in ['feature_groups', 'n_recommendations', 'metadata']]
            if feature_keys:
                quality_scores = [(f, results[f].get('quality_score', 0)) for f in feature_keys]
                quality_scores.sort(key=lambda x: x[1], reverse=True)
                top_feature, top_score = quality_scores[0]
            else:
                top_feature, top_score = "None", 0
            
            report.append(f"| {description} | {n_features} | {top_feature} | {top_score:.3f} |")
        
        # Feature behavior comparison
        report.append("\n## Feature Behavior Patterns by Race Type")
        
        # Collect all pattern types
        all_patterns = set()
        for results in all_results.values():
            if 'feature_groups' in results and 'pattern_groups' in results['feature_groups']:
                all_patterns.update(results['feature_groups']['pattern_groups'].keys())
        
        for pattern in sorted(all_patterns):
            report.append(f"\n### {pattern.capitalize()} Features")
            report.append("| Race Type | Count | Examples |")
            report.append("|-----------|-------|----------|")
            
            for race_type, results in all_results.items():
                description = results.get('metadata', {}).get('race_type_description', race_type)
                if 'feature_groups' in results and 'pattern_groups' in results['feature_groups']:
                    pattern_features = results['feature_groups']['pattern_groups'].get(pattern, [])
                    count = len(pattern_features)
                    examples = ", ".join(pattern_features)
                else:
                    count = 0
                    examples = ""
                
                report.append(f"| {description} | {count} | {examples} |")
        
        return "\n".join(report)