"""
Evaluation framework for race kind clustering.
Provides comprehensive evaluation metrics and visualization tools
for assessing clustering quality and interpretability.
"""

import sqlite3
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import json
from typing import Dict, List, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')


class ClusteringEvaluator:
    """Comprehensive evaluation framework for clustering results."""
    
    def __init__(self, clustering_instance):
        """Initialize with a RaceKindClustering instance."""
        self.clustering = clustering_instance
        self.evaluation_results = {}
        
    def evaluate_clustering_stability(self, method: str = 'kmeans', 
                                    n_bootstrap: int = 10, 
                                    sample_fraction: float = 0.8) -> Dict:
        """Evaluate clustering stability through bootstrap resampling."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        original_labels = self.clustering.clusters[method]
        n_samples = len(original_labels)
        n_clusters = len(set(original_labels)) - (1 if -1 in original_labels else 0)
        
        stability_scores = []
        
        for i in range(n_bootstrap):
            # Bootstrap sample
            indices = np.random.choice(n_samples, 
                                     size=int(n_samples * sample_fraction), 
                                     replace=True)
            
            bootstrap_features = self.clustering.features[indices]
            
            # Re-cluster
            if method == 'kmeans':
                from sklearn.cluster import KMeans
                model = KMeans(n_clusters=n_clusters, random_state=i)
            elif method == 'hierarchical':
                from sklearn.cluster import AgglomerativeClustering
                model = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
            else:
                continue
            
            bootstrap_labels = model.fit_predict(bootstrap_features)
            
            # Compare with original labels for sampled indices
            # We need to map bootstrap results back to original indices
            if len(bootstrap_labels) == len(indices):
                # Get original labels for the sampled indices
                original_subset = original_labels[indices]
                
                # Calculate adjusted Rand index
                from sklearn.metrics import adjusted_rand_score
                ari = adjusted_rand_score(original_subset, bootstrap_labels)
                stability_scores.append(ari)
        
        stability_result = {
            'method': method,
            'n_bootstrap': n_bootstrap,
            'mean_stability': np.mean(stability_scores),
            'std_stability': np.std(stability_scores),
            'min_stability': np.min(stability_scores),
            'max_stability': np.max(stability_scores)
        }
        
        print(f"Stability for {method}: {stability_result['mean_stability']:.3f} ± {stability_result['std_stability']:.3f}")
        return stability_result
    
    def evaluate_temporal_consistency(self, method: str = 'kmeans') -> Dict:
        """Evaluate if clusters are consistent across time periods."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        data = self.clustering.data.copy()
        data['cluster'] = labels
        
        # Group by year ranges
        year_ranges = [
            (2015, 2017, '2015-2017'),
            (2018, 2020, '2018-2020'),
            (2021, 2023, '2021-2023'),
            (2024, 2025, '2024-2025')
        ]
        
        temporal_distribution = {}
        
        for start_year, end_year, period in year_ranges:
            period_data = data[(data['race_year'] >= start_year) & 
                              (data['race_year'] <= end_year)]
            
            if len(period_data) > 0:
                cluster_dist = period_data['cluster'].value_counts(normalize=True).to_dict()
                temporal_distribution[period] = {
                    'n_races': len(period_data),
                    'cluster_distribution': cluster_dist
                }
        
        # Calculate temporal stability metric
        if len(temporal_distribution) > 1:
            # Get all unique clusters across all periods
            all_clusters = set()
            for period_data in temporal_distribution.values():
                all_clusters.update(period_data['cluster_distribution'].keys())
            all_clusters = sorted(list(all_clusters))
            
            # Normalize distributions to have same cluster set
            normalized_distributions = []
            for period_data in temporal_distribution.values():
                dist = period_data['cluster_distribution']
                normalized = [dist.get(cluster, 0) for cluster in all_clusters]
                # Ensure it sums to 1
                total = sum(normalized)
                if total > 0:
                    normalized = [x/total for x in normalized]
                normalized_distributions.append(normalized)
            
            # Use KL divergence to measure distribution changes
            from scipy.stats import entropy
            stability_scores = []
            
            for i in range(len(normalized_distributions) - 1):
                # Add small epsilon to avoid log(0)
                dist1 = np.array(normalized_distributions[i]) + 1e-10
                dist2 = np.array(normalized_distributions[i+1]) + 1e-10
                # Renormalize
                dist1 = dist1 / dist1.sum()
                dist2 = dist2 / dist2.sum()
                
                kl_div = entropy(dist1, dist2)
                stability_scores.append(kl_div)
            
            temporal_stability = 1 / (1 + np.mean(stability_scores)) if stability_scores else 1.0
        else:
            temporal_stability = 1.0
        
        result = {
            'method': method,
            'temporal_distribution': temporal_distribution,
            'temporal_stability_score': temporal_stability
        }
        
        print(f"Temporal stability for {method}: {temporal_stability:.3f}")
        return result
    
    def evaluate_feature_importance(self, method: str = 'kmeans') -> pd.DataFrame:
        """Evaluate which features are most important for clustering."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        features = self.clustering.features
        feature_names = self.clustering.feature_names
        
        # Calculate feature importance using ANOVA F-statistic
        from sklearn.feature_selection import f_classif
        f_scores, p_values = f_classif(features, labels)
        
        # Create importance dataframe
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'f_score': f_scores,
            'p_value': p_values,
            'importance_rank': pd.Series(f_scores).rank(ascending=False)
        })
        
        importance_df = importance_df.sort_values('f_score', ascending=False)

        print(f"\nTop 10 discriminative features for {method}:")
        print(importance_df.head(10)[['feature', 'f_score']])
        
        return importance_df
    
    def calculate_cluster_separability(self, method: str = 'kmeans') -> Dict:
        """Calculate detailed separability metrics for clusters."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        features = self.clustering.features
        
        # Calculate silhouette scores per sample
        silhouette_vals = silhouette_samples(features, labels)
        
        # Group by cluster
        separability_by_cluster = {}
        unique_labels = set(labels)
        
        for label in unique_labels:
            if label == -1:  # Skip noise
                continue
            
            cluster_mask = labels == label
            cluster_silhouettes = silhouette_vals[cluster_mask]
            
            separability_by_cluster[f'cluster_{label}'] = {
                'size': np.sum(cluster_mask),
                'mean_silhouette': np.mean(cluster_silhouettes),
                'std_silhouette': np.std(cluster_silhouettes),
                'min_silhouette': np.min(cluster_silhouettes),
                'max_silhouette': np.max(cluster_silhouettes),
                'negative_silhouettes': np.sum(cluster_silhouettes < 0)
            }
        
        overall_metrics = {
            'method': method,
            'overall_silhouette': silhouette_score(features, labels),
            'n_clusters': len(unique_labels) - (1 if -1 in unique_labels else 0),
            'cluster_metrics': separability_by_cluster
        }
        
        return overall_metrics
    
    def evaluate_cluster_characteristics(self, method: str = 'kmeans') -> pd.DataFrame:
        """Analyze detailed characteristics of each cluster with focus on breakpoint features."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        data = self.clustering.data.copy()
        data['cluster'] = labels
        
        characteristics = []
        
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:  # Skip noise
                continue
            
            cluster_data = data[data['cluster'] == cluster_id]
            
            # Basic stats
            char = {
                'cluster_id': cluster_id,
                'n_races': len(cluster_data),
                'pct_of_total': len(cluster_data) / len(data) * 100,
                
                # Race characteristics
                'avg_finishers': cluster_data['total_finishers'].mean(),
                'std_finishers': cluster_data['total_finishers'].std(),
                'median_finishers': cluster_data['total_finishers'].median(),
                
                # Category distribution (detailed)
                'main_category': cluster_data['race_category'].mode()[0] if len(cluster_data) > 0 else 'N/A',
                'category_counts': cluster_data['race_category'].value_counts().to_dict(),
                'category_percentages': (cluster_data['race_category'].value_counts(normalize=True) * 100).to_dict(),
                
                # Temporal characteristics
                'year_range': f"{cluster_data['race_year'].min()}-{cluster_data['race_year'].max()}",
                'median_year': cluster_data['race_year'].median(),
                'n_unique_competitions': cluster_data['competition_name'].nunique(),
                
                # Winning time characteristics
                'avg_winning_time_hours': cluster_data['winning_time'].mean() / 3600,
                'median_winning_time_hours': cluster_data['winning_time'].median() / 3600,
                'winning_time_range_hours': (cluster_data['winning_time'].max() - cluster_data['winning_time'].min()) / 3600,
            }
            
            # BREAKPOINT ANALYSIS - Key insight
            # Kurtosis breakdown point analysis
            kurtosis_breakdown = cluster_data['kurtosis_breakdown_point']
            char.update({
                'kurtosis_breakdown_mean': kurtosis_breakdown.mean(),
                'kurtosis_breakdown_median': kurtosis_breakdown.median(),
                'kurtosis_breakdown_std': kurtosis_breakdown.std(),
                'pct_no_kurtosis_breakdown': (kurtosis_breakdown == 0).mean() * 100,
                'kurtosis_breakdown_distribution': kurtosis_breakdown.value_counts().to_dict(),
                'most_common_kurtosis_breakdown': kurtosis_breakdown.mode()[0] if len(kurtosis_breakdown) > 0 else 0,
            })
            
            # Variance breakdown point analysis
            variance_breakdown = cluster_data['variance_breakdown_point']
            char.update({
                'variance_breakdown_mean': variance_breakdown.mean(),
                'variance_breakdown_median': variance_breakdown.median(),
                'variance_breakdown_std': variance_breakdown.std(),
                'pct_no_variance_breakdown': (variance_breakdown == 0).mean() * 100,
                'variance_breakdown_distribution': variance_breakdown.value_counts().to_dict(),
                'most_common_variance_breakdown': variance_breakdown.mode()[0] if len(variance_breakdown) > 0 else 0,
            })
            
            # Gradient characteristics for all features
            for feature in self.clustering.feature_names:
                if feature in cluster_data.columns:
                    feature_data = cluster_data[feature]
                    char.update({
                        f'{feature}_mean': feature_data.mean(),
                        f'{feature}_median': feature_data.median(),
                        f'{feature}_std': feature_data.std(),
                        f'{feature}_min': feature_data.min(),
                        f'{feature}_max': feature_data.max(),
                        f'{feature}_q25': feature_data.quantile(0.25),
                        f'{feature}_q75': feature_data.quantile(0.75),
                        f'{feature}_iqr': feature_data.quantile(0.75) - feature_data.quantile(0.25),
                    })
            
            characteristics.append(char)
        
        return pd.DataFrame(characteristics)
    
    def analyze_breakpoint_patterns(self, method: str = 'kmeans') -> Dict:
        """Deep dive analysis of breakpoint patterns across clusters."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        data = self.clustering.data.copy()
        data['cluster'] = labels
        
        analysis = {
            'method': method,
            'kurtosis_breakdown_analysis': {},
            'variance_breakdown_analysis': {},
            'combined_breakdown_analysis': {}
        }
        
        # Analyze kurtosis breakdown patterns
        kurtosis_by_cluster = {}
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:
                continue
            cluster_data = data[data['cluster'] == cluster_id]
            kurtosis_breakdown = cluster_data['kurtosis_breakdown_point']
            
            kurtosis_by_cluster[f'cluster_{cluster_id}'] = {
                'total_races': len(cluster_data),
                'no_breakdown_count': int((kurtosis_breakdown == 0).sum()),
                'no_breakdown_pct': float((kurtosis_breakdown == 0).mean() * 100),
                'breakdown_points': kurtosis_breakdown[kurtosis_breakdown > 0].value_counts().to_dict(),
                'mean_breakdown_point': float(kurtosis_breakdown[kurtosis_breakdown > 0].mean()) if (kurtosis_breakdown > 0).any() else 0,
                'most_common_breakdown': int(kurtosis_breakdown.mode()[0]) if len(kurtosis_breakdown) > 0 else 0
            }
        
        analysis['kurtosis_breakdown_analysis'] = kurtosis_by_cluster
        
        # Analyze variance breakdown patterns
        variance_by_cluster = {}
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:
                continue
            cluster_data = data[data['cluster'] == cluster_id]
            variance_breakdown = cluster_data['variance_breakdown_point']
            
            variance_by_cluster[f'cluster_{cluster_id}'] = {
                'total_races': len(cluster_data),
                'no_breakdown_count': int((variance_breakdown == 0).sum()),
                'no_breakdown_pct': float((variance_breakdown == 0).mean() * 100),
                'breakdown_points': variance_breakdown[variance_breakdown > 0].value_counts().to_dict(),
                'mean_breakdown_point': float(variance_breakdown[variance_breakdown > 0].mean()) if (variance_breakdown > 0).any() else 0,
                'most_common_breakdown': int(variance_breakdown.mode()[0]) if len(variance_breakdown) > 0 else 0
            }
        
        analysis['variance_breakdown_analysis'] = variance_by_cluster
        
        # Combined breakdown analysis
        combined_analysis = {}
        for cluster_id in sorted(set(labels)):
            if cluster_id == -1:
                continue
            cluster_data = data[data['cluster'] == cluster_id]
            
            # Create breakdown pattern categories
            kurtosis_breaks = cluster_data['kurtosis_breakdown_point'] > 0
            variance_breaks = cluster_data['variance_breakdown_point'] > 0
            
            patterns = {
                'both_break': (kurtosis_breaks & variance_breaks).sum(),
                'only_kurtosis_breaks': (kurtosis_breaks & ~variance_breaks).sum(),
                'only_variance_breaks': (~kurtosis_breaks & variance_breaks).sum(),
                'neither_breaks': (~kurtosis_breaks & ~variance_breaks).sum()
            }
            
            total = len(cluster_data)
            combined_analysis[f'cluster_{cluster_id}'] = {
                'total_races': total,
                'pattern_counts': patterns,
                'pattern_percentages': {k: (v/total)*100 for k, v in patterns.items()}
            }
        
        analysis['combined_breakdown_analysis'] = combined_analysis
        
        return analysis
    
    def generate_evaluation_report(self, output_file: str = 'race_kinds/race_kind_finding/clustering_evaluation_report.txt'):
        """Generate comprehensive evaluation report."""
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("RACE KIND CLUSTERING EVALUATION REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Dataset summary
        report_lines.append("DATASET SUMMARY")
        report_lines.append("-" * 40)
        report_lines.append(f"Total races analyzed: {len(self.clustering.data)}")
        report_lines.append(f"Features used: {', '.join(self.clustering.feature_names)}")
        report_lines.append(f"Clustering methods evaluated: {', '.join(self.clustering.clusters.keys())}\n")
        
        # Evaluate each method
        for method in self.clustering.clusters.keys():
            report_lines.append(f"\n{'='*60}")
            report_lines.append(f"METHOD: {method.upper()}")
            report_lines.append(f"{'='*60}\n")
            
            # Separability metrics
            sep_metrics = self.calculate_cluster_separability(method)
            report_lines.append("CLUSTER SEPARABILITY")
            report_lines.append("-" * 30)
            report_lines.append(f"Overall silhouette score: {sep_metrics['overall_silhouette']:.3f}")
            report_lines.append(f"Number of clusters: {sep_metrics['n_clusters']}")
            
            for cluster_name, metrics in sep_metrics['cluster_metrics'].items():
                report_lines.append(f"\n{cluster_name}:")
                report_lines.append(f"  Size: {metrics['size']} races")
                report_lines.append(f"  Mean silhouette: {metrics['mean_silhouette']:.3f} ± {metrics['std_silhouette']:.3f}")
                report_lines.append(f"  Poorly assigned races: {metrics['negative_silhouettes']}")
            
            # Stability evaluation
            report_lines.append("\n\nSTABILITY ANALYSIS")
            report_lines.append("-" * 30)
            stability = self.evaluate_clustering_stability(method, n_bootstrap=5)
            report_lines.append(f"Bootstrap stability: {stability['mean_stability']:.3f} ± {stability['std_stability']:.3f}")
            
            # Temporal consistency
            temporal = self.evaluate_temporal_consistency(method)
            report_lines.append(f"Temporal stability: {temporal['temporal_stability_score']:.3f}")
            
            # Feature importance
            report_lines.append("\n\nFEATURE IMPORTANCE")
            report_lines.append("-" * 30)
            importance = self.evaluate_feature_importance(method)
            for _, row in importance.head(3).iterrows():
                report_lines.append(f"{row['feature']}: F-score = {row['f_score']:.2f}")
            
            # Detailed cluster characteristics
            report_lines.append("\n\nDETAILED CLUSTER CHARACTERISTICS")
            report_lines.append("-" * 40)
            characteristics = self.evaluate_cluster_characteristics(method)
            
            for _, cluster in characteristics.iterrows():
                cluster_id = int(cluster['cluster_id'])
                report_lines.append(f"\n{'='*50}")
                report_lines.append(f"CLUSTER {cluster_id}")
                report_lines.append(f"{'='*50}")
                
                # Basic characteristics
                report_lines.append(f"Size: {int(cluster['n_races'])} races ({cluster['pct_of_total']:.1f}% of total)")
                report_lines.append(f"Finishers: {cluster['avg_finishers']:.0f} ± {cluster['std_finishers']:.0f} (median: {cluster['median_finishers']:.0f})")
                report_lines.append(f"Years: {cluster['year_range']} (median: {cluster['median_year']:.0f})")
                report_lines.append(f"Unique competitions: {int(cluster['n_unique_competitions'])}")
                
                # Category distribution
                report_lines.append(f"\nCategory Distribution:")
                if isinstance(cluster['category_percentages'], dict):
                    for cat, pct in cluster['category_percentages'].items():
                        count = cluster['category_counts'].get(cat, 0)
                        report_lines.append(f"  {cat}: {count} races ({pct:.1f}%)")
                
                # Winning time characteristics
                report_lines.append(f"\nRace Duration:")
                report_lines.append(f"  Average: {cluster['avg_winning_time_hours']:.1f} hours")
                report_lines.append(f"  Median: {cluster['median_winning_time_hours']:.1f} hours")
                report_lines.append(f"  Range: {cluster['winning_time_range_hours']:.1f} hours")
                
                # BREAKPOINT ANALYSIS
                report_lines.append(f"\nBREAKDOWN POINT PATTERNS:")
                report_lines.append(f"  Kurtosis breakdown:")
                report_lines.append(f"    No breakdown: {cluster['pct_no_kurtosis_breakdown']:.1f}% of races")
                if cluster['kurtosis_breakdown_mean'] > 0:
                    report_lines.append(f"    Mean breakdown point: {cluster['kurtosis_breakdown_mean']:.1f}")
                    report_lines.append(f"    Most common: {int(cluster['most_common_kurtosis_breakdown'])}")
                
                report_lines.append(f"  Variance breakdown:")
                report_lines.append(f"    No breakdown: {cluster['pct_no_variance_breakdown']:.1f}% of races")
                if cluster['variance_breakdown_mean'] > 0:
                    report_lines.append(f"    Mean breakdown point: {cluster['variance_breakdown_mean']:.1f}")
                    report_lines.append(f"    Most common: {int(cluster['most_common_variance_breakdown'])}")
                
                # Key gradient features
                report_lines.append(f"\nKEY GRADIENT FEATURES:")
                for feature in ['nth_percentile_gap_5_slope', 'nth_percentile_gap_25_slope', 'nth_percentile_gap_5_volatility']:
                    if f'{feature}_mean' in cluster:
                        mean_val = cluster[f'{feature}_mean']
                        std_val = cluster[f'{feature}_std']
                        median_val = cluster[f'{feature}_median']
                        report_lines.append(f"  {feature}:")
                        report_lines.append(f"    Mean: {mean_val:.4f} ± {std_val:.4f}")
                        report_lines.append(f"    Median: {median_val:.4f}")
                        report_lines.append(f"    Range: [{cluster[f'{feature}_min']:.4f}, {cluster[f'{feature}_max']:.4f}]")
            
            # Breakpoint pattern analysis
            report_lines.append(f"\n\n{'='*60}")
            report_lines.append("BREAKPOINT PATTERN ANALYSIS")
            report_lines.append(f"{'='*60}")
            
            breakpoint_analysis = self.analyze_breakpoint_patterns(method)
            
            # Combined breakdown patterns
            report_lines.append(f"\nCOMBINED BREAKDOWN PATTERNS:")
            report_lines.append("-" * 35)
            for cluster_key, data in breakpoint_analysis['combined_breakdown_analysis'].items():
                cluster_num = cluster_key.split('_')[1]
                report_lines.append(f"\nCluster {cluster_num} ({data['total_races']} races):")
                patterns = data['pattern_percentages']
                report_lines.append(f"  Both break: {patterns['both_break']:.1f}%")
                report_lines.append(f"  Only kurtosis breaks: {patterns['only_kurtosis_breaks']:.1f}%")
                report_lines.append(f"  Only variance breaks: {patterns['only_variance_breaks']:.1f}%")
                report_lines.append(f"  Neither breaks: {patterns['neither_breaks']:.1f}%")
            
            # Detailed breakdown point distributions
            report_lines.append(f"\nKURTOSIS BREAKDOWN POINT DISTRIBUTIONS:")
            report_lines.append("-" * 45)
            for cluster_key, data in breakpoint_analysis['kurtosis_breakdown_analysis'].items():
                cluster_num = cluster_key.split('_')[1]
                report_lines.append(f"\nCluster {cluster_num}:")
                report_lines.append(f"  No breakdown: {data['no_breakdown_pct']:.1f}% ({data['no_breakdown_count']} races)")
                if data['breakdown_points']:
                    report_lines.append(f"  Breakdown points: {data['breakdown_points']}")
                    report_lines.append(f"  Mean breakdown: {data['mean_breakdown_point']:.1f}")
            
            report_lines.append(f"\nVARIANCE BREAKDOWN POINT DISTRIBUTIONS:")
            report_lines.append("-" * 45)
            for cluster_key, data in breakpoint_analysis['variance_breakdown_analysis'].items():
                cluster_num = cluster_key.split('_')[1]
                report_lines.append(f"\nCluster {cluster_num}:")
                report_lines.append(f"  No breakdown: {data['no_breakdown_pct']:.1f}% ({data['no_breakdown_count']} races)")
                if data['breakdown_points']:
                    report_lines.append(f"  Breakdown points: {data['breakdown_points']}")
                    report_lines.append(f"  Mean breakdown: {data['mean_breakdown_point']:.1f}")
        
        # Recommendations
        report_lines.append("\n\n" + "="*80)
        report_lines.append("RECOMMENDATIONS")
        report_lines.append("="*80)
        
        # Find best method
        best_method = max(self.clustering.clusters.keys(), 
                         key=lambda m: self.calculate_cluster_separability(m)['overall_silhouette'])
        
        report_lines.append(f"1. Best performing method: {best_method}")
        report_lines.append("2. Consider validating clusters with domain experts")
        report_lines.append("3. Test cluster assignments on new races for predictive validity")
        report_lines.append("4. Consider hybrid approach combining clustering with rule-based refinement")
        
        # Write report
        report_text = '\n'.join(report_lines)
        with open(output_file, 'w') as f:
            f.write(report_text)
        
        print(f"\nEvaluation report saved to {output_file}")
        return report_text
    
    def visualize_clusters(self, method: str = 'kmeans', 
                          output_file: str = 'race_kinds/race_kind_finding/cluster_visualization.png'):
        """Create visualization of clusters using PCA."""
        if method not in self.clustering.clusters:
            raise ValueError(f"Method {method} not found. Run clustering first.")
        
        labels = self.clustering.clusters[method]
        features = self.clustering.features
        
        # Reduce to 2D using PCA
        pca = PCA(n_components=2)
        features_2d = pca.fit_transform(features)
        
        # Create plot
        plt.figure(figsize=(10, 8))
        
        # Plot each cluster
        unique_labels = set(labels)
        colors = plt.cm.rainbow(np.linspace(0, 1, len(unique_labels)))
        
        for label, color in zip(sorted(unique_labels), colors):
            if label == -1:  # Noise
                color = 'gray'
                marker = 'x'
            else:
                marker = 'o'
            
            mask = labels == label
            plt.scatter(features_2d[mask, 0], features_2d[mask, 1], 
                       c=[color], marker=marker, s=50, alpha=0.6,
                       label=f'Cluster {label}' if label != -1 else 'Noise')
        
        plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)')
        plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)')
        plt.title(f'{method.capitalize()} Clustering Results (PCA projection)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(output_file, dpi=150)
        plt.close()
        
        print(f"Cluster visualization saved to {output_file}")
        
        # Save explained variance
        return {
            'pca_variance_explained': pca.explained_variance_ratio_.tolist(),
            'total_variance_explained': sum(pca.explained_variance_ratio_)
        }
    
    def save_detailed_analysis(self, output_dir: str = 'race_kinds/race_kind_finding'):
        """Save detailed cluster analysis to JSON files."""
        import json
        
        def convert_numpy_types(obj):
            """Convert numpy types to native Python types for JSON serialization."""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            else:
                return obj
        
        for method in self.clustering.clusters.keys():
            # Save detailed characteristics
            characteristics = self.evaluate_cluster_characteristics(method)
            characteristics_file = f'{output_dir}/{method}_detailed_characteristics.json'
            characteristics.to_json(characteristics_file, orient='records', indent=2)
            
            # Save breakpoint analysis with numpy type conversion
            breakpoint_analysis = self.analyze_breakpoint_patterns(method)
            breakpoint_analysis_converted = convert_numpy_types(breakpoint_analysis)
            breakpoint_file = f'{output_dir}/{method}_breakpoint_analysis.json'
            with open(breakpoint_file, 'w') as f:
                json.dump(breakpoint_analysis_converted, f, indent=2)
            
            print(f"Detailed analysis for {method} saved to {output_dir}/")
        
        return True


def main():
    """Run the evaluation pipeline."""
    from unsupervised_clustering import RaceKindClustering
    
    # Initialize and run clustering (will auto-find database)
    clustering = RaceKindClustering()
    clustering.load_stage_race_data(min_finishers=40)
    clustering.prepare_features()
    
    # Run clustering methods
    clustering.kmeans_clustering(range(3, 6))
    clustering.hierarchical_clustering(range(3, 6))
    
    # Initialize evaluator
    evaluator = ClusteringEvaluator(clustering)
    
    # Generate evaluation report
    evaluator.generate_evaluation_report()
    
    # Save detailed analysis
    evaluator.save_detailed_analysis()
    
    # Create visualizations
    for method in clustering.clusters.keys():
        evaluator.visualize_clusters(method, 
                                   f'race_kinds/race_kind_finding/{method}_visualization.png')
    
    # Save detailed results
    clustering.save_results()
    clustering.close()
    
    print("\nEvaluation complete!")


if __name__ == "__main__":
    main()