#!/usr/bin/env python3
"""Test the optimized dataset generator with pre-computed features."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rider_performance'))

from rider_performance.optimized_dataset_generator import OptimizedDatasetGenerator
import time

def test_optimized_generator():
    """Test the optimized generator with pre-computed features."""
    db_path = "database/database/cycling_races.db"
    
    print("Testing optimized dataset generator with pre-computed features...")
    print("=" * 80)
    
    # Initialize generator
    generator = OptimizedDatasetGenerator(db_path)
    
    print(f"Experience feature count: {len(generator.experience_feature_names)}")
    print(f"Experience features: {generator.experience_feature_names}")
    print()
    
    # Test with a small dataset
    print("Generating small test dataset...")
    start_time = time.time()
    
    datasets = generator.generate_datasets_fast(
        cutoff_date="2010-12-31",
        min_results=100,
        target_variable='uci_points_actual',
        use_parallel=False  # Use sequential for testing
    )
    
    elapsed = time.time() - start_time
    print(f"Generated datasets in {elapsed:.2f} seconds")
    
    # Check results
    gc_dataset = datasets['gc_dataset']
    stage_one_day_dataset = datasets['stage_one_day_dataset']
    
    print(f"GC dataset: {len(gc_dataset)} rows")
    print(f"Stage/One-day dataset: {len(stage_one_day_dataset)} rows")
    
    if len(gc_dataset) > 0:
        print("\nGC dataset columns:")
        print(f"  Total columns: {len(gc_dataset.columns)}")
        
        # Check experience features
        experience_cols = [col for col in gc_dataset.columns if col in generator.experience_feature_names]
        print(f"  Experience features found: {len(experience_cols)}")
        
        # Show sample experience features
        print("\nSample experience features from first row:")
        first_row = gc_dataset.iloc[0]
        for feat in ['total_prior_races', 'prior_wt_races', 'prior_wt_proportion', 'overall_success_rate']:
            if feat in first_row:
                print(f"  {feat}: {first_row[feat]}")
        
        # Check for pre-computed features
        print("\nPre-computed features check:")
        precomputed_features = ['prior_wt_points_actual', 'prior_gc_points_actual', 'total_prior_points_actual']
        for feat in precomputed_features:
            if feat in first_row:
                print(f"  {feat}: {first_row[feat]}")
            else:
                print(f"  {feat}: MISSING")
    
    if len(stage_one_day_dataset) > 0:
        print(f"\nStage/One-day dataset columns: {len(stage_one_day_dataset.columns)}")
        
        # Check experience features
        experience_cols = [col for col in stage_one_day_dataset.columns if col in generator.experience_feature_names]
        print(f"  Experience features found: {len(experience_cols)}")

if __name__ == "__main__":
    test_optimized_generator()