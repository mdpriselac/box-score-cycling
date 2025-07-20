"""
Correlation Feature Analysis Module

This module analyzes the quality and behavior of correlations between rider performance 
and race features across different percentile levels.
"""

# Main interfaces (use optimized versions by default)
from .optimized_correlation_analyzer import OptimizedCorrelationAnalyzer as CorrelationAnalyzer
from .optimized_correlation_analyzer import analyze_correlations_optimized as analyze_correlations
from .blob_data_loader import BlobCorrelationDataLoader as CorrelationDataLoader

# Legacy interfaces (for backward compatibility)
from .correlation_analyzer import CorrelationAnalyzer as LegacyCorrelationAnalyzer
from .data_loader import CorrelationDataLoader as LegacyCorrelationDataLoader

# Supporting modules
from .statistics_calculator import CorrelationStatisticsCalculator
from .pattern_classifier import CorrelationPatternClassifier
from .quality_scorer import CorrelationQualityScorer
from .report_generator import CorrelationReportGenerator

__all__ = [
    # Main interfaces (optimized)
    'CorrelationAnalyzer',
    'analyze_correlations',
    'CorrelationDataLoader',
    
    # Legacy interfaces
    'LegacyCorrelationAnalyzer',
    'LegacyCorrelationDataLoader',
    
    # Supporting modules
    'CorrelationStatisticsCalculator',
    'CorrelationPatternClassifier',
    'CorrelationQualityScorer',
    'CorrelationReportGenerator'
]