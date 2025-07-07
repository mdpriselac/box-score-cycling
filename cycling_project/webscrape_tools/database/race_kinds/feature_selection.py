"""
Feature Selection and Analysis Module

This module provides systematic feature selection for race kind analysis by:
1. Removing highly correlated features
2. Identifying features with low variance
3. Analyzing feature distributions
4. Testing feature discriminative power
5. Selecting optimal feature subsets for different race contexts
"""

import numpy as np
import pandas as pd
import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import (
    mutual_info_regression, f_classif, chi2,
    SelectKBest, VarianceThreshold, RFE
)
from sklearn.ensemble import RandomForestClassifier
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import kurtosis, skew, shapiro, kstest, normaltest
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster
from typing import Dict, List, Tuple, Optional, Set
import warnings
import matplotlib.pyplot as plt
import seaborn as sns
warnings.filterwarnings('ignore')


class FeatureSelector:
    """
    Systematic feature selection for race kind analysis.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the feature selector.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.all_features = None
        self.data = None
        self.feature_scores = {}
        self.selected_features = None
        
    def get_all_feature_columns(self, table_name: str) -> List[str]:
        """
        Get all numeric feature columns from a race features table.
        
        Args:
            table_name: Name of the race features table
            
        Returns:
            List of feature column names
        """
        conn = sqlite3.connect(self.db_path)
        
        # Get table schema
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # Exclude metadata columns
        exclude_columns = {
            'id', 'competition_id', 'percentile_analyzed', 'extraction_date',
            'competition_name', 'competition_type', 'race_id', 'race_name',
            'race_category', 'race_year', 'race_date'
        }
        
        # Get numeric columns
        numeric_types = {'REAL', 'INTEGER', 'NUMERIC'}
        feature_columns = [
            col[1] for col in columns 
            if col[2] in numeric_types and col[1] not in exclude_columns
        ]
        
        conn.close()
        self.all_features = feature_columns
        return feature_columns
    
    def load_data(
        self,
        table_name: str,
        competition_type: Optional[str] = None,
        race_category: Optional[str] = None,
        min_finishers: int = 30
    ) -> pd.DataFrame:
        """
        Load race data for feature analysis.
        
        Args:
            table_name: Name of the race features table
            competition_type: Filter by competition type
            race_category: Filter by race category
            min_finishers: Minimum number of finishers
            
        Returns:
            DataFrame with race features
        """
        if self.all_features is None:
            self.get_all_feature_columns(table_name)
        
        conn = sqlite3.connect(self.db_path)
        
        # Build query - quote column names that start with numbers
        quoted_features = []
        for feature in self.all_features:
            if feature[0].isdigit():
                quoted_features.append(f'"{feature}"')
            else:
                quoted_features.append(feature)
        
        feature_cols = ', '.join(quoted_features)
        query = f"""
        SELECT competition_id, competition_type, race_category, {feature_cols}
        FROM {table_name}
        WHERE included_finishers >= ?
        """
        params = [min_finishers]
        
        if competition_type is not None:
            if competition_type == 'stage_one_day':
                query += " AND competition_type IN ('stage', 'one_day')"
            else:
                query += " AND competition_type = ?"
                params.append(competition_type)
        
        if race_category is not None:
            query += " AND race_category = ?"
            params.append(race_category)
        
        self.data = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        return self.data
    
    def analyze_correlations(
        self,
        threshold: float = 0.95
    ) -> Tuple[pd.DataFrame, Set[str]]:
        """
        Analyze feature correlations and identify highly correlated pairs.
        
        Args:
            threshold: Correlation threshold for removal
            
        Returns:
            Tuple of (correlation matrix, set of features to remove)
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Calculate correlation matrix
        feature_data = self.data[self.all_features].fillna(0)
        corr_matrix = feature_data.corr()
        
        # Find highly correlated features
        upper_triangle = np.triu(np.ones_like(corr_matrix), k=1).astype(bool)
        high_corr_pairs = []
        
        for i in range(len(corr_matrix)):
            for j in range(i + 1, len(corr_matrix)):
                if abs(corr_matrix.iloc[i, j]) > threshold:
                    high_corr_pairs.append({
                        'feature1': corr_matrix.index[i],
                        'feature2': corr_matrix.columns[j],
                        'correlation': corr_matrix.iloc[i, j]
                    })
        
        # Decide which features to remove (keep the one with higher variance)
        features_to_remove = set()
        for pair in high_corr_pairs:
            var1 = feature_data[pair['feature1']].var()
            var2 = feature_data[pair['feature2']].var()
            
            # Remove the feature with lower variance
            if var1 > var2:
                features_to_remove.add(pair['feature2'])
            else:
                features_to_remove.add(pair['feature1'])
        
        self.feature_scores['correlation_removed'] = features_to_remove
        
        return corr_matrix, features_to_remove
    
    def analyze_variance(
        self,
        threshold: float = 0.01
    ) -> Tuple[pd.Series, Set[str]]:
        """
        Analyze feature variance and identify low-variance features.
        
        Args:
            threshold: Variance threshold (normalized)
            
        Returns:
            Tuple of (variance series, set of low-variance features)
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Calculate normalized variance
        feature_data = self.data[self.all_features].fillna(0)
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(feature_data)
        
        # Calculate variance of scaled features
        variances = pd.Series(
            scaled_data.var(axis=0),
            index=feature_data.columns
        )
        
        # Identify low-variance features
        low_variance_features = set(variances[variances < threshold].index)
        
        self.feature_scores['low_variance'] = low_variance_features
        
        return variances, low_variance_features
    
    def analyze_distributions(self) -> pd.DataFrame:
        """
        Analyze feature distributions for normality, skewness, and kurtosis.
        
        Returns:
            DataFrame with distribution statistics
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        feature_data = self.data[self.all_features].fillna(0)
        
        distribution_stats = []
        
        for feature in self.all_features:
            values = feature_data[feature].values
            
            # Skip if all values are the same
            if len(np.unique(values)) < 2:
                continue
            
            # Shapiro-Wilk test for normality
            if len(values) < 5000:  # Shapiro-Wilk has sample size limit
                _, p_value = shapiro(values)
            else:
                _, p_value = normaltest(values)
            
            stats = {
                'feature': feature,
                'mean': values.mean(),
                'std': values.std(),
                'skewness': skew(values),
                'kurtosis': kurtosis(values),
                'normality_p_value': p_value,
                'is_normal': p_value > 0.05,
                'unique_values': len(np.unique(values)),
                'zero_ratio': (values == 0).sum() / len(values)
            }
            
            distribution_stats.append(stats)
        
        dist_df = pd.DataFrame(distribution_stats)
        self.feature_scores['distribution_stats'] = dist_df
        
        return dist_df
    
    def analyze_clustering_power(
        self,
        n_clusters: int = 4,
        n_iterations: int = 10
    ) -> pd.Series:
        """
        Analyze how well each feature contributes to clustering.
        
        Args:
            n_clusters: Number of clusters to test
            n_iterations: Number of iterations for stability
            
        Returns:
            Series with feature importance scores
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        feature_data = self.data[self.all_features].fillna(0)
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(feature_data)
        
        feature_scores = {}
        
        # Test each feature individually
        for i, feature in enumerate(self.all_features):
            scores = []
            
            for _ in range(n_iterations):
                # Cluster using single feature
                kmeans = KMeans(n_clusters=n_clusters, random_state=np.random.randint(1000))
                labels = kmeans.fit_predict(scaled_data[:, i].reshape(-1, 1))
                
                # Calculate inertia ratio
                inertia_ratio = kmeans.inertia_ / len(scaled_data)
                scores.append(1 / (1 + inertia_ratio))  # Higher is better
            
            feature_scores[feature] = np.mean(scores)
        
        # Also test with all features for comparison
        all_features_scores = []
        for _ in range(n_iterations):
            kmeans = KMeans(n_clusters=n_clusters, random_state=np.random.randint(1000))
            kmeans.fit(scaled_data)
            all_features_scores.append(1 / (1 + kmeans.inertia_ / len(scaled_data)))
        
        # Normalize scores
        max_score = np.mean(all_features_scores)
        clustering_power = pd.Series(feature_scores) / max_score
        
        self.feature_scores['clustering_power'] = clustering_power
        
        return clustering_power
    
    def analyze_feature_importance(
        self,
        target_clusters: Optional[np.ndarray] = None
    ) -> pd.Series:
        """
        Analyze feature importance using Random Forest.
        
        Args:
            target_clusters: Target cluster labels (will create if not provided)
            
        Returns:
            Series with feature importance scores
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        feature_data = self.data[self.all_features].fillna(0)
        
        # Create target clusters if not provided
        if target_clusters is None:
            scaler = StandardScaler()
            scaled_data = scaler.fit_transform(feature_data)
            kmeans = KMeans(n_clusters=4, random_state=42)
            target_clusters = kmeans.fit_predict(scaled_data)
        
        # Train Random Forest
        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(feature_data, target_clusters)
        
        # Get feature importances
        importances = pd.Series(
            rf.feature_importances_,
            index=self.all_features
        )
        
        self.feature_scores['rf_importance'] = importances
        
        return importances
    
    def analyze_redundancy(self) -> Tuple[Dict[str, List[str]], Set[str]]:
        """
        Analyze feature redundancy using hierarchical clustering.
        
        Returns:
            Tuple of (feature clusters, redundant features to remove)
        """
        if self.data is None:
            raise ValueError("No data loaded. Call load_data() first.")
        
        # Calculate correlation matrix
        feature_data = self.data[self.all_features].fillna(0)
        corr_matrix = feature_data.corr().fillna(0)
        
        # Hierarchical clustering on features
        distance_matrix = 1 - abs(corr_matrix)
        linkage_matrix = linkage(distance_matrix, method='average')
        
        # Form clusters with distance threshold
        clusters = fcluster(linkage_matrix, 0.5, criterion='distance')
        
        # Group features by cluster
        feature_clusters = {}
        for i, cluster in enumerate(clusters):
            cluster_name = f'cluster_{cluster}'
            if cluster_name not in feature_clusters:
                feature_clusters[cluster_name] = []
            feature_clusters[cluster_name].append(self.all_features[i])
        
        # Select representative from each cluster (highest variance)
        redundant_features = set()
        
        for cluster_features in feature_clusters.values():
            if len(cluster_features) > 1:
                # Keep feature with highest variance
                variances = feature_data[cluster_features].var()
                keep_feature = variances.idxmax()
                
                # Mark others as redundant
                for feature in cluster_features:
                    if feature != keep_feature:
                        redundant_features.add(feature)
        
        self.feature_scores['redundant_features'] = redundant_features
        
        return feature_clusters, redundant_features
    
    def select_features(
        self,
        correlation_threshold: float = 0.95,
        variance_threshold: float = 0.01,
        min_clustering_power: float = 0.1,
        min_rf_importance: float = 0.01,
        max_features: Optional[int] = None,
        custom_weights: Optional[Dict[str, float]] = None
    ) -> List[str]:
        """
        Select optimal features based on multiple criteria.
        
        Args:
            correlation_threshold: Maximum correlation allowed
            variance_threshold: Minimum variance required
            min_clustering_power: Minimum clustering power
            min_rf_importance: Minimum RF importance
            max_features: Maximum number of features to select
            custom_weights: Custom weights for scoring
            
        Returns:
            List of selected feature names
        """
        # Run all analyses
        print("Running feature selection analysis...")
        
        print("1. Analyzing correlations...")
        _, corr_remove = self.analyze_correlations(correlation_threshold)
        
        print("2. Analyzing variance...")
        _, var_remove = self.analyze_variance(variance_threshold)
        
        print("3. Analyzing distributions...")
        dist_stats = self.analyze_distributions()
        
        print("4. Analyzing clustering power...")
        clustering_power = self.analyze_clustering_power()
        
        print("5. Analyzing feature importance...")
        rf_importance = self.analyze_feature_importance()
        
        print("6. Analyzing redundancy...")
        _, redundant = self.analyze_redundancy()
        
        # Combine removal sets
        features_to_remove = corr_remove | var_remove | redundant
        
        # Filter by thresholds
        valid_features = [
            f for f in self.all_features
            if f not in features_to_remove
            and clustering_power.get(f, 0) >= min_clustering_power
            and rf_importance.get(f, 0) >= min_rf_importance
        ]
        
        # Score remaining features
        if custom_weights is None:
            custom_weights = {
                'clustering_power': 0.3,
                'rf_importance': 0.3,
                'distribution_quality': 0.2,
                'uniqueness': 0.2
            }
        
        feature_scores = {}
        
        for feature in valid_features:
            # Calculate distribution quality score
            dist_row = dist_stats[dist_stats['feature'] == feature].iloc[0]
            dist_quality = (
                (1 - abs(dist_row['skewness']) / 10) * 0.5 +  # Prefer less skewed
                (1 - dist_row['zero_ratio']) * 0.3 +  # Prefer non-zero
                (min(dist_row['unique_values'] / 100, 1)) * 0.2  # Prefer more unique values
            )
            
            # Calculate uniqueness (inverse of correlation with other features)
            feature_data = self.data[valid_features].fillna(0)
            corr_with_others = feature_data.corr()[feature].abs().mean()
            uniqueness = 1 - corr_with_others
            
            # Combine scores
            score = (
                custom_weights['clustering_power'] * clustering_power.get(feature, 0) +
                custom_weights['rf_importance'] * rf_importance.get(feature, 0) +
                custom_weights['distribution_quality'] * dist_quality +
                custom_weights['uniqueness'] * uniqueness
            )
            
            feature_scores[feature] = score
        
        # Sort by score and select top features
        sorted_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)
        
        if max_features is not None:
            selected_features = [f[0] for f in sorted_features[:max_features]]
        else:
            # Select features with score above mean
            mean_score = np.mean([f[1] for f in sorted_features])
            selected_features = [f[0] for f in sorted_features if f[1] > mean_score]
        
        self.selected_features = selected_features
        self.feature_scores['final_scores'] = feature_scores
        
        return selected_features
    
    def generate_feature_report(
        self,
        output_path: str = 'database/race_kinds/reports/feature_selection_report.md'
    ) -> str:
        """
        Generate a comprehensive feature selection report.
        
        Args:
            output_path: Path for the output report
            
        Returns:
            Path to the generated report
        """
        with open(output_path, 'w') as f:
            f.write("# Feature Selection Report\n\n")
            f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- Total features analyzed: {len(self.all_features)}\n")
            f.write(f"- Features selected: {len(self.selected_features)}\n")
            f.write(f"- Features removed: {len(self.all_features) - len(self.selected_features)}\n\n")
            
            # Selected features
            f.write("## Selected Features\n\n")
            if 'final_scores' in self.feature_scores:
                f.write("| Feature | Score | Clustering Power | RF Importance |\n")
                f.write("|---------|-------|-----------------|---------------|\n")
                
                for feature in self.selected_features:
                    score = self.feature_scores['final_scores'].get(feature, 0)
                    cluster_power = self.feature_scores['clustering_power'].get(feature, 0)
                    rf_imp = self.feature_scores['rf_importance'].get(feature, 0)
                    f.write(f"| {feature} | {score:.3f} | {cluster_power:.3f} | {rf_imp:.3f} |\n")
            
            # Removed features
            f.write("\n## Removed Features\n\n")
            
            if 'correlation_removed' in self.feature_scores:
                f.write(f"### High Correlation ({len(self.feature_scores['correlation_removed'])} features)\n")
                for feature in sorted(self.feature_scores['correlation_removed']):
                    f.write(f"- {feature}\n")
            
            if 'low_variance' in self.feature_scores:
                f.write(f"\n### Low Variance ({len(self.feature_scores['low_variance'])} features)\n")
                for feature in sorted(self.feature_scores['low_variance']):
                    f.write(f"- {feature}\n")
            
            if 'redundant_features' in self.feature_scores:
                f.write(f"\n### Redundant Features ({len(self.feature_scores['redundant_features'])} features)\n")
                for feature in sorted(self.feature_scores['redundant_features']):
                    f.write(f"- {feature}\n")
            
            # Distribution statistics
            if 'distribution_stats' in self.feature_scores:
                f.write("\n## Distribution Analysis\n\n")
                dist_df = self.feature_scores['distribution_stats']
                
                f.write("### Features with high skewness (|skew| > 2):\n")
                high_skew = dist_df[abs(dist_df['skewness']) > 2]
                for _, row in high_skew.iterrows():
                    f.write(f"- {row['feature']}: skewness = {row['skewness']:.2f}\n")
                
                f.write("\n### Features with many zeros (> 50%):\n")
                high_zeros = dist_df[dist_df['zero_ratio'] > 0.5]
                for _, row in high_zeros.iterrows():
                    f.write(f"- {row['feature']}: {row['zero_ratio']:.1%} zeros\n")
        
        print(f"\nFeature selection report generated: {output_path}")
        return output_path
    
    def visualize_features(
        self,
        output_dir: str = 'database/race_kinds/reports'
    ):
        """
        Create visualizations of feature analysis.
        
        Args:
            output_dir: Directory for output plots
        """
        if self.data is None or self.selected_features is None:
            raise ValueError("No analysis completed. Run select_features() first.")
        
        # Correlation heatmap of selected features
        plt.figure(figsize=(12, 10))
        selected_data = self.data[self.selected_features].fillna(0)
        corr_matrix = selected_data.corr()
        
        sns.heatmap(corr_matrix, cmap='coolwarm', center=0, 
                   annot=True, fmt='.2f', square=True)
        plt.title('Correlation Heatmap of Selected Features')
        plt.tight_layout()
        plt.savefig(f'{output_dir}/selected_features_correlation.png')
        plt.close()
        
        # Feature importance plot
        if 'final_scores' in self.feature_scores:
            plt.figure(figsize=(10, 8))
            scores = pd.Series(self.feature_scores['final_scores'])
            scores = scores.sort_values(ascending=True)
            
            colors = ['green' if f in self.selected_features else 'gray' for f in scores.index]
            scores.plot(kind='barh', color=colors)
            plt.xlabel('Feature Score')
            plt.title('Feature Selection Scores')
            plt.tight_layout()
            plt.savefig(f'{output_dir}/feature_selection_scores.png')
            plt.close()