"""
Visualization Tools for Cluster Alignment Analysis

Creates visualizations to understand cluster alignment patterns and stability.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Optional
import json
from pathlib import Path


class ClusterAlignmentVisualizer:
    """
    Creates visualizations for cluster alignment analysis.
    """
    
    def __init__(self, embeddings_path: str = '../cluster_embeddings/complete_cluster_embeddings.json'):
        """
        Initialize the visualizer with cluster embeddings.
        
        Args:
            embeddings_path: Path to the complete cluster embeddings JSON file
        """
        self.embeddings_path = Path(embeddings_path)
        self._load_embeddings()
        
    def _load_embeddings(self):
        """Load cluster embeddings from JSON file."""
        with open(self.embeddings_path) as f:
            self.embeddings = json.load(f)
    
    def create_alignment_heatmap(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str,
        save_path: Optional[str] = None,
        figsize: tuple = (14, 12)
    ) -> np.ndarray:
        """
        Create a heatmap showing cluster similarities across percentiles,
        organized by master cluster assignment.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            k_value: Number of clusters
            population_type: 'with_breakdown' or 'no_breakdown'
            save_path: Optional path to save the figure
            figsize: Figure size
            
        Returns:
            Similarity matrix
        """
        percentiles = sorted(master_assignments.keys(), key=int)
        
        # Organize clusters by master assignment
        ordered_embeddings = []
        labels = []
        block_boundaries = []
        
        for master_id in range(k_value):
            block_start = len(ordered_embeddings)
            
            for p in percentiles:
                for local_id, master in master_assignments[p].items():
                    if master == master_id:
                        key = f"p{p}_k{k_value}_c{local_id}"
                        embedding = np.array(
                            self.embeddings[population_type]['embeddings_vector'][key]
                        )
                        ordered_embeddings.append(embedding)
                        labels.append(f"P{p}-M{master_id}")
                        break
            
            if len(ordered_embeddings) > block_start:
                block_boundaries.append(len(ordered_embeddings))
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(ordered_embeddings)
        
        # Create visualization
        fig, ax = plt.subplots(figsize=figsize)
        
        # Create heatmap
        sns.heatmap(similarity_matrix, 
                   xticklabels=labels, 
                   yticklabels=labels,
                   cmap='RdBu_r',
                   center=0.5,
                   vmin=0, vmax=1,
                   cbar_kws={'label': 'Cosine Similarity'},
                   ax=ax)
        
        # Add block boundaries
        for boundary in block_boundaries[:-1]:
            ax.axhline(y=boundary, color='black', linewidth=2)
            ax.axvline(x=boundary, color='black', linewidth=2)
        
        plt.title(f'Cluster Alignment Heatmap\n{population_type} (K={k_value})')
        plt.xlabel('Cluster (Percentile-Master)')
        plt.ylabel('Cluster (Percentile-Master)')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved alignment heatmap to {save_path}")
        
        plt.close()
        
        return similarity_matrix
    
    def plot_stability_metrics(
        self,
        stability_metrics: Dict,
        save_path: Optional[str] = None,
        figsize: tuple = (16, 10)
    ):
        """
        Create multiple plots showing different stability metrics.
        
        Args:
            stability_metrics: Dictionary of stability metrics
            save_path: Optional path to save the figure
            figsize: Figure size
        """
        fig, axes = plt.subplots(2, 3, figsize=figsize)
        
        # 1. Transition Consistency
        ax = axes[0, 0]
        transition_data = stability_metrics['transition_consistency']['transition_details']
        x_labels = [f"{d['from_percentile']}->{d['to_percentile']}" for d in transition_data]
        y_values = [d['similarity'] for d in transition_data]
        
        ax.plot(range(len(y_values)), y_values, 'o-', linewidth=2, markersize=6)
        ax.set_xlabel('Percentile Transition')
        ax.set_ylabel('Average Similarity')
        ax.set_title('Transition Consistency')
        ax.set_xticks(range(0, len(x_labels), max(1, len(x_labels)//10)))
        ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), max(1, len(x_labels)//10))], 
                           rotation=45, ha='right')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=np.mean(y_values), color='r', linestyle='--', alpha=0.5, label=f'Mean: {np.mean(y_values):.3f}')
        ax.legend()
        
        # 2. Master Coherence
        ax = axes[0, 1]
        coherence_data = stability_metrics['master_coherence']['per_master_coherence']
        masters = list(coherence_data.keys())
        coherence_scores = [coherence_data[m]['coherence_score'] for m in masters]
        
        bars = ax.bar(range(len(masters)), coherence_scores)
        ax.set_xlabel('Master Cluster')
        ax.set_ylabel('Coherence Score')
        ax.set_title('Master Cluster Coherence')
        ax.set_xticks(range(len(masters)))
        ax.set_xticklabels([m.replace('master_', 'M') for m in masters])
        ax.axhline(y=np.mean(coherence_scores), color='r', linestyle='--', alpha=0.5, 
                  label=f'Mean: {np.mean(coherence_scores):.3f}')
        ax.legend()
        
        # Color bars based on coherence
        for i, bar in enumerate(bars):
            if coherence_scores[i] >= 0.8:
                bar.set_color('green')
            elif coherence_scores[i] >= 0.6:
                bar.set_color('orange')
            else:
                bar.set_color('red')
        
        # 3. Percentile Stability
        ax = axes[0, 2]
        stability_data = stability_metrics['percentile_stability']['per_percentile_stability']
        percentiles = sorted(stability_data.keys(), key=int)
        stability_scores = [stability_data[p]['stability_score'] for p in percentiles]
        
        ax.plot(percentiles, stability_scores, 'o-', linewidth=2, markersize=6)
        ax.set_xlabel('Percentile')
        ax.set_ylabel('Stability Score')
        ax.set_title('Percentile Stability')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=np.mean(stability_scores), color='r', linestyle='--', alpha=0.5,
                  label=f'Mean: {np.mean(stability_scores):.3f}')
        ax.legend()
        
        # 4. Cluster Purity
        ax = axes[1, 0]
        purity_data = stability_metrics['cluster_purity']['per_master_purity']
        masters = list(purity_data.keys())
        purity_scores = [purity_data[m]['purity_score'] for m in masters]
        dispersions = [purity_data[m]['dispersion'] for m in masters]
        
        x = range(len(masters))
        ax.bar(x, purity_scores, alpha=0.7, label='Purity')
        ax.bar(x, dispersions, alpha=0.7, bottom=purity_scores, label='Dispersion')
        ax.set_xlabel('Master Cluster')
        ax.set_ylabel('Score')
        ax.set_title('Cluster Purity and Dispersion')
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace('master_', 'M') for m in masters])
        ax.legend()
        
        # 5. Feature Consistency
        ax = axes[1, 1]
        if 'feature_consistency' in stability_metrics:
            consistency_data = stability_metrics['feature_consistency']['per_master_consistency']
            masters = list(consistency_data.keys())
            cv_scores = [consistency_data[m]['avg_cv'] for m in masters]
            
            bars = ax.bar(range(len(masters)), cv_scores)
            ax.set_xlabel('Master Cluster')
            ax.set_ylabel('Average CV')
            ax.set_title('Feature Consistency (lower is better)')
            ax.set_xticks(range(len(masters)))
            ax.set_xticklabels([m.replace('master_', 'M') for m in masters])
            
            # Color bars based on CV (lower is better)
            for i, bar in enumerate(bars):
                if cv_scores[i] <= 0.2:
                    bar.set_color('green')
                elif cv_scores[i] <= 0.4:
                    bar.set_color('orange')
                else:
                    bar.set_color('red')
        
        # 6. Overall Summary
        ax = axes[1, 2]
        summary_metrics = {
            'Overall Stability': stability_metrics.get('overall_stability', 0),
            'Avg Transition': stability_metrics['transition_consistency']['avg_transition_consistency'],
            'Avg Coherence': stability_metrics['master_coherence']['average_coherence'],
            'Avg Percentile Stability': stability_metrics['percentile_stability']['average_stability'],
            'Avg Purity': stability_metrics['cluster_purity']['average_purity']
        }
        
        y_pos = range(len(summary_metrics))
        values = list(summary_metrics.values())
        colors = ['green' if v >= 0.7 else 'orange' if v >= 0.5 else 'red' for v in values]
        
        bars = ax.barh(y_pos, values, color=colors)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(list(summary_metrics.keys()))
        ax.set_xlabel('Score')
        ax.set_title('Summary Metrics')
        ax.set_xlim(0, 1)
        
        # Add value labels
        for i, (bar, value) in enumerate(zip(bars, values)):
            ax.text(value + 0.01, bar.get_y() + bar.get_height()/2, 
                   f'{value:.3f}', va='center')
        
        plt.suptitle('Cluster Alignment Stability Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved stability metrics plot to {save_path}")
        
        plt.close()
    
    def plot_master_cluster_evolution(
        self,
        master_assignments: Dict,
        master_profiles: Dict,
        k_value: int,
        save_path: Optional[str] = None,
        figsize: tuple = (16, 8)
    ):
        """
        Visualize how master clusters evolve across percentiles.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            master_profiles: Master cluster profiles
            k_value: Number of clusters
            save_path: Optional path to save the figure
            figsize: Figure size
        """
        fig, axes = plt.subplots(1, 2, figsize=figsize)
        
        # 1. Master cluster membership across percentiles
        ax = axes[0]
        percentiles = sorted(master_assignments.keys(), key=int)
        
        # Create matrix showing master assignments
        assignment_matrix = np.zeros((k_value, len(percentiles)))
        
        for j, p in enumerate(percentiles):
            for local_id, master_id in master_assignments[p].items():
                assignment_matrix[master_id, j] = 1
        
        im = ax.imshow(assignment_matrix, aspect='auto', cmap='Blues')
        ax.set_xlabel('Percentile')
        ax.set_ylabel('Master Cluster')
        ax.set_title('Master Cluster Presence Across Percentiles')
        ax.set_xticks(range(len(percentiles)))
        ax.set_xticklabels(percentiles, rotation=45)
        ax.set_yticks(range(k_value))
        ax.set_yticklabels([f'Master {i}' for i in range(k_value)])
        
        # Add colorbar
        plt.colorbar(im, ax=ax, label='Present')
        
        # 2. Top features for each master cluster
        ax = axes[1]
        
        # Prepare data for grouped bar chart
        n_features = 5
        master_ids = [f"master_{i}" for i in range(k_value)]
        feature_importance_data = []
        feature_names = set()
        
        for master_id in master_ids:
            if master_id in master_profiles:
                top_features = master_profiles[master_id]['top_features'][:n_features]
                for feat, importance in top_features:
                    feature_names.add(feat)
                    feature_importance_data.append({
                        'master': master_id,
                        'feature': feat,
                        'importance': importance
                    })
        
        # Create grouped bar chart
        feature_names = sorted(list(feature_names))
        x = np.arange(len(master_ids))
        width = 0.8 / len(feature_names) if feature_names else 0.8
        
        for i, feature in enumerate(feature_names[:10]):  # Limit to top 10 features
            values = []
            for master_id in master_ids:
                if master_id in master_profiles:
                    # Find importance for this feature in this master
                    importance = 0
                    for feat, imp in master_profiles[master_id]['top_features']:
                        if feat == feature:
                            importance = imp
                            break
                    values.append(importance)
                else:
                    values.append(0)
            
            offset = (i - len(feature_names)/2) * width
            ax.bar(x + offset, values, width, label=feature[:20])  # Truncate long names
        
        ax.set_xlabel('Master Cluster')
        ax.set_ylabel('Feature Importance')
        ax.set_title('Top Features by Master Cluster')
        ax.set_xticks(x)
        ax.set_xticklabels([m.replace('master_', 'M') for m in master_ids])
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        
        plt.suptitle('Master Cluster Evolution Analysis', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved evolution plot to {save_path}")
        
        plt.close()
    
    def create_cross_percentile_flow(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str,
        save_path: Optional[str] = None,
        figsize: tuple = (14, 10)
    ):
        """
        Create a flow diagram showing how clusters transition between
        master assignments across percentiles.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            k_value: Number of clusters
            population_type: 'with_breakdown' or 'no_breakdown'
            save_path: Optional path to save the figure
            figsize: Figure size
        """
        percentiles = sorted(master_assignments.keys(), key=int)
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Colors for each master cluster
        colors = plt.cm.Set3(np.linspace(0, 1, k_value))
        
        # Plot each percentile as a column
        for i, p in enumerate(percentiles):
            y_positions = np.linspace(0, 1, k_value)
            
            for local_id in range(k_value):
                master_id = master_assignments[p][local_id]
                
                # Draw node
                ax.scatter(i, y_positions[local_id], 
                          s=200, c=[colors[master_id]], 
                          edgecolors='black', linewidth=1.5, zorder=3)
                
                # Add connection to next percentile
                if i < len(percentiles) - 1:
                    next_p = percentiles[i + 1]
                    # Find which cluster in next percentile has same master
                    for next_local_id, next_master_id in master_assignments[next_p].items():
                        if next_master_id == master_id:
                            ax.plot([i, i+1], 
                                   [y_positions[local_id], y_positions[next_local_id]], 
                                   color=colors[master_id], alpha=0.5, linewidth=2, zorder=1)
                            break
        
        # Customize plot
        ax.set_xticks(range(len(percentiles)))
        ax.set_xticklabels(percentiles, rotation=45)
        ax.set_xlabel('Percentile')
        ax.set_ylabel('Cluster Position')
        ax.set_title(f'Cluster Flow Across Percentiles\n{population_type} (K={k_value})')
        
        # Add legend
        legend_elements = []
        for master_id in range(k_value):
            legend_elements.append(
                plt.scatter([], [], s=100, c=[colors[master_id]], 
                           edgecolors='black', label=f'Master {master_id}')
            )
        ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5))
        
        ax.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Saved flow diagram to {save_path}")
        
        plt.close()