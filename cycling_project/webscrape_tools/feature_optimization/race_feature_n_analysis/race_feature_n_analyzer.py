import numpy as np
import pandas as pd
import json
from datetime import datetime
import sqlite3
from typing import Dict, List, Tuple, Optional
from pathlib import Path

from .feature_variability_analyzer import FeatureVariabilityAnalyzer, VariabilityMetrics
from .monotonicity_analyzer import MonotonicityAnalyzer
from .distinctiveness_analyzer import DistinctivenessAnalyzer
from .feature_pattern_classifier import FeaturePatternClassifier


class RaceFeatureNAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        
        # Initialize sub-analyzers
        self.variability_analyzer = FeatureVariabilityAnalyzer(db_path)
        self.monotonicity_analyzer = MonotonicityAnalyzer(db_path)
        self.distinctiveness_analyzer = DistinctivenessAnalyzer(db_path)
        self.pattern_classifier = FeaturePatternClassifier(db_path)
        
        self.feature_columns = self.variability_analyzer.feature_columns
    
    def calculate_overall_stability(self, feature_name: str, variability_results: Dict) -> float:
        metrics, trends = variability_results
        
        if not metrics:
            return 0
        
        # Calculate CV stability across N
        cv_values = [m.cv for m in metrics.values()]
        cv_stability = 1 - (np.std(cv_values) / (np.mean(cv_values) + 1e-10))
        
        # Calculate mean stability
        mean_values = [m.mean for m in metrics.values()]
        mean_stability = 1 - (np.std(mean_values) / (np.mean(mean_values) + 1e-10))
        
        # Consider trend stability (low R² means less predictable change)
        trend_stability = 1 - trends.get('cv_r2', 0)
        
        return np.mean([cv_stability, mean_stability, trend_stability])
    
    def calculate_overall_information_value(self, feature_name: str, distinctiveness_results: Dict) -> float:
        if not distinctiveness_results or 'information_gain' not in distinctiveness_results:
            return 0
        
        # Average information gain across all targets
        ig_scores = []
        for target_results in distinctiveness_results['information_gain'].values():
            if 'mean_ig' in target_results:
                ig_scores.append(target_results['mean_ig'])
        
        if not ig_scores:
            return 0
        
        # Combine with distinctiveness score
        mean_distinctiveness = distinctiveness_results['distinctiveness'].get('mean_distinctiveness', 0)
        mean_ig = np.mean(ig_scores)
        
        return (mean_distinctiveness + mean_ig) / 2
    
    def calculate_overall_quality(self, feature_name: str, all_results: Dict) -> float:
        quality_components = []
        
        # Stability component
        if 'variability_analysis' in all_results:
            stability = self.calculate_overall_stability(feature_name, all_results['variability_analysis'])
            quality_components.append(stability)
        
        # Information value component
        if 'distinctiveness' in all_results:
            info_value = self.calculate_overall_information_value(feature_name, all_results['distinctiveness'])
            quality_components.append(info_value)
        
        # Monotonicity component (prefer features with clear trends)
        if 'monotonicity' in all_results and 'monotonicity' in all_results['monotonicity']:
            mono = all_results['monotonicity']['monotonicity']
            monotonicity_score = abs(mono.spearman_correlation) * mono.linearity_r2
            quality_components.append(monotonicity_score)
        
        return np.mean(quality_components) if quality_components else 0
    
    def create_quality_based_tiers(self, results: Dict) -> Dict[str, List[str]]:
        # Calculate quality scores for all features
        quality_scores = []
        
        for feature in self.feature_columns:
            if feature in results:
                score = results[feature].get('quality_score', 0)
                quality_scores.append((feature, score))
        
        # Sort by quality score
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Create tiers
        n_features = len(quality_scores)
        tier_size = n_features // 3
        
        tiers = {
            'tier_1_high_quality': [f[0] for f in quality_scores[:tier_size]],
            'tier_2_medium_quality': [f[0] for f in quality_scores[tier_size:2*tier_size]],
            'tier_3_low_quality': [f[0] for f in quality_scores[2*tier_size:]]
        }
        
        return tiers
    
    def recommend_n_levels(self, results: Dict) -> Dict:
        """Recommend optimal N levels with nuanced interpretation"""
        
        # Collect detailed scores for each N level
        n_detailed_scores = {n: {'peak_features': [], 'strong_features': [], 'all_scores': []} 
                            for n in self.n_levels}
        
        elite_features = []  # Features that strongly prefer lower N
        inclusive_features = []  # Features that prefer higher N
        stable_features = []  # Features that work well across N levels
        
        for feature, feature_results in results.items():
            if feature in self.feature_columns:
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
                    'peak_features': n_detailed_scores[n]['peak_features'][:5],
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
                'total_features_analyzed': len(self.feature_columns)
            },
            
            'traditional_sets': {
                'minimal_set': [30, 50, 80],  # Strategic sampling
                'balanced_set': [30, 40, 60, 80, 90],  # More comprehensive
                'comprehensive_set': self.n_levels
            },
            
            'n_level_analysis': n_analysis
        }
        
        return recommendations
    
    def run_comprehensive_analysis(self) -> Dict:
        results = {}
        
        print("Starting comprehensive race feature N analysis...")
        print(f"Analyzing {len(self.feature_columns)} features across N levels: {self.n_levels}")
        
        # Analyze each feature
        for i, feature in enumerate(self.feature_columns):
            print(f"\nAnalyzing feature {i+1}/{len(self.feature_columns)}: {feature}")
            
            try:
                # Variability analysis
                print(f"  - Running variability analysis...")
                variability_metrics, variability_trends = self.variability_analyzer.analyze_feature_across_n(feature)
                
                # Monotonicity analysis
                print(f"  - Running monotonicity analysis...")
                monotonicity_results = {
                    'monotonicity': self.monotonicity_analyzer.analyze_monotonicity(feature),
                    'trajectories': self.monotonicity_analyzer.analyze_feature_trajectories(feature)
                }
                
                # Distinctiveness analysis
                print(f"  - Running distinctiveness analysis...")
                distinctiveness_results = self.distinctiveness_analyzer.analyze_feature_discriminative_power(feature)
                
                # Pattern classification
                print(f"  - Classifying behavior patterns...")
                pattern_results = self.pattern_classifier.classify_feature_behavior(feature)
                
                # Compile results
                results[feature] = {
                    'variability_analysis': (variability_metrics, variability_trends),
                    'monotonicity': monotonicity_results,
                    'distinctiveness': distinctiveness_results,
                    'behavior_pattern': pattern_results,
                    'stability_score': self.calculate_overall_stability(feature, (variability_metrics, variability_trends)),
                    'information_score': self.calculate_overall_information_value(feature, distinctiveness_results),
                    'quality_score': 0  # Will be calculated after all features are analyzed
                }
                
                # Calculate quality score with all components
                results[feature]['quality_score'] = self.calculate_overall_quality(feature, results[feature])
                
            except Exception as e:
                print(f"  ! Error analyzing {feature}: {e}")
                continue
        
        # Group-level analyses
        print("\nPerforming group-level analyses...")
        
        # Classify all features by pattern
        pattern_classifications = self.pattern_classifier.classify_all_features()
        pattern_groups = self.pattern_classifier.group_features_by_pattern(pattern_classifications)
        
        # Monotonicity classification
        mono_results = self.monotonicity_analyzer.analyze_all_features()
        monotonicity_groups = self.monotonicity_analyzer.classify_features_by_monotonicity(mono_results)
        
        # Quality tiers
        quality_tiers = self.create_quality_based_tiers(results)
        
        # N-level recommendations
        n_recommendations = self.recommend_n_levels(results)
        
        # Add group results
        results['feature_groups'] = {
            'pattern_groups': pattern_groups,
            'monotonicity_groups': monotonicity_groups,
            'quality_tiers': quality_tiers
        }
        
        results['n_recommendations'] = n_recommendations
        
        # Add metadata
        results['metadata'] = {
            'analysis_date': datetime.now().isoformat(),
            'n_features_analyzed': len(self.feature_columns),
            'n_levels': self.n_levels,
            'db_path': self.db_path
        }
        
        return results
    
    def save_results(self, results: Dict, output_path: str = None):
        if output_path is None:
            output_path = f"race_feature_n_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert complex objects to serializable format
        def convert_to_serializable(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif hasattr(obj, '__dict__') and not isinstance(obj, type):
                # Convert dataclass/object to dict, avoiding circular references
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
                return None  # Skip callable objects
            else:
                try:
                    # Try to convert to string if not JSON serializable
                    json.dumps(obj)
                    return obj
                except:
                    return str(obj)
        
        # Create a clean copy of results for serialization
        serializable_results = convert_to_serializable(results)
        
        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")
    
    def generate_summary_report(self, results: Dict) -> str:
        report = []
        report.append("# Race Feature N Analysis Summary Report")
        report.append(f"\nAnalysis Date: {results['metadata']['analysis_date']}")
        report.append(f"Features Analyzed: {results['metadata']['n_features_analyzed']}")
        report.append(f"N Levels: {results['metadata']['n_levels']}")
        
        # Top features by quality
        report.append("\n## Top 10 Features by Quality Score")
        quality_scores = [(f, r.get('quality_score', 0)) for f, r in results.items() if f in self.feature_columns]
        quality_scores.sort(key=lambda x: x[1], reverse=True)
        
        for i, (feature, score) in enumerate(quality_scores[:10]):
            report.append(f"{i+1}. {feature}: {score:.3f}")
        
        # Feature patterns
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
        report.append("\n## Feature Quality Tiers")
        tiers = results['feature_groups']['quality_tiers']
        for tier, features in tiers.items():
            if features:  # Only show tiers that have features
                report.append(f"\n### {tier} ({len(features)} features)")
                report.append(", ".join(features))
        
        return "\n".join(report)
    
    def __del__(self):
        # Ensure all connections are closed
        if hasattr(self, 'variability_analyzer'):
            self.variability_analyzer.close_connection()
        if hasattr(self, 'monotonicity_analyzer'):
            self.monotonicity_analyzer.close_connection()
        if hasattr(self, 'distinctiveness_analyzer'):
            self.distinctiveness_analyzer.close_connection()
        if hasattr(self, 'pattern_classifier') and hasattr(self.pattern_classifier, '__del__'):
            self.pattern_classifier.__del__()