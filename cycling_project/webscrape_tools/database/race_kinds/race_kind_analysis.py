"""
Race Kind Analysis Module

This module provides various methods for identifying and categorizing races into different kinds
based on their statistical and engineered features. It includes multiple clustering algorithms,
dimensionality reduction techniques, and custom scoring systems.
"""

import numpy as np
import pandas as pd
import sqlite3
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.decomposition import PCA
from sklearn.metrics import (
    silhouette_score, calinski_harabasz_score, davies_bouldin_score,
    pairwise_distances
)
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import cdist
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')


class RaceKindAnalyzer:
    """
    Main class for analyzing and categorizing races into kinds based on their features.
    """
    
    def __init__(self, db_path: str, feature_columns: Optional[List[str]] = None):
        """
        Initialize the RaceKindAnalyzer.
        
        Args:
            db_path: Path to the SQLite database containing race features
            feature_columns: List of feature columns to use (None for default set)
        """
        self.db_path = db_path
        
        # Use provided features or default set
        if feature_columns is not None:
            self.feature_columns = feature_columns
        else:
            self.feature_columns = [
                'variance_normalized', 'std_deviation_normalized',
                'skewness_absolute', 'kurtosis_absolute',
                'gini_coefficient', 'shannon_entropy_normalized',
                'biggest_group_metric', 'time_gap_evenness_metric',
                'clumpiness_score', 'selection_metric',
                'proportion_in_groups', 'avg_group_size',
                '10th_percentile_gap', '25th_percentile_gap', '50th_percentile_gap'
            ]
        
        self.scaler = None
        self.data = None
        self.scaled_features = None
        
    def set_feature_columns(self, feature_columns: List[str]):
        """
        Set the feature columns to use for analysis.
        
        Args:
            feature_columns: List of feature column names
        """
        self.feature_columns = feature_columns
        # Reset prepared features if they exist
        self.scaled_features = None
        
    def load_data(
        self,
        table_name: str,
        competition_type: Optional[str] = None,
        race_category: Optional[str] = None,
        min_finishers: int = 30
    ) -> pd.DataFrame:
        """
        Load race feature data from a specific percentile table.
        
        Args:
            table_name: Name of the percentile table (e.g., 'race_features_70')
            competition_type: Filter by competition type ('gc', 'stage', 'one_day', 'stage_one_day')
            race_category: Filter by race category ('wt', 'pro', 'd1')
            min_finishers: Minimum number of finishers required
            
        Returns:
            DataFrame with loaded race features
        """
        conn = sqlite3.connect(self.db_path)
        
        # Build dynamic query with only needed columns plus metadata
        metadata_columns = [
            'competition_id', 'competition_name', 'competition_type',
            'race_id', 'race_name', 'race_category', 'race_year', 'race_date'
        ]
        
        # Check which feature columns exist in the table
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        available_columns = {col[1] for col in cursor.fetchall()}
        
        # Filter feature columns to only include those that exist
        valid_features = [col for col in self.feature_columns if col in available_columns]
        if len(valid_features) < len(self.feature_columns):
            missing = set(self.feature_columns) - set(valid_features)
            print(f"Warning: Missing features in {table_name}: {missing}")
            self.feature_columns = valid_features
        
        # Build column list for query - quote column names that start with numbers
        quoted_metadata = []
        for col in metadata_columns:
            if col[0].isdigit():
                quoted_metadata.append(f'"{col}"')
            else:
                quoted_metadata.append(col)
        
        quoted_features = []
        for col in valid_features:
            if col[0].isdigit():
                quoted_features.append(f'"{col}"')
            else:
                quoted_features.append(col)
        
        query_columns = quoted_metadata + quoted_features
        columns_str = ', '.join(query_columns)
        
        query = f"SELECT {columns_str} FROM {table_name} WHERE included_finishers >= ?"
        params = [min_finishers]
        
        if competition_type is not None:
            if competition_type == 'gc':
                query += " AND competition_type = ?"
                params.append('gc')
            elif competition_type == 'stage_one_day':
                query += " AND competition_type IN (?, ?)"
                params.extend(['stage', 'one_day'])
            elif competition_type in ['stage', 'one_day']:
                query += " AND competition_type = ?"
                params.append(competition_type)
            else:
                query += " AND competition_type = ?"
                params.append(competition_type)
        
        if race_category is not None:
            query += " AND race_category = ?"
            params.append(race_category)
        
        self.data = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return self.data
    
    def prepare_features(self, scaling_method: str = 'standard') -> np.ndarray:
        """
        Prepare and scale features for analysis.
        
        Args:
            scaling_method: 'standard' for StandardScaler, 'robust' for RobustScaler
            
        Returns:
            Scaled feature array
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Extract features
        features = self.data[self.feature_columns].fillna(0)
        
        # Scale features
        if scaling_method == 'standard':
            self.scaler = StandardScaler()
        elif scaling_method == 'robust':
            self.scaler = RobustScaler()
        else:
            raise ValueError(f"Unknown scaling method: {scaling_method}")
        
        self.scaled_features = self.scaler.fit_transform(features)
        return self.scaled_features
    
    def kmeans_clustering(
        self,
        n_clusters_range: range = range(2, 11),
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Perform K-means clustering with multiple cluster numbers.
        
        Args:
            n_clusters_range: Range of cluster numbers to try
            random_state: Random seed for reproducibility
            
        Returns:
            Dictionary containing clustering results and evaluation metrics
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        results = {
            'method': 'kmeans',
            'cluster_results': {},
            'evaluation_metrics': {},
            'best_n_clusters': None,
            'best_score': -np.inf
        }
        
        for n_clusters in n_clusters_range:
            # Fit K-means
            kmeans = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
            labels = kmeans.fit_predict(self.scaled_features)
            
            # Calculate metrics
            if n_clusters < len(np.unique(labels)) or n_clusters >= len(self.scaled_features):
                continue
                
            silhouette = silhouette_score(self.scaled_features, labels)
            calinski = calinski_harabasz_score(self.scaled_features, labels)
            davies_bouldin = davies_bouldin_score(self.scaled_features, labels)
            
            # Calculate inertia ratio
            inertia_ratio = kmeans.inertia_ / len(self.scaled_features)
            
            # Store results
            results['cluster_results'][n_clusters] = {
                'labels': labels,
                'centers': kmeans.cluster_centers_,
                'inertia': kmeans.inertia_,
                'model': kmeans  # Store the model for evaluation
            }
            
            results['evaluation_metrics'][n_clusters] = {
                'silhouette_score': silhouette,
                'calinski_harabasz_score': calinski,
                'davies_bouldin_score': davies_bouldin,
                'inertia_ratio': inertia_ratio
            }
            
            # Update best based on silhouette score
            if silhouette > results['best_score']:
                results['best_score'] = silhouette
                results['best_n_clusters'] = n_clusters
        
        return results
    
    def hierarchical_clustering(
        self,
        n_clusters_range: range = range(2, 11),
        linkage_method: str = 'ward'
    ) -> Dict[str, Any]:
        """
        Perform hierarchical clustering.
        
        Args:
            n_clusters_range: Range of cluster numbers to try
            linkage_method: Linkage method ('ward', 'complete', 'average', 'single')
            
        Returns:
            Dictionary containing clustering results and evaluation metrics
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        results = {
            'method': 'hierarchical',
            'linkage_method': linkage_method,
            'cluster_results': {},
            'evaluation_metrics': {},
            'best_n_clusters': None,
            'best_score': -np.inf,
            'linkage_matrix': linkage(self.scaled_features, method=linkage_method)
        }
        
        for n_clusters in n_clusters_range:
            # Fit hierarchical clustering
            hc = AgglomerativeClustering(n_clusters=n_clusters, linkage=linkage_method)
            labels = hc.fit_predict(self.scaled_features)
            
            # Calculate metrics
            if n_clusters < len(np.unique(labels)) or n_clusters >= len(self.scaled_features):
                continue
                
            silhouette = silhouette_score(self.scaled_features, labels)
            calinski = calinski_harabasz_score(self.scaled_features, labels)
            davies_bouldin = davies_bouldin_score(self.scaled_features, labels)
            
            # Store results
            results['cluster_results'][n_clusters] = {
                'labels': labels,
                'model': hc  # Store the model for evaluation
            }
            
            results['evaluation_metrics'][n_clusters] = {
                'silhouette_score': silhouette,
                'calinski_harabasz_score': calinski,
                'davies_bouldin_score': davies_bouldin
            }
            
            # Update best based on silhouette score
            if silhouette > results['best_score']:
                results['best_score'] = silhouette
                results['best_n_clusters'] = n_clusters
        
        return results
    
    def dbscan_clustering(
        self,
        eps_range: List[float] = None,
        min_samples_range: List[int] = None
    ) -> Dict[str, Any]:
        """
        Perform DBSCAN clustering with different parameters.
        
        Args:
            eps_range: Range of epsilon values to try
            min_samples_range: Range of min_samples values to try
            
        Returns:
            Dictionary containing clustering results and evaluation metrics
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        if eps_range is None:
            # Calculate distances to find appropriate eps range
            distances = pairwise_distances(self.scaled_features)
            eps_range = np.percentile(distances.flatten(), [1, 2, 3, 5, 7, 10])
        
        if min_samples_range is None:
            min_samples_range = [3, 5, 7, 10]
        
        results = {
            'method': 'dbscan',
            'parameter_results': {},
            'best_params': None,
            'best_score': -np.inf
        }
        
        for eps in eps_range:
            for min_samples in min_samples_range:
                # Fit DBSCAN
                dbscan = DBSCAN(eps=eps, min_samples=min_samples)
                labels = dbscan.fit_predict(self.scaled_features)
                
                # Check if meaningful clusters were found
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                n_noise = list(labels).count(-1)
                
                if n_clusters < 2 or n_clusters >= len(self.scaled_features) * 0.5:
                    continue
                
                # Calculate metrics only for non-noise points
                non_noise_mask = labels != -1
                if np.sum(non_noise_mask) < 10:
                    continue
                
                silhouette = silhouette_score(
                    self.scaled_features[non_noise_mask],
                    labels[non_noise_mask]
                ) if n_clusters > 1 else -1
                
                # Store results
                param_key = f"eps={eps:.3f}_min_samples={min_samples}"
                results['parameter_results'][param_key] = {
                    'labels': labels,
                    'n_clusters': n_clusters,
                    'n_noise': n_noise,
                    'silhouette_score': silhouette,
                    'noise_ratio': n_noise / len(labels)
                }
                
                # Update best based on silhouette score
                if silhouette > results['best_score'] and n_noise < len(labels) * 0.3:
                    results['best_score'] = silhouette
                    results['best_params'] = {'eps': eps, 'min_samples': min_samples}
        
        return results
    
    def gaussian_mixture_clustering(
        self,
        n_components_range: range = range(2, 11),
        random_state: int = 42
    ) -> Dict[str, Any]:
        """
        Perform Gaussian Mixture Model clustering.
        
        Args:
            n_components_range: Range of component numbers to try
            random_state: Random seed for reproducibility
            
        Returns:
            Dictionary containing clustering results and evaluation metrics
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        results = {
            'method': 'gaussian_mixture',
            'cluster_results': {},
            'evaluation_metrics': {},
            'best_n_components': None,
            'best_score': -np.inf
        }
        
        for n_components in n_components_range:
            # Fit Gaussian Mixture
            gmm = GaussianMixture(
                n_components=n_components,
                random_state=random_state,
                n_init=3
            )
            gmm.fit(self.scaled_features)
            labels = gmm.predict(self.scaled_features)
            
            # Calculate metrics
            if n_components < len(np.unique(labels)) or n_components >= len(self.scaled_features):
                continue
                
            silhouette = silhouette_score(self.scaled_features, labels)
            aic = gmm.aic(self.scaled_features)
            bic = gmm.bic(self.scaled_features)
            
            # Store results
            results['cluster_results'][n_components] = {
                'labels': labels,
                'means': gmm.means_,
                'covariances': gmm.covariances_,
                'weights': gmm.weights_,
                'converged': gmm.converged_,
                'model': gmm  # Store the model for evaluation
            }
            
            results['evaluation_metrics'][n_components] = {
                'silhouette_score': silhouette,
                'aic': aic,
                'bic': bic,
                'log_likelihood': gmm.score(self.scaled_features)
            }
            
            # Update best based on silhouette score (higher is better)
            if silhouette > results['best_score']:
                results['best_score'] = silhouette
                results['best_n_components'] = n_components
        
        return results
    
    def pca_analysis(self, n_components: int = None) -> Dict[str, Any]:
        """
        Perform PCA analysis for dimensionality reduction and visualization.
        
        Args:
            n_components: Number of components (None for all)
            
        Returns:
            Dictionary containing PCA results
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        # Fit PCA
        pca = PCA(n_components=n_components)
        transformed_features = pca.fit_transform(self.scaled_features)
        
        results = {
            'method': 'pca',
            'transformed_features': transformed_features,
            'components': pca.components_,
            'explained_variance': pca.explained_variance_,
            'explained_variance_ratio': pca.explained_variance_ratio_,
            'cumulative_variance_ratio': np.cumsum(pca.explained_variance_ratio_),
            'n_components_95': np.argmax(np.cumsum(pca.explained_variance_ratio_) >= 0.95) + 1
        }
        
        # Feature importance for each component
        feature_importance = {}
        for i in range(min(5, len(pca.components_))):  # Top 5 components
            component_weights = np.abs(pca.components_[i])
            feature_indices = np.argsort(component_weights)[::-1]
            feature_importance[f'PC{i+1}'] = [
                (self.feature_columns[idx], component_weights[idx])
                for idx in feature_indices[:5]  # Top 5 features
            ]
        
        results['feature_importance'] = feature_importance
        
        return results
    
    def feature_based_scoring(self) -> Dict[str, Any]:
        """
        Create custom scoring systems based on domain knowledge of cycling races.
        
        Returns:
            Dictionary containing different scoring systems and their results
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Check if required features are available
        required_features = [
            'biggest_group_metric', 'selection_metric', 'proportion_in_groups',
            'gini_coefficient', 'std_deviation_normalized', 'abandon_ratio',
            'time_gap_evenness_metric', 'clumpiness_score', 'variance_normalized'
        ]
        
        missing_features = [f for f in required_features if f not in self.data.columns]
        
        if missing_features:
            # If critical features are missing, return a simplified analysis
            return {
                'method': 'feature_based_scoring',
                'error': f'Missing required features: {missing_features}',
                'dominant_type': ['mixed'] * len(self.data),  # Fallback classification
                'confidence': [0.5] * len(self.data)
            }
        
        results = {
            'method': 'feature_based_scoring',
            'scoring_systems': {}
        }
        
        # 1. Sprint Finish Score (high group metric, low selection)
        sprint_score = (
            self.data['biggest_group_metric'] * 2 +
            (1 - self.data['selection_metric']) +
            self.data['proportion_in_groups']
        ) / 4
        
        # 2. Selective Race Score (high selection, high spread)
        selective_score = (
            self.data['selection_metric'] * 2 +
            self.data['gini_coefficient'] +
            self.data['std_deviation_normalized']
        ) / 4
        
        # 3. Attritional Race Score (high abandon ratio, high time gaps)
        attritional_score = (
            self.data['abandon_ratio'] * 2 +
            self.data.get('50th_percentile_gap', 0) / 300 +  # Normalize to ~0-1
            self.data['variance_normalized']
        ) / 4
        
        # 4. Balanced Race Score (even gaps, medium selection)
        balanced_score = (
            self.data['time_gap_evenness_metric'] * 2 +
            (1 - abs(self.data['selection_metric'] - 0.5) * 2) +
            (1 - self.data['clumpiness_score'])
        ) / 4
        
        # Normalize all scores to 0-1
        for score_name, score_values in [
            ('sprint_finish', sprint_score),
            ('selective', selective_score),
            ('attritional', attritional_score),
            ('balanced', balanced_score)
        ]:
            score_min, score_max = score_values.min(), score_values.max()
            if score_max > score_min:
                normalized_score = (score_values - score_min) / (score_max - score_min)
            else:
                normalized_score = score_values
            
            results['scoring_systems'][score_name] = {
                'scores': normalized_score.values,
                'mean': float(normalized_score.mean()),
                'std': float(normalized_score.std()),
                'categories': self._categorize_by_score(normalized_score)
            }
        
        # Combined categorization based on dominant score
        all_scores = pd.DataFrame({
            'sprint': results['scoring_systems']['sprint_finish']['scores'],
            'selective': results['scoring_systems']['selective']['scores'],
            'attritional': results['scoring_systems']['attritional']['scores'],
            'balanced': results['scoring_systems']['balanced']['scores']
        })
        
        results['dominant_type'] = all_scores.idxmax(axis=1).values
        results['dominant_score'] = all_scores.max(axis=1).values
        
        return results
    
    def _categorize_by_score(self, scores: pd.Series, n_categories: int = 3) -> np.ndarray:
        """
        Categorize races based on score thresholds.
        
        Args:
            scores: Series of scores
            n_categories: Number of categories
            
        Returns:
            Array of category labels
        """
        thresholds = np.percentile(scores, np.linspace(0, 100, n_categories + 1)[1:-1])
        categories = np.digitize(scores, thresholds)
        return categories
    
    def evaluate_clustering_stability(
        self,
        method_results: Dict[str, Any],
        n_iterations: int = 10,
        subsample_ratio: float = 0.8
    ) -> Dict[str, float]:
        """
        Evaluate the stability of a clustering method through subsampling.
        
        Args:
            method_results: Results from a clustering method
            n_iterations: Number of subsampling iterations
            subsample_ratio: Ratio of data to use in each iteration
            
        Returns:
            Dictionary with stability metrics
        """
        if self.scaled_features is None:
            raise ValueError("Features not prepared. Call prepare_features() first.")
        
        method = method_results['method']
        
        # Get best parameters
        if method == 'kmeans':
            n_clusters = method_results['best_n_clusters']
            reference_labels = method_results['cluster_results'][n_clusters]['labels']
        elif method == 'hierarchical':
            n_clusters = method_results['best_n_clusters']
            reference_labels = method_results['cluster_results'][n_clusters]['labels']
        else:
            return {'stability_score': 0.0}
        
        stability_scores = []
        
        for _ in range(n_iterations):
            # Subsample data
            n_samples = len(self.scaled_features)
            subsample_size = int(n_samples * subsample_ratio)
            indices = np.random.choice(n_samples, subsample_size, replace=False)
            subsample_features = self.scaled_features[indices]
            
            # Re-cluster
            if method == 'kmeans':
                kmeans = KMeans(n_clusters=n_clusters, random_state=np.random.randint(1000))
                subsample_labels = kmeans.fit_predict(subsample_features)
            elif method == 'hierarchical':
                hc = AgglomerativeClustering(n_clusters=n_clusters)
                subsample_labels = hc.fit_predict(subsample_features)
            
            # Compare with reference (for overlapping samples)
            reference_subset = reference_labels[indices]
            
            # Calculate adjusted rand index (simple version)
            from sklearn.metrics import adjusted_rand_score
            stability = adjusted_rand_score(reference_subset, subsample_labels)
            stability_scores.append(stability)
        
        return {
            'stability_mean': float(np.mean(stability_scores)),
            'stability_std': float(np.std(stability_scores)),
            'stability_min': float(np.min(stability_scores)),
            'stability_max': float(np.max(stability_scores))
        }
    
    def get_cluster_characteristics(
        self,
        labels: np.ndarray,
        top_n_features: int = 5
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get characteristics of each cluster.
        
        Args:
            labels: Cluster labels
            top_n_features: Number of top distinguishing features to return
            
        Returns:
            Dictionary with cluster characteristics
        """
        if self.data is None or self.scaled_features is None:
            raise ValueError("No data loaded or features not prepared.")
        
        characteristics = {}
        
        for cluster_id in np.unique(labels):
            if cluster_id == -1:  # Skip noise in DBSCAN
                continue
            
            cluster_mask = labels == cluster_id
            cluster_data = self.data[cluster_mask]
            cluster_features = self.scaled_features[cluster_mask]
            
            # Calculate mean features for this cluster
            cluster_means = np.mean(cluster_features, axis=0)
            overall_means = np.mean(self.scaled_features, axis=0)
            
            # Find most distinguishing features
            feature_diffs = np.abs(cluster_means - overall_means)
            top_feature_indices = np.argsort(feature_diffs)[::-1][:top_n_features]
            
            characteristics[int(cluster_id)] = {
                'size': int(np.sum(cluster_mask)),
                'percentage': float(np.sum(cluster_mask) / len(labels) * 100),
                'top_features': [
                    {
                        'name': self.feature_columns[idx],
                        'cluster_mean': float(cluster_means[idx]),
                        'overall_mean': float(overall_means[idx]),
                        'difference': float(feature_diffs[idx])
                    }
                    for idx in top_feature_indices
                ],
                'competition_types': cluster_data['competition_type'].value_counts().to_dict(),
                'race_categories': cluster_data['race_category'].value_counts().to_dict(),
                'example_races': cluster_data[['race_name', 'competition_name']].head(5).to_dict('records')
            }
        
        return characteristics