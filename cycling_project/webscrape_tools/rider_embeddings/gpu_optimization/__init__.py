"""
GPU optimization module for rider embeddings.

This module provides GPU acceleration for matrix operations using Apple's
Metal Performance Shaders (MPS) through PyTorch.

Key optimizations:
- Batch correlation calculations on GPU
- Parallel matrix operations
- Memory-efficient tensor operations
- Automatic fallback to CPU when GPU is unavailable

Expected performance improvement: 2-3x additional speedup on top of database optimizations
"""

from .metal_accelerator import MetalAccelerator
from .gpu_calculator import GPUOptimizedInteractionCalculator
from .batch_processor import GPUBatchProcessor

__all__ = ['MetalAccelerator', 'GPUOptimizedInteractionCalculator', 'GPUBatchProcessor']