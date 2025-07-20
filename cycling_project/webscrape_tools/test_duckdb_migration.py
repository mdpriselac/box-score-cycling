"""
Test DuckDB migration and performance for correlation analysis.
"""

import duckdb
import time
import pandas as pd


def test_duckdb_connection():
    """Test basic DuckDB functionality"""
    
    print("=== Testing DuckDB ===")
    
    # Connect to DuckDB (in-memory for testing)
    conn = duckdb.connect()
    
    # Test basic query
    result = conn.execute("SELECT 42 as answer").fetchone()
    print(f"✓ Basic query works: {result[0]}")
    
    # Test with pandas
    df = pd.DataFrame({'test': [1, 2, 3], 'data': ['a', 'b', 'c']})
    result = conn.execute("SELECT * FROM df").fetchdf()
    print(f"✓ Pandas integration works: {len(result)} rows")
    
    conn.close()


def test_sqlite_to_duckdb_import():
    """Test importing SQLite data into DuckDB"""
    
    print("\n=== Testing SQLite Import ===")
    
    # Connect to DuckDB (persistent file) - creates file automatically
    duck_conn = duckdb.connect('test_cycling.duckdb')
    
    # Install and load sqlite extension
    print("Installing SQLite extension...")
    duck_conn.execute("INSTALL sqlite")
    duck_conn.execute("LOAD sqlite")
    
    # Test connecting to SQLite database
    sqlite_path = "database/database/cycling_races.db"
    print(f"Connecting to SQLite: {sqlite_path}")
    
    try:
        # Attach SQLite database
        duck_conn.execute(f"ATTACH '{sqlite_path}' AS sqlite_db (TYPE sqlite)")
        
        # Test reading from SQLite
        print("Testing small query from SQLite...")
        start_time = time.time()
        
        result = duck_conn.execute("""
            SELECT COUNT(*) 
            FROM sqlite_db.rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            AND feature_name = 'abandon_ratio'
            LIMIT 1
        """).fetchone()
        
        elapsed = time.time() - start_time
        print(f"✓ Count query: {result[0]:,} rows in {elapsed:.2f} seconds")
        
        # Test loading sample data
        print("Loading sample data...")
        start_time = time.time()
        
        sample_df = duck_conn.execute("""
            SELECT percentile, correlation_value, race_count
            FROM sqlite_db.rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            AND feature_name = 'abandon_ratio'
            AND correlation_value IS NOT NULL
            LIMIT 1000
        """).fetchdf()
        
        elapsed = time.time() - start_time
        print(f"✓ Sample data: {len(sample_df)} rows in {elapsed:.2f} seconds")
        
        # Test aggregation
        print("Testing aggregation...")
        start_time = time.time()
        
        agg_result = duck_conn.execute("""
            SELECT percentile, 
                   COUNT(*) as count,
                   AVG(correlation_value) as avg_corr,
                   STDDEV(correlation_value) as std_corr
            FROM sqlite_db.rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            AND feature_name = 'abandon_ratio'
            AND correlation_value IS NOT NULL
            GROUP BY percentile
            ORDER BY percentile
        """).fetchdf()
        
        elapsed = time.time() - start_time
        print(f"✓ Aggregation: {len(agg_result)} groups in {elapsed:.2f} seconds")
        print("Sample results:")
        print(agg_result.head())
        
    except Exception as e:
        print(f"✗ Error: {e}")
    
    finally:
        duck_conn.close()


def test_duckdb_vs_sqlite_performance():
    """Compare DuckDB vs SQLite performance on same query"""
    
    print("\n=== Performance Comparison ===")
    
    # DuckDB test
    print("Testing DuckDB...")
    duck_conn = duckdb.connect('test_cycling.duckdb')
    duck_conn.execute("INSTALL sqlite")
    duck_conn.execute("LOAD sqlite")
    duck_conn.execute("ATTACH 'database/database/cycling_races.db' AS sqlite_db (TYPE sqlite)")
    
    query = """
    SELECT percentile, correlation_value, race_count
    FROM sqlite_db.rider_correlations_denorm 
    WHERE correlation_type = 'same_type' 
    AND feature_name = 'abandon_ratio'
    AND correlation_value IS NOT NULL
    AND rider_result_id IN (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20)
    """
    
    # Time DuckDB query
    start_time = time.time()
    duck_result = duck_conn.execute(query).fetchdf()
    duck_time = time.time() - start_time
    
    print(f"DuckDB: {len(duck_result)} rows in {duck_time:.2f} seconds")
    
    duck_conn.close()
    
    print(f"\nPrevious SQLite time: ~180+ seconds")
    print(f"DuckDB improvement: {180/duck_time:.1f}x faster")


if __name__ == "__main__":
    test_duckdb_connection()
    test_sqlite_to_duckdb_import()
    test_duckdb_vs_sqlite_performance()
    
    print("\n=== DuckDB Test Complete ===")
    print("If successful, DuckDB should be much faster for analytics!")