"""
Test chunk loading performance for correlation data.
"""

import time
import sqlite3
import pandas as pd
from typing import List, Tuple


def test_chunk_loading():
    """Test loading abandon_ratio/same_type data in chunks with performance tracking"""
    
    print("=== Chunk Loading Performance Test ===")
    print("Feature: abandon_ratio, Correlation Type: same_type, Percentile: 70")
    print()
    
    # Connect to database
    conn = sqlite3.connect("database/database/cycling_races.db")
    
    # Base query (no ORDER BY for speed)
    base_query = """
    SELECT rider_result_id, competition_id, correlation_value, race_count
    FROM rider_correlations_denorm 
    WHERE correlation_type = 'same_type' 
    AND feature_name = 'abandon_ratio'
    AND percentile = 70
    AND correlation_value IS NOT NULL
    LIMIT ? OFFSET ?
    """
    
    # Test parameters
    chunk_sizes = [5000, 10000]
    chunk_stats = {5000: {'count': 0, 'total_time': 0, 'total_rows': 0}, 
                   10000: {'count': 0, 'total_time': 0, 'total_rows': 0}}
    
    offset = 0
    chunk_size_index = 0
    total_rows_loaded = 0
    all_data = []
    
    print("Starting chunk loading...")
    print("Format: [Chunk #] Size: XXXX | Rows: XXXX | Time: X.XXs | Rate: XXXX rows/s | Avg Rate: XXXX rows/s")
    print("-" * 100)
    
    while True:
        # Alternate between chunk sizes
        current_chunk_size = chunk_sizes[chunk_size_index % len(chunk_sizes)]
        chunk_size_index += 1
        
        # Load chunk
        start_time = time.time()
        
        try:
            chunk_df = pd.read_sql_query(
                base_query, 
                conn, 
                params=[current_chunk_size, offset]
            )
        except Exception as e:
            print(f"Error loading chunk: {e}")
            break
        
        load_time = time.time() - start_time
        rows_in_chunk = len(chunk_df)
        
        # Check if we're done (no more data)
        if rows_in_chunk == 0:
            print("No more data - loading complete!")
            break
        
        # Update statistics
        total_rows_loaded += rows_in_chunk
        all_data.append(chunk_df)
        
        # Update stats for this chunk size
        stats = chunk_stats[current_chunk_size]
        stats['count'] += 1
        stats['total_time'] += load_time
        stats['total_rows'] += rows_in_chunk
        
        # Calculate rates
        current_rate = rows_in_chunk / load_time if load_time > 0 else 0
        avg_rate = stats['total_rows'] / stats['total_time'] if stats['total_time'] > 0 else 0
        
        # Print progress
        chunk_num = sum(s['count'] for s in chunk_stats.values())
        print(f"[{chunk_num:2d}] Size: {current_chunk_size:5d} | Rows: {rows_in_chunk:4d} | "
              f"Time: {load_time:5.2f}s | Rate: {current_rate:6.0f} rows/s | "
              f"Avg Rate: {avg_rate:6.0f} rows/s")
        
        # Update offset for next chunk
        offset += rows_in_chunk
        
        # Safety check - don't load forever
        if total_rows_loaded > 100000:  # Stop after 100k rows for testing
            print(f"Stopping after {total_rows_loaded:,} rows for safety")
            break
    
    # Final summary
    print("\n" + "=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)
    
    combined_df = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    print(f"Total rows loaded: {len(combined_df):,}")
    print(f"Unique competitions: {combined_df['competition_id'].nunique()}")
    print(f"Correlation range: {combined_df['correlation_value'].min():.4f} to {combined_df['correlation_value'].max():.4f}")
    
    print("\nPerformance by chunk size:")
    for size, stats in chunk_stats.items():
        if stats['count'] > 0:
            avg_time = stats['total_time'] / stats['count']
            avg_rate = stats['total_rows'] / stats['total_time']
            avg_rows = stats['total_rows'] / stats['count']
            
            print(f"  {size:5d} rows: {stats['count']:2d} chunks, "
                  f"avg {avg_time:.2f}s/chunk, {avg_rate:.0f} rows/s, "
                  f"{avg_rows:.0f} rows/chunk")
    
    # Overall performance
    total_time = sum(s['total_time'] for s in chunk_stats.values())
    overall_rate = total_rows_loaded / total_time if total_time > 0 else 0
    
    print(f"\nOverall: {total_rows_loaded:,} rows in {total_time:.2f}s = {overall_rate:.0f} rows/s")
    
    conn.close()
    
    return combined_df


if __name__ == "__main__":
    df = test_chunk_loading()
    print(f"\nTest complete! Loaded {len(df):,} rows total.")