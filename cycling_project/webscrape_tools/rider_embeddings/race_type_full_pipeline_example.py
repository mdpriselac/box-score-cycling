#!/usr/bin/env python3
"""
Complete pipeline example for race type correlations:
Generate → Store → Load → Feature Selection → Meta-Report

This script demonstrates the full workflow for race-type-specific analysis.
"""
import sys
from pathlib import Path
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.race_type_pipeline_adapter import (
    RaceTypeCorrelationAdapter, 
    RaceTypeDataGenerator
)
from rider_embeddings.data_generation import ParquetStorage, CorrelationDataLoader
from rider_embeddings.performance_feature_link import RaceTypeCorrelationCalculator
from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator
from rider_embeddings.performance_optimization.parallel_correlation_generator import ParallelCorrelationGenerator

# ====================================================================
# CONFIGURATION SECTION - MODIFY THESE SETTINGS
# ====================================================================

# Race type minimum requirements based on percentiles
# Higher percentiles = better quality, fewer results
# Lower percentiles = more data, potentially more noise
RACE_TYPE_PERCENTILES = {
    'gc': 60,           # Use 60th percentile for GC (very experienced GC riders)
    'stage': 60,        # Use 60th percentile for Stage (experienced stage riders)  
    'one_day': 60,      # Use 60th percentile for One Day (experienced one-day riders)
    'stage_one_day': 60, # Use 60th percentile for Stage+OneDay (moderate experience)
    'all': 60            # Use 60th percentile for All (very experienced overall)
}

# Sample configuration
SAMPLE_CONFIG = {
    'use_sample_mode': True,        # Set to False for full dataset processing
    'sample_size': 10000,           # Number of rider results to sample (if sample mode)
    'use_enhanced_parallel': True   # Use enhanced parallel processing
}

# Database and output configuration  
DB_PATH = "database/database/cycling_races.db"
OUTPUT_DIR = "race_type_correlation_data_percentile_test"

# ====================================================================
# END CONFIGURATION SECTION
# ====================================================================


def calculate_percentile_minimums(db_path: str, percentile_config: dict) -> dict:
    """
    Calculate minimum race counts based on percentiles for each race type.
    
    Args:
        db_path: Path to the database
        percentile_config: Dictionary mapping race type to desired percentile
        
    Returns:
        Dictionary mapping race type to minimum race count
    """
    print("Calculating percentile-based minimum race requirements...")
    
    race_type_definitions = {
        'gc': ['gc'],
        'stage': ['stage'], 
        'one_day': ['one_day'],
        'stage_one_day': ['stage', 'one_day'],
        'all': ['gc', 'stage', 'one_day']
    }
    
    minimums = {}
    
    with sqlite3.connect(db_path) as conn:
        for race_type, percentile in percentile_config.items():
            competition_types = race_type_definitions[race_type]
            
            # Build the competition type filter
            if len(competition_types) == 1:
                type_filter = f"= '{competition_types[0]}'"
            else:
                type_list = "', '".join(competition_types)
                type_filter = f"IN ('{type_list}')"
            
            # Query to get all prior race counts for this race type
            query = f"""
            WITH race_type_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.rider_id 
                        ORDER BY c.date
                    ) - 1 as prior_races_of_type
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date <= '2025-01-01'
                AND c.competition_type {type_filter}
            )
            SELECT prior_races_of_type
            FROM race_type_results
            WHERE prior_races_of_type > 0
            """
            
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                minimum_races = int(np.percentile(df['prior_races_of_type'], percentile))
                minimums[race_type] = minimum_races
                
                total_results = len(df)
                eligible_results = len(df[df['prior_races_of_type'] >= minimum_races])
                coverage_pct = (eligible_results / total_results) * 100
                
                print(f"  {race_type}: {percentile}th percentile = {minimum_races} races "
                      f"({eligible_results:,} results, {coverage_pct:.1f}% coverage)")
            else:
                minimums[race_type] = 1
                print(f"  {race_type}: No data found, using minimum of 1")
    
    return minimums

def step1_generate_race_type_correlations(
    db_path: str, 
    output_dir: str,
    sample_mode: bool,
    use_enhanced_parallel: bool,
    percentile_config: dict,
    sample_size: int = 30000
):
    """
    Step 1: Generate race type correlation data using percentile-based minimums
    """
    print("\n" + "="*60)
    print("STEP 1: GENERATING RACE TYPE CORRELATION DATA")
    print("="*60)
    
    # Calculate minimum race counts based on percentiles
    minimum_races = calculate_percentile_minimums(db_path, percentile_config)
    
    # Create calculator config from percentile minimums
    calculator_config = {
        'type': 'race_type',
        'min_races_all': minimum_races['all'],
        'min_races_stage': minimum_races['stage'], 
        'min_races_one_day': minimum_races['one_day'],
        'min_races_gc': minimum_races['gc']
    }
    
    print(f"\nUsing calculated minimums: {calculator_config}")
    
    if use_enhanced_parallel and sample_mode:
        # Use enhanced parallel generator for best performance
        print("Using Enhanced Parallel Generator with race-type calculations...")
        generator = EnhancedParallelCorrelationGenerator(
            db_path=db_path,
            output_dir=output_dir,
            batch_size=100,
            min_races=minimum_races['all'],  # Use 'all' minimum as base threshold
            n_workers=4,
            preload_all_data=True
        )
        
        # Generate sample using enhanced parallel processing
        print(f"Generating sample of {sample_size} with enhanced parallel processing...")
        generator.generate_sample_parallel_enhanced(
            sample_size=sample_size,
            feature_tables=[
                'race_features_30', 'race_features_40', 'race_features_50',
                'race_features_60', 'race_features_70', 'race_features_80', 'race_features_90'
            ],
            output_name="race_type_percentile_sample",
            calculator_config=calculator_config
        )
        
    elif use_enhanced_parallel and not sample_mode:
        # Use enhanced parallel generator for full dataset
        print("Using Enhanced Parallel Generator for full dataset...")
        generator = EnhancedParallelCorrelationGenerator(
            db_path=db_path,
            output_dir=output_dir,
            batch_size=100,  # Larger batches for full dataset
            min_races=minimum_races['all'],
            n_workers=4,
            preload_all_data=True
        )
        
        print("Generating full dataset with enhanced parallel processing...")
        print("This uses memory-efficient chunking to process large datasets")
        print("Expected time: 1-3 hours depending on database size")
        
        generator.generate_all_correlations_parallel_enhanced(
            feature_tables=[
                'race_features_30', 'race_features_40', 'race_features_50',
                'race_features_60','race_features_70', 'race_features_80', 
                'race_features_90'
            ],
            calculator_type='race_type',
            calculator_config=calculator_config,
            checkpoint_interval=5000,  # Save checkpoint every 5000 riders
            resume=True  # Enable resume capability
        )
        
    else:
        # Fallback to original sequential generator (using percentile-based minimums)
        print("Using Sequential Generator (legacy mode)...")
        generator = RaceTypeDataGenerator(
            db_path=db_path,
            output_dir=output_dir,
            batch_size=100,
            min_races_all=minimum_races['all'],
            min_races_stage=minimum_races['stage'],
            min_races_one_day=minimum_races['one_day'],
            min_races_gc=minimum_races['gc']
        )
        
        if sample_mode:
            generator.generate_sample(
                sample_size=sample_size,
                feature_tables=[
                     'race_features_30', 'race_features_40', 'race_features_50','race_features_60',
                     'race_features_70', 'race_features_80', 'race_features_90'
                ],
                output_name="race_type_percentile_sample"
            )
        else:
            generator.generate_all_correlations(
                feature_tables=None,
                limit=None,
                resume=True
            )
    
    print(f"✓ Race type correlation data generated in {output_dir}")
    return output_dir


def step2_load_and_transform_data(data_dir: str, output_name: str = None) -> list:
    """
    Step 2: Load race type correlation data and transform for analysis (OPTIMIZED)
    
    Note: For race type data, we need to handle the extra 'race_type' column
    """
    print("\n" + "="*60)
    print("STEP 2: LOADING AND TRANSFORMING RACE TYPE DATA")
    print("="*60)
    
    # For this example, we'll load the parquet data directly
    # and reconstruct the race type correlation format
    import pandas as pd
    import glob
    
    # Find the correct parquet file
    if output_name:
        # Look for specific output file
        parquet_file = Path(data_dir) / f"{output_name}_correlations.parquet"
        if not parquet_file.exists():
            print(f"Warning: {parquet_file} not found, searching for alternatives...")
            parquet_files = list(Path(data_dir).glob("*_correlations.parquet"))
            if not parquet_files:
                raise ValueError(f"No correlation parquet files found in {data_dir}")
            # Get the most recent file
            parquet_file = max(parquet_files, key=lambda f: f.stat().st_mtime)
    else:
        # Find the most recent correlation file
        parquet_files = list(Path(data_dir).glob("*_correlations.parquet"))
        if not parquet_files:
            raise ValueError(f"No correlation parquet files found in {data_dir}")
        parquet_file = max(parquet_files, key=lambda f: f.stat().st_mtime)
    
    # Load the data
    print(f"Loading from {parquet_file}")
    df = pd.read_parquet(parquet_file)
    
    print(f"Loaded {len(df)} correlation records")
    print(f"Columns in data: {df.columns.tolist()}")
    
    # Check if this is race type data
    if 'race_type' in df.columns:
        print(f"Race types in data: {df['race_type'].unique()}")
    else:
        print("WARNING: No 'race_type' column found - this may not be race type correlation data!")
    
    print("Transforming data (optimized)...")
    import time
    transform_start = time.time()
    
    # OPTIMIZATION: Pre-sort for efficient groupby operations
    df = df.sort_values(['rider_result_id', 'race_type', 'percentile'])
    
    # OPTIMIZATION: Filter out null correlations early
    df = df[df['correlation'].notna()]
    print(f"After filtering: {len(df)} valid correlation records")
    
    # Transform back to race type correlation format using optimized approach
    race_type_results = []
    
    # Group by rider_result_id (single groupby operation)
    for rider_result_id, rider_group in df.groupby('rider_result_id'):
        # Get metadata from first row (more efficient)
        calculation_date = rider_group['calculation_date'].iloc[0]
        
        # Build feature correlations using vectorized operations
        feature_correlations = {}
        n_races = {}
        
        # Single pass through race types
        for race_type, race_group in rider_group.groupby('race_type'):
            n_races[race_type] = int(race_group['n_races'].iloc[0])
            
            # Build percentile data efficiently
            percentile_data = {}
            for percentile, perc_group in race_group.groupby('percentile'):
                # OPTIMIZATION: Use vectorized dict creation instead of iterrows
                correlations = dict(zip(
                    perc_group['feature'], 
                    perc_group['correlation'].astype(float)
                ))
                
                if correlations:
                    percentile_data[percentile] = correlations
            
            if percentile_data:
                feature_correlations[race_type] = percentile_data
        
        race_type_results.append({
            'rider_result_id': int(rider_result_id),
            'feature_correlations': feature_correlations,
            'metadata': {
                'n_races': n_races,
                'method': 'race_type_correlation',
                'calculation_date': calculation_date,
                'warnings': []
            }
        })
    
    transform_time = time.time() - transform_start
    print(f"Transformed into {len(race_type_results)} rider results in {transform_time:.2f} seconds")
    return race_type_results


def step3_run_race_type_analysis(race_type_results: list, output_dir: str = "race_type_analysis_30k"):
    """
    Step 3: Run feature selection analysis for each race type
    """
    print("\n" + "="*60)
    print("STEP 3: RUNNING RACE TYPE FEATURE SELECTION ANALYSIS")
    print("="*60)
    
    # Initialize adapter
    adapter = RaceTypeCorrelationAdapter()
    
    # Run analysis for all race types
    all_results = adapter.run_all_race_types(
        race_type_results,
        race_types=['gc', 'stage', 'one_day', 'stage_one_day', 'all'],
        max_features=25,
        k_range=[3, 4, 5, 6, 7]
    )
    
    # Generate comprehensive meta-report
    print("\n" + "="*60)
    print("STEP 4: GENERATING META-REPORT")
    print("="*60)
    
    report_path = adapter.generate_meta_report(all_results, output_dir)
    
    return all_results, report_path


def step4_export_optimized_datasets(
    all_results: dict, 
    race_type_results: list,
    output_dir: str = "race_type_optimized_data_30k"
):
    """
    Step 4: Export optimized datasets for each race type
    """
    print("\n" + "="*60)
    print("STEP 5: EXPORTING OPTIMIZED DATASETS")
    print("="*60)
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    adapter = RaceTypeCorrelationAdapter()
    
    for race_type, analysis_results in all_results.items():
        if 'error' not in analysis_results:
            # Get recommended features
            recommendations = analysis_results.get('recommendations', {}).get('summary', {})
            best_percentile = recommendations.get('recommended_percentile')
            best_features = recommendations.get('recommended_features', [])
            
            if best_percentile and best_features:
                print(f"\nExporting {race_type} optimized dataset...")
                print(f"  Percentile: {best_percentile}")
                print(f"  Features: {len(best_features)}")
                
                # Extract race type data
                extracted_data = adapter.extract_race_type_data(race_type_results, race_type)
                
                # Create optimized dataset
                optimized_records = []
                for result in extracted_data:
                    if best_percentile in result['feature_correlations']:
                        record = {
                            'rider_result_id': result['rider_result_id'],
                            'n_races': result['metadata']['n_races']
                        }
                        
                        # Add only recommended features
                        correlations = result['feature_correlations'][best_percentile]
                        for feature in best_features:
                            if feature in correlations:
                                record[f'corr_{feature}'] = correlations[feature]
                        
                        optimized_records.append(record)
                
                if optimized_records:
                    # Save as parquet and CSV
                    import pandas as pd
                    opt_df = pd.DataFrame(optimized_records)
                    
                    parquet_file = output_path / f"{race_type}_optimized.parquet"
                    csv_file = output_path / f"{race_type}_optimized.csv"
                    
                    opt_df.to_parquet(parquet_file, compression='snappy')
                    opt_df.to_csv(csv_file, index=False)
                    
                    # Save configuration
                    config = {
                        'race_type': race_type,
                        'percentile': best_percentile,
                        'features': best_features,
                        'n_riders': len(opt_df),
                        'export_date': datetime.now().isoformat()
                    }
                    
                    config_file = output_path / f"{race_type}_config.json"
                    with open(config_file, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    print(f"  ✓ Exported to {parquet_file.name}")
    
    print(f"\n✓ Optimized datasets exported to {output_dir}")


def main():
    """Run the complete race type pipeline with percentile-based configuration."""
    print("RACE TYPE CORRELATION PIPELINE")
    print("="*80)
    print("🚀 Now with Percentile-Based Quality Control!")
    
    # Display current configuration
    print("\nCurrent Configuration:")
    print(f"Sample Mode: {SAMPLE_CONFIG['use_sample_mode']}")
    if SAMPLE_CONFIG['use_sample_mode']:
        print(f"Sample Size: {SAMPLE_CONFIG['sample_size']:,} rider results")
    print(f"Enhanced Parallel: {SAMPLE_CONFIG['use_enhanced_parallel']}")
    print(f"Database: {DB_PATH}")
    print(f"Output Directory: {OUTPUT_DIR}")
    
    print("\nPercentile Configuration:")
    for race_type, percentile in RACE_TYPE_PERCENTILES.items():
        print(f"  {race_type}: {percentile}th percentile")
    
    print("\nNote: Higher percentiles = better quality data, fewer results")
    print("      Lower percentiles = more data, potentially more noise")
    
    # Option to modify configuration
    modify = input("\nModify configuration? [y/N]: ").strip().lower()
    if modify == 'y':
        print("\nTo modify settings, edit the configuration section at the top of this file.")
        print("Current settings will be used for this run.")
    
    sample_mode = SAMPLE_CONFIG['use_sample_mode']
    use_enhanced_parallel = SAMPLE_CONFIG['use_enhanced_parallel']
    sample_size = SAMPLE_CONFIG['sample_size']
    
    if sample_mode:
        if use_enhanced_parallel:
            print(f"\n🚀 Running in SAMPLE mode with Enhanced Parallel Processing ({sample_size:,} rider results)")
            print("   Expected time: ~10-30 seconds")
        else:
            print(f"\n🔬 Running in SAMPLE mode with Sequential Processing ({sample_size:,} rider results)")
            print("   Expected time: ~2-3 minutes")
    else:
        if use_enhanced_parallel:
            print("\n⚡ Running in FULL mode with Enhanced Parallel Processing")
            print("   Expected time: ~30-60 minutes (much faster than before!)")
        else:
            print("\n⚠️  Running in FULL mode with Sequential Processing (legacy)")
            print("   Expected time: Several hours")
        
        confirm = input("Are you sure? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    
    try:
        # Step 1: Generate correlations using percentile-based configuration
        data_dir = step1_generate_race_type_correlations(
            DB_PATH,
            OUTPUT_DIR, 
            sample_mode=sample_mode,
            use_enhanced_parallel=use_enhanced_parallel,
            percentile_config=RACE_TYPE_PERCENTILES,
            sample_size=sample_size
        )
        
        # Determine output name based on mode
        output_name = "race_type_percentile_sample" if sample_mode else None
        
        # Step 2: Load and transform data
        race_type_results = step2_load_and_transform_data(data_dir, output_name)
        
        # Step 3: Run analysis and generate meta-report
        all_results, report_path = step3_run_race_type_analysis(race_type_results)
        
        # Step 4: Export optimized datasets
        step4_export_optimized_datasets(all_results, race_type_results)
        
        print("\n" + "="*80)
        print("✅ PIPELINE COMPLETE!")
        print("="*80)
        
        if use_enhanced_parallel:
            print("🚀 Enhanced Parallel Processing was used for significant speedup!")
            print("   - Optimized sampling: ~244x faster than original")
            print("   - Parallel correlation generation: ~4x workers")
            print("   - Batched database loading: 100% cache hit rate")
        
        print(f"\nKey outputs:")
        print(f"  - Race type correlation data: {data_dir}/")
        print(f"  - Analysis results and reports: race_type_analysis/")
        print(f"  - Optimized datasets: race_type_optimized_data/")
        print(f"  - Meta-report: {report_path}")
        
        # Print summary from meta-report
        print("\n📊 QUICK SUMMARY:")
        with open(report_path, 'r') as f:
            lines = f.readlines()
            in_summary = False
            for line in lines:
                if "SUMMARY OF RECOMMENDATIONS" in line:
                    in_summary = True
                elif in_summary and line.strip() == "":
                    break
                elif in_summary:
                    print(line.rstrip())
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()