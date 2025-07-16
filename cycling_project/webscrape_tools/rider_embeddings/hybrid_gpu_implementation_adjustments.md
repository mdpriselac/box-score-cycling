# Hybrid GPU Implementation Adjustments

## Executive Summary

The current GPU implementation is inefficient because it tries to GPU-accelerate Spearman correlations, which are inherently sequential and perform poorly on GPU (47s GPU vs 0.7s CPU). This document outlines a hybrid approach that uses CPU for correlations and GPU only for matrix operations where it provides actual speedup.

## Current State Analysis

### What Works Well (Keep)
- **Database optimizations**: 5-10x speedup from pre-loading data
- **Shared memory approach**: Eliminates redundant queries
- **Modular architecture**: Clean separation of concerns

### What's Broken (Fix/Remove)
- **GPU correlation calculation**: 67x slower than CPU (47s vs 0.7s)
- **Small batch sizes**: GPU overhead not justified
- **Complex tensor conversions**: Unnecessary complexity
- **Device mismatch errors**: Inconsistent tensor placement

### What's Missing (Add)
- **Hybrid processing**: CPU for correlations, GPU for matrix ops
- **Larger batch processing**: 1000+ riders at once
- **Simplified GPU operations**: Focus only on matrix multiplications

## Implementation Plan

### Phase 1: Simplify and Remove Bad GPU Code

#### 1.1 Remove Inefficient GPU Correlation Code
**Files to modify:**
- `rider_embeddings/gpu_optimization/metal_accelerator.py`

**Actions:**
- Remove `batch_spearman_correlations()` method (lines ~45-120)
- Remove `_gpu_spearman_correlations()` method (lines ~121-170)
- Remove `_convert_to_ranks()` method (lines ~171-195)
- Remove `_pearson_correlation()` method (lines ~196-210)
- Keep only `batch_interaction_calculations()` method

#### 1.2 Simplify GPU Calculator
**Files to modify:**
- `rider_embeddings/gpu_optimization/gpu_calculator.py`

**Actions:**
- Remove `_calculate_gpu_correlations()` method (lines ~150-180)
- Remove `_prepare_single_rider_for_gpu()` method (lines ~220-250)
- Simplify `_gpu_batch_processing()` to use CPU correlations
- Remove complex tensor conversion logic

#### 1.3 Remove Unused Batch Processor Logic
**Files to modify:**
- `rider_embeddings/gpu_optimization/batch_processor.py`

**Actions:**
- Remove `prepare_correlation_batch()` method (lines ~60-150)
- Keep only `prepare_interaction_batch()` method
- Simplify data structures

### Phase 2: Implement Hybrid CPU/GPU Approach

#### 2.1 Create Hybrid Calculator
**New file to create:**
- `rider_embeddings/gpu_optimization/hybrid_calculator.py`

**Purpose:** Combines CPU correlations with GPU matrix operations

**Key components:**
```python
class HybridInteractionCalculator:
    def __init__(self, shared_data, use_gpu=True):
        # Use existing OptimizedInteractionCalculator for correlations
        self.cpu_calculator = OptimizedInteractionCalculator(shared_data)
        # Use GPU only for matrix operations
        self.gpu_accelerator = MetalAccelerator(enable_gpu=use_gpu)
    
    def calculate_batch_interactions(self, rider_batch):
        # Step 1: CPU correlation calculation (fast)
        correlations = self.cpu_calculator.calculate_correlations_batch(rider_batch)
        
        # Step 2: GPU matrix operations (where GPU excels)
        if len(rider_batch) > 100:  # Only use GPU for large batches
            interactions = self.gpu_accelerator.batch_interaction_calculations(
                current_features_tensor, correlations_tensor
            )
        else:
            interactions = self.cpu_calculator.calculate_interactions(correlations)
        
        return self.format_results(interactions)
```

#### 2.2 Modify Existing CPU Calculator
**Files to modify:**
- `rider_embeddings/database_optimization/optimized_calculator.py`

**Actions:**
- Add `calculate_correlations_batch()` method for processing multiple riders
- Add `calculate_interactions_batch()` method for CPU fallback
- Optimize for larger batch sizes (current handles 1 rider at a time)

#### 2.3 Streamline GPU Accelerator
**Files to modify:**
- `rider_embeddings/gpu_optimization/metal_accelerator.py`

**Actions:**
- Remove all correlation-related methods
- Keep only `batch_interaction_calculations()` method
- Optimize for larger batches (1000+ riders)
- Add memory management for large tensors

### Phase 3: Update Extraction Script

#### 3.1 Modify Main Extraction Script
**Files to modify:**
- `rider_embeddings/extract_interaction_embeddings_gpu_optimized.py`

**Actions:**
- Replace `GPUOptimizedInteractionCalculator` with `HybridInteractionCalculator`
- Increase batch sizes dramatically:
  ```python
  OPTIMIZATION_CONFIG = {
      'chunk_size': 1000,      # Process 1000 riders per chunk
      'gpu_batch_size': 500,   # GPU batch size
      'cpu_batch_size': 100,   # CPU batch size for small batches
      'gpu_memory_target_mb': 6144  # Use more GPU memory
  }
  ```
- Add hybrid processing logic in worker function

#### 3.2 Update Worker Function
**Files to modify:**
- `rider_embeddings/extract_interaction_embeddings_gpu_optimized.py`

**Worker function logic:**
```python
def process_rider_chunk_hybrid(chunk_data):
    calculator = HybridInteractionCalculator(shared_data, use_gpu=True)
    
    # Process entire chunk at once (1000 riders)
    results = calculator.calculate_batch_interactions(
        rider_batch=chunk_data['rider_result_data'],
        feature_tables=chunk_data['feature_tables']
    )
    
    return results
```

### Phase 4: Performance Optimization

#### 4.1 Optimize Memory Usage
**Files to modify:**
- `rider_embeddings/gpu_optimization/metal_accelerator.py`

**Actions:**
- Add memory pooling for large tensors
- Add automatic batch size adjustment based on available memory
- Add tensor cleanup after operations

#### 4.2 Add Performance Monitoring
**Files to modify:**
- `rider_embeddings/gpu_optimization/hybrid_calculator.py`

**Actions:**
- Add timing for CPU vs GPU operations
- Add memory usage monitoring
- Add automatic CPU fallback for small batches

### Phase 5: Testing and Validation

#### 5.1 Create Hybrid Test Suite
**New file to create:**
- `rider_embeddings/test_hybrid_gpu_acceleration.py`

**Test scenarios:**
- Small batches (< 100 riders) → CPU only
- Medium batches (100-500 riders) → Hybrid
- Large batches (500+ riders) → GPU for matrix ops
- Memory stress testing with 1000+ riders

#### 5.2 Benchmark Performance
**Expected results:**
- Small batches: Same as current database-optimized (24s for 1000 riders)
- Large batches: 2-3x additional speedup for matrix operations
- Memory usage: 2-4GB GPU memory for 1000 riders

## Implementation Priority

### High Priority (Week 1)
1. Remove inefficient GPU correlation code
2. Create hybrid calculator with CPU correlations
3. Update extraction script to use hybrid approach

### Medium Priority (Week 2)
1. Optimize memory usage for large batches
2. Add performance monitoring
3. Create comprehensive test suite

### Low Priority (Week 3)
1. Fine-tune batch size algorithms
2. Add automatic memory management
3. Create performance comparison reports

## Files Reference

### Existing Files to Modify
1. `rider_embeddings/gpu_optimization/metal_accelerator.py` - Remove correlation methods
2. `rider_embeddings/gpu_optimization/gpu_calculator.py` - Simplify to hybrid approach
3. `rider_embeddings/database_optimization/optimized_calculator.py` - Add batch methods
4. `rider_embeddings/extract_interaction_embeddings_gpu_optimized.py` - Use hybrid calculator

### New Files to Create
1. `rider_embeddings/gpu_optimization/hybrid_calculator.py` - Main hybrid implementation
2. `rider_embeddings/test_hybrid_gpu_acceleration.py` - Test suite

### Files to Remove/Deprecate
1. `rider_embeddings/gpu_optimization/batch_processor.py` - Most methods unused
2. Complex tensor conversion logic in gpu_calculator.py

## Success Metrics

### Before (Current GPU Implementation)
- Correlation calculation: 47s GPU vs 0.7s CPU
- Total time: 22.7s for 128 riders (0.177s per rider)
- Speedup: 0.0x (GPU slower than CPU)

### After (Target Hybrid Implementation)
- Correlation calculation: 0.7s CPU (same as before)
- Matrix operations: 2-3x faster on GPU for large batches
- Total time: 8-12s for 1000 riders (0.008-0.012s per rider)
- Speedup: 2-3x additional improvement over database-optimized

## Key Principles

1. **Use the right tool for the job**: CPU for correlations, GPU for matrix ops
2. **Batch size matters**: Only use GPU for large batches (500+ riders)
3. **Simplicity over complexity**: Remove unnecessary tensor conversions
4. **Measure everything**: Add comprehensive performance monitoring
5. **Graceful degradation**: Always have CPU fallback

## Next Steps

1. Review this plan with the team
2. Start with Phase 1 (removing bad GPU code)
3. Implement hybrid calculator (Phase 2)
4. Test with realistic data sizes
5. Iterate based on performance results

This hybrid approach should provide actual speedup while maintaining the simplicity and reliability of the database-optimized version.