#!/usr/bin/env python3
"""
Complete pipeline example: Generate correlations → Store → Load → Feature Selection

This script demonstrates the full workflow from generating rider performance
correlations to selecting optimal features.
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.data_generation import (
    CorrelationDataGenerator, 
    ParquetStorage, 
    CorrelationDataLoader
)
from rider_embeddings.feature_selection import FeatureSelectionPipeline


def step1_generate_correlations(db_path: str, output_dir: str = "correlation_data", sample_mode: bool = True):
    """
    Step 1: Generate correlation data
    
    Args:
        db_path: Path to cycling database
        output_dir: Directory for output files
        sample_mode: If True, generate sample data; if False, generate full dataset
    """
    print("\n" + "="*60)
    print("STEP 1: GENERATING CORRELATION DATA")
    print("="*60)
    
    # Initialize generator
    generator = CorrelationDataGenerator(
        db_path=db_path,
        output_dir=output_dir,
        batch_size=500,
        min_races=25
    )
    
    if sample_mode:
        # Generate sample for testing
        print("Generating sample correlation data...")
        generator.generate_sample(
            sample_size=500,  # 500 riders for demo
            feature_tables=[
                'race_features_30', 'race_features_40', 'race_features_50',
                'race_features_60', 'race_features_70', 
                'race_features_80', 'race_features_90', 
            ],
            output_name="demo_sample"
        )
    else:
        # Generate full dataset
        print("Generating full correlation dataset...")
        print("WARNING: This may take several hours for large databases!")
        
        generator.generate_all_correlations(
            feature_tables=None,  # All percentiles
            limit=None,  # All eligible riders
            resume=True  # Enable checkpointing
        )
    
    print(f"✓ Correlation data generated in {output_dir}")


def step2_optimize_storage(output_dir: str = "correlation_data"):
    """
    Step 2: Optimize and organize storage
    """
    print("\n" + "="*60)
    print("STEP 2: OPTIMIZING STORAGE")
    print("="*60)
    
    storage = ParquetStorage(output_dir)
    
    # Get storage statistics
    stats = storage.get_storage_stats()
    print(f"\nStorage Statistics:")
    print(f"  Files: {stats['total_files']}")
    print(f"  Size: {stats['total_size_mb']:.2f} MB")
    print(f"  Estimated records: {stats.get('estimated_records', 'N/A')}")
    
    # Check if we have batch files to optimize
    if stats['total_files'] > 1:
        print("\nOptimizing storage by merging batches...")
        
        # Option 1: Merge all batches
        merged_path = storage.merge_batches(
            output_file="merged_correlations.parquet",
            delete_originals=False  # Keep originals for safety
        )
        
        # Option 2: Create partitioned dataset for efficient queries
        print("\nCreating partitioned dataset...")
        partitioned_path = storage.partition_by_percentile(
            source_file="merged_correlations.parquet"
        )
        
        print(f"✓ Created partitioned dataset at {partitioned_path}")
    elif stats['total_files'] == 0:
        # Check for sample files
        sample_files = list(Path(output_dir).glob("*sample*.parquet"))
        if sample_files:
            print(f"\nFound sample file: {sample_files[0].name}")
            print("Using sample file for analysis...")
        else:
            print("\nNo correlation files found!")
            return
    
    # Create feature index
    print("\nCreating feature index...")
    try:
        feature_index = storage.create_feature_index()
        print(f"✓ Indexed {len(feature_index)} percentiles")
    except Exception as e:
        print(f"⚠ Could not create feature index: {e}")
    
    # Validate data
    print("\nValidating data quality...")
    validation = storage.validate_data(sample_size=500)
    
    if validation['valid']:
        print("✓ Data validation passed!")
    else:
        print("⚠ Data validation issues found:")
        issues = validation.get('issues', [])
        for issue in issues:
            print(f"  - {issue}")
        
        # Print validation summary anyway
        if 'summary' in validation:
            summary = validation['summary']
            print(f"\nValidation Summary:")
            print(f"  Unique riders: {summary.get('unique_riders', 'N/A')}")
            print(f"  Unique percentiles: {summary.get('unique_percentiles', 'N/A')}")
            print(f"  Null correlations: {summary.get('null_correlations', 'N/A')}")


def step3_run_feature_selection(output_dir: str = "correlation_data"):
    """
    Step 3: Load data and run feature selection analysis
    """
    print("\n" + "="*60)
    print("STEP 3: FEATURE SELECTION ANALYSIS")
    print("="*60)
    
    # Initialize data loader
    loader = CorrelationDataLoader(output_dir)
    
    # Get data summary
    summary = loader.get_data_summary()
    print(f"\nData Summary:")
    print(f"  Available percentiles: {', '.join(summary['available_percentiles'])}")
    print(f"  Unique riders: {summary['data_statistics']['unique_riders']}")
    print(f"  Storage format: {summary['storage_format']}")
    
    # Load correlation data for feature selection
    print("\nLoading correlation data...")
    correlation_results = loader.load_for_feature_selection(
        percentiles=None,  # Analyze all available percentiles
        min_races=25,  # Higher threshold for quality
        sample_size=None  # Use all available data
    )
    
    print(f"Loaded {len(correlation_results)} rider results")
    
    # Run feature selection pipeline
    print("\nRunning comprehensive feature selection analysis...")
    pipeline = FeatureSelectionPipeline(
        correlation_threshold=0.9,
        random_state=142
    )
    
    results = pipeline.analyze_all(
        correlation_results=correlation_results,
        k_range=[3, 4, 5, 6, 7],  # Test different cluster counts
        max_features=25  # Limit to top 25 features
    )
    
    # Save results
    pipeline.save_results(
        results, 
        f"{output_dir}/feature_selection_results.json",
        include_raw_data=False  # Summary only
    )
    
    # Generate report
    report = pipeline.generate_report(results)
    report_path = f"{output_dir}/feature_selection_report.txt"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n✓ Feature selection complete!")
    print(f"✓ Results saved to {output_dir}/")
    
    return results


def interpret_results(results: dict):
    """Interpret and display key findings from the analysis with detailed explanations."""
    print("\n" + "="*60)
    print("ANALYSIS RESULTS INTERPRETATION")
    print("="*60)
    
    recommendations = results['recommendations']
    correlation_analysis = results['correlation_quality_analysis']
    clustering_analysis = results['clustering_analysis']
    
    # Percentile recommendations with explanations
    print("\n1. PERCENTILE SELECTION & REASONING")
    print("-" * 35)
    
    percentile_rec = recommendations['percentile_recommendations']
    best_percentile = percentile_rec['best_overall']
    
    print(f"🏆 Best Overall Percentile: {best_percentile}")
    
    # Explain what this percentile means
    percentile_num = best_percentile.split('_')[-1]
    print(f"   📝 Meaning: Analyzes top {percentile_num}% of race finishers")
    if int(percentile_num) >= 90:
        print(f"   🏃 Focus: Entire race field including strugglers")
    elif int(percentile_num) >= 70:
        print(f"   🚴 Focus: Main field performance excluding only DNFs")
    else:
        print(f"   🏁 Focus: Elite performance excluding back-of-pack")
    
    # Show WHY it was chosen
    if best_percentile in correlation_analysis['percentile_quality_metrics']:
        metrics = correlation_analysis['percentile_quality_metrics'][best_percentile]
        print(f"\n   📊 Why {best_percentile} was selected:")
        print(f"   • Signal Strength: {metrics['signal_strength']:.4f} (higher = better rider differentiation)")
        print(f"   • Feature Coverage: {metrics['feature_coverage']:.1%} (features with multi-rider data)")
        print(f"   • Mean Correlation: {metrics['mean_abs_correlation']:.4f} (rider-feature relationship strength)")
    
    # Show comparison with alternatives
    print(f"\n   🔍 Comparison with alternatives:")
    scores = percentile_rec['percentile_scores']
    sorted_percentiles = sorted(scores.items(), key=lambda x: x[1]['combined_score'], reverse=True)
    
    for i, (percentile, score_data) in enumerate(sorted_percentiles[:3], 1):
        status = "👑 SELECTED" if i == 1 else f"#{i} alternative"
        print(f"   {status:12} {percentile}: {score_data['combined_score']:.4f}")
        if i == 1:
            print(f"               ↳ Best balance of correlation quality + clustering")
        elif score_data['correlation_score'] > score_data['clustering_score']:
            print(f"               ↳ Strong correlations but weaker rider grouping")
        else:
            print(f"               ↳ Good rider grouping but weaker correlations")
    
    # Feature recommendations with explanations
    print(f"\n2. FEATURE SELECTION PROCESS")
    print("-" * 28)
    
    summary = recommendations['summary']
    feature_rec = recommendations['feature_recommendations']
    
    print(f"🎯 Selected {summary['feature_count']} features from ~45 available")
    
    if best_percentile in feature_rec:
        selection_info = feature_rec[best_percentile]
        reduction_stats = selection_info['redundancy_reduction']
        
        print(f"\n   📝 Selection Process:")
        print(f"   1. Quality Ranking: All features scored on correlation strength & discriminative power")
        print(f"   2. Redundancy Removal: {reduction_stats['features_removed']} redundant features removed")
        print(f"   3. Final Selection: Kept highest-quality non-redundant features")
        
        print(f"\n   📉 Redundancy Reduction Details:")
        print(f"   • Removed: {reduction_stats['features_removed']} features ({reduction_stats['reduction_rate']:.1%})")
        print(f"   • Reason: Features with >75% correlation to higher-quality features")
        print(f"   • Benefit: Eliminates information overlap while preserving signal")
    
    print(f"\n   🏅 Top Selected Features (showing first 10):")
    for i, feature in enumerate(summary['recommended_features'][:10], 1):
        # Add brief explanation of what the feature likely measures
        if 'variance' in feature.lower():
            explanation = "(race competitiveness)"
        elif 'gini' in feature.lower():
            explanation = "(result distribution)"
        elif 'percentile_gap' in feature.lower():
            explanation = "(time gaps)"
        elif 'group' in feature.lower():
            explanation = "(bunch dynamics)"
        elif 'selection' in feature.lower():
            explanation = "(race difficulty)"
        else:
            explanation = "(race characteristic)"
        
        print(f"   {i:2d}. {feature:<25} {explanation}")
    
    if len(summary['recommended_features']) > 10:
        print(f"   ... and {len(summary['recommended_features']) - 10} more features")
    
    # Clustering insights with implications
    print(f"\n3. EXPECTED RIDER CLASSIFICATION")
    print("-" * 30)
    
    if best_percentile in clustering_analysis.get('percentile_analyses', {}):
        cluster_data = clustering_analysis['percentile_analyses'][best_percentile]
        optimal_k = cluster_data.get('optimal_k', 'N/A')
        
        if optimal_k != 'N/A' and optimal_k in cluster_data.get('clustering_results', {}):
            cluster_results = cluster_data['clustering_results'][optimal_k]
            silhouette = cluster_results['silhouette_score']
            cluster_sizes = cluster_results['cluster_sizes']
            
            print(f"🎯 Rider Types: {optimal_k} distinct groups expected")
            print(f"📊 Separation Quality: {silhouette:.4f}", end="")
            
            if silhouette > 0.5:
                print(" (Excellent - clear rider specializations)")
            elif silhouette > 0.3:
                print(" (Good - identifiable rider types)")
            else:
                print(" (Moderate - some overlap between types)")
            
            print(f"👥 Group Sizes: {cluster_sizes}")
            
            # Interpret what this means
            print(f"\n   📝 What this means:")
            print(f"   • Riders will be classified into {optimal_k} performance-based types")
            print(f"   • Types based on how riders perform relative to {best_percentile} race characteristics")
            print(f"   • Classification uses {summary['feature_count']} race features (e.g., competitiveness, time gaps)")
            
            if optimal_k == 3:
                print(f"   • Likely types: Specialists, All-rounders, Situational performers")
            elif optimal_k == 4:
                print(f"   • Likely types: Multiple specialization categories")
            elif optimal_k >= 5:
                print(f"   • Multiple nuanced performance categories")
    
    print(f"\n4. NEXT STEPS")
    print("-" * 10)
    print(f"✅ Ready for rider kind analysis with:")
    print(f"   • Percentile: {best_percentile}")
    print(f"   • Features: {summary['feature_count']} optimized features")
    print(f"   • Expected outcome: {optimal_k if 'optimal_k' in locals() else 'Multiple'} rider types")
    print(f"   • Confidence: Based on {results['analysis_metadata']['total_rider_results']} rider results")


def step4_export_final_dataset(output_dir: str = "correlation_data", results: dict = None):
    """
    Step 4: Export optimized dataset based on feature selection results
    """
    print("\n" + "="*60)
    print("STEP 4: EXPORTING OPTIMIZED DATASET")
    print("="*60)
    
    if results is None:
        # Load results if not provided
        with open(f"{output_dir}/feature_selection_results.json", 'r') as f:
            results = json.load(f)
    
    # Get recommendations
    recommendations = results['recommendations']
    best_percentile = recommendations['summary']['recommended_percentile']
    recommended_features = recommendations['summary']['recommended_features']
    
    print(f"\nBased on analysis:")
    print(f"  Best percentile: {best_percentile}")
    print(f"  Recommended features: {len(recommended_features)}")
    
    # Load optimized dataset
    loader = CorrelationDataLoader(output_dir)
    
    # Export filtered dataset
    print(f"\nExporting optimized dataset...")
    optimized_df = loader.load_for_specific_analysis(
        percentile=best_percentile,
        features=recommended_features
    )
    
    # Save in multiple formats
    export_dir = Path(output_dir) / "optimized_export"
    export_dir.mkdir(exist_ok=True)
    
    # Parquet for efficiency
    optimized_df.to_parquet(
        export_dir / "optimized_correlations.parquet",
        compression='snappy'
    )
    
    # CSV for compatibility
    optimized_df.to_csv(
        export_dir / "optimized_correlations.csv",
        index=False
    )
    
    # Save configuration
    config = {
        'export_date': datetime.now().isoformat(),
        'percentile': best_percentile,
        'features': recommended_features,
        'total_records': len(optimized_df),
        'unique_riders': optimized_df['rider_result_id'].nunique()
    }
    
    with open(export_dir / "export_config.json", 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Exported optimized dataset to {export_dir}")
    print(f"  Records: {len(optimized_df)}")
    print(f"  File size: {(export_dir / 'optimized_correlations.parquet').stat().st_size / 1024 / 1024:.2f} MB")


def main():
    """Run the complete pipeline."""
    db_path = "database/database/cycling_races.db"
    output_dir = "correlation_data"
    
    # Check if database exists
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        print("Please update the db_path variable with your database location.")
        return
    
    print("🚴 RIDER EMBEDDINGS PIPELINE")
    print("="*60)
    print("This pipeline will:")
    print("1. Generate rider performance correlations")
    print("2. Optimize storage with parquet files")
    print("3. Run feature selection analysis")
    print("4. Export optimized dataset")
    print("="*60)
    
    # Ask user for mode
    response = input("\nGenerate sample data (S) or full dataset (F)? [S/F]: ").strip().upper()
    sample_mode = response != 'F'
    
    if not sample_mode:
        confirm = input("⚠️  Full generation may take hours. Continue? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return
    
    try:
        # Run pipeline steps
        step1_generate_correlations(db_path, output_dir, sample_mode)
        step2_optimize_storage(output_dir)
        results = step3_run_feature_selection(output_dir)
        interpret_results(results)
        step4_export_final_dataset(output_dir, results)
        
        print("\n" + "="*60)
        print("🎉 PIPELINE COMPLETE!")
        print("="*60)
        
        # Print final recommendations
        recommendations = results['recommendations']['summary']
        print(f"\n📊 Final Recommendations:")
        print(f"   Percentile: {recommendations['recommended_percentile']}")
        print(f"   Features: {recommendations['feature_count']} selected")
        print(f"\n📁 All outputs saved to: {output_dir}/")
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()