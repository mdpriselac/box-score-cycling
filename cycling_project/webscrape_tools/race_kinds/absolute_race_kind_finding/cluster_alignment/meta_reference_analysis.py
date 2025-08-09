"""
Meta-Analysis of Reference Percentile Impact on Cluster Alignment

This module runs cluster alignment analysis using different reference percentiles
to understand how the choice of reference affects master cluster definitions and stability.
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from scipy.optimize import linear_sum_assignment

from master_cluster_aligner import MasterClusterAligner
from stability_metrics import ClusterStabilityAnalyzer
from visualization_tools import ClusterAlignmentVisualizer


class MetaReferenceAnalyzer:
    """
    Analyzes how different reference percentiles affect cluster alignment results.
    """
    
    def __init__(self, output_dir: str = 'meta_reference_results'):
        """
        Initialize the meta-analyzer.
        
        Args:
            output_dir: Directory for saving meta-analysis results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Reference percentiles to test
        self.reference_percentiles = ['10', '25', '50', '75', '95']
        
        # Initialize components
        self.aligner = MasterClusterAligner()
        self.stability_analyzer = ClusterStabilityAnalyzer()
        self.visualizer = ClusterAlignmentVisualizer()
        
        # Create subdirectories
        self.individual_results_dir = self.output_dir / 'individual_alignments'
        self.individual_results_dir.mkdir(exist_ok=True)
        
        self.comparison_results_dir = self.output_dir / 'cross_reference_comparisons'
        self.comparison_results_dir.mkdir(exist_ok=True)
        
        self.plots_dir = self.output_dir / 'plots'
        self.plots_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.output_dir / 'reports'
        self.reports_dir.mkdir(exist_ok=True)
    
    def run_meta_analysis(
        self,
        population_types: List[str] = ['with_breakdown', 'no_breakdown'],
        k_values: List[int] = [3, 4, 5, 6, 7, 8]
    ):
        """
        Run complete meta-analysis across different reference percentiles.
        
        Args:
            population_types: List of population types to analyze
            k_values: List of K values to analyze
        """
        print("=" * 80)
        print("META-ANALYSIS: REFERENCE PERCENTILE IMPACT")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Output directory: {self.output_dir}")
        print(f"Reference percentiles: {self.reference_percentiles}")
        print(f"Populations: {population_types}")
        print(f"K values: {k_values}")
        print("=" * 80)
        
        # Store all alignment results for comparison
        all_alignments = {}
        
        for population_type in population_types:
            print(f"\n{'='*60}")
            print(f"ANALYZING POPULATION: {population_type}")
            print(f"{'='*60}")
            
            all_alignments[population_type] = {}
            
            for k_value in k_values:
                print(f"\n{'-'*40}")
                print(f"Processing K={k_value}")
                print(f"{'-'*40}")
                
                k_alignments = {}
                
                # Run alignment for each reference percentile
                for ref_percentile in self.reference_percentiles:
                    print(f"\n  Reference percentile: {ref_percentile}")
                    
                    # Run alignment
                    master_assignments, alignment_scores, master_embeddings = \
                        self.aligner.align_clusters_across_percentiles(
                            population_type=population_type,
                            k_value=k_value,
                            reference_percentile=ref_percentile
                        )
                    
                    # Get master cluster profiles
                    master_profiles = self.aligner.get_master_cluster_profiles(
                        master_assignments, population_type, k_value
                    )
                    
                    # Calculate stability metrics
                    stability_metrics = self.stability_analyzer.calculate_all_stability_metrics(
                        master_assignments, k_value, population_type
                    )
                    
                    # Store results
                    k_alignments[ref_percentile] = {
                        'master_assignments': master_assignments,
                        'alignment_scores': alignment_scores,
                        'master_embeddings': master_embeddings,
                        'master_profiles': master_profiles,
                        'stability_metrics': stability_metrics
                    }
                    
                    # Save individual results
                    self._save_individual_results(
                        k_alignments[ref_percentile], 
                        population_type, 
                        k_value, 
                        ref_percentile
                    )
                    
                    print(f"    Avg alignment: {np.mean(list(alignment_scores.values())):.3f}")
                    print(f"    Overall stability: {stability_metrics['overall_stability']:.3f}")
                
                all_alignments[population_type][k_value] = k_alignments
                
                # Analyze cross-reference patterns for this K
                self._analyze_cross_reference_patterns(
                    k_alignments, population_type, k_value
                )
        
        # Generate comprehensive comparison report
        self._generate_meta_analysis_report(all_alignments)
        
        print("\n" + "=" * 80)
        print("META-ANALYSIS COMPLETE")
        print(f"Results saved to: {self.output_dir}")
        print("=" * 80)
    
    def _save_individual_results(self, results: Dict, population_type: str, 
                                k_value: int, ref_percentile: str):
        """Save individual alignment results."""
        filename = f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
        filepath = self.individual_results_dir / filename
        
        # Convert to serializable format
        serializable_results = self._convert_to_serializable(results)
        
        with open(filepath, 'w') as f:
            json.dump(serializable_results, f, indent=2)
    
    def _convert_to_serializable(self, obj):
        """Convert numpy types to serializable format."""
        if isinstance(obj, dict):
            # Convert both keys and values, handling numpy int64 keys
            return {
                (int(k) if isinstance(k, np.integer) else
                 float(k) if isinstance(k, np.floating) else
                 k.item() if hasattr(k, 'item') else
                 str(k)): self._convert_to_serializable(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_serializable(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        else:
            return obj
    
    def _analyze_cross_reference_patterns(self, k_alignments: Dict, 
                                        population_type: str, k_value: int):
        """
        Analyze how master cluster assignments vary across reference percentiles.
        """
        print(f"\n    Analyzing cross-reference patterns...")
        
        # Create cross-reference similarity matrix
        ref_percentiles = list(k_alignments.keys())
        n_refs = len(ref_percentiles)
        
        # Calculate master cluster correlation across references
        master_correlations = np.zeros((n_refs, n_refs))
        
        for i, ref1 in enumerate(ref_percentiles):
            for j, ref2 in enumerate(ref_percentiles):
                if i == j:
                    master_correlations[i, j] = 1.0
                else:
                    # Calculate similarity between master cluster sets
                    similarity = self._calculate_master_cluster_similarity(
                        k_alignments[ref1]['master_embeddings'],
                        k_alignments[ref2]['master_embeddings']
                    )
                    master_correlations[i, j] = similarity
        
        # Find most stable clusters across references
        stable_clusters = self._identify_stable_clusters(k_alignments, k_value)
        
        # Calculate reference consistency scores
        consistency_scores = {}
        for ref_percentile in ref_percentiles:
            scores = []
            for other_ref in ref_percentiles:
                if ref_percentile != other_ref:
                    i = ref_percentiles.index(ref_percentile)
                    j = ref_percentiles.index(other_ref)
                    scores.append(master_correlations[i, j])
            consistency_scores[ref_percentile] = np.mean(scores)
        
        # Store cross-reference analysis
        cross_ref_results = {
            'population_type': population_type,
            'k_value': k_value,
            'reference_percentiles': ref_percentiles,
            'master_correlations': master_correlations.tolist(),
            'consistency_scores': consistency_scores,
            'stable_clusters': stable_clusters,
            'most_consistent_reference': max(consistency_scores, key=consistency_scores.get),
            'least_consistent_reference': min(consistency_scores, key=consistency_scores.get)
        }
        
        # Save cross-reference results
        filename = f"{population_type}_k{k_value}_cross_reference_analysis.json"
        filepath = self.comparison_results_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(cross_ref_results, f, indent=2)
        
        # Create visualization
        self._create_cross_reference_heatmap(
            master_correlations, ref_percentiles, population_type, k_value
        )
        
        print(f"      Most consistent reference: {cross_ref_results['most_consistent_reference']}")
        print(f"      Avg consistency score: {np.mean(list(consistency_scores.values())):.3f}")
    
    def _calculate_master_cluster_similarity(self, embeddings1: Dict, embeddings2: Dict) -> float:
        """Calculate similarity between two sets of master cluster embeddings."""
        # Convert embeddings to matrices
        k_value = len(embeddings1)
        
        emb1_matrix = np.array([embeddings1[i] for i in range(k_value)])
        emb2_matrix = np.array([embeddings2[i] for i in range(k_value)])
        
        # Calculate cost matrix for optimal matching
        cost_matrix = np.zeros((k_value, k_value))
        
        for i in range(k_value):
            for j in range(k_value):
                similarity = cosine_similarity([emb1_matrix[i]], [emb2_matrix[j]])[0][0]
                cost_matrix[i, j] = -similarity
        
        # Find optimal assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # Calculate average similarity for optimal assignment
        total_similarity = sum(-cost_matrix[i, j] for i, j in zip(row_ind, col_ind))
        return total_similarity / k_value
    
    def _identify_stable_clusters(self, k_alignments: Dict, k_value: int) -> Dict:
        """Identify clusters that remain stable across reference choices."""
        stable_clusters = {}
        
        # For each master cluster position, check consistency across references
        for master_id in range(k_value):
            similarities = []
            
            # Compare this master cluster across all reference pairs
            ref_list = list(k_alignments.keys())
            
            for i, ref1 in enumerate(ref_list):
                for j, ref2 in enumerate(ref_list[i+1:], i+1):
                    emb1 = k_alignments[ref1]['master_embeddings'][master_id]
                    emb2 = k_alignments[ref2]['master_embeddings'][master_id]
                    
                    similarity = cosine_similarity([emb1], [emb2])[0][0]
                    similarities.append(similarity)
            
            stable_clusters[f"master_{master_id}"] = {
                'avg_cross_ref_similarity': float(np.mean(similarities)),
                'min_similarity': float(np.min(similarities)),
                'max_similarity': float(np.max(similarities)),
                'stability_score': float(np.mean(similarities))
            }
        
        return stable_clusters
    
    def _create_cross_reference_heatmap(self, correlation_matrix: np.ndarray, 
                                      ref_percentiles: List[str],
                                      population_type: str, k_value: int):
        """Create heatmap showing master cluster correlations across references."""
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        plt.figure(figsize=(10, 8))
        
        sns.heatmap(
            correlation_matrix,
            xticklabels=[f"Ref {p}%" for p in ref_percentiles],
            yticklabels=[f"Ref {p}%" for p in ref_percentiles],
            annot=True,
            fmt='.3f',
            cmap='RdBu_r',
            center=0.5,
            vmin=0,
            vmax=1,
            cbar_kws={'label': 'Master Cluster Similarity'}
        )
        
        plt.title(f'Cross-Reference Master Cluster Similarity\n{population_type} (K={k_value})')
        plt.xlabel('Reference Percentile')
        plt.ylabel('Reference Percentile')
        plt.tight_layout()
        
        save_path = self.plots_dir / f"{population_type}_k{k_value}_cross_reference_heatmap.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"      Saved cross-reference heatmap to {save_path}")
    
    def _generate_meta_analysis_report(self, all_alignments: Dict):
        """Generate comprehensive meta-analysis report."""
        report_path = self.reports_dir / "meta_analysis_report.txt"
        
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("META-ANALYSIS REPORT: REFERENCE PERCENTILE IMPACT\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Reference Percentiles Tested: {', '.join(self.reference_percentiles)}\n\n")
            
            for population_type, pop_data in all_alignments.items():
                f.write(f"\n{'='*60}\n")
                f.write(f"POPULATION: {population_type.upper()}\n")
                f.write(f"{'='*60}\n")
                
                # Load cross-reference analyses
                for k_value, k_data in pop_data.items():
                    f.write(f"\nK={k_value} ANALYSIS:\n")
                    f.write("-" * 40 + "\n")
                    
                    # Load cross-reference analysis file
                    cross_ref_file = self.comparison_results_dir / f"{population_type}_k{k_value}_cross_reference_analysis.json"
                    
                    if cross_ref_file.exists():
                        with open(cross_ref_file, 'r') as cf:
                            cross_ref_data = json.load(cf)
                        
                        f.write(f"Most Consistent Reference: {cross_ref_data['most_consistent_reference']}%\n")
                        f.write(f"Least Consistent Reference: {cross_ref_data['least_consistent_reference']}%\n")
                        
                        # Show consistency scores
                        f.write("\nReference Consistency Scores:\n")
                        for ref, score in sorted(cross_ref_data['consistency_scores'].items()):
                            f.write(f"  {ref}%: {score:.3f}\n")
                        
                        # Show stable clusters
                        f.write("\nCluster Stability Across References:\n")
                        for cluster, data in cross_ref_data['stable_clusters'].items():
                            f.write(f"  {cluster}: {data['stability_score']:.3f}\n")
                        
                        # Calculate reference impact
                        consistency_values = list(cross_ref_data['consistency_scores'].values())
                        avg_consistency = np.mean(consistency_values)
                        std_consistency = np.std(consistency_values)
                        
                        f.write(f"\nReference Impact Summary:\n")
                        f.write(f"  Average Consistency: {avg_consistency:.3f}\n")
                        f.write(f"  Consistency Std Dev: {std_consistency:.3f}\n")
                        
                        if std_consistency < 0.05:
                            f.write("  -> LOW impact: Reference choice has minimal effect\n")
                        elif std_consistency < 0.15:
                            f.write("  -> MODERATE impact: Reference choice affects some clusters\n")
                        else:
                            f.write("  -> HIGH impact: Reference choice significantly affects clusters\n")
            
            # Overall recommendations
            f.write(f"\n{'='*60}\n")
            f.write("OVERALL RECOMMENDATIONS\n")
            f.write(f"{'='*60}\n\n")
            
            f.write("1. REFERENCE PERCENTILE SELECTION:\n")
            f.write("   Based on consistency across all populations and K values:\n")
            
            # Find most consistent reference overall
            all_consistency_scores = {}
            for ref in self.reference_percentiles:
                scores = []
                for pop in all_alignments.keys():
                    for k in all_alignments[pop].keys():
                        cross_ref_file = self.comparison_results_dir / f"{pop}_k{k}_cross_reference_analysis.json"
                        if cross_ref_file.exists():
                            with open(cross_ref_file, 'r') as cf:
                                data = json.load(cf)
                                scores.append(data['consistency_scores'][ref])
                all_consistency_scores[ref] = np.mean(scores) if scores else 0
            
            best_ref = max(all_consistency_scores, key=all_consistency_scores.get)
            f.write(f"   -> Recommended reference: {best_ref}% (consistency: {all_consistency_scores[best_ref]:.3f})\n\n")
            
            f.write("2. STABILITY INSIGHTS:\n")
            f.write("   - Check individual population reports for detailed stability patterns\n")
            f.write("   - Consider using multiple reference percentiles if consistency is low\n")
            f.write("   - Higher consistency suggests robust underlying race type structure\n\n")
            
            f.write("3. INTERPRETATION:\n")
            f.write("   - High cross-reference similarity = Race types are fundamental\n")
            f.write("   - Low cross-reference similarity = Race classification depends on inclusion level\n")
            f.write("   - Mixed results suggest some race types are stable, others are inclusion-dependent\n\n")
        
        print(f"\nMeta-analysis report saved to {report_path}")


def main():
    """Main entry point for meta-analysis."""
    print("Starting Meta-Analysis of Reference Percentile Impact...")
    
    # Initialize analyzer
    analyzer = MetaReferenceAnalyzer()
    
    # Run complete meta-analysis
    analyzer.run_meta_analysis(
        population_types=['with_breakdown', 'no_breakdown'],
        k_values=[3, 4, 5, 6, 7, 8]
    )
    
    print("\nMeta-analysis complete!")


if __name__ == "__main__":
    main()