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
        """Recommend optimal N levels"""
        n_scores = {n: [] for n in self.n_levels}
        
        for feature, feature_results in results.items():
            if feature not in ['feature_groups', 'n_recommendations', 'metadata']:
                if 'distinctiveness' in feature_results and 'optimal_range' in feature_results['distinctiveness']:
                    optimal_range = feature_results['distinctiveness']['optimal_range']
                    for n in optimal_range:
                        if n in n_scores:
                            n_scores[n].append(1)
        
        n_importance = {}
        feature_count = len([k for k in results.keys() if k not in ['feature_groups', 'n_recommendations', 'metadata']])
        
        for n, scores in n_scores.items():
            n_importance[n] = len(scores) / feature_count if feature_count > 0 else 0
        
        sorted_n = sorted(n_importance.items(), key=lambda x: x[1], reverse=True)
        
        recommendations = {
            'minimal_set': [],
            'balanced_set': [],
            'comprehensive_set': self.n_levels
        }
        
        # Build recommendations
        cumulative_importance = 0
        for n, importance in sorted_n:
            recommendations['minimal_set'].append(n)
            cumulative_importance += importance
            if cumulative_importance >= 0.6:
                break
        
        cumulative_importance = 0
        for n, importance in sorted_n:
            if n not in recommendations['balanced_set']:
                recommendations['balanced_set'].append(n)
            cumulative_importance += importance
            if cumulative_importance >= 0.85:
                break
        
        recommendations['minimal_set'].sort()
        recommendations['balanced_set'].sort()
        
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
            report.append("\n## Recommended N Levels")
            n_recs = results['n_recommendations']
            report.append(f"- Minimal Set (60% coverage): {n_recs.get('minimal_set', [])}")
            report.append(f"- Balanced Set (85% coverage): {n_recs.get('balanced_set', [])}")
            report.append(f"- Comprehensive Set: {n_recs.get('comprehensive_set', [])}")
        
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