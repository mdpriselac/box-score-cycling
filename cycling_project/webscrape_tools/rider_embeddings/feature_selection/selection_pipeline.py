import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
import json
from datetime import datetime
import warnings

from .correlation_analyzer import CorrelationQualityAnalyzer
from .clustering_analyzer import ClusteringQualityAnalyzer
from .redundancy_analyzer import FeatureRedundancyAnalyzer


class FeatureSelectionPipeline:
    """
    Integrated pipeline for feature selection analysis.
    
    Combines correlation quality, clustering quality, and redundancy analysis
    to provide comprehensive recommendations for percentile and feature selection.
    """
    
    def __init__(
        self, 
        correlation_threshold: float = 0.8,
        random_state: int = 42
    ):
        """
        Initialize the feature selection pipeline.
        
        Args:
            correlation_threshold: Threshold for redundancy analysis
            random_state: Random state for clustering analysis
        """
        self.correlation_analyzer = CorrelationQualityAnalyzer()
        self.clustering_analyzer = ClusteringQualityAnalyzer(random_state=random_state)
        self.redundancy_analyzer = FeatureRedundancyAnalyzer(correlation_threshold)
        
    def analyze_all(
        self, 
        correlation_results: List[Dict[str, Any]],
        percentiles: List[str] = None,
        k_range: List[int] = None,
        max_features: int = None
    ) -> Dict[str, Any]:
        """
        Run complete feature selection analysis pipeline.
        
        Args:
            correlation_results: List of correlation results from CorrelationCalculator
            percentiles: List of percentiles to analyze (if None, analyzes all available)
            k_range: Range of k values for clustering analysis
            max_features: Maximum number of features to recommend
            
        Returns:
            Comprehensive analysis results with recommendations
        """
        print("Starting comprehensive feature selection analysis...")
        
        # Validate input
        if not correlation_results:
            raise ValueError("No correlation results provided")
        
        # Extract available percentiles if not specified
        if percentiles is None:
            valid_result = next(
                (r for r in correlation_results if r['feature_correlations']), 
                None
            )
            if valid_result:
                percentiles = list(valid_result['feature_correlations'].keys())
            else:
                raise ValueError("No valid correlation results found")
        
        print(f"Analyzing {len(percentiles)} percentiles: {percentiles}")
        
        # 1. Correlation Quality Analysis
        print("1. Running correlation quality analysis...")
        correlation_quality = self.correlation_analyzer.analyze_percentile_quality(correlation_results)
        percentile_rankings_corr = self.correlation_analyzer.rank_percentiles(correlation_quality)
        
        # 2. Feature Analysis for All Percentiles
        print("2. Analyzing features for all percentiles...")
        top_percentiles = list(correlation_quality.keys())  # Analyze all percentiles
        
        feature_analyses = {}
        redundancy_analyses = {}
        
        for percentile in top_percentiles:
            try:
                print(f"   Analyzing {percentile}...")
                
                # Feature quality analysis
                feature_quality = self.correlation_analyzer.analyze_feature_quality(
                    correlation_results, percentile
                )
                feature_rankings = self.correlation_analyzer.rank_features(feature_quality)
                
                # Redundancy analysis
                feature_correlations = self.redundancy_analyzer.calculate_feature_correlations(
                    correlation_results, percentile
                )
                redundancy_data = self.redundancy_analyzer.identify_redundant_features(
                    feature_correlations
                )
                
                # Feature recommendations
                feature_quality_scores = {name: score for name, score in feature_rankings}
                selection_recommendations = self.redundancy_analyzer.recommend_feature_selection(
                    redundancy_data, feature_quality_scores, max_features
                )
                
                feature_analyses[percentile] = {
                    'quality_metrics': feature_quality,
                    'rankings': feature_rankings,
                    'top_20_features': feature_rankings[:20]
                }
                
                redundancy_analyses[percentile] = {
                    'feature_correlations': feature_correlations,
                    'redundancy_data': redundancy_data,
                    'selection_recommendations': selection_recommendations
                }
                
            except Exception as e:
                print(f"   Warning: Could not analyze {percentile}: {e}")
                warnings.warn(f"Analysis failed for {percentile}: {e}")
        
        # 3. Run clustering analysis on selected features for each percentile
        print("3. Running clustering analysis on selected features...")
        selected_features_clustering = {}
        
        # For each percentile that has feature recommendations
        for percentile in redundancy_analyses.keys():
            if percentile in redundancy_analyses:
                redundancy_data = redundancy_analyses[percentile]
                selection_rec = redundancy_data['selection_recommendations']
                
                # Get the selected features
                if selection_rec['final_selection']:
                    selected_features = selection_rec['final_selection']
                else:
                    # Fall back to top features minus redundant ones
                    top_features = [f[0] for f in feature_analyses[percentile]['rankings'][:30]]
                    features_to_remove = set(selection_rec['features_to_remove'])
                    selected_features = [f for f in top_features if f not in features_to_remove]
                    
                    if max_features and len(selected_features) > max_features:
                        selected_features = selected_features[:max_features]
                
                if selected_features:
                    try:
                        print(f"   Analyzing clustering for {percentile} with {len(selected_features)} selected features...")
                        
                        # Run clustering on selected features only
                        selected_analysis = self.clustering_analyzer.analyze_clustering_quality(
                            correlation_results,
                            percentile,
                            k_range=k_range,
                            selected_features=selected_features
                        )
                        
                        # Get cluster characteristics for selected features
                        optimal_k = selected_analysis.get('optimal_k')
                        if optimal_k:
                            try:
                                characteristics = self.clustering_analyzer.get_cluster_characteristics(
                                    correlation_results,
                                    percentile,
                                    k=optimal_k,
                                    selected_features=selected_features,
                                    precomputed_analysis=selected_analysis
                                )
                                # Merge the characteristics into selected_analysis
                                selected_analysis.update(characteristics)
                            except Exception as e:
                                print(f"   Warning: Could not get cluster characteristics for {percentile}: {e}")
                        
                        selected_features_clustering[percentile] = {
                            'analysis': selected_analysis,
                            'features_used': selected_features,
                            'num_features': len(selected_features)
                        }
                        
                    except Exception as e:
                        print(f"   Warning: Could not re-analyze clustering for {percentile}: {e}")
                        import traceback
                        traceback.print_exc()
                        warnings.warn(f"Selected features clustering failed for {percentile}: {e}")
        
        # 4. Generate Integrated Recommendations
        print("4. Generating integrated recommendations...")
        recommendations = self._generate_recommendations(
            correlation_quality,
            percentile_rankings_corr,
            selected_features_clustering,  # Use clustering results from selected features
            feature_analyses,
            redundancy_analyses,
            max_features
        )
        
        # 6. Compile Final Results
        final_results = {
            'analysis_metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_rider_results': len(correlation_results),
                'percentiles_analyzed': percentiles,
                'max_features_constraint': max_features,
                'analysis_components': [
                    'correlation_quality',
                    'feature_selection',
                    'selected_features_clustering'
                ]
            },
            'correlation_quality_analysis': {
                'percentile_quality_metrics': correlation_quality,
                'percentile_rankings': percentile_rankings_corr
            },
            'clustering_analysis': selected_features_clustering,
            'feature_analysis': feature_analyses,
            'redundancy_analysis': redundancy_analyses,
            'recommendations': recommendations
        }
        
        print("Analysis complete!")
        return final_results
    
    def _generate_recommendations(
        self,
        correlation_quality: Dict[str, Dict[str, float]],
        percentile_rankings_corr: List[Tuple[str, float]],
        selected_features_clustering: Dict[str, Dict[str, Any]],
        feature_analyses: Dict[str, Dict[str, Any]],
        redundancy_analyses: Dict[str, Dict[str, Any]],
        max_features: Optional[int]
    ) -> Dict[str, Any]:
        """Generate integrated recommendations from all analyses."""
        
        # Best percentile recommendations
        best_percentile_corr = percentile_rankings_corr[0][0] if percentile_rankings_corr else None
        # Find best percentile based on selected features clustering
        best_percentile_clustering = None
        if selected_features_clustering:
            best_clustering_score = 0
            for percentile, clustering_data in selected_features_clustering.items():
                if 'analysis' in clustering_data:
                    analysis = clustering_data['analysis']
                    optimal_k = analysis.get('optimal_k')
                    if optimal_k and optimal_k in analysis.get('clustering_results', {}):
                        silhouette = analysis['clustering_results'][optimal_k]['silhouette_score']
                        if silhouette > best_clustering_score:
                            best_clustering_score = silhouette
                            best_percentile_clustering = percentile
        
        # Consensus percentile (appears in top 3 of both analyses)
        top_3_corr = {p[0] for p in percentile_rankings_corr[:3]}
        
        # Get top 3 from selected features clustering
        clustering_rankings = []
        for percentile, clustering_data in selected_features_clustering.items():
            if 'analysis' in clustering_data:
                analysis = clustering_data['analysis']
                optimal_k = analysis.get('optimal_k')
                if optimal_k and optimal_k in analysis.get('clustering_results', {}):
                    silhouette = analysis['clustering_results'][optimal_k]['silhouette_score']
                    clustering_rankings.append((percentile, silhouette))
        
        clustering_rankings.sort(key=lambda x: x[1], reverse=True)
        top_3_clustering = {p[0] for p in clustering_rankings[:3]}
        consensus_percentiles = list(top_3_corr.intersection(top_3_clustering))
        
        # Feature recommendations for best percentiles
        feature_recommendations = {}
        
        for percentile in feature_analyses.keys():
            if percentile in redundancy_analyses:
                redundancy_data = redundancy_analyses[percentile]
                selection_rec = redundancy_data['selection_recommendations']
                
                # Get final feature selection
                if selection_rec['final_selection']:
                    recommended_features = selection_rec['final_selection']
                else:
                    # Fall back to top features minus redundant ones
                    top_features = [f[0] for f in feature_analyses[percentile]['rankings'][:30]]
                    features_to_remove = set(selection_rec['features_to_remove'])
                    recommended_features = [f for f in top_features if f not in features_to_remove]
                    
                    if max_features and len(recommended_features) > max_features:
                        recommended_features = recommended_features[:max_features]
                
                feature_recommendations[percentile] = {
                    'recommended_features': recommended_features,
                    'num_features': len(recommended_features),
                    'redundancy_reduction': selection_rec['reduction_stats'],
                    'selection_method': 'redundancy_aware' if selection_rec['features_to_remove'] else 'quality_ranking'
                }
        
        # Overall quality scores for percentiles
        percentile_scores = {}
        
        for percentile in correlation_quality.keys():
            # Correlation quality score
            corr_score = next((score for name, score in percentile_rankings_corr if name == percentile), 0)
            
            # Clustering quality score from selected features clustering
            clustering_score = 0
            if percentile in selected_features_clustering:
                clustering_data = selected_features_clustering[percentile]
                if 'analysis' in clustering_data:
                    analysis = clustering_data['analysis']
                    optimal_k = analysis.get('optimal_k')
                    if optimal_k and optimal_k in analysis.get('clustering_results', {}):
                        # Normalize silhouette score (0-1) to similar scale as correlation score
                        silhouette = analysis['clustering_results'][optimal_k]['silhouette_score']
                        clustering_score = max(0, silhouette) * 2  # Scale to 0-2 range
            
            # Combined score (equal weight correlation and clustering)
            combined_score = (corr_score + clustering_score) / 2
            percentile_scores[percentile] = {
                'correlation_score': corr_score,
                'clustering_score': clustering_score,
                'combined_score': combined_score
            }
        
        # Final recommendations
        best_overall_percentile = max(
            percentile_scores.keys(), 
            key=lambda p: percentile_scores[p]['combined_score']
        ) if percentile_scores else None
        
        return {
            'percentile_recommendations': {
                'best_for_correlation_quality': best_percentile_corr,
                'best_for_clustering': best_percentile_clustering,
                'consensus_percentiles': consensus_percentiles,
                'best_overall': best_overall_percentile,
                'percentile_scores': percentile_scores
            },
            'feature_recommendations': feature_recommendations,
            'summary': {
                'recommended_percentile': best_overall_percentile,
                'recommended_features': feature_recommendations.get(
                    best_overall_percentile, {}
                ).get('recommended_features', []),
                'feature_count': len(feature_recommendations.get(
                    best_overall_percentile, {}
                ).get('recommended_features', [])),
                'analysis_basis': 'Combined correlation quality and clustering analysis'
            }
        }
    
    def save_results(
        self, 
        results: Dict[str, Any], 
        output_path: str,
        include_raw_data: bool = False
    ) -> None:
        """
        Save analysis results to file.
        
        Args:
            results: Output from analyze_all
            output_path: Path to save results
            include_raw_data: Whether to include detailed raw analysis data
        """
        # Create summary version if not including raw data
        if not include_raw_data:
            summary_results = {
                'analysis_metadata': results['analysis_metadata'],
                'recommendations': results['recommendations'],
                'summary_statistics': {
                    'percentiles_analyzed': len(results['correlation_quality_analysis']['percentile_quality_metrics']),
                    'top_percentile_features': {
                        percentile: len(analysis['rankings'])
                        for percentile, analysis in results['feature_analysis'].items()
                    }
                }
            }
            results_to_save = summary_results
        else:
            results_to_save = results
        
        with open(output_path, 'w') as f:
            json.dump(results_to_save, f, indent=2, default=str)
        
        print(f"Results saved to {output_path}")
    
    def generate_report(self, results: Dict[str, Any]) -> str:
        """
        Generate a detailed human-readable report with explanations.
        
        Args:
            results: Output from analyze_all
            
        Returns:
            Formatted text report with detailed explanations
        """
        recommendations = results['recommendations']
        metadata = results['analysis_metadata']
        correlation_analysis = results['correlation_quality_analysis']
        clustering_analysis = results['clustering_analysis']
        feature_analysis = results['feature_analysis']
        redundancy_analysis = results['redundancy_analysis']
        
        report = []
        report.append("COMPREHENSIVE FEATURE SELECTION ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")
        
        # Analysis overview
        report.append(f"Analysis Date: {metadata['timestamp']}")
        report.append(f"Rider Results Analyzed: {metadata['total_rider_results']}")
        report.append(f"Percentiles Analyzed: {', '.join(metadata['percentiles_analyzed'])}")
        if metadata['max_features_constraint']:
            report.append(f"Maximum Features Constraint: {metadata['max_features_constraint']}")
        report.append("")
        
        # SECTION 1: Percentile Analysis with Explanations
        report.append("1. PERCENTILE ANALYSIS & SELECTION RATIONALE")
        report.append("=" * 50)
        
        percentile_rec = recommendations['percentile_recommendations']
        best_percentile = percentile_rec['best_overall']
        
        report.append(f"🏆 RECOMMENDED PERCENTILE: {best_percentile}")
        report.append("")
        
        # Explain why this percentile was chosen
        report.append("WHY THIS PERCENTILE WAS SELECTED:")
        report.append("-" * 35)
        
        # Get detailed metrics for the best percentile
        if best_percentile in correlation_analysis['percentile_quality_metrics']:
            corr_metrics = correlation_analysis['percentile_quality_metrics'][best_percentile]
            
            report.append(f"📊 Correlation Quality Metrics:")
            report.append(f"   • Signal Strength: {corr_metrics['signal_strength']:.4f}")
            report.append(f"     (Combination of correlation strength and variance - higher is better)")
            report.append(f"   • Mean Absolute Correlation: {corr_metrics['mean_abs_correlation']:.4f}")
            report.append(f"     (Average strength of rider-feature relationships)")
            report.append(f"   • Correlation Variance: {corr_metrics['correlation_variance']:.4f}")
            report.append(f"     (How much correlations vary between riders - higher = more discriminative)")
            report.append(f"   • Feature Coverage: {corr_metrics['feature_coverage']:.1%}")
            report.append(f"     (Proportion of features with data from multiple riders)")
            report.append("")
        
        # Clustering quality explanation
        # Check if we have clustering results for the best percentile
        clustering_analysis = results['clustering_analysis']
        selected_clustering = clustering_analysis.get(best_percentile)
        
        if selected_clustering and 'analysis' in selected_clustering:
            report.append("DEBUG: WE SELECTED selected_clustering and 'analysis' in selected_clustering")
            # Use selected features clustering metrics
            selected_analysis = selected_clustering['analysis']
            optimal_k = selected_analysis.get('optimal_k', 'N/A')
            
            if optimal_k != 'N/A' and optimal_k in selected_analysis.get('clustering_results', {}):
                #Get the cluster quality results
                cluster_results = selected_analysis['clustering_results'][optimal_k]
                silhouette = cluster_results['silhouette_score']
                #Cluster quality reporting
                report.append(f"🎯 Clustering Quality Metrics (based on selected features):")
                report.append(f"   • Optimal Clusters: {optimal_k}")
                report.append(f"   • Silhouette Score: {silhouette:.4f}")
                if silhouette > 0.5:
                    report.append(f"     (Excellent cluster separation - riders form distinct groups)")
                elif silhouette > 0.3:
                    report.append(f"     (Good cluster separation - clear rider types emerge)")
                else:
                    report.append(f"     (Moderate cluster separation - some rider differentiation)")
                #Cluster size balance reporting
                cluster_sizes = cluster_results['cluster_sizes']
                report.append(f"   • Cluster Sizes: {cluster_sizes}")
                size_balance = cluster_results['size_balance']
                if size_balance < 0.5:
                    report.append(f"     (Well-balanced cluster sizes)")
                else:
                    report.append(f"     (Some cluster size imbalance)")
                # Add cluster characteristics with feature importance
                report.append("DEBUG: Checking for cluster characteristics")
                if 'cluster_characteristics' in selected_analysis:
                    report.append(f"DEBUG: selected_clustering exists: {len(selected_analysis['cluster_characteristics'])} cluster characteristics found")
                    for cluster_id, cluster_chars in selected_analysis['cluster_characteristics'].items():
                        report.append(f"\n Cluster {int(cluster_id) + 1} Characteristics:")
                        #sort the top features by the absolute value of their mean correlation (descending order, highest to lowest)
                        top_features = sorted(
                            cluster_chars['top_features'], 
                            key=lambda x: abs(x['mean_correlation']), 
                            reverse=True
                        )[:4]
                        for i, feature_data in enumerate(top_features, 1):
                            feature_name = feature_data['feature']
                            mean_corr = feature_data['mean_correlation']
                            importance = abs(mean_corr)
                            report.append(f"     {i}. {feature_name:<28} {mean_corr:+.3f} (imp: {importance:.3f})")
                            
                
        elif 'percentile_analyses' in clustering_analysis and best_percentile in clustering_analysis['percentile_analyses']:
            report.append("DEBUG: WE SELECTED 'percentile_analyes' in clustering_analysis and best_percentile in clusterign_analysis['percentile_analyses']")
            # Fall back to all-features clustering if selected features clustering not available
            cluster_data = clustering_analysis['percentile_analyses'][best_percentile]
            optimal_k = cluster_data.get('optimal_k', 'N/A')
            
            if optimal_k != 'N/A' and optimal_k in cluster_data.get('clustering_results', {}):
                cluster_results = cluster_data['clustering_results'][optimal_k]
                silhouette = cluster_results['silhouette_score']
                
                report.append(f"🎯 Clustering Quality Metrics (all features):")
                report.append(f"   • Optimal Clusters: {optimal_k}")
                report.append(f"   • Silhouette Score: {silhouette:.4f}")
                if silhouette > 0.5:
                    report.append(f"     (Excellent cluster separation - riders form distinct groups)")
                elif silhouette > 0.3:
                    report.append(f"     (Good cluster separation - clear rider types emerge)")
                else:
                    report.append(f"     (Moderate cluster separation - some rider differentiation)")
                
            
                cluster_sizes = cluster_results['cluster_sizes']
                report.append(f"   • Cluster Sizes: {cluster_sizes}")
                size_balance = cluster_results['size_balance']
                if size_balance < 0.5:
                    report.append(f"     (Well-balanced cluster sizes)")
                else:
                    report.append(f"     (Some cluster size imbalance)")
                
                # Add cluster characteristics with feature importance
                # Check if we have clustering results for this percentile
                report.append("DEBUG: Checking for cluster characteristics")
                report.append(f"DEBUG: selected_clustering exists: {selected_clustering is not None}")
                if selected_clustering and 'analysis' in selected_clustering:
                    # Use the selected features clustering results
                    selected_analysis = selected_clustering['analysis']
                    report.append(f"DEBUG: Keys in selected_analysis: {list(selected_analysis.keys())}")
                    if 'cluster_characteristics' in selected_analysis:
                        cluster_chars = selected_analysis['cluster_characteristics']
                        report.append("")
                        report.append(f"🏷️  CLUSTER PROFILES (based on {selected_clustering['num_features']} selected features):")
                        report.append("-" * 20)
                        
                        clusters_data = cluster_chars
                        
                        # Sort cluster IDs to ensure consistent ordering
                        sorted_cluster_items = sorted(
                            clusters_data.items(),
                            key=lambda x: int(x[0]) if str(x[0]).isdigit() else int(x[0])  # Handle both int and string keys
                        )
                        
                        for cluster_id_str, char_data in sorted_cluster_items:
                            cluster_size = char_data['size']
                            top_features = char_data['top_features'][:4]  # Top 4 features
                            
                            # Convert cluster_id to int for display
                            if isinstance(cluster_id_str, str):
                                display_cluster_num = int(cluster_id_str) + 1
                            else:
                                display_cluster_num = cluster_id_str + 1
                            
                            report.append(f"\n   Cluster {display_cluster_num} ({cluster_size} riders):")
                            report.append(f"   Top distinguishing features:")
                            
                            for i, feature_data in enumerate(top_features, 1):
                                feature_name = feature_data['feature']
                                mean_corr = feature_data['mean_correlation']
                                importance = abs(mean_corr)  # Use absolute correlation as importance
                                
                                # Truncate long feature names for display
                                display_name = feature_name[:25] + "..." if len(feature_name) > 25 else feature_name
                                
                                # Format the correlation value with sign
                                corr_sign = "+" if mean_corr >= 0 else ""
                                report.append(f"     {i}. {display_name:<28} {corr_sign}{mean_corr:.3f} (imp: {importance:.3f})")
                else:
                    # No cluster characteristics available for display
                    report.append("")
                    report.append("🏷️  CLUSTER PROFILES: Not available (clustering analysis may have failed)")
                    report.append("")
                
                report.append("")
        else:
            report.append("DEBUG: We did not select either clustering analysis options, we need another way to identify the clustering feature importances")
        # Comparison with other percentiles
        report.append("COMPARISON WITH OTHER PERCENTILES:")
        report.append("-" * 35)
        scores = percentile_rec['percentile_scores']
        sorted_percentiles = sorted(scores.items(), key=lambda x: x[1]['combined_score'], reverse=True)
        
        report.append(f"{'Rank':<4} {'Percentile':<16} {'Combined':<9} {'Why Better/Worse'}")
        report.append("-" * 65)
        
        for rank, (percentile, score_data) in enumerate(sorted_percentiles[:5], 1):
            combined = score_data['combined_score']
            corr_score = score_data['correlation_score']
            clust_score = score_data['clustering_score']
            
            # Generate explanation
            if rank == 1:
                explanation = "Best overall balance"
            elif corr_score > 0.8 and clust_score < 0.3:
                explanation = "High correlation, poor clustering"
            elif corr_score < 0.3 and clust_score > 0.8:
                explanation = "Poor correlation, good clustering"
            elif combined < 0.3:
                explanation = "Weak on both metrics"
            else:
                explanation = "Moderate performance"
            
            report.append(f"{rank:<4} {percentile:<16} {combined:<9.4f} {explanation}")
        
        report.append("")
        
        # SECTION 2: Feature Selection with Explanations
        report.append("2. FEATURE SELECTION & REDUNDANCY ANALYSIS")
        report.append("=" * 45)
        
        summary = recommendations['summary']
        report.append(f"🎯 SELECTED FEATURES: {summary['feature_count']} features")
        report.append("")
        
        # Explain feature selection process
        if best_percentile in redundancy_analysis:
            redund_data = redundancy_analysis[best_percentile]
            selection_rec = redund_data['selection_recommendations']
            
            report.append("FEATURE SELECTION PROCESS:")
            report.append("-" * 25)
            
            # Redundancy removal explanation
            if selection_rec['features_to_remove']:
                removed_count = len(selection_rec['features_to_remove'])
                reduction_rate = selection_rec['reduction_stats']['reduction_rate']
                
                report.append(f"📉 Redundancy Reduction:")
                report.append(f"   • Removed {removed_count} redundant features ({reduction_rate:.1%} reduction)")
                report.append(f"   • Kept highest quality feature from each redundant group")
                
                # Show some examples of redundant groups
                group_selections = selection_rec['group_selections']
                if group_selections:
                    report.append(f"   • Example redundant groups:")
                    for i, group_sel in enumerate(group_selections[:3]):
                        kept = group_sel['selected']
                        removed = group_sel['removed']
                        report.append(f"     - Kept '{kept}', removed {len(removed)} similar features")
                report.append("")
            
            # Feature quality ranking explanation
            if best_percentile in feature_analysis:
                feature_rankings = feature_analysis[best_percentile]['rankings']
                
                report.append(f"🏅 TOP SELECTED FEATURES (by quality score):")
                report.append("-" * 40)
                
                for i, (feature, score) in enumerate(feature_rankings[:15], 1):
                    if feature in summary['recommended_features']:
                        status = "✓ Selected"
                    else:
                        status = "✗ Removed (redundant)"
                    
                    report.append(f"  {i:2d}. {feature:<30} {score:6.4f} {status}")
                
                if len(feature_rankings) > 15:
                    remaining_selected = [f for f in summary['recommended_features'] 
                                        if f not in [fr[0] for fr in feature_rankings[:15]]]
                    if remaining_selected:
                        report.append(f"  ... and {len(remaining_selected)} more selected features")
                
                report.append("")
        
        # SECTION 3: Feature Quality Explanations
        report.append("3. FEATURE QUALITY CRITERIA")
        report.append("=" * 30)
        report.append("Features were ranked based on:")
        report.append("• Mean Absolute Correlation: How strongly features relate to rider performance")
        report.append("• Discriminative Power: How well features distinguish between different riders")
        report.append("• Sample Size: How many riders have valid data for each feature")
        report.append("• Dynamic Range: The spread of correlation values across riders")
        report.append("")
        
        # SECTION 4: Expected Outcomes
        report.append("4. EXPECTED OUTCOMES WITH SELECTED FEATURES")
        report.append("=" * 45)
        
        # Use clustering results for expected outcomes if available  
        if selected_clustering and 'analysis' in selected_clustering:
            # Use selected features clustering results
            selected_analysis = selected_clustering['analysis']
            optimal_k = selected_analysis.get('optimal_k', 'N/A')
            
            report.append(f"🎯 Rider Classification:")
            report.append(f"   • Expected {optimal_k} distinct rider types")
            report.append(f"   • Using {best_percentile} (top {best_percentile.split('_')[-1]}% of race finishers)")
            report.append(f"   • With {summary['feature_count']} optimized features")
            
            if optimal_k != 'N/A' and optimal_k in selected_analysis.get('clustering_results', {}):
                silhouette = selected_analysis['clustering_results'][optimal_k]['silhouette_score']
                if silhouette > 0.5:
                    report.append(f"   • High confidence in rider type separation")
                elif silhouette > 0.3:
                    report.append(f"   • Moderate confidence in rider type separation")
                else:
                    report.append(f"   • Lower confidence - rider types may overlap")
        else:
            report.append(f"🎯 Rider Classification:")
            report.append(f"   • Using {best_percentile} (top {best_percentile.split('_')[-1]}% of race finishers)")
            report.append(f"   • With {summary['feature_count']} optimized features")
            report.append(f"   • Clustering analysis not available")
        
        report.append("")
        
        # SECTION 5: Technical Summary
        report.append("5. TECHNICAL SUMMARY")
        report.append("=" * 20)
        report.append(f"Analysis Basis: {recommendations['summary']['analysis_basis']}")
        report.append(f"Data Points: {metadata['total_rider_results']} rider results")
        report.append(f"Features Considered: ~40-50 per percentile")
        report.append(f"Final Feature Set: {summary['feature_count']} features")
        
        return "\n".join(report)