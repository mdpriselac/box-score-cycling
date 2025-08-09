"""
Check if cluster embeddings are actually different from each other
"""

import json
import numpy as np
from pathlib import Path


def check_embeddings():
    """Check if embeddings are actually different or all the same."""
    
    # Load embeddings
    with open('../cluster_embeddings/complete_cluster_embeddings.json') as f:
        embeddings = json.load(f)
    
    for population_type in ['with_breakdown', 'no_breakdown']:
        print(f"\n{'='*60}")
        print(f"CHECKING EMBEDDINGS: {population_type}")
        print(f"{'='*60}")
        
        # Check K=3 embeddings for percentile 50
        k_value = 3
        percentile = '50'
        
        print(f"\nChecking K={k_value}, Percentile={percentile}")
        
        # Get all three cluster embeddings
        cluster_embeddings = []
        for cluster_id in range(k_value):
            key = f"p{percentile}_k{k_value}_c{cluster_id}"
            embedding = embeddings[population_type]['embeddings_vector'][key]
            cluster_embeddings.append(np.array(embedding))
            
            # Check if embedding is all zeros or has variance
            embedding_array = np.array(embedding)
            non_zero_count = np.count_nonzero(embedding_array)
            print(f"\n  Cluster {cluster_id} ({key}):")
            print(f"    Non-zero features: {non_zero_count}/{len(embedding)}")
            print(f"    Sum of values: {np.sum(embedding_array):.4f}")
            print(f"    Max value: {np.max(embedding_array):.4f}")
            print(f"    Std dev: {np.std(embedding_array):.4f}")
            
            # Show top 5 non-zero features
            embedding_dict = embeddings[population_type]['embeddings_dict'][key]
            sorted_features = sorted(embedding_dict.items(), key=lambda x: x[1], reverse=True)
            print(f"    Top features:")
            for feat, val in sorted_features[:5]:
                if val > 0:
                    print(f"      {feat}: {val:.4f}")
        
        # Check if embeddings are identical
        print(f"\n  Comparing embeddings:")
        for i in range(k_value):
            for j in range(i+1, k_value):
                if np.array_equal(cluster_embeddings[i], cluster_embeddings[j]):
                    print(f"    WARNING: Cluster {i} and {j} have IDENTICAL embeddings!")
                else:
                    diff = np.sum(np.abs(cluster_embeddings[i] - cluster_embeddings[j]))
                    print(f"    Cluster {i} vs {j}: Total difference = {diff:.4f}")
        
        # Check across different percentiles for same cluster
        print(f"\n  Checking same cluster across percentiles:")
        cluster_id = 0
        test_percentiles = ['20', '30', '50', '70', '90']
        
        for p in test_percentiles:
            key = f"p{p}_k{k_value}_c{cluster_id}"
            embedding = np.array(embeddings[population_type]['embeddings_vector'][key])
            non_zero = np.count_nonzero(embedding)
            print(f"    P{p}, C{cluster_id}: {non_zero} non-zero features")


if __name__ == "__main__":
    check_embeddings()