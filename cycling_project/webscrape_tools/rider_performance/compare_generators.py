#!/usr/bin/env python3
"""
Compare performance between original and optimized dataset generators.
"""

import time
from dataset_generator import DatasetGenerator
from optimized_dataset_generator import OptimizedDatasetGenerator

def time_generator(generator_func, name: str):
    """Time a generator function and return results."""
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"{'='*60}")
    
    start_time = time.time()
    try:
        datasets = generator_func()
        elapsed = time.time() - start_time
        
        print(f"✓ {name} completed in {elapsed:.2f} seconds")
        print(f"GC dataset: {len(datasets['gc_dataset'])} rows")
        print(f"Stage/One-day dataset: {len(datasets['stage_one_day_dataset'])} rows")
        
        return {
            'success': True,
            'elapsed': elapsed,
            'gc_rows': len(datasets['gc_dataset']),
            'stage_rows': len(datasets['stage_one_day_dataset']),
            'total_rows': len(datasets['gc_dataset']) + len(datasets['stage_one_day_dataset'])
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"✗ {name} failed after {elapsed:.2f} seconds: {e}")
        return {
            'success': False,
            'elapsed': elapsed,
            'error': str(e)
        }

def main():
    db_path = "database/database/cycling_races.db"
    
    # Test parameters
    cutoff_date = "2010-12-31"
    min_results = 100
    target_variable = 'uci_points_actual'
    
    print("Dataset Generator Performance Comparison")
    print("=" * 60)
    print(f"Parameters:")
    print(f"  Cutoff date: {cutoff_date}")
    print(f"  Min results: {min_results}")
    print(f"  Target variable: {target_variable}")
    
    # Original generator
    def test_original():
        generator = DatasetGenerator(db_path)
        return generator.generate_datasets(
            cutoff_date=cutoff_date,
            min_results=min_results,
            target_variable=target_variable
        )
    
    # Optimized generator (sequential)
    def test_optimized_sequential():
        generator = OptimizedDatasetGenerator(db_path)
        return generator.generate_datasets_fast(
            cutoff_date=cutoff_date,
            min_results=min_results,
            target_variable=target_variable,
            use_parallel=False
        )
    
    # Optimized generator (parallel)
    def test_optimized_parallel():
        generator = OptimizedDatasetGenerator(db_path)
        return generator.generate_datasets_fast(
            cutoff_date=cutoff_date,
            min_results=min_results,
            target_variable=target_variable,
            use_parallel=True
        )
    
    # Run tests
    results = {}
    
    # Test original generator
    results['original'] = time_generator(test_original, "Original Generator")
    
    # Test optimized sequential
    results['optimized_sequential'] = time_generator(test_optimized_sequential, "Optimized Generator (Sequential)")
    
    # Test optimized parallel
    results['optimized_parallel'] = time_generator(test_optimized_parallel, "Optimized Generator (Parallel)")
    
    # Summary
    print(f"\n{'='*60}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*60}")
    
    successful_tests = {k: v for k, v in results.items() if v['success']}
    
    if len(successful_tests) > 1:
        baseline = None
        for name, result in successful_tests.items():
            if baseline is None:
                baseline = result['elapsed']
                print(f"{name:>25}: {result['elapsed']:>8.2f}s (baseline)")
            else:
                speedup = baseline / result['elapsed']
                print(f"{name:>25}: {result['elapsed']:>8.2f}s ({speedup:.1f}x faster)")
        
        # Data validation
        print(f"\nData Validation:")
        first_result = list(successful_tests.values())[0]
        for name, result in successful_tests.items():
            if result['total_rows'] == first_result['total_rows']:
                print(f"{name:>25}: ✓ {result['total_rows']:,} total rows")
            else:
                print(f"{name:>25}: ✗ {result['total_rows']:,} total rows (expected {first_result['total_rows']:,})")
    else:
        print("Not enough successful tests to compare performance")
    
    # Error summary
    failed_tests = {k: v for k, v in results.items() if not v['success']}
    if failed_tests:
        print(f"\nFailed Tests:")
        for name, result in failed_tests.items():
            print(f"{name:>25}: {result['error']}")

if __name__ == "__main__":
    main()