#!/usr/bin/env python3
"""
Test script to compare the original vs optimized rider sampling performance.
"""
import time
import sys
from pathlib import Path

# Add to path for imports
sys.path.append(str(Path(__file__).parent))

from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator


def test_sampling_performance():
    """Compare original vs optimized sampling approaches."""
    
    print("RIDER SAMPLING PERFORMANCE TEST")
    print("=" * 60)
    
    db_path = "database/database/cycling_races.db"
    sample_sizes = [50, 100, 200]  # Test different sizes
    
    generator = EnhancedParallelCorrelationGenerator(
        db_path=db_path,
        output_dir="sampling_test",
        batch_size=50,
        n_workers=4,
        preload_all_data=False  # Just test sampling, not full processing
    )
    
    for sample_size in sample_sizes:
        print(f"\n🔍 Testing sample size: {sample_size} riders")
        print("-" * 50)
        
        # Test optimized approach
        print("Testing OPTIMIZED two-step sampling...")
        start_time = time.time()
        
        try:
            optimized_results = generator._get_sample_rider_results_optimized(sample_size)
            optimized_time = time.time() - start_time
            
            print(f"✓ Optimized sampling: {len(optimized_results)} results in {optimized_time:.2f}s")
            print(f"✓ Rate: {len(optimized_results)/optimized_time:.1f} results/second")
            
            if optimized_time < 1.0:
                print("🚀 Excellent performance!")
            elif optimized_time < 5.0:
                print("✓ Good performance")
            else:
                print("⚠ Could be faster")
                
        except Exception as e:
            print(f"✗ Optimized sampling failed: {e}")
            import traceback
            traceback.print_exc()
    
    # Test larger sample to see scaling
    print(f"\n🔍 Testing LARGE sample: 1000 riders")
    print("-" * 50)
    
    start_time = time.time()
    try:
        large_results = generator._get_sample_rider_results_optimized(1000)
        large_time = time.time() - start_time
        
        print(f"✓ Large optimized sampling: {len(large_results)} results in {large_time:.2f}s")
        print(f"✓ Rate: {len(large_results)/large_time:.1f} results/second")
        
        # Extrapolate to very large datasets
        print(f"\n📊 Extrapolated performance:")
        for size in [5000, 10000, 20000]:
            estimated_time = large_time * (size / 1000)
            print(f"  {size:,} riders: ~{estimated_time:.1f} seconds ({estimated_time/60:.1f} minutes)")
            
    except Exception as e:
        print(f"✗ Large sampling failed: {e}")
    
    print(f"\n✅ Sampling performance test completed!")


def test_database_queries():
    """Test the individual database queries to understand performance."""
    
    print("\n" + "=" * 60)
    print("DATABASE QUERY ANALYSIS")
    print("=" * 60)
    
    import sqlite3
    db_path = "database/database/cycling_races.db"
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Test 1: Count total rider_results
        print("\n📊 Database Statistics:")
        start_time = time.time()
        cursor.execute("SELECT COUNT(*) FROM rider_results")
        total_results = cursor.fetchone()[0]
        query_time = time.time() - start_time
        print(f"  Total rider results: {total_results:,} (query: {query_time:.3f}s)")
        
        # Test 2: Count eligible riders (simple GROUP BY)
        start_time = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM (
                SELECT rider_id, COUNT(*) as race_count
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id  
                GROUP BY rider_id
                HAVING COUNT(*) >= 25
            )
        """)
        eligible_riders = cursor.fetchone()[0]
        query_time = time.time() - start_time
        print(f"  Eligible riders (25+ races): {eligible_riders:,} (query: {query_time:.3f}s)")
        
        # Test 3: Sample 500 eligible riders  
        start_time = time.time()
        cursor.execute("""
            SELECT rider_id, COUNT(*) as race_count
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id  
            WHERE c.date <= '2025-01-01'
            GROUP BY rider_id
            HAVING COUNT(*) >= 25
            ORDER BY RANDOM()
            LIMIT 500
        """)
        sampled_riders = cursor.fetchall()
        query_time = time.time() - start_time
        print(f"  Sample 500 eligible riders: {len(sampled_riders)} found (query: {query_time:.3f}s)")
        
        if sampled_riders:
            avg_races = sum(r[1] for r in sampled_riders) / len(sampled_riders)
            print(f"  Average races per sampled rider: {avg_races:.1f}")


if __name__ == "__main__":
    test_database_queries()
    test_sampling_performance()