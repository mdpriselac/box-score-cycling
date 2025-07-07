"""
Race Kind Evaluation Framework

This module provides a comprehensive framework for evaluating different race kind
identification methods across multiple percentile tables. It generates detailed
reports comparing the effectiveness of various clustering and scoring approaches.
"""

import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime
import json
import os
from typing import Dict, List, Tuple, Optional, Any
import matplotlib.pyplot as plt
import seaborn as sns
from race_kind_analysis import RaceKindAnalyzer
import warnings
warnings.filterwarnings('ignore')


class RaceKindEvaluator:
    """
    Evaluates and compares different race kind identification methods.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the evaluator.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.results = {}
        self.analyzer = RaceKindAnalyzer(db_path)
        
    def get_available_percentile_tables(self) -> List[str]:
        """
        Get list of available race_features tables in the database.
        
        Returns:
            List of table names
        """
        conn = sqlite3.connect(self.db_path)
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'race_features_%'
        ORDER BY name
        """
        tables = pd.read_sql_query(query, conn)['name'].tolist()
        conn.close()
        return tables
    
    def evaluate_single_percentile(
        self,
        table_name: str,
        competition_type: Optional[str] = None,
        race_categories: Optional[List[str]] = None,
        methods: List[str] = None,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluate all methods on a single percentile table.
        
        Args:
            table_name: Name of the percentile table
            competition_type: Filter by competition type
            race_categories: Filter by race categories (e.g., ['wt', 'pro'])
            methods: List of methods to evaluate (None for all)
            verbose: Print progress messages
            
        Returns:
            Dictionary with evaluation results for each method
        """
        if verbose:
            print(f"\nEvaluating {table_name}...")
        
        # Load and prepare data
        if race_categories and len(race_categories) > 1:
            # Load and combine data from multiple categories
            all_data = []
            for category in race_categories:
                cat_data = self.analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                all_data.append(cat_data)
            
            # Combine data from all categories
            import pandas as pd
            self.analyzer.data = pd.concat(all_data, ignore_index=True)
        else:
            # Single category or no category filtering
            category = race_categories[0] if race_categories else None
            self.analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
        
        if len(self.analyzer.data) < 30:
            if verbose:
                print(f"  Skipping {table_name}: insufficient data ({len(self.analyzer.data)} races)")
            return {}
        
        self.analyzer.prepare_features(scaling_method='robust')
        
        if methods is None:
            methods = ['kmeans', 'hierarchical', 'dbscan', 'gaussian_mixture', 'pca', 'feature_based']
        
        results = {
            'table_name': table_name,
            'n_races': len(self.analyzer.data),
            'competition_type': competition_type,
            'methods': {}
        }
        
        # Evaluate each method
        for method in methods:
            if verbose:
                print(f"  Testing {method}...")
            
            try:
                if method == 'kmeans':
                    method_results = self.analyzer.kmeans_clustering(range(2, min(11, len(self.analyzer.data)//5)))
                    stability = self.analyzer.evaluate_clustering_stability(method_results)
                    method_results['stability'] = stability
                    
                elif method == 'hierarchical':
                    method_results = self.analyzer.hierarchical_clustering(range(2, min(11, len(self.analyzer.data)//5)))
                    stability = self.analyzer.evaluate_clustering_stability(method_results)
                    method_results['stability'] = stability
                    
                elif method == 'dbscan':
                    method_results = self.analyzer.dbscan_clustering()
                    
                elif method == 'gaussian_mixture':
                    method_results = self.analyzer.gaussian_mixture_clustering(range(2, min(11, len(self.analyzer.data)//5)))
                    
                elif method == 'pca':
                    method_results = self.analyzer.pca_analysis()
                    
                elif method == 'feature_based':
                    method_results = self.analyzer.feature_based_scoring()
                
                # Add cluster characteristics for applicable methods
                if method in ['kmeans', 'hierarchical'] and 'best_n_clusters' in method_results:
                    best_n = method_results['best_n_clusters']
                    if best_n and best_n in method_results['cluster_results']:
                        labels = method_results['cluster_results'][best_n]['labels']
                        method_results['cluster_characteristics'] = self.analyzer.get_cluster_characteristics(labels)
                
                results['methods'][method] = method_results
                
            except Exception as e:
                if verbose:
                    print(f"    Error in {method}: {str(e)}")
                results['methods'][method] = {'error': str(e)}
        
        return results
    
    def evaluate_all_percentiles(
        self,
        competition_type: Optional[str] = None,
        race_categories: Optional[List[str]] = None,
        methods: List[str] = None,
        tables: List[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate methods across all percentile tables.
        
        Args:
            competition_type: Filter by competition type
            race_categories: Filter by race categories
            methods: List of methods to evaluate
            tables: List of tables to evaluate (None for all)
            
        Returns:
            Dictionary with all evaluation results
        """
        if tables is None:
            tables = self.get_available_percentile_tables()
        
        all_results = {}
        
        for table in tables:
            results = self.evaluate_single_percentile(
                table,
                competition_type=competition_type,
                race_categories=race_categories,
                methods=methods
            )
            if results:
                all_results[table] = results
        
        self.results = all_results
        return all_results
    
    def compare_method_performance(self) -> pd.DataFrame:
        """
        Create a comparison table of method performance across percentiles.
        
        Returns:
            DataFrame with performance metrics
        """
        if not self.results:
            raise ValueError("No results available. Run evaluation first.")
        
        comparison_data = []
        
        for table, table_results in self.results.items():
            percentile = int(table.split('_')[-1])
            
            for method, method_results in table_results['methods'].items():
                if 'error' in method_results:
                    continue
                
                row = {
                    'percentile': percentile,
                    'table': table,
                    'method': method,
                    'n_races': table_results['n_races']
                }
                
                # Extract relevant metrics based on method
                if method in ['kmeans', 'hierarchical']:
                    if 'best_n_clusters' in method_results:
                        row['best_n_clusters'] = method_results['best_n_clusters']
                        row['best_score'] = method_results['best_score']
                        
                        # Get metrics for best clustering
                        best_n = method_results['best_n_clusters']
                        if best_n in method_results['evaluation_metrics']:
                            metrics = method_results['evaluation_metrics'][best_n]
                            row.update(metrics)
                        
                        # Add stability metrics
                        if 'stability' in method_results:
                            row['stability_mean'] = method_results['stability']['stability_mean']
                            row['stability_std'] = method_results['stability']['stability_std']
                
                elif method == 'gaussian_mixture':
                    if 'best_n_components' in method_results:
                        row['best_n_components'] = method_results['best_n_components']
                        best_n = method_results['best_n_components']
                        if best_n in method_results['evaluation_metrics']:
                            metrics = method_results['evaluation_metrics'][best_n]
                            row.update(metrics)
                
                elif method == 'dbscan':
                    if 'best_params' in method_results and method_results['best_params']:
                        row['best_eps'] = method_results['best_params']['eps']
                        row['best_min_samples'] = method_results['best_params']['min_samples']
                        row['best_score'] = method_results['best_score']
                
                elif method == 'pca':
                    row['n_components_95'] = method_results['n_components_95']
                    row['variance_explained_pc1'] = method_results['explained_variance_ratio'][0]
                    row['variance_explained_pc2'] = method_results['explained_variance_ratio'][1] if len(method_results['explained_variance_ratio']) > 1 else 0
                
                comparison_data.append(row)
        
        return pd.DataFrame(comparison_data)
    
    def evaluate_cross_percentile_stability(
        self,
        method: str = 'kmeans'
    ) -> Dict[str, Any]:
        """
        Evaluate how stable race groupings are across different percentiles.
        
        Args:
            method: Clustering method to use
            
        Returns:
            Dictionary with stability analysis
        """
        if not self.results:
            raise ValueError("No results available. Run evaluation first.")
        
        # Get race IDs that appear in multiple tables
        race_appearances = {}
        
        for table, table_results in self.results.items():
            if method not in table_results['methods'] or 'error' in table_results['methods'][method]:
                continue
            
            # Get competition IDs from the data
            comp_ids = self.analyzer.load_data(table)['competition_id'].tolist()
            
            for comp_id in comp_ids:
                if comp_id not in race_appearances:
                    race_appearances[comp_id] = {}
                
                # Get cluster assignment for this race
                method_results = table_results['methods'][method]
                if 'best_n_clusters' in method_results:
                    best_n = method_results['best_n_clusters']
                    if best_n in method_results['cluster_results']:
                        # Find index of this competition
                        try:
                            idx = comp_ids.index(comp_id)
                            labels = method_results['cluster_results'][best_n]['labels']
                            race_appearances[comp_id][table] = labels[idx]
                        except:
                            pass
        
        # Analyze consistency
        consistency_scores = []
        
        for comp_id, appearances in race_appearances.items():
            if len(appearances) > 1:
                # Check if race stays in similar clusters across percentiles
                cluster_values = list(appearances.values())
                # Simple consistency: standard deviation of cluster assignments
                consistency = 1.0 / (1.0 + np.std(cluster_values))
                consistency_scores.append(consistency)
        
        return {
            'method': method,
            'n_races_analyzed': len(consistency_scores),
            'mean_consistency': float(np.mean(consistency_scores)) if consistency_scores else 0,
            'std_consistency': float(np.std(consistency_scores)) if consistency_scores else 0,
            'consistency_distribution': consistency_scores
        }
    
    def generate_report(
        self,
        output_dir: str = 'database/race_kinds/reports',
        include_plots: bool = True
    ) -> str:
        """
        Generate a comprehensive evaluation report.
        
        Args:
            output_dir: Directory to save report files
            include_plots: Whether to generate visualization plots
            
        Returns:
            Path to the main report file
        """
        if not self.results:
            raise ValueError("No results available. Run evaluation first.")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_name = f"race_kind_evaluation_{timestamp}"
        
        # Generate comparison table
        comparison_df = self.compare_method_performance()
        
        # Create main report
        report_path = os.path.join(output_dir, f"{report_name}.md")
        
        with open(report_path, 'w') as f:
            f.write("# Race Kind Evaluation Report\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary statistics
            f.write("## Summary\n\n")
            f.write(f"- Evaluated {len(self.results)} percentile tables\n")
            f.write(f"- Tested {len(comparison_df['method'].unique())} methods\n")
            f.write(f"- Total evaluations: {len(comparison_df)}\n\n")
            
            # Method performance summary
            f.write("## Method Performance Summary\n\n")
            
            for method in comparison_df['method'].unique():
                method_data = comparison_df[comparison_df['method'] == method]
                f.write(f"### {method.replace('_', ' ').title()}\n\n")
                
                if method in ['kmeans', 'hierarchical']:
                    if 'silhouette_score' in method_data.columns:
                        f.write(f"- Mean Silhouette Score: {method_data['silhouette_score'].mean():.3f} ± {method_data['silhouette_score'].std():.3f}\n")
                    if 'stability_mean' in method_data.columns:
                        f.write(f"- Mean Stability: {method_data['stability_mean'].mean():.3f} ± {method_data['stability_mean'].std():.3f}\n")
                    if 'best_n_clusters' in method_data.columns:
                        f.write(f"- Typical number of clusters: {method_data['best_n_clusters'].mode().iloc[0] if len(method_data) > 0 else 'N/A'}\n")
                
                f.write("\n")
            
            # Detailed results by percentile
            f.write("## Detailed Results by Percentile\n\n")
            
            for table in sorted(self.results.keys()):
                percentile = table.split('_')[-1]
                f.write(f"### {percentile}th Percentile\n\n")
                
                table_results = self.results[table]
                f.write(f"- Number of races: {table_results['n_races']}\n\n")
                
                # Best performing method
                best_method = None
                best_score = -np.inf
                
                for method, method_results in table_results['methods'].items():
                    if 'error' not in method_results and 'best_score' in method_results:
                        if method_results['best_score'] > best_score:
                            best_score = method_results['best_score']
                            best_method = method
                
                if best_method:
                    f.write(f"- Best performing method: **{best_method}** (score: {best_score:.3f})\n\n")
                
                # Cluster characteristics for best method
                if best_method and 'cluster_characteristics' in table_results['methods'][best_method]:
                    f.write("#### Cluster Characteristics\n\n")
                    chars = table_results['methods'][best_method]['cluster_characteristics']
                    
                    for cluster_id, cluster_info in sorted(chars.items()):
                        f.write(f"**Cluster {cluster_id}** ({cluster_info['size']} races, {cluster_info['percentage']:.1f}%)\n")
                        f.write("- Top distinguishing features:\n")
                        for feat in cluster_info['top_features'][:3]:
                            f.write(f"  - {feat['name']}: {feat['cluster_mean']:.3f} (vs {feat['overall_mean']:.3f})\n")
                        f.write("\n")
            
            # Cross-percentile stability
            f.write("## Cross-Percentile Stability Analysis\n\n")
            
            for method in ['kmeans', 'hierarchical']:
                stability_results = self.evaluate_cross_percentile_stability(method)
                f.write(f"### {method.title()}\n")
                f.write(f"- Races analyzed: {stability_results['n_races_analyzed']}\n")
                f.write(f"- Mean consistency: {stability_results['mean_consistency']:.3f}\n")
                f.write(f"- Std consistency: {stability_results['std_consistency']:.3f}\n\n")
            
            # Recommendations
            f.write("## Recommendations\n\n")
            f.write(self._generate_recommendations(comparison_df))
        
        # Save detailed results as JSON
        json_path = os.path.join(output_dir, f"{report_name}_detailed.json")
        with open(json_path, 'w') as f:
            # Convert numpy types to Python types for JSON serialization
            json_results = self._prepare_for_json(self.results)
            json.dump(json_results, f, indent=2)
        
        # Save comparison table as CSV
        csv_path = os.path.join(output_dir, f"{report_name}_comparison.csv")
        comparison_df.to_csv(csv_path, index=False)
        
        # Generate plots if requested
        if include_plots:
            self._generate_plots(comparison_df, output_dir, report_name)
        
        print(f"\nReport generated: {report_path}")
        return report_path
    
    def _generate_recommendations(self, comparison_df: pd.DataFrame) -> str:
        """Generate recommendations based on evaluation results."""
        recommendations = []
        
        # Find best overall method
        if 'silhouette_score' in comparison_df.columns:
            method_scores = comparison_df.groupby('method')['silhouette_score'].mean().sort_values(ascending=False)
            if len(method_scores) > 0:
                best_method = method_scores.index[0]
                best_score = method_scores.iloc[0]
                recommendations.append(
                    f"1. **Best overall clustering method**: {best_method} "
                    f"(mean silhouette score: {best_score:.3f})"
                )
        
        # Find most stable method
        if 'stability_mean' in comparison_df.columns:
            stability_scores = comparison_df.groupby('method')['stability_mean'].mean().sort_values(ascending=False)
            if len(stability_scores) > 0:
                most_stable = stability_scores.index[0]
                recommendations.append(
                    f"2. **Most stable method**: {most_stable} "
                    f"(mean stability: {stability_scores.iloc[0]:.3f})"
                )
        
        # Optimal percentile
        percentile_scores = comparison_df.groupby('percentile').agg({
            'silhouette_score': 'mean',
            'stability_mean': 'mean'
        }).mean(axis=1).sort_values(ascending=False)
        
        if len(percentile_scores) > 0:
            best_percentile = percentile_scores.index[0]
            recommendations.append(
                f"3. **Optimal percentile for analysis**: {best_percentile}th percentile"
            )
        
        # Feature-based vs clustering
        recommendations.append(
            "4. **Consider combining approaches**: Use clustering for initial grouping "
            "and feature-based scoring for interpretation"
        )
        
        return "\n".join(recommendations)
    
    def _prepare_for_json(self, obj: Any) -> Any:
        """Convert numpy types to Python types for JSON serialization."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self._prepare_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._prepare_for_json(item) for item in obj]
        else:
            return obj
    
    def _generate_plots(self, comparison_df: pd.DataFrame, output_dir: str, report_name: str):
        """Generate visualization plots for the report."""
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # Plot 1: Silhouette scores by method and percentile
        if 'silhouette_score' in comparison_df.columns:
            plt.figure(figsize=(10, 6))
            pivot_data = comparison_df.pivot_table(
                values='silhouette_score',
                index='percentile',
                columns='method',
                aggfunc='mean'
            )
            pivot_data.plot(marker='o')
            plt.title('Silhouette Scores by Method and Percentile')
            plt.xlabel('Percentile')
            plt.ylabel('Silhouette Score')
            plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{report_name}_silhouette_scores.png"))
            plt.close()
        
        # Plot 2: Stability scores
        if 'stability_mean' in comparison_df.columns:
            plt.figure(figsize=(8, 6))
            stability_data = comparison_df[comparison_df['stability_mean'].notna()]
            sns.boxplot(data=stability_data, x='method', y='stability_mean')
            plt.title('Clustering Stability by Method')
            plt.xlabel('Method')
            plt.ylabel('Stability Score')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{report_name}_stability.png"))
            plt.close()
        
        # Plot 3: Optimal number of clusters
        if 'best_n_clusters' in comparison_df.columns:
            plt.figure(figsize=(8, 6))
            cluster_data = comparison_df[comparison_df['best_n_clusters'].notna()]
            sns.boxplot(data=cluster_data, x='percentile', y='best_n_clusters')
            plt.title('Optimal Number of Clusters by Percentile')
            plt.xlabel('Percentile')
            plt.ylabel('Number of Clusters')
            plt.tight_layout()
            plt.savefig(os.path.join(output_dir, f"{report_name}_n_clusters.png"))
            plt.close()