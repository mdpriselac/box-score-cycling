"""
Find Race Kinds - Main Script

This script demonstrates how to use the race kind analysis tools to identify
different types of races based on their statistical characteristics.
"""

import os
import sys
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
from race_kind_analysis import RaceKindAnalyzer
from race_kind_evaluation import RaceKindEvaluator
from feature_selection import FeatureSelector
from race_kind_models import RaceKindModelManager

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def analyze_single_percentile(
    percentile: int,
    competition_type: str = None,
    method: str = 'kmeans',
    use_feature_selection: bool = False,
    max_features: int = 20,
    feature_selection_categories: list = None,
    analysis_categories: list = None,
    eval_categories: list = None,
    save_model: bool = False,
    save_features: bool = False,
    db_path: str = DB_PATH
):
    """
    Analyze race kinds for a single percentile table.
    
    Args:
        percentile: Percentile value (30, 40, 50, etc.)
        competition_type: Type of competitions to analyze
        method: Clustering method to use
        use_feature_selection: Whether to use automatic feature selection
        max_features: Maximum features to select if using feature selection
        feature_selection_categories: Race categories for feature selection (e.g., ['wt', 'pro'])
        analysis_categories: Race categories for race kind analysis (e.g., ['wt'])
        eval_categories: Race categories for evaluation (e.g., ['wt', 'pro', 'd1'])
        save_model: Whether to save the best model
        save_features: Whether to calculate and save race kind features
        db_path: Path to database
    """
    print(f"\n{'='*60}")
    print(f"Analyzing {percentile}th Percentile - {method} method")
    if use_feature_selection:
        print(f"Using automatic feature selection (max {max_features} features)")
    print(f"{'='*60}\n")
    
    selected_features = None
    
    # Step 1: Feature selection (if requested)
    if use_feature_selection:
        print("🔍 Running feature selection...")
        if feature_selection_categories:
            print(f"   Feature selection categories: {feature_selection_categories}")
        
        selector = FeatureSelector(db_path)
        table_name = f"race_features_{percentile}"
        
        try:
            # Use feature selection categories for broader feature training
            # For multiple categories, we need to load data for each and combine
            if feature_selection_categories and len(feature_selection_categories) > 1:
                all_data = []
                for category in feature_selection_categories:
                    cat_data = selector.load_data(table_name, competition_type=competition_type, race_category=category)
                    all_data.append(cat_data)
                
                # Combine data from all categories
                selector.data = pd.concat(all_data, ignore_index=True)
                print(f"   Loaded {len(selector.data)} races from {len(feature_selection_categories)} categories")
            else:
                # Single category or no category filtering
                category = feature_selection_categories[0] if feature_selection_categories else None
                selector.load_data(table_name, competition_type=competition_type, race_category=category)
                cat_desc = f" from {category}" if category else ""
                print(f"   Loaded {len(selector.data)} races{cat_desc}")
            
            selected_features = selector.select_features(
                max_features=max_features,
                correlation_threshold=0.9
            )
            print(f"Selected {len(selected_features)} optimal features:")
            for i, feature in enumerate(selected_features[:5], 1):
                print(f"  {i}. {feature}")
            if len(selected_features) > 5:
                print(f"  ... and {len(selected_features) - 5} more")
        except Exception as e:
            print(f"⚠️  Feature selection failed: {e}")
            print("Falling back to default features")
            selected_features = None
    
    # Initialize analyzer
    analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
    
    # Step 2: Load data for race kind analysis
    table_name = f"race_features_{percentile}"
    print(f"\n🏁 Loading data for race kind analysis from {table_name}...")
    if analysis_categories:
        print(f"   Analysis categories: {analysis_categories}")
    
    try:
        # For multiple analysis categories, we need to combine them
        if analysis_categories and len(analysis_categories) > 1:
            all_data = []
            for category in analysis_categories:
                cat_data = analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                all_data.append(cat_data)
            
            # Combine data from all categories
            analyzer.data = pd.concat(all_data, ignore_index=True)
            print(f"Loaded {len(analyzer.data)} races from {len(analysis_categories)} categories")
        else:
            # Single category or no category filtering
            category = analysis_categories[0] if analysis_categories else None
            data = analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
            cat_desc = f" from {category}" if category else ""
            print(f"Loaded {len(data)} races{cat_desc}")
        
        # Prepare features
        print("Preparing features...")
        analyzer.prepare_features(scaling_method='robust')
        
        # Run selected method
        print(f"Running {method} analysis...")
        
        if method == 'kmeans':
            results = analyzer.kmeans_clustering(range(3, min(8, len(analyzer.data)//10)))
            best_k = results['best_n_clusters']
            print(f"\nBest number of clusters: {best_k}")
            print(f"Silhouette score: {results['best_score']:.3f}")
            
            # Get cluster characteristics
            labels = results['cluster_results'][best_k]['labels']
            characteristics = analyzer.get_cluster_characteristics(labels)
            
            print("\nCluster Characteristics:")
            for cluster_id, info in sorted(characteristics.items()):
                print(f"\n  Cluster {cluster_id} ({info['size']} races, {info['percentage']:.1f}%):")
                print("    Top features:")
                for feat in info['top_features'][:3]:
                    print(f"      - {feat['name']}: {feat['cluster_mean']:.3f}")
                print(f"    Competition types: {info['competition_types']}")
                print("    Example races:")
                for race in info['example_races'][:3]:
                    print(f"      - {race['race_name']} - {race['competition_name']}")
        
        elif method == 'feature_based':
            results = analyzer.feature_based_scoring()
            
            print("\nRace Type Distribution:")
            dominant_types = pd.Series(results['dominant_type'])
            for race_type, count in dominant_types.value_counts().items():
                percentage = count / len(dominant_types) * 100
                print(f"  {race_type}: {count} races ({percentage:.1f}%)")
            
            # Show examples of each type
            analyzer.data['dominant_type'] = results['dominant_type']
            print("\nExample races by type:")
            for race_type in dominant_types.unique():
                print(f"\n  {race_type.upper()}:")
                examples = analyzer.data[analyzer.data['dominant_type'] == race_type][['race_name', 'competition_name']].head(3)
                for _, race in examples.iterrows():
                    print(f"    - {race['race_name']} - {race['competition_name']}")
        
        elif method == 'hierarchical':
            results = analyzer.hierarchical_clustering(range(3, min(8, len(analyzer.data)//10)))
            best_k = results['best_n_clusters']
            print(f"\nBest number of clusters: {best_k}")
            print(f"Silhouette score: {results['best_score']:.3f}")
            
            # Similar output to kmeans
            labels = results['cluster_results'][best_k]['labels']
            characteristics = analyzer.get_cluster_characteristics(labels)
            
            print("\nCluster Characteristics:")
            for cluster_id, info in sorted(characteristics.items()):
                print(f"\n  Cluster {cluster_id} ({info['size']} races):")
                print(f"    Competition types: {info['competition_types']}")
        
        # Step 3: Evaluation on different categories (if requested)
        if eval_categories and eval_categories != analysis_categories:
            print(f"\n📊 Evaluating on different categories: {eval_categories}")
            
            # Create a new analyzer for evaluation
            eval_analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
            
            # Load evaluation data
            if eval_categories and len(eval_categories) > 1:
                all_eval_data = []
                for category in eval_categories:
                    cat_data = eval_analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                    all_eval_data.append(cat_data)
                eval_analyzer.data = pd.concat(all_eval_data, ignore_index=True)
                print(f"   Loaded {len(eval_analyzer.data)} races from {len(eval_categories)} categories for evaluation")
            else:
                category = eval_categories[0] if eval_categories else None
                eval_data = eval_analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                print(f"   Loaded {len(eval_data)} races from {category} for evaluation")
            
            # Prepare features using same scaling
            eval_analyzer.prepare_features(scaling_method='robust')
            
            # Apply the trained model to evaluation data
            if method == 'kmeans' and 'best_n_clusters' in results:
                best_k = results['best_n_clusters']
                trained_model = results['cluster_results'][best_k]['model']
                
                # Predict on evaluation data
                eval_labels = trained_model.predict(eval_analyzer.scaled_features)
                
                # Calculate evaluation metrics
                from sklearn.metrics import silhouette_score
                eval_silhouette = silhouette_score(eval_analyzer.scaled_features, eval_labels)
                
                print(f"\n   Evaluation Results:")
                print(f"   Training silhouette score: {results['best_score']:.3f}")
                print(f"   Evaluation silhouette score: {eval_silhouette:.3f}")
                print(f"   Score difference: {eval_silhouette - results['best_score']:.3f}")
                
                # Get cluster distribution for evaluation data
                eval_characteristics = eval_analyzer.get_cluster_characteristics(eval_labels)
                
                print("\n   Cluster Distribution on Evaluation Data:")
                for cluster_id, info in sorted(eval_characteristics.items()):
                    print(f"   Cluster {cluster_id}: {info['size']} races ({info['percentage']:.1f}%)")
                    if 'd1' in eval_categories:
                        # Show category breakdown if D1 is included
                        category_counts = {}
                        for idx, label in enumerate(eval_labels):
                            if label == cluster_id:
                                cat = eval_analyzer.data.iloc[idx]['race_category']
                                category_counts[cat] = category_counts.get(cat, 0) + 1
                        if category_counts:
                            print(f"      Category breakdown: {category_counts}")
                
                # Add evaluation results to main results
                results['evaluation'] = {
                    'categories': eval_categories,
                    'n_races': len(eval_analyzer.data),
                    'silhouette_score': eval_silhouette,
                    'score_difference': eval_silhouette - results['best_score'],
                    'cluster_distribution': eval_characteristics
                }
        
        # Save model and features if requested
        if (save_model or save_features) and method in ['kmeans', 'hierarchical', 'gaussian_mixture']:
            model_manager = RaceKindModelManager(db_path)
            
            # Get the best model
            if method == 'kmeans' and 'best_n_clusters' in results:
                best_k = results['best_n_clusters']
                best_model = results['cluster_results'][best_k]['model']
            elif method == 'hierarchical' and 'best_n_clusters' in results:
                best_k = results['best_n_clusters']
                best_model = results['cluster_results'][best_k]['model']
            elif method == 'gaussian_mixture' and 'best_n_components' in results:
                best_k = results['best_n_components']
                best_model = results['cluster_results'][best_k]['model']
            else:
                best_model = None
            
            if best_model and save_model:
                # Prepare metadata
                metadata = {
                    'best_score': results['best_score'],
                    'feature_selection_used': use_feature_selection,
                    'feature_selection_categories': feature_selection_categories,
                    'analysis_categories': analysis_categories,
                    'competition_type': competition_type
                }
                
                # Save the model
                model_path = model_manager.save_model(
                    model=best_model,
                    algorithm=method,
                    percentile=percentile,
                    feature_columns=analyzer.feature_columns,
                    scaler=analyzer.scaler,
                    metadata=metadata
                )
                results['saved_model_path'] = model_path
                
            if best_model and save_features:
                # Create table name
                comp_type_suffix = f"_{competition_type}" if competition_type else ""
                table_name = f"race_kind_features_{method}_{percentile}{comp_type_suffix}"
                
                # Create table
                model_manager.create_race_kind_features_table(
                    table_name=table_name,
                    algorithm=method,
                    percentile=percentile,
                    feature_columns=analyzer.feature_columns,
                    metadata=metadata if save_model else None
                )
                
                # Calculate and store features
                competition_ids = analyzer.data['competition_id'].tolist()
                features_df = model_manager.calculate_race_kind_features(
                    X=analyzer.scaled_features,
                    model=best_model,
                    algorithm=method
                )
                
                model_manager.store_race_kind_features(
                    table_name=table_name,
                    competition_ids=competition_ids,
                    features_df=features_df
                )
                
                results['features_table_name'] = table_name
                print(f"\nSaved race kind features to table: {table_name}")
        
        return results
        
    except Exception as e:
        print(f"Error analyzing {table_name}: {str(e)}")
        return None


def evaluate_methods_single_percentile(
    percentile: int,
    competition_type: str = None,
    use_feature_selection: bool = False,
    max_features: int = 20,
    feature_selection_categories: list = None,
    analysis_categories: list = None,
    eval_categories: list = None,
    db_path: str = DB_PATH,
    output_dir: str = 'database/race_kinds/reports'
):
    """
    Evaluate all clustering methods on a single percentile with full feature control.
    
    Args:
        percentile: Percentile value to evaluate (30, 40, 50, etc.)
        competition_type: Type of competitions to analyze
        use_feature_selection: Whether to use automatic feature selection
        max_features: Maximum features to select if using feature selection
        feature_selection_categories: Race categories for feature selection
        analysis_categories: Race categories for training the models
        eval_categories: Race categories for evaluation (if different from training)
        db_path: Path to database
        output_dir: Directory for output reports
    """
    print("\n" + "="*60)
    print(f"EVALUATING ALL METHODS - {percentile}th Percentile")
    print("="*60)
    
    # Step 1: Feature selection (if requested)
    selected_features = None
    if use_feature_selection:
        print("\n🔍 Running feature selection...")
        if feature_selection_categories:
            print(f"   Feature selection categories: {feature_selection_categories}")
        
        selector = FeatureSelector(db_path)
        table_name = f"race_features_{percentile}"
        
        try:
            # Use feature selection with specified categories
            if feature_selection_categories and len(feature_selection_categories) > 1:
                all_data = []
                for category in feature_selection_categories:
                    cat_data = selector.load_data(table_name, competition_type=competition_type, race_category=category)
                    all_data.append(cat_data)
                selector.data = pd.concat(all_data, ignore_index=True)
                print(f"   Loaded {len(selector.data)} races from {len(feature_selection_categories)} categories")
            else:
                category = feature_selection_categories[0] if feature_selection_categories else None
                selector.load_data(table_name, competition_type=competition_type, race_category=category)
                cat_desc = f" from {category}" if category else ""
                print(f"   Loaded {len(selector.data)} races{cat_desc}")
            
            selected_features = selector.select_features(
                max_features=max_features,
                correlation_threshold=0.9
            )
            print(f"   Selected {len(selected_features)} optimal features")
            
        except Exception as e:
            print(f"   ⚠️  Feature selection failed: {e}")
            print("   Falling back to default features")
            selected_features = None
    
    # Step 2: Evaluate all methods
    methods = ['kmeans', 'hierarchical', 'gaussian_mixture', 'feature_based', 'dbscan']
    all_results = {}
    
    print(f"\n📊 Evaluating {len(methods)} methods on {percentile}th percentile...")
    
    for method in methods:
        print(f"\n➤ Testing {method}...")
        try:
            # Create analyzer with selected features
            analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
            
            # Load and prepare data
            table_name = f"race_features_{percentile}"
            if analysis_categories and len(analysis_categories) > 1:
                all_data = []
                for category in analysis_categories:
                    cat_data = analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                    all_data.append(cat_data)
                analyzer.data = pd.concat(all_data, ignore_index=True)
            else:
                category = analysis_categories[0] if analysis_categories else None
                analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
            
            analyzer.prepare_features(scaling_method='robust')
            
            # Run the specific method
            if method == 'kmeans':
                method_results = analyzer.kmeans_clustering(range(3, min(8, len(analyzer.data)//10)))
                # Get cluster characteristics
                if 'best_n_clusters' in method_results:
                    best_k = method_results['best_n_clusters']
                    labels = method_results['cluster_results'][best_k]['labels']
                    method_results['cluster_characteristics'] = analyzer.get_cluster_characteristics(labels)
                    
            elif method == 'hierarchical':
                method_results = analyzer.hierarchical_clustering(range(3, min(8, len(analyzer.data)//10)))
                if 'best_n_clusters' in method_results:
                    best_k = method_results['best_n_clusters']
                    labels = method_results['cluster_results'][best_k]['labels']
                    method_results['cluster_characteristics'] = analyzer.get_cluster_characteristics(labels)
                    
            elif method == 'gaussian_mixture':
                method_results = analyzer.gaussian_mixture_clustering(range(3, min(8, len(analyzer.data)//10)))
                
            elif method == 'feature_based':
                method_results = analyzer.feature_based_scoring()
                # Get type distribution
                dominant_types = pd.Series(method_results['dominant_type'])
                method_results['type_distribution'] = dominant_types.value_counts().to_dict()
                
            elif method == 'dbscan':
                method_results = analyzer.dbscan_clustering()
            
            # Add evaluation if requested
            if eval_categories and eval_categories != analysis_categories and method in ['kmeans', 'gaussian_mixture', 'hierarchical', 'dbscan']:
                eval_analyzer = RaceKindAnalyzer(db_path, feature_columns=selected_features)
                
                # Load evaluation data
                if eval_categories and len(eval_categories) > 1:
                    all_eval_data = []
                    for category in eval_categories:
                        cat_data = eval_analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                        all_eval_data.append(cat_data)
                    eval_analyzer.data = pd.concat(all_eval_data, ignore_index=True)
                else:
                    category = eval_categories[0] if eval_categories else None
                    eval_analyzer.load_data(table_name, competition_type=competition_type, race_category=category)
                
                eval_analyzer.prepare_features(scaling_method='robust')
                
                # Apply trained model
                best_k = None
                if 'best_n_clusters' in method_results:
                    best_k = method_results['best_n_clusters']
                elif 'best_n_components' in method_results:
                    best_k = method_results['best_n_components']
                
                # Handle evaluation differently for each method
                from sklearn.metrics import silhouette_score
                
                if method == 'hierarchical' and best_k is not None:
                    # Hierarchical clustering doesn't have predict(), so we need to refit
                    from sklearn.cluster import AgglomerativeClustering
                    eval_model = AgglomerativeClustering(n_clusters=best_k, linkage='ward')
                    eval_labels = eval_model.fit_predict(eval_analyzer.scaled_features)
                    eval_silhouette = silhouette_score(eval_analyzer.scaled_features, eval_labels)
                    
                elif method == 'dbscan' and method_results.get('best_params'):
                    # DBSCAN needs to be rerun with best parameters
                    from sklearn.cluster import DBSCAN
                    best_params = method_results['best_params']
                    eval_model = DBSCAN(eps=best_params['eps'], min_samples=best_params['min_samples'])
                    eval_labels = eval_model.fit_predict(eval_analyzer.scaled_features)
                    
                    # Calculate silhouette only for non-noise points
                    non_noise_mask = eval_labels != -1
                    if np.sum(non_noise_mask) >= 10 and len(set(eval_labels[non_noise_mask])) > 1:
                        eval_silhouette = silhouette_score(
                            eval_analyzer.scaled_features[non_noise_mask],
                            eval_labels[non_noise_mask]
                        )
                    else:
                        eval_silhouette = -1  # Failed evaluation
                        
                elif best_k is not None:
                    # For methods with predict() method (kmeans, gaussian_mixture)
                    trained_model = method_results['cluster_results'][best_k]['model']
                    eval_labels = trained_model.predict(eval_analyzer.scaled_features)
                    eval_silhouette = silhouette_score(eval_analyzer.scaled_features, eval_labels)
                
                else:
                    eval_silhouette = None
                
                # Store evaluation results if successful
                if eval_silhouette is not None and eval_silhouette > -1:
                    method_results['evaluation'] = {
                        'categories': eval_categories,
                        'n_races': len(eval_analyzer.data),
                        'silhouette_score': eval_silhouette,
                        'score_difference': eval_silhouette - method_results['best_score']
                    }
            
            # Store results if successful
            if method_results:
                all_results[method] = method_results
                print(f"   ✓ {method} completed successfully")
            else:
                print(f"   ✗ {method} failed")
                
        except Exception as e:
            print(f"   ✗ {method} error: {str(e)}")
            continue
    
    # Step 3: Generate comprehensive report
    print("\n📝 Generating evaluation report...")
    
    # Create report content
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_name = f"method_comparison_{percentile}th_percentile_{timestamp}"
    report_path = os.path.join(output_dir, f"{report_name}.md")
    
    os.makedirs(output_dir, exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write(f"# Race Kind Method Comparison Report\n\n")
        f.write(f"**Percentile**: {percentile}th\n")
        f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Competition Type**: {competition_type or 'All'}\n")
        f.write(f"**Feature Selection**: {'Yes' if use_feature_selection else 'No'}\n")
        if use_feature_selection:
            f.write(f"**Features Selected**: {len(selected_features)}\n")
            f.write(f"**Feature Selection Categories**: {feature_selection_categories}\n")
        f.write(f"**Analysis Categories**: {analysis_categories}\n")
        if eval_categories:
            f.write(f"**Evaluation Categories**: {eval_categories}\n")
        f.write("\n")
        
        # Summary table
        f.write("## Method Performance Summary\n\n")
        f.write("| Method | Best Score | Clusters/Types | Eval Score | Score Diff |\n")
        f.write("|--------|------------|----------------|------------|------------|\n")
        
        for method, results in all_results.items():
            score = results.get('best_score', 0)
            
            # Handle different cluster/component naming
            if method == 'dbscan':
                # For DBSCAN, count unique clusters (excluding noise points labeled as -1)
                if 'best_params' in results and results['best_params']:
                    # Find the best parameter result
                    best_key = None
                    for key, param_result in results.get('parameter_results', {}).items():
                        if param_result.get('silhouette_score', -1) == results['best_score']:
                            best_key = key
                            break
                    
                    if best_key:
                        n_clusters = results['parameter_results'][best_key]['n_clusters']
                    else:
                        n_clusters = 'Unknown'
                else:
                    n_clusters = 'Failed'
            else:
                n_clusters = results.get('best_n_clusters', results.get('best_n_components', 'N/A'))
            
            eval_score = 'N/A'
            score_diff = 'N/A'
            if 'evaluation' in results:
                eval_score = f"{results['evaluation']['silhouette_score']:.3f}"
                score_diff = f"{results['evaluation']['score_difference']:+.3f}"
            
            f.write(f"| {method} | {score:.3f} | {n_clusters} | {eval_score} | {score_diff} |\n")
        
        # Detailed results for each method
        f.write("\n## Detailed Method Results\n\n")
        
        for method, results in all_results.items():
            f.write(f"### {method.replace('_', ' ').title()}\n\n")
            
            if method in ['kmeans', 'hierarchical']:
                f.write(f"- **Best number of clusters**: {results.get('best_n_clusters', 'N/A')}\n")
                f.write(f"- **Silhouette score**: {results.get('best_score', 0):.3f}\n")
                
                if 'cluster_characteristics' in results:
                    f.write("\n**Cluster Distribution**:\n\n")
                    chars = results['cluster_characteristics']
                    for cluster_id, info in sorted(chars.items()):
                        f.write(f"- Cluster {cluster_id}: {info['size']} races ({info['percentage']:.1f}%)\n")
            
            elif method == 'feature_based':
                if 'error' in results:
                    f.write(f"- **Error**: {results['error']}\n")
                elif 'type_distribution' in results:
                    f.write("\n**Race Type Distribution**:\n\n")
                    for race_type, count in results['type_distribution'].items():
                        percentage = count / sum(results['type_distribution'].values()) * 100
                        f.write(f"- {race_type}: {count} races ({percentage:.1f}%)\n")
            
            elif method == 'dbscan':
                if 'best_params' in results and results['best_params']:
                    f.write(f"- **Best eps**: {results['best_params']['eps']:.3f}\n")
                    f.write(f"- **Best min_samples**: {results['best_params']['min_samples']}\n")
                    f.write(f"- **Silhouette score**: {results.get('best_score', 0):.3f}\n")
                    
                    # Find the best parameter result
                    best_key = None
                    for key, param_result in results.get('parameter_results', {}).items():
                        if param_result.get('silhouette_score', -1) == results['best_score']:
                            best_key = key
                            break
                    
                    if best_key:
                        best_result = results['parameter_results'][best_key]
                        f.write(f"- **Clusters found**: {best_result['n_clusters']}\n")
                        f.write(f"- **Noise points**: {best_result['n_noise']}\n")
                        f.write(f"- **Noise ratio**: {best_result['noise_ratio']:.1%}\n")
                    else:
                        f.write("- **Status**: Best parameters not found in results\n")
                else:
                    f.write("- **Status**: Failed to find suitable parameters\n")
            
            elif method == 'gaussian_mixture':
                f.write(f"- **Best number of components**: {results.get('best_n_components', 'N/A')}\n")
                f.write(f"- **Silhouette score**: {results.get('best_score', 0):.3f}\n")
                if results.get('best_n_components'):
                    best_n = results['best_n_components']
                    if best_n in results.get('evaluation_metrics', {}):
                        metrics = results['evaluation_metrics'][best_n]
                        f.write(f"- **BIC**: {metrics.get('bic', 'N/A'):.1f}\n")
                        f.write(f"- **AIC**: {metrics.get('aic', 'N/A'):.1f}\n")
            
            # Evaluation results if present
            if 'evaluation' in results:
                f.write("\n**Evaluation Performance**:\n\n")
                eval_data = results['evaluation']
                f.write(f"- Training score: {results.get('best_score', 0):.3f}\n")
                f.write(f"- Evaluation score: {eval_data['silhouette_score']:.3f}\n")
                f.write(f"- Score difference: {eval_data['score_difference']:+.3f}\n")
                f.write(f"- Evaluation races: {eval_data['n_races']}\n")
        
        # Selected features if applicable
        if selected_features:
            f.write("\n## Selected Features\n\n")
            for i, feature in enumerate(selected_features, 1):
                f.write(f"{i}. {feature}\n")
        
        # Recommendations
        f.write("\n## Recommendations\n\n")
        
        # Find best method
        best_method = max(all_results.items(), 
                         key=lambda x: x[1].get('best_score', -np.inf))[0]
        best_score = all_results[best_method].get('best_score', 0)
        
        f.write(f"1. **Best performing method**: {best_method} (score: {best_score:.3f})\n")
        
        # Check generalization if eval was done
        if any('evaluation' in r for r in all_results.values()):
            best_gen = min((m for m, r in all_results.items() if 'evaluation' in r),
                          key=lambda m: abs(all_results[m]['evaluation']['score_difference']))
            f.write(f"2. **Best generalization**: {best_gen} ")
            f.write(f"(score difference: {all_results[best_gen]['evaluation']['score_difference']:+.3f})\n")
    
    print(f"\n✅ Report saved to: {report_path}")
    
    return {
        'percentile': percentile,
        'methods': all_results,
        'selected_features': selected_features,
        'report_path': report_path
    }


def evaluate_all_methods(
    percentiles: list = None,
    competition_type: str = None,
    use_feature_selection: bool = False,
    max_features: int = 20,
    feature_selection_categories: list = None,
    analysis_categories: list = None,
    eval_categories: list = None,
    db_path: str = DB_PATH,
    output_dir: str = 'database/race_kinds/reports'
):
    """
    Evaluate all methods across multiple percentiles with full feature control.
    
    Args:
        percentiles: List of percentiles to evaluate (default: all available)
        competition_type: Type of competitions to analyze
        use_feature_selection: Whether to use automatic feature selection
        max_features: Maximum features to select if using feature selection
        feature_selection_categories: Race categories for feature selection
        analysis_categories: Race categories for training the models
        eval_categories: Race categories for evaluation
        db_path: Path to database
        output_dir: Directory for output reports
    """
    # If no percentiles specified, use all
    if percentiles is None:
        percentiles = [30, 40, 50, 60, 70, 80, 90, 100]
    
    print("\n" + "="*60)
    print("COMPREHENSIVE MULTI-PERCENTILE EVALUATION")
    print(f"Percentiles: {percentiles}")
    print("="*60)
    
    all_percentile_results = []
    
    # Evaluate each percentile
    for percentile in percentiles:
        print(f"\n{'='*50}")
        print(f"Processing {percentile}th percentile...")
        print(f"{'='*50}")
        
        try:
            results = evaluate_methods_single_percentile(
                percentile=percentile,
                competition_type=competition_type,
                use_feature_selection=use_feature_selection,
                max_features=max_features,
                feature_selection_categories=feature_selection_categories,
                analysis_categories=analysis_categories,
                eval_categories=eval_categories,
                db_path=db_path,
                output_dir=output_dir
            )
            all_percentile_results.append(results)
            
        except Exception as e:
            print(f"Error evaluating {percentile}th percentile: {str(e)}")
            continue
    
    # Generate summary report across all percentiles
    if len(all_percentile_results) > 1:
        print("\n📊 Generating cross-percentile summary report...")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_report_name = f"cross_percentile_summary_{timestamp}"
        summary_report_path = os.path.join(output_dir, f"{summary_report_name}.md")
        
        with open(summary_report_path, 'w') as f:
            f.write("# Cross-Percentile Method Comparison Summary\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Percentiles Evaluated**: {percentiles}\n")
            f.write(f"**Competition Type**: {competition_type or 'All'}\n\n")
            
            # Collect method scores across percentiles
            method_scores = {}
            for result in all_percentile_results:
                percentile = result['percentile']
                for method, method_result in result['methods'].items():
                    if method not in method_scores:
                        method_scores[method] = []
                    method_scores[method].append({
                        'percentile': percentile,
                        'score': method_result.get('best_score', 0),
                        'n_clusters': method_result.get('best_n_clusters', method_result.get('best_n_components', 'N/A'))
                    })
            
            # Summary table
            f.write("## Method Performance Across Percentiles\n\n")
            f.write("| Method | Mean Score | Std Dev | Best Percentile | Worst Percentile |\n")
            f.write("|--------|------------|---------|-----------------|------------------|\n")
            
            for method, scores in method_scores.items():
                score_values = [s['score'] for s in scores]
                mean_score = np.mean(score_values)
                std_score = np.std(score_values)
                
                best_idx = np.argmax(score_values)
                worst_idx = np.argmin(score_values)
                
                best_perc = scores[best_idx]['percentile']
                worst_perc = scores[worst_idx]['percentile']
                
                f.write(f"| {method} | {mean_score:.3f} | {std_score:.3f} | "
                       f"{best_perc}th ({score_values[best_idx]:.3f}) | "
                       f"{worst_perc}th ({score_values[worst_idx]:.3f}) |\n")
            
            # Individual report links
            f.write("\n## Individual Percentile Reports\n\n")
            for result in all_percentile_results:
                f.write(f"- [{result['percentile']}th percentile]({os.path.basename(result['report_path'])})\n")
        
        print(f"✅ Summary report saved to: {summary_report_path}")
    
    return all_percentile_results


def quick_analysis(db_path: str = DB_PATH):
    """
    Run a quick analysis to demonstrate the race kind finding capabilities.
    
    Args:
        db_path: Path to database
    """
    print("\n" + "="*60)
    print("QUICK RACE KIND ANALYSIS DEMO")
    print("="*60)
    
    # Analyze 70th percentile with different methods
    percentile = 70
    
    # Try k-means clustering
    print("\n1. K-means Clustering Analysis")
    analyze_single_percentile(percentile, competition_type='stage', method='kmeans', db_path=db_path)
    
    # Try feature-based scoring
    print("\n\n2. Feature-based Scoring Analysis")
    analyze_single_percentile(percentile, competition_type='stage', method='feature_based', db_path=db_path)
    
    # Compare GC races separately
    print("\n\n3. Grand Tour GC Analysis")
    analyze_single_percentile(percentile, competition_type='gc', method='kmeans', db_path=db_path)


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Find and analyze race kinds in cycling data"
    )
    
    parser.add_argument(
        '--mode',
        choices=['quick', 'single', 'evaluate'],
        default='quick',
        help='Analysis mode: quick demo, single percentile, or full evaluation'
    )
    
    parser.add_argument(
        '--percentile',
        type=int,
        choices=[30, 40, 50, 60, 70, 80, 90, 100],
        default=None,
        help='Percentile table to analyze (for single mode, default 70) or evaluation mode (default all)'
    )
    
    parser.add_argument(
        '--method',
        choices=['kmeans', 'hierarchical', 'dbscan', 'gaussian_mixture', 'feature_based'],
        default='kmeans',
        help='Clustering method to use (for single mode)'
    )
    
    parser.add_argument(
        '--competition-type',
        choices=['gc', 'stage', 'one_day', 'stage_one_day'],
        help='Filter by competition type'
    )
    
    parser.add_argument(
        '--db-path',
        default=DB_PATH,
        help='Path to SQLite database'
    )
    
    parser.add_argument(
        '--output-dir',
        default='database/race_kinds/reports',
        help='Directory for output reports'
    )
    
    parser.add_argument(
        '--use-feature-selection',
        action='store_true',
        help='Use automatic feature selection (for single mode)'
    )
    
    parser.add_argument(
        '--max-features',
        type=int,
        default=20,
        help='Maximum features to select when using feature selection'
    )
    
    parser.add_argument(
        '--feature-selection-categories',
        nargs='+',
        choices=['wt', 'pro', 'd1'],
        help='Race categories for feature selection (e.g., wt pro)'
    )
    
    parser.add_argument(
        '--analysis-categories', 
        nargs='+',
        choices=['wt', 'pro', 'd1'],
        help='Race categories for race kind analysis (e.g., wt)'
    )
    
    parser.add_argument(
        '--eval-categories',
        nargs='+',
        choices=['wt', 'pro', 'd1'],
        help='Race categories for evaluation (e.g., wt pro d1)'
    )
    
    parser.add_argument(
        '--save-model',
        action='store_true',
        help='Save the best model for later use'
    )
    
    parser.add_argument(
        '--save-features',
        action='store_true',
        help='Calculate and save race kind features to database'
    )
    
    args = parser.parse_args()
    
    # Run selected mode
    if args.mode == 'quick':
        quick_analysis(args.db_path)
    
    elif args.mode == 'single':
        analyze_single_percentile(
            args.percentile or 70,  # Default to 70 for single mode
            competition_type=args.competition_type,
            method=args.method,
            use_feature_selection=args.use_feature_selection,
            max_features=args.max_features,
            feature_selection_categories=args.feature_selection_categories,
            analysis_categories=args.analysis_categories,
            eval_categories=args.eval_categories,
            save_model=args.save_model,
            save_features=args.save_features,
            db_path=args.db_path
        )
    
    elif args.mode == 'evaluate':
        # For evaluate mode, we can either evaluate a single percentile or multiple
        percentiles_to_eval = None
        if args.percentile:
            # If a specific percentile is given, evaluate just that one
            percentiles_to_eval = [args.percentile]
        
        evaluate_all_methods(
            percentiles=percentiles_to_eval,
            competition_type=args.competition_type,
            use_feature_selection=args.use_feature_selection,
            max_features=args.max_features,
            feature_selection_categories=args.feature_selection_categories,
            analysis_categories=args.analysis_categories,
            eval_categories=args.eval_categories,
            db_path=args.db_path,
            output_dir=args.output_dir
        )
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()