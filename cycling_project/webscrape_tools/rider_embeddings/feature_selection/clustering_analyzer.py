import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple, Optional
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.decomposition import PCA
import warnings
from collections import defaultdict


class ClusteringQualityAnalyzer:
    """
    Analyze clustering quality of rider correlation data across percentiles.
    
    Determines which percentiles produce the most separable rider clusters
    based on their feature correlations.
    """
    
    def __init__(self, random_state: int = 42):
        """
        Initialize the clustering quality analyzer.
        
        Args:
            random_state: Random state for reproducible results
        """
        self.random_state = random_state
        
    def prepare_correlation_matrix(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        min_features: int = 5,
        selected_features: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[int], List[str]]:
        """
        Convert correlation results to a matrix suitable for clustering.
        
        Args:
            correlation_results: List of correlation results
            percentile: Percentile to analyze (e.g., 'race_features_100')
            min_features: Minimum number of valid features required per rider
            selected_features: If provided, only use these features for clustering
            
        Returns:
            Tuple of (correlation_matrix, rider_result_ids, feature_names)
        """
        # Filter valid results
        valid_results = [
            r for r in correlation_results 
            if (r['metadata']['n_races'] >= 5 and 
                not r['metadata']['warnings'] and
                percentile in r['feature_correlations'])
        ]
        
        if not valid_results:
            raise ValueError(f"No valid results found for percentile {percentile}")
        
        # Get features to use
        if selected_features:
            # Use only the selected features
            feature_names = selected_features
        else:
            # Get all possible features
            all_features = set()
            for result in valid_results:
                all_features.update(result['feature_correlations'][percentile].keys())
            feature_names = sorted(list(all_features))
        
        # Build correlation matrix
        correlation_matrix = []
        rider_ids = []
        
        for result in valid_results:
            correlations = result['feature_correlations'][percentile]
            
            # Create correlation vector
            corr_vector = []
            valid_count = 0
            
            for feature in feature_names:
                corr = correlations.get(feature)
                if corr is not None and not np.isnan(corr):
                    corr_vector.append(corr)
                    valid_count += 1
                else:
                    corr_vector.append(0.0)  # Impute missing as 0
            
            # Only include riders with sufficient valid features
            if valid_count >= min_features:
                correlation_matrix.append(corr_vector)
                rider_ids.append(result['rider_result_id'])
        
        if len(correlation_matrix) < 10:
            raise ValueError(f"Insufficient data: only {len(correlation_matrix)} riders with enough features")
        
        return np.array(correlation_matrix), rider_ids, feature_names
    
    def analyze_clustering_quality(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        k_range: List[int] = None,
        scale_features: bool = True,
        selected_features: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze clustering quality for a specific percentile.
        
        Args:
            correlation_results: List of correlation results
            percentile: Percentile to analyze
            k_range: Range of k values to test for clustering
            scale_features: Whether to standardize features before clustering
            selected_features: If provided, only use these features for clustering
            
        Returns:
            Dictionary with clustering quality metrics
        """
        if k_range is None:
            k_range = [2, 3, 4, 5, 6, 7, 8]
        
        # Prepare data
        correlation_matrix, rider_ids, feature_names = self.prepare_correlation_matrix(
            correlation_results, percentile, selected_features=selected_features
        )
        
        # Scale features if requested
        if scale_features:
            scaler = StandardScaler()
            scaled_matrix = scaler.fit_transform(correlation_matrix)
        else:
            scaled_matrix = correlation_matrix
        
        # Test different numbers of clusters
        clustering_results = {}
        
        for k in k_range:
            if k >= len(scaled_matrix):
                continue
                
            kmeans = KMeans(n_clusters=k, random_state=self.random_state, n_init=10)
            cluster_labels = kmeans.fit_predict(scaled_matrix)
            
            # Calculate quality metrics
            silhouette = silhouette_score(scaled_matrix, cluster_labels)
            calinski_harabasz = calinski_harabasz_score(scaled_matrix, cluster_labels)
            davies_bouldin = davies_bouldin_score(scaled_matrix, cluster_labels)
            
            # Calculate additional metrics
            inertia = kmeans.inertia_
            cluster_sizes = np.bincount(cluster_labels)
            size_balance = np.std(cluster_sizes) / np.mean(cluster_sizes)  # Lower is better
            
            clustering_results[k] = {
                'silhouette_score': silhouette,
                'calinski_harabasz_score': calinski_harabasz,
                'davies_bouldin_score': davies_bouldin,  # Lower is better
                'inertia': inertia,
                'size_balance': size_balance,
                'cluster_sizes': cluster_sizes.tolist(),
                'labels': cluster_labels.tolist()
            }
        
        # Find optimal k
        best_k = self._find_optimal_k(clustering_results)
        
        # PCA analysis
        pca_analysis = self._analyze_pca(scaled_matrix)
        
        return {
            'percentile': percentile,
            'data_shape': correlation_matrix.shape,
            'feature_names': feature_names,
            'rider_ids': rider_ids,
            'clustering_results': clustering_results,
            'optimal_k': best_k,
            'pca_analysis': pca_analysis,
            'scaled_features': scale_features
        }
    
    def _find_optimal_k(self, clustering_results: Dict[int, Dict[str, Any]]) -> int:
        """Find optimal number of clusters based on multiple metrics."""
        if not clustering_results:
            return 2
        
        scores = {}
        
        # Normalize metrics for comparison (higher is better for all)
        for k, results in clustering_results.items():
            # Silhouette: higher is better (already 0-1)
            silhouette_norm = results['silhouette_score']
            
            # Davies-Bouldin: lower is better, so invert
            db_norm = 1 / (1 + results['davies_bouldin_score'])
            
            # Size balance: lower is better, so invert
            balance_norm = 1 / (1 + results['size_balance'])
            
            # Combined score (equal weights)
            combined_score = (silhouette_norm + db_norm + balance_norm) / 3
            scores[k] = combined_score
        
        return max(scores.keys(), key=lambda k: scores[k])
    
    def _analyze_pca(self, correlation_matrix: np.ndarray) -> Dict[str, Any]:
        """Analyze PCA decomposition of correlation matrix."""
        pca = PCA()
        pca.fit(correlation_matrix)
        
        # Calculate cumulative variance explained
        cumvar = np.cumsum(pca.explained_variance_ratio_)
        
        # Find components needed for different variance thresholds
        var_thresholds = [0.5, 0.7, 0.8, 0.9, 0.95]
        components_needed = {}
        
        for threshold in var_thresholds:
            components_needed[threshold] = np.argmax(cumvar >= threshold) + 1
        
        return {
            'explained_variance_ratio': pca.explained_variance_ratio_[:10].tolist(),
            'cumulative_variance': cumvar[:10].tolist(),
            'components_for_variance': components_needed,
            'total_components': len(pca.explained_variance_ratio_)
        }
    
    def compare_percentiles(
        self, 
        correlation_results: List[Dict[str, Any]],
        percentiles: List[str] = None,
        k_range: List[int] = None
    ) -> Dict[str, Any]:
        """
        Compare clustering quality across multiple percentiles.
        
        Args:
            correlation_results: List of correlation results
            percentiles: List of percentiles to compare
            k_range: Range of k values to test
            
        Returns:
            Dictionary with comparative analysis
        """
        if percentiles is None:
            # Extract percentiles from first valid result
            valid_result = next(
                (r for r in correlation_results if r['feature_correlations']), 
                None
            )
            if valid_result:
                percentiles = list(valid_result['feature_correlations'].keys())
            else:
                raise ValueError("No valid correlation results found")
        
        percentile_analyses = {}
        percentile_scores = {}
        
        for percentile in percentiles:
            try:
                analysis = self.analyze_clustering_quality(
                    correlation_results, percentile, k_range
                )
                percentile_analyses[percentile] = analysis
                
                # Calculate overall score for this percentile
                optimal_k = analysis['optimal_k']
                if optimal_k in analysis['clustering_results']:
                    results = analysis['clustering_results'][optimal_k]
                    
                    # Composite score combining multiple metrics
                    silhouette = results['silhouette_score']
                    db_inverted = 1 / (1 + results['davies_bouldin_score'])
                    balance_inverted = 1 / (1 + results['size_balance'])
                    
                    # PCA score: more variance in fewer components is better
                    pca_score = analysis['pca_analysis']['explained_variance_ratio'][0]
                    
                    composite_score = (silhouette + db_inverted + balance_inverted + pca_score) / 4
                    percentile_scores[percentile] = composite_score
                
            except Exception as e:
                print(f"Warning: Could not analyze {percentile}: {e}")
                percentile_scores[percentile] = 0.0
        
        # Rank percentiles
        ranked_percentiles = sorted(
            percentile_scores.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return {
            'percentile_analyses': percentile_analyses,
            'percentile_scores': percentile_scores,
            'ranked_percentiles': ranked_percentiles,
            'best_percentile': ranked_percentiles[0][0] if ranked_percentiles else None
        }
    
    def get_cluster_characteristics(
        self, 
        correlation_results: List[Dict[str, Any]], 
        percentile: str,
        k: int = None,
        selected_features: Optional[List[str]] = None,
        precomputed_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze characteristics of clusters for a specific percentile and k.
        
        Args:
            correlation_results: List of correlation results
            percentile: Percentile to analyze
            k: Number of clusters (if None, uses optimal k)
            selected_features: If provided, only use these features for clustering
            precomputed_analysis: If provided, use this analysis instead of computing new one
            
        Returns:
            Dictionary with cluster characteristics
        """
        # Get clustering analysis
        if precomputed_analysis:
            analysis = precomputed_analysis
        else:
            analysis = self.analyze_clustering_quality(
                correlation_results, percentile, selected_features=selected_features
            )
        
        if k is None:
            k = analysis['optimal_k']
        
        if k not in analysis['clustering_results']:
            raise ValueError(f"k={k} not in clustering results")
        
        # Prepare data
        correlation_matrix, rider_ids, feature_names = self.prepare_correlation_matrix(
            correlation_results, percentile, selected_features=selected_features
        )
        
        # Get cluster labels
        labels = np.array(analysis['clustering_results'][k]['labels'])
        
        # Analyze each cluster
        cluster_characteristics = {}
        
        for cluster_id in range(k):
            cluster_mask = labels == cluster_id
            cluster_data = correlation_matrix[cluster_mask]
            cluster_riders = [rider_ids[i] for i in np.where(cluster_mask)[0]]
            
            # Calculate cluster statistics
            cluster_mean = np.mean(cluster_data, axis=0)
            cluster_std = np.std(cluster_data, axis=0)
            
            # Find most distinctive features (highest absolute mean)
            feature_importance = np.abs(cluster_mean)
            top_features_idx = np.argsort(feature_importance)[-10:][::-1]
            
            top_features = [
                {
                    'feature': feature_names[idx],
                    'mean_correlation': cluster_mean[idx],
                    'std_correlation': cluster_std[idx]
                }
                for idx in top_features_idx
            ]
            
            cluster_characteristics[cluster_id] = {
                'size': len(cluster_riders),
                'rider_ids': cluster_riders,
                'top_features': top_features,
                'mean_correlations': cluster_mean.tolist(),
                'std_correlations': cluster_std.tolist()
            }
        
        return {
            'percentile': percentile,
            'k': k,
            'feature_names': feature_names,
            'cluster_characteristics': cluster_characteristics,
            'silhouette_score': analysis['clustering_results'][k]['silhouette_score']
        }