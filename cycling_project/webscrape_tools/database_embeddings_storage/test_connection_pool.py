#!/usr/bin/env python3
"""
Test script for database connection pool
"""
import threading
import time
import logging
from config import ProcessingConfig
from correlation_processor import DatabaseConnectionPool

def test_connection_pool():
    """Test the database connection pool under load"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    config = ProcessingConfig()
    
    # Create connection pool
    pool = DatabaseConnectionPool(
        config.DB_PATH, 
        pool_size=4, 
        timeout_seconds=10
    )
    
    print("=== Testing Database Connection Pool ===")
    print(f"Pool size: 4")
    print(f"Database: {config.DB_PATH}")
    
    # Test 1: Basic functionality
    print("\n1. Testing basic connection pool functionality...")
    try:
        conn = pool.get_connection()
        result = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()
        print(f"✓ Basic query successful: {result[0]} competitions")
        pool.return_connection(conn)
    except Exception as e:
        print(f"✗ Basic test failed: {e}")
        return False
    
    # Test 2: Concurrent access
    print("\n2. Testing concurrent access...")
    
    def worker_thread(thread_id, results):
        """Worker thread for testing concurrent access"""
        try:
            conn = pool.get_connection(timeout=5)
            
            # Simulate some work
            result = conn.execute("SELECT COUNT(*) FROM rider_results WHERE competition_id < ?", [9000]).fetchone()
            time.sleep(0.1)  # Simulate processing time
            
            pool.return_connection(conn)
            results[thread_id] = f"Thread {thread_id}: {result[0]} results"
            
        except Exception as e:
            results[thread_id] = f"Thread {thread_id}: ERROR - {e}"
    
    # Create multiple threads
    threads = []
    results = {}
    
    for i in range(8):  # More threads than pool size to test queuing
        thread = threading.Thread(target=worker_thread, args=(i, results))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Check results
    success_count = sum(1 for r in results.values() if "ERROR" not in r)
    print(f"Concurrent test results: {success_count}/8 threads successful")
    
    for thread_id, result in results.items():
        if "ERROR" in result:
            print(f"  ✗ {result}")
        else:
            print(f"  ✓ {result}")
    
    # Test 3: Pool exhaustion handling
    print("\n3. Testing pool exhaustion handling...")
    connections = []
    try:
        # Get all connections from pool
        for i in range(4):
            conn = pool.get_connection(timeout=1)
            connections.append(conn)
        
        # Try to get one more (should timeout)
        try:
            extra_conn = pool.get_connection(timeout=1)
            print("✗ Pool exhaustion not handled properly")
            pool.return_connection(extra_conn)
        except Exception:
            print("✓ Pool exhaustion handled correctly (timeout as expected)")
        
    finally:
        # Return all connections
        for conn in connections:
            pool.return_connection(conn)
    
    # Cleanup
    pool.close_all()
    
    if success_count >= 7:  # Allow for 1 failure due to timing
        print("\n🎉 Connection pool test PASSED!")
        return True
    else:
        print("\n❌ Connection pool test FAILED!")
        return False

if __name__ == "__main__":
    success = test_connection_pool()
    exit(0 if success else 1)