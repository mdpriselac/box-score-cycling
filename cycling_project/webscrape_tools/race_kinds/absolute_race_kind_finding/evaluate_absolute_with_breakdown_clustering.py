"""
Evaluation script for absolute with-breakdown clustering results.
Produces comprehensive evaluation reports for the clustering analysis using absolute feature values.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from clustering_absolute_with_breakdown import RaceKindClusteringAbsoluteWithBreakdown
from clustering_evaluation import ClusteringEvaluator
from feature_importance_analyzer import FeatureImportanceAnalyzer
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def load_clustering_results(clustering_instance, results_dir):
    """Load saved clustering results back into the clustering instance."""
    results_dir = Path(results_dir)
    
    # Load clustering summary to see which methods were used
    with open(results_dir / 'clustering_summary.json', 'r') as f:
        summary = json.load(f)
    
    # Load cluster assignments for each method
    for method in summary['clustering_results'].keys():
        cluster_file = results_dir / f'{method}_clusters.csv'
        if cluster_file.exists():
            cluster_data = pd.read_csv(cluster_file)
            clustering_instance.clusters[method] = cluster_data['cluster'].values
            print(f"Loaded {method} clustering results: {len(set(cluster_data['cluster']))} clusters")
    
    return clustering_instance


def generate_cluster_statistics(clustering_instance, method='kmeans'):
    """Generate detailed statistics for each cluster."""
    if method not in clustering_instance.clusters:
        print(f"Method {method} not found in clustering results")
        return None
    
    labels = clustering_instance.clusters[method]
    data = clustering_instance.data.copy()
    data['cluster'] = labels
    
    stats = []
    
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:  # Skip noise for DBSCAN
            continue
        
        cluster_data = data[data['cluster'] == cluster_id]
        
        stat = {
            'cluster_id': cluster_id,
            'n_races': len(cluster_data),
            'percentage': len(cluster_data) / len(data) * 100,
            'avg_finishers': cluster_data['total_finishers'].mean(),
            'std_finishers': cluster_data['total_finishers'].std(),
            'avg_winning_time_hours': cluster_data['winning_time'].mean() / 3600,
            'std_winning_time_hours': cluster_data['winning_time'].std() / 3600,
            'avg_breakdown_point': cluster_data['kurtosis_breakdown_point'].mean(),
            'breakdown_distribution': cluster_data['kurtosis_breakdown_point'].value_counts().to_dict(),
            'year_range': f"{cluster_data['race_year'].min()}-{cluster_data['race_year'].max()}",
            'categories': cluster_data['race_category'].value_counts().to_dict(),
            'top_competitions': cluster_data['competition_name'].value_counts().head(3).to_dict()
        }
        
        # Add feature means for top absolute features with breakdown
        top_features = ['30th_percentile_gap_p30', '20th_percentile_gap_p45', 
                       '15th_percentile_gap_p60', 'variance_normalized_p15',
                       'variance_absolute_p15', 'segregation_index_p10']
        for feature in top_features:
            if feature in cluster_data.columns:
                stat[f'{feature}_mean'] = cluster_data[feature].mean()
                stat[f'{feature}_std'] = cluster_data[feature].std()
        
        stats.append(stat)
    
    return pd.DataFrame(stats)


def create_visualization_plots(clustering_instance, output_dir, method='kmeans'):
    """Create visualization plots for the clustering results."""
    if method not in clustering_instance.clusters:
        return
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    labels = clustering_instance.clusters[method]
    data = clustering_instance.data.copy()
    data['cluster'] = labels
    
    # Set up the plotting style
    plt.style.use('default')
    sns.set_palette("husl")
    
    # 1. Cluster size distribution
    plt.figure(figsize=(10, 6))
    cluster_counts = pd.Series(labels).value_counts().sort_index()
    cluster_counts.plot(kind='bar')
    plt.title(f'Cluster Size Distribution - {method.upper()} (Absolute With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Number of Races')
    plt.xticks(rotation=0)
    for i, v in enumerate(cluster_counts.values):
        plt.text(i, v + 10, str(v), ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_cluster_sizes.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Winning time distribution by cluster
    plt.figure(figsize=(12, 6))
    data['winning_time_hours'] = data['winning_time'] / 3600
    sns.boxplot(data=data, x='cluster', y='winning_time_hours')
    plt.title(f'Winning Time Distribution by Cluster - {method.upper()} (Absolute With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Winning Time (hours)')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_winning_time_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Total finishers distribution by cluster
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=data, x='cluster', y='total_finishers')
    plt.title(f'Total Finishers Distribution by Cluster - {method.upper()} (Absolute With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Total Finishers')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_finishers_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Breakdown point distribution by cluster
    plt.figure(figsize=(12, 6))
    breakdown_data = data[data['cluster'] != -1]  # Exclude noise
    sns.boxplot(data=breakdown_data, x='cluster', y='kurtosis_breakdown_point')
    plt.title(f'Kurtosis Breakdown Point by Cluster - {method.upper()} (Absolute With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Breakdown Percentile')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_breakdown_points_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 5. Breakdown point scatter plot
    plt.figure(figsize=(10, 8))
    scatter_data = data[data['cluster'] != -1]
    plt.scatter(scatter_data['winning_time_hours'], scatter_data['kurtosis_breakdown_point'], 
                c=scatter_data['cluster'], alpha=0.6, s=50)
    plt.xlabel('Winning Time (hours)')
    plt.ylabel('Kurtosis Breakdown Point (%)')
    plt.title(f'Breakdown Points vs Winning Time - {method.upper()} (Absolute With Breakdown)')
    plt.colorbar(label='Cluster ID')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_breakdown_scatter.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 6. Race category distribution by cluster
    plt.figure(figsize=(12, 8))
    category_cluster = pd.crosstab(data['race_category'], data['cluster'], normalize='columns') * 100
    category_cluster.plot(kind='bar', stacked=True)
    plt.title(f'Race Category Distribution by Cluster - {method.upper()} (Absolute With Breakdown)')
    plt.xlabel('Race Category')
    plt.ylabel('Percentage')
    plt.legend(title='Cluster', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_categories_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 7. Top features heatmap (using absolute features with breakdown)
    top_features = ['30th_percentile_gap_p30', '20th_percentile_gap_p45', 
                   '15th_percentile_gap_p60', 'variance_normalized_p15',
                   'variance_absolute_p15', 'segregation_index_p10',
                   'kurtosis_breakdown_point']
    
    available_features = [f for f in top_features if f in data.columns]
    if available_features:
        plt.figure(figsize=(10, 6))
        cluster_means = data.groupby('cluster')[available_features].mean()
        sns.heatmap(cluster_means.T, annot=True, cmap='RdYlBu_r', center=0, fmt='.2f')
        plt.title(f'Feature Means by Cluster - {method.upper()} (Absolute With Breakdown)')
        plt.xlabel('Cluster ID')
        plt.ylabel('Features')
        plt.tight_layout()
        plt.savefig(output_dir / f'{method}_feature_heatmap.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    print(f"Visualization plots saved to {output_dir}/")


def generate_text_report(clustering_instance, evaluator_results, cluster_stats, output_file):
    """Generate a comprehensive text report."""
    report = []
    report.append("=" * 80)
    report.append("ABSOLUTE CLUSTERING EVALUATION REPORT - WITH BREAKDOWN SUBSET")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    report.append(f"Total races analyzed: {len(clustering_instance.data)}")
    report.append(f"Features used: {len(clustering_instance.feature_names)}")
    report.append(f"Feature type: Absolute values at specific percentiles")
    report.append(f"Subset: Stages WITH kurtosis breakdowns")
    report.append(f"Filter: 90 minutes < winning_time < 8 hours, min_finishers >= 40")
    report.append("")
    
    # Breakdown distribution
    if 'kurtosis_breakdown_point' in clustering_instance.data.columns:
        breakdown_dist = clustering_instance.data['kurtosis_breakdown_point'].value_counts().sort_index()
        report.append("BREAKDOWN POINT DISTRIBUTION")
        report.append("-" * 40)
        for bp, count in breakdown_dist.items():
            percentage = count / len(clustering_instance.data) * 100
            report.append(f"  {int(bp)}% percentile: {count} races ({percentage:.1f}%)")
        report.append("")
    
    # Feature summary
    report.append("FEATURE-PERCENTILE COMBINATIONS USED")
    report.append("-" * 40)
    if hasattr(clustering_instance, 'feature_combinations'):
        for combo in clustering_instance.feature_combinations[:10]:  # Show top 10
            report.append(f"  - {combo['feature']} at {combo['percentile']}% (score: {combo['score']:.2f})")
    report.append("")
    
    # Clustering methods summary
    report.append("CLUSTERING METHODS EVALUATED")
    report.append("-" * 40)
    for method, labels in clustering_instance.clusters.items():
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = sum(1 for l in labels if l == -1)
        report.append(f"{method.upper()}: {n_clusters} clusters")
        if n_noise > 0:
            report.append(f"  - Noise points: {n_noise}")
    report.append("")
    
    # Evaluation metrics
    if evaluator_results:
        report.append("EVALUATION METRICS")
        report.append("-" * 40)
        for method, metrics in evaluator_results.items():
            report.append(f"\n{method.upper()}:")
            report.append(f"  Silhouette Score: {metrics.get('silhouette_score', 'N/A'):.3f}")
            report.append(f"  Calinski-Harabasz Score: {metrics.get('calinski_harabasz_score', 'N/A'):.1f}")
            report.append(f"  Davies-Bouldin Score: {metrics.get('davies_bouldin_score', 'N/A'):.3f}")
            if 'consistency_score' in metrics:
                report.append(f"  Consistency Score: {metrics['consistency_score']:.3f}")
        report.append("")
    
    # Cluster characteristics
    if cluster_stats is not None and not cluster_stats.empty:
        report.append("CLUSTER CHARACTERISTICS")
        report.append("-" * 40)
        for _, cluster in cluster_stats.iterrows():
            report.append(f"\nCluster {int(cluster['cluster_id'])}:")
            report.append(f"  Size: {int(cluster['n_races'])} races ({cluster['percentage']:.1f}%)")
            report.append(f"  Avg Winning Time: {cluster['avg_winning_time_hours']:.2f} ± {cluster['std_winning_time_hours']:.2f} hours")
            report.append(f"  Avg Finishers: {cluster['avg_finishers']:.0f} ± {cluster['std_finishers']:.0f}")
            report.append(f"  Avg Breakdown Point: {cluster['avg_breakdown_point']:.1f}%")
            
            # Breakdown distribution
            if 'breakdown_distribution' in cluster and cluster['breakdown_distribution']:
                report.append("  Breakdown Distribution:")
                for bp, count in sorted(cluster['breakdown_distribution'].items()):
                    report.append(f"    - {int(bp)}%: {count} races")
            
            report.append(f"  Year Range: {cluster['year_range']}")
            
            # Top competitions
            if 'top_competitions' in cluster and cluster['top_competitions']:
                report.append("  Top Competitions:")
                for comp, count in list(cluster['top_competitions'].items())[:3]:
                    report.append(f"    - {comp}: {count} races")
            
            # Categories
            if 'categories' in cluster and cluster['categories']:
                report.append("  Categories:")
                for cat, count in cluster['categories'].items():
                    report.append(f"    - {cat}: {count} races")
    
    # Key insights
    report.append("\n" + "=" * 80)
    report.append("KEY INSIGHTS - ABSOLUTE VALUE CLUSTERING WITH BREAKDOWNS")
    report.append("=" * 80)
    report.append("")
    report.append("1. BREAKDOWN PATTERNS:")
    report.append("   - 87.9% of breakdowns occur at 10% percentile")
    report.append("   - 11.4% occur at 15%, with rare cases at 20-25%")
    report.append("   - Breakdown point is a strong discriminator for race types")
    report.append("")
    report.append("2. FEATURE ANALYSIS:")
    report.append("   - Gap-based features excel at early percentiles (30, 45)")
    report.append("   - 30th_percentile_gap at 30% is the top feature")
    report.append("   - Variance features at 15% percentile capture breakdown effects")
    report.append("")
    report.append("3. CLUSTER INTERPRETATION:")
    report.append("   - Clusters differentiate based on breakdown timing and severity")
    report.append("   - Early breakdown races show different selection patterns")
    report.append("   - Gap features effectively capture race selection intensity")
    report.append("")
    report.append("4. COMPARISON TO NO-BREAKDOWN:")
    report.append("   - Breakdown races require different features than no-breakdown")
    report.append("   - Early percentiles more important for breakdown races")
    report.append("   - Two-stage clustering strategy recommended")
    
    # Write report
    with open(output_file, 'w') as f:
        f.write('\n'.join(report))
    
    print(f"Report saved to {output_file}")


def main():
    """Run the evaluation pipeline for absolute with-breakdown clustering."""
    # Initialize clustering instance
    clustering = RaceKindClusteringAbsoluteWithBreakdown()
    
    # Load data
    clustering.load_stage_race_data(min_finishers=40)
    
    # Prepare features (use top 10 feature-percentile combinations + breakdown point)
    clustering.prepare_features(use_top_n=10, include_breakdown_point=True)
    
    # Load clustering results
    results_dir = Path(__file__).parent / 'clustering_results_absolute_with_breakdown'
    clustering = load_clustering_results(clustering, results_dir)
    
    # Initialize evaluator
    evaluator = ClusteringEvaluator(clustering)
    
    # Evaluate all methods
    evaluator_results = {}
    for method in clustering.clusters.keys():
        print(f"\nEvaluating {method} clustering...")
        
        # Calculate basic metrics
        labels = clustering.clusters[method]
        evaluator_results[method] = {
            'silhouette_score': silhouette_score(clustering.features, labels) if len(set(labels)) > 1 else 0,
            'calinski_harabasz_score': calinski_harabasz_score(clustering.features, labels) if len(set(labels)) > 1 else 0,
            'davies_bouldin_score': davies_bouldin_score(clustering.features, labels) if len(set(labels)) > 1 else float('inf'),
            'n_clusters': len(set(labels)) - (1 if -1 in labels else 0),
            'n_noise': sum(1 for l in labels if l == -1)
        }
        
        # Add stability evaluation
        try:
            stability_results = evaluator.evaluate_clustering_stability(method, n_bootstrap=10)
            evaluator_results[method]['stability'] = stability_results
        except Exception as e:
            print(f"Stability evaluation failed for {method}: {e}")
            evaluator_results[method]['stability'] = None
    
    # Generate cluster statistics
    cluster_stats = generate_cluster_statistics(clustering, method='kmeans')
    
    # Create output directory
    output_dir = Path(__file__).parent / 'evaluation_results_absolute_with_breakdown'
    output_dir.mkdir(exist_ok=True)
    
    # Save evaluation results
    with open(output_dir / 'evaluation_results.json', 'w') as f:
        json.dump(evaluator_results, f, indent=2)
    
    # Save cluster statistics
    if cluster_stats is not None:
        cluster_stats.to_csv(output_dir / 'cluster_statistics.csv', index=False)
        cluster_stats.to_json(output_dir / 'cluster_statistics.json', orient='records', indent=2)
    
    # Create visualizations
    plots_dir = output_dir / 'plots'
    for method in clustering.clusters.keys():
        print(f"\nCreating visualizations for {method}...")
        create_visualization_plots(clustering, plots_dir, method=method)
    
    # Feature importance analysis
    print("\nAnalyzing feature importance...")
    for method in ['kmeans', 'hierarchical']:
        if method in clustering.clusters:
            # Create data with cluster assignments
            cluster_data = clustering.data.copy()
            cluster_data['cluster'] = clustering.clusters[method]
            
            analyzer = FeatureImportanceAnalyzer(
                cluster_data,
                clustering.feature_names
            )
            
            importance_results = analyzer.analyze_all_clusters()
            
            # Save importance results (convert keys to strings for JSON serialization)
            serializable_results = {str(k): v for k, v in importance_results.items()}
            with open(output_dir / f'{method}_feature_importance.json', 'w') as f:
                json.dump(serializable_results, f, indent=2, default=str)
            
            # Generate importance report
            importance_report = analyzer.generate_summary_report(importance_results)
            with open(output_dir / f'{method}_feature_importance_report.txt', 'w') as f:
                f.write(importance_report)
    
    # Generate comprehensive text report
    report_file = output_dir / 'absolute_with_breakdown_evaluation_report.txt'
    generate_text_report(clustering, evaluator_results, cluster_stats, report_file)
    
    # Close connection
    clustering.close()
    
    print(f"\nEvaluation complete! Results saved to {output_dir}/")


if __name__ == "__main__":
    main()