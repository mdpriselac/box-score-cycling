"""
Test loading all abandon_ratio data at once (no pagination).
"""

import time
import sqlite3
import pandas as pd


def test_single_load():
    """Load all abandon_ratio/same_type/percentile=70 data at once"""
    
    print("=== Single Load Performance Test ===")
    print("Feature: abandon_ratio, Correlation Type: same_type, Percentile: 70")
    print()
    
    # Connect to database
    conn = sqlite3.connect("database/database/cycling_races.db")
    
    # Single query - no LIMIT, no OFFSET, no ORDER BY
    query = """
    SELECT rider_result_id, competition_id, correlation_value, race_count
    FROM rider_correlations_denorm 
    WHERE correlation_type = 'same_type' 
    AND feature_name = 'abandon_ratio'
    AND percentile = 70
    AND correlation_value IS NOT NULL
    """
    
    print("Loading all data in single query...")
    start_time = time.time()
    
    try:
        df = pd.read_sql_query(query, conn)
        load_time = time.time() - start_time
        
        print(f"✓ Loaded {len(df):,} rows in {load_time:.2f} seconds")
        print(f"  Rate: {len(df)/load_time:,.0f} rows/second")
        print(f"  Memory usage: ~{df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
        
        # Data analysis
        print(f"\nData Summary:")
        print(f"  Unique competitions: {df['competition_id'].nunique():,}")
        print(f"  Correlation range: {df['correlation_value'].min():.4f} to {df['correlation_value'].max():.4f}")
        print(f"  Race count range: {df['race_count'].min()} to {df['race_count'].max()}")
        print(f"  rider_result_id range: {df['rider_result_id'].min():,} to {df['rider_result_id'].max():,}")
        
        # Test filtering for specific competition
        print(f"\nTesting in-memory filtering...")
        filter_start = time.time()
        comp_53_data = df[df['competition_id'] == 53]
        filter_time = time.time() - filter_start
        
        print(f"  Competition 53: {len(comp_53_data)} rows in {filter_time:.4f} seconds")
        print(f"  Filter rate: {len(df)/filter_time:,.0f} rows/second")
        
        # Test aggregation
        print(f"\nTesting in-memory aggregation...")
        agg_start = time.time()
        competition_stats = df.groupby('competition_id')['correlation_value'].agg(['count', 'mean', 'std']).head(10)
        agg_time = time.time() - agg_start
        
        print(f"  Aggregation by competition: {agg_time:.4f} seconds")
        print(f"  Sample results:")
        print(competition_stats)
        
    except Exception as e:
        print(f"✗ Error: {e}")
        df = pd.DataFrame()
    
    finally:
        conn.close()
    
    return df


if __name__ == "__main__":
    df = test_single_load()
    
    if len(df) > 0:
        print(f"\n=== Success! ===")
        print(f"Single query approach loaded {len(df):,} rows efficiently.")
        print(f"This eliminates pagination complexity and should work well for correlation analysis.")
    else:
        print(f"\n=== Failed ===")
        print(f"Single query approach didn't work. May need to fall back to chunking strategy.")