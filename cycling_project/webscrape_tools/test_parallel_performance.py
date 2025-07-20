"""
Test parallel database access for correlation analysis.
"""

import time
import pandas as pd
import sqlite3
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count


def load_single_feature(args):
    """Load data for a single feature (for parallel execution)"""
    feature_name, correlation_type, db_path = args
    
    start_time = time.time()
    
    # Each thread/process gets its own connection
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT feature_name, percentile, correlation_value, race_count, total_count, null_count
    FROM rider_correlations_denorm
    WHERE correlation_type = ? 
      AND feature_name = ?
      AND correlation_value IS NOT NULL
    ORDER BY percentile
    """
    
    df = pd.read_sql_query(query, conn, params=[correlation_type, feature_name])
    conn.close()
    
    elapsed = time.time() - start_time
    
    return {
        'feature': feature_name,
        'rows': len(df),
        'time': elapsed,
        'data': df
    }


def test_parallel_loading():
    """Test parallel loading of multiple features"""
    
    print("=== Parallel Loading Test ===")
    print(f"CPU cores available: {cpu_count()}")
    
    db_path = "database/database/cycling_races.db"
    correlation_type = 'same_type'
    
    # Get list of features to test
    conn = sqlite3.connect(db_path)
    features_query = """
    SELECT DISTINCT feature_name 
    FROM rider_correlations_denorm 
    WHERE correlation_type = 'same_type'
    LIMIT 10
    """
    features = pd.read_sql_query(features_query, conn)['feature_name'].tolist()
    conn.close()
    
    print(f"Testing with {len(features)} features: {features[:5]}...")
    
    # Test 1: Sequential loading (baseline)
    print("\n--- Sequential Loading (Baseline) ---")
    start_time = time.time()
    sequential_results = []
    
    for i, feature in enumerate(features):
        result = load_single_feature((feature, correlation_type, db_path))
        sequential_results.append(result)
        print(f"  {i+1}/{len(features)}: {feature} - {result['rows']:,} rows in {result['time']:.2f}s")
    
    sequential_total = time.time() - start_time
    print(f"Sequential total: {sequential_total:.2f} seconds")
    
    # Test 2: Thread-based parallel loading
    print("\n--- Thread-Based Parallel Loading ---")
    print("(Multiple threads, shared Python process)")
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        start_time = time.time()
        
        # Submit all tasks
        future_to_feature = {
            executor.submit(load_single_feature, (feature, correlation_type, db_path)): feature 
            for feature in features
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_feature):
            feature = future_to_feature[future]
            result = future.result()
            completed += 1
            elapsed = time.time() - start_time
            print(f"  {completed}/{len(features)}: {feature} - {result['rows']:,} rows (Total elapsed: {elapsed:.1f}s)")
    
    thread_total = time.time() - start_time
    print(f"Thread parallel total: {thread_total:.2f} seconds")
    print(f"Speedup: {sequential_total/thread_total:.2f}x")
    
    # Test 3: Process-based parallel loading
    print("\n--- Process-Based Parallel Loading ---") 
    print("(Multiple processes, true parallelism)")
    
    with ProcessPoolExecutor(max_workers=4) as executor:
        start_time = time.time()
        
        # Submit all tasks
        future_to_feature = {
            executor.submit(load_single_feature, (feature, correlation_type, db_path)): feature 
            for feature in features
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_feature):
            feature = future_to_feature[future]
            result = future.result()
            completed += 1
            elapsed = time.time() - start_time
            print(f"  {completed}/{len(features)}: {feature} - {result['rows']:,} rows (Total elapsed: {elapsed:.1f}s)")
    
    process_total = time.time() - start_time
    print(f"Process parallel total: {process_total:.2f} seconds")
    print(f"Speedup: {sequential_total/process_total:.2f}x")
    
    # Summary
    print("\n=== Summary ===")
    print(f"Sequential: {sequential_total:.2f}s (1.0x baseline)")
    print(f"Thread parallel: {thread_total:.2f}s ({sequential_total/thread_total:.2f}x speedup)")
    print(f"Process parallel: {process_total:.2f}s ({sequential_total/process_total:.2f}x speedup)")
    
    # Test optimal worker count
    print("\n--- Testing Optimal Worker Count ---")
    worker_counts = [1, 2, 4, 6, 8]
    
    for workers in worker_counts:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            start_time = time.time()
            
            futures = [
                executor.submit(load_single_feature, (feature, correlation_type, db_path))
                for feature in features[:6]  # Just test 6 features
            ]
            
            # Wait for all to complete
            for future in futures:
                future.result()
            
            elapsed = time.time() - start_time
            print(f"  {workers} workers: {elapsed:.2f}s")


if __name__ == "__main__":
    test_parallel_loading()
    print("\n=== Parallel Test Complete ===")