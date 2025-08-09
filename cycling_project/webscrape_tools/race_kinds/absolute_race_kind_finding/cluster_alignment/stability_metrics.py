"""
Cluster Stability Metrics

Calculates various metrics to assess cluster stability and consistency 
across percentiles after alignment.
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Tuple
import json
from pathlib import Path


class ClusterStabilityAnalyzer:
    """
    Analyzes the stability of cluster assignments across percentiles.
    """
    
    def __init__(self, embeddings_path: str = '../cluster_embeddings/complete_cluster_embeddings.json'):
        """
        Initialize the analyzer with cluster embeddings.
        
        Args:
            embeddings_path: Path to the complete cluster embeddings JSON file
        """
        self.embeddings_path = Path(embeddings_path)
        self._load_embeddings()
        
    def _load_embeddings(self):
        """Load cluster embeddings from JSON file."""
        with open(self.embeddings_path) as f:
            self.embeddings = json.load(f)
            
    def calculate_all_stability_metrics(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Calculate comprehensive stability metrics for aligned clusters.
        
        Args:
            master_assignments: Dictionary of cluster assignments
            k_value: Number of clusters
            population_type: 'with_breakdown' or 'no_breakdown'
            
        Returns:
            Dictionary containing all stability metrics
        """
        metrics = {
            'transition_consistency': self.calculate_transition_consistency(
                master_assignments, k_value, population_type
            ),
            'master_coherence': self.calculate_master_coherence(
                master_assignments, k_value, population_type
            ),
            'percentile_stability': self.calculate_percentile_stability(
                master_assignments, k_value, population_type
            ),
            'feature_consistency': self.calculate_feature_consistency(
                master_assignments, k_value, population_type
            ),
            'cluster_purity': self.calculate_cluster_purity(
                master_assignments, k_value, population_type
            )
        }
        
        # Calculate overall stability score
        metrics['overall_stability'] = self._calculate_overall_stability(metrics)
        
        return metrics
    
    def calculate_transition_consistency(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Measure how consistently clusters maintain their master assignment
        across adjacent percentiles.
        """
        percentiles = sorted(master_assignments.keys(), key=int)
        n_percentiles = len(percentiles)
        
        # Track transitions between adjacent percentiles
        transition_matrix = np.zeros((n_percentiles - 1, k_value))
        transition_details = []
        
        for i in range(n_percentiles - 1):
            p1, p2 = percentiles[i], percentiles[i + 1]
            
            for master_id in range(k_value):
                # Find clusters assigned to this master in both percentiles
                local1 = None
                local2 = None
                
                for local_id, master in master_assignments[p1].items():
                    if master == master_id:
                        local1 = local_id
                        break
                        
                for local_id, master in master_assignments[p2].items():
                    if master == master_id:
                        local2 = local_id
                        break
                
                if local1 is not None and local2 is not None:
                    # Calculate similarity between aligned clusters
                    key1 = f"p{p1}_k{k_value}_c{local1}"
                    key2 = f"p{p2}_k{k_value}_c{local2}"
                    
                    vec1 = np.array(self.embeddings[population_type]['embeddings_vector'][key1])
                    vec2 = np.array(self.embeddings[population_type]['embeddings_vector'][key2])
                    
                    similarity = cosine_similarity([vec1], [vec2])[0][0]
                    transition_matrix[i, master_id] = similarity
                else:
                    transition_matrix[i, master_id] = 0.0
            
            # Calculate transition score for this pair
            transition_score = np.mean(transition_matrix[i])
            transition_details.append({
                'from_percentile': p1,
                'to_percentile': p2,
                'similarity': transition_score,
                'per_cluster': transition_matrix[i].tolist()
            })
        
        return {
            'transition_matrix': transition_matrix.tolist(),
            'transition_details': transition_details,
            'avg_transition_consistency': np.mean(transition_matrix),
            'min_transition_consistency': np.min(transition_matrix),
            'max_transition_consistency': np.max(transition_matrix),
            'std_transition_consistency': np.std(transition_matrix)
        }
    
    def calculate_master_coherence(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Calculate the internal coherence of each master cluster.
        """
        master_coherence = {}
        
        for master_id in range(k_value):
            cluster_embeddings = []
            cluster_members = []
            
            # Collect all embeddings assigned to this master
            for percentile, assignments in master_assignments.items():
                for local_id, master in assignments.items():
                    if master == master_id:
                        key = f"p{percentile}_k{k_value}_c{local_id}"
                        embedding = np.array(
                            self.embeddings[population_type]['embeddings_vector'][key]
                        )
                        cluster_embeddings.append(embedding)
                        cluster_members.append((percentile, local_id))
            
            if len(cluster_embeddings) > 1:
                # Calculate pairwise similarities
                similarity_matrix = cosine_similarity(cluster_embeddings)
                
                # Exclude diagonal (self-similarity)
                mask = ~np.eye(similarity_matrix.shape[0], dtype=bool)
                pairwise_similarities = similarity_matrix[mask]
                
                coherence_score = np.mean(pairwise_similarities)
                coherence_std = np.std(pairwise_similarities)
                min_similarity = np.min(pairwise_similarities)
                max_similarity = np.max(pairwise_similarities)
            else:
                coherence_score = 1.0
                coherence_std = 0.0
                min_similarity = 1.0
                max_similarity = 1.0
            
            master_coherence[f"master_{master_id}"] = {
                'coherence_score': float(coherence_score),
                'coherence_std': float(coherence_std),
                'min_similarity': float(min_similarity),
                'max_similarity': float(max_similarity),
                'n_members': len(cluster_embeddings),
                'members': cluster_members
            }
        
        # Calculate overall coherence
        avg_coherence = np.mean([m['coherence_score'] for m in master_coherence.values()])
        
        return {
            'per_master_coherence': master_coherence,
            'average_coherence': float(avg_coherence),
            'min_coherence': float(min([m['coherence_score'] for m in master_coherence.values()])),
            'max_coherence': float(max([m['coherence_score'] for m in master_coherence.values()]))
        }
    
    def calculate_percentile_stability(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Calculate stability scores for each percentile.
        """
        percentiles = sorted(master_assignments.keys(), key=int)
        percentile_stability = {}
        
        for i, percentile in enumerate(percentiles):
            similarities = []
            
            # Compare to previous percentile
            if i > 0:
                prev_p = percentiles[i-1]
                for master_id in range(k_value):
                    # Find corresponding clusters
                    local_current = None
                    local_prev = None
                    
                    for local_id, master in master_assignments[percentile].items():
                        if master == master_id:
                            local_current = local_id
                            break
                    
                    for local_id, master in master_assignments[prev_p].items():
                        if master == master_id:
                            local_prev = local_id
                            break
                    
                    if local_current is not None and local_prev is not None:
                        key1 = f"p{percentile}_k{k_value}_c{local_current}"
                        key2 = f"p{prev_p}_k{k_value}_c{local_prev}"
                        
                        vec1 = np.array(self.embeddings[population_type]['embeddings_vector'][key1])
                        vec2 = np.array(self.embeddings[population_type]['embeddings_vector'][key2])
                        
                        similarities.append(cosine_similarity([vec1], [vec2])[0][0])
            
            # Compare to next percentile
            if i < len(percentiles) - 1:
                next_p = percentiles[i+1]
                for master_id in range(k_value):
                    # Find corresponding clusters
                    local_current = None
                    local_next = None
                    
                    for local_id, master in master_assignments[percentile].items():
                        if master == master_id:
                            local_current = local_id
                            break
                    
                    for local_id, master in master_assignments[next_p].items():
                        if master == master_id:
                            local_next = local_id
                            break
                    
                    if local_current is not None and local_next is not None:
                        key1 = f"p{percentile}_k{k_value}_c{local_current}"
                        key2 = f"p{next_p}_k{k_value}_c{local_next}"
                        
                        vec1 = np.array(self.embeddings[population_type]['embeddings_vector'][key1])
                        vec2 = np.array(self.embeddings[population_type]['embeddings_vector'][key2])
                        
                        similarities.append(cosine_similarity([vec1], [vec2])[0][0])
            
            stability_score = np.mean(similarities) if similarities else 1.0
            percentile_stability[percentile] = {
                'stability_score': float(stability_score),
                'n_comparisons': len(similarities)
            }
        
        return {
            'per_percentile_stability': percentile_stability,
            'average_stability': float(np.mean([s['stability_score'] for s in percentile_stability.values()])),
            'most_stable_percentile': max(percentile_stability.items(), key=lambda x: x[1]['stability_score'])[0],
            'least_stable_percentile': min(percentile_stability.items(), key=lambda x: x[1]['stability_score'])[0]
        }
    
    def calculate_feature_consistency(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Analyze how consistently features are important across master clusters.
        """
        feature_space = self.embeddings[population_type]['feature_space']
        master_feature_importance = {i: [] for i in range(k_value)}
        
        # Collect feature importances for each master cluster
        for percentile, assignments in master_assignments.items():
            for local_id, master_id in assignments.items():
                key = f"p{percentile}_k{k_value}_c{local_id}"
                embedding_dict = self.embeddings[population_type]['embeddings_dict'][key]
                master_feature_importance[master_id].append(embedding_dict)
        
        # Calculate feature consistency for each master cluster
        feature_consistency = {}
        
        for master_id in range(k_value):
            if not master_feature_importance[master_id]:
                continue
                
            feature_stds = {}
            feature_means = {}
            
            for feature in feature_space:
                importances = [emb.get(feature, 0) for emb in master_feature_importance[master_id]]
                feature_means[feature] = np.mean(importances)
                feature_stds[feature] = np.std(importances)
            
            # Calculate coefficient of variation for each feature
            feature_cvs = {}
            for feature in feature_space:
                if feature_means[feature] > 0:
                    feature_cvs[feature] = feature_stds[feature] / feature_means[feature]
                else:
                    feature_cvs[feature] = 0
            
            # Get most and least consistent features
            sorted_features = sorted(feature_cvs.items(), key=lambda x: x[1])
            
            feature_consistency[f"master_{master_id}"] = {
                'avg_cv': float(np.mean(list(feature_cvs.values()))),
                'most_consistent_features': sorted_features[:5],
                'least_consistent_features': sorted_features[-5:],
                'feature_cvs': feature_cvs
            }
        
        return {
            'per_master_consistency': feature_consistency,
            'overall_feature_consistency': float(
                np.mean([m['avg_cv'] for m in feature_consistency.values()])
            )
        }
    
    def calculate_cluster_purity(
        self,
        master_assignments: Dict,
        k_value: int,
        population_type: str
    ) -> Dict:
        """
        Calculate how "pure" each master cluster is in terms of 
        containing similar clusters.
        """
        purity_scores = {}
        
        for master_id in range(k_value):
            # Get all clusters assigned to this master
            master_clusters = []
            
            for percentile, assignments in master_assignments.items():
                for local_id, master in assignments.items():
                    if master == master_id:
                        key = f"p{percentile}_k{k_value}_c{local_id}"
                        embedding = np.array(
                            self.embeddings[population_type]['embeddings_vector'][key]
                        )
                        master_clusters.append({
                            'percentile': percentile,
                            'local_id': local_id,
                            'embedding': embedding
                        })
            
            if len(master_clusters) > 1:
                # Calculate average distance from centroid
                embeddings = np.array([c['embedding'] for c in master_clusters])
                centroid = np.mean(embeddings, axis=0)
                
                distances = []
                for emb in embeddings:
                    # Use cosine distance (1 - cosine_similarity)
                    similarity = cosine_similarity([emb], [centroid])[0][0]
                    distance = 1 - similarity
                    distances.append(distance)
                
                purity_score = 1 - np.mean(distances)  # Higher score = more pure
                dispersion = np.std(distances)
            else:
                purity_score = 1.0
                dispersion = 0.0
            
            purity_scores[f"master_{master_id}"] = {
                'purity_score': float(purity_score),
                'dispersion': float(dispersion),
                'n_members': len(master_clusters)
            }
        
        return {
            'per_master_purity': purity_scores,
            'average_purity': float(np.mean([p['purity_score'] for p in purity_scores.values()])),
            'min_purity': float(min([p['purity_score'] for p in purity_scores.values()])),
            'max_purity': float(max([p['purity_score'] for p in purity_scores.values()]))
        }
    
    def _calculate_overall_stability(self, metrics: Dict) -> float:
        """
        Calculate an overall stability score from all metrics.
        """
        scores = [
            metrics['transition_consistency']['avg_transition_consistency'],
            metrics['master_coherence']['average_coherence'],
            metrics['percentile_stability']['average_stability'],
            1 - metrics['feature_consistency']['overall_feature_consistency'],  # Lower CV is better
            metrics['cluster_purity']['average_purity']
        ]
        
        return float(np.mean(scores))