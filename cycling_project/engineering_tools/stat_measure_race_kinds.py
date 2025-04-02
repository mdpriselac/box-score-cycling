import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans, DBSCAN, AgglomerativeClustering
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import umap
from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score, adjusted_rand_score
from typing import List, Dict, Union, Tuple, Optional
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import warnings
import importlib.util

class RaceClusterAnalyzer:
    """
    A toolkit for clustering and analyzing race types based on statistical measures.
    
    This class provides methods for:
    - Filtering race types
    - Feature selection
    - Applying various clustering algorithms
    - Evaluating clustering results
    - Visualizing clusters and their characteristics
    """
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize the RaceClusterAnalyzer with a dataframe of race statistics.
        
        Args:
            data: DataFrame containing race statistics (from create_stat_measures_db)
        """
        self.data = data.copy()
        self.filtered_data = None
        self.features = None
        self.scaled_features = None
        self.scaler = None
        self.cluster_labels = None
        self.model = None
        self.feature_importance = None
        
        # Default columns to exclude from clustering
        self.default_exclude_cols = [
            'name', 'parent_race', 'stage_name', 'year', 'date', 
            'fc_race_id', 'tour', 'race_type', 'finishing_times','normalized_variance'
        ]
    
    def filter_race_types(self, race_types: List[str]) -> pd.DataFrame:
        """
        Filter the data to include only specified race types.
        
        Args:
            race_types: List of race types to include ('gc', 'stage', 'one_day')
            
        Returns:
            Filtered DataFrame
        """
        if not race_types:
            raise ValueError("At least one race type must be specified")
        
        self.filtered_data = self.data[self.data['race_type'].isin(race_types)].copy()
        return self.filtered_data
    
    def prepare_features(self, exclude_cols: List[str] = None, include_cols: List[str] = None) -> np.ndarray:
        """
        Prepare feature matrix for clustering by selecting columns and scaling.
        
        Args:
            exclude_cols: Columns to exclude from clustering
            include_cols: Specific columns to include (overrides exclude_cols)
            
        Returns:
            Scaled feature matrix
        """
        if self.filtered_data is None:
            raise ValueError("Must call filter_race_types before preparing features")
        
        # Determine columns to use
        if include_cols is not None:
            feature_cols = include_cols
        else:
            exclude_list = self.default_exclude_cols if exclude_cols is None else exclude_cols
            feature_cols = [col for col in self.filtered_data.columns if col not in exclude_list]
        
        # Store feature columns for later reference
        self._feature_cols = feature_cols
        
        # Drop rows with NaN values in selected features
        clean_data = self.filtered_data.dropna(subset=feature_cols)
        self.filtered_data = clean_data
        
        # Extract features
        self.features = clean_data[feature_cols].values
        
        # Scale features
        self.scaler = StandardScaler()
        self.scaled_features = self.scaler.fit_transform(self.features)
        
        return self.scaled_features
    
    def cluster(self, 
                algorithm: str = 'kmeans', 
                n_clusters: int = 3, 
                **kwargs) -> np.ndarray:
        """
        Apply a clustering algorithm to the feature matrix.
        
        Args:
            algorithm: Clustering algorithm to use ('kmeans', 'dbscan', 'hierarchical', 'gmm')
            n_clusters: Number of clusters (for applicable algorithms)
            **kwargs: Additional parameters for the clustering algorithm
            
        Returns:
            Cluster labels
        """
        if self.scaled_features is None:
            raise ValueError("Must call prepare_features before clustering")
        
        if algorithm == 'kmeans':
            self.model = KMeans(n_clusters=n_clusters, random_state=42, **kwargs)
        elif algorithm == 'dbscan':
            self.model = DBSCAN(**kwargs)
        elif algorithm == 'hierarchical':
            self.model = AgglomerativeClustering(n_clusters=n_clusters, **kwargs)
        elif algorithm == 'gmm':
            self.model = GaussianMixture(n_components=n_clusters, random_state=42, **kwargs)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        # Fit the model and get cluster labels
        if algorithm == 'gmm':
            self.model.fit(self.scaled_features)
            self.cluster_labels = self.model.predict(self.scaled_features)
        else:
            self.cluster_labels = self.model.fit_predict(self.scaled_features)
        
        # Add cluster labels to the filtered dataframe
        self.filtered_data['cluster'] = self.cluster_labels
        
        return self.cluster_labels
    
    def evaluate_clustering(self, true_labels: np.ndarray = None) -> Dict[str, float]:
        """
        Evaluate the clustering results using various metrics.
        
        Args:
            true_labels: Optional ground truth labels for supervised evaluation
            
        Returns:
            Dictionary of evaluation metrics
        """
        if self.cluster_labels is None:
            raise ValueError("Must call cluster before evaluating")
        
        metrics = {}
        
        # Calculate silhouette score
        try:
            metrics['silhouette'] = silhouette_score(self.scaled_features, self.cluster_labels)
        except:
            metrics['silhouette'] = float('nan')
        
        # Calculate Davies-Bouldin index
        try:
            metrics['davies_bouldin'] = davies_bouldin_score(self.scaled_features, self.cluster_labels)
        except:
            metrics['davies_bouldin'] = float('nan')
        
        # Calculate Calinski-Harabasz index
        try:
            metrics['calinski_harabasz'] = calinski_harabasz_score(self.scaled_features, self.cluster_labels)
        except:
            metrics['calinski_harabasz'] = float('nan')
        
        # If ground truth labels are provided, calculate ARI
        if true_labels is not None:
            metrics['adjusted_rand'] = adjusted_rand_score(true_labels, self.cluster_labels)
        
        return metrics
    
    def optimal_k(self, k_range: range = range(2, 11), metric: str = 'silhouette') -> Tuple[int, List[float]]:
        """
        Find the optimal number of clusters for K-means.
        
        Args:
            k_range: Range of k values to test
            metric: Metric to optimize ('silhouette', 'davies_bouldin', 'calinski_harabasz')
            
        Returns:
            Tuple of (optimal k, list of metric values)
        """
        if self.scaled_features is None:
            raise ValueError("Must call prepare_features before finding optimal k")
        
        scores = []
        
        for k in k_range:
            model = KMeans(n_clusters=k, random_state=42)
            labels = model.fit_predict(self.scaled_features)
            
            if metric == 'silhouette':
                score = silhouette_score(self.scaled_features, labels)
                scores.append(score)
            elif metric == 'davies_bouldin':
                score = davies_bouldin_score(self.scaled_features, labels)
                scores.append(-score)  # Lower is better, so negate
            elif metric == 'calinski_harabasz':
                score = calinski_harabasz_score(self.scaled_features, labels)
                scores.append(score)
            else:
                raise ValueError(f"Unsupported metric: {metric}")
        
        optimal_k = k_range[np.argmax(scores)]
        return optimal_k, scores
    
    def visualize_clusters_2d(self, method: str = 'pca', interactive: bool = False) -> Union[plt.Figure, go.Figure]:
        """
        Visualize clusters in 2D using dimensionality reduction.
        
        Args:
            method: Method for dimensionality reduction ('pca', 'tsne', 'umap')
            interactive: Whether to use plotly for interactive visualization
            
        Returns:
            Matplotlib or Plotly figure
        """
        if self.cluster_labels is None:
            raise ValueError("Must call cluster before visualizing")
        
        # Apply dimensionality reduction
        if method == 'pca':
            reducer = PCA(n_components=2, random_state=42)
            embedding = reducer.fit_transform(self.scaled_features)
            x_label, y_label = 'PCA Component 1', 'PCA Component 2'
        elif method == 'tsne':
            reducer = TSNE(n_components=2, random_state=42)
            embedding = reducer.fit_transform(self.scaled_features)
            x_label, y_label = 't-SNE Component 1', 't-SNE Component 2'
        elif method == 'umap':
            # Suppress UMAP warnings about parallelism and random_state
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="n_jobs value .* overridden to .* by setting random_state")
                warnings.filterwarnings("ignore", message="OMP: Info #276")
                reducer = umap.UMAP(random_state=42)
                embedding = reducer.fit_transform(self.scaled_features)
            x_label, y_label = 'UMAP Component 1', 'UMAP Component 2'
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        # Create DataFrame for visualization
        viz_df = pd.DataFrame({
            'x': embedding[:, 0],
            'y': embedding[:, 1],
            'cluster': self.cluster_labels,
            'race_type': self.filtered_data['race_type'].values
        })
        
        # Add useful columns for hover data
        useful_hover_cols = ['name', 'year', 'tour', 'total_time']
        for col in useful_hover_cols:
            if col in self.filtered_data.columns:
                viz_df[col] = self.filtered_data[col].values
        
        if interactive:
            # Check if required dependencies for interactive plotting are available
            has_nbformat = importlib.util.find_spec('nbformat') is not None
            try:
                import nbformat
                from packaging import version
                has_valid_nbformat = version.parse(nbformat.__version__) >= version.parse('4.2.0')
            except (ImportError, AttributeError):
                has_valid_nbformat = False
            
            if not has_nbformat or not has_valid_nbformat:
                print("Warning: Interactive visualization requires nbformat>=4.2.0. Falling back to static matplotlib plot.")
                interactive = False
            
        if interactive:
            # Create interactive plotly visualization
            fig = px.scatter(
                viz_df, x='x', y='y', 
                color='cluster', symbol='race_type',
                title=f'Cluster Visualization using {method.upper()}',
                labels={'x': x_label, 'y': y_label, 'cluster': 'Cluster', 'race_type': 'Race Type'},
                hover_data=viz_df.columns
            )
            return fig
        else:
            # Create matplotlib visualization
            fig, ax = plt.subplots(figsize=(10, 8))
            race_types = viz_df['race_type'].unique()
            clusters = sorted(viz_df['cluster'].unique())
            
            for cluster in clusters:
                for race_type in race_types:
                    mask = (viz_df['cluster'] == cluster) & (viz_df['race_type'] == race_type)
                    ax.scatter(
                        viz_df.loc[mask, 'x'], 
                        viz_df.loc[mask, 'y'],
                        label=f'Cluster {cluster}, {race_type}',
                        marker=self._get_marker_for_race_type(race_type),
                        alpha=0.7
                    )
            
            ax.set_xlabel(x_label)
            ax.set_ylabel(y_label)
            ax.set_title(f'Cluster Visualization using {method.upper()}')
            ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            return fig
    
    def interactive_cluster_viz(self, method: str = 'pca') -> None:
        """
        Create and display an interactive visualization if possible, with fallback to static.
        This method handles the display so the user doesn't need to call .show()
        
        Args:
            method: Method for dimensionality reduction ('pca', 'tsne', 'umap')
        """
        fig = self.visualize_clusters_2d(method=method, interactive=True)
        
        # If we got a plotly figure, try to display it
        if isinstance(fig, go.Figure):
            try:
                # Try to display the interactive plot
                fig.show()
            except Exception as e:
                print(f"Error displaying interactive plot: {e}")
                print("Falling back to static matplotlib visualization")
                # Fall back to matplotlib
                plt_fig = self.visualize_clusters_2d(method=method, interactive=False)
                plt.show()
        else:
            # If we got a matplotlib figure, just display it
            plt.show()
    
    def visualize_feature_importance(self, feature_names: List[str] = None) -> plt.Figure:
        """
        Visualize the importance of features in distinguishing clusters.
        
        Args:
            feature_names: Names of the features (if None, will use column names)
            
        Returns:
            Matplotlib figure
        """
        if self.cluster_labels is None or self.features is None:
            raise ValueError("Must call cluster before visualizing feature importance")
        
        # Get feature names
        if feature_names is None:
            # If self.features was created with include_cols, use those
            exclude_list = self.default_exclude_cols
            available_cols = [col for col in self.filtered_data.columns if col not in exclude_list]
            
            # Make sure we only use features that were actually included in clustering
            if hasattr(self, '_feature_cols') and self._feature_cols is not None:
                feature_names = self._feature_cols
            else:
                # Try to infer feature names from the filtered data
                n_features = self.features.shape[1]
                if len(available_cols) == n_features:
                    feature_names = available_cols
                else:
                    feature_names = [f'Feature {i+1}' for i in range(n_features)]
                    print(f"Warning: Could not match feature names. Using generic names.")
        
        # Verify feature names list matches the feature count
        if len(feature_names) != self.features.shape[1]:
            raise ValueError(f"Number of feature names ({len(feature_names)}) does not match feature count ({self.features.shape[1]})")
        
        # Calculate feature means for each cluster
        cluster_means = []
        unique_clusters = sorted(set(self.cluster_labels))
        
        # Need at least 2 clusters for meaningful comparison
        if len(unique_clusters) < 2:
            print("Warning: Need at least 2 clusters for meaningful feature importance visualization.")
            # Create a basic single-row heatmap
            cluster_means_df = pd.DataFrame([np.mean(self.features, axis=0)], columns=feature_names)
            cluster_means_df.index = [f'Cluster {unique_clusters[0]}']
            plt.figure(figsize=(min(12, len(feature_names) * 0.8), 3))
            sns.heatmap(cluster_means_df, annot=True, cmap='viridis', fmt='.2f', linewidths=0.5)
            plt.title('Feature Means for Single Cluster')
            plt.tight_layout()
            return plt.gcf()
        
        # Calculate means for each cluster
        for cluster in unique_clusters:
            mask = self.cluster_labels == cluster
            if np.sum(mask) > 0:  # Ensure the cluster has at least one member
                cluster_means.append(np.mean(self.features[mask], axis=0))
            else:
                # Handle empty clusters
                cluster_means.append(np.zeros(self.features.shape[1]))
                print(f"Warning: Cluster {cluster} is empty")
        
        # Create a DataFrame for visualization
        cluster_means_df = pd.DataFrame(cluster_means, columns=feature_names)
        cluster_means_df.index = [f'Cluster {c}' for c in unique_clusters]
        
        # Z-score normalization for better visualization
        try:
            z_scores = (cluster_means_df - cluster_means_df.mean()) / cluster_means_df.std()
            # Handle any remaining NaN values (from zero std dev)
            z_scores = z_scores.fillna(0)
        except Exception as e:
            print(f"Warning: Could not compute z-scores: {e}. Using raw values instead.")
            z_scores = cluster_means_df
        
        # Adjust figure size based on number of features and clusters
        fig_width = min(16, max(8, len(feature_names) * 0.5))
        fig_height = max(3, len(unique_clusters) * 0.8)
        
        # Plot heatmap
        plt.figure(figsize=(fig_width, fig_height))
        
        # If too many features, rotate labels
        if len(feature_names) > 8:
            plt.xticks(rotation=45, ha='right')
        
        # Create heatmap with custom formatting
        fmt = '.2f' if z_scores.abs().max().max() < 10 else '.1f'
        ax = sns.heatmap(z_scores, annot=True, cmap='coolwarm', center=0, 
                   fmt=fmt, linewidths=0.5, cbar_kws={'label': 'Z-score'})
        
        plt.title('Feature Importance by Cluster (Z-scored)')
        plt.ylabel('Cluster')
        plt.tight_layout()
        
        # Store the feature importance information
        self.feature_importance = z_scores
        
        return plt.gcf()
    
    def compare_race_types_in_clusters(self) -> plt.Figure:
        """
        Visualize the distribution of race types within each cluster.
        
        Returns:
            Matplotlib figure
        """
        if self.cluster_labels is None:
            raise ValueError("Must call cluster before comparing race types")
        
        # Count race types within each cluster
        counts_df = pd.crosstab(self.filtered_data['cluster'], self.filtered_data['race_type'])
        
        # Convert to percentages
        percentage_df = counts_df.div(counts_df.sum(axis=1), axis=0) * 100
        
        # Plot stacked bar chart
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        counts_df.plot(kind='bar', stacked=True, ax=ax1, colormap='viridis')
        ax1.set_title('Count of Race Types in Each Cluster')
        ax1.set_xlabel('Cluster')
        ax1.set_ylabel('Count')
        ax1.legend(title='Race Type')
        
        percentage_df.plot(kind='bar', stacked=True, ax=ax2, colormap='viridis')
        ax2.set_title('Percentage of Race Types in Each Cluster')
        ax2.set_xlabel('Cluster')
        ax2.set_ylabel('Percentage')
        ax2.legend(title='Race Type')
        
        plt.tight_layout()
        return fig
    
    def cluster_profile_boxplots(self, feature_names: List[str] = None, max_cols: int = 3) -> plt.Figure:
        """
        Create boxplots showing the distribution of features for each cluster.
        
        Args:
            feature_names: Names of features to include (if None, will use all)
            max_cols: Maximum number of columns for the subplot grid
            
        Returns:
            Matplotlib figure
        """
        if self.cluster_labels is None or self.features is None:
            raise ValueError("Must call cluster before creating profile boxplots")
        
        if feature_names is None:
            # Get feature names from filtered data
            exclude_list = self.default_exclude_cols
            feature_names = [col for col in self.filtered_data.columns if col not in exclude_list]
        
        # Determine subplot grid dimensions
        n_features = len(feature_names)
        n_cols = min(max_cols, n_features)
        n_rows = (n_features + n_cols - 1) // n_cols
        
        # Create boxplot for each feature
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows))
        axes = axes.flatten() if n_features > 1 else [axes]
        
        for i, feature in enumerate(feature_names):
            if i < len(axes):
                # Create a temporary DataFrame for seaborn
                temp_df = pd.DataFrame({
                    'value': self.filtered_data[feature],
                    'cluster': self.filtered_data['cluster']
                })
                
                sns.boxplot(x='cluster', y='value', data=temp_df, ax=axes[i])
                axes[i].set_title(feature)
                axes[i].set_xlabel('Cluster')
                
                # Hide unused subplots
                for j in range(n_features, len(axes)):
                    axes[j].set_visible(False)
        
        plt.tight_layout()
        return fig
    
    def _get_marker_for_race_type(self, race_type: str) -> str:
        """Helper method to assign markers to race types"""
        markers = {
            'one_day': 'o',
            'stage': '^',
            'gc': 's'
        }
        return markers.get(race_type, 'x')

    def save_results(self, filename: str) -> None:
        """
        Save the filtered data with cluster labels to a CSV file.
        
        Args:
            filename: Name of the file to save
        """
        if self.filtered_data is None or 'cluster' not in self.filtered_data.columns:
            raise ValueError("Must call cluster before saving results")
        
        self.filtered_data.to_csv(filename, index=False)
        print(f"Results saved to {filename}")
