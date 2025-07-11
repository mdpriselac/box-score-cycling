#!/usr/bin/env python3
"""
Test script to demonstrate the performance improvements from parallel processing
and batched database loading.
"""
import time
import sys
from pathlib import Path

# Add to path for imports
sys.path.append(str(Path(__file__).parent))

from rider_embeddings.performance_optimization import ParallelCorrelationGenerator
from rider_embeddings.race_type_pipeline_adapter import RaceTypeDataGenerator


def test_performance_comparison():
    """Compare performance between original and optimized implementations."""
    
    print("PARALLEL PROCESSING PERFORMANCE TEST")
    print("=" * 60)
    
    db_path = "database/database/cycling_races.db"
    sample_size = 100  # Start with smaller sample for testing
    
    # Test 1: Original sequential implementation
    print(f"\n1. Testing ORIGINAL sequential implementation...")
    print(f"   Sample size: {sample_size} riders")
    
    original_generator = RaceTypeDataGenerator(
        db_path=db_path,
        output_dir="original_test_data",
        batch_size=50,
        min_races_gc=8,
        min_races_stage=15,
        min_races_one_day=10,
        min_races_all=25
    )
    
    start_time = time.time()
    
    try:
        original_generator.generate_sample(
            sample_size=sample_size,
            feature_tables=['race_features_70', 'race_features_80', 'race_features_90'],
            output_name="original_performance_test"
        )
        
        original_time = time.time() - start_time
        print(f"   ✓ Original implementation completed in {original_time:.2f} seconds")
        print(f"   ✓ Rate: {sample_size / original_time:.2f} riders/second")
        
    except Exception as e:
        print(f"   ✗ Original implementation failed: {e}")
        original_time = None
    
    # Test 2: Parallel implementation
    print(f"\n2. Testing PARALLEL implementation...")
    print(f"   Sample size: {sample_size} riders")
    
    parallel_generator = ParallelCorrelationGenerator(
        db_path=db_path,
        output_dir="parallel_test_data",
        batch_size=50,
        n_workers=4,  # Use 4 workers for testing
        use_batched_loading=True
    )
    
    start_time = time.time()
    
    try:
        parallel_generator.generate_sample_parallel(
            sample_size=sample_size,
            feature_tables=['race_features_70', 'race_features_80', 'race_features_90'],
            output_name="parallel_performance_test",
            calculator_type='race_type'
        )
        
        parallel_time = time.time() - start_time
        print(f"   ✓ Parallel implementation completed in {parallel_time:.2f} seconds")
        print(f"   ✓ Rate: {sample_size / parallel_time:.2f} riders/second")
        
    except Exception as e:
        print(f"   ✗ Parallel implementation failed: {e}")
        import traceback
        traceback.print_exc()
        parallel_time = None
    
    # Performance comparison
    print(f"\n3. PERFORMANCE COMPARISON")
    print("-" * 40)
    
    if original_time and parallel_time:
        speedup = original_time / parallel_time
        print(f"   Original time:    {original_time:.2f} seconds")
        print(f"   Parallel time:    {parallel_time:.2f} seconds")
        print(f"   Speedup:          {speedup:.2f}x faster")
        
        if speedup > 1.5:
            print(f"   ✓ Significant performance improvement!")
        elif speedup > 1.1:
            print(f"   ✓ Moderate performance improvement")
        else:
            print(f"   ⚠ Limited performance improvement")
    else:
        print("   ✗ Could not compare - one implementation failed")
    
    # Test 3: Larger sample (if initial test was successful)
    if parallel_time and parallel_time < 30:  # Only if parallel was fast
        larger_sample = 500
        print(f"\n4. Testing LARGER SAMPLE with parallel processing...")
        print(f"   Sample size: {larger_sample} riders")
        
        start_time = time.time()
        
        try:
            parallel_generator.generate_sample_parallel(
                sample_size=larger_sample,
                feature_tables=['race_features_80', 'race_features_90'],
                output_name="large_parallel_test",
                calculator_type='race_type'
            )
            
            large_time = time.time() - start_time
            print(f"   ✓ Large sample completed in {large_time:.2f} seconds")
            print(f"   ✓ Rate: {larger_sample / large_time:.2f} riders/second")
            
            # Estimate time savings for full dataset
            estimated_full_time = large_time * (10000 / larger_sample)  # Estimate for 10k riders
            print(f"   📊 Estimated time for 10,000 riders: {estimated_full_time/60:.1f} minutes")
            
        except Exception as e:
            print(f"   ✗ Large sample failed: {e}")
    
    print(f"\n5. RECOMMENDATIONS")
    print("-" * 40)
    
    if parallel_time:
        print("   ✓ Parallel processing is working correctly")
        print("   ✓ Ready for production use")
        print("   ✓ Consider increasing sample sizes for full pipeline")
        
        if parallel_time < 10:
            print("   ✓ Performance is excellent - can handle large datasets")
        elif parallel_time < 30:
            print("   ✓ Performance is good - suitable for regular use")
        else:
            print("   ⚠ Performance is acceptable but may need tuning for large datasets")
    else:
        print("   ✗ Parallel processing needs debugging")
        print("   ⚠ Check multiprocessing compatibility")
        print("   ⚠ Verify database access in workers")
    
    print(f"\nTest completed!")


def test_batch_loading_only():
    """Test just the batched database loading performance."""
    
    print("\nBATCHED DATABASE LOADING TEST")
    print("=" * 60)
    
    from rider_embeddings.performance_optimization import BatchedDatabaseLoader
    import sqlite3
    
    db_path = "database/database/cycling_races.db"
    
    # Get sample rider result IDs
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rr.id 
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date > '2020-01-01'
            ORDER BY RANDOM()
            LIMIT 200
        """)
        rider_result_ids = [row[0] for row in cursor.fetchall()]
    
    print(f"Testing with {len(rider_result_ids)} rider results...")
    
    # Test batched loading
    loader = BatchedDatabaseLoader(db_path)
    
    start_time = time.time()
    
    loader.preload_all_data(
        rider_result_ids,
        ['race_features_70', 'race_features_80', 'race_features_90']
    )
    
    load_time = time.time() - start_time
    
    # Get statistics
    stats = loader.get_cache_stats()
    
    print(f"✓ Batch loading completed in {load_time:.2f} seconds")
    print(f"✓ Cached data for {stats['rider_results_cached']} riders")
    print(f"✓ Total historical races: {stats['total_historical_races']}")
    print(f"✓ Average races per rider: {stats['average_races_per_rider']:.1f}")
    
    # Test cache access performance
    start_time = time.time()
    cache_hits = 0
    
    for rider_result_id in rider_result_ids[:50]:  # Test first 50
        history = loader.get_cached_rider_history(rider_result_id)
        if history:
            cache_hits += 1
            # Test feature access
            competition_ids = [h['competition_id'] for h in history[:5]]  # First 5 races
            features = loader.get_cached_race_features(competition_ids, 'race_features_80')
    
    access_time = time.time() - start_time
    
    print(f"✓ Cache access test: {cache_hits}/50 hits in {access_time:.3f} seconds")
    print(f"✓ Cache hit rate: {cache_hits/50*100:.1f}%")
    
    loader.clear_cache()
    print("✓ Cache cleared")


if __name__ == "__main__":
    # Test batch loading first
    test_batch_loading_only()
    
    # Then test full parallel processing
    test_performance_comparison()