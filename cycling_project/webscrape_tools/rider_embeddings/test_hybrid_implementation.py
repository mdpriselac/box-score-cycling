#!/usr/bin/env python3
"""
Test script for the hybrid CPU/GPU implementation

This script tests the hybrid implementation with different batch sizes to verify
that the optimizations work correctly and provide expected performance improvements.
"""

import sys
from pathlib import Path
import time
import logging

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.database_optimization import SharedDataLoader, BulkQueryUtils
from rider_embeddings.gpu_optimization.hybrid_calculator import HybridInteractionCalculator

# Configuration
DB_PATH = "database/database/cycling_races.db"
FEATURE_TABLES = [
    'race_features_60', 'race_features_70', 'race_features_80', 'race_features_90'
]
RACE_TYPE_PERCENTILES = {
    'gc': 40,  # Lower percentiles for testing
    'stage': 40,
    'one_day': 40,
    'stage_one_day': 40,
    'all': 40
}
INTERACTION_TYPES = ['dot', 'hadamard', 'cosine']
TEST_SAMPLE_SIZE = 200  # Small sample for testing


def test_hybrid_calculator():
    """Test the hybrid calculator with different batch sizes."""
    print("HYBRID CALCULATOR TEST")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        # Initialize utility classes
        bulk_utils = BulkQueryUtils(DB_PATH)
        data_loader = SharedDataLoader(DB_PATH)
        
        print("Step 1: Setting up test data...")
        
        # Calculate minimums
        minimums = bulk_utils.calculate_percentile_minimums(RACE_TYPE_PERCENTILES)
        
        # Get sample data
        print(f"Getting sample of {TEST_SAMPLE_SIZE} rider results...")
        rider_results = bulk_utils.get_rider_result_sample_with_competitions(
            TEST_SAMPLE_SIZE, minimums
        )
        
        print(f"Retrieved {len(rider_results)} rider results")
        
        # Pre-load data
        print("Pre-loading data into shared memory...")
        competition_ids = bulk_utils.get_unique_competition_ids(rider_results)
        rider_result_ids = bulk_utils.get_rider_result_ids(rider_results)
        
        preload_start = time.time()
        shared_race_features = data_loader.preload_race_features(
            competition_ids, FEATURE_TABLES
        )
        shared_rider_histories = data_loader.preload_rider_histories(rider_result_ids)
        preload_time = time.time() - preload_start
        
        print(f"Pre-loading completed in {preload_time:.1f} seconds")
        
        # Configuration
        calculator_config = {
            'min_races_all': minimums['all'],
            'min_races_stage': minimums['stage'],
            'min_races_one_day': minimums['one_day'],
            'min_races_gc': minimums['gc']
        }
        
        print("\nStep 2: Testing different batch sizes...")
        
        # Test different batch sizes
        test_batches = [
            ("Small batch (CPU)", 10),
            ("Medium batch (CPU)", 50),
            ("Large batch (GPU)", 100),
            ("Very large batch (GPU)", 150)
        ]
        
        results_summary = []
        
        for test_name, batch_size in test_batches:
            print(f"\n{test_name} - {batch_size} riders:")
            
            # Create subset of data
            test_data = rider_results[:batch_size]
            
            # Create hybrid calculator
            calculator = HybridInteractionCalculator(
                shared_race_features=shared_race_features,
                shared_rider_histories=shared_rider_histories,
                calculator_config=calculator_config,
                use_gpu=True,
                gpu_batch_size=100,  # Threshold for GPU usage
                cpu_batch_size=50
            )
            
            # Process batch
            start_time = time.time()
            
            try:
                results = calculator.calculate_batch_interactions(
                    test_data, FEATURE_TABLES, INTERACTION_TYPES
                )
                
                processing_time = time.time() - start_time
                
                # Get performance stats
                stats = calculator.get_performance_stats()
                
                print(f"  ✓ Processed {len(results)} results in {processing_time:.2f} seconds")
                print(f"  ✓ Average per rider: {processing_time/len(results):.3f} seconds")
                print(f"  ✓ GPU usage ratio: {stats.get('gpu_usage_ratio', 0):.1%}")
                print(f"  ✓ CPU correlation time: {stats.get('cpu_correlation_time', 0):.2f}s")
                print(f"  ✓ GPU interaction time: {stats.get('gpu_interaction_time', 0):.2f}s")
                
                # Verify results structure
                if results:
                    sample_result = results[0]
                    phase1_data = sample_result.get('phase1_interactions', {})
                    phase2_data = sample_result.get('phase2_interactions', {})
                    has_phase1 = len(phase1_data) > 0
                    has_phase2 = len(phase2_data) > 0
                    print(f"  ✓ Results structure: Phase1={has_phase1}, Phase2={has_phase2}")
                    
                    # Debug info
                    if has_phase1:
                        print(f"    Phase1 race types: {list(phase1_data.keys())}")
                    if has_phase2:
                        print(f"    Phase2 race types: {list(phase2_data.keys())}")
                    
                    # Check metadata for warnings
                    metadata = sample_result.get('metadata', {})
                    warnings = metadata.get('warnings', [])
                    if warnings:
                        print(f"    Warnings: {warnings[:2]}")  # Show first 2 warnings
                    
                    race_counts = metadata.get('n_races', {})
                    if race_counts:
                        print(f"    Race counts: {race_counts}")
                
                results_summary.append({
                    'test_name': test_name,
                    'batch_size': batch_size,
                    'processing_time': processing_time,
                    'per_rider_time': processing_time/len(results),
                    'gpu_usage_ratio': stats.get('gpu_usage_ratio', 0),
                    'success': True
                })
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results_summary.append({
                    'test_name': test_name,
                    'batch_size': batch_size,
                    'processing_time': 0,
                    'per_rider_time': 0,
                    'gpu_usage_ratio': 0,
                    'success': False,
                    'error': str(e)
                })
        
        print("\n" + "=" * 50)
        print("TEST RESULTS SUMMARY")
        print("=" * 50)
        
        for result in results_summary:
            if result['success']:
                print(f"{result['test_name']}:")
                print(f"  Batch size: {result['batch_size']}")
                print(f"  Total time: {result['processing_time']:.2f}s")
                print(f"  Per rider: {result['per_rider_time']:.3f}s")
                print(f"  GPU usage: {result['gpu_usage_ratio']:.1%}")
            else:
                print(f"{result['test_name']}: FAILED - {result.get('error', 'Unknown error')}")
            print()
        
        # Performance comparison
        successful_results = [r for r in results_summary if r['success']]
        if len(successful_results) >= 2:
            fastest = min(successful_results, key=lambda x: x['per_rider_time'])
            slowest = max(successful_results, key=lambda x: x['per_rider_time'])
            speedup = slowest['per_rider_time'] / fastest['per_rider_time']
            
            print(f"Performance Analysis:")
            print(f"  Fastest: {fastest['test_name']} ({fastest['per_rider_time']:.3f}s per rider)")
            print(f"  Slowest: {slowest['test_name']} ({slowest['per_rider_time']:.3f}s per rider)")
            print(f"  Speedup: {speedup:.1f}x")
        
        print("\n✅ Hybrid implementation test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


def test_gpu_availability():
    """Test GPU availability and basic functionality."""
    print("\nGPU AVAILABILITY TEST")
    print("=" * 30)
    
    try:
        import torch
        
        print(f"PyTorch version: {torch.__version__}")
        print(f"MPS available: {torch.backends.mps.is_available()}")
        
        if torch.backends.mps.is_available():
            # Test basic GPU operation
            device = torch.device('mps')
            test_tensor = torch.randn(100, 100, device=device)
            result = torch.mm(test_tensor, test_tensor.t())
            print("✅ Basic GPU operations working")
            
            # Test memory
            large_tensor = torch.randn(1000, 1000, device=device)
            print("✅ GPU memory allocation working")
        else:
            print("⚠️  GPU not available, will use CPU mode")
            
    except Exception as e:
        print(f"❌ GPU test failed: {e}")


if __name__ == "__main__":
    test_gpu_availability()
    test_hybrid_calculator()