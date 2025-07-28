"""
Unsupervised clustering module for race kind classification using absolute feature values - NO BREAKDOWN subset.
Implements multiple clustering algorithms to identify distinct race kinds
for stages WITHOUT breakdowns, using absolute feature values from specific percentile levels.
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

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


class RaceKindClusteringAbsoluteNoBreakdown:
    """Main class for unsupervised clustering of race kinds using absolute values - no breakdown subset."""
    
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
        self.subset_name = "absolute_no_breakdown"
        self.optimal_percentiles = [50, 55, 45]  # From analysis
        self.top_features = []  # Will be populated from analysis
    
    def find_database(self):
        """Find the SQLite database file"""
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.exists(db_path):
                return db_path
        
        # Go up to find db
        db_path = Path(__file__).parent.parent.parent.parent / "database" / "database" / "cycling_races.db"
        if db_path.exists():
            return str(db_path)
        
        raise FileNotFoundError("Database not found")
    
    def load_features_from_analysis(self):
        """Load the features that showed separability potential from the analysis."""
        analysis_path = Path(__file__).parent.parent / "absolute_stage_kind_support_analysis" / "absolute_no_breakdown_analysis.json"
        
        with open(analysis_path, 'r') as f:
            analysis = json.load(f)
        
        # Get top features based on tier system
        top_combinations = []
        if 'top_combinations' in analysis:
            # Direct access to top_combinations
            for combo in analysis['top_combinations']:
                # Focus on highest performing features (score > 10)
                if combo['score'] > 10:
                    # Clean feature name - remove both outer quotes and escaped inner quotes
                    feature_name = combo['feature'].strip()
                    if feature_name.startswith('"') and feature_name.endswith('"'):
                        feature_name = feature_name[1:-1]  # Remove quotes
                    top_combinations.append({
                        'feature': feature_name,
                        'percentile': combo['percentile'],
                        'score': combo['score']
                    })
        else:
            # Alternative: build from feature_results with high scores
            all_combinations = []
            for feature_name, feature_data in analysis.get('feature_results', {}).items():
                for percentile_data in feature_data:
                    if 'separability_score' in percentile_data:
                        all_combinations.append({
                            'feature': feature_name,
                            'percentile': percentile_data['percentile'],
                            'score': percentile_data['separability_score']
                        })
            
            # Sort by score and take top combinations
            all_combinations.sort(key=lambda x: x['score'], reverse=True)
            for combo in all_combinations:
                if combo['score'] > 10:
                    top_combinations.append(combo)
        
        print(f"Loaded {len(top_combinations)} top feature-percentile combinations from analysis")
        return top_combinations
    
    def get_kurtosis_breakdown_points(self) -> Dict[int, Optional[int]]:
        """Get breakdown points for all competitions."""
        # Import the utility function
        import sys
        sys.path.append(str(Path(__file__).parent.parent / "absolute_stage_kind_support_analysis"))
        from find_kurtosis_breakdown_point import get_all_breakdown_points
        
        breakdown_points = get_all_breakdown_points(self.conn)
        return breakdown_points
        
    def load_stage_race_data(self, min_finishers: int = 40) -> pd.DataFrame:
        """Load stage race data with absolute features - NO BREAKDOWN subset."""
        # First get breakdown points
        breakdown_points = self.get_kurtosis_breakdown_points()
        
        # Get the feature combinations from analysis
        feature_combinations = self.load_features_from_analysis()
        
        # Build queries for each percentile table we need
        percentiles_needed = set()
        features_by_percentile = {}
        
        for combo in feature_combinations:
            percentile = combo['percentile']
            feature = combo['feature']
            percentiles_needed.add(percentile)
            if percentile not in features_by_percentile:
                features_by_percentile[percentile] = []
            features_by_percentile[percentile].append(feature)
        
        # Base query to get competitions without breakdown
        base_query = """
        SELECT DISTINCT rf100.competition_id,
               rf100.competition_name,
               rf100.race_name,
               rf100.race_category,
               rf100.race_year,
               rf100.total_finishers,
               rf100.winning_time
        FROM race_features_100 rf100
        WHERE rf100.competition_type = 'stage'
        AND rf100.winning_time > 5400  -- More than 90 minutes
        AND rf100.winning_time <= 28800  -- Less than 8 hours
        AND rf100.total_finishers >= ?
        """
        
        # Execute base query
        base_data = pd.read_sql_query(base_query, self.conn, params=(min_finishers,))
        
        # Filter for competitions without breakdown
        no_breakdown_ids = [comp_id for comp_id, bp in breakdown_points.items() if bp is None]
        base_data = base_data[base_data['competition_id'].isin(no_breakdown_ids)]
        
        print(f"Found {len(base_data)} competitions without kurtosis breakdown")
        
        # Now get features from each percentile table
        for percentile in sorted(percentiles_needed):
            table_name = f"race_features_{percentile}"
            features_to_get = features_by_percentile[percentile]
            
            # Build feature query
            feature_cols = []
            for feature in features_to_get:
                # Clean the feature name of quotes first
                clean_feature = feature.strip().strip('"').strip("'")
                
                # Create safe alias by replacing special characters and prefixing with 'f_'
                safe_alias = 'f_' + clean_feature.replace('"', '').replace(' ', '_').replace("'", '')
                
                # SQLite column references - use cleaned feature name
                if clean_feature[0].isdigit() or any(c in clean_feature for c in [' ', '"', '(', ')', '-']):
                    feature_cols.append(f'"{clean_feature}" as {safe_alias}_p{percentile}')
                else:
                    feature_cols.append(f'{clean_feature} as {safe_alias}_p{percentile}')
            
            feature_query = f"""
            SELECT competition_id, {', '.join(feature_cols)}
            FROM {table_name}
            WHERE competition_id IN ({','.join(str(id) for id in base_data['competition_id'])})
            """
            
            feature_data = pd.read_sql_query(feature_query, self.conn)
            base_data = base_data.merge(feature_data, on='competition_id', how='left')
        
        self.data = base_data
        print(f"Loaded {len(self.data)} stage races without breakdowns with {len(self.data.columns)} columns")
        
        # Store feature combinations for later use
        self.feature_combinations = feature_combinations
        
        return self.data
    
    def prepare_features(self, use_top_n: Optional[int] = None) -> np.ndarray:
        """Prepare features for clustering based on separability analysis."""
        if self.data is None:
            raise ValueError("Load data first using load_stage_race_data()")
        
        # Get feature columns from data based on loaded combinations
        feature_columns = []
        
        if use_top_n is not None:
            # Use only top N feature combinations
            for i, combo in enumerate(self.feature_combinations):
                if i < use_top_n:
                    # Create safe column name - must match what we created in SQL
                    safe_feature = 'f_' + combo['feature'].replace('"', '').replace(' ', '_').replace("'", '')
                    col_name = f"{safe_feature}_p{combo['percentile']}"
                    if col_name in self.data.columns:
                        feature_columns.append(col_name)
        else:
            # Use all feature combinations
            for combo in self.feature_combinations:
                # Create safe column name - must match what we created in SQL
                safe_feature = 'f_' + combo['feature'].replace('"', '').replace(' ', '_').replace("'", '')
                col_name = f"{safe_feature}_p{combo['percentile']}"
                if col_name in self.data.columns:
                    feature_columns.append(col_name)
        
        print(f"Using {len(feature_columns)} feature columns for clustering")
        self.feature_names = feature_columns
        
        # Extract features and handle missing values
        feature_data = self.data[feature_columns].fillna(0)
        
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
            
            # Add feature statistics for top features
            for feature in self.feature_names[:10]:  # Top 10 features
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
            'feature_combinations': self.feature_combinations,
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
    """Run the clustering pipeline for no-breakdown races using absolute values."""
    # Initialize clustering
    clustering = RaceKindClusteringAbsoluteNoBreakdown()
    
    # Load data
    clustering.load_stage_race_data(min_finishers=40)
    
    # Prepare features (use top 10 feature-percentile combinations)
    clustering.prepare_features(use_top_n=10)
    
    # Run clustering algorithms
    print("\n--- Running K-means clustering (ABSOLUTE NO BREAKDOWN) ---")
    kmeans_results = clustering.kmeans_clustering(range(3, 8))
    
    print("\n--- Running DBSCAN clustering (ABSOLUTE NO BREAKDOWN) ---")
    dbscan_results = clustering.dbscan_clustering(
        eps_range=np.arange(0.5, 2.0, 0.1),
        min_samples_range=range(10, 30, 5)
    )
    
    print("\n--- Running Hierarchical clustering (ABSOLUTE NO BREAKDOWN) ---")
    hierarchical_results = clustering.hierarchical_clustering(range(3, 8))
    
    # Save results
    clustering.save_results()
    
    # Close connection
    clustering.close()
    
    print("\nClustering complete for ABSOLUTE NO BREAKDOWN subset!")


if __name__ == "__main__":
    main()