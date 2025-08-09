import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics.pairwise import cosine_similarity
import json

class CrossPercentileClusterAligner:
    def __init__(self, embeddings_path):
        with open(embeddings_path) as f:
            self.embeddings = json.load(f)
        
    def align_clusters_across_percentiles(self, population_type, k_value):
        """
        Align all clusters for a given K across all percentiles to master clusters
        """
        percentiles = ['10', '15', '20', '25', '30', '35', '40', '45', '50', 
                      '55', '60', '65', '70', '75', '80', '85', '90', '95', '100']
        
        # Step 1: Choose reference percentile (median percentile as stable reference)
        reference_percentile = '50'  # or use the one with best cluster quality
        
        # Step 2: Initialize master clusters from reference
        master_assignments = {}
        master_embeddings = {}
        
        for cluster_id in range(k_value):
            key = f"p{reference_percentile}_k{k_value}_c{cluster_id}"
            master_embeddings[cluster_id] = np.array(
                self.embeddings[population_type]['embeddings_vector'][key]
            )
            master_assignments[reference_percentile] = {cluster_id: cluster_id}
        
        # Step 3: Sequentially align other percentiles
        alignment_scores = {}
        
        for percentile in percentiles:
            if percentile == reference_percentile:
                alignment_scores[percentile] = 1.0
                continue
                
            # Create cost matrix for Hungarian algorithm
            cost_matrix = np.zeros((k_value, k_value))
            
            for local_cluster in range(k_value):
                local_key = f"p{percentile}_k{k_value}_c{local_cluster}"
                local_embedding = np.array(
                    self.embeddings[population_type]['embeddings_vector'][local_key]
                )
                
                for master_cluster in range(k_value):
                    # Use negative similarity as cost (we want to maximize similarity)
                    similarity = cosine_similarity(
                        [local_embedding], 
                        [master_embeddings[master_cluster]]
                    )[0][0]
                    cost_matrix[local_cluster, master_cluster] = -similarity
            
            # Solve assignment problem
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            # Store assignments and calculate alignment score
            master_assignments[percentile] = {}
            total_similarity = 0
            
            for local_idx, master_idx in zip(row_ind, col_ind):
                master_assignments[percentile][local_idx] = master_idx
                total_similarity += -cost_matrix[local_idx, master_idx]
            
            alignment_scores[percentile] = total_similarity / k_value
            
            # Optionally update master embeddings (running average)
            # This makes the master clusters more representative
            for local_idx, master_idx in zip(row_ind, col_ind):
                local_key = f"p{percentile}_k{k_value}_c{local_idx}"
                local_embedding = np.array(
                    self.embeddings[population_type]['embeddings_vector'][local_key]
                )
                # Weighted update based on alignment quality
                weight = 0.1 * alignment_scores[percentile]
                master_embeddings[master_idx] = (
                    (1 - weight) * master_embeddings[master_idx] + 
                    weight * local_embedding
                )
        
        return master_assignments, alignment_scores, master_embeddings