def create_alignment_heatmap(self, master_assignments, k_value, population_type):
    """
    Create a heatmap showing cluster similarities across percentiles
    """
    import matplotlib.pyplot as plt
    import seaborn as sns
    
    percentiles = sorted(master_assignments.keys(), key=int)
    
    # Create similarity matrix
    n_clusters_total = len(percentiles) * k_value
    labels = []
    
    # Reorder clusters by master assignment
    ordered_embeddings = []
    
    for p in percentiles:
        for master_id in range(k_value):
            # Find local cluster assigned to this master
            for local_id, master in master_assignments[p].items():
                if master == master_id:
                    key = f"p{p}_k{k_value}_c{local_id}"
                    embedding = np.array(
                        self.embeddings[population_type]['embeddings_vector'][key]
                    )
                    ordered_embeddings.append(embedding)
                    labels.append(f"P{p}-M{master_id}")
                    break
    
    similarity_matrix = cosine_similarity(ordered_embeddings)
    
    plt.figure(figsize=(12, 10))
    sns.heatmap(similarity_matrix, 
                xticklabels=labels, 
                yticklabels=labels,
                cmap='coolwarm',
                center=0.5,
                vmin=0, vmax=1)
    plt.title(f'Cluster Alignment Heatmap (K={k_value})')
    plt.tight_layout()
    
    return similarity_matrix