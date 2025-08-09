def calculate_cluster_stability_metrics(self, master_assignments, k_value, population_type):
    """
    Calculate various metrics to assess cluster stability across percentiles
    """
    percentiles = list(master_assignments.keys())
    n_percentiles = len(percentiles)
    
    # 1. Transition consistency: How often do clusters maintain their master assignment
    transition_matrix = np.zeros((n_percentiles - 1, k_value))
    
    for i in range(n_percentiles - 1):
        p1, p2 = percentiles[i], percentiles[i + 1]
        for local_cluster in range(k_value):
            master1 = master_assignments[p1][local_cluster]
            # Find which cluster in p2 maps to the same master
            for local2, master2 in master_assignments[p2].items():
                if master2 == master1:
                    # Calculate similarity between these aligned clusters
                    key1 = f"p{p1}_k{k_value}_c{local_cluster}"
                    key2 = f"p{p2}_k{k_value}_c{local2}"
                    
                    vec1 = np.array(self.embeddings[population_type]['embeddings_vector'][key1])
                    vec2 = np.array(self.embeddings[population_type]['embeddings_vector'][key2])
                    
                    similarity = cosine_similarity([vec1], [vec2])[0][0]
                    transition_matrix[i, master1] = similarity
                    break
    
    # 2. Master cluster coherence: Average similarity within each master cluster
    master_coherence = {}
    
    for master_id in range(k_value):
        cluster_embeddings = []
        
        for percentile in percentiles:
            for local_id, master in master_assignments[percentile].items():
                if master == master_id:
                    key = f"p{percentile}_k{k_value}_c{local_id}"
                    embedding = np.array(
                        self.embeddings[population_type]['embeddings_vector'][key]
                    )
                    cluster_embeddings.append(embedding)
        
        if len(cluster_embeddings) > 1:
            # Calculate average pairwise similarity
            similarity_matrix = cosine_similarity(cluster_embeddings)
            # Exclude diagonal
            mask = ~np.eye(similarity_matrix.shape[0], dtype=bool)
            master_coherence[master_id] = similarity_matrix[mask].mean()
        else:
            master_coherence[master_id] = 1.0
    
    # 3. Percentile stability score
    percentile_stability = {}
    
    for i, percentile in enumerate(percentiles[1:], 1):
        # Compare to adjacent percentiles
        similarities = []
        
        # Previous percentile
        if i > 0:
            prev_p = percentiles[i-1]
            for local_id in range(k_value):
                master = master_assignments[percentile][local_id]
                # Find corresponding cluster in previous percentile
                for prev_local, prev_master in master_assignments[prev_p].items():
                    if prev_master == master:
                        key1 = f"p{percentile}_k{k_value}_c{local_id}"
                        key2 = f"p{prev_p}_k{k_value}_c{prev_local}"
                        
                        vec1 = np.array(self.embeddings[population_type]['embeddings_vector'][key1])
                        vec2 = np.array(self.embeddings[population_type]['embeddings_vector'][key2])
                        
                        similarities.append(cosine_similarity([vec1], [vec2])[0][0])
        
        percentile_stability[percentile] = np.mean(similarities) if similarities else 0
    
    return {
        'transition_consistency': transition_matrix,
        'master_coherence': master_coherence,
        'percentile_stability': percentile_stability,
        'average_stability': np.mean(list(percentile_stability.values()))
    }