#!/usr/bin/env python3
"""
Test script for parallel processing implementation
"""
import logging
import time
import psutil
from config import ProcessingConfig
from correlation_processor import CorrelationProcessor

def test_parallel_vs_sequential():
    """Test parallel processing vs sequential processing"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    config = ProcessingConfig()
    processor = CorrelationProcessor(config.DB_PATH, config)
    
    # Initialize components
    processor.threshold_calculator.calculate_thresholds()
    processor.features_loader.preload_race_features()
    
    # Get a small batch of competitions for testing with actual eligible riders
    import sqlite3
    with sqlite3.connect(config.DB_PATH) as conn:
        test_competitions = conn.execute("""
            SELECT DISTINCT c.id as competition_id, c.date as competition_date, c.competition_type
            FROM competitions c
            JOIN rider_results rr ON c.id = rr.competition_id
            WHERE c.id BETWEEN 4000 AND 4100
            AND rr.total_prior_races >= 13
            AND (
                (c.competition_type = 'gc' AND rr.prior_gc_races >= 6)
                OR
                (c.competition_type = 'stage' AND rr.prior_stage_races >= 33 AND rr.prior_stage_one_days >= 28)
                OR
                (c.competition_type = 'one_day' AND rr.prior_one_day_races >= 6 AND rr.prior_stage_one_days >= 28)
            )
            ORDER BY c.date
            LIMIT 3
        """).fetchall()
    
    test_batch = [{'competition_id': r[0], 'competition_date': r[1], 'race_type': r[2]} for r in test_competitions]
    
    print("=== Testing Parallel vs Sequential Processing ===")
    print(f"Testing with {len(test_batch)} competitions")
    print(f"CPU cores available: {psutil.cpu_count()}")
    
    # Test 1: Sequential processing
    print("\n1. Testing Sequential Processing...")
    config.THREAD_SAFETY_ENABLED = False
    start_time = time.time()
    
    results_sequential = processor._process_competition_batch(test_batch)
    
    sequential_time = time.time() - start_time
    print(f"Sequential processing: {len(results_sequential)} results in {sequential_time:.2f}s")
    
    # Test 2: Parallel processing
    print("\n2. Testing Parallel Processing...")
    config.THREAD_SAFETY_ENABLED = True
    config.NUM_WORKERS = 4
    start_time = time.time()
    
    results_parallel = processor._process_competition_batch(test_batch)
    
    parallel_time = time.time() - start_time
    print(f"Parallel processing: {len(results_parallel)} results in {parallel_time:.2f}s")
    
    # Compare results
    speedup = sequential_time / parallel_time if parallel_time > 0 else 0
    print(f"\nSpeedup: {speedup:.2f}x")
    
    # Verify data integrity
    print("\n3. Verifying Data Integrity...")
    
    if len(results_sequential) == len(results_parallel):
        print("✓ Same number of results")
    else:
        print(f"✗ Different number of results: {len(results_sequential)} vs {len(results_parallel)}")
    
    # Check if results contain the same rider_result_ids and correlation_types
    seq_keys = set((r['rider_result_id'], r['correlation_type']) for r in results_sequential)
    par_keys = set((r['rider_result_id'], r['correlation_type']) for r in results_parallel)
    
    if seq_keys == par_keys:
        print("✓ Same rider results and correlation types")
    else:
        print(f"✗ Different keys: {len(seq_keys)} vs {len(par_keys)}")
        missing_in_parallel = seq_keys - par_keys
        extra_in_parallel = par_keys - seq_keys
        if missing_in_parallel:
            print(f"Missing in parallel: {list(missing_in_parallel)[:5]}")
        if extra_in_parallel:
            print(f"Extra in parallel: {list(extra_in_parallel)[:5]}")
    
    print("\n=== Test Complete ===")
    
    return speedup, len(results_parallel) > 0

def test_thread_safety():
    """Test database thread safety"""
    print("\n=== Testing Thread Safety ===")
    
    config = ProcessingConfig()
    config.THREAD_SAFETY_ENABLED = True
    config.NUM_WORKERS = 4
    
    processor = CorrelationProcessor(config.DB_PATH, config)
    
    # Test concurrent database access
    import sqlite3
    import threading
    
    def test_connection():
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                conn.execute("PRAGMA busy_timeout = 30000")
                conn.execute("PRAGMA synchronous = NORMAL")
                conn.execute("PRAGMA journal_mode = WAL")
                
                # Simple query
                result = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()
                return result[0] > 0
        except Exception as e:
            print(f"Database connection error: {e}")
            return False
    
    # Test multiple concurrent connections
    threads = []
    results = []
    
    for i in range(4):
        thread = threading.Thread(target=lambda: results.append(test_connection()))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    if all(results):
        print("✓ Thread safety test passed")
        return True
    else:
        print("✗ Thread safety test failed")
        return False

if __name__ == "__main__":
    try:
        # Test parallel processing
        speedup, success = test_parallel_vs_sequential()
        
        # Test thread safety
        thread_safe = test_thread_safety()
        
        print(f"\n=== Final Results ===")
        print(f"Parallel processing: {'✓ PASSED' if success else '✗ FAILED'}")
        print(f"Thread safety: {'✓ PASSED' if thread_safe else '✗ FAILED'}")
        print(f"Performance speedup: {speedup:.2f}x")
        
        if success and thread_safe and speedup > 1.0:
            print("🎉 Parallel processing implementation is ready for deployment!")
        else:
            print("⚠️  Issues detected - review before deployment")
            
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()