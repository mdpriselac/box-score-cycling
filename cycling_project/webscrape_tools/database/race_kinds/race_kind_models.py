"""
Race Kind Model Persistence and Feature Extraction

This module handles:
1. Saving and loading trained clustering models
2. Calculating race kind features (cluster membership, distances, density, boundary distance)
3. Creating and managing race_kind_features tables
4. Applying saved models to new races
"""

import os
import pickle
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.cluster import KMeans, AgglomerativeClustering, DBSCAN
from sklearn.mixture import GaussianMixture
from scipy.spatial.distance import cdist


class PredictableAgglomerativeClustering:
    """Wrapper for AgglomerativeClustering that adds predict functionality."""
    
    def __init__(self, n_clusters=4, **kwargs):
        self.n_clusters = n_clusters
        self.agg = AgglomerativeClustering(n_clusters=n_clusters, **kwargs)
        self.cluster_centers_ = None
        
    def fit(self, X):
        """Fit the clustering and calculate cluster centers."""
        self.labels_ = self.agg.fit_predict(X)
        
        # Calculate and store cluster centers
        self.cluster_centers_ = np.array([
            X[self.labels_ == i].mean(axis=0) 
            for i in range(self.n_clusters)
        ])
        return self
    
    def predict(self, X):
        """Assign new samples to nearest cluster center."""
        distances = cdist(X, self.cluster_centers_)
        return np.argmin(distances, axis=1)
    
    def transform(self, X):
        """Get distances to all cluster centers."""
        return cdist(X, self.cluster_centers_)
    
    def fit_predict(self, X):
        """Fit and return labels."""
        self.fit(X)
        return self.labels_


class RaceKindModelManager:
    """Manages race kind models and feature extraction."""
    
    def __init__(self, db_path: str, model_dir: str = "database/race_kinds/models"):
        """
        Initialize the model manager.
        
        Args:
            db_path: Path to the SQLite database
            model_dir: Directory to store saved models
        """
        self.db_path = db_path
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
    
    def save_model(self, 
                   model: Union[KMeans, PredictableAgglomerativeClustering, DBSCAN, GaussianMixture],
                   algorithm: str,
                   percentile: int,
                   feature_columns: List[str],
                   scaler: Union[StandardScaler, RobustScaler],
                   metadata: Dict = None) -> str:
        """
        Save a trained clustering model and its metadata.
        
        Args:
            model: Trained clustering model
            algorithm: Algorithm name (kmeans, hierarchical, dbscan, gaussian_mixture)
            percentile: Percentile used for training
            feature_columns: List of feature column names used
            scaler: Fitted scaler used for feature normalization
            metadata: Additional metadata (scores, parameters, etc.)
        
        Returns:
            Path to saved model file
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        model_name = f"{algorithm}_{percentile}th_{timestamp}"
        model_path = os.path.join(self.model_dir, f"{model_name}.pkl")
        
        # Prepare model data
        model_data = {
            'model': model,
            'algorithm': algorithm,
            'percentile': percentile,
            'feature_columns': feature_columns,
            'scaler': scaler,
            'timestamp': timestamp,
            'metadata': metadata or {}
        }
        
        # Save model
        with open(model_path, 'wb') as f:
            pickle.dump(model_data, f)
        
        # Also save metadata as JSON for easy inspection
        metadata_path = os.path.join(self.model_dir, f"{model_name}_metadata.json")
        json_metadata = {
            'algorithm': algorithm,
            'percentile': percentile,
            'feature_columns': feature_columns,
            'timestamp': timestamp,
            'model_path': model_path,
            'metadata': {k: v for k, v in (metadata or {}).items() 
                        if isinstance(v, (int, float, str, list, dict))}
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(json_metadata, f, indent=2)
        
        print(f"Model saved to: {model_path}")
        return model_path
    
    def load_model(self, model_path: str) -> Dict:
        """
        Load a saved model and its metadata.
        
        Args:
            model_path: Path to the saved model file
        
        Returns:
            Dictionary containing model, scaler, and metadata
        """
        with open(model_path, 'rb') as f:
            model_data = pickle.load(f)
        
        return model_data
    
    def calculate_race_kind_features(self,
                                   X: np.ndarray,
                                   model: Union[KMeans, PredictableAgglomerativeClustering, GaussianMixture, DBSCAN],
                                   algorithm: str,
                                   labels: Optional[np.ndarray] = None,
                                   max_clusters: int = None) -> pd.DataFrame:
        """
        Calculate comprehensive race kind features for each race.
        
        Args:
            X: Scaled feature matrix
            model: Trained clustering model
            algorithm: Algorithm name
            labels: Pre-computed cluster labels (optional)
            max_clusters: Maximum number of clusters to create columns for (for padding)
        
        Returns:
            DataFrame with race kind features
        """
        n_samples = X.shape[0]
        
        # Get cluster labels if not provided
        if labels is None:
            if algorithm in ['kmeans', 'gaussian_mixture', 'hierarchical']:
                labels = model.predict(X)
            elif algorithm == 'dbscan':
                # DBSCAN needs to be refit
                labels = model.fit_predict(X)
        
        # Initialize feature dataframe
        features_df = pd.DataFrame()
        
        # 1. Cluster membership (one-hot encoded)
        unique_labels = sorted(set(labels))
        if -1 in unique_labels:  # Remove noise label from DBSCAN
            unique_labels.remove(-1)
        
        # Use max_clusters if provided, otherwise use actual number of clusters
        if max_clusters is None:
            max_clusters = len(unique_labels)
        
        # Create cluster membership columns for all possible clusters (up to max_clusters)
        for i in range(max_clusters):
            if i in unique_labels:
                features_df[f'cluster_{i}'] = (labels == i).astype(int)
            else:
                features_df[f'cluster_{i}'] = 0  # Default to 0 for missing clusters
        
        # 2. Distance to each cluster center
        if algorithm in ['kmeans', 'hierarchical']:
            # Both have cluster_centers_ attribute
            centers = model.cluster_centers_
            distances = euclidean_distances(X, centers)
            
            # Add distances to actual clusters
            for i in range(len(centers)):
                features_df[f'distance_to_cluster_{i}'] = distances[:, i]
            
            # Add NULL distances for missing clusters (up to max_clusters)
            for i in range(len(centers), max_clusters):
                features_df[f'distance_to_cluster_{i}'] = np.nan
        
        elif algorithm == 'gaussian_mixture':
            # For GMM, use component means as centers
            centers = model.means_
            distances = euclidean_distances(X, centers)
            
            # Add distances to actual clusters
            for i in range(len(centers)):
                features_df[f'distance_to_cluster_{i}'] = distances[:, i]
            
            # Add NULL distances for missing clusters (up to max_clusters)
            for i in range(len(centers), max_clusters):
                features_df[f'distance_to_cluster_{i}'] = np.nan
        
        elif algorithm == 'dbscan':
            # Calculate centroid for each cluster
            centers = []
            for label in unique_labels:
                mask = labels == label
                if np.any(mask):
                    center = X[mask].mean(axis=0)
                    centers.append(center)
            
            if centers:
                centers = np.array(centers)
                distances = euclidean_distances(X, centers)
                
                # Add distances to actual clusters
                for i, label in enumerate(unique_labels):
                    features_df[f'distance_to_cluster_{label}'] = distances[:, i]
                
                # Add NULL distances for missing clusters (up to max_clusters)
                for i in range(max(unique_labels) + 1, max_clusters):
                    features_df[f'distance_to_cluster_{i}'] = np.nan
            else:
                # No clusters found, set all distances to NaN
                for i in range(max_clusters):
                    features_df[f'distance_to_cluster_{i}'] = np.nan
        
        # 3. Local density (average distance to k nearest neighbors in same cluster)
        k_neighbors = 5  # Number of neighbors to consider
        local_density = np.zeros(n_samples)
        
        for i in range(n_samples):
            if labels[i] == -1:  # Skip noise points
                local_density[i] = np.nan
                continue
                
            # Find points in same cluster
            same_cluster_mask = (labels == labels[i]) & (np.arange(n_samples) != i)
            
            if np.sum(same_cluster_mask) > 0:
                # Calculate distances to all points in same cluster
                distances_to_cluster = euclidean_distances([X[i]], X[same_cluster_mask])[0]
                
                # Take average of k nearest neighbors (or all if fewer than k)
                k_actual = min(k_neighbors, len(distances_to_cluster))
                nearest_distances = np.sort(distances_to_cluster)[:k_actual]
                local_density[i] = np.mean(nearest_distances)
            else:
                local_density[i] = np.nan
        
        features_df['local_density'] = local_density
        
        # 4. Boundary distance (distance to nearest point in different cluster)
        boundary_distance = np.zeros(n_samples)
        
        for i in range(n_samples):
            if labels[i] == -1:  # Skip noise points
                boundary_distance[i] = np.nan
                continue
                
            # Find points in different clusters
            different_cluster_mask = (labels != labels[i]) & (labels != -1)
            
            if np.sum(different_cluster_mask) > 0:
                # Calculate distances to all points in different clusters
                distances_to_others = euclidean_distances([X[i]], X[different_cluster_mask])[0]
                boundary_distance[i] = np.min(distances_to_others)
            else:
                boundary_distance[i] = np.nan
        
        features_df['boundary_distance'] = boundary_distance
        
        # 5. Cluster assignment (categorical)
        features_df['cluster_label'] = labels
        
        # 6. Probability scores for probabilistic models
        if algorithm == 'gaussian_mixture':
            # Get probability of belonging to each component
            probs = model.predict_proba(X)
            
            # Add probabilities for actual clusters
            for i in range(probs.shape[1]):
                features_df[f'cluster_{i}_probability'] = probs[:, i]
            
            # Add NULL probabilities for missing clusters (up to max_clusters)
            for i in range(probs.shape[1], max_clusters):
                features_df[f'cluster_{i}_probability'] = np.nan
        
        return features_df
    
    def create_race_kind_features_table(self,
                                      table_name: str,
                                      algorithm: str,
                                      percentile: int,
                                      feature_columns: List[str],
                                      max_clusters: int = None,
                                      metadata: Dict = None):
        """
        Create a table to store race kind features in the database.
        
        Args:
            table_name: Name for the new table
            algorithm: Algorithm used
            percentile: Percentile used
            feature_columns: List of original features used for clustering
            max_clusters: Maximum number of clusters to create columns for
            metadata: Additional metadata to store
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Drop table if it exists
        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        
        # Use provided max_clusters or default to 10
        if max_clusters is None:
            max_clusters = 10
        
        # Create table with dynamic columns based on max_clusters
        create_sql = f"""
        CREATE TABLE {table_name} (
            competition_id INTEGER PRIMARY KEY,
            cluster_label INTEGER,
            local_density REAL,
            boundary_distance REAL
        """
        
        # Add cluster membership columns and distance columns
        for i in range(max_clusters):
            create_sql += f",\n            cluster_{i} INTEGER DEFAULT 0"
            create_sql += f",\n            distance_to_cluster_{i} REAL"
        
        # Add probability columns for GMM
        if algorithm == 'gaussian_mixture':
            for i in range(max_clusters):
                create_sql += f",\n            cluster_{i}_probability REAL"
        
        create_sql += "\n        )"
        
        cursor.execute(create_sql)
        
        # Create metadata table
        metadata_table = f"{table_name}_metadata"
        cursor.execute(f"DROP TABLE IF EXISTS {metadata_table}")
        cursor.execute(f"""
        CREATE TABLE {metadata_table} (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        
        # Insert metadata
        metadata_entries = [
            ('algorithm', algorithm),
            ('percentile', str(percentile)),
            ('feature_columns', json.dumps(feature_columns)),
            ('created_at', datetime.now().isoformat())
        ]
        
        if metadata:
            for k, v in metadata.items():
                if isinstance(v, (list, dict)):
                    v = json.dumps(v)
                metadata_entries.append((k, str(v)))
        
        cursor.executemany(
            f"INSERT INTO {metadata_table} (key, value) VALUES (?, ?)",
            metadata_entries
        )
        
        conn.commit()
        conn.close()
        
        print(f"Created table: {table_name}")
    
    def store_race_kind_features(self,
                               table_name: str,
                               competition_ids: List[int],
                               features_df: pd.DataFrame):
        """
        Store calculated race kind features in the database.
        
        Args:
            table_name: Table name to store features
            competition_ids: List of competition IDs
            features_df: DataFrame with calculated features
        """
        conn = sqlite3.connect(self.db_path)
        
        # Prepare data for insertion
        features_df['competition_id'] = competition_ids
        
        # Get column names from the table
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        table_columns = [row[1] for row in cursor.fetchall()]
        
        # Filter features_df to only include columns that exist in the table
        columns_to_insert = [col for col in features_df.columns if col in table_columns]
        insert_df = features_df[columns_to_insert]
        
        # Insert data
        insert_df.to_sql(table_name, conn, if_exists='append', index=False)
        
        conn.close()
        
        print(f"Stored {len(features_df)} race features in {table_name}")
    
    def predict_and_store_new_races(self,
                                  model_path: str,
                                  source_table: str,
                                  target_table: str,
                                  competition_ids: Optional[List[int]] = None,
                                  competition_type: Optional[str] = None,
                                  race_category: Optional[str] = None,
                                  max_clusters: Optional[int] = None) -> int:
        """
        Apply a saved model to new races and store the results.
        
        Args:
            model_path: Path to saved model
            source_table: Table containing race features (e.g., 'race_features_70')
            target_table: Table to store race kind features
            competition_ids: Specific competition IDs to process (if None, process all)
            competition_type: Filter by competition type
            race_category: Filter by race category
            max_clusters: Maximum number of clusters for feature calculation (if None, uses 4)
        
        Returns:
            Number of races processed
        """
        # Load model
        model_data = self.load_model(model_path)
        model = model_data['model']
        scaler = model_data['scaler']
        feature_columns = model_data['feature_columns']
        algorithm = model_data['algorithm']
        
        # Load race data from database
        conn = sqlite3.connect(self.db_path)
        
        # Build query
        query = f"SELECT * FROM {source_table}"
        conditions = []
        
        if competition_ids:
            placeholders = ','.join(['?' for _ in competition_ids])
            conditions.append(f"competition_id IN ({placeholders})")
        
        if competition_type:
            conditions.append("competition_type = ?")
        
        if race_category:
            conditions.append("race_category = ?")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        # Prepare parameters
        params = []
        if competition_ids:
            params.extend(competition_ids)
        if competition_type:
            params.append(competition_type)
        if race_category:
            params.append(race_category)
        
        # Load data
        data = pd.read_sql_query(query, conn, params=params)
        
        if len(data) == 0:
            print("No races found to process")
            return 0
        
        # Extract competition IDs
        comp_ids = data['competition_id'].tolist()
        
        # Ensure we have required features
        missing_features = set(feature_columns) - set(data.columns)
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
        
        # Select and scale features, handling NaN values
        X_df = data[feature_columns].fillna(0)
        X_scaled = scaler.transform(X_df)
        
        # Calculate race kind features with max_clusters for consistency
        if max_clusters is None:
            max_clusters = 4
        features_df = self.calculate_race_kind_features(X_scaled, model, algorithm, max_clusters=max_clusters)
        
        # Store in database
        self.store_race_kind_features(target_table, comp_ids, features_df)
        
        conn.close()
        
        return len(data)
    
    def apply_model_to_new_races(self,
                               model_path: str,
                               new_data: pd.DataFrame,
                               competition_ids: List[int]) -> pd.DataFrame:
        """
        Apply a saved model to new race data.
        
        Args:
            model_path: Path to saved model
            new_data: DataFrame with race features (must have same columns as training)
            competition_ids: List of competition IDs for the new races
        
        Returns:
            DataFrame with race kind features for the new races
        """
        # Load model
        model_data = self.load_model(model_path)
        model = model_data['model']
        scaler = model_data['scaler']
        feature_columns = model_data['feature_columns']
        algorithm = model_data['algorithm']
        
        # Ensure new data has required features
        missing_features = set(feature_columns) - set(new_data.columns)
        if missing_features:
            raise ValueError(f"Missing required features: {missing_features}")
        
        # Select and scale features, handling NaN values
        X_new_df = new_data[feature_columns].fillna(0)
        X_new_scaled = scaler.transform(X_new_df)
        
        # Calculate race kind features with max_clusters for consistency
        features_df = self.calculate_race_kind_features(X_new_scaled, model, algorithm, max_clusters=4)
        features_df['competition_id'] = competition_ids
        
        return features_df
    
    def list_saved_models(self) -> List[Dict]:
        """
        List all saved models with their metadata.
        
        Returns:
            List of dictionaries containing model information
        """
        models = []
        
        for filename in os.listdir(self.model_dir):
            if filename.endswith('_metadata.json'):
                metadata_path = os.path.join(self.model_dir, filename)
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                models.append(metadata)
        
        # Sort by timestamp (newest first)
        models.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return models