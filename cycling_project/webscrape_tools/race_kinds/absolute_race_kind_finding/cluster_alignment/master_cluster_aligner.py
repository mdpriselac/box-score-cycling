"""
Master Cluster Alignment System

This module implements the core alignment algorithm to correlate clusters across
different percentiles, creating master clusters that represent consistent race kinds.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics.pairwise import cosine_similarity
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class MasterClusterAligner:
    """
    Aligns clusters across percentiles to create master cluster assignments.
    Uses Hungarian algorithm for optimal cluster matching.
    """
    
    def __init__(self, embeddings_path: str = '../cluster_embeddings/complete_cluster_embeddings.json'):
        """
        Initialize the aligner with cluster embeddings.
        
        Args:
            embeddings_path: Path to the complete cluster embeddings JSON file
        """
        self.embeddings_path = Path(embeddings_path)
        self._load_embeddings()
        
    def _load_embeddings(self):
        """Load cluster embeddings from JSON file."""
        with open(self.embeddings_path) as f:
            self.embeddings = json.load(f)
        print(f"Loaded embeddings from {self.embeddings_path}")
        
    def align_clusters_across_percentiles(
        self, 
        population_type: str, 
        k_value: int,
        reference_percentile: str = '50',
        update_master_embeddings: bool = True,
        update_weight: float = 0.1
    ) -> Tuple[Dict, Dict, Dict]:
        """
        Align all clusters for a given K across all percentiles to master clusters.
        
        Args:
            population_type: 'with_breakdown' or 'no_breakdown'
            k_value: Number of clusters (3-8)
            reference_percentile: Reference percentile for initial master clusters
            update_master_embeddings: Whether to update master embeddings iteratively
            update_weight: Weight for updating master embeddings (0-1)
            
        Returns:
            Tuple of (master_assignments, alignment_scores, master_embeddings)
        """
        percentiles = ['10', '15', '20', '25', '30', '35', '40', '45', '50', 
                      '55', '60', '65', '70', '75', '80', '85', '90']
        
        print(f"\nAligning {population_type} clusters for K={k_value}")
        print(f"Reference percentile: {reference_percentile}")
        
        # Initialize master clusters from reference percentile
        master_assignments = {}
        master_embeddings = {}
        
        for cluster_id in range(k_value):
            key = f"p{reference_percentile}_k{k_value}_c{cluster_id}"
            master_embeddings[cluster_id] = np.array(
                self.embeddings[population_type]['embeddings_vector'][key]
            )
            
        master_assignments[reference_percentile] = {
            cluster_id: cluster_id for cluster_id in range(k_value)
        }
        
        # Track alignment quality
        alignment_scores = {reference_percentile: 1.0}
        alignment_details = {}
        
        # Align other percentiles
        for percentile in percentiles:
            if percentile == reference_percentile:
                continue
                
            # Create cost matrix for Hungarian algorithm
            cost_matrix = np.zeros((k_value, k_value))
            similarity_matrix = np.zeros((k_value, k_value))
            
            for local_cluster in range(k_value):
                local_key = f"p{percentile}_k{k_value}_c{local_cluster}"
                local_embedding = np.array(
                    self.embeddings[population_type]['embeddings_vector'][local_key]
                )
                
                for master_cluster in range(k_value):
                    # Calculate cosine similarity
                    similarity = cosine_similarity(
                        [local_embedding], 
                        [master_embeddings[master_cluster]]
                    )[0][0]
                    similarity_matrix[local_cluster, master_cluster] = similarity
                    # Use negative similarity as cost (Hungarian minimizes)
                    cost_matrix[local_cluster, master_cluster] = -similarity
            
            # Solve optimal assignment problem
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            # Store assignments and calculate alignment quality
            master_assignments[percentile] = {}
            total_similarity = 0
            cluster_similarities = []
            
            for local_idx, master_idx in zip(row_ind, col_ind):
                master_assignments[percentile][local_idx] = master_idx
                similarity = similarity_matrix[local_idx, master_idx]
                total_similarity += similarity
                cluster_similarities.append(similarity)
            
            # Calculate alignment score
            alignment_scores[percentile] = total_similarity / k_value
            alignment_details[percentile] = {
                'cluster_similarities': cluster_similarities,
                'min_similarity': min(cluster_similarities),
                'max_similarity': max(cluster_similarities),
                'std_similarity': np.std(cluster_similarities)
            }
            
            # Update master embeddings if requested
            if update_master_embeddings:
                for local_idx, master_idx in zip(row_ind, col_ind):
                    local_key = f"p{percentile}_k{k_value}_c{local_idx}"
                    local_embedding = np.array(
                        self.embeddings[population_type]['embeddings_vector'][local_key]
                    )
                    # Weighted update based on alignment quality
                    weight = update_weight * alignment_scores[percentile]
                    master_embeddings[master_idx] = (
                        (1 - weight) * master_embeddings[master_idx] + 
                        weight * local_embedding
                    )
        
        # Print alignment summary
        print(f"\nAlignment complete for K={k_value}")
        print(f"Average alignment score: {np.mean(list(alignment_scores.values())):.3f}")
        print(f"Min alignment score: {min(alignment_scores.values()):.3f}")
        print(f"Max alignment score: {max(alignment_scores.values()):.3f}")
        
        return master_assignments, alignment_scores, master_embeddings
    
    def get_master_cluster_profiles(
        self,
        master_assignments: Dict,
        population_type: str,
        k_value: int
    ) -> Dict:
        """
        Create profiles for each master cluster based on aligned clusters.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            population_type: 'with_breakdown' or 'no_breakdown'
            k_value: Number of clusters
            
        Returns:
            Dictionary of master cluster profiles
        """
        profiles = {}
        feature_space = self.embeddings[population_type]['feature_space']
        
        for master_id in range(k_value):
            # Collect all embeddings assigned to this master cluster
            cluster_embeddings = []
            percentile_members = []
            
            for percentile, assignments in master_assignments.items():
                for local_id, master in assignments.items():
                    if master == master_id:
                        key = f"p{percentile}_k{k_value}_c{local_id}"
                        embedding_dict = self.embeddings[population_type]['embeddings_dict'][key]
                        cluster_embeddings.append(embedding_dict)
                        percentile_members.append(percentile)
            
            # Calculate average feature importances
            avg_importance = {}
            for feature in feature_space:
                importances = [emb.get(feature, 0) for emb in cluster_embeddings]
                avg_importance[feature] = np.mean(importances)
            
            # Get top features
            sorted_features = sorted(
                avg_importance.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            top_features = sorted_features[:10]
            
            profiles[f"master_{master_id}"] = {
                'n_members': len(cluster_embeddings),
                'percentiles_present': sorted(set(percentile_members), key=int),
                'avg_feature_importance': avg_importance,
                'top_features': top_features,
                'feature_diversity': np.std(list(avg_importance.values()))
            }
        
        return profiles
    
    def calculate_cluster_migration(
        self,
        master_assignments: Dict,
        k_value: int
    ) -> Dict:
        """
        Track how clusters migrate between master assignments across percentiles.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            k_value: Number of clusters
            
        Returns:
            Migration patterns dictionary
        """
        percentiles = sorted(master_assignments.keys(), key=int)
        migrations = []
        
        for i in range(len(percentiles) - 1):
            p1, p2 = percentiles[i], percentiles[i + 1]
            
            # Track transitions
            transitions = {}
            for local_id in range(k_value):
                master1 = master_assignments[p1][local_id]
                master2 = master_assignments[p2][local_id]
                
                if master1 != master2:
                    transitions[local_id] = {
                        'from_master': master1,
                        'to_master': master2,
                        'percentile_transition': f"{p1}->{p2}"
                    }
            
            if transitions:
                migrations.append({
                    'from_percentile': p1,
                    'to_percentile': p2,
                    'transitions': transitions,
                    'n_transitions': len(transitions)
                })
        
        return {
            'migrations': migrations,
            'total_migrations': sum(m['n_transitions'] for m in migrations),
            'migration_rate': sum(m['n_transitions'] for m in migrations) / (len(percentiles) - 1) / k_value
        }