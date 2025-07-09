#!/usr/bin/env python3
"""Test the optimized dataset generator with enhanced features."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rider_performance.optimized_dataset_generator import OptimizedDatasetGenerator
import time

def test_optimized_generator():
    """Test the optimized generator with enhanced features."""
    db_path = "database/database/cycling_races.db"
    
    print("Testing optimized dataset generator with enhanced features...")
    print("=" * 80)
    
    # Initialize generator (will use enhanced features by default)
    generator = OptimizedDatasetGenerator(db_path, use_enhanced_experience=True)
    
    print(f"Enhanced feature count: {len(generator.experience_feature_names)}")
    print(f"First 10 features: {generator.experience_feature_names[:10]}")
    print()
    
    # Generate a small test dataset
    start_time = time.time()
    
    datasets = generator.generate_datasets_fast(
        cutoff_date="2010-12-31",
        min_results=100,  # Riders with at least 50 results
        target_variable='uci_points_actual',
        use_parallel=False  # Single-threaded for testing
    )
    
    elapsed = time.time() - start_time
    
    print(f"\nGeneration completed in {elapsed:.2f} seconds")
    print(f"GC dataset: {len(datasets['gc_dataset'])} rows")
    print(f"Stage/One-day dataset: {len(datasets['stage_one_day_dataset'])} rows")
    
    # Check the columns in the generated dataset
    if len(datasets['gc_dataset']) > 0:
        gc_df = datasets['gc_dataset']
        print(f"\nTotal columns in GC dataset: {len(gc_df.columns)}")
        
        # Count different types of features
        experience_features = [col for col in gc_df.columns if col in generator.experience_feature_names]
        race_features = [col for col in gc_df.columns if col.startswith('rf_')]
        race_kind_features = [col for col in gc_df.columns if col.startswith('rkf_')]
        
        print(f"Experience features: {len(experience_features)}")
        print(f"Race features: {len(race_features)}")
        print(f"Race kind features: {len(race_kind_features)}")
        
        # Show sample of experience features
        print(f"\nSample experience features:")
        for feat in experience_features[:5]:
            values = gc_df[feat].describe()
            print(f"  {feat}: mean={values['mean']:.2f}, std={values['std']:.2f}, min={values['min']}, max={values['max']}")
        
        # Check for the basic features we expect
        basic_features = [
            'total_prior_races', 'prior_wt_proportion', 
            'total_prior_uci_points_actual', 'rider_age_at_race'
        ]
        
        print(f"\nChecking for basic features:")
        for feat in basic_features:
            if feat in gc_df.columns:
                print(f"  ✓ {feat} found")
            else:
                print(f"  ✗ {feat} MISSING")
        
        # Check for some enhanced features
        enhanced_sample = [
            'prior_gc_success_rate', 'overall_success_rate',
            'points_variance', 'rider_vs_clumpiness_score_performance'
        ]
        
        print(f"\nChecking for enhanced features:")
        for feat in enhanced_sample:
            if feat in gc_df.columns:
                print(f"  ✓ {feat} found")
            else:
                print(f"  ✗ {feat} not found (may depend on available race features)")


if __name__ == "__main__":
    test_optimized_generator()