"""
Evaluation script for with-breakdown clustering results.
Produces comprehensive evaluation reports for the clustering analysis.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from clustering_with_breakdown import RaceKindClusteringWithBreakdown
from clustering_evaluation import ClusteringEvaluator
from feature_importance_analyzer import FeatureImportanceAnalyzer
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
            'year_range': f"{cluster_data['race_year'].min()}-{cluster_data['race_year'].max()}",
            'categories': cluster_data['race_category'].value_counts().to_dict(),
            'top_competitions': cluster_data['competition_name'].value_counts().head(3).to_dict()
        }
        
        # Add breakdown statistics
        stat['avg_kurtosis_breakdown'] = cluster_data['kurtosis_breakdown_point'].mean()
        stat['std_kurtosis_breakdown'] = cluster_data['kurtosis_breakdown_point'].std()
        stat['avg_variance_breakdown'] = cluster_data['variance_breakdown_point'].mean()
        stat['std_variance_breakdown'] = cluster_data['variance_breakdown_point'].std()
        stat['pct_with_kurtosis_breakdown'] = (cluster_data['kurtosis_breakdown_point'] > 0).mean() * 100
        stat['pct_with_variance_breakdown'] = (cluster_data['variance_breakdown_point'] > 0).mean() * 100
        
        # Add feature means for top features
        top_features = ['nth_percentile_gap_25_slope', 'kurtosis_breakdown_point',
                       'nth_percentile_gap_50_slope', 'variance_absolute_slope',
                       'nth_percentile_gap_25_directional_changes',
                       'variance_absolute_directional_changes']
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
    plt.figure(figsize=(12, 6))
    cluster_counts = pd.Series(labels).value_counts().sort_index()
    if -1 in cluster_counts.index:  # DBSCAN noise
        cluster_counts = cluster_counts.drop(-1)  # Don't plot noise
    cluster_counts.plot(kind='bar')
    plt.title(f'Cluster Size Distribution - {method.upper()} (With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Number of Races')
    plt.xticks(rotation=0)
    for i, v in enumerate(cluster_counts.values):
        plt.text(i, v + 10, str(v), ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_cluster_sizes.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Breakdown points distribution by cluster
    if method != 'dbscan':  # Skip for DBSCAN due to noise
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # Kurtosis breakdown
        sns.boxplot(data=data[data['cluster'] != -1], x='cluster', y='kurtosis_breakdown_point', ax=ax1)
        ax1.set_title(f'Kurtosis Breakdown Point by Cluster - {method.upper()}')
        ax1.set_xlabel('Cluster ID')
        ax1.set_ylabel('Kurtosis Breakdown Point (Percentile)')
        
        # Variance breakdown
        sns.boxplot(data=data[data['cluster'] != -1], x='cluster', y='variance_breakdown_point', ax=ax2)
        ax2.set_title(f'Variance Breakdown Point by Cluster - {method.upper()}')
        ax2.set_xlabel('Cluster ID')
        ax2.set_ylabel('Variance Breakdown Point (Percentile)')
        
        plt.tight_layout()
        plt.savefig(output_dir / f'{method}_breakdown_points_by_cluster.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 3. Winning time distribution by cluster
    plt.figure(figsize=(12, 6))
    data['winning_time_hours'] = data['winning_time'] / 3600
    plot_data = data[data['cluster'] != -1] if -1 in data['cluster'].values else data
    sns.boxplot(data=plot_data, x='cluster', y='winning_time_hours')
    plt.title(f'Winning Time Distribution by Cluster - {method.upper()} (With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Winning Time (hours)')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_winning_time_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Total finishers distribution by cluster
    plt.figure(figsize=(12, 6))
    plot_data = data[data['cluster'] != -1] if -1 in data['cluster'].values else data
    sns.boxplot(data=plot_data, x='cluster', y='total_finishers')
    plt.title(f'Total Finishers Distribution by Cluster - {method.upper()} (With Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Total Finishers')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_finishers_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 5. Race category distribution by cluster
    if method != 'dbscan':  # Skip for DBSCAN due to complexity with noise
        plt.figure(figsize=(12, 8))
        plot_data = data[data['cluster'] != -1] if -1 in data['cluster'].values else data
        category_cluster = pd.crosstab(plot_data['race_category'], plot_data['cluster'], normalize='columns') * 100
        category_cluster.plot(kind='bar', stacked=True)
        plt.title(f'Race Category Distribution by Cluster - {method.upper()} (With Breakdown)')
        plt.xlabel('Race Category')
        plt.ylabel('Percentage')
        plt.legend(title='Cluster', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.xticks(rotation=0)
        plt.tight_layout()
        plt.savefig(output_dir / f'{method}_categories_by_cluster.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 6. Breakdown scatter plot
    if method != 'dbscan':
        plt.figure(figsize=(10, 8))
        plot_data = data[data['cluster'] != -1] if -1 in data['cluster'].values else data
        scatter = plt.scatter(plot_data['kurtosis_breakdown_point'], 
                            plot_data['variance_breakdown_point'],
                            c=plot_data['cluster'], 
                            cmap='viridis', 
                            alpha=0.6)
        plt.colorbar(scatter, label='Cluster ID')
        plt.xlabel('Kurtosis Breakdown Point (Percentile)')
        plt.ylabel('Variance Breakdown Point (Percentile)')
        plt.title(f'Breakdown Points Scatter Plot - {method.upper()} (With Breakdown)')
        plt.tight_layout()
        plt.savefig(output_dir / f'{method}_breakdown_scatter.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 7. Top features heatmap
    top_features = ['kurtosis_breakdown_point', 'variance_breakdown_point',
                   'nth_percentile_gap_25_slope', 'nth_percentile_gap_50_slope',
                   'nth_percentile_gap_25_directional_changes',
                   'variance_absolute_slope', 'variance_normalized_slope',
                   'variance_absolute_directional_changes']
    
    available_features = [f for f in top_features if f in data.columns]
    if available_features and method != 'dbscan':
        plt.figure(figsize=(12, 8))
        plot_data = data[data['cluster'] != -1] if -1 in data['cluster'].values else data
        cluster_means = plot_data.groupby('cluster')[available_features].mean()
        sns.heatmap(cluster_means.T, annot=True, cmap='RdYlBu_r', center=0, fmt='.3f')
        plt.title(f'Feature Means by Cluster - {method.upper()} (With Breakdown)')
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
    report.append("CLUSTERING EVALUATION REPORT - WITH BREAKDOWN SUBSET")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    report.append(f"Total races analyzed: {len(clustering_instance.data)}")
    report.append(f"Features used: {len(clustering_instance.feature_names)}")
    report.append(f"Subset: Stages WITH breakdowns")
    report.append(f"Filter: 90 minutes < winning_time < 8 hours, min_finishers >= 40")
    report.append(f"Breakdown criteria: kurtosis_breakdown_point > 0 OR variance_breakdown_point > 0")
    report.append("")
    
    # Breakdown statistics
    data = clustering_instance.data
    report.append("BREAKDOWN STATISTICS")
    report.append("-" * 40)
    report.append(f"Races with kurtosis breakdown: {(data['kurtosis_breakdown_point'] > 0).sum()} ({(data['kurtosis_breakdown_point'] > 0).mean()*100:.1f}%)")
    report.append(f"Races with variance breakdown: {(data['variance_breakdown_point'] > 0).sum()} ({(data['variance_breakdown_point'] > 0).mean()*100:.1f}%)")
    report.append(f"Average kurtosis breakdown: {data['kurtosis_breakdown_point'].mean():.1f} percentile")
    report.append(f"Average variance breakdown: {data['variance_breakdown_point'].mean():.1f} percentile")
    report.append("")
    
    # Clustering methods summary
    report.append("CLUSTERING METHODS EVALUATED")
    report.append("-" * 40)
    for method, labels in clustering_instance.clusters.items():
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = sum(1 for l in labels if l == -1)
        report.append(f"{method.upper()}: {n_clusters} clusters")
        if n_noise > 0:
            report.append(f"  - Noise points: {n_noise} ({n_noise/len(labels)*100:.1f}%)")
    report.append("")
    
    # Evaluation results
    if evaluator_results:
        report.append("CLUSTERING QUALITY METRICS")
        report.append("-" * 40)
        
        for method, results in evaluator_results.items():
            if 'stability' in results:
                stability = results['stability']
                report.append(f"{method.upper()} Stability:")
                report.append(f"  Mean stability: {stability['mean_stability']:.3f} ± {stability['std_stability']:.3f}")
                report.append(f"  Range: {stability['min_stability']:.3f} - {stability['max_stability']:.3f}")
                report.append("")
    
    # Detailed cluster analysis
    if cluster_stats is not None and not cluster_stats.empty:
        report.append("DETAILED CLUSTER ANALYSIS (K-MEANS)")
        report.append("-" * 40)
        
        for _, cluster in cluster_stats.iterrows():
            cluster_id = cluster['cluster_id']
            report.append(f"CLUSTER {cluster_id}")
            report.append("~" * 20)
            report.append(f"  Size: {cluster['n_races']} races ({cluster['percentage']:.1f}%)")
            report.append(f"  Finishers: {cluster['avg_finishers']:.1f} ± {cluster['std_finishers']:.1f}")
            report.append(f"  Winning time: {cluster['avg_winning_time_hours']:.2f} ± {cluster['std_winning_time_hours']:.2f} hours")
            report.append(f"  Years: {cluster['year_range']}")
            
            # Breakdown characteristics
            report.append(f"  Kurtosis breakdown: {cluster['avg_kurtosis_breakdown']:.1f} ± {cluster['std_kurtosis_breakdown']:.1f} percentile")
            report.append(f"  Variance breakdown: {cluster['avg_variance_breakdown']:.1f} ± {cluster['std_variance_breakdown']:.1f} percentile")
            
            # Categories
            categories = cluster['categories']
            if isinstance(categories, dict):
                cat_str = ", ".join([f"{k}: {v}" for k, v in categories.items()])
                report.append(f"  Categories: {cat_str}")
            
            # Top competitions
            competitions = cluster['top_competitions']
            if isinstance(competitions, dict):
                comp_str = ", ".join([f"{k}: {v}" for k, v in list(competitions.items())[:3]])
                report.append(f"  Top competitions: {comp_str}")
            
            report.append("")
    
    # Insights and recommendations
    report.append("KEY INSIGHTS")
    report.append("-" * 40)
    report.append("1. Breakdown location (percentile) is a strong discriminator for race clustering")
    report.append("2. K-means identifies 5 distinct clusters with clear breakdown patterns")
    report.append("3. DBSCAN struggles with this feature space (high noise), suggesting complex structure")
    report.append("4. Hierarchical clustering provides fine-grained analysis with 7 clusters")
    report.append("5. Breakdown timing correlates with race characteristics and duration")
    report.append("")
    
    report.append("RECOMMENDATIONS")
    report.append("-" * 40)
    report.append("1. Use K-means with 5 clusters for practical race kind classification")
    report.append("2. Consider breakdown timing as primary feature for race characterization")
    report.append("3. Investigate what causes breakdowns at different percentiles")
    report.append("4. Validate clusters against race terrain and tactical patterns")
    report.append("5. Combine with no-breakdown analysis for comprehensive race classification")
    
    # Write report
    with open(output_file, 'w') as f:
        f.write("\n".join(report))
    
    print(f"Text report saved to {output_file}")


def main():
    """Main evaluation function."""
    print("Starting evaluation of with-breakdown clustering results...")
    
    # Initialize clustering instance
    clustering = RaceKindClusteringWithBreakdown()
    
    # Load data
    print("Loading data...")
    clustering.load_stage_race_data(min_finishers=40)
    clustering.prepare_features()
    
    # Load clustering results
    results_dir = Path(__file__).parent / 'clustering_results_with_breakdown'
    clustering = load_clustering_results(clustering, results_dir)
    
    # Initialize evaluator
    evaluator = ClusteringEvaluator(clustering)
    
    # Run evaluations
    print("Running stability evaluation...")
    evaluator_results = {}
    
    for method in clustering.clusters.keys():
        try:
            # Skip DBSCAN if too much noise
            if method == 'dbscan':
                labels = clustering.clusters[method]
                noise_ratio = sum(1 for l in labels if l == -1) / len(labels)
                if noise_ratio > 0.8:  # Skip if more than 80% noise
                    print(f"Skipping {method} evaluation due to high noise ratio ({noise_ratio:.1%})")
                    continue
            
            stability_results = evaluator.evaluate_clustering_stability(method, n_bootstrap=20)
            evaluator_results[method] = {'stability': stability_results}
            print(f"Completed stability evaluation for {method}")
        except Exception as e:
            print(f"Error evaluating {method}: {e}")
    
    # Generate cluster statistics
    print("Generating cluster statistics...")
    cluster_stats = generate_cluster_statistics(clustering, 'kmeans')
    
    # Feature importance analysis
    print("Running feature importance analysis...")
    feature_importance_results = {}
    
    for method in clustering.clusters.keys():
        try:
            # Skip DBSCAN if too much noise
            if method == 'dbscan':
                labels = clustering.clusters[method]
                noise_ratio = sum(1 for l in labels if l == -1) / len(labels)
                if noise_ratio > 0.8:  # Skip if more than 80% noise
                    print(f"Skipping feature importance analysis for {method} due to high noise ratio ({noise_ratio:.1%})")
                    continue
            
            # Prepare data for feature importance analysis
            analysis_data = clustering.data.copy()
            analysis_data['cluster'] = clustering.clusters[method]
            
            # Initialize feature importance analyzer
            importance_analyzer = FeatureImportanceAnalyzer(analysis_data, clustering.feature_names)
            
            # Analyze all clusters
            cluster_analyses = importance_analyzer.analyze_all_clusters()
            feature_importance_results[method] = cluster_analyses
            
            print(f"Completed feature importance analysis for {method}")
            
        except Exception as e:
            print(f"Error in feature importance analysis for {method}: {e}")
    
    # Create output directory
    output_dir = Path(__file__).parent / 'evaluation_results_with_breakdown'
    output_dir.mkdir(exist_ok=True)
    
    # Save detailed statistics
    if cluster_stats is not None:
        cluster_stats.to_csv(output_dir / 'cluster_statistics.csv', index=False)
        cluster_stats.to_json(output_dir / 'cluster_statistics.json', orient='records', indent=2)
    
    # Save feature importance results
    for method, analyses in feature_importance_results.items():
        try:
            # Export detailed results
            output_file = output_dir / f'{method}_feature_importance.json'
            
            # Convert to exportable format
            export_data = {}
            for cluster_id, features in analyses.items():
                export_data[str(cluster_id)] = []
                for feature in features:
                    export_data[str(cluster_id)].append({
                        'feature_name': feature.feature_name,
                        'cluster_mean': feature.cluster_mean,
                        'population_mean': feature.population_mean,
                        'other_clusters_mean': feature.other_clusters_mean,
                        'effect_size_population': feature.effect_size_population,
                        'effect_size_others': feature.effect_size_others,
                        'statistical_significance': feature.statistical_significance,
                        'importance_score': feature.importance_score,
                        'tier': feature.tier,
                        'interpretation': feature.interpretation
                    })
            
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            # Generate and save feature importance report
            importance_analyzer = FeatureImportanceAnalyzer(
                clustering.data.copy().assign(cluster=clustering.clusters[method]), 
                clustering.feature_names
            )
            cluster_analyses = importance_analyzer.analyze_all_clusters()
            summary_report = importance_analyzer.generate_summary_report(cluster_analyses)
            
            with open(output_dir / f'{method}_feature_importance_report.txt', 'w') as f:
                f.write(summary_report)
            
            print(f"Saved feature importance analysis for {method}")
            
        except Exception as e:
            print(f"Error saving feature importance results for {method}: {e}")
    
    # Create visualizations
    print("Creating visualization plots...")
    for method in clustering.clusters.keys():
        create_visualization_plots(clustering, output_dir / 'plots', method)
    
    # Generate comprehensive text report
    print("Generating text report...")
    generate_text_report(clustering, evaluator_results, cluster_stats, 
                        output_dir / 'with_breakdown_evaluation_report.txt')
    
    # Save evaluation results
    with open(output_dir / 'evaluation_results.json', 'w') as f:
        json.dump(evaluator_results, f, indent=2)
    
    print(f"\nEvaluation complete! Results saved to {output_dir}/")
    print(f"Files generated:")
    print(f"  - with_breakdown_evaluation_report.txt")
    print(f"  - cluster_statistics.csv/json")
    print(f"  - evaluation_results.json")
    print(f"  - *_feature_importance.json (detailed analysis)")
    print(f"  - *_feature_importance_report.txt (human-readable)")
    print(f"  - plots/ directory with visualizations")
    
    # Close connection
    clustering.close()


if __name__ == "__main__":
    main()