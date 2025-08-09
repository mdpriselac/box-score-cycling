"""
Main Runner Script for Cluster Alignment Analysis

Coordinates the full alignment analysis pipeline and generates comprehensive reports.
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from master_cluster_aligner import MasterClusterAligner
from stability_metrics import ClusterStabilityAnalyzer
from visualization_tools import ClusterAlignmentVisualizer


def convert_numpy_to_native(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    Handles dictionary keys and nested structures.
    """
    if isinstance(obj, dict):
        # Convert both keys and values
        return {
            (int(k) if isinstance(k, np.integer) else
             float(k) if isinstance(k, np.floating) else
             k.item() if hasattr(k, 'item') else
             str(k)): convert_numpy_to_native(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_to_native(item) for item in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    else:
        return obj


class AlignmentAnalysisPipeline:
    """
    Orchestrates the complete cluster alignment analysis.
    """
    
    def __init__(self, output_dir: str = 'alignment_results'):
        """
        Initialize the pipeline.
        
        Args:
            output_dir: Directory for saving results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.aligner = MasterClusterAligner()
        self.stability_analyzer = ClusterStabilityAnalyzer()
        self.visualizer = ClusterAlignmentVisualizer()
        
        # Create subdirectories
        self.plots_dir = self.output_dir / 'plots'
        self.plots_dir.mkdir(exist_ok=True)
        
        self.reports_dir = self.output_dir / 'reports'
        self.reports_dir.mkdir(exist_ok=True)
        
        self.data_dir = self.output_dir / 'data'
        self.data_dir.mkdir(exist_ok=True)
        
    def run_complete_analysis(
        self,
        population_types: List[str] = ['with_breakdown', 'no_breakdown'],
        k_values: List[int] = [3, 4, 5, 6, 7, 8],
        reference_percentiles: Dict[str, str] = None
    ):
        """
        Run complete alignment analysis for all populations and K values.
        
        Args:
            population_types: List of population types to analyze
            k_values: List of K values to analyze
            reference_percentiles: Optional dict of reference percentiles per population
        """
        if reference_percentiles is None:
            reference_percentiles = {
                'with_breakdown': '50',
                'no_breakdown': '50'
            }
        
        print("=" * 80)
        print("CLUSTER ALIGNMENT ANALYSIS PIPELINE")
        print("=" * 80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Output directory: {self.output_dir}")
        print(f"Populations: {population_types}")
        print(f"K values: {k_values}")
        print("=" * 80)
        
        # Store results for summary
        all_results = {}
        
        for population_type in population_types:
            print(f"\n{'='*60}")
            print(f"ANALYZING POPULATION: {population_type}")
            print(f"{'='*60}")
            
            population_results = {}
            
            for k_value in k_values:
                print(f"\n{'-'*40}")
                print(f"Processing K={k_value}")
                print(f"{'-'*40}")
                
                # Run alignment
                master_assignments, alignment_scores, master_embeddings = \
                    self.aligner.align_clusters_across_percentiles(
                        population_type=population_type,
                        k_value=k_value,
                        reference_percentile=reference_percentiles[population_type]
                    )
                
                # Get master cluster profiles
                master_profiles = self.aligner.get_master_cluster_profiles(
                    master_assignments, population_type, k_value
                )
                
                # Calculate migration patterns
                migration_patterns = self.aligner.calculate_cluster_migration(
                    master_assignments, k_value
                )
                
                # Calculate stability metrics
                stability_metrics = self.stability_analyzer.calculate_all_stability_metrics(
                    master_assignments, k_value, population_type
                )
                
                # Generate visualizations
                self._generate_visualizations(
                    master_assignments, 
                    master_profiles,
                    stability_metrics,
                    k_value, 
                    population_type
                )
                
                # Store results
                results = {
                    'master_assignments': master_assignments,
                    'alignment_scores': alignment_scores,
                    'master_profiles': master_profiles,
                    'migration_patterns': migration_patterns,
                    'stability_metrics': stability_metrics
                }
                
                population_results[k_value] = results
                
                # Save individual results
                self._save_k_results(results, k_value, population_type)
            
            all_results[population_type] = population_results
            
            # Generate population summary
            self._generate_population_summary(population_results, population_type)
        
        # Generate final summary report
        self._generate_final_summary(all_results)
        
        print("\n" + "=" * 80)
        print("ANALYSIS COMPLETE")
        print(f"Results saved to: {self.output_dir}")
        print("=" * 80)
    
    def _generate_visualizations(
        self,
        master_assignments: Dict,
        master_profiles: Dict,
        stability_metrics: Dict,
        k_value: int,
        population_type: str
    ):
        """Generate all visualizations for a specific K value."""
        
        # Create subdirectory for this configuration
        viz_dir = self.plots_dir / f"{population_type}_k{k_value}"
        viz_dir.mkdir(exist_ok=True)
        
        print(f"Generating visualizations...")
        
        # 1. Alignment heatmap
        self.visualizer.create_alignment_heatmap(
            master_assignments,
            k_value,
            population_type,
            save_path=viz_dir / "alignment_heatmap.png"
        )
        
        # 2. Stability metrics plot
        self.visualizer.plot_stability_metrics(
            stability_metrics,
            save_path=viz_dir / "stability_metrics.png"
        )
        
        # 3. Master cluster evolution
        self.visualizer.plot_master_cluster_evolution(
            master_assignments,
            master_profiles,
            k_value,
            save_path=viz_dir / "cluster_evolution.png"
        )
        
        # 4. Cross-percentile flow
        self.visualizer.create_cross_percentile_flow(
            master_assignments,
            k_value,
            population_type,
            save_path=viz_dir / "percentile_flow.png"
        )
        
        print(f"Visualizations saved to {viz_dir}")
    
    def _save_k_results(self, results: Dict, k_value: int, population_type: str):
        """Save results for a specific K value."""
        
        # Save assignments (convert numpy types first)
        assignments_file = self.data_dir / f"{population_type}_k{k_value}_assignments.json"
        assignments_native = convert_numpy_to_native(results['master_assignments'])
        with open(assignments_file, 'w') as f:
            json.dump(assignments_native, f, indent=2)
        
        # Save full results
        results_file = self.data_dir / f"{population_type}_k{k_value}_results.json"
        
        # Convert all results to native types for JSON serialization
        serializable_results = convert_numpy_to_native({
            'master_assignments': results['master_assignments'],
            'alignment_scores': results['alignment_scores'],
            'master_profiles': results['master_profiles'],
            'migration_patterns': results['migration_patterns'],
            'stability_metrics': results['stability_metrics']
        })
        
        with open(results_file, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        print(f"Results saved to {results_file}")
    
    def _generate_population_summary(self, population_results: Dict, population_type: str):
        """Generate summary report for a population."""
        
        report_file = self.reports_dir / f"{population_type}_summary.txt"
        
        with open(report_file, 'w') as f:
            f.write(f"{'='*80}\n")
            f.write(f"CLUSTER ALIGNMENT SUMMARY: {population_type}\n")
            f.write(f"{'='*80}\n\n")
            
            # Summary table
            f.write("K-VALUE COMPARISON\n")
            f.write("-" * 60 + "\n")
            f.write(f"{'K':<5} {'Avg Alignment':<15} {'Stability':<15} {'Coherence':<15} {'Migrations':<15}\n")
            f.write("-" * 60 + "\n")
            
            best_k = None
            best_stability = 0
            
            for k_value, results in sorted(population_results.items()):
                avg_alignment = np.mean(list(results['alignment_scores'].values()))
                overall_stability = results['stability_metrics']['overall_stability']
                avg_coherence = results['stability_metrics']['master_coherence']['average_coherence']
                migration_rate = results['migration_patterns']['migration_rate']
                
                f.write(f"{k_value:<5} {avg_alignment:<15.3f} {overall_stability:<15.3f} "
                       f"{avg_coherence:<15.3f} {migration_rate:<15.3f}\n")
                
                if overall_stability > best_stability:
                    best_stability = overall_stability
                    best_k = k_value
            
            f.write("\n" + "="*60 + "\n")
            f.write(f"RECOMMENDED K VALUE: {best_k} (stability: {best_stability:.3f})\n")
            f.write("="*60 + "\n\n")
            
            # Detailed results for best K
            if best_k:
                f.write(f"DETAILED RESULTS FOR K={best_k}\n")
                f.write("-" * 60 + "\n\n")
                
                best_results = population_results[best_k]
                
                # Master cluster profiles
                f.write("Master Cluster Profiles:\n")
                f.write("-" * 40 + "\n")
                
                for master_id, profile in best_results['master_profiles'].items():
                    f.write(f"\n{master_id}:\n")
                    f.write(f"  Members: {profile['n_members']}\n")
                    f.write(f"  Percentiles: {profile['percentiles_present']}\n")
                    f.write(f"  Top Features:\n")
                    for feat, imp in profile['top_features'][:5]:
                        f.write(f"    - {feat}: {imp:.3f}\n")
                
                # Stability metrics
                f.write("\n" + "="*60 + "\n")
                f.write("Stability Metrics:\n")
                f.write("-" * 40 + "\n")
                
                metrics = best_results['stability_metrics']
                f.write(f"  Overall Stability: {metrics['overall_stability']:.3f}\n")
                f.write(f"  Transition Consistency: {metrics['transition_consistency']['avg_transition_consistency']:.3f}\n")
                f.write(f"  Average Coherence: {metrics['master_coherence']['average_coherence']:.3f}\n")
                f.write(f"  Average Purity: {metrics['cluster_purity']['average_purity']:.3f}\n")
                
                # Most and least stable percentiles
                f.write(f"\n  Most Stable Percentile: {metrics['percentile_stability']['most_stable_percentile']}\n")
                f.write(f"  Least Stable Percentile: {metrics['percentile_stability']['least_stable_percentile']}\n")
        
        print(f"Population summary saved to {report_file}")
    
    def _generate_final_summary(self, all_results: Dict):
        """Generate final summary report across all populations."""
        
        report_file = self.reports_dir / "final_summary_report.txt"
        
        with open(report_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write("CLUSTER ALIGNMENT ANALYSIS - FINAL SUMMARY\n")
            f.write("="*80 + "\n\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Output Directory: {self.output_dir}\n\n")
            
            # Cross-population comparison
            f.write("CROSS-POPULATION COMPARISON\n")
            f.write("="*60 + "\n\n")
            
            for population_type, pop_results in all_results.items():
                f.write(f"\n{population_type.upper()}\n")
                f.write("-"*40 + "\n")
                
                # Find best K for this population
                best_k = None
                best_stability = 0
                
                for k_value, results in pop_results.items():
                    stability = results['stability_metrics']['overall_stability']
                    if stability > best_stability:
                        best_stability = stability
                        best_k = k_value
                
                f.write(f"Best K value: {best_k}\n")
                f.write(f"Best stability score: {best_stability:.3f}\n")
                
                if best_k:
                    best_results = pop_results[best_k]
                    f.write(f"Average alignment score: {np.mean(list(best_results['alignment_scores'].values())):.3f}\n")
                    f.write(f"Migration rate: {best_results['migration_patterns']['migration_rate']:.3f}\n")
                    f.write(f"Number of stable master clusters: {best_k}\n")
            
            # Recommendations
            f.write("\n" + "="*60 + "\n")
            f.write("RECOMMENDATIONS\n")
            f.write("="*60 + "\n\n")
            
            f.write("1. K-VALUE SELECTION:\n")
            for population_type, pop_results in all_results.items():
                best_k = max(pop_results.keys(), 
                           key=lambda k: pop_results[k]['stability_metrics']['overall_stability'])
                f.write(f"   - {population_type}: Use K={best_k}\n")
            
            f.write("\n2. STABLE PERCENTILE RANGES:\n")
            for population_type, pop_results in all_results.items():
                # Find most stable percentiles
                for k_value, results in pop_results.items():
                    if k_value == best_k:
                        stable_percentiles = []
                        for p, score in results['stability_metrics']['percentile_stability']['per_percentile_stability'].items():
                            if score['stability_score'] >= 0.8:
                                stable_percentiles.append(p)
                        
                        if stable_percentiles:
                            f.write(f"   - {population_type}: Percentiles {', '.join(stable_percentiles)}\n")
                        else:
                            f.write(f"   - {population_type}: No highly stable percentiles (>0.8)\n")
            
            f.write("\n3. FEATURE IMPORTANCE:\n")
            f.write("   Review master cluster profiles for consistent feature patterns\n")
            f.write("   across percentiles to identify key discriminating features.\n")
            
            f.write("\n" + "="*80 + "\n")
            f.write("END OF REPORT\n")
            f.write("="*80 + "\n")
        
        print(f"\nFinal summary report saved to {report_file}")


def main():
    """
    Main entry point for running the alignment analysis.
    """
    print("\nStarting Cluster Alignment Analysis...")
    
    # Initialize pipeline
    pipeline = AlignmentAnalysisPipeline()
    
    # Run complete analysis
    pipeline.run_complete_analysis(
        population_types=['with_breakdown', 'no_breakdown'],
        k_values=[3, 4, 5, 6, 7, 8],
        reference_percentiles={
            'with_breakdown': '50',
            'no_breakdown': '50'
        }
    )
    
    print("\nAnalysis complete!")


if __name__ == "__main__":
    main()