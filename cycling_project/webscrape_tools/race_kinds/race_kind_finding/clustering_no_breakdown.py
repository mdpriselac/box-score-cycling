"""
Unsupervised clustering module for race kind classification - NO BREAKDOWN subset.
Implements multiple clustering algorithms to identify distinct race kinds
for stages WITHOUT breakdowns, using features identified from separability analysis.
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
from pathlib import Path
import os
import warnings
warnings.filterwarnings('ignore')

from cycling_project.engineering_tools.imputation import smart_fillna

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


class RaceKindClusteringNoBreakdown:
    """Main class for unsupervised clustering of race kinds - no breakdown subset."""
    
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
        self.feature_names = []
        self.subset_name = "no_breakdown"
    
    def find_database(self):
        """Find the SQLite database file"""
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.exists(db_path):
                return db_path
        
        # Go up to find db
        db_path = Path(__file__).parent.parent.parent / "database" / "database" / "cycling_races.db"
        if db_path.exists():
            return str(db_path)
        
        raise FileNotFoundError("Database not found")
    
    def load_features_from_analysis(self):
        """Load the features that showed separability potential from the analysis."""
        analysis_path = Path(__file__).parent.parent / "stage_kind_support_analysis" / "stage_no_breakdown_analysis.json"
        
        with open(analysis_path, 'r') as f:
            analysis = json.load(f)
        
        # Get all features that showed separability potential (score > 0)
        feature_ranking = analysis['comparative_analysis']['feature_ranking']
        selected_features = []
        
        for feature_info in feature_ranking:
            if feature_info['score'] > 0:
                selected_features.append(feature_info['feature'])
        
        print(f"Loaded {len(selected_features)} features with separability potential from analysis")
        return selected_features
        
    def load_stage_race_data(self, min_finishers: int = 40) -> pd.DataFrame:
        """Load stage race data with gradient features - NO BREAKDOWN subset."""
        # First get the feature list
        feature_list = self.load_features_from_analysis()
        
        # Build the SELECT clause dynamically based on features
        select_columns = [
            "rfg.competition_id",
            "rfg.competition_name", 
            "rfg.race_name",
            "rfg.race_category",
            "rfg.race_year",
            "rfg.total_finishers",
            "COALESCE(rfg.kurtosis_null_percentile, 0) as kurtosis_breakdown_point",
            "COALESCE(rfg.variance_zero_percentile, 0) as variance_breakdown_point",
            "rf100.winning_time"
        ]
        
        # Add gradient feature columns dynamically
        gradient_columns = []
        for feature in feature_list:
            # Skip breakdown features as they're already included
            if feature not in ['kurtosis_breakdown_point', 'variance_breakdown_point']:
                gradient_columns.append(f"rfg.{feature}_slope")
                gradient_columns.append(f"rfg.{feature}_volatility")
                gradient_columns.append(f"rfg.{feature}_monotonicity")
                gradient_columns.append(f"rfg.{feature}_directional_changes")
        
        select_columns.extend(gradient_columns)
        
        query = f"""
        SELECT 
            {', '.join(select_columns)}
        FROM race_feature_gradients rfg
        JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
        WHERE rfg.competition_type = 'stage'
        AND rf100.winning_time > 5400  -- More than 90 minutes (filters out TTs)
        AND rf100.winning_time < 28800  -- Less than 8 hours (filters out outliers)
        AND rfg.total_finishers >= ?
        AND rfg.variance_normalized_values IS NOT NULL  -- Has gradient data
        AND COALESCE(rfg.kurtosis_null_percentile, 0) = 0  -- No kurtosis breakdown
        AND COALESCE(rfg.variance_zero_percentile, 0) = 0  -- No variance breakdown
        ORDER BY rfg.total_finishers DESC
        """
        
        self.data = pd.read_sql_query(query, self.conn, params=(min_finishers,))
        print(f"Loaded {len(self.data)} stage races without breakdowns (min_finishers={min_finishers})")
        
        # Store feature list for later use
        self.available_features = feature_list
        
        return self.data
    
    def prepare_features(self, use_top_n: Optional[int] = None) -> np.ndarray:
        """Prepare features for clustering based on separability analysis."""
        if self.data is None:
            raise ValueError("Load data first using load_stage_race_data()")
        
        # Get gradient feature columns from data
        feature_columns = []
        for col in self.data.columns:
            if col.endswith('_slope') or col.endswith('_volatility') or col.endswith('_monotonicity') or col.endswith('_directional_changes'):
                if not pd.isna(self.data[col]).all():  # Skip if all NaN
                    feature_columns.append(col)
        
        # If use_top_n specified, limit to top N features by score
        if use_top_n is not None:
            # Load analysis to get feature ranking
            analysis_path = Path(__file__).parent.parent / "stage_kind_support_analysis" / "stage_no_breakdown_analysis.json"
            with open(analysis_path, 'r') as f:
                analysis = json.load(f)
            
            # Get top N features
            top_features = []
            for i, feature_info in enumerate(analysis['comparative_analysis']['feature_ranking']):
                if i < use_top_n:
                    feature_name = feature_info['feature']
                    # Add all related columns (slope, volatility, monotonicity, directional_changes)
                    for suffix in ['_slope', '_volatility', '_monotonicity', '_directional_changes']:
                        col_name = f"{feature_name}{suffix}"
                        if col_name in feature_columns:
                            top_features.append(col_name)
            
            feature_columns = top_features
        
        print(f"Using {len(feature_columns)} feature columns for clustering")
        self.feature_names = feature_columns

        # Extract features and handle missing values with type-aware imputation
        feature_data = smart_fillna(self.data[feature_columns], feature_columns=feature_columns)

        # Standardize features
        self.features = self.scaler.fit_transform(feature_data)
        
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
                'avg_winning_time': cluster_races['winning_time'].mean() / 3600,  # Convert to hours
                'categories': cluster_races['race_category'].value_counts().to_dict(),
                'top_competitions': cluster_races['competition_name'].value_counts().head(5).to_dict(),
                'year_range': f"{cluster_races['race_year'].min()}-{cluster_races['race_year'].max()}"
            }
            
            # Add feature statistics
            for feature in self.feature_names:
                if feature in cluster_data.columns:
                    profile[f"{feature}_mean"] = cluster_races[feature].mean()
                    profile[f"{feature}_std"] = cluster_races[feature].std()
            
            profiles.append(profile)
        
        return pd.DataFrame(profiles)
    
    def save_results(self, output_dir: str = None):
        """Save clustering results to files."""
        if output_dir is None:
            output_dir = Path(__file__).parent / f'clustering_results_{self.subset_name}'
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Save metadata
        metadata = {
            'subset': self.subset_name,
            'feature_names': self.feature_names,
            'n_races': len(self.data),
            'n_features': len(self.feature_names),
            'features_from_analysis': self.available_features,
            'clustering_results': {}
        }
        
        # Save cluster assignments and profiles for each method
        for method, labels in self.clusters.items():
            # Save cluster assignments
            cluster_data = self.data[['competition_id', 'competition_name', 'race_name']].copy()
            cluster_data['cluster'] = labels
            cluster_data.to_csv(output_dir / f'{method}_clusters.csv', index=False)
            
            # Get and save profiles
            profiles = self.get_cluster_profiles(method)
            profiles.to_json(output_dir / f'{method}_profiles.json', orient='records', indent=2)
            
            # Add to metadata
            metadata['clustering_results'][method] = {
                'n_clusters': len(set(labels)) - (1 if -1 in labels else 0),
                'cluster_sizes': pd.Series(labels).value_counts().to_dict()
            }
        
        # Save metadata
        with open(output_dir / 'clustering_summary.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Results saved to {output_dir}/")
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Run the clustering pipeline for no-breakdown races."""
    # Initialize clustering
    clustering = RaceKindClusteringNoBreakdown()
    
    # Load data
    clustering.load_stage_race_data(min_finishers=40)
    
    # Prepare features (use all features with separability potential)
    clustering.prepare_features()
    
    # Run clustering algorithms
    print("\n--- Running K-means clustering (NO BREAKDOWN) ---")
    kmeans_results = clustering.kmeans_clustering(range(3, 8))
    
    print("\n--- Running DBSCAN clustering (NO BREAKDOWN) ---")
    dbscan_results = clustering.dbscan_clustering(
        eps_range=np.arange(0.5, 2.0, 0.1),
        min_samples_range=range(10, 30, 5)
    )
    
    print("\n--- Running Hierarchical clustering (NO BREAKDOWN) ---")
    hierarchical_results = clustering.hierarchical_clustering(range(3, 8))
    
    # Save results
    clustering.save_results()
    
    # Close connection
    clustering.close()
    
    print("\nClustering complete for NO BREAKDOWN subset!")


if __name__ == "__main__":
    main()