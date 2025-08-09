"""
Aligned Master Cluster Feature Comparison Analysis

This module performs a two-stage analysis:
1. Optimally aligns master clusters across different reference percentiles
2. Analyzes feature consistency of aligned master clusters

This provides insights into both alignment quality and post-alignment consistency.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from scipy.optimize import linear_sum_assignment
from itertools import combinations


class AlignedMasterClusterAnalyzer:
    """
    Performs two-stage analysis of master clusters across reference percentiles:
    1. Cross-reference alignment quality
    2. Post-alignment feature consistency
    """
    
    def __init__(self, meta_results_dir: str = 'meta_reference_results'):
        """
        Initialize the aligned feature comparison analyzer.
        
        Args:
            meta_results_dir: Directory containing meta-analysis results
        """
        self.meta_results_dir = Path(meta_results_dir)
        self.individual_results_dir = self.meta_results_dir / 'individual_alignments'
        
        self.output_dir = self.meta_results_dir / 'aligned_feature_analysis'
        self.output_dir.mkdir(exist_ok=True)
        
        self.reference_percentiles = ['10', '25', '50', '75', '95']
    
    def run_full_aligned_analysis(
        self,
        population_types: List[str] = ['with_breakdown', 'no_breakdown'],
        k_values: List[int] = [3, 4, 5, 6, 7, 8]
    ):
        """
        Run complete two-stage aligned analysis.
        
        Args:
            population_types: List of population types to analyze
            k_values: List of K values to analyze
        """
        print("="*80)
        print("ALIGNED MASTER CLUSTER ANALYSIS")
        print("="*80)
        print("Stage 1: Cross-reference master cluster alignment")
        print("Stage 2: Post-alignment feature consistency analysis")
        print("="*80)
        
        all_results = {}
        
        for population_type in population_types:
            print(f"\nAnalyzing population: {population_type}")
            all_results[population_type] = {}
            
            for k_value in k_values:
                print(f"  Processing K={k_value}...")
                
                # Stage 1: Calculate cross-reference alignments
                alignment_results = self._calculate_cross_reference_alignments(
                    population_type, k_value
                )
                
                if alignment_results is None:
                    continue
                
                # Stage 2: Analyze post-alignment feature consistency
                consistency_results = self._analyze_post_alignment_consistency(
                    population_type, k_value, alignment_results
                )
                
                # Combine results
                combined_results = {
                    'alignment_quality': alignment_results,
                    'feature_consistency': consistency_results
                }
                
                all_results[population_type][k_value] = combined_results
                
                # Generate individual reports
                self._generate_individual_report(population_type, k_value, combined_results)
        
        # Generate comprehensive summary
        self._generate_comprehensive_summary(all_results)
        
        print(f"\nAligned analysis complete! Results saved to: {self.output_dir}")
    
    def _calculate_cross_reference_alignments(
        self, 
        population_type: str, 
        k_value: int
    ) -> Optional[Dict]:
        """
        Stage 1: Calculate optimal alignments between all reference percentile pairs.
        
        Returns:
            Dictionary containing alignment quality metrics
        """
        # Load master embeddings for all reference percentiles
        master_embeddings_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    # Convert master embeddings back to numpy arrays
                    master_embeddings = {}
                    for master_id, embedding in results['master_embeddings'].items():
                        master_embeddings[int(master_id)] = np.array(embedding)
                    master_embeddings_by_ref[ref_percentile] = master_embeddings
        
        if len(master_embeddings_by_ref) < 2:
            print(f"    Insufficient data for {population_type} K={k_value}")
            return None
        
        # Calculate pairwise alignments between all reference combinations
        alignment_results = {
            'pairwise_alignments': {},
            'alignment_scores': {},
            'alignment_mappings': {}
        }
        
        for ref1, ref2 in combinations(self.reference_percentiles, 2):
            if ref1 not in master_embeddings_by_ref or ref2 not in master_embeddings_by_ref:
                continue
            
            # Calculate optimal alignment between ref1 and ref2
            alignment_score, mapping = self._align_master_clusters(
                master_embeddings_by_ref[ref1],
                master_embeddings_by_ref[ref2]
            )
            
            pair_key = f"{ref1}_{ref2}"
            alignment_results['pairwise_alignments'][pair_key] = {
                'ref1': ref1,
                'ref2': ref2,
                'alignment_score': alignment_score,
                'mapping': mapping
            }
            alignment_results['alignment_scores'][pair_key] = alignment_score
            alignment_results['alignment_mappings'][pair_key] = mapping
        
        # Calculate summary statistics
        scores = list(alignment_results['alignment_scores'].values())
        alignment_results['summary'] = {
            'avg_alignment_score': float(np.mean(scores)),
            'min_alignment_score': float(np.min(scores)),
            'max_alignment_score': float(np.max(scores)),
            'std_alignment_score': float(np.std(scores)),
            'n_comparisons': len(scores)
        }
        
        return alignment_results
    
    def _align_master_clusters(
        self, 
        embeddings1: Dict[int, np.ndarray], 
        embeddings2: Dict[int, np.ndarray]
    ) -> Tuple[float, Dict[int, int]]:
        """
        Use Hungarian algorithm to optimally align two sets of master cluster embeddings.
        
        Returns:
            Tuple of (alignment_score, mapping_dict)
        """
        k_value = len(embeddings1)
        
        # Create similarity matrix
        similarity_matrix = np.zeros((k_value, k_value))
        
        for i in range(k_value):
            for j in range(k_value):
                sim = cosine_similarity([embeddings1[i]], [embeddings2[j]])[0][0]
                similarity_matrix[i, j] = sim
        
        # Use Hungarian algorithm to find optimal assignment
        # Convert to cost matrix (negative similarity)
        cost_matrix = -similarity_matrix
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # Calculate alignment score (average similarity of optimal assignment)
        alignment_score = np.mean([similarity_matrix[i, j] for i, j in zip(row_ind, col_ind)])
        
        # Create mapping dictionary
        mapping = {int(i): int(j) for i, j in zip(row_ind, col_ind)}
        
        return float(alignment_score), mapping
    
    def _analyze_post_alignment_consistency(
        self,
        population_type: str,
        k_value: int,
        alignment_results: Dict
    ) -> Dict:
        """
        Stage 2: Analyze feature consistency of optimally aligned master clusters.
        
        Args:
            population_type: Population type
            k_value: Number of clusters
            alignment_results: Results from stage 1 alignment
            
        Returns:
            Dictionary containing post-alignment consistency metrics
        """
        # Load master profiles for all reference percentiles
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        # Use 50% as the canonical reference for alignment
        canonical_ref = '50'
        if canonical_ref not in master_profiles_by_ref:
            canonical_ref = list(master_profiles_by_ref.keys())[0]
        
        # Align all other references to canonical reference
        aligned_profiles = {canonical_ref: master_profiles_by_ref[canonical_ref]}
        
        for ref_percentile in self.reference_percentiles:
            if ref_percentile == canonical_ref or ref_percentile not in master_profiles_by_ref:
                continue
            
            # Find the alignment mapping for this reference pair
            pair_key = f"{canonical_ref}_{ref_percentile}"
            reverse_pair_key = f"{ref_percentile}_{canonical_ref}"
            
            mapping = None
            if pair_key in alignment_results['alignment_mappings']:
                mapping = alignment_results['alignment_mappings'][pair_key]
            elif reverse_pair_key in alignment_results['alignment_mappings']:
                # Reverse the mapping
                reverse_mapping = alignment_results['alignment_mappings'][reverse_pair_key]
                mapping = {v: k for k, v in reverse_mapping.items()}
            
            if mapping is not None:
                # Apply alignment mapping to create aligned profiles
                aligned_profiles[ref_percentile] = {}
                
                for canonical_master_id in range(k_value):
                    if canonical_master_id in mapping:
                        original_master_id = mapping[canonical_master_id]
                        original_key = f"master_{original_master_id}"
                        canonical_key = f"master_{canonical_master_id}"
                        
                        if original_key in master_profiles_by_ref[ref_percentile]:
                            aligned_profiles[ref_percentile][canonical_key] = \
                                master_profiles_by_ref[ref_percentile][original_key]
        
        # Now analyze consistency of aligned master clusters
        consistency_results = {}
        
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            consistency_results[master_key] = self._calculate_master_cluster_consistency(
                aligned_profiles, master_key
            )
        
        # Calculate overall consistency metrics
        all_feature_consistencies = []
        all_importance_cvs = []
        
        for master_data in consistency_results.values():
            if 'feature_consistency' in master_data:
                for feature_data in master_data['feature_consistency'].values():
                    all_feature_consistencies.append(feature_data['consistency'])
                    all_importance_cvs.append(feature_data['importance_cv'])
        
        consistency_results['summary'] = {
            'avg_feature_consistency': float(np.mean(all_feature_consistencies)) if all_feature_consistencies else 0.0,
            'avg_importance_cv': float(np.mean(all_importance_cvs)) if all_importance_cvs else 0.0,
            'n_aligned_references': len(aligned_profiles),
            'canonical_reference': canonical_ref
        }
        
        return consistency_results
    
    def _calculate_master_cluster_consistency(
        self,
        aligned_profiles: Dict,
        master_key: str
    ) -> Dict:
        """
        Calculate consistency metrics for a single master cluster across aligned references.
        """
        # Collect all features and their importance across aligned references
        feature_data = {}
        
        for ref_percentile, profiles in aligned_profiles.items():
            if master_key in profiles:
                top_features = profiles[master_key]['top_features']
                
                for feature, importance in top_features:
                    if feature not in feature_data:
                        feature_data[feature] = {}
                    feature_data[feature][ref_percentile] = importance
        
        # Calculate consistency metrics for each feature
        feature_consistency = {}
        
        for feature, ref_importances in feature_data.items():
            values = list(ref_importances.values())
            
            if len(values) >= 2:
                feature_consistency[feature] = {
                    'appearances': len(values),
                    'consistency': len(values) / len(aligned_profiles),
                    'avg_importance': float(np.mean(values)),
                    'std_importance': float(np.std(values)),
                    'importance_cv': float(np.std(values) / np.mean(values)) if np.mean(values) > 0 else 0,
                    'min_importance': float(np.min(values)),
                    'max_importance': float(np.max(values)),
                    'range': float(np.max(values) - np.min(values)),
                    'reference_values': ref_importances
                }
        
        # Identify most stable and variable features
        if feature_consistency:
            stable_features = sorted(
                feature_consistency.items(),
                key=lambda x: (x[1]['consistency'], -x[1]['importance_cv']),
                reverse=True
            )[:10]
            
            variable_features = sorted(
                [(f, data) for f, data in feature_consistency.items() if data['consistency'] >= 0.6],
                key=lambda x: x[1]['importance_cv'],
                reverse=True
            )[:10]
        else:
            stable_features = []
            variable_features = []
        
        return {
            'feature_consistency': feature_consistency,
            'most_stable_features': stable_features,
            'most_variable_features': variable_features,
            'n_features_analyzed': len(feature_consistency)
        }
    
    def _generate_individual_report(
        self,
        population_type: str,
        k_value: int,
        combined_results: Dict
    ):
        """Generate detailed report for a specific population and K value."""
        
        report_path = self.output_dir / f"{population_type}_k{k_value}_aligned_analysis.txt"
        
        with open(report_path, 'w') as f:
            f.write("="*100 + "\n")
            f.write(f"ALIGNED MASTER CLUSTER ANALYSIS REPORT\n")
            f.write(f"Population: {population_type} | K-Value: {k_value}\n")
            f.write("="*100 + "\n\n")
            
            # Stage 1: Alignment Quality Results
            alignment_data = combined_results['alignment_quality']
            
            f.write("STAGE 1: CROSS-REFERENCE ALIGNMENT QUALITY\n")
            f.write("-"*50 + "\n")
            f.write(f"Average Alignment Score: {alignment_data['summary']['avg_alignment_score']:.4f}\n")
            f.write(f"Alignment Score Range: {alignment_data['summary']['min_alignment_score']:.4f} - {alignment_data['summary']['max_alignment_score']:.4f}\n")
            f.write(f"Standard Deviation: {alignment_data['summary']['std_alignment_score']:.4f}\n")
            f.write(f"Number of Comparisons: {alignment_data['summary']['n_comparisons']}\n\n")
            
            # Interpretation of alignment quality
            avg_score = alignment_data['summary']['avg_alignment_score']
            if avg_score >= 0.8:
                interpretation = "EXCELLENT - Master clusters are highly consistent across references"
            elif avg_score >= 0.7:
                interpretation = "GOOD - Master clusters show strong consistency with some variation"
            elif avg_score >= 0.6:
                interpretation = "MODERATE - Master clusters have moderate consistency, some reference dependency"
            elif avg_score >= 0.5:
                interpretation = "POOR - Significant differences in cluster structure across references"
            else:
                interpretation = "VERY POOR - Master clusters are fundamentally different across references"
            
            f.write(f"Interpretation: {interpretation}\n\n")
            
            # Detailed pairwise alignment scores
            f.write("Pairwise Alignment Scores:\n")
            for pair_key, score in sorted(alignment_data['alignment_scores'].items()):
                refs = pair_key.split('_')
                f.write(f"  {refs[0]}% vs {refs[1]}%: {score:.4f}\n")
            f.write("\n")
            
            # Stage 2: Feature Consistency Results
            consistency_data = combined_results['feature_consistency']
            
            f.write("STAGE 2: POST-ALIGNMENT FEATURE CONSISTENCY\n")
            f.write("-"*50 + "\n")
            f.write(f"Average Feature Consistency: {consistency_data['summary']['avg_feature_consistency']:.4f}\n")
            f.write(f"Average Importance CV: {consistency_data['summary']['avg_importance_cv']:.4f}\n")
            f.write(f"References Aligned: {consistency_data['summary']['n_aligned_references']}\n")
            f.write(f"Canonical Reference: {consistency_data['summary']['canonical_reference']}%\n\n")
            
            # Feature consistency interpretation
            avg_consistency = consistency_data['summary']['avg_feature_consistency']
            avg_cv = consistency_data['summary']['avg_importance_cv']
            
            if avg_consistency >= 0.8 and avg_cv <= 0.3:
                consistency_interpretation = "EXCELLENT - Features are highly consistent across references"
            elif avg_consistency >= 0.6 and avg_cv <= 0.5:
                consistency_interpretation = "GOOD - Features show strong consistency with some variation"
            elif avg_consistency >= 0.4:
                consistency_interpretation = "MODERATE - Features have moderate consistency, reference-dependent characteristics"
            else:
                consistency_interpretation = "POOR - Features vary significantly across references"
            
            f.write(f"Interpretation: {consistency_interpretation}\n\n")
            
            # Master cluster details
            for master_id in range(k_value):
                master_key = f"master_{master_id}"
                if master_key in consistency_data:
                    master_data = consistency_data[master_key]
                    
                    f.write(f"MASTER CLUSTER {master_id}\n")
                    f.write("-"*30 + "\n")
                    f.write(f"Features Analyzed: {master_data['n_features_analyzed']}\n\n")
                    
                    # Most stable features
                    if master_data['most_stable_features']:
                        f.write("Most Stable Features (high consistency, low variation):\n")
                        for feature, data in master_data['most_stable_features'][:5]:
                            f.write(f"  {feature[:40]:<40} consistency: {data['consistency']:.2f}, CV: {data['importance_cv']:.3f}\n")
                        f.write("\n")
                    
                    # Most variable features
                    if master_data['most_variable_features']:
                        f.write("Most Variable Features (among consistent ones):\n")
                        for feature, data in master_data['most_variable_features'][:5]:
                            f.write(f"  {feature[:40]:<40} CV: {data['importance_cv']:.3f}, range: {data['range']:.4f}\n")
                        f.write("\n")
            
            # Overall conclusions
            f.write("OVERALL CONCLUSIONS\n")
            f.write("-"*30 + "\n")
            
            if avg_score >= 0.7 and avg_consistency >= 0.6:
                f.write("✓ ROBUST CLASSIFICATION: Race types are fundamental and consistent\n")
                f.write("  - Master clusters align well across references\n")
                f.write("  - Feature profiles remain stable\n")
                f.write("  - Classification system captures universal race characteristics\n")
            elif avg_score >= 0.6:
                f.write("~ MODERATE ROBUSTNESS: Some reference dependency exists\n")
                f.write("  - Master clusters show reasonable alignment\n")
                f.write("  - Some features change with inclusion perspective\n")
                f.write("  - Core race types exist but characteristics may vary\n")
            else:
                f.write("✗ REFERENCE-DEPENDENT: Classification varies significantly with inclusion level\n")
                f.write("  - Poor alignment between references suggests different taxonomies\n")
                f.write("  - Race characteristics change fundamentally with inclusion percentage\n")
                f.write("  - Consider separate models for different inclusion ranges\n")
        
        print(f"    Saved detailed report: {report_path}")
    
    def _generate_comprehensive_summary(self, all_results: Dict):
        """Generate comprehensive summary across all populations and K values."""
        
        summary_path = self.output_dir / "comprehensive_aligned_analysis_summary.txt"
        
        with open(summary_path, 'w') as f:
            f.write("="*100 + "\n")
            f.write("COMPREHENSIVE ALIGNED ANALYSIS SUMMARY\n")
            f.write("="*100 + "\n\n")
            
            f.write("This report summarizes the two-stage analysis across all populations and K-values:\n")
            f.write("1. Cross-reference alignment quality (how well master clusters align)\n")
            f.write("2. Post-alignment feature consistency (how similar aligned clusters are)\n\n")
            
            # Summary statistics
            all_alignment_scores = []
            all_consistency_scores = []
            
            for population_type, pop_data in all_results.items():
                f.write(f"POPULATION: {population_type.upper()}\n")
                f.write("="*60 + "\n\n")
                
                for k_value, results in pop_data.items():
                    alignment_score = results['alignment_quality']['summary']['avg_alignment_score']
                    consistency_score = results['feature_consistency']['summary']['avg_feature_consistency']
                    
                    all_alignment_scores.append(alignment_score)
                    all_consistency_scores.append(consistency_score)
                    
                    f.write(f"K={k_value}:\n")
                    f.write(f"  Alignment Quality: {alignment_score:.4f}\n")
                    f.write(f"  Feature Consistency: {consistency_score:.4f}\n")
                    
                    # Classification
                    if alignment_score >= 0.7 and consistency_score >= 0.6:
                        classification = "ROBUST"
                    elif alignment_score >= 0.6:
                        classification = "MODERATE"
                    else:
                        classification = "REFERENCE-DEPENDENT"
                    
                    f.write(f"  Classification: {classification}\n\n")
                
                f.write("\n")
            
            # Overall recommendations
            f.write("OVERALL FINDINGS AND RECOMMENDATIONS\n")
            f.write("="*60 + "\n\n")
            
            avg_alignment = np.mean(all_alignment_scores)
            avg_consistency = np.mean(all_consistency_scores)
            
            f.write(f"Average Alignment Quality: {avg_alignment:.4f}\n")
            f.write(f"Average Feature Consistency: {avg_consistency:.4f}\n\n")
            
            if avg_alignment >= 0.7 and avg_consistency >= 0.6:
                f.write("CONCLUSION: ROBUST RACE TYPE SYSTEM\n")
                f.write("- Race types are fundamental characteristics that appear consistently\n")
                f.write("- Classification system is reliable across inclusion levels\n")
                f.write("- Features represent universal race characteristics\n")
            elif avg_alignment >= 0.6:
                f.write("CONCLUSION: MODERATELY ROBUST WITH SOME REFERENCE DEPENDENCY\n")
                f.write("- Core race types exist but may vary with inclusion perspective\n")
                f.write("- Consider using multiple reference points for classification\n")
                f.write("- Some features may be inclusion-level dependent\n")
            else:
                f.write("CONCLUSION: SIGNIFICANT REFERENCE DEPENDENCY\n")
                f.write("- Race classification varies substantially with inclusion level\n")
                f.write("- Consider separate models for different inclusion ranges\n")
                f.write("- Early finisher vs. full field perspectives may capture different aspects\n")
            
            f.write("\nRECOMMENDATIONS:\n")
            
            # Find best performing configurations
            best_configs = []
            for pop_type, pop_data in all_results.items():
                for k_val, results in pop_data.items():
                    alignment = results['alignment_quality']['summary']['avg_alignment_score']
                    consistency = results['feature_consistency']['summary']['avg_feature_consistency']
                    combined_score = (alignment + consistency) / 2
                    best_configs.append((pop_type, k_val, combined_score, alignment, consistency))
            
            best_configs.sort(key=lambda x: x[2], reverse=True)
            
            f.write("\nBest Performing Configurations:\n")
            for pop_type, k_val, combined, alignment, consistency in best_configs[:5]:
                f.write(f"  {pop_type} K={k_val}: Combined={combined:.3f} (Align={alignment:.3f}, Consist={consistency:.3f})\n")
        
        print(f"\nComprehensive summary saved to: {summary_path}")


def main():
    """Main entry point for aligned feature comparison analysis."""
    print("Starting Aligned Master Cluster Feature Analysis...")
    
    # Initialize analyzer
    analyzer = AlignedMasterClusterAnalyzer()
    
    # Run complete aligned analysis
    analyzer.run_full_aligned_analysis(
        population_types=['with_breakdown', 'no_breakdown'],
        k_values=[3, 4, 5, 6, 7, 8]
    )
    
    print("\nAligned analysis complete!")


if __name__ == "__main__":
    main()