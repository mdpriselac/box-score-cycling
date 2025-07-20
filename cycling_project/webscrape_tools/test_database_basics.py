"""
Basic database connectivity and performance test.
"""

import time
import sqlite3
import pandas as pd


def test_basic_queries():
    """Test basic database operations to isolate the issue"""
    
    print("=== Basic Database Test ===")
    
    db_path = "database/database/cycling_races.db"
    
    # Test 1: Basic connection
    print("\n1. Testing basic connection...")
    start = time.time()
    try:
        conn = sqlite3.connect(db_path)
        print(f"✓ Connected in {time.time() - start:.3f}s")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return
    
    # Test 2: Simple count
    print("\n2. Testing simple count...")
    start = time.time()
    try:
        result = conn.execute("SELECT COUNT(*) FROM rider_correlations_denorm").fetchone()
        elapsed = time.time() - start
        print(f"✓ Total rows: {result[0]:,} (query took {elapsed:.3f}s)")
    except Exception as e:
        print(f"✗ Count failed: {e}")
    
    # Test 3: Count with WHERE clause
    print("\n3. Testing filtered count...")
    start = time.time()
    try:
        result = conn.execute("""
            SELECT COUNT(*) 
            FROM rider_correlations_denorm 
            WHERE correlation_type = 'same_type'
        """).fetchone()
        elapsed = time.time() - start
        print(f"✓ Rows with same_type: {result[0]:,} (query took {elapsed:.3f}s)")
    except Exception as e:
        print(f"✗ Filtered count failed: {e}")
    
    # Test 4: Get first row
    print("\n4. Testing single row fetch...")
    start = time.time()
    try:
        result = conn.execute("""
            SELECT * FROM rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            LIMIT 1
        """).fetchone()
        elapsed = time.time() - start
        print(f"✓ Got 1 row in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Single row fetch failed: {e}")
    
    # Test 5: Get 100 rows
    print("\n5. Testing 100 row fetch...")
    start = time.time()
    try:
        cursor = conn.execute("""
            SELECT * FROM rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            LIMIT 100
        """)
        rows = cursor.fetchall()
        elapsed = time.time() - start
        print(f"✓ Got {len(rows)} rows in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ 100 row fetch failed: {e}")
    
    # Test 6: Check for database locks
    print("\n6. Checking for database locks...")
    try:
        result = conn.execute("PRAGMA lock_status").fetchall()
        print(f"Lock status: {result}")
    except:
        print("(lock_status not available)")
    
    # Test 7: Check database integrity
    print("\n7. Quick integrity check...")
    start = time.time()
    try:
        result = conn.execute("PRAGMA quick_check").fetchone()
        elapsed = time.time() - start
        print(f"✓ Integrity: {result[0]} (took {elapsed:.3f}s)")
    except Exception as e:
        print(f"✗ Integrity check failed: {e}")
    
    # Test 8: Test pandas read_sql with small limit
    print("\n8. Testing pandas read_sql with 10 rows...")
    start = time.time()
    try:
        df = pd.read_sql_query("""
            SELECT * FROM rider_correlations_denorm 
            WHERE correlation_type = 'same_type' 
            LIMIT 10
        """, conn)
        elapsed = time.time() - start
        print(f"✓ Pandas loaded {len(df)} rows in {elapsed:.3f}s")
    except Exception as e:
        print(f"✗ Pandas read failed: {e}")
    
    conn.close()
    print("\n=== Basic Test Complete ===")


if __name__ == "__main__":
    test_basic_queries()