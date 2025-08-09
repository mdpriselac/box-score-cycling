"""
Master Cluster Feature Comparison Report Generator

Creates detailed reports comparing master cluster feature profiles
across different reference percentiles.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns


class MasterClusterFeatureComparison:
    """
    Generates comprehensive feature comparison reports for master clusters
    across different reference percentiles.
    """
    
    def __init__(self, meta_results_dir: str = 'meta_reference_results'):
        """
        Initialize the feature comparison analyzer.
        
        Args:
            meta_results_dir: Directory containing meta-analysis results
        """
        self.meta_results_dir = Path(meta_results_dir)
        self.individual_results_dir = self.meta_results_dir / 'individual_alignments'
        
        self.output_dir = self.meta_results_dir / 'feature_comparisons'
        self.output_dir.mkdir(exist_ok=True)
        
        self.reference_percentiles = ['10', '25', '50', '75', '95']
    
    def generate_all_feature_comparisons(
        self,
        population_types: List[str] = ['with_breakdown', 'no_breakdown'],
        k_values: List[int] = [3, 4, 5, 6, 7, 8]
    ):
        """
        Generate feature comparison reports for all populations and K values.
        
        Args:
            population_types: List of population types to analyze
            k_values: List of K values to analyze
        """
        print("="*80)
        print("MASTER CLUSTER FEATURE COMPARISON REPORT GENERATION")
        print("="*80)
        
        for population_type in population_types:
            print(f"\nGenerating reports for {population_type}...")
            
            for k_value in k_values:
                print(f"  Processing K={k_value}...")
                
                # Generate detailed feature comparison
                self._generate_feature_comparison_report(population_type, k_value)
                
                # Generate feature stability analysis
                self._generate_feature_stability_report(population_type, k_value)
                
                # Generate cross-reference heatmaps
                self._generate_feature_heatmaps(population_type, k_value)
        
        # Generate summary comparison across all configurations
        self._generate_summary_comparison(population_types, k_values)
        
        print(f"\nAll feature comparison reports saved to: {self.output_dir}")
    
    def _generate_feature_comparison_report(self, population_type: str, k_value: int):
        """Generate detailed feature comparison report for a specific configuration."""
        
        # Load master cluster profiles for all reference percentiles
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            print(f"    No results found for {population_type} K={k_value}")
            return
        
        # Generate detailed report
        report_path = self.output_dir / f"{population_type}_k{k_value}_feature_comparison.txt"
        
        with open(report_path, 'w') as f:
            f.write("="*100 + "\n")
            f.write(f"MASTER CLUSTER FEATURE COMPARISON\n")
            f.write(f"Population: {population_type} | K-Value: {k_value}\n")
            f.write("="*100 + "\n\n")
            
            # For each master cluster
            for master_id in range(k_value):
                f.write(f"MASTER CLUSTER {master_id}\n")
                f.write("-"*50 + "\n\n")
                
                # Create comparison table for this master cluster
                self._write_master_cluster_comparison(f, master_profiles_by_ref, f"master_{master_id}")
                
                f.write("\n" + "="*100 + "\n\n")
        
        print(f"    Saved detailed comparison: {report_path}")
    
    def _write_master_cluster_comparison(self, f, master_profiles_by_ref: Dict, master_key: str):
        """Write detailed comparison for a single master cluster."""
        
        # Collect all features and their importance across references
        feature_data = {}
        
        for ref_percentile, profiles in master_profiles_by_ref.items():
            if master_key in profiles:
                top_features = profiles[master_key]['top_features']
                
                for feature, importance in top_features[:10]:  # Top 10 features
                    if feature not in feature_data:
                        feature_data[feature] = {}
                    feature_data[feature][ref_percentile] = importance
        
        if not feature_data:
            f.write("No feature data available for this master cluster.\n")
            return
        
        # Write header
        f.write(f"{'Feature':<35}")
        for ref in self.reference_percentiles:
            f.write(f"{'Ref'+ref+'%':<12}")
        f.write(f"{'Consistency':<12}{'Avg':<10}{'Range':<15}\n")
        f.write("-"*120 + "\n")
        
        # Calculate feature statistics
        feature_stats = {}
        for feature, ref_importances in feature_data.items():
            values = [ref_importances.get(ref, 0.0) for ref in self.reference_percentiles]
            non_zero_values = [v for v in values if v > 0]
            
            if non_zero_values:
                avg_importance = np.mean(non_zero_values)
                importance_range = max(non_zero_values) - min(non_zero_values)
                consistency = len(non_zero_values) / len(self.reference_percentiles)  # Fraction of references where feature appears
            else:
                avg_importance = 0
                importance_range = 0
                consistency = 0
            
            feature_stats[feature] = {
                'avg': avg_importance,
                'range': importance_range,
                'consistency': consistency,
                'values': values
            }
        
        # Sort features by average importance
        sorted_features = sorted(feature_stats.items(), key=lambda x: x[1]['avg'], reverse=True)
        
        # Write feature data
        for feature, stats in sorted_features:
            f.write(f"{feature[:34]:<35}")
            
            for ref in self.reference_percentiles:
                importance = feature_data[feature].get(ref, 0.0)
                if importance > 0:
                    f.write(f"{importance:<12.4f}")
                else:
                    f.write(f"{'--':<12}")
            
            f.write(f"{stats['consistency']:<12.2f}")
            f.write(f"{stats['avg']:<10.4f}")
            f.write(f"{stats['range']:<15.4f}")
            f.write("\n")
        
        f.write("\n")
        f.write("Legend:\n")
        f.write("  Consistency: Fraction of references where feature appears in top 10\n")
        f.write("  Avg: Average importance across references where feature appears\n")
        f.write("  Range: Difference between max and min importance values\n")
        f.write("  --: Feature not in top 10 for this reference\n\n")
    
    def _generate_feature_stability_report(self, population_type: str, k_value: int):
        """Generate feature stability analysis report."""
        
        # Load master cluster profiles for all reference percentiles
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            return
        
        # Analyze feature stability across references
        stability_data = []
        
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            
            # Collect all unique features for this master cluster
            all_features = set()
            feature_importances = {}
            
            for ref_percentile, profiles in master_profiles_by_ref.items():
                if master_key in profiles:
                    top_features = profiles[master_key]['top_features']
                    
                    for feature, importance in top_features[:10]:
                        all_features.add(feature)
                        if feature not in feature_importances:
                            feature_importances[feature] = {}
                        feature_importances[feature][ref_percentile] = importance
            
            # Calculate stability metrics for each feature
            for feature in all_features:
                ref_values = []
                for ref in self.reference_percentiles:
                    if ref in feature_importances[feature]:
                        ref_values.append(feature_importances[feature][ref])
                
                if len(ref_values) >= 2:
                    stability_data.append({
                        'master_cluster': master_id,
                        'feature': feature,
                        'appearances': len(ref_values),
                        'consistency': len(ref_values) / len(self.reference_percentiles),
                        'avg_importance': np.mean(ref_values),
                        'std_importance': np.std(ref_values),
                        'cv': np.std(ref_values) / np.mean(ref_values) if np.mean(ref_values) > 0 else 0,
                        'min_importance': np.min(ref_values),
                        'max_importance': np.max(ref_values),
                        'range': np.max(ref_values) - np.min(ref_values)
                    })
        
        # Create stability report
        stability_df = pd.DataFrame(stability_data)
        
        if not stability_df.empty:
            report_path = self.output_dir / f"{population_type}_k{k_value}_feature_stability.csv"
            stability_df.to_csv(report_path, index=False)
            
            # Create summary statistics
            summary_path = self.output_dir / f"{population_type}_k{k_value}_stability_summary.txt"
            
            with open(summary_path, 'w') as f:
                f.write("="*80 + "\n")
                f.write(f"FEATURE STABILITY SUMMARY\n")
                f.write(f"Population: {population_type} | K-Value: {k_value}\n")
                f.write("="*80 + "\n\n")
                
                # Most stable features (high consistency, low CV)
                f.write("MOST STABLE FEATURES (appear in most references with consistent importance):\n")
                f.write("-"*70 + "\n")
                stable_features = stability_df.sort_values(['consistency', 'cv'], ascending=[False, True]).head(15)
                
                for _, row in stable_features.iterrows():
                    f.write(f"Master {int(row['master_cluster'])} - {row['feature'][:40]:<40} ")
                    f.write(f"(consistency: {row['consistency']:.2f}, CV: {row['cv']:.3f})\n")
                
                f.write("\n\nMOST VARIABLE FEATURES (importance changes significantly across references):\n")
                f.write("-"*70 + "\n")
                variable_features = stability_df[stability_df['consistency'] >= 0.6].sort_values('cv', ascending=False).head(15)
                
                for _, row in variable_features.iterrows():
                    f.write(f"Master {int(row['master_cluster'])} - {row['feature'][:40]:<40} ")
                    f.write(f"(CV: {row['cv']:.3f}, range: {row['range']:.4f})\n")
                
                f.write(f"\n\nOVERALL STATISTICS:\n")
                f.write("-"*30 + "\n")
                f.write(f"Average feature consistency: {stability_df['consistency'].mean():.3f}\n")
                f.write(f"Average coefficient of variation: {stability_df['cv'].mean():.3f}\n")
                f.write(f"Features appearing in all references: {len(stability_df[stability_df['consistency'] == 1.0])}\n")
                f.write(f"Features appearing in only one reference: {len(stability_df[stability_df['consistency'] == 0.2])}\n")
            
            print(f"    Saved stability analysis: {report_path}")
            print(f"    Saved stability summary: {summary_path}")
    
    def _generate_feature_heatmaps(self, population_type: str, k_value: int):
        """Generate heatmaps showing feature importance across references for each master cluster."""
        
        # Load master cluster profiles for all reference percentiles
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            return
        
        # Create heatmap for each master cluster
        fig, axes = plt.subplots(k_value, 1, figsize=(14, 4*k_value))
        if k_value == 1:
            axes = [axes]
        
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            
            # Collect feature importance data
            feature_data = {}
            
            for ref_percentile, profiles in master_profiles_by_ref.items():
                if master_key in profiles:
                    top_features = profiles[master_key]['top_features']
                    
                    for feature, importance in top_features[:15]:  # Top 15 for heatmap
                        if feature not in feature_data:
                            feature_data[feature] = {}
                        feature_data[feature][ref_percentile] = importance
            
            if feature_data:
                # Create DataFrame for heatmap
                heatmap_data = []
                feature_names = []
                
                # Sort features by average importance
                feature_avgs = {}
                for feature, ref_importances in feature_data.items():
                    values = [ref_importances.get(ref, 0.0) for ref in self.reference_percentiles]
                    feature_avgs[feature] = np.mean([v for v in values if v > 0])
                
                sorted_features = sorted(feature_avgs.items(), key=lambda x: x[1], reverse=True)
                
                for feature, _ in sorted_features:
                    row = []
                    for ref in self.reference_percentiles:
                        importance = feature_data[feature].get(ref, 0.0)
                        row.append(importance)
                    heatmap_data.append(row)
                    feature_names.append(feature[:25])  # Truncate long names
                
                if heatmap_data:
                    heatmap_array = np.array(heatmap_data)
                    
                    sns.heatmap(
                        heatmap_array,
                        xticklabels=[f"Ref {p}%" for p in self.reference_percentiles],
                        yticklabels=feature_names,
                        annot=True,
                        fmt='.3f',
                        cmap='YlOrRd',
                        ax=axes[master_id],
                        cbar_kws={'label': 'Feature Importance'}
                    )
                    
                    axes[master_id].set_title(f'Master Cluster {master_id} - Top Features Across References')
                    axes[master_id].set_xlabel('Reference Percentile')
            else:
                axes[master_id].text(0.5, 0.5, f'No data for Master Cluster {master_id}', 
                                    ha='center', va='center', transform=axes[master_id].transAxes)
                axes[master_id].set_title(f'Master Cluster {master_id} - No Data')
        
        plt.suptitle(f'Feature Importance Heatmaps - {population_type} (K={k_value})', fontsize=16)
        plt.tight_layout()
        
        heatmap_path = self.output_dir / f"{population_type}_k{k_value}_feature_heatmaps.png"
        plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved feature heatmaps: {heatmap_path}")
    
    def _generate_summary_comparison(self, population_types: List[str], k_values: List[int]):
        """Generate overall summary comparing feature patterns across all configurations."""
        
        summary_path = self.output_dir / "overall_feature_comparison_summary.txt"
        
        with open(summary_path, 'w') as f:
            f.write("="*100 + "\n")
            f.write("OVERALL FEATURE COMPARISON SUMMARY\n")
            f.write("="*100 + "\n\n")
            
            f.write("This summary analyzes feature consistency patterns across all populations,\n")
            f.write("K-values, and reference percentiles to identify the most robust and\n")
            f.write("variable features in race kind classification.\n\n")
            
            for population_type in population_types:
                f.write(f"POPULATION: {population_type.upper()}\n")
                f.write("="*60 + "\n\n")
                
                for k_value in k_values:
                    stability_file = self.output_dir / f"{population_type}_k{k_value}_feature_stability.csv"
                    
                    if stability_file.exists():
                        stability_df = pd.read_csv(stability_file)
                        
                        f.write(f"K={k_value}:\n")
                        f.write("-"*20 + "\n")
                        
                        # Most consistent features
                        most_consistent = stability_df.nlargest(5, 'consistency')[['feature', 'consistency', 'avg_importance']]
                        f.write("  Most Consistent Features:\n")
                        for _, row in most_consistent.iterrows():
                            f.write(f"    - {row['feature']:<30} (consistency: {row['consistency']:.2f})\n")
                        
                        # Most variable features with high consistency
                        high_consistency = stability_df[stability_df['consistency'] >= 0.8]
                        if not high_consistency.empty:
                            most_variable = high_consistency.nlargest(3, 'cv')[['feature', 'cv', 'range']]
                            f.write("\n  Most Variable Features (among highly consistent ones):\n")
                            for _, row in most_variable.iterrows():
                                f.write(f"    - {row['feature']:<30} (CV: {row['cv']:.3f})\n")
                        
                        f.write("\n")
                
                f.write("\n")
        
        print(f"\nOverall summary saved to: {summary_path}")


def main():
    """Main entry point for feature comparison report generation."""
    print("Starting Master Cluster Feature Comparison Report Generation...")
    
    # Initialize comparison analyzer
    comparator = MasterClusterFeatureComparison()
    
    # Generate all feature comparison reports
    comparator.generate_all_feature_comparisons(
        population_types=['with_breakdown', 'no_breakdown'],
        k_values=[3, 4, 5, 6, 7, 8]
    )
    
    print("\nFeature comparison report generation complete!")


if __name__ == "__main__":
    main()