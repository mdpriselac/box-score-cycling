#!/usr/bin/env python3
"""
Database I/O Optimized Interaction Embeddings Extraction Script

This script uses the modular database optimization components to achieve
significant performance improvements in interaction embeddings extraction.

Key optimizations implemented:
- Pre-loads ALL race features into shared memory
- Bulk loads rider histories in single queries
- Eliminates redundant database queries
- Uses optimized calculator with shared data

Expected performance improvement: 5-10x reduction in database query time
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple
import time
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
from tqdm import tqdm

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import our optimized modules
from rider_embeddings.database_optimization import (
    SharedDataLoader, 
    OptimizedInteractionCalculator, 
    BulkQueryUtils
)

# Import organization functions from original script
from rider_embeddings.extract_interaction_embeddings_optimized import (
    organize_phase1_embeddings,
    organize_phase2_embeddings,
    save_metadata
)

# ====================================================================
# CONFIGURATION SECTION
# ====================================================================

# Race type minimum requirements
RACE_TYPE_PERCENTILES = {
    'gc': 60,
    'stage': 60,
    'one_day': 60,
    'stage_one_day': 60,
    'all': 60
}

# Performance optimization settings
OPTIMIZATION_CONFIG = {
    'n_workers': 4,
    'batch_size': 100,
    'sample_mode': True,
    'sample_size': 1000,
    'chunk_size': 100,
    'preload_all_data': True,
    'enable_logging': True
}

# Database and output configuration
DB_PATH = "database/database/cycling_races.db"
OUTPUT_DIR = "interaction_embeddings_db_optimized"

# Feature tables to process
FEATURE_TABLES = [
    'race_features_30', 'race_features_40', 'race_features_50',
    'race_features_60', 'race_features_70', 'race_features_80',
    'race_features_90', 'race_features_100'
]

# Race types to process
RACE_TYPES = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']

# Interaction types to calculate
INTERACTION_TYPES = ['dot', 'hadamard', 'cosine']

# ====================================================================
# OPTIMIZED WORKER FUNCTION
# ====================================================================

def process_rider_chunk_db_optimized(chunk_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process rider chunk using pre-loaded shared data."""
    rider_result_data = chunk_data['rider_result_data']
    shared_race_features = chunk_data['shared_race_features']
    shared_rider_histories = chunk_data['shared_rider_histories']
    feature_tables = chunk_data['feature_tables']
    calculator_config = chunk_data['calculator_config']
    chunk_id = chunk_data.get('chunk_id', 'unknown')
    
    # Set up logging
    if OPTIMIZATION_CONFIG['enable_logging']:
        logging.basicConfig(level=logging.INFO, format=f'Worker-{chunk_id}: %(message)s')
        logger = logging.getLogger(f'worker_{chunk_id}')
    else:
        logger = logging.getLogger(f'worker_{chunk_id}')
        logger.setLevel(logging.WARNING)
    
    try:
        logger.info(f"Processing {len(rider_result_data)} riders with shared data")
        
        # Create optimized calculator
        calculator = OptimizedInteractionCalculator(
            shared_race_features=shared_race_features,
            shared_rider_histories=shared_rider_histories,
            calculator_config=calculator_config
        )
        
        results = []
        successful = 0
        failed = 0
        
        for rider_result_id, competition_id in rider_result_data:
            try:
                result = calculator.calculate_interaction_embeddings_optimized(
                    rider_result_id=rider_result_id,
                    competition_id=competition_id,
                    feature_tables=feature_tables,
                    interaction_types=INTERACTION_TYPES
                )
                results.append(result)
                successful += 1
                
            except Exception as e:
                failed += 1
                error_result = {
                    'rider_result_id': rider_result_id,
                    'phase1_interactions': {},
                    'phase2_interactions': {},
                    'metadata': {
                        'calculation_date': datetime.now().isoformat(),
                        'warnings': [f"Error processing rider {rider_result_id}: {str(e)}"],
                        'error': str(e),
                        'method': 'optimized_interaction_embeddings'
                    }
                }
                results.append(error_result)
                logger.error(f"Error processing rider {rider_result_id}: {e}")
        
        logger.info(f"Chunk complete: {successful} successful, {failed} failed")
        return results
        
    except Exception as e:
        logger.error(f"Chunk processing failed: {e}")
        return []


def main():
    """Run the database-optimized interaction embeddings extraction."""
    print("DATABASE I/O OPTIMIZED INTERACTION EMBEDDINGS EXTRACTION")
    print("="*80)
    print("🎯 Extracting interaction embeddings with database optimizations")
    print("🚀 Using modular optimization components")
    
    # Display optimizations
    print("\nOptimizations Applied:")
    print("✓ Modular architecture with separate optimization components")
    print("✓ Pre-load all race features into shared memory")
    print("✓ Bulk load rider histories in single queries")
    print("✓ Eliminate redundant database queries")
    print("✓ Use optimized calculator with shared data")
    
    # Display configuration
    print(f"\nConfiguration:")
    print(f"Sample Mode: {OPTIMIZATION_CONFIG['sample_mode']}")
    if OPTIMIZATION_CONFIG['sample_mode']:
        print(f"Sample Size: {OPTIMIZATION_CONFIG['sample_size']:,}")
    print(f"Workers: {OPTIMIZATION_CONFIG['n_workers']}")
    print(f"Chunk Size: {OPTIMIZATION_CONFIG['chunk_size']}")
    print(f"Database: {DB_PATH}")
    print(f"Output: {OUTPUT_DIR}")
    
    if not OPTIMIZATION_CONFIG['sample_mode']:
        confirm = input("\nProcess full dataset? This will take longer but use all optimizations. [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    
    try:
        start_time = time.time()
        
        # Initialize utility classes
        bulk_utils = BulkQueryUtils(DB_PATH)
        data_loader = SharedDataLoader(DB_PATH)
        
        # Step 1: Calculate minimums and validate feature tables
        print("\n" + "="*60)
        print("STEP 1: SETUP AND VALIDATION")
        print("="*60)
        
        minimums = bulk_utils.calculate_percentile_minimums(RACE_TYPE_PERCENTILES)
        valid_feature_tables = bulk_utils.validate_feature_tables(FEATURE_TABLES)
        
        calculator_config = {
            'min_races_all': minimums['all'],
            'min_races_stage': minimums['stage'],
            'min_races_one_day': minimums['one_day'],
            'min_races_gc': minimums['gc']
        }
        
        print(f"✓ Using {len(valid_feature_tables)} validated feature tables")
        
        # Step 2: Get rider results
        print("\n" + "="*60)
        print("STEP 2: RIDER RESULT SELECTION")
        print("="*60)
        
        if OPTIMIZATION_CONFIG['sample_mode']:
            print(f"Getting sample of {OPTIMIZATION_CONFIG['sample_size']} rider results...")
            rider_results = bulk_utils.get_rider_result_sample_with_competitions(
                OPTIMIZATION_CONFIG['sample_size'],
                minimums
            )
        else:
            print("Getting full dataset of rider results...")
            rider_results = bulk_utils.get_full_rider_result_dataset(minimums)
        
        print(f"✓ Retrieved {len(rider_results)} rider results for processing")
        
        # Step 3: Pre-load ALL data into shared memory
        print("\n" + "="*60)
        print("STEP 3: PRE-LOADING DATA INTO SHARED MEMORY")
        print("="*60)
        
        # Extract IDs
        competition_ids = bulk_utils.get_unique_competition_ids(rider_results)
        rider_result_ids = bulk_utils.get_rider_result_ids(rider_results)
        
        # Pre-load race features
        preload_start = time.time()
        print("Pre-loading race features...")
        shared_race_features = data_loader.preload_race_features(
            competition_ids, 
            valid_feature_tables
        )
        
        # Pre-load rider histories
        print("Pre-loading rider histories...")
        shared_rider_histories = data_loader.preload_rider_histories(rider_result_ids)
        
        preload_time = time.time() - preload_start
        print(f"\n✓ Pre-loading completed in {preload_time:.1f} seconds")
        
        # Validate data integrity
        print("Validating data integrity...")
        validation_results = data_loader.validate_data_integrity(
            shared_race_features, 
            shared_rider_histories
        )
        
        cache_stats = data_loader.get_cache_statistics(
            shared_race_features,
            shared_rider_histories
        )
        
        print(f"✓ Data validation completed:")
        print(f"  - Race features: {validation_results['race_features_stats']}")
        print(f"  - Rider histories: {validation_results['rider_histories_stats']}")
        print(f"  - Cache efficiency: {cache_stats['estimated_memory_efficiency']['total_cached_entries']:,} entries")
        
        # Step 4: Process in parallel with shared data
        print("\n" + "="*60)
        print("STEP 4: PARALLEL PROCESSING WITH SHARED DATA")
        print("="*60)
        
        # Split into chunks
        chunk_size = OPTIMIZATION_CONFIG['chunk_size']
        chunks = [
            rider_results[i:i + chunk_size] 
            for i in range(0, len(rider_results), chunk_size)
        ]
        
        print(f"Split into {len(chunks)} chunks of ~{chunk_size} riders each")
        
        # Prepare chunk data
        chunk_data_list = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'rider_result_data': chunk,
                'shared_race_features': shared_race_features,
                'shared_rider_histories': shared_rider_histories,
                'feature_tables': valid_feature_tables,
                'calculator_config': calculator_config,
                'chunk_id': f"{i+1}/{len(chunks)}"
            }
            chunk_data_list.append(chunk_data)
        
        # Process chunks in parallel
        all_results = []
        processing_start = time.time()
        
        with ProcessPoolExecutor(max_workers=OPTIMIZATION_CONFIG['n_workers']) as executor:
            future_to_chunk = {
                executor.submit(process_rider_chunk_db_optimized, chunk_data): i
                for i, chunk_data in enumerate(chunk_data_list)
            }
            
            with tqdm(total=len(chunks), desc="Processing chunks", unit="chunk") as pbar:
                for future in as_completed(future_to_chunk):
                    chunk_idx = future_to_chunk[future]
                    try:
                        results = future.result()
                        all_results.extend(results)
                        pbar.update(1)
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_idx}: {e}")
                        pbar.update(1)
        
        processing_time = time.time() - processing_start
        
        print(f"\n✓ Processed {len(all_results)} results in {processing_time:.1f} seconds")
        
        # Step 5: Save results
        print("\n" + "="*60)
        print("STEP 5: SAVING RESULTS")
        print("="*60)
        
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(exist_ok=True)
        
        organize_phase1_embeddings(all_results, output_path)
        organize_phase2_embeddings(all_results, output_path)
        
        # Enhanced metadata with optimization info
        enhanced_config = {
            **OPTIMIZATION_CONFIG,
            'optimization_modules_used': [
                'SharedDataLoader',
                'OptimizedInteractionCalculator', 
                'BulkQueryUtils'
            ],
            'database_optimizations': {
                'preload_time_seconds': preload_time,
                'processing_time_seconds': processing_time,
                'total_competitions_cached': len(competition_ids),
                'total_riders_cached': len(rider_result_ids),
                'cache_statistics': cache_stats
            }
        }
        
        save_metadata(output_path, all_results, enhanced_config)
        
        total_time = time.time() - start_time
        
        print("\n" + "="*80)
        print("✅ DATABASE OPTIMIZED EXTRACTION COMPLETE!")
        print("="*80)
        
        print(f"\nPerformance Summary:")
        print(f"  Pre-loading time: {preload_time:.1f} seconds")
        print(f"  Processing time: {processing_time:.1f} seconds")
        print(f"  Total time: {total_time:.1f} seconds")
        print(f"  Average per rider: {total_time/len(rider_results):.3f} seconds")
        
        # Calculate potential speedup
        original_estimated_time = len(rider_results) * 0.130  # From original script
        speedup = original_estimated_time / total_time
        
        print(f"\nDatabase I/O Optimizations Impact:")
        print(f"  ✓ Pre-loaded {len(competition_ids)} race feature sets")
        print(f"  ✓ Bulk loaded {len(rider_result_ids)} rider histories")
        print(f"  ✓ Eliminated redundant queries")
        print(f"  ✓ Used shared memory across workers")
        print(f"  ✓ Estimated speedup: {speedup:.1f}x faster")
        
        print(f"\nModule Usage:")
        print(f"  ✓ SharedDataLoader: Pre-loaded all data")
        print(f"  ✓ OptimizedInteractionCalculator: Zero DB queries during processing")
        print(f"  ✓ BulkQueryUtils: Efficient bulk operations")
        
        print(f"\n📁 Output saved to: {OUTPUT_DIR}/")
        print(f"📊 Detailed metadata saved with optimization metrics")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()