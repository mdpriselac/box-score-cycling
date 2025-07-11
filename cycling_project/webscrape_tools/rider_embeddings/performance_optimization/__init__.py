# Performance Optimization Package
"""
High-performance implementations for rider embedding correlation generation.

This package provides optimized versions of the correlation generation pipeline
with significant performance improvements through:
- Batched database loading
- Parallel processing
- Optimized data structures
- Memory-efficient operations
"""

from .batched_database_loader import BatchedDatabaseLoader
from .optimized_base import OptimizedPerformanceFeatureLinkBase, BatchedCorrelationCalculatorMixin
from .parallel_correlation_generator import ParallelCorrelationGenerator

__all__ = [
    'BatchedDatabaseLoader',
    'OptimizedPerformanceFeatureLinkBase', 
    'BatchedCorrelationCalculatorMixin',
    'ParallelCorrelationGenerator'
]