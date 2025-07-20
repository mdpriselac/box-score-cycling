"""
Test loading correlation data from blob table vs denormalized table.
"""

import time
import sqlite3
import pandas as pd
import numpy as np
import pickle


def test_blob_loading():
    """Test loading correlation matrices from blob table"""
    
    print("=== Blob Loading Performance Test ===")
    print()
    
    # Connect to database
    conn = sqlite3.connect("database/database/cycling_races.db")
    
    # Test 1: Count and basic info
    print("1. Checking blob table size...")
    start_time = time.time()
    
    count_query = """
    SELECT correlation_type, COUNT(*) as count,
           AVG(LENGTH(correlation_matrix)) as avg_blob_size
    FROM rider_correlations_blob 
    GROUP BY correlation_type
    """
    
    counts = pd.read_sql_query(count_query, conn)
    count_time = time.time() - start_time
    
    print(f"Count query: {count_time:.2f} seconds")
    print(counts)
    print()
    
    # Test 2: Load sample blob data
    print("2. Loading sample blob data...")
    start_time = time.time()
    
    sample_query = """
    SELECT rider_result_id, competition_id, correlation_type, 
           correlation_matrix, race_count
    FROM rider_correlations_blob 
    WHERE correlation_type = 'same_type'
    LIMIT 100
    """
    
    sample_df = pd.read_sql_query(sample_query, conn)
    sample_time = time.time() - start_time
    
    print(f"Loaded {len(sample_df)} blob rows in {sample_time:.2f} seconds")
    print(f"Blob size range: {sample_df['correlation_matrix'].apply(len).min()} to {sample_df['correlation_matrix'].apply(len).max()} bytes")
    print()
    
    # Test 3: Decompress and analyze blob structure
    print("3. Testing blob decompression...")
    
    if len(sample_df) > 0:
        start_time = time.time()
        
        # Test decompressing first blob
        first_blob = sample_df.iloc[0]['correlation_matrix']
        
        try:
            # Try to decompress (assuming it's compressed numpy array)
            import gzip
            decompressed = gzip.decompress(first_blob)
            matrix = np.frombuffer(decompressed, dtype=np.float64).reshape(8, 37)  # 8 percentiles x 37 features
            
            decomp_time = time.time() - start_time
            print(f"✓ Decompressed blob: {matrix.shape} array in {decomp_time:.4f} seconds")
            print(f"Matrix sample: {matrix[0][:5]}...")  # First 5 values of first percentile
            
            # Test decompressing all samples
            start_time = time.time()
            all_matrices = []
            
            for idx, row in sample_df.iterrows():
                blob = row['correlation_matrix']
                decompressed = gzip.decompress(blob)
                matrix = np.frombuffer(decompressed, dtype=np.float64).reshape(8, 37)
                all_matrices.append(matrix)
            
            batch_time = time.time() - start_time
            print(f"✓ Decompressed {len(all_matrices)} matrices in {batch_time:.3f} seconds")
            print(f"Rate: {len(all_matrices)/batch_time:.0f} matrices/second")
            
        except Exception as e:
            print(f"✗ Blob decompression failed: {e}")
            print(f"First 20 bytes: {first_blob[:20]}")
    
    # Test 4: Compare loading strategies
    print("\n4. Comparing loading strategies for abandon_ratio...")
    
    # Strategy A: Denormalized table (previous approach)
    print("Strategy A: Denormalized table")
    start_time = time.time()
    
    denorm_query = """
    SELECT rider_result_id, competition_id, percentile, correlation_value, race_count
    FROM rider_correlations_denorm 
    WHERE correlation_type = 'same_type' 
    AND feature_name = 'abandon_ratio'
    AND correlation_value IS NOT NULL
    LIMIT 10000
    """
    
    denorm_df = pd.read_sql_query(denorm_query, conn)
    denorm_time = time.time() - start_time
    
    print(f"  Denormalized: {len(denorm_df)} rows in {denorm_time:.2f} seconds")
    
    # Strategy B: Blob table  
    print("Strategy B: Blob table")
    start_time = time.time()
    
    blob_query = """
    SELECT rider_result_id, competition_id, correlation_matrix, race_count
    FROM rider_correlations_blob 
    WHERE correlation_type = 'same_type'
    LIMIT 10000
    """
    
    blob_df = pd.read_sql_query(blob_query, conn)
    blob_load_time = time.time() - start_time
    
    # Extract abandon_ratio from blobs
    start_time = time.time()
    abandon_data = []
    
    for idx, row in blob_df.iterrows():
        try:
            blob = row['correlation_matrix']
            decompressed = gzip.decompress(blob)
            matrix = np.frombuffer(decompressed, dtype=np.float64).reshape(8, 37)
            
            # abandon_ratio is feature index ? (need to check)
            # For now, let's just extract one feature column
            feature_idx = 0  # Placeholder
            
            for percentile_idx, percentile in enumerate([30, 40, 50, 60, 70, 80, 90, 100]):
                correlation = matrix[percentile_idx, feature_idx]
                abandon_data.append({
                    'rider_result_id': row['rider_result_id'],
                    'competition_id': row['competition_id'],
                    'percentile': percentile,
                    'correlation_value': correlation,
                    'race_count': row['race_count']
                })
                
        except Exception as e:
            continue
    
    blob_process_time = time.time() - start_time
    blob_total_time = blob_load_time + blob_process_time
    
    print(f"  Blob load: {len(blob_df)} rows in {blob_load_time:.2f} seconds")
    print(f"  Blob processing: {len(abandon_data)} extracted in {blob_process_time:.2f} seconds") 
    print(f"  Total blob time: {blob_total_time:.2f} seconds")
    
    print(f"\nComparison:")
    print(f"  Denormalized: {denorm_time:.2f}s for {len(denorm_df)} rows")
    print(f"  Blob approach: {blob_total_time:.2f}s for {len(abandon_data)} rows")
    
    if blob_total_time < denorm_time:
        speedup = denorm_time / blob_total_time
        print(f"  ✓ Blob approach is {speedup:.1f}x faster!")
    else:
        slowdown = blob_total_time / denorm_time
        print(f"  ✗ Blob approach is {slowdown:.1f}x slower")
    
    conn.close()


if __name__ == "__main__":
    test_blob_loading()