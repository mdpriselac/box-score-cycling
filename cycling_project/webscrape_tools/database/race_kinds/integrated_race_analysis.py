"""
Integrated Race Analysis

This script demonstrates the complete workflow:
1. Feature selection and analysis
2. Race kind identification using optimal features
3. Comprehensive evaluation and reporting
"""

import os
from datetime import datetime
from feature_selection import FeatureSelector
from race_kind_analysis import RaceKindAnalyzer
from race_kind_evaluation import RaceKindEvaluator

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def analyze_with_feature_selection(
    table_name: str,
    competition_type: str = None,
    race_category: str = None,
    max_features: int = 12,
    db_path: str = DB_PATH
):
    """
    Run complete analysis with automatic feature selection.
    
    Args:
        table_name: Race features table name
        competition_type: Type filter
        race_category: Category filter
        max_features: Maximum features to select
        db_path: Database path
    """
    print(f"\n{'='*80}")
    print(f"INTEGRATED RACE ANALYSIS: {table_name}")
    if competition_type:
        print(f"Competition Type: {competition_type}")
    if race_category:
        print(f"Race Category: {race_category}")
    print(f"{'='*80}")
    
    # Step 1: Feature Selection
    print("\n🔍 STEP 1: FEATURE SELECTION")
    print("-" * 40)
    
    selector = FeatureSelector(db_path)
    
    # Load data for feature analysis
    data = selector.load_data(
        table_name,
        competition_type=competition_type,
        race_category=race_category
    )
    
    print(f"Loaded {len(data)} races from {table_name}")
    print(f"Available features: {len(selector.all_features)}")
    
    # Select optimal features
    selected_features = selector.select_features(
        correlation_threshold=0.9,
        variance_threshold=0.01,
        min_clustering_power=0.1,
        min_rf_importance=0.005,
        max_features=max_features
    )
    
    print(f"\nSelected {len(selected_features)} optimal features:")
    for i, feature in enumerate(selected_features, 1):
        print(f"  {i:2d}. {feature}")
    
    # Step 2: Race Kind Analysis
    print("\n🏁 STEP 2: RACE KIND ANALYSIS")
    print("-" * 40)
    
    # Initialize analyzer with selected features
    analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
    
    # Load data (will use only selected features)
    analyzer.load_data(
        table_name,
        competition_type=competition_type,
        race_category=race_category
    )
    
    print(f"Prepared analysis with {len(analyzer.feature_columns)} features")
    
    # Prepare features for clustering
    analyzer.prepare_features(scaling_method='robust')
    
    # Test multiple methods
    methods_results = {}
    
    # K-means clustering
    print("\nTesting K-means clustering...")
    kmeans_results = analyzer.kmeans_clustering(range(2, min(8, len(data)//10)))
    methods_results['kmeans'] = kmeans_results
    print(f"  Best k={kmeans_results['best_n_clusters']}, silhouette={kmeans_results['best_score']:.3f}")
    
    # Hierarchical clustering
    print("Testing hierarchical clustering...")
    hierarchical_results = analyzer.hierarchical_clustering(range(2, min(8, len(data)//10)))
    methods_results['hierarchical'] = hierarchical_results
    print(f"  Best k={hierarchical_results['best_n_clusters']}, silhouette={hierarchical_results['best_score']:.3f}")
    
    # Feature-based scoring
    print("Testing feature-based scoring...")
    scoring_results = analyzer.feature_based_scoring()
    methods_results['feature_based'] = scoring_results
    
    # Show race type distribution
    import pandas as pd
    type_counts = pd.Series(scoring_results['dominant_type']).value_counts()
    print("  Race type distribution:")
    for race_type, count in type_counts.items():
        print(f"    - {race_type}: {count} races ({count/len(data)*100:.1f}%)")
    
    # Step 3: Best Method Analysis
    print("\n📊 STEP 3: DETAILED ANALYSIS OF BEST METHOD")
    print("-" * 50)
    
    # Choose best clustering method
    best_method = 'kmeans' if kmeans_results['best_score'] > hierarchical_results['best_score'] else 'hierarchical'
    best_results = methods_results[best_method]
    
    print(f"Best clustering method: {best_method}")
    print(f"Silhouette score: {best_results['best_score']:.3f}")
    
    # Get cluster characteristics
    best_k = best_results['best_n_clusters']
    labels = best_results['cluster_results'][best_k]['labels']
    characteristics = analyzer.get_cluster_characteristics(labels)
    
    print(f"\nCluster Analysis ({best_k} clusters):")
    for cluster_id, info in sorted(characteristics.items()):
        print(f"\n  🏆 Cluster {cluster_id} ({info['size']} races, {info['percentage']:.1f}%)")
        
        # Top distinguishing features
        print("    Top distinguishing features:")
        for feat in info['top_features'][:3]:
            direction = "↑" if feat['cluster_mean'] > feat['overall_mean'] else "↓"
            print(f"      {direction} {feat['name']}: {feat['cluster_mean']:.3f} (avg: {feat['overall_mean']:.3f})")
        
        # Competition types
        comp_types = info['competition_types']
        if comp_types:
            main_type = max(comp_types.items(), key=lambda x: x[1])
            print(f"    Main type: {main_type[0]} ({main_type[1]} races)")
        
        # Example races
        print("    Example races:")
        for race in info['example_races'][:2]:
            print(f"      - {race['race_name']} - {race['competition_name']}")
    
    # Step 4: Generate Reports
    print("\n📝 STEP 4: GENERATING REPORTS")
    print("-" * 35)
    
    # Create output directory
    output_dir = 'database/race_kinds/reports'
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate feature selection report
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    feature_report = f"{output_dir}/feature_selection_{table_name}_{timestamp}.md"
    selector.generate_feature_report(feature_report)
    print(f"✓ Feature selection report: {feature_report}")
    
    # Generate visualizations
    try:
        selector.visualize_features(output_dir)
        print(f"✓ Feature visualizations saved to: {output_dir}")
    except Exception as e:
        print(f"⚠ Could not generate visualizations: {e}")
    
    return {
        'selected_features': selected_features,
        'methods_results': methods_results,
        'best_method': best_method,
        'cluster_characteristics': characteristics,
        'data_summary': {
            'n_races': len(data),
            'table_name': table_name,
            'competition_type': competition_type,
            'race_category': race_category
        }
    }


def compare_feature_sets(
    table_name: str,
    competition_type: str = None,
    db_path: str = DB_PATH
):
    """
    Compare analysis results using default features vs selected features.
    
    Args:
        table_name: Race features table name
        competition_type: Type filter
        db_path: Database path
    """
    print(f"\n{'='*80}")
    print(f"FEATURE SET COMPARISON: {table_name}")
    print(f"{'='*80}")
    
    # Test with default features
    print("\n📊 Analysis with DEFAULT features:")
    analyzer_default = RaceKindAnalyzer(db_path)  # Uses default features
    analyzer_default.load_data(table_name, competition_type=competition_type)
    analyzer_default.prepare_features()
    
    default_results = analyzer_default.kmeans_clustering(range(2, 7))
    print(f"  Default features ({len(analyzer_default.feature_columns)}): "
          f"silhouette = {default_results['best_score']:.3f}")
    
    # Test with selected features
    print("\n🔍 Analysis with SELECTED features:")
    selector = FeatureSelector(db_path)
    selector.load_data(table_name, competition_type=competition_type)
    selected_features = selector.select_features(max_features=10)
    
    analyzer_selected = RaceKindAnalyzer(db_path, feature_columns=selected_features)
    analyzer_selected.load_data(table_name, competition_type=competition_type)
    analyzer_selected.prepare_features()
    
    selected_results = analyzer_selected.kmeans_clustering(range(2, 7))
    print(f"  Selected features ({len(selected_features)}): "
          f"silhouette = {selected_results['best_score']:.3f}")
    
    # Compare
    improvement = selected_results['best_score'] - default_results['best_score']
    print(f"\n📈 IMPROVEMENT: {improvement:+.3f} silhouette score")
    
    if improvement > 0:
        print("✅ Feature selection improved clustering quality!")
    else:
        print("⚠️  Default features performed better in this case.")
    
    return {
        'default_score': default_results['best_score'],
        'selected_score': selected_results['best_score'],
        'improvement': improvement,
        'selected_features': selected_features
    }


def main():
    """Run integrated analysis demo."""
    print("🏁 INTEGRATED RACE KIND ANALYSIS WITH FEATURE SELECTION")
    print("=" * 80)
    
    # Example 1: Analyze stage races at 70th percentile
    print("\n1️⃣  EXAMPLE 1: Stage races at 70th percentile")
    results_70 = analyze_with_feature_selection(
        'race_features_70',
        competition_type='stage',
        max_features=10
    )
    
    # Example 2: Compare feature sets for one-day races
    print("\n\n2️⃣  EXAMPLE 2: Feature set comparison for one-day races")
    comparison = compare_feature_sets(
        'race_features_60',
        competition_type='one_day'
    )
    
    # Example 3: GC races analysis
    print("\n\n3️⃣  EXAMPLE 3: GC races with feature selection")
    results_gc = analyze_with_feature_selection(
        'race_features_50',
        competition_type='gc',
        max_features=8
    )
    
    # Summary
    print(f"\n\n{'='*80}")
    print("🎯 ANALYSIS COMPLETE!")
    print("="*80)
    print("\nKey findings:")
    print(f"- Stage races: {len(results_70['selected_features'])} optimal features selected")
    print(f"- One-day comparison: {comparison['improvement']:+.3f} improvement with feature selection")
    print(f"- GC races: {len(results_gc['selected_features'])} optimal features selected")
    print("\nReports and visualizations saved to database/race_kinds/reports/")


if __name__ == "__main__":
    main()