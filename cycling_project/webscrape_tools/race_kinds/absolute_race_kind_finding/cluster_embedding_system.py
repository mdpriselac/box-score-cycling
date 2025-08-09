"""
Cluster Embedding System for Absolute Race Kind Clustering.

This module creates standardized cluster embeddings that enable cross-percentile
cluster comparison and future master-cluster assignment. Each cluster embedding
contains ALL features from the population with their importance values.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import warnings
warnings.filterwarnings('ignore')


class ClusterEmbeddingGenerator:
    """Generate standardized cluster embeddings for cross-percentile comparison."""
    
    def __init__(self):
        """Initialize embedding generator with clustering results."""
        self.base_dir = Path(__file__).parent
        self.breakdown_dir = self.base_dir / "clustering_results_with_breakdown"
        self.no_breakdown_dir = self.base_dir / "clustering_results_no_breakdown"
        
        # Load clustering results
        self.breakdown_results = self._load_results("with_breakdown")
        self.no_breakdown_results = self._load_results("no_breakdown")
        
        # Get complete feature spaces
        self.breakdown_feature_space = self._build_feature_space("with_breakdown")
        self.no_breakdown_feature_space = self._build_feature_space("no_breakdown")
        
        print(f"Breakdown population feature space: {len(self.breakdown_feature_space)} features")
        print(f"No-breakdown population feature space: {len(self.no_breakdown_feature_space)} features")
    
    def _load_results(self, population_type: str) -> Dict:
        """Load clustering results for a population."""
        if population_type == "with_breakdown":
            results_file = self.breakdown_dir / "absolute_clustering_results.json"
        else:
            results_file = self.no_breakdown_dir / "absolute_clustering_results.json"
        
        try:
            with open(results_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Warning: No results found for {population_type} population")
            return {}
    
    def _build_feature_space(self, population_type: str) -> List[str]:
        """Build complete feature space for a population across all percentiles."""
        if population_type == "with_breakdown":
            results = self.breakdown_results
        else:
            results = self.no_breakdown_results
        
        all_features = set()
        
        # Collect all features used across all percentiles and K values
        for percentile, percentile_results in results.items():
            for k_value, k_results in percentile_results.items():
                if 'feature_importances' in k_results:
                    features = k_results['feature_importances']['overall'].keys()
                    all_features.update(features)
        
        # Return sorted list for consistent ordering
        return sorted(list(all_features))
    
    def create_cluster_embedding_dict(self, population_type: str, percentile: str, 
                                    k_value: str, cluster_id: str) -> Dict[str, float]:
        """Create dictionary-format cluster embedding for a specific cluster."""
        if population_type == "with_breakdown":
            results = self.breakdown_results
            feature_space = self.breakdown_feature_space
        else:
            results = self.no_breakdown_results
            feature_space = self.no_breakdown_feature_space
        
        # Initialize embedding with all features set to 0
        embedding_dict = {feature: 0.0 for feature in feature_space}
        
        # Get cluster-specific feature importances if available
        if (percentile in results and 
            k_value in results[percentile] and 
            'feature_importances' in results[percentile][k_value]):
            
            cluster_key = f"cluster_{cluster_id}"
            cluster_data = results[percentile][k_value]['feature_importances']['by_cluster']
            
            if cluster_key in cluster_data:
                cluster_importances = cluster_data[cluster_key]['feature_importances']
                
                # Update embedding with actual feature importances
                for feature, importance in cluster_importances.items():
                    if feature in embedding_dict:
                        embedding_dict[feature] = importance
        
        return embedding_dict
    
    def create_cluster_embedding_vector(self, population_type: str, percentile: str, 
                                      k_value: str, cluster_id: str) -> np.ndarray:
        """Create vector-format cluster embedding for a specific cluster."""
        embedding_dict = self.create_cluster_embedding_dict(
            population_type, percentile, k_value, cluster_id
        )
        
        if population_type == "with_breakdown":
            feature_space = self.breakdown_feature_space
        else:
            feature_space = self.no_breakdown_feature_space
        
        # Convert to vector using consistent feature ordering
        embedding_vector = np.array([embedding_dict[feature] for feature in feature_space])
        
        return embedding_vector
    
    def generate_all_embeddings(self) -> Dict:
        """Generate all cluster embeddings for both populations."""
        embeddings = {
            'with_breakdown': {
                'feature_space': self.breakdown_feature_space,
                'embeddings_dict': {},
                'embeddings_vector': {},
                'metadata': {}
            },
            'no_breakdown': {
                'feature_space': self.no_breakdown_feature_space,
                'embeddings_dict': {},
                'embeddings_vector': {},
                'metadata': {}
            }
        }
        
        # Generate embeddings for breakdown population
        self._generate_population_embeddings('with_breakdown', embeddings['with_breakdown'])
        
        # Generate embeddings for no-breakdown population
        self._generate_population_embeddings('no_breakdown', embeddings['no_breakdown'])
        
        return embeddings
    
    def _generate_population_embeddings(self, population_type: str, embedding_data: Dict):
        """Generate embeddings for a specific population."""
        if population_type == "with_breakdown":
            results = self.breakdown_results
        else:
            results = self.no_breakdown_results
        
        print(f"\nGenerating embeddings for {population_type} population...")
        
        total_embeddings = 0
        
        for percentile, percentile_results in results.items():
            if not percentile_results:
                continue
                
            print(f"  Processing percentile {percentile}...")
            
            for k_value, k_results in percentile_results.items():
                if 'feature_importances' not in k_results:
                    continue
                
                n_clusters = int(k_value)
                
                for cluster_id in range(n_clusters):
                    # Create embedding key
                    embedding_key = f"p{percentile}_k{k_value}_c{cluster_id}"
                    
                    # Generate dictionary embedding
                    dict_embedding = self.create_cluster_embedding_dict(
                        population_type, percentile, k_value, str(cluster_id)
                    )
                    
                    # Generate vector embedding
                    vector_embedding = self.create_cluster_embedding_vector(
                        population_type, percentile, k_value, str(cluster_id)
                    )
                    
                    # Store embeddings
                    embedding_data['embeddings_dict'][embedding_key] = dict_embedding
                    embedding_data['embeddings_vector'][embedding_key] = vector_embedding.tolist()
                    
                    # Store metadata
                    embedding_data['metadata'][embedding_key] = {
                        'percentile': int(percentile),
                        'k_value': int(k_value),
                        'cluster_id': cluster_id,
                        'population_type': population_type,
                        'n_features_used': sum(1 for v in dict_embedding.values() if v > 0),
                        'total_importance': sum(dict_embedding.values()),
                        'max_importance': max(dict_embedding.values()) if dict_embedding.values() else 0,
                        'top_features': self._get_top_features(dict_embedding, n=5)
                    }
                    
                    total_embeddings += 1
        
        print(f"  Generated {total_embeddings} cluster embeddings")
    
    def _get_top_features(self, embedding_dict: Dict[str, float], n: int = 5) -> List[Tuple[str, float]]:
        """Get top N features by importance from embedding."""
        sorted_features = sorted(embedding_dict.items(), key=lambda x: x[1], reverse=True)
        return [(feature, importance) for feature, importance in sorted_features[:n] if importance > 0]
    
    def calculate_embedding_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray, 
                                     method: str = 'cosine') -> float:
        """Calculate similarity between two cluster embeddings."""
        if method == 'cosine':
            # Cosine similarity
            dot_product = np.dot(embedding1, embedding2)
            norm1 = np.linalg.norm(embedding1)
            norm2 = np.linalg.norm(embedding2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return dot_product / (norm1 * norm2)
        
        elif method == 'euclidean':
            # Negative Euclidean distance (higher values = more similar)
            return -np.linalg.norm(embedding1 - embedding2)
        
        elif method == 'correlation':
            # Pearson correlation coefficient
            return np.corrcoef(embedding1, embedding2)[0, 1] if len(embedding1) > 1 else 0.0
        
        else:
            raise ValueError(f"Unknown similarity method: {method}")
    
    def find_similar_clusters(self, population_type: str, reference_percentile: str, 
                            reference_k: str, reference_cluster: str, 
                            target_percentile: str = None, top_n: int = 10) -> List[Dict]:
        """Find clusters most similar to a reference cluster."""
        embeddings = self.generate_all_embeddings()
        
        # Get reference embedding
        ref_key = f"p{reference_percentile}_k{reference_k}_c{reference_cluster}"
        
        if ref_key not in embeddings[population_type]['embeddings_vector']:
            raise ValueError(f"Reference cluster not found: {ref_key}")
        
        ref_vector = np.array(embeddings[population_type]['embeddings_vector'][ref_key])
        
        similarities = []
        
        for key, vector in embeddings[population_type]['embeddings_vector'].items():
            # Skip self-comparison
            if key == ref_key:
                continue
                
            # Filter by target percentile if specified
            if target_percentile is not None:
                if not key.startswith(f"p{target_percentile}_"):
                    continue
            
            # Calculate similarity
            target_vector = np.array(vector)
            similarity = self.calculate_embedding_similarity(ref_vector, target_vector)
            
            similarities.append({
                'cluster_key': key,
                'similarity': similarity,
                'metadata': embeddings[population_type]['metadata'][key]
            })
        
        # Sort by similarity and return top N
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        return similarities[:top_n]
    
    def analyze_cross_percentile_patterns(self, population_type: str, k_value: str) -> Dict:
        """Analyze how clusters change across percentiles for a given K value."""
        embeddings = self.generate_all_embeddings()
        
        analysis = {
            'k_value': int(k_value),
            'population_type': population_type,
            'percentile_clusters': {},
            'cross_percentile_similarities': {},
            'stable_features': {},
            'changing_features': {}
        }
        
        # Collect clusters for each percentile
        for key, metadata in embeddings[population_type]['metadata'].items():
            if metadata['k_value'] == int(k_value):
                percentile = metadata['percentile']
                if percentile not in analysis['percentile_clusters']:
                    analysis['percentile_clusters'][percentile] = []
                
                analysis['percentile_clusters'][percentile].append({
                    'cluster_key': key,
                    'cluster_id': metadata['cluster_id'],
                    'top_features': metadata['top_features'],
                    'total_importance': metadata['total_importance']
                })
        
        # Calculate cross-percentile similarities for each cluster position
        for cluster_id in range(int(k_value)):
            cluster_similarities = {}
            
            for p1 in analysis['percentile_clusters'].keys():
                for p2 in analysis['percentile_clusters'].keys():
                    if p1 >= p2:  # Only calculate upper triangle
                        continue
                    
                    key1 = f"p{p1}_k{k_value}_c{cluster_id}"
                    key2 = f"p{p2}_k{k_value}_c{cluster_id}"
                    
                    if (key1 in embeddings[population_type]['embeddings_vector'] and 
                        key2 in embeddings[population_type]['embeddings_vector']):
                        
                        vec1 = np.array(embeddings[population_type]['embeddings_vector'][key1])
                        vec2 = np.array(embeddings[population_type]['embeddings_vector'][key2])
                        
                        similarity = self.calculate_embedding_similarity(vec1, vec2)
                        cluster_similarities[f"p{p1}_vs_p{p2}"] = similarity
            
            analysis['cross_percentile_similarities'][f'cluster_{cluster_id}'] = cluster_similarities
        
        return analysis
    
    def save_embeddings(self, output_dir: Optional[Path] = None):
        """Save all cluster embeddings to files."""
        if output_dir is None:
            output_dir = self.base_dir / "cluster_embeddings"
        
        output_dir.mkdir(exist_ok=True)
        
        # Generate all embeddings
        print("Generating all cluster embeddings...")
        embeddings = self.generate_all_embeddings()
        
        # Save complete embeddings data
        embeddings_file = output_dir / "complete_cluster_embeddings.json"
        
        # Convert numpy arrays to lists for JSON serialization
        json_embeddings = {}
        for population, data in embeddings.items():
            json_embeddings[population] = {
                'feature_space': data['feature_space'],
                'embeddings_dict': data['embeddings_dict'],
                'embeddings_vector': data['embeddings_vector'],  # Already converted to lists
                'metadata': data['metadata']
            }
        
        with open(embeddings_file, 'w') as f:
            json.dump(json_embeddings, f, indent=2)
        
        print(f"Complete embeddings saved to {embeddings_file}")
        
        # Save summary statistics
        summary = {
            'breakdown_population': {
                'feature_space_size': len(embeddings['with_breakdown']['feature_space']),
                'total_embeddings': len(embeddings['with_breakdown']['embeddings_dict']),
                'percentiles_covered': list(set([meta['percentile'] for meta in embeddings['with_breakdown']['metadata'].values()])),
                'k_values_covered': list(set([meta['k_value'] for meta in embeddings['with_breakdown']['metadata'].values()]))
            },
            'no_breakdown_population': {
                'feature_space_size': len(embeddings['no_breakdown']['feature_space']),
                'total_embeddings': len(embeddings['no_breakdown']['embeddings_dict']),
                'percentiles_covered': list(set([meta['percentile'] for meta in embeddings['no_breakdown']['metadata'].values()])),
                'k_values_covered': list(set([meta['k_value'] for meta in embeddings['no_breakdown']['metadata'].values()]))
            }
        }
        
        summary_file = output_dir / "embedding_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Embedding summary saved to {summary_file}")
        
        # Save feature spaces separately for easy reference
        breakdown_features_file = output_dir / "breakdown_feature_space.json"
        with open(breakdown_features_file, 'w') as f:
            json.dump(embeddings['with_breakdown']['feature_space'], f, indent=2)
        
        no_breakdown_features_file = output_dir / "no_breakdown_feature_space.json"
        with open(no_breakdown_features_file, 'w') as f:
            json.dump(embeddings['no_breakdown']['feature_space'], f, indent=2)
        
        print(f"Feature spaces saved to {output_dir}")
        
        return embeddings


def main():
    """Generate cluster embeddings for both populations."""
    print("=" * 60)
    print("CLUSTER EMBEDDING GENERATION")
    print("=" * 60)
    
    generator = ClusterEmbeddingGenerator()
    
    # Generate and save all embeddings
    embeddings = generator.save_embeddings()
    
    # Print some example analysis
    print("\n" + "=" * 60)
    print("EXAMPLE ANALYSIS")
    print("=" * 60)
    
    # Find similar clusters example
    try:
        similar = generator.find_similar_clusters(
            population_type='with_breakdown',
            reference_percentile='25',
            reference_k='3', 
            reference_cluster='0',
            top_n=5
        )
        
        print(f"\nTop 5 clusters similar to breakdown p25_k3_c0:")
        for i, sim in enumerate(similar, 1):
            print(f"{i}. {sim['cluster_key']}: similarity = {sim['similarity']:.3f}")
            print(f"   Top features: {[f'{name}:{val:.3f}' for name, val in sim['metadata']['top_features'][:3]]}")
    
    except Exception as e:
        print(f"Similar cluster analysis failed: {e}")
    
    # Cross-percentile pattern analysis example
    try:
        patterns = generator.analyze_cross_percentile_patterns('with_breakdown', '3')
        print(f"\nCross-percentile similarity analysis for breakdown K=3:")
        
        for cluster_id, similarities in patterns['cross_percentile_similarities'].items():
            if similarities:  # Only show if we have data
                avg_similarity = np.mean(list(similarities.values()))
                print(f"{cluster_id}: average cross-percentile similarity = {avg_similarity:.3f}")
                break  # Just show one example
    
    except Exception as e:
        print(f"Cross-percentile analysis failed: {e}")
    
    print("\n" + "=" * 60)
    print("CLUSTER EMBEDDING GENERATION COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    main()