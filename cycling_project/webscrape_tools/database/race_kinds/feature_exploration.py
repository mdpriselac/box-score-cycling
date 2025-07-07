"""
Feature Exploration Script

Quick tool to explore feature selection across different percentiles and competition types.
Generates detailed reports on which features are selected and why.
"""

import argparse
import os
from datetime import datetime
import pandas as pd
import numpy as np
from feature_selection import FeatureSelector

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def explore_features(
    percentiles: list,
    competition_types: list,
    race_categories: list = None,
    max_features: int = 15,
    output_dir: str = 'database/race_kinds/reports',
    db_path: str = DB_PATH
):
    """
    Explore feature selection across multiple scenarios.
    
    Args:
        percentiles: List of percentile values (e.g., [50, 70, 90])
        competition_types: List of competition types (e.g., ['stage', 'gc'])
        race_categories: List of race categories (e.g., ['wt', 'pro'])
        max_features: Maximum features to select
        output_dir: Directory for output files
        db_path: Database path
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    all_results = []
    detailed_reports = []
    
    print(f"\n🔍 FEATURE EXPLORATION ACROSS SCENARIOS")
    print(f"{'='*80}")
    print(f"Percentiles: {percentiles}")
    print(f"Competition types: {competition_types}")
    if race_categories:
        print(f"Race categories: {race_categories}")
    print(f"Max features: {max_features}")
    
    scenario_count = 0
    total_scenarios = len(percentiles) * len(competition_types)
    
    for percentile in percentiles:
        for comp_type in competition_types:
            scenario_count += 1
            table_name = f"race_features_{percentile}"
            
            print(f"\n📊 Scenario {scenario_count}/{total_scenarios}: {table_name}")
            if comp_type:
                print(f"   Competition type: {comp_type}")
            if race_categories:
                print(f"   Race categories: {race_categories}")
            
            try:
                # Initialize selector
                selector = FeatureSelector(db_path)
                
                # Load data - combine multiple categories if specified
                if race_categories and len(race_categories) > 1:
                    # Load and combine data from multiple categories
                    all_data = []
                    for category in race_categories:
                        cat_data = selector.load_data(
                            table_name,
                            competition_type=comp_type,
                            race_category=category
                        )
                        all_data.append(cat_data)
                    
                    # Combine data from all categories
                    import pandas as pd
                    selector.data = pd.concat(all_data, ignore_index=True)
                    data = selector.data
                else:
                    # Single category or no category filtering
                    category = race_categories[0] if race_categories else None
                    data = selector.load_data(
                        table_name,
                        competition_type=comp_type,
                        race_category=category
                    )
                
                if len(data) < 20:
                    print(f"   ⚠️  Insufficient data ({len(data)} races), skipping...")
                    continue
                
                print(f"   Loaded {len(data)} races with {len(selector.all_features)} features")
                
                # Run feature selection
                selected_features = selector.select_features(
                    correlation_threshold=0.9,
                    variance_threshold=0.01,
                    min_clustering_power=0.1,
                    min_rf_importance=0.005,
                    max_features=max_features
                )
                
                print(f"   ✅ Selected {len(selected_features)} features")
                
                # Collect summary info
                scenario_info = {
                    'percentile': percentile,
                    'competition_type': comp_type,
                    'race_category': race_categories,  # Use the full list, not individual category
                    'n_races': len(data),
                    'total_features': len(selector.all_features),
                    'selected_features': len(selected_features),
                    'selected_feature_names': selected_features,
                    'removed_correlation': len(selector.feature_scores.get('correlation_removed', set())),
                    'removed_low_variance': len(selector.feature_scores.get('low_variance', set())),
                    'removed_redundant': len(selector.feature_scores.get('redundant_features', set()))
                }
                
                all_results.append(scenario_info)
                
                # Generate detailed analysis for this scenario
                detailed_analysis = generate_detailed_analysis(selector, scenario_info)
                detailed_reports.append(detailed_analysis)
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                continue
    
    # Generate comprehensive report
    report_path = generate_exploration_report(
        all_results, 
        detailed_reports, 
        output_dir, 
        timestamp,
        max_features
    )
    
    # Generate comparison table
    comparison_path = generate_comparison_table(all_results, output_dir, timestamp)
    
    print(f"\n🎉 Feature exploration complete!")
    print(f"📄 Main report: {report_path}")
    print(f"📊 Comparison table: {comparison_path}")
    
    return all_results


def generate_detailed_analysis(selector, scenario_info):
    """Generate detailed analysis for a single scenario."""
    analysis = {
        'scenario': scenario_info,
        'feature_details': {}
    }
    
    # Get feature scores
    final_scores = selector.feature_scores.get('final_scores', {})
    clustering_power = selector.feature_scores.get('clustering_power', {})
    rf_importance = selector.feature_scores.get('rf_importance', {})
    
    # Categorize all features
    selected_features = set(scenario_info['selected_feature_names'])
    correlation_removed = selector.feature_scores.get('correlation_removed', set())
    low_variance = selector.feature_scores.get('low_variance', set())
    redundant = selector.feature_scores.get('redundant_features', set())
    
    # All features analysis
    for feature in selector.all_features:
        status = 'selected' if feature in selected_features else 'removed'
        
        removal_reasons = []
        if feature in correlation_removed:
            removal_reasons.append('high_correlation')
        if feature in low_variance:
            removal_reasons.append('low_variance')
        if feature in redundant:
            removal_reasons.append('redundant')
        if feature not in selected_features and not removal_reasons:
            removal_reasons.append('low_score')
        
        analysis['feature_details'][feature] = {
            'status': status,
            'removal_reasons': removal_reasons,
            'final_score': final_scores.get(feature, 0),
            'clustering_power': clustering_power.get(feature, 0),
            'rf_importance': rf_importance.get(feature, 0)
        }
    
    return analysis


def generate_exploration_report(all_results, detailed_reports, output_dir, timestamp, max_features):
    """Generate comprehensive exploration report."""
    report_path = os.path.join(output_dir, f"feature_exploration_{timestamp}.md")
    
    with open(report_path, 'w') as f:
        f.write("# Feature Selection Exploration Report\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Executive Summary
        f.write("## Executive Summary\n\n")
        f.write(f"- **Total scenarios analyzed**: {len(all_results)}\n")
        f.write(f"- **Max features per scenario**: {max_features}\n")
        
        if all_results:
            total_races = sum(r['n_races'] for r in all_results)
            avg_selected = np.mean([r['selected_features'] for r in all_results])
            f.write(f"- **Total races analyzed**: {total_races:,}\n")
            f.write(f"- **Average features selected**: {avg_selected:.1f}\n")
        
        # Feature Selection Patterns
        f.write("\n## Feature Selection Patterns\n\n")
        
        # Most commonly selected features
        feature_frequency = {}
        for result in all_results:
            for feature in result['selected_feature_names']:
                feature_frequency[feature] = feature_frequency.get(feature, 0) + 1
        
        if feature_frequency:
            f.write("### Most Frequently Selected Features\n\n")
            sorted_features = sorted(feature_frequency.items(), key=lambda x: x[1], reverse=True)
            f.write("| Feature | Times Selected | Frequency |\n")
            f.write("|---------|---------------|----------|\n")
            for feature, count in sorted_features[:15]:
                freq = count / len(all_results) * 100 if len(all_results) > 0 else 0
                f.write(f"| {feature} | {count} | {freq:.1f}% |\n")
        
        # Removal patterns
        f.write("\n### Feature Removal Patterns\n\n")
        removal_stats = {
            'correlation': sum(r['removed_correlation'] for r in all_results),
            'low_variance': sum(r['removed_low_variance'] for r in all_results),
            'redundant': sum(r['removed_redundant'] for r in all_results)
        }
        
        if len(all_results) > 0:
            f.write(f"- **High correlation removals**: {removal_stats['correlation']} (avg {removal_stats['correlation']/len(all_results):.1f} per scenario)\n")
            f.write(f"- **Low variance removals**: {removal_stats['low_variance']} (avg {removal_stats['low_variance']/len(all_results):.1f} per scenario)\n")
            f.write(f"- **Redundancy removals**: {removal_stats['redundant']} (avg {removal_stats['redundant']/len(all_results):.1f} per scenario)\n")
        else:
            f.write("- **No successful scenarios to analyze**\n")
        
        # Detailed scenario analysis
        f.write("\n## Detailed Scenario Analysis\n\n")
        
        for i, (result, details) in enumerate(zip(all_results, detailed_reports)):
            scenario_title = f"Scenario {i+1}: {result['percentile']}th percentile"
            if result['competition_type']:
                scenario_title += f" - {result['competition_type']}"
            if result['race_category']:
                scenario_title += f" - {result['race_category']}"
            
            f.write(f"### {scenario_title}\n\n")
            f.write(f"- **Races analyzed**: {result['n_races']}\n")
            f.write(f"- **Features available**: {result['total_features']}\n")
            f.write(f"- **Features selected**: {result['selected_features']}\n\n")
            
            # Selected features with scores
            f.write("#### Selected Features\n\n")
            f.write("| Feature | Final Score | Clustering Power | RF Importance |\n")
            f.write("|---------|------------|-----------------|---------------|\n")
            
            selected_details = [
                (feat, details['feature_details'][feat]) 
                for feat in result['selected_feature_names']
                if feat in details['feature_details']
            ]
            selected_details.sort(key=lambda x: x[1]['final_score'], reverse=True)
            
            for feature, feat_details in selected_details:
                f.write(f"| {feature} | {feat_details['final_score']:.3f} | "
                       f"{feat_details['clustering_power']:.3f} | "
                       f"{feat_details['rf_importance']:.3f} |\n")
            
            # Removed features by reason
            f.write("\n#### Removed Features by Reason\n\n")
            
            removed_by_reason = {}
            for feature, feat_details in details['feature_details'].items():
                if feat_details['status'] == 'removed':
                    for reason in feat_details['removal_reasons']:
                        if reason not in removed_by_reason:
                            removed_by_reason[reason] = []
                        removed_by_reason[reason].append(feature)
            
            for reason, features in removed_by_reason.items():
                f.write(f"**{reason.replace('_', ' ').title()}** ({len(features)} features):\n")
                for feature in sorted(features)[:10]:  # Show first 10
                    f.write(f"- {feature}\n")
                if len(features) > 10:
                    f.write(f"- ... and {len(features) - 10} more\n")
                f.write("\n")
            
            f.write("---\n\n")
    
    return report_path


def generate_comparison_table(all_results, output_dir, timestamp):
    """Generate CSV comparison table."""
    df = pd.DataFrame(all_results)
    
    # Expand selected features into separate columns for analysis
    all_selected_features = set()
    for result in all_results:
        all_selected_features.update(result['selected_feature_names'])
    
    # Create binary feature matrix
    feature_matrix = pd.DataFrame(index=df.index, columns=sorted(all_selected_features))
    for i, result in enumerate(all_results):
        for feature in all_selected_features:
            feature_matrix.loc[i, feature] = 1 if feature in result['selected_feature_names'] else 0
    
    # Combine with scenario info
    scenario_df = df[['percentile', 'competition_type', 'race_category', 'n_races', 
                     'total_features', 'selected_features']].copy()
    comparison_df = pd.concat([scenario_df, feature_matrix], axis=1)
    
    # Save
    csv_path = os.path.join(output_dir, f"feature_comparison_{timestamp}.csv")
    comparison_df.to_csv(csv_path, index=False)
    
    return csv_path


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Explore feature selection across different scenarios"
    )
    
    parser.add_argument(
        '--percentiles',
        nargs='+',
        type=int,
        default=[30,40,50, 60, 70, 80],
        help='Percentile levels to analyze (e.g., 50 70 90)'
    )
    
    parser.add_argument(
        '--competition-types',
        nargs='+',
        choices=['gc', 'stage', 'one_day', 'stage_one_day'],
        default=['stage', 'one_day', 'stage_one_day'],
        help='Competition types to analyze'
    )
    
    parser.add_argument(
        '--race-categories',
        nargs='+',
        choices=['wt','pro','d1'],
        help='Race categories to analyze (optional)'
    )
    
    parser.add_argument(
        '--max-features',
        type=int,
        default=20,
        help='Maximum features to select per scenario'
    )
    
    parser.add_argument(
        '--output-dir',
        default='database/race_kinds/reports',
        help='Output directory for reports'
    )
    
    parser.add_argument(
        '--db-path',
        default=DB_PATH,
        help='Path to SQLite database'
    )
    
    args = parser.parse_args()
    
    # Run exploration
    results = explore_features(
        percentiles=args.percentiles,
        competition_types=args.competition_types,
        race_categories=args.race_categories,
        max_features=args.max_features,
        output_dir=args.output_dir,
        db_path=args.db_path
    )
    
    print(f"\n✨ Explored {len(results)} scenarios successfully!")


if __name__ == "__main__":
    main()