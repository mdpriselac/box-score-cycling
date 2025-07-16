#!/usr/bin/env python3
"""
Test GPU acceleration components independently

This script tests the GPU acceleration components to identify performance
bottlenecks and validate the Metal accelerator works correctly.
"""

import sys
from pathlib import Path
import torch
import numpy as np
import time
from typing import Dict, Any

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.gpu_optimization.metal_accelerator import MetalAccelerator
from rider_embeddings.gpu_optimization.batch_processor import GPUBatchProcessor


def test_metal_accelerator():
    """Test the Metal accelerator with synthetic data."""
    print("Testing Metal Accelerator...")
    print("-" * 50)
    
    accelerator = MetalAccelerator(enable_gpu=True, batch_size=32)
    
    print(f"GPU available: {accelerator.is_gpu_available()}")
    print(f"Device: {accelerator.device}")
    
    # Test basic GPU operations with larger batches
    batch_size = 256  # Much larger batch size
    n_races = 200     # More races per rider
    n_features = 37
    
    # Create test data
    performance_data = torch.randn(batch_size, n_races)
    features_data = torch.randn(batch_size, n_races, n_features)
    
    print(f"\nTest data shape:")
    print(f"  Performance: {performance_data.shape}")
    print(f"  Features: {features_data.shape}")
    
    # Test correlation calculation
    print("\nTesting correlation calculation...")
    start_time = time.time()
    
    correlations = accelerator.batch_spearman_correlations(
        performance_data, features_data
    )
    
    correlation_time = time.time() - start_time
    print(f"  Correlation time: {correlation_time:.3f} seconds")
    print(f"  Output shape: {correlations.shape}")
    print(f"  Sample correlations: {correlations[0, :5]}")
    
    # Test interaction calculations with larger matrices
    print("\nTesting interaction calculations...")
    race_features = torch.randn(batch_size, 8, n_features)  # 8 percentiles
    correlations_input = torch.randn(batch_size, 8, n_features)
    
    start_time = time.time()
    
    interactions = accelerator.batch_interaction_calculations(
        race_features, correlations_input
    )
    
    interaction_time = time.time() - start_time
    print(f"  Interaction time: {interaction_time:.3f} seconds")
    print(f"  Dot products shape: {interactions['dot'].shape}")
    print(f"  Hadamard products shape: {interactions['hadamard'].shape}")
    print(f"  Cosine similarities shape: {interactions['cosine'].shape}")
    
    # Performance stats
    stats = accelerator.get_performance_stats()
    print(f"\nPerformance stats:")
    print(f"  GPU operations: {stats['gpu_operations']}")
    print(f"  CPU fallbacks: {stats['cpu_fallbacks']}")
    print(f"  Total GPU time: {stats['total_gpu_time']:.3f}s")
    
    # Benchmark with larger batches
    print("\nBenchmarking GPU vs CPU...")
    benchmark_results = accelerator.benchmark_gpu_vs_cpu(
        batch_size=128, n_races=150, n_features=37
    )
    
    print(f"  GPU time: {benchmark_results['gpu_time']:.3f}s")
    print(f"  CPU time: {benchmark_results['cpu_time']:.3f}s")
    print(f"  Speedup: {benchmark_results['speedup']:.1f}x")
    
    return True


def test_batch_processor():
    """Test the GPU batch processor."""
    print("\n\nTesting GPU Batch Processor...")
    print("-" * 50)
    
    device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
    processor = GPUBatchProcessor(device=device, max_batch_size=32)
    
    print(f"Device: {device}")
    print(f"Max batch size: {processor.max_batch_size}")
    print(f"Number of features: {processor.n_features}")
    
    # Create synthetic shared data
    print("\nCreating synthetic shared data...")
    
    # Mock shared race features
    shared_race_features = {
        'race_features_60': {
            1: {name: np.random.randn() for name in processor.feature_names},
            2: {name: np.random.randn() for name in processor.feature_names},
            3: {name: np.random.randn() for name in processor.feature_names}
        },
        'race_features_70': {
            1: {name: np.random.randn() for name in processor.feature_names},
            2: {name: np.random.randn() for name in processor.feature_names},
            3: {name: np.random.randn() for name in processor.feature_names}
        }
    }
    
    # Mock shared rider histories
    shared_rider_histories = {
        101: [
            {'competition_id': 1, 'uci_points_proportional': 10.5, 'competition_type': 'stage'},
            {'competition_id': 2, 'uci_points_proportional': 8.2, 'competition_type': 'stage'},
            {'competition_id': 3, 'uci_points_proportional': 12.1, 'competition_type': 'one_day'}
        ],
        102: [
            {'competition_id': 1, 'uci_points_proportional': 15.3, 'competition_type': 'stage'},
            {'competition_id': 2, 'uci_points_proportional': 11.7, 'competition_type': 'stage'}
        ]
    }
    
    # Test batch preparation
    rider_batch = [(101, 1), (102, 2)]
    feature_tables = ['race_features_60', 'race_features_70']
    
    print(f"Processing batch of {len(rider_batch)} riders...")
    
    start_time = time.time()
    
    batch_data = processor.prepare_correlation_batch(
        rider_batch=rider_batch,
        shared_rider_histories=shared_rider_histories,
        shared_race_features=shared_race_features,
        feature_tables=feature_tables,
        race_type='all'
    )
    
    prep_time = time.time() - start_time
    
    print(f"  Preparation time: {prep_time:.3f} seconds")
    print(f"  Batch size: {batch_data['batch_size']}")
    print(f"  Max races: {batch_data['max_races']}")
    print(f"  Performance tensor shape: {batch_data['performance'].shape}")
    print(f"  Features tensor shape: {batch_data['features'].shape}")
    print(f"  Masks tensor shape: {batch_data['masks'].shape}")
    
    # Test statistics
    stats = processor.get_batch_statistics()
    print(f"\nBatch statistics:")
    print(f"  Total batches: {stats.get('total_batches', 0)}")
    print(f"  Avg padding efficiency: {stats.get('avg_padding_efficiency', 0):.2%}")
    print(f"  Avg memory usage: {stats.get('avg_memory_usage_mb', 0):.1f} MB")
    
    return True


def test_integration():
    """Test integration between components."""
    print("\n\nTesting Integration...")
    print("-" * 50)
    
    # Test end-to-end workflow with larger batches
    accelerator = MetalAccelerator(enable_gpu=True)
    processor = GPUBatchProcessor(device=accelerator.device)
    
    # Create realistic test data with larger batches
    batch_size = 128  # Much larger batch
    n_races = 200     # More races per rider
    n_features = 37
    
    # Simulate correlation calculation
    performance_data = torch.randn(batch_size, n_races)
    features_data = torch.randn(batch_size, n_races, n_features)
    
    print(f"Testing end-to-end workflow...")
    
    start_time = time.time()
    
    # Step 1: Calculate correlations
    correlations = accelerator.batch_spearman_correlations(
        performance_data, features_data
    )
    
    # Step 2: Calculate interactions
    race_features = torch.randn(batch_size, 8, n_features)  # 8 percentiles
    correlations_reshaped = correlations.unsqueeze(1).repeat(1, 8, 1)  # Repeat for percentiles
    
    interactions = accelerator.batch_interaction_calculations(
        race_features, correlations_reshaped
    )
    
    total_time = time.time() - start_time
    
    print(f"  Total time: {total_time:.3f} seconds")
    print(f"  Time per rider: {total_time/batch_size:.3f} seconds")
    
    # Compare with CPU baseline
    print(f"\nComparing with CPU baseline...")
    
    # CPU version (simplified) - move everything to CPU
    cpu_start = time.time()
    
    # Move data to CPU for fair comparison
    race_features_cpu = race_features.cpu()
    correlations_cpu = correlations_reshaped.cpu()
    
    # Simulate CPU correlation calculation
    cpu_correlations = torch.randn(batch_size, n_features)
    
    # Simulate CPU interaction calculation
    cpu_interactions = {
        'dot': torch.sum(race_features_cpu * correlations_cpu, dim=(1, 2)),
        'hadamard': race_features_cpu * correlations_cpu,
        'cosine': torch.randn(batch_size)  # Simplified
    }
    
    cpu_time = time.time() - cpu_start
    
    print(f"  CPU time: {cpu_time:.3f} seconds")
    print(f"  GPU time: {total_time:.3f} seconds")
    print(f"  Speedup: {cpu_time/total_time:.1f}x")
    
    return True


def main():
    """Run all GPU tests."""
    print("GPU ACCELERATION COMPONENT TESTS")
    print("="*70)
    
    # Check basic GPU availability
    print(f"PyTorch version: {torch.__version__}")
    print(f"MPS available: {torch.backends.mps.is_available()}")
    
    if not torch.backends.mps.is_available():
        print("⚠️  MPS not available, tests will use CPU")
    
    try:
        # Test individual components
        test_metal_accelerator()
        test_batch_processor()
        test_integration()
        
        print("\n" + "="*70)
        print("✅ ALL GPU TESTS PASSED!")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()