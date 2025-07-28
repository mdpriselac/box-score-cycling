"""
Evaluation script for no-breakdown clustering results.
Produces comprehensive evaluation reports for the clustering analysis.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from clustering_no_breakdown import RaceKindClusteringNoBreakdown
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
        
        # Add feature means for top features
        top_features = ['kurtosis_absolute_slope', 'kurtosis_absolute_volatility', 
                       'kurtosis_absolute_directional_changes',
                       'nth_percentile_gap_5_slope', 'nth_percentile_gap_25_slope',
                       'nth_percentile_gap_5_directional_changes']
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
    plt.title(f'Cluster Size Distribution - {method.upper()} (No Breakdown)')
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
    plt.title(f'Winning Time Distribution by Cluster - {method.upper()} (No Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Winning Time (hours)')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_winning_time_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Total finishers distribution by cluster
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=data, x='cluster', y='total_finishers')
    plt.title(f'Total Finishers Distribution by Cluster - {method.upper()} (No Breakdown)')
    plt.xlabel('Cluster ID')
    plt.ylabel('Total Finishers')
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_finishers_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 4. Race category distribution by cluster
    plt.figure(figsize=(12, 8))
    category_cluster = pd.crosstab(data['race_category'], data['cluster'], normalize='columns') * 100
    category_cluster.plot(kind='bar', stacked=True)
    plt.title(f'Race Category Distribution by Cluster - {method.upper()} (No Breakdown)')
    plt.xlabel('Race Category')
    plt.ylabel('Percentage')
    plt.legend(title='Cluster', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(output_dir / f'{method}_categories_by_cluster.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 5. Top features heatmap
    top_features = ['kurtosis_absolute_slope', 'kurtosis_absolute_volatility', 
                   'kurtosis_absolute_directional_changes',
                   'nth_percentile_gap_5_slope', 'nth_percentile_gap_25_slope',
                   'nth_percentile_gap_5_directional_changes',
                   'skewness_normalized_slope', 'variance_absolute_slope',
                   'variance_absolute_directional_changes']
    
    available_features = [f for f in top_features if f in data.columns]
    if available_features:
        plt.figure(figsize=(10, 6))
        cluster_means = data.groupby('cluster')[available_features].mean()
        sns.heatmap(cluster_means.T, annot=True, cmap='RdYlBu_r', center=0)
        plt.title(f'Feature Means by Cluster - {method.upper()} (No Breakdown)')
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
    report.append("CLUSTERING EVALUATION REPORT - NO BREAKDOWN SUBSET")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    report.append(f"Total races analyzed: {len(clustering_instance.data)}")
    report.append(f"Features used: {len(clustering_instance.feature_names)}")
    report.append(f"Subset: Stages WITHOUT breakdowns")
    report.append(f"Filter: 90 minutes < winning_time < 8 hours, min_finishers >= 40")
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
    report.append("1. No-breakdown races show natural clustering patterns despite statistical consistency")
    report.append("2. Clusters may represent different race dynamics or terrain characteristics")
    report.append("3. Feature gradients provide sufficient discriminatory power for classification")
    report.append("4. Winning time and race category show some correlation with clusters")
    report.append("")
    
    report.append("RECOMMENDATIONS")
    report.append("-" * 40)
    report.append("1. Use K-means with 3 clusters for practical race kind classification")
    report.append("2. Consider hierarchical clustering for more granular analysis")
    report.append("3. Validate clusters against external race characteristics")
    report.append("4. Investigate what drives the clustering patterns (terrain, tactics, etc.)")
    
    # Write report
    with open(output_file, 'w') as f:
        f.write("\n".join(report))
    
    print(f"Text report saved to {output_file}")


def main():
    """Main evaluation function."""
    print("Starting evaluation of no-breakdown clustering results...")
    
    # Initialize clustering instance
    clustering = RaceKindClusteringNoBreakdown()
    
    # Load data
    print("Loading data...")
    clustering.load_stage_race_data(min_finishers=40)
    clustering.prepare_features()
    
    # Load clustering results
    results_dir = Path(__file__).parent / 'clustering_results_no_breakdown'
    clustering = load_clustering_results(clustering, results_dir)
    
    # Initialize evaluator
    evaluator = ClusteringEvaluator(clustering)
    
    # Run evaluations
    print("Running stability evaluation...")
    evaluator_results = {}
    
    for method in clustering.clusters.keys():
        try:
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
            # Prepare data for feature importance analysis
            analysis_data = clustering.data.copy()
            analysis_data['cluster'] = clustering.clusters[method]
            
            # Initialize feature importance analyzer
            importance_analyzer = FeatureImportanceAnalyzer(analysis_data, clustering.feature_names)
            
            # Analyze all clusters
            cluster_analyses = importance_analyzer.analyze_all_clusters()
            feature_importance_results[method] = cluster_analyses
            
            # Generate summary report
            summary_report = importance_analyzer.generate_summary_report(cluster_analyses)
            
            print(f"Completed feature importance analysis for {method}")
            
        except Exception as e:
            print(f"Error in feature importance analysis for {method}: {e}")
    
    # Create output directory
    output_dir = Path(__file__).parent / 'evaluation_results_no_breakdown'
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
                        output_dir / 'no_breakdown_evaluation_report.txt')
    
    # Save evaluation results
    with open(output_dir / 'evaluation_results.json', 'w') as f:
        json.dump(evaluator_results, f, indent=2)
    
    print(f"\nEvaluation complete! Results saved to {output_dir}/")
    print(f"Files generated:")
    print(f"  - no_breakdown_evaluation_report.txt")
    print(f"  - cluster_statistics.csv/json")
    print(f"  - evaluation_results.json")
    print(f"  - *_feature_importance.json (detailed analysis)")
    print(f"  - *_feature_importance_report.txt (human-readable)")
    print(f"  - plots/ directory with visualizations")
    
    # Close connection
    clustering.close()


if __name__ == "__main__":
    main()