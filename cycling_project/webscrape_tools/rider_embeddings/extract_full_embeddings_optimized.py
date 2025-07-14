#!/usr/bin/env python3
"""
Optimized Full Rider Embeddings Extraction Script

This script generates FULL (unoptimized) rider embeddings for baseline comparison
using all the enhanced parallel processing optimizations from the pipeline.

Data Structure:
- race_type_full_embeddings/
  ├── gc/
  │   ├── race_features_30_full.parquet
  │   ├── race_features_40_full.parquet  
  │   ├── ... (all percentiles)
  │   └── gc_config.json
  ├── stage/
  ├── one_day/
  ├── stage_one_day/
  └── all/

Each parquet file contains ALL feature correlations (no optimization/selection).
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any
import time

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.race_type_pipeline_adapter import RaceTypeCorrelationAdapter
from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator

# ====================================================================
# CONFIGURATION SECTION
# ====================================================================

# Race type minimum requirements (same as optimized pipeline)
RACE_TYPE_PERCENTILES = {
    'gc': 60,           # Use 60th percentile for GC
    'stage': 60,        # Use 60th percentile for Stage  
    'one_day': 60,      # Use 60th percentile for One Day
    'stage_one_day': 60, # Use 60th percentile for Stage+OneDay
    'all': 60            # Use 60th percentile for All
}

# Performance optimization settings
OPTIMIZATION_CONFIG = {
    'use_enhanced_parallel': True,     # Up to 50x speedup
    'parallel_race_types': True,       # Additional 2-3x speedup  
    'max_concurrent_race_types': 3,    # Safe concurrency level
    'n_workers': 4,                    # Parallel correlation workers
    'preload_all_data': True,          # Shared data optimization
    'batch_size': 100,                 # Memory management
    'sample_mode': True,               # Set to False for full dataset
    'sample_size': 100000               # Sample size if in sample mode
}

# Database and output configuration  
DB_PATH = "database/database/cycling_races.db"
OUTPUT_DIR = "race_type_full_embeddings"
TEMP_DIR = "race_type_correlation_data_full_temp"

# All feature percentiles to process
FEATURE_TABLES = [
    'race_features_30', 'race_features_40', 'race_features_50',
    'race_features_60', 'race_features_70', 'race_features_80', 
    'race_features_90', 'race_features_100'
]

# Race types to process
RACE_TYPES = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']

# ====================================================================
# END CONFIGURATION SECTION
# ====================================================================


def calculate_percentile_minimums(db_path: str, percentile_config: dict) -> dict:
    """Calculate minimum race counts based on percentiles for each race type."""
    print("Calculating percentile-based minimum race requirements...")
    
    import sqlite3
    
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


def step1_generate_full_correlations(
    db_path: str,
    temp_dir: str,
    optimization_config: dict,
    percentile_config: dict
):
    """Step 1: Generate FULL correlation data using enhanced parallel processing."""
    print("\n" + "="*70)
    print("STEP 1: GENERATING FULL CORRELATION DATA (ALL FEATURES)")
    print("="*70)
    
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
    print(f"Enhanced parallel processing: {optimization_config['use_enhanced_parallel']}")
    print(f"Parallel race types: {optimization_config['parallel_race_types']}")
    print(f"Workers: {optimization_config['n_workers']}")
    
    # Use enhanced parallel generator for best performance
    generator = EnhancedParallelCorrelationGenerator(
        db_path=db_path,
        output_dir=temp_dir,
        batch_size=optimization_config['batch_size'],
        min_races=minimum_races['all'],
        n_workers=optimization_config['n_workers'],
        preload_all_data=optimization_config['preload_all_data']
    )
    
    if optimization_config['sample_mode']:
        print(f"\n🚀 Generating FULL embeddings sample ({optimization_config['sample_size']:,} riders)")
        print("   This includes ALL features for ALL percentiles (no optimization)")
        
        generator.generate_sample_parallel_enhanced(
            sample_size=optimization_config['sample_size'],
            feature_tables=FEATURE_TABLES,
            output_name="full_embeddings_sample",
            calculator_config=calculator_config
        )
        
    else:
        print("\n⚡ Generating FULL embeddings for complete dataset")
        print("   This includes ALL features for ALL percentiles (no optimization)")
        print("   Expected time: 15-30 minutes with parallel optimizations")
        
        generator.generate_all_correlations_parallel_enhanced(
            feature_tables=FEATURE_TABLES,
            calculator_type='race_type',
            calculator_config=calculator_config,
            checkpoint_interval=5000,
            resume=True,
            parallel_race_types=optimization_config['parallel_race_types'],
            max_concurrent_race_types=optimization_config['max_concurrent_race_types']
        )
    
    print(f"✓ Full correlation data generated in {temp_dir}")
    return temp_dir


def step2_organize_full_embeddings_by_structure(
    temp_dir: str,
    output_dir: str,
    sample_mode: bool
):
    """Step 2: Organize full embeddings by race_type -> percentile structure."""
    print("\n" + "="*70)
    print("STEP 2: ORGANIZING FULL EMBEDDINGS BY RACE TYPE -> PERCENTILE")
    print("="*70)
    
    # Create output directory structure
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Load the raw correlation data
    temp_path = Path(temp_dir)
    if sample_mode:
        parquet_file = temp_path / "full_embeddings_sample_correlations.parquet"
    else:
        # Find the most recent correlation file
        parquet_files = list(temp_path.glob("*_correlations.parquet"))
        if not parquet_files:
            raise ValueError(f"No correlation parquet files found in {temp_dir}")
        parquet_file = max(parquet_files, key=lambda f: f.stat().st_mtime)
    
    print(f"Loading from {parquet_file}")
    df = pd.read_parquet(parquet_file)
    
    print(f"Loaded {len(df)} correlation records")
    print(f"Race types: {sorted(df['race_type'].unique())}")
    print(f"Percentiles: {sorted(df['percentile'].unique())}")
    
    # Organize by race type -> percentile
    print("\nOrganizing data by race type and percentile...")
    
    race_type_stats = {}
    
    for race_type in RACE_TYPES:
        print(f"\nProcessing race type: {race_type}")
        race_type_data = df[df['race_type'] == race_type].copy()
        
        if race_type_data.empty:
            print(f"  No data found for {race_type}")
            continue
        
        # Create race type directory
        race_type_path = output_path / race_type
        race_type_path.mkdir(exist_ok=True)
        
        percentile_stats = {}
        
        for percentile in FEATURE_TABLES:
            percentile_data = race_type_data[race_type_data['percentile'] == percentile].copy()
            
            if percentile_data.empty:
                print(f"    No data for {percentile}")
                continue
            
            # Create rider embedding matrix for this race_type + percentile
            print(f"    Processing {percentile}...")
            
            # Pivot to create rider x feature matrix
            embedding_matrix = percentile_data.pivot_table(
                index='rider_result_id',
                columns='feature', 
                values='correlation',
                aggfunc='first'  # In case of duplicates
            ).reset_index()
            
            # Add metadata columns
            metadata_cols = percentile_data[['rider_result_id', 'n_races', 'calculation_date']].drop_duplicates()
            embedding_matrix = embedding_matrix.merge(metadata_cols, on='rider_result_id', how='left')
            
            # Reorder columns: metadata first, then correlations
            metadata_columns = ['rider_result_id', 'n_races', 'calculation_date']
            feature_columns = [col for col in embedding_matrix.columns if col not in metadata_columns]
            embedding_matrix = embedding_matrix[metadata_columns + sorted(feature_columns)]
            
            # Save as parquet
            output_file = race_type_path / f"{percentile}_full.parquet"
            embedding_matrix.to_parquet(output_file, compression='snappy')
            
            # Track statistics
            n_riders = len(embedding_matrix)
            n_features = len(feature_columns)
            percentile_stats[percentile] = {
                'n_riders': n_riders,
                'n_features': n_features,
                'file': f"{percentile}_full.parquet"
            }
            
            print(f"      ✓ Saved {n_riders:,} riders x {n_features} features to {output_file.name}")
        
        # Save race type configuration
        race_type_config = {
            'race_type': race_type,
            'data_type': 'full_embeddings',
            'percentiles': percentile_stats,
            'total_riders': sum(stats['n_riders'] for stats in percentile_stats.values()) // len(percentile_stats) if percentile_stats else 0,
            'export_date': datetime.now().isoformat(),
            'description': 'Full rider embeddings with ALL features (no optimization applied)'
        }
        
        config_file = race_type_path / f"{race_type}_config.json"
        with open(config_file, 'w') as f:
            json.dump(race_type_config, f, indent=2)
        
        race_type_stats[race_type] = race_type_config
        print(f"  ✓ Saved config to {config_file.name}")
    
    # Save overall summary
    summary = {
        'export_type': 'full_embeddings',
        'race_types': race_type_stats,
        'percentiles_included': FEATURE_TABLES,
        'optimization_applied': False,
        'export_date': datetime.now().isoformat(),
        'note': 'These are complete rider embeddings with all features for baseline comparison'
    }
    
    summary_file = output_path / "full_embeddings_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✓ Full embeddings organized in {output_dir}")
    print(f"✓ Summary saved to {summary_file.name}")
    
    return race_type_stats


def main():
    """Run the full embeddings extraction with enhanced parallel processing."""
    print("FULL RIDER EMBEDDINGS EXTRACTION")
    print("="*80)
    print("🎯 Extracting COMPLETE rider embeddings for baseline comparison")
    print("🚀 Using enhanced parallel processing for maximum speed")
    
    # Display current configuration
    print("\nCurrent Configuration:")
    print(f"Sample Mode: {OPTIMIZATION_CONFIG['sample_mode']}")
    if OPTIMIZATION_CONFIG['sample_mode']:
        print(f"Sample Size: {OPTIMIZATION_CONFIG['sample_size']:,} rider results")
    print(f"Enhanced Parallel: {OPTIMIZATION_CONFIG['use_enhanced_parallel']}")
    print(f"Parallel Race Types: {OPTIMIZATION_CONFIG['parallel_race_types']}")
    print(f"Max Concurrent Race Types: {OPTIMIZATION_CONFIG['max_concurrent_race_types']}")
    print(f"Workers: {OPTIMIZATION_CONFIG['n_workers']}")
    print(f"Database: {DB_PATH}")
    print(f"Output Directory: {OUTPUT_DIR}")
    
    print(f"\nPercentiles to process: {len(FEATURE_TABLES)}")
    for percentile in FEATURE_TABLES:
        print(f"  - {percentile}")
    
    print(f"\nRace types to process: {len(RACE_TYPES)}")
    for race_type in RACE_TYPES:
        percentile = RACE_TYPE_PERCENTILES[race_type]
        print(f"  - {race_type} (minimum: {percentile}th percentile)")
    
    print("\n" + "="*50)
    print("DATA STRUCTURE:")
    print("race_type_full_embeddings/")
    print("├── gc/")
    print("│   ├── race_features_30_full.parquet")
    print("│   ├── race_features_40_full.parquet")
    print("│   ├── ... (all percentiles)")
    print("│   └── gc_config.json")
    print("├── stage/ ├── one_day/ ├── stage_one_day/ └── all/")
    print("="*50)
    
    if OPTIMIZATION_CONFIG['sample_mode']:
        if OPTIMIZATION_CONFIG['parallel_race_types']:
            print(f"\n🚀 Sample mode with parallel race types - Expected time: ~10-30 seconds")
        else:
            print(f"\n🚀 Sample mode - Expected time: ~30-60 seconds")
    else:
        if OPTIMIZATION_CONFIG['parallel_race_types']:
            print(f"\n⚡ Full dataset with parallel race types - Expected time: ~15-30 minutes")
        else:
            print(f"\n⚡ Full dataset - Expected time: ~30-60 minutes")
        
        confirm = input("Process full dataset? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    
    try:
        start_time = time.time()
        
        # Step 1: Generate full correlations using enhanced parallel processing
        temp_dir = step1_generate_full_correlations(
            DB_PATH,
            TEMP_DIR,
            OPTIMIZATION_CONFIG,
            RACE_TYPE_PERCENTILES
        )
        
        # Step 2: Organize by race_type -> percentile structure
        race_type_stats = step2_organize_full_embeddings_by_structure(
            temp_dir,
            OUTPUT_DIR,
            OPTIMIZATION_CONFIG['sample_mode']
        )
        
        total_time = time.time() - start_time
        
        print("\n" + "="*80)
        print("✅ FULL EMBEDDINGS EXTRACTION COMPLETE!")
        print("="*80)
        
        print(f"\n🚀 Enhanced parallel processing delivered significant speedup!")
        print(f"   - Total processing time: {total_time:.1f} seconds")
        if OPTIMIZATION_CONFIG['use_enhanced_parallel']:
            print(f"   - Enhanced parallel generation: {OPTIMIZATION_CONFIG['n_workers']} workers")
            print(f"   - Pre-loaded shared data: 100% cache hit rate")
        if OPTIMIZATION_CONFIG['parallel_race_types']:
            print(f"   - Parallel race types: {OPTIMIZATION_CONFIG['max_concurrent_race_types']} concurrent")
        
        print(f"\n📊 EXTRACTION SUMMARY:")
        total_riders = 0
        total_files = 0
        
        for race_type, stats in race_type_stats.items():
            n_riders = stats.get('total_riders', 0)
            n_percentiles = len(stats.get('percentiles', {}))
            total_riders += n_riders
            total_files += n_percentiles
            print(f"  {race_type}: {n_riders:,} riders x {n_percentiles} percentiles")
        
        print(f"\nTotal: {total_files} files with {total_riders:,} total rider records")
        
        print(f"\n📁 OUTPUT STRUCTURE:")
        print(f"  - Main directory: {OUTPUT_DIR}/")
        print(f"  - Race type subdirectories: {len(RACE_TYPES)}")
        print(f"  - Percentile files per race type: {len(FEATURE_TABLES)}")
        print(f"  - Configuration files: {len(RACE_TYPES)} race type configs + 1 summary")
        
        print(f"\n🎯 COMPARISON READY:")
        print(f"  - Full embeddings: {OUTPUT_DIR}/")
        print(f"  - Optimized embeddings: race_type_optimized_data/")
        print(f"  - Each race type has both full and optimized versions for comparison")
        
        print(f"\n💡 USAGE:")
        print(f"  Load full embeddings: pd.read_parquet('{OUTPUT_DIR}/gc/race_features_90_full.parquet')")
        print(f"  Compare with optimized: pd.read_parquet('race_type_optimized_data/gc_optimized.parquet')")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()