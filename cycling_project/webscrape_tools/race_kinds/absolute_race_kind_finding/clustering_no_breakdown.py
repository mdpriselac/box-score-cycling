"""
Clustering module for absolute race kind classification - NO BREAKDOWN subset.
Implements K-means clustering for multiple cluster counts (3-8) across different percentile levels.
"""

import sqlite3
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
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


class AbsoluteRaceKindClusteringNoBreakdown:
    """Clustering for races without kurtosis breakdown using absolute features."""
    
    def __init__(self, db_path: str = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self.find_database()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.percentiles = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        self.cluster_range = range(3, 9)  # 3 to 8 clusters
        self.clustering_results = {}
        self.evaluation_metrics = {}
        self.feature_importances = {}
        self.scalers = {}
        
    def find_database(self):
        """Find the SQLite database file."""
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
    
    def load_selected_features(self, percentile: int) -> List[str]:
        """Load the features selected for this percentile."""
        feature_file = Path(__file__).parent / "feature_selection_results" / "selected_features_no_breakdown.json"
        
        with open(feature_file, 'r') as f:
            data = json.load(f)
        
        return data['feature_selections'].get(str(percentile), [])
    
    def load_race_data(self, percentile: int, min_finishers: int = 40) -> pd.DataFrame:
        """Load race data with selected features for a specific percentile."""
        features = self.load_selected_features(percentile)
        
        if not features:
            print(f"No features selected for percentile {percentile}")
            return pd.DataFrame()
        
        table_name = f"race_features_{percentile}"
        
        # Build column list with proper quoting
        select_cols = ['rf.competition_id', 'rf.competition_name', 'rf.race_name', 
                      'rf.race_category', 'rf.race_year', 'rf.total_finishers',
                      'rf100.winning_time']
        
        for feature in features:
            if feature[0].isdigit() or 'percentile_gap' in feature:
                select_cols.append(f'rf."{feature}"')
            else:
                select_cols.append(f'rf.{feature}')
        
        columns = ', '.join(select_cols)
        
        # Query for races without kurtosis breakdown
        query = f"""
        WITH no_breakdown_races AS (
            SELECT DISTINCT rf100.competition_id
            FROM race_features_100 rf100
            WHERE NOT EXISTS (
                SELECT 1 FROM race_features_10 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
            ) AND NOT EXISTS (
                SELECT 1 FROM race_features_15 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
            ) AND NOT EXISTS (
                SELECT 1 FROM race_features_20 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
            ) AND NOT EXISTS (
                SELECT 1 FROM race_features_25 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
            )
        )
        SELECT {columns}
        FROM {table_name} rf
        INNER JOIN race_features_100 rf100 ON rf.competition_id = rf100.competition_id
        WHERE rf.competition_id IN (SELECT competition_id FROM no_breakdown_races)
        AND rf.total_finishers >= {min_finishers}
        AND rf100.winning_time >= 5400
        AND rf100.winning_time <= 28800
        """
        
        df = pd.read_sql_query(query, self.conn)
        
        return df
    
    def prepare_features(self, df: pd.DataFrame, percentile: int) -> Tuple[pd.DataFrame, np.ndarray]:
        """Prepare and scale features for clustering."""
        features = self.load_selected_features(percentile)
        
        # Extract feature columns - only those that exist in the dataframe
        available_features = [f for f in features if f in df.columns]
        if not available_features:
            print(f"No features available in data for percentile {percentile}")
            return df, np.array([])
        
        feature_data = df[available_features].copy()
        
        # For no-breakdown races, we should have complete data
        # Check for any unexpected NaN values
        if feature_data.isna().any().any():
            print(f"Warning: Unexpected NaNs found. Dropping affected rows.")
            feature_data = feature_data.dropna()
            df = df.loc[feature_data.index]
        
        # Ensure we have enough data for clustering
        if len(feature_data) < 10:
            print(f"Warning: Only {len(feature_data)} races available for clustering at percentile {percentile}")
            return df, np.array([])
        
        # Standardize features
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(feature_data)
        
        # Store scaler for later use
        self.scalers[percentile] = scaler
        
        print(f"  Prepared {len(feature_data)} races with {len(available_features)} features")
        
        return df, scaled_features
    
    def cluster_percentile(self, percentile: int) -> Dict:
        """Perform clustering for a specific percentile across different K values."""
        print(f"\nClustering percentile {percentile}...")
        
        # Load data
        df = self.load_race_data(percentile)
        if df.empty:
            print(f"No data available for percentile {percentile}")
            return {}
        
        print(f"Loaded {len(df)} races for clustering")
        
        # Prepare features
        df, scaled_features = self.prepare_features(df, percentile)
        
        if scaled_features.size == 0:
            print(f"No usable features for percentile {percentile}")
            return {}
        
        results = {}
        
        for n_clusters in self.cluster_range:
            print(f"  Testing {n_clusters} clusters...")
            
            # Perform K-means clustering
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(scaled_features)
            
            # Calculate evaluation metrics
            silhouette = silhouette_score(scaled_features, labels)
            calinski = calinski_harabasz_score(scaled_features, labels)
            davies_bouldin = davies_bouldin_score(scaled_features, labels)
            
            # Calculate feature importances (based on cluster centers)
            feature_names = self.load_selected_features(percentile)
            # Only use features that were actually used in clustering
            actual_features = [f for f in feature_names if f in df.columns]
            feature_importances = self.calculate_feature_importances(
                kmeans.cluster_centers_, actual_features
            )
            
            # Store results
            results[n_clusters] = {
                'labels': labels.tolist(),
                'cluster_centers': kmeans.cluster_centers_.tolist(),
                'metrics': {
                    'silhouette_score': silhouette,
                    'calinski_harabasz_score': calinski,
                    'davies_bouldin_score': davies_bouldin,
                    'inertia': kmeans.inertia_
                },
                'feature_importances': feature_importances,
                'competition_ids': df['competition_id'].tolist(),
                'competition_names': df['competition_name'].tolist(),
                'race_names': df['race_name'].tolist()
            }
            
            print(f"    Silhouette: {silhouette:.3f}, Calinski-Harabasz: {calinski:.1f}, "
                  f"Davies-Bouldin: {davies_bouldin:.3f}")
        
        return results
    
    def calculate_feature_importances(self, cluster_centers: np.ndarray, 
                                     feature_names: List[str]) -> Dict:
        """Calculate feature importances based on cluster center variations."""
        # Calculate overall variance of each feature across cluster centers
        variances = np.var(cluster_centers, axis=0)
        
        # Normalize to get relative importances for overall
        total_variance = np.sum(variances)
        if total_variance > 0:
            overall_importances_array = variances / total_variance
        else:
            overall_importances_array = np.ones(len(feature_names)) / len(feature_names)
        
        # Create importance dictionary for each cluster
        cluster_importances = {}
        
        # Calculate cluster-specific importances based on absolute values of cluster centers
        # normalized relative to the maximum center value for each cluster
        for i, center in enumerate(cluster_centers):
            # Use absolute values of cluster center as basis for importance
            abs_center = np.abs(center)
            
            # Normalize to create importance weights for this specific cluster
            total_abs = np.sum(abs_center)
            if total_abs > 0:
                cluster_specific_importances = abs_center / total_abs
            else:
                cluster_specific_importances = np.ones(len(feature_names)) / len(feature_names)
            
            cluster_importances[f'cluster_{i}'] = {
                'center_values': {name: float(val) for name, val in zip(feature_names, center)},
                'feature_importances': {name: float(imp) for name, imp in zip(feature_names, cluster_specific_importances)}
            }
        
        # Overall importances based on variance across clusters
        overall_importances = {name: float(imp) for name, imp in zip(feature_names, overall_importances_array)}
        
        return {
            'by_cluster': cluster_importances,
            'overall': overall_importances
        }
    
    def run_all_clustering(self):
        """Run clustering for all percentiles."""
        for percentile in self.percentiles:
            self.clustering_results[percentile] = self.cluster_percentile(percentile)
        
        print("\n" + "="*50)
        print("Clustering complete for all percentiles")
    
    def save_results(self):
        """Save clustering results to files."""
        output_dir = Path(__file__).parent / "clustering_results_no_breakdown"
        output_dir.mkdir(exist_ok=True)
        
        # Save main results
        results_file = output_dir / "absolute_clustering_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.clustering_results, f, indent=2)
        
        print(f"\nResults saved to {results_file}")
        
        # Save a summary
        summary = self.create_summary()
        summary_file = output_dir / "clustering_summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Summary saved to {summary_file}")
        
        # Save best clusters for each percentile (based on silhouette score)
        for percentile, results in self.clustering_results.items():
            if not results:
                continue
            
            # Find best K based on silhouette score
            best_k = max(results.keys(), 
                        key=lambda k: results[k]['metrics']['silhouette_score'])
            
            # Save cluster assignments
            cluster_df = pd.DataFrame({
                'competition_id': results[best_k]['competition_ids'],
                'competition_name': results[best_k]['competition_names'],
                'race_name': results[best_k]['race_names'],
                'cluster': results[best_k]['labels']
            })
            
            cluster_file = output_dir / f"percentile_{percentile}_best_clusters.csv"
            cluster_df.to_csv(cluster_file, index=False)
            print(f"Best clusters for percentile {percentile} saved to {cluster_file}")
    
    def create_summary(self) -> Dict:
        """Create a summary of clustering results."""
        summary = {
            'percentiles_analyzed': self.percentiles,
            'cluster_range': list(self.cluster_range),
            'total_races_by_percentile': {},
            'best_k_by_percentile': {},
            'metrics_summary': {}
        }
        
        for percentile, results in self.clustering_results.items():
            if not results:
                continue
            
            # Get total races
            first_k = list(results.keys())[0]
            summary['total_races_by_percentile'][percentile] = len(results[first_k]['competition_ids'])
            
            # Find best K based on different metrics
            best_silhouette = max(results.keys(), 
                                key=lambda k: results[k]['metrics']['silhouette_score'])
            best_calinski = max(results.keys(),
                              key=lambda k: results[k]['metrics']['calinski_harabasz_score'])
            best_davies = min(results.keys(),
                            key=lambda k: results[k]['metrics']['davies_bouldin_score'])
            
            summary['best_k_by_percentile'][percentile] = {
                'by_silhouette': best_silhouette,
                'by_calinski': best_calinski,
                'by_davies_bouldin': best_davies
            }
            
            # Metrics summary
            summary['metrics_summary'][percentile] = {}
            for k, res in results.items():
                summary['metrics_summary'][percentile][k] = res['metrics']
        
        return summary
    
    def analyze_feature_importance_trends(self) -> Dict:
        """Analyze how feature importances change across percentiles."""
        importance_trends = {}
        
        for percentile, results in self.clustering_results.items():
            if not results:
                continue
            
            # Use best K based on silhouette
            best_k = max(results.keys(),
                        key=lambda k: results[k]['metrics']['silhouette_score'])
            
            importances = results[best_k]['feature_importances']['overall']
            
            for feature, importance in importances.items():
                if feature not in importance_trends:
                    importance_trends[feature] = {}
                importance_trends[feature][percentile] = importance
        
        return importance_trends


def main():
    """Run absolute clustering for races without breakdown."""
    print("="*50)
    print("Absolute Race Kind Clustering - NO BREAKDOWN")
    print("="*50)
    
    clusterer = AbsoluteRaceKindClusteringNoBreakdown()
    
    # Run clustering for all percentiles
    clusterer.run_all_clustering()
    
    # Save results
    clusterer.save_results()
    
    # Analyze feature importance trends
    trends = clusterer.analyze_feature_importance_trends()
    
    print("\n" + "="*50)
    print("Feature Importance Trends Across Percentiles:")
    print("="*50)
    
    for feature, percentile_importances in trends.items():
        print(f"\n{feature}:")
        for percentile, importance in sorted(percentile_importances.items()):
            print(f"  Percentile {percentile}: {importance:.3f}")


if __name__ == "__main__":
    main()