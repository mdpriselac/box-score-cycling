#!/usr/bin/env python3
"""
Example usage of the comprehensive feature selection pipeline.

This script demonstrates how to:
1. Generate correlation data for multiple riders
2. Run the integrated feature selection analysis
3. Get recommendations for optimal percentiles and features
4. Save and interpret results
"""
import sys
from pathlib import Path
import json

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.performance_feature_link.correlation_method import CorrelationCalculator
from rider_embeddings.feature_selection import FeatureSelectionPipeline


def generate_sample_correlation_data(db_path: str, num_riders: int = 50) -> list:
    """Generate correlation data for sample of rider results."""
    import sqlite3
    
    print(f"Generating correlation data for {num_riders} rider results...")
    
    # Get sample rider results with sufficient history
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        query = """
        SELECT rr.id, rr.rider_id, c.date as competition_date, COUNT(*) as prior_races
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN rider_results rr2 ON rr2.rider_id = rr.rider_id
        JOIN competitions c2 ON rr2.competition_id = c2.id
        WHERE c2.date < c.date
        GROUP BY rr.id, rr.rider_id, c.date
        HAVING COUNT(*) >= 10
        ORDER BY RANDOM()
        LIMIT ?
        """
        cursor.execute(query, (num_riders,))
        sample_results = cursor.fetchall()
    
    if len(sample_results) < 10:
        raise ValueError(f"Only found {len(sample_results)} suitable rider results (need at least 10)")
    
    print(f"Found {len(sample_results)} suitable rider results")
    
    # Calculate correlations
    calc = CorrelationCalculator(db_path, min_races=5)
    
    # All available feature tables
    feature_tables = [
        'race_features_30', 'race_features_40', 'race_features_50', 
        'race_features_60', 'race_features_70', 'race_features_80', 
        'race_features_90', 'race_features_100'
    ]
    
    # Use batch calculation for efficiency
    rider_result_ids = [r[0] for r in sample_results]
    correlation_results = calc.batch_calculate(rider_result_ids, feature_tables)
    
    # Filter out results with errors
    valid_results = [
        r for r in correlation_results 
        if r['metadata']['n_races'] >= 5 and not r['metadata']['warnings']
    ]
    
    print(f"Generated valid correlation data for {len(valid_results)} rider results")
    return valid_results


def run_feature_selection_analysis(correlation_results: list) -> dict:
    """Run the complete feature selection analysis."""
    print("\n" + "="*60)
    print("RUNNING COMPREHENSIVE FEATURE SELECTION ANALYSIS")
    print("="*60)
    
    # Initialize pipeline
    pipeline = FeatureSelectionPipeline(
        correlation_threshold=0.75,  # Slightly lower threshold for more sensitivity
        random_state=42
    )
    
    # Run complete analysis
    results = pipeline.analyze_all(
        correlation_results=correlation_results,
        k_range=[2, 3, 4, 5, 6, 7, 8],  # Test different cluster counts
        max_features=25  # Limit to top 25 features
    )
    
    return results


def interpret_results(results: dict):
    """Interpret and display key findings from the analysis."""
    print("\n" + "="*60)
    print("ANALYSIS RESULTS INTERPRETATION")
    print("="*60)
    
    recommendations = results['recommendations']
    
    # Percentile recommendations
    print("\n1. PERCENTILE RECOMMENDATIONS")
    print("-" * 30)
    
    percentile_rec = recommendations['percentile_recommendations']
    
    print(f"🏆 Best Overall Percentile: {percentile_rec['best_overall']}")
    print(f"📊 Best for Correlation Quality: {percentile_rec['best_for_correlation_quality']}")
    print(f"🎯 Best for Clustering: {percentile_rec['best_for_clustering']}")
    
    if percentile_rec['consensus_percentiles']:
        print(f"🤝 Consensus (top 3 in both): {', '.join(percentile_rec['consensus_percentiles'])}")
    
    # Show percentile scores
    print(f"\nPercentile Quality Scores:")
    scores = percentile_rec['percentile_scores']
    sorted_percentiles = sorted(scores.items(), key=lambda x: x[1]['combined_score'], reverse=True)
    
    for i, (percentile, score_data) in enumerate(sorted_percentiles[:5], 1):
        print(f"  {i}. {percentile}: {score_data['combined_score']:.4f} "
              f"(corr: {score_data['correlation_score']:.4f}, "
              f"clust: {score_data['clustering_score']:.4f})")
    
    # Feature recommendations
    print(f"\n2. FEATURE RECOMMENDATIONS")
    print("-" * 25)
    
    summary = recommendations['summary']
    print(f"📋 Recommended Percentile: {summary['recommended_percentile']}")
    print(f"🔢 Recommended Feature Count: {summary['feature_count']}")
    
    if summary['recommended_features']:
        print(f"\n🏅 Top Recommended Features:")
        for i, feature in enumerate(summary['recommended_features'][:12], 1):
            print(f"  {i:2d}. {feature}")
        
        if len(summary['recommended_features']) > 12:
            print(f"  ... and {len(summary['recommended_features']) - 12} more")
    
    # Redundancy reduction info
    feature_rec = recommendations['feature_recommendations']
    best_percentile = summary['recommended_percentile']
    
    if best_percentile in feature_rec:
        reduction_stats = feature_rec[best_percentile]['redundancy_reduction']
        print(f"\n3. REDUNDANCY REDUCTION")
        print("-" * 20)
        print(f"📉 Features removed due to redundancy: {reduction_stats['features_removed']}")
        print(f"📊 Reduction rate: {reduction_stats['reduction_rate']:.1%}")
    
    # Clustering insights
    clustering_data = results.get('clustering_analysis', {})
    if 'best_percentile' in clustering_data and clustering_data['best_percentile']:
        best_clustering_percentile = clustering_data['best_percentile']
        
        print(f"\n4. CLUSTERING INSIGHTS")
        print("-" * 18)
        print(f"🎯 Best clustering percentile: {best_clustering_percentile}")
        
        if 'percentile_analyses' in clustering_data:
            percentile_data = clustering_data['percentile_analyses'].get(best_clustering_percentile, {})
            if 'optimal_k' in percentile_data:
                optimal_k = percentile_data['optimal_k']
                print(f"🔍 Optimal number of rider clusters: {optimal_k}")
                
                if 'clustering_results' in percentile_data and optimal_k in percentile_data['clustering_results']:
                    cluster_results = percentile_data['clustering_results'][optimal_k]
                    print(f"📈 Silhouette score: {cluster_results['silhouette_score']:.4f}")
                    print(f"🎯 Cluster sizes: {cluster_results['cluster_sizes']}")


def save_and_report(results: dict, output_dir: str = "feature_selection_output"):
    """Save results and generate reports."""
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Initialize pipeline for report generation
    pipeline = FeatureSelectionPipeline()
    
    # Save detailed results
    detailed_path = output_path / "detailed_results.json"
    pipeline.save_results(results, str(detailed_path), include_raw_data=True)
    
    # Save summary results
    summary_path = output_path / "summary_results.json"
    pipeline.save_results(results, str(summary_path), include_raw_data=False)
    
    # Generate and save text report
    report = pipeline.generate_report(results)
    report_path = output_path / "analysis_report.txt"
    
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📁 Results saved to {output_dir}/:")
    print(f"   📊 detailed_results.json - Complete analysis data")
    print(f"   📋 summary_results.json - Summary and recommendations")
    print(f"   📝 analysis_report.txt - Human-readable report")
    
    return str(report_path)


def main():
    """Run the complete feature selection example."""
    db_path = "database/database/cycling_races.db"
    
    try:
        # Step 1: Generate correlation data
        correlation_results = generate_sample_correlation_data(db_path, num_riders=100)
        
        # Step 2: Run feature selection analysis
        results = run_feature_selection_analysis(correlation_results)
        
        # Step 3: Interpret results
        interpret_results(results)
        
        # Step 4: Save results and generate reports
        report_path = save_and_report(results)
        
        print(f"\n" + "="*60)
        print("ANALYSIS COMPLETE!")
        print("="*60)
        print(f"📋 View the detailed report at: {report_path}")
        print(f"🎯 Recommended setup:")
        
        summary = results['recommendations']['summary']
        print(f"   - Use percentile: {summary['recommended_percentile']}")
        print(f"   - With {summary['feature_count']} features")
        print(f"   - Expected to provide good rider discrimination")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()