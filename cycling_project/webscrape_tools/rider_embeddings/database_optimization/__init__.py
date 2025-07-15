"""
Database optimization module for rider embeddings.

This module provides optimized database loading and caching functionality
to significantly improve performance of interaction embeddings extraction.

Key optimizations:
- Pre-load all race features into shared memory
- Bulk load rider histories in single queries
- Eliminate redundant database queries
- Use caching for repeated lookups

Expected performance improvement: 5-10x reduction in database query time
"""

from .shared_data_loader import SharedDataLoader
from .optimized_calculator import OptimizedInteractionCalculator
from .bulk_query_utils import BulkQueryUtils

__all__ = ['SharedDataLoader', 'OptimizedInteractionCalculator', 'BulkQueryUtils']