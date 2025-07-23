"""
Unsupervised clustering module for race kind classification.
Implements multiple clustering algorithms to identify distinct race kinds
based on gradient features from finishing time distributions.
"""

import sqlite3
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
import json
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class RaceKindClustering:
    """Main class for unsupervised clustering of race kinds."""
    
    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self.find_database()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.data = None
        self.features = None
        self.scaler = StandardScaler()
        self.clusters = {}
    
    def find_database(self):
        """Find the SQLite database file"""
        from pathlib import Path
        import os
        
        try:
            print("Trying to load database from environment variable...")
            from dotenv import load_dotenv
            print('running load_dotenv()')
            load_dotenv()
            print('loaded dotenv')
            db_path = os.getenv('DB_PATH')
            print(f"Using database path: {db_path}")
            if db_path and os.path.exists(db_path):
                return db_path
        except ImportError as e:
            print(f"Error loading dotenv: {e}")
        
        raise FileNotFoundError("Database not found")
        
    def load_stage_race_data(self, min_finishers: int = 40) -> pd.DataFrame:
        """Load stage race data with gradient features."""
        query = """
        SELECT 
            rfg.competition_id,
            rfg.competition_name,
            rfg.race_name,
            rfg.race_category,
            rfg.race_year,
            rfg.total_finishers,
            COALESCE(rfg.kurtosis_null_percentile, 0) as kurtosis_breakdown_point,
            COALESCE(rfg.variance_zero_percentile, 0) as variance_breakdown_point,
            rfg.nth_percentile_gap_5_slope,
            rfg.nth_percentile_gap_5_volatility,
            rfg.nth_percentile_gap_5_monotonicity,
            rfg.nth_percentile_gap_25_slope,
            rfg.nth_percentile_gap_25_volatility,
            rfg.nth_percentile_gap_25_monotonicity,
            rfg.nth_percentile_gap_50_slope,
            rfg.nth_percentile_gap_50_volatility,
            rfg.nth_percentile_gap_50_monotonicity,
            rfg.variance_absolute_slope,
            rfg.variance_absolute_volatility,
            rfg.variance_normalized_slope,
            rfg.variance_normalized_volatility,
            rfg.kurtosis_absolute_slope,
            rfg.kurtosis_absolute_volatility,
            rfg.kurtosis_normalized_slope,
            rfg.kurtosis_normalized_volatility,
            rfg.gini_coefficient_slope,
            rfg.gini_coefficient_volatility,
            rfg.clumpiness_score_slope,
            rfg.clumpiness_score_volatility,
            rfg.selection_metric_slope,
            rfg.selection_metric_volatility,
            rfg.biggest_group_metric_slope,
            rfg.biggest_group_metric_volatility,
            rfg.skewness_absolute_slope,
            rfg.skewness_absolute_volatility,
            rfg.skewness_normalized_slope,
            rfg.skewness_normalized_volatility,
            rf100.winning_time
        FROM race_feature_gradients rfg
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        WHERE rfg.competition_type = 'stage'
        AND rf100.winning_time > 5400  -- More than 90 minutes (filters out TTs)
        AND rfg.total_finishers >= ?
        """
        
        self.data = pd.read_sql_query(query, self.conn, params=(min_finishers,))
        print(f"Loaded {len(self.data)} stage races with gradient features")
        return self.data
    
    def select_top_features(self, feature_scores: Dict[str, float], n_features: int = 8) -> List[str]:
        """Select top N features based on separability scores."""
        # Based on the analysis report
        feature_ranking = {
            'kurtosis_breakdown_point': 2.6184,
            'nth_percentile_gap_5_slope': 2.4599,
            'nth_percentile_gap_5_volatility': 2.4599,
            'nth_percentile_gap_5_monotonicity': 2.4599,
            'nth_percentile_gap_25_slope': 1.7974,
            'nth_percentile_gap_25_volatility': 1.7974,
            'nth_percentile_gap_25_monotonicity': 1.7974,
            'variance_breakdown_point': 1.2936,
            'nth_percentile_gap_50_slope': 1.2680,
            'nth_percentile_gap_50_volatility': 1.2680,
            'nth_percentile_gap_50_monotonicity': 1.2680,
            'variance_absolute_slope': 1.2115,
            'variance_absolute_volatility': 1.2115,
            'kurtosis_absolute_slope': 1.1735,
            'kurtosis_absolute_volatility': 1.1735,
            'kurtosis_normalized_slope': 1.1735,
            'kurtosis_normalized_volatility': 1.1735,
            'variance_normalized_slope': 1.1266,
            'variance_normalized_volatility': 1.1266,
            'biggest_group_metric_slope': 0.9870,
            'biggest_group_metric_volatility': 0.9870
        }
        
        # Get available features from data
        available_features = [f for f in feature_ranking.keys() if f in self.data.columns]
        
        # Sort by score and select top N
        sorted_features = sorted(available_features, key=lambda x: feature_ranking.get(x, 0), reverse=True)
        selected = sorted_features[:n_features]
        
        print(f"Selected top {n_features} features: {selected}")
        return selected
    
    def prepare_features(self, feature_list: Optional[List[str]] = None) -> np.ndarray:
        """Prepare and scale features for clustering."""
        if feature_list is None:
            feature_list = self.select_top_features({}, n_features=8)
        
        self.feature_names = feature_list
        feature_data = self.data[feature_list].copy()
        
        # Handle missing values
        feature_data = feature_data.fillna(feature_data.median())
        
        # Scale features
        self.features = self.scaler.fit_transform(feature_data)
        
        print(f"Prepared {self.features.shape[1]} features for {self.features.shape[0]} races")
        return self.features
    
    def kmeans_clustering(self, n_clusters_range: range = range(3, 8)) -> Dict:
        """Perform K-means clustering with elbow method."""
        results = {
            'inertias': [],
            'silhouette_scores': [],
            'calinski_scores': [],
            'davies_bouldin_scores': [],
            'n_clusters': [],
            'best_model': None,
            'best_n_clusters': None,
            'best_silhouette': -1
        }
        
        for n_clusters in n_clusters_range:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(self.features)
            
            # Calculate metrics
            inertia = kmeans.inertia_
            silhouette = silhouette_score(self.features, labels)
            calinski = calinski_harabasz_score(self.features, labels)
            davies_bouldin = davies_bouldin_score(self.features, labels)
            
            results['inertias'].append(inertia)
            results['silhouette_scores'].append(silhouette)
            results['calinski_scores'].append(calinski)
            results['davies_bouldin_scores'].append(davies_bouldin)
            results['n_clusters'].append(n_clusters)
            
            # Track best model by silhouette score
            if silhouette > results['best_silhouette']:
                results['best_silhouette'] = silhouette
                results['best_n_clusters'] = n_clusters
                results['best_model'] = kmeans
                self.clusters['kmeans'] = labels
        
        print(f"K-means: Best n_clusters={results['best_n_clusters']} with silhouette={results['best_silhouette']:.3f}")
        return results
    
    def dbscan_clustering(self, eps_range: np.ndarray = np.arange(0.5, 3.0, 0.1), 
                         min_samples_range: range = range(5, 20, 5)) -> Dict:
        """Perform DBSCAN clustering with parameter search."""
        results = {
            'parameter_grid': [],
            'best_params': None,
            'best_silhouette': -1,
            'best_model': None
        }
        
        for eps in eps_range:
            for min_samples in min_samples_range:
                dbscan = DBSCAN(eps=eps, min_samples=min_samples)
                labels = dbscan.fit_predict(self.features)
                
                # Skip if all points are noise or only one cluster
                n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
                if n_clusters < 2:
                    continue
                
                # Calculate silhouette score (excluding noise points)
                mask = labels != -1
                if np.sum(mask) > 0:
                    silhouette = silhouette_score(self.features[mask], labels[mask])
                    
                    param_result = {
                        'eps': eps,
                        'min_samples': min_samples,
                        'n_clusters': n_clusters,
                        'n_noise': np.sum(labels == -1),
                        'silhouette': silhouette
                    }
                    results['parameter_grid'].append(param_result)
                    
                    if silhouette > results['best_silhouette']:
                        results['best_silhouette'] = silhouette
                        results['best_params'] = {'eps': eps, 'min_samples': min_samples}
                        results['best_model'] = dbscan
                        self.clusters['dbscan'] = labels
        
        if results['best_params']:
            print(f"DBSCAN: Best params={results['best_params']} with silhouette={results['best_silhouette']:.3f}")
        else:
            print("DBSCAN: No valid clustering found")
        
        return results
    
    def hierarchical_clustering(self, n_clusters_range: range = range(3, 8)) -> Dict:
        """Perform hierarchical clustering."""
        results = {
            'silhouette_scores': [],
            'n_clusters': [],
            'best_model': None,
            'best_n_clusters': None,
            'best_silhouette': -1
        }
        
        for n_clusters in n_clusters_range:
            hierarchical = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
            labels = hierarchical.fit_predict(self.features)
            
            silhouette = silhouette_score(self.features, labels)
            
            results['silhouette_scores'].append(silhouette)
            results['n_clusters'].append(n_clusters)
            
            if silhouette > results['best_silhouette']:
                results['best_silhouette'] = silhouette
                results['best_n_clusters'] = n_clusters
                results['best_model'] = hierarchical
                self.clusters['hierarchical'] = labels
        
        print(f"Hierarchical: Best n_clusters={results['best_n_clusters']} with silhouette={results['best_silhouette']:.3f}")
        return results
    
    def get_cluster_profiles(self, method: str = 'kmeans') -> pd.DataFrame:
        """Generate profiles for each cluster."""
        if method not in self.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clusters[method]
        
        # Add cluster labels to data
        cluster_data = self.data.copy()
        cluster_data['cluster'] = labels
        
        # Calculate cluster profiles
        profiles = []
        
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:  # Skip noise for DBSCAN
                continue
                
            cluster_mask = labels == cluster_id
            cluster_races = cluster_data[cluster_mask]
            
            profile = {
                'cluster_id': cluster_id,
                'n_races': len(cluster_races),
                'avg_finishers': cluster_races['total_finishers'].mean(),
                'categories': cluster_races['race_category'].value_counts().to_dict(),
                'years': f"{cluster_races['race_year'].min()}-{cluster_races['race_year'].max()}"
            }
            
            # Add feature averages
            for feature in self.feature_names:
                profile[f'avg_{feature}'] = cluster_races[feature].mean()
            
            # Sample races
            sample_races = cluster_races.nsmallest(5, 'competition_id')[
                ['competition_name', 'race_name', 'race_year']
            ].to_dict('records')
            profile['sample_races'] = sample_races
            
            profiles.append(profile)
        
        return pd.DataFrame(profiles)
    
    def save_results(self, output_dir: str = 'race_kinds/race_kind_finding'):
        """Save clustering results and profiles."""
        results = {
            'feature_names': self.feature_names,
            'n_races': len(self.data),
            'clustering_results': {}
        }
        
        # Save cluster assignments
        for method, labels in self.clusters.items():
            cluster_data = self.data[['competition_id', 'competition_name', 'race_name']].copy()
            cluster_data['cluster'] = labels
            
            # Save to CSV
            cluster_data.to_csv(f'{output_dir}/{method}_clusters.csv', index=False)
            
            # Get profiles
            profiles = self.get_cluster_profiles(method)
            profiles.to_json(f'{output_dir}/{method}_profiles.json', orient='records', indent=2)
            
            results['clustering_results'][method] = {
                'n_clusters': len(set(labels)) - (1 if -1 in labels else 0),
                'cluster_sizes': pd.Series(labels).value_counts().to_dict()
            }
        
        # Save summary
        with open(f'{output_dir}/clustering_summary.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"Results saved to {output_dir}/")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Run the clustering pipeline."""
    # Initialize clustering (will auto-find database)
    clustering = RaceKindClustering()
    
    # Load data
    clustering.load_stage_race_data(min_finishers=40)
    
    # Prepare features (top 5)
    clustering.prepare_features()
    
    # Run clustering algorithms
    print("\n--- Running K-means clustering ---")
    kmeans_results = clustering.kmeans_clustering(range(3, 8))
    
    print("\n--- Running DBSCAN clustering ---")
    dbscan_results = clustering.dbscan_clustering(
        eps_range=np.arange(0.5, 2.0, 0.1),
        min_samples_range=range(10, 30, 5)
    )
    
    print("\n--- Running Hierarchical clustering ---")
    hierarchical_results = clustering.hierarchical_clustering(range(3, 8))
    
    # Save results
    clustering.save_results()
    
    # Close connection
    clustering.close()
    
    print("\nClustering complete!")


if __name__ == "__main__":
    main()