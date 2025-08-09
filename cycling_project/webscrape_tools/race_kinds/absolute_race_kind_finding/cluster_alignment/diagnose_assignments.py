"""
Diagnostic script to analyze master cluster assignments
"""

import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path


def diagnose_assignments():
    """Check if assignments are actually being optimized or just matching indices."""
    
    # Load embeddings
    with open('../cluster_embeddings/complete_cluster_embeddings.json') as f:
        embeddings = json.load(f)
    
    # Check both populations
    for population_type in ['with_breakdown', 'no_breakdown']:
        print(f"\n{'='*60}")
        print(f"DIAGNOSING: {population_type}")
        print(f"{'='*60}")
        
        # Check K=3 as an example
        k_value = 3
        print(f"\nAnalyzing K={k_value}")
        
        # Get reference percentile embeddings (50)
        ref_percentile = '50'
        ref_embeddings = []
        for cluster_id in range(k_value):
            key = f"p{ref_percentile}_k{k_value}_c{cluster_id}"
            ref_embeddings.append(
                np.array(embeddings[population_type]['embeddings_vector'][key])
            )
        
        # Check a few other percentiles
        test_percentiles = ['20', '30', '70', '90']
        
        for test_p in test_percentiles:
            print(f"\n  Percentile {test_p} vs Reference {ref_percentile}:")
            
            # Create similarity matrix
            similarity_matrix = np.zeros((k_value, k_value))
            
            for local_cluster in range(k_value):
                local_key = f"p{test_p}_k{k_value}_c{local_cluster}"
                local_embedding = np.array(
                    embeddings[population_type]['embeddings_vector'][local_key]
                )
                
                for ref_cluster in range(k_value):
                    similarity = cosine_similarity(
                        [local_embedding],
                        [ref_embeddings[ref_cluster]]
                    )[0][0]
                    similarity_matrix[local_cluster, ref_cluster] = similarity
            
            # Display similarity matrix
            print(f"    Similarity Matrix:")
            print(f"    (rows=P{test_p} clusters, cols=P{ref_percentile} masters)")
            print(f"    {'':8}", end='')
            for j in range(k_value):
                print(f"M{j:6}", end='')
            print()
            
            for i in range(k_value):
                print(f"    C{i}: ", end='')
                for j in range(k_value):
                    sim = similarity_matrix[i, j]
                    # Highlight diagonal values
                    if i == j:
                        print(f"[{sim:5.3f}]", end='')
                    else:
                        print(f" {sim:5.3f} ", end='')
                print()
            
            # Find best assignment for each cluster
            print(f"    Best matches:")
            for i in range(k_value):
                best_match = np.argmax(similarity_matrix[i])
                best_sim = similarity_matrix[i, best_match]
                diagonal_sim = similarity_matrix[i, i]
                
                if best_match == i:
                    print(f"      C{i} -> M{best_match} (diagonal match, sim={best_sim:.3f})")
                else:
                    print(f"      C{i} -> M{best_match} (sim={best_sim:.3f}) "
                          f"[diagonal would be {diagonal_sim:.3f}]")
            
            # Check if Hungarian algorithm would pick different assignment
            from scipy.optimize import linear_sum_assignment
            cost_matrix = -similarity_matrix  # Negative for minimization
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            
            hungarian_same_as_diagonal = all(row_ind[i] == col_ind[i] == i for i in range(k_value))
            
            if hungarian_same_as_diagonal:
                print(f"    Hungarian result: SAME as diagonal (0->0, 1->1, 2->2)")
            else:
                print(f"    Hungarian result: DIFFERENT from diagonal!")
                for i, j in zip(row_ind, col_ind):
                    print(f"      C{i} -> M{j}")
        
        # Also check assignment files if they exist
        assignment_file = Path(f'alignment_results/data/{population_type}_k{k_value}_assignments.json')
        if assignment_file.exists():
            print(f"\n  Checking saved assignments:")
            with open(assignment_file) as f:
                saved_assignments = json.load(f)
            
            # Check if all percentiles have diagonal assignments
            all_diagonal = True
            for p, assignments in saved_assignments.items():
                for local_id, master_id in assignments.items():
                    if str(local_id) != str(master_id):
                        all_diagonal = False
                        print(f"    P{p}: C{local_id} -> M{master_id} (non-diagonal!)")
            
            if all_diagonal:
                print(f"    WARNING: All assignments are diagonal (0->0, 1->1, 2->2)")
                print(f"    This suggests clusters might be too similar or there's an issue")


if __name__ == "__main__":
    diagnose_assignments()