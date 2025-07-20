"""
Simple performance test - just same_type correlation with 2 chunk sizes.
Live progress updates included.
Plus test loading entire feature at once without chunking.
"""

import time
import pandas as pd
import sys
from feature_optimization.correlation_feature_analysis.data_loader import CorrelationDataLoader


def test_same_type_chunk_sizes():
    """Test same_type correlation with two chunk sizes"""
    
    print("=== Simple Performance Test ===")
    print("Correlation type: same_type (GC races)")
    print("Feature: abandon_ratio")
    print("Live progress updates enabled\n")
    
    chunk_sizes = [500_000, 2_000_000]
    
    with CorrelationDataLoader("database/database/cycling_races.db") as loader:
        
        # First, quick check of data size
        print("Checking data size...")
        start_time = time.time()
        
        chunk_gen = loader.load_correlation_data('same_type', chunk_size=10_000)
        first_small_chunk = next(chunk_gen)
        
        total_features = first_small_chunk['feature_name'].nunique()
        abandon_rows = len(first_small_chunk[first_small_chunk['feature_name'] == 'abandon_ratio'])
        
        elapsed = time.time() - start_time
        print(f"✓ First 10K rows: {total_features} features, {abandon_rows} abandon_ratio rows in {elapsed:.3f}s")
        
        # Test the two chunk sizes
        for chunk_size in chunk_sizes:
            print(f"\n--- Testing chunk size: {chunk_size:,} ---")
            
            start_time = time.time()
            total_rows = 0
            chunk_count = 0
            last_update_time = start_time
            
            try:
                for chunk in loader.load_correlation_data('same_type', chunk_size=chunk_size):
                    # Filter to abandon_ratio
                    feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
                    total_rows += len(feature_chunk)
                    chunk_count += 1
                    
                    # Live progress update every second
                    current_time = time.time()
                    if current_time - last_update_time > 1.0:
                        elapsed = current_time - start_time
                        rate = total_rows / elapsed if elapsed > 0 else 0
                        print(f"  Progress: {chunk_count} chunks, {total_rows:,} rows, {elapsed:.1f}s, {rate:,.0f} rows/sec", end='\r')
                        sys.stdout.flush()
                        last_update_time = current_time
                    
                    # Stop after getting enough data to measure speed
                    if total_rows > 100_000:  
                        print(f"\n  (Stopping after {total_rows:,} rows for speed measurement)")
                        break
                
                elapsed = time.time() - start_time
                print(f"✓ Processed {total_rows:,} rows in {chunk_count} chunks")
                print(f"  Total time: {elapsed:.2f} seconds")
                print(f"  Average rate: {total_rows/elapsed:,.0f} rows/second")
                
            except Exception as e:
                print(f"\n✗ Error with chunk size {chunk_size}: {e}")

        # Test complete loading of one feature with progress
        print(f"\n--- Complete abandon_ratio loading (all same_type data) ---")
        start_time = time.time()
        last_update_time = start_time
        
        chunks = []
        chunk_count = 0
        total_rows_seen = 0
        
        print("Loading data with progress updates...")
        
        for chunk in loader.load_correlation_data('same_type', chunk_size=1_000_000):
            feature_chunk = chunk[chunk['feature_name'] == 'abandon_ratio']
            chunk_count += 1
            
            if len(feature_chunk) > 0:
                chunks.append(feature_chunk)
                total_rows_seen += len(feature_chunk)
            
            # Live progress update
            current_time = time.time()
            if current_time - last_update_time > 0.5:  # Update every 0.5 seconds
                elapsed = current_time - start_time
                print(f"  Chunks: {chunk_count}, Rows found: {total_rows_seen:,}, Time: {elapsed:.1f}s", end='\r')
                sys.stdout.flush()
                last_update_time = current_time
        
        # Final processing
        print(f"\nCombining {len(chunks)} chunks...")
        df = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        elapsed = time.time() - start_time
        
        print(f"✓ Complete loading finished!")
        print(f"  Total rows: {len(df):,}")
        print(f"  Total time: {elapsed:.2f} seconds")
        print(f"  Loading rate: {len(df)/elapsed:,.0f} rows/second")
        
        if len(df) > 0:
            print(f"\nData summary:")
            print(f"  Percentiles found: {sorted(df['percentile'].unique())}")
            print(f"  Non-null correlations: {df['correlation_value'].notna().sum():,} ({df['correlation_value'].notna().sum()/len(df)*100:.1f}%)")
            print(f"  Unique race counts: {df['race_count'].nunique()}")
        
        # NEW: Test loading all at once without chunking
        print(f"\n--- Testing single query (no chunking) ---")
        print("Loading abandon_ratio for same_type in one query...")
        
        start_time = time.time()
        try:
            # Direct SQL query without chunking
            query = """
            SELECT feature_name, percentile, correlation_value, race_count, total_count, null_count
            FROM rider_correlations_denorm
            WHERE correlation_type = 'same_type' 
              AND feature_name = 'abandon_ratio'
              AND correlation_value IS NOT NULL
            ORDER BY percentile
            """
            
            print("  Executing query...")
            single_df = pd.read_sql_query(query, loader.conn)
            elapsed = time.time() - start_time
            
            print(f"✓ Single query complete!")
            print(f"  Total rows: {len(single_df):,}")
            print(f"  Total time: {elapsed:.2f} seconds")
            print(f"  Loading rate: {len(single_df)/elapsed:,.0f} rows/second")
            
            if len(single_df) > 0:
                print(f"  Percentiles: {sorted(single_df['percentile'].unique())}")
                print(f"  Memory usage: {single_df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"✗ Single query failed after {elapsed:.1f}s: {e}")


if __name__ == "__main__":
    test_same_type_chunk_sizes()
    print("\n=== Simple Test Complete ===")