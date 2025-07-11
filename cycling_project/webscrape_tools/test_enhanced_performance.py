#!/usr/bin/env python3
"""
Comprehensive performance test comparing original, parallel, and enhanced parallel implementations.
"""
import time
import sys
from pathlib import Path

# Add to path for imports
sys.path.append(str(Path(__file__).parent))

from rider_embeddings.race_type_pipeline_adapter import RaceTypeDataGenerator
from rider_embeddings.performance_optimization import ParallelCorrelationGenerator
from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator


def test_comprehensive_performance():
    """Compare all three implementations: original, parallel, and enhanced parallel."""
    
    print("COMPREHENSIVE PERFORMANCE COMPARISON")
    print("=" * 70)
    
    db_path = "database/database/cycling_races.db"
    sample_size = 200  # Increased sample size for better testing
    feature_tables = ['race_features_70', 'race_features_80', 'race_features_90']
    
    results = {}
    
    # Test 1: Original Sequential Implementation
    print(f"\n1. ORIGINAL SEQUENTIAL IMPLEMENTATION")
    print("-" * 50)
    print(f"Sample size: {sample_size} riders")
    
    try:
        original_generator = RaceTypeDataGenerator(
            db_path=db_path,
            output_dir="original_comprehensive_test",
            batch_size=50,
            min_races_gc=8,
            min_races_stage=15,
            min_races_one_day=10,
            min_races_all=25
        )
        
        start_time = time.time()
        
        original_generator.generate_sample(
            sample_size=sample_size,
            feature_tables=feature_tables,
            output_name="original_comprehensive"
        )
        
        original_time = time.time() - start_time
        original_rate = sample_size / original_time
        
        results['original'] = {
            'time': original_time,
            'rate': original_rate,
            'status': 'success'
        }
        
        print(f"✓ Completed in {original_time:.2f} seconds")
        print(f"✓ Rate: {original_rate:.2f} riders/second")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        results['original'] = {'status': 'failed', 'error': str(e)}
    
    # Test 2: Standard Parallel Implementation
    print(f"\n2. STANDARD PARALLEL IMPLEMENTATION")
    print("-" * 50)
    print(f"Sample size: {sample_size} riders, 4 workers")
    
    try:
        parallel_generator = ParallelCorrelationGenerator(
            db_path=db_path,
            output_dir="parallel_comprehensive_test",
            batch_size=50,
            n_workers=4,
            use_batched_loading=False  # Standard parallel without batching
        )
        
        start_time = time.time()
        
        parallel_generator.generate_sample_parallel(
            sample_size=sample_size,
            feature_tables=feature_tables,
            output_name="parallel_comprehensive",
            calculator_type='race_type'
        )
        
        parallel_time = time.time() - start_time
        parallel_rate = sample_size / parallel_time
        
        results['parallel'] = {
            'time': parallel_time,
            'rate': parallel_rate,
            'status': 'success'
        }
        
        print(f"✓ Completed in {parallel_time:.2f} seconds")
        print(f"✓ Rate: {parallel_rate:.2f} riders/second")
        
        if 'original' in results and results['original']['status'] == 'success':
            speedup = results['original']['time'] / parallel_time
            print(f"✓ Speedup vs original: {speedup:.2f}x")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        results['parallel'] = {'status': 'failed', 'error': str(e)}
    
    # Test 3: Enhanced Parallel Implementation (with pre-loading)
    print(f"\n3. ENHANCED PARALLEL IMPLEMENTATION")
    print("-" * 50)
    print(f"Sample size: {sample_size} riders, 4 workers, pre-loading enabled")
    
    try:
        enhanced_generator = EnhancedParallelCorrelationGenerator(
            db_path=db_path,
            output_dir="enhanced_comprehensive_test",
            batch_size=50,
            n_workers=4,
            preload_all_data=True
        )
        
        start_time = time.time()
        
        enhanced_generator.generate_sample_parallel_enhanced(
            sample_size=sample_size,
            feature_tables=feature_tables,
            output_name="enhanced_comprehensive"
        )
        
        enhanced_time = time.time() - start_time
        enhanced_rate = sample_size / enhanced_time
        
        results['enhanced'] = {
            'time': enhanced_time,
            'rate': enhanced_rate,
            'status': 'success'
        }
        
        print(f"✓ Completed in {enhanced_time:.2f} seconds")
        print(f"✓ Rate: {enhanced_rate:.2f} riders/second")
        
        if 'original' in results and results['original']['status'] == 'success':
            speedup = results['original']['time'] / enhanced_time
            print(f"✓ Speedup vs original: {speedup:.2f}x")
        
        if 'parallel' in results and results['parallel']['status'] == 'success':
            improvement = results['parallel']['time'] / enhanced_time
            print(f"✓ Improvement vs parallel: {improvement:.2f}x")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        results['enhanced'] = {'status': 'failed', 'error': str(e)}
    
    # Performance Analysis
    print(f"\n4. PERFORMANCE ANALYSIS")
    print("=" * 50)
    
    successful_tests = [k for k, v in results.items() if v.get('status') == 'success']
    
    if len(successful_tests) >= 2:
        print("\nTiming Comparison:")
        print(f"{'Method':<20} {'Time (s)':<12} {'Rate (r/s)':<12} {'Speedup':<10}")
        print("-" * 60)
        
        baseline_time = None
        if 'original' in results and results['original']['status'] == 'success':
            baseline_time = results['original']['time']
        elif successful_tests:
            baseline_time = results[successful_tests[0]]['time']
        
        for method in ['original', 'parallel', 'enhanced']:
            if method in results and results[method]['status'] == 'success':
                data = results[method]
                speedup = baseline_time / data['time'] if baseline_time else 1.0
                print(f"{method.capitalize():<20} {data['time']:<12.2f} {data['rate']:<12.2f} {speedup:<10.2f}x")
        
        # Best performer
        best_method = max(successful_tests, key=lambda m: results[m]['rate'])
        best_rate = results[best_method]['rate']
        
        print(f"\n🏆 Best performer: {best_method.upper()}")
        print(f"   Rate: {best_rate:.2f} riders/second")
        
        # Extrapolate to larger datasets
        print(f"\n📊 Extrapolated Performance for Large Datasets:")
        for dataset_size in [1000, 5000, 10000]:
            time_estimate = dataset_size / best_rate
            print(f"   {dataset_size:,} riders: ~{time_estimate/60:.1f} minutes ({time_estimate:.0f} seconds)")
    
    else:
        print("⚠ Insufficient successful tests for comparison")
    
    # Recommendations
    print(f"\n5. RECOMMENDATIONS")
    print("=" * 50)
    
    if 'enhanced' in results and results['enhanced']['status'] == 'success':
        enhanced_data = results['enhanced']
        
        if enhanced_data['rate'] > 5.0:
            print("✓ Enhanced parallel processing is highly effective")
            print("✓ Recommended for production use")
            print("✓ Can handle large datasets efficiently")
        elif enhanced_data['rate'] > 2.0:
            print("✓ Enhanced parallel processing shows good improvement")
            print("✓ Suitable for regular use")
        else:
            print("⚠ Enhanced parallel processing needs optimization")
        
        # Check if enhancement was beneficial
        if ('parallel' in results and results['parallel']['status'] == 'success' and
            enhanced_data['rate'] > results['parallel']['rate'] * 1.2):
            print("✓ Pre-loading provides significant benefit")
        elif 'parallel' in results and results['parallel']['status'] == 'success':
            print("⚠ Pre-loading provides marginal benefit")
        
    else:
        print("✗ Enhanced parallel processing needs debugging")
    
    # Memory and scaling considerations
    print(f"\n6. SCALING CONSIDERATIONS")
    print("=" * 50)
    
    if successful_tests:
        best_rate = max(results[m]['rate'] for m in successful_tests)
        
        print(f"Current best rate: {best_rate:.2f} riders/second")
        
        # Memory estimates for pre-loading
        riders_per_gb = 5000  # Rough estimate
        for dataset_size in [1000, 5000, 10000]:
            memory_gb = dataset_size / riders_per_gb
            processing_time = dataset_size / best_rate
            
            print(f"{dataset_size:,} riders:")
            print(f"  - Estimated memory: ~{memory_gb:.1f} GB")
            print(f"  - Estimated time: ~{processing_time/60:.1f} minutes")
            
            if memory_gb > 16:
                print("  - ⚠ High memory usage - consider chunked processing")
            elif memory_gb > 8:
                print("  - ⚠ Moderate memory usage - monitor available RAM")
            else:
                print("  - ✓ Reasonable memory usage")
    
    print(f"\nComprehensive performance test completed!")
    return results


if __name__ == "__main__":
    test_comprehensive_performance()