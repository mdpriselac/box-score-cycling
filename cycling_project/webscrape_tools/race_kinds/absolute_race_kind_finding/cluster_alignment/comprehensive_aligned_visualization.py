"""
Comprehensive Aligned Visualization and Analysis System

Generates all visualizations and detailed data analysis using the proper
cross-reference alignment system. This builds on the aligned analysis to 
create comprehensive reports, visualizations, and data exports.
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
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend


class ComprehensiveAlignedAnalyzer:
    """
    Creates comprehensive visualizations and analysis based on properly aligned
    master clusters across reference percentiles.
    """
    
    def __init__(self, meta_results_dir: str = 'meta_reference_results'):
        """
        Initialize the comprehensive analyzer.
        
        Args:
            meta_results_dir: Directory containing meta-analysis results
        """
        self.meta_results_dir = Path(meta_results_dir)
        self.individual_results_dir = self.meta_results_dir / 'individual_alignments'
        self.aligned_analysis_dir = self.meta_results_dir / 'aligned_feature_analysis'
        
        self.output_dir = self.meta_results_dir / 'comprehensive_analysis'
        self.output_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.plots_dir = self.output_dir / 'plots'
        self.plots_dir.mkdir(exist_ok=True)
        
        self.data_dir = self.output_dir / 'data'
        self.data_dir.mkdir(exist_ok=True)
        
        self.tables_dir = self.output_dir / 'tables'
        self.tables_dir.mkdir(exist_ok=True)
        
        self.reference_percentiles = ['10', '25', '50', '75', '95']
    
    def generate_all_comprehensive_analysis(
        self,
        population_types: List[str] = ['with_breakdown', 'no_breakdown'],
        k_values: List[int] = [3, 4, 5, 6, 7, 8]
    ):
        """
        Generate all comprehensive visualizations and analysis.
        
        Args:
            population_types: List of population types to analyze
            k_values: List of K values to analyze
        """
        print("="*80)
        print("COMPREHENSIVE ALIGNED ANALYSIS AND VISUALIZATION")
        print("="*80)
        
        for population_type in population_types:
            print(f"\nProcessing population: {population_type}")
            
            for k_value in k_values:
                print(f"  Generating comprehensive analysis for K={k_value}...")
                
                # 1. Cross-reference correlation heatmaps
                self._generate_cross_reference_heatmaps(population_type, k_value)
                
                # 2. Feature evolution visualizations
                self._generate_feature_evolution_plots(population_type, k_value)
                
                # 3. Stability trend plots
                self._generate_stability_trend_plots(population_type, k_value)
                
                # 4. Aligned master cluster comparison tables
                self._generate_aligned_comparison_tables(population_type, k_value)
                
                # 5. Master cluster flow diagrams
                self._generate_master_cluster_flow_diagrams(population_type, k_value)
                
                # 6. Feature consistency radar charts
                self._generate_feature_consistency_radar_charts(population_type, k_value)
        
        # Generate cross-population and cross-K summaries
        self._generate_cross_population_summaries(population_types, k_values)
        
        print(f"\nAll comprehensive analysis saved to: {self.output_dir}")
    
    def _generate_cross_reference_heatmaps(self, population_type: str, k_value: int):
        """Generate detailed cross-reference correlation heatmaps."""
        
        # Load alignment results
        alignment_file = self.aligned_analysis_dir / f"{population_type}_k{k_value}_aligned_analysis.txt"
        if not alignment_file.exists():
            print(f"    No alignment data for {population_type} K={k_value}")
            return
        
        # Load master embeddings for all references
        master_embeddings_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_embeddings = {}
                    for master_id, embedding in results['master_embeddings'].items():
                        master_embeddings[int(master_id)] = np.array(embedding)
                    master_embeddings_by_ref[ref_percentile] = master_embeddings
        
        if len(master_embeddings_by_ref) < 2:
            return
        
        # Calculate cross-reference similarity matrix
        n_refs = len(self.reference_percentiles)
        similarity_matrix = np.zeros((n_refs, n_refs))
        
        for i, ref1 in enumerate(self.reference_percentiles):
            for j, ref2 in enumerate(self.reference_percentiles):
                if ref1 in master_embeddings_by_ref and ref2 in master_embeddings_by_ref:
                    if i == j:
                        similarity_matrix[i, j] = 1.0
                    else:
                        # Calculate optimal alignment similarity
                        sim_score, _ = self._align_master_clusters(
                            master_embeddings_by_ref[ref1],
                            master_embeddings_by_ref[ref2]
                        )
                        similarity_matrix[i, j] = sim_score
        
        # Create comprehensive heatmap
        fig, axes = plt.subplots(1, 2, figsize=(20, 8))
        
        # Overall similarity heatmap
        sns.heatmap(
            similarity_matrix,
            xticklabels=[f"Ref {p}%" for p in self.reference_percentiles],
            yticklabels=[f"Ref {p}%" for p in self.reference_percentiles],
            annot=True,
            fmt='.3f',
            cmap='RdBu_r',
            center=0.7,
            vmin=0,
            vmax=1,
            ax=axes[0],
            cbar_kws={'label': 'Alignment Similarity'}
        )
        axes[0].set_title(f'Cross-Reference Master Cluster Similarity\n{population_type} (K={k_value})')
        
        # Individual master cluster similarities
        master_similarities = np.zeros((k_value, len(self.reference_percentiles)))
        
        for master_id in range(k_value):
            for j, ref in enumerate(self.reference_percentiles):
                if ref in master_embeddings_by_ref:
                    # Calculate this master's consistency across references
                    similarities = []
                    base_embedding = master_embeddings_by_ref[ref][master_id]
                    
                    for other_ref in self.reference_percentiles:
                        if other_ref != ref and other_ref in master_embeddings_by_ref:
                            # Find best matching master in other reference
                            best_sim = 0
                            for other_master_id in range(k_value):
                                other_embedding = master_embeddings_by_ref[other_ref][other_master_id]
                                sim = cosine_similarity([base_embedding], [other_embedding])[0][0]
                                best_sim = max(best_sim, sim)
                            similarities.append(best_sim)
                    
                    master_similarities[master_id, j] = np.mean(similarities) if similarities else 0
        
        sns.heatmap(
            master_similarities,
            xticklabels=[f"Ref {p}%" for p in self.reference_percentiles],
            yticklabels=[f"Master {i}" for i in range(k_value)],
            annot=True,
            fmt='.3f',
            cmap='viridis',
            ax=axes[1],
            cbar_kws={'label': 'Cross-Reference Consistency'}
        )
        axes[1].set_title(f'Individual Master Cluster Consistency\n{population_type} (K={k_value})')
        
        plt.tight_layout()
        save_path = self.plots_dir / f"{population_type}_k{k_value}_cross_reference_heatmaps.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved cross-reference heatmaps: {save_path}")
    
    def _generate_feature_evolution_plots(self, population_type: str, k_value: int):
        """Generate plots showing how top features evolve across reference percentiles."""
        
        # Load master profiles for all references
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            return
        
        # Create feature evolution plots
        fig, axes = plt.subplots(k_value, 1, figsize=(16, 6*k_value))
        if k_value == 1:
            axes = [axes]
        
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            
            # Collect all features that appear in top 10 for this master
            all_features = set()
            feature_importance_by_ref = {}
            
            for ref, profiles in master_profiles_by_ref.items():
                if master_key in profiles:
                    top_features = profiles[master_key]['top_features']
                    feature_importance_by_ref[ref] = dict(top_features[:15])
                    all_features.update([f for f, _ in top_features[:15]])
            
            # Select top features by average importance
            feature_avgs = {}
            for feature in all_features:
                importances = []
                for ref in self.reference_percentiles:
                    if ref in feature_importance_by_ref and feature in feature_importance_by_ref[ref]:
                        importances.append(feature_importance_by_ref[ref][feature])
                if importances:
                    feature_avgs[feature] = np.mean(importances)
            
            # Plot top features
            top_features = sorted(feature_avgs.items(), key=lambda x: x[1], reverse=True)[:8]
            
            for feature, _ in top_features:
                y_values = []
                for ref in self.reference_percentiles:
                    if ref in feature_importance_by_ref and feature in feature_importance_by_ref[ref]:
                        y_values.append(feature_importance_by_ref[ref][feature])
                    else:
                        y_values.append(0)
                
                axes[master_id].plot(self.reference_percentiles, y_values, 
                                   marker='o', linewidth=2, markersize=6, 
                                   label=feature[:25])
            
            axes[master_id].set_title(f'Master Cluster {master_id} - Feature Evolution')
            axes[master_id].set_xlabel('Reference Percentile')
            axes[master_id].set_ylabel('Feature Importance')
            axes[master_id].legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
            axes[master_id].grid(True, alpha=0.3)
        
        plt.suptitle(f'Feature Evolution Across References - {population_type} (K={k_value})', fontsize=16)
        plt.tight_layout()
        
        save_path = self.plots_dir / f"{population_type}_k{k_value}_feature_evolution.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved feature evolution plot: {save_path}")
    
    def _generate_stability_trend_plots(self, population_type: str, k_value: int):
        """Generate plots showing stability trends across different metrics."""
        
        # Load alignment analysis results
        alignment_file = self.aligned_analysis_dir / f"{population_type}_k{k_value}_aligned_analysis.txt"
        if not alignment_file.exists():
            return
        
        # Calculate stability metrics across reference pairs
        stability_data = []
        
        # Load master embeddings
        master_embeddings_by_ref = {}
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_embeddings = {}
                    for master_id, embedding in results['master_embeddings'].items():
                        master_embeddings[int(master_id)] = np.array(embedding)
                    master_embeddings_by_ref[ref_percentile] = master_embeddings
        
        # Calculate pairwise stabilities
        for ref1, ref2 in combinations(self.reference_percentiles, 2):
            if ref1 in master_embeddings_by_ref and ref2 in master_embeddings_by_ref:
                alignment_score, mapping = self._align_master_clusters(
                    master_embeddings_by_ref[ref1],
                    master_embeddings_by_ref[ref2]
                )
                
                ref_distance = abs(int(ref1) - int(ref2))
                stability_data.append({
                    'ref1': int(ref1),
                    'ref2': int(ref2),
                    'ref_distance': ref_distance,
                    'alignment_score': alignment_score
                })
        
        if not stability_data:
            return
        
        stability_df = pd.DataFrame(stability_data)
        
        # Create stability trend plots
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 1. Stability vs Reference Distance
        axes[0, 0].scatter(stability_df['ref_distance'], stability_df['alignment_score'], 
                          alpha=0.7, s=60)
        axes[0, 0].set_xlabel('Reference Percentile Distance')
        axes[0, 0].set_ylabel('Alignment Score')
        axes[0, 0].set_title('Stability vs Reference Distance')
        axes[0, 0].grid(True, alpha=0.3)
        
        # Add trend line
        z = np.polyfit(stability_df['ref_distance'], stability_df['alignment_score'], 1)
        p = np.poly1d(z)
        x_trend = np.linspace(stability_df['ref_distance'].min(), stability_df['ref_distance'].max(), 100)
        axes[0, 0].plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2)
        
        # 2. Stability by reference percentile
        ref_stability = {}
        for ref in self.reference_percentiles:
            ref_scores = []
            for _, row in stability_df.iterrows():
                if row['ref1'] == int(ref) or row['ref2'] == int(ref):
                    ref_scores.append(row['alignment_score'])
            if ref_scores:
                ref_stability[ref] = np.mean(ref_scores)
        
        if ref_stability:
            refs = list(ref_stability.keys())
            scores = list(ref_stability.values())
            axes[0, 1].bar(refs, scores, alpha=0.7, color='skyblue', edgecolor='navy')
            axes[0, 1].set_xlabel('Reference Percentile')
            axes[0, 1].set_ylabel('Average Alignment Score')
            axes[0, 1].set_title('Stability by Reference Percentile')
            axes[0, 1].grid(True, alpha=0.3, axis='y')
        
        # 3. Stability distribution
        axes[1, 0].hist(stability_df['alignment_score'], bins=15, alpha=0.7, 
                       color='lightgreen', edgecolor='darkgreen')
        axes[1, 0].axvline(stability_df['alignment_score'].mean(), color='red', 
                          linestyle='--', linewidth=2, label=f'Mean: {stability_df["alignment_score"].mean():.3f}')
        axes[1, 0].set_xlabel('Alignment Score')
        axes[1, 0].set_ylabel('Frequency')
        axes[1, 0].set_title('Alignment Score Distribution')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 4. Stability heatmap
        stability_matrix = np.zeros((len(self.reference_percentiles), len(self.reference_percentiles)))
        for i, ref1 in enumerate(self.reference_percentiles):
            for j, ref2 in enumerate(self.reference_percentiles):
                if i == j:
                    stability_matrix[i, j] = 1.0
                else:
                    matching_rows = stability_df[
                        ((stability_df['ref1'] == int(ref1)) & (stability_df['ref2'] == int(ref2))) |
                        ((stability_df['ref1'] == int(ref2)) & (stability_df['ref2'] == int(ref1)))
                    ]
                    if not matching_rows.empty:
                        stability_matrix[i, j] = matching_rows['alignment_score'].iloc[0]
        
        sns.heatmap(stability_matrix,
                   xticklabels=[f"{p}%" for p in self.reference_percentiles],
                   yticklabels=[f"{p}%" for p in self.reference_percentiles],
                   annot=True, fmt='.3f', cmap='RdYlBu_r',
                   ax=axes[1, 1], cbar_kws={'label': 'Alignment Score'})
        axes[1, 1].set_title('Pairwise Stability Matrix')
        
        plt.suptitle(f'Stability Analysis - {population_type} (K={k_value})', fontsize=16)
        plt.tight_layout()
        
        save_path = self.plots_dir / f"{population_type}_k{k_value}_stability_trends.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved stability trends plot: {save_path}")
    
    def _generate_aligned_comparison_tables(self, population_type: str, k_value: int):
        """Generate detailed aligned master cluster comparison tables."""
        
        # Load master profiles for all references
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            return
        
        # Create aligned comparison tables
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            
            # Collect feature data across references
            feature_comparison_data = []
            
            # Get all unique features for this master cluster
            all_features = set()
            for ref, profiles in master_profiles_by_ref.items():
                if master_key in profiles:
                    top_features = profiles[master_key]['top_features']
                    all_features.update([f for f, _ in top_features])
            
            # Create comparison data
            for feature in sorted(all_features):
                row = {'feature': feature}
                
                # Add importance for each reference
                for ref in self.reference_percentiles:
                    if ref in master_profiles_by_ref and master_key in master_profiles_by_ref[ref]:
                        top_features_dict = dict(master_profiles_by_ref[ref][master_key]['top_features'])
                        importance = top_features_dict.get(feature, 0.0)
                        row[f'ref_{ref}'] = importance
                    else:
                        row[f'ref_{ref}'] = 0.0
                
                # Calculate statistics
                importances = [row[f'ref_{ref}'] for ref in self.reference_percentiles if row[f'ref_{ref}'] > 0]
                if importances:
                    row['avg_importance'] = np.mean(importances)
                    row['std_importance'] = np.std(importances)
                    row['cv'] = np.std(importances) / np.mean(importances) if np.mean(importances) > 0 else 0
                    row['consistency'] = len(importances) / len(self.reference_percentiles)
                    row['range'] = max(importances) - min(importances)
                else:
                    row['avg_importance'] = 0
                    row['std_importance'] = 0
                    row['cv'] = 0
                    row['consistency'] = 0
                    row['range'] = 0
                
                feature_comparison_data.append(row)
            
            # Create DataFrame and save
            comparison_df = pd.DataFrame(feature_comparison_data)
            comparison_df = comparison_df.sort_values(['avg_importance'], ascending=False)
            
            table_path = self.tables_dir / f"{population_type}_k{k_value}_master{master_id}_comparison.csv"
            comparison_df.to_csv(table_path, index=False, float_format='%.4f')
            
            print(f"    Saved master {master_id} comparison table: {table_path}")
    
    def _generate_master_cluster_flow_diagrams(self, population_type: str, k_value: int):
        """Generate flow diagrams showing master cluster evolution."""
        
        # Load master embeddings
        master_embeddings_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_embeddings = {}
                    for master_id, embedding in results['master_embeddings'].items():
                        master_embeddings[int(master_id)] = np.array(embedding)
                    master_embeddings_by_ref[ref_percentile] = master_embeddings
        
        if len(master_embeddings_by_ref) < 2:
            return
        
        # Create flow diagram
        fig, ax = plt.subplots(figsize=(16, 10))
        
        # Colors for each master cluster
        colors = plt.cm.Set3(np.linspace(0, 1, k_value))
        
        # Calculate alignments between adjacent references
        ref_positions = {ref: i for i, ref in enumerate(self.reference_percentiles)}
        
        # Plot nodes for each reference-master combination
        node_positions = {}
        
        for ref in self.reference_percentiles:
            if ref not in master_embeddings_by_ref:
                continue
                
            x = ref_positions[ref]
            y_positions = np.linspace(0, 1, k_value)
            
            for master_id in range(k_value):
                y = y_positions[master_id]
                node_positions[(ref, master_id)] = (x, y)
                
                ax.scatter(x, y, s=300, c=[colors[master_id]], 
                          edgecolors='black', linewidth=2, zorder=3)
                
                # Add labels
                ax.annotate(f'M{master_id}', (x, y), xytext=(5, 5), 
                           textcoords='offset points', fontsize=8, 
                           fontweight='bold')
        
        # Draw connections between adjacent references
        for i in range(len(self.reference_percentiles) - 1):
            ref1 = self.reference_percentiles[i]
            ref2 = self.reference_percentiles[i + 1]
            
            if ref1 in master_embeddings_by_ref and ref2 in master_embeddings_by_ref:
                # Calculate optimal alignment
                alignment_score, mapping = self._align_master_clusters(
                    master_embeddings_by_ref[ref1],
                    master_embeddings_by_ref[ref2]
                )
                
                # Draw connections based on optimal mapping
                for master1, master2 in mapping.items():
                    if (ref1, master1) in node_positions and (ref2, master2) in node_positions:
                        x1, y1 = node_positions[(ref1, master1)]
                        x2, y2 = node_positions[(ref2, master2)]
                        
                        # Line thickness based on alignment quality
                        line_width = max(1, alignment_score * 4)
                        
                        ax.plot([x1, x2], [y1, y2], 
                               color=colors[master1], alpha=0.6, 
                               linewidth=line_width, zorder=1)
        
        # Customize plot
        ax.set_xticks(range(len(self.reference_percentiles)))
        ax.set_xticklabels([f"{p}%" for p in self.reference_percentiles])
        ax.set_xlabel('Reference Percentile')
        ax.set_ylabel('Master Cluster')
        ax.set_title(f'Master Cluster Flow Diagram - {population_type} (K={k_value})')
        
        # Add legend
        legend_elements = []
        for master_id in range(k_value):
            legend_elements.append(
                plt.scatter([], [], s=100, c=[colors[master_id]], 
                           edgecolors='black', label=f'Master {master_id}')
            )
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5))
        
        ax.grid(True, alpha=0.3, axis='x')
        ax.set_ylim(-0.1, 1.1)
        
        plt.tight_layout()
        
        save_path = self.plots_dir / f"{population_type}_k{k_value}_flow_diagram.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved flow diagram: {save_path}")
    
    def _generate_feature_consistency_radar_charts(self, population_type: str, k_value: int):
        """Generate radar charts showing feature consistency patterns."""
        
        # Load master profiles
        master_profiles_by_ref = {}
        
        for ref_percentile in self.reference_percentiles:
            results_file = self.individual_results_dir / f"{population_type}_k{k_value}_ref{ref_percentile}_results.json"
            
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                    master_profiles_by_ref[ref_percentile] = results['master_profiles']
        
        if not master_profiles_by_ref:
            return
        
        # Create radar charts for each master cluster
        fig, axes = plt.subplots(1, k_value, figsize=(6*k_value, 6), 
                               subplot_kw=dict(projection='polar'))
        if k_value == 1:
            axes = [axes]
        
        for master_id in range(k_value):
            master_key = f"master_{master_id}"
            ax = axes[master_id]
            
            # Get top features across all references
            all_features = set()
            for ref, profiles in master_profiles_by_ref.items():
                if master_key in profiles:
                    top_features = profiles[master_key]['top_features']
                    all_features.update([f for f, _ in top_features[:8]])
            
            if not all_features:
                continue
            
            # Select most consistent features
            feature_consistency = {}
            for feature in all_features:
                appearances = 0
                importances = []
                for ref in self.reference_percentiles:
                    if (ref in master_profiles_by_ref and 
                        master_key in master_profiles_by_ref[ref]):
                        top_features_dict = dict(master_profiles_by_ref[ref][master_key]['top_features'])
                        if feature in top_features_dict:
                            appearances += 1
                            importances.append(top_features_dict[feature])
                
                if appearances >= 2:
                    consistency = appearances / len(self.reference_percentiles)
                    avg_importance = np.mean(importances)
                    feature_consistency[feature] = {
                        'consistency': consistency,
                        'avg_importance': avg_importance,
                        'score': consistency * avg_importance
                    }
            
            # Select top features for radar chart
            top_features = sorted(feature_consistency.items(), 
                                key=lambda x: x[1]['score'], reverse=True)[:8]
            
            if not top_features:
                continue
            
            # Create radar chart data
            features = [f[0][:15] for f in top_features]  # Truncate names
            n_features = len(features)
            
            # Calculate angles for radar chart
            angles = np.linspace(0, 2*np.pi, n_features, endpoint=False).tolist()
            angles += angles[:1]  # Complete the circle
            
            # Plot data for each reference
            for ref in self.reference_percentiles:
                if ref not in master_profiles_by_ref or master_key not in master_profiles_by_ref[ref]:
                    continue
                    
                top_features_dict = dict(master_profiles_by_ref[ref][master_key]['top_features'])
                values = []
                
                for feature, _ in top_features:
                    importance = top_features_dict.get(feature, 0.0)
                    values.append(importance)
                
                values += values[:1]  # Complete the circle
                
                ax.plot(angles, values, 'o-', linewidth=2, 
                       label=f'Ref {ref}%', alpha=0.7)
                ax.fill(angles, values, alpha=0.1)
            
            # Customize radar chart
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(features, fontsize=8)
            ax.set_ylim(0, max([max(v[1]['avg_importance'] for v in top_features), 0.1]))
            ax.set_title(f'Master Cluster {master_id}\nFeature Consistency', 
                        fontsize=12, fontweight='bold', pad=20)
            ax.grid(True)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0), fontsize=8)
        
        plt.suptitle(f'Feature Consistency Radar Charts - {population_type} (K={k_value})', 
                    fontsize=16, fontweight='bold')
        plt.tight_layout()
        
        save_path = self.plots_dir / f"{population_type}_k{k_value}_radar_charts.png"
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"    Saved radar charts: {save_path}")
    
    def _generate_cross_population_summaries(self, population_types: List[str], k_values: List[int]):
        """Generate cross-population and cross-K summaries."""
        
        # Create comprehensive summary DataFrame
        summary_data = []
        
        for population_type in population_types:
            for k_value in k_values:
                # Load alignment analysis if available
                analysis_file = self.aligned_analysis_dir / f"{population_type}_k{k_value}_aligned_analysis.txt"
                
                if analysis_file.exists():
                    # Extract key metrics (simplified parsing)
                    try:
                        with open(analysis_file, 'r') as f:
                            content = f.read()
                            
                        # Extract alignment score
                        alignment_score = 0
                        if "Average Alignment Score:" in content:
                            line = [l for l in content.split('\n') if "Average Alignment Score:" in l][0]
                            alignment_score = float(line.split(':')[1].strip())
                        
                        # Extract consistency score
                        consistency_score = 0
                        if "Average Feature Consistency:" in content:
                            line = [l for l in content.split('\n') if "Average Feature Consistency:" in l][0]
                            consistency_score = float(line.split(':')[1].strip())
                        
                        summary_data.append({
                            'population': population_type,
                            'k_value': k_value,
                            'alignment_score': alignment_score,
                            'consistency_score': consistency_score,
                            'combined_score': (alignment_score + consistency_score) / 2
                        })
                        
                    except:
                        continue
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_path = self.data_dir / "comprehensive_summary_data.csv"
            summary_df.to_csv(summary_path, index=False, float_format='%.4f')
            
            # Create summary visualization
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            
            # 1. Alignment scores by K and population
            pivot_alignment = summary_df.pivot(index='k_value', columns='population', values='alignment_score')
            sns.heatmap(pivot_alignment, annot=True, fmt='.3f', cmap='RdYlBu_r', ax=axes[0, 0])
            axes[0, 0].set_title('Alignment Scores by K-Value and Population')
            
            # 2. Consistency scores by K and population
            pivot_consistency = summary_df.pivot(index='k_value', columns='population', values='consistency_score')
            sns.heatmap(pivot_consistency, annot=True, fmt='.3f', cmap='RdYlBu_r', ax=axes[0, 1])
            axes[0, 1].set_title('Consistency Scores by K-Value and Population')
            
            # 3. Combined scores
            pivot_combined = summary_df.pivot(index='k_value', columns='population', values='combined_score')
            sns.heatmap(pivot_combined, annot=True, fmt='.3f', cmap='RdYlBu_r', ax=axes[1, 0])
            axes[1, 0].set_title('Combined Scores by K-Value and Population')
            
            # 4. Score comparison
            for pop in population_types:
                pop_data = summary_df[summary_df['population'] == pop]
                axes[1, 1].plot(pop_data['k_value'], pop_data['combined_score'], 
                               'o-', label=pop, linewidth=2, markersize=8)
            
            axes[1, 1].set_xlabel('K-Value')
            axes[1, 1].set_ylabel('Combined Score')
            axes[1, 1].set_title('Combined Score Trends')
            axes[1, 1].legend()
            axes[1, 1].grid(True, alpha=0.3)
            
            plt.suptitle('Comprehensive Analysis Summary', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            summary_plot_path = self.plots_dir / "comprehensive_summary.png"
            plt.savefig(summary_plot_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"    Saved comprehensive summary: {summary_path}")
            print(f"    Saved summary plot: {summary_plot_path}")
    
    def _align_master_clusters(self, embeddings1: Dict[int, np.ndarray], 
                              embeddings2: Dict[int, np.ndarray]) -> Tuple[float, Dict[int, int]]:
        """Use Hungarian algorithm to optimally align two sets of master cluster embeddings."""
        k_value = len(embeddings1)
        
        similarity_matrix = np.zeros((k_value, k_value))
        
        for i in range(k_value):
            for j in range(k_value):
                sim = cosine_similarity([embeddings1[i]], [embeddings2[j]])[0][0]
                similarity_matrix[i, j] = sim
        
        cost_matrix = -similarity_matrix
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        alignment_score = np.mean([similarity_matrix[i, j] for i, j in zip(row_ind, col_ind)])
        mapping = {int(i): int(j) for i, j in zip(row_ind, col_ind)}
        
        return float(alignment_score), mapping


def main():
    """Main entry point for comprehensive aligned visualization."""
    print("Starting Comprehensive Aligned Visualization and Analysis...")
    
    analyzer = ComprehensiveAlignedAnalyzer()
    
    analyzer.generate_all_comprehensive_analysis(
        population_types=['with_breakdown', 'no_breakdown'],
        k_values=[3, 4, 5, 6, 7, 8]
    )
    
    print("\nComprehensive analysis complete!")


if __name__ == "__main__":
    main()