"""
Optimized correlation analyzer using blob storage.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .blob_data_loader import BlobCorrelationDataLoader
from .statistics_calculator import CorrelationStatisticsCalculator
from .pattern_classifier import CorrelationPatternClassifier
from .quality_scorer import CorrelationQualityScorer
from .report_generator import CorrelationReportGenerator
from .correlation_feature_analyzer import CorrelationFeatureAnalyzer
from . import config


class OptimizedCorrelationAnalyzer:
    """Optimized correlation analyzer using blob storage for 13x speedup"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the optimized correlation analyzer.
        
        Args:
            db_path: Path to the database (defaults to config.DEFAULT_DB_PATH)
        """
        self.db_path = db_path or config.DEFAULT_DB_PATH
        self.blob_loader = BlobCorrelationDataLoader(self.db_path)
        self.stats_calculator = CorrelationStatisticsCalculator()
        self.pattern_classifier = CorrelationPatternClassifier(
            stability_threshold=config.PATTERN_THRESHOLDS['stability_threshold'],
            trend_slope_threshold=config.PATTERN_THRESHOLDS['trend_slope_threshold'],
            trend_r_threshold=config.PATTERN_THRESHOLDS['trend_r_threshold']
        )
        self.quality_scorer = CorrelationQualityScorer(config.QUALITY_WEIGHTS)
        self.percentiles = config.PERCENTILES
        
        # Cache for complete dataset
        self._complete_data_cache = {}
    
    def analyze(self, correlation_type: str = 'same_type', 
                output_dir: str = None,
                use_cache: bool = True) -> Dict:
        """
        Run complete analysis pipeline using optimized blob loading.
        
        Args:
            correlation_type: Type of correlation to analyze
            output_dir: Directory for output (defaults to config.DEFAULT_OUTPUT_DIR)
            use_cache: Whether to cache complete dataset in memory
            
        Returns:
            Complete analysis report dictionary
        """
        print(f"Starting optimized correlation analysis for type: {correlation_type}")
        
        # 1. Load complete dataset (much faster than individual queries)
        complete_data = self._load_complete_data(correlation_type, use_cache)
        
        # 2. Calculate statistics for all features at once
        stats_df = self._calculate_all_statistics_optimized(complete_data)
        
        # 3. Analyze patterns
        patterns, trend_results = self._analyze_patterns(stats_df)
        
        # 4. Calculate quality scores and assign tiers
        quality_scores, tiers = self._calculate_quality_scores(patterns, stats_df)
        
        # 5. Analyze data availability
        data_availability = self._analyze_data_availability(stats_df)
        
        # 6. Generate report
        report_generator = CorrelationReportGenerator(output_dir or config.DEFAULT_OUTPUT_DIR)
        report = report_generator.generate_summary(
            correlation_type=correlation_type,
            patterns=patterns,
            quality_scores=quality_scores,
            tiers=tiers,
            stats_df=stats_df,
            data_availability=data_availability,
            percentiles=self.percentiles
        )
        
        # 7. Save report and create visualizations
        report_generator.save_report(report, format='json')
        report_generator.save_report(report, format='markdown')
        report_generator.create_visualizations(report)
        
        print(f"Analysis complete. Results saved to {report_generator.output_dir}")
        
        return report
    
    def _load_complete_data(self, correlation_type: str, use_cache: bool = True) -> pd.DataFrame:
        """Load complete correlation dataset with optional caching"""
        
        if use_cache and correlation_type in self._complete_data_cache:
            print(f"Using cached data for {correlation_type}")
            return self._complete_data_cache[correlation_type]
        
        # Load from blob storage
        complete_data = self.blob_loader.load_complete_correlation_data(correlation_type)
        
        if use_cache:
            self._complete_data_cache[correlation_type] = complete_data
            print(f"Cached complete dataset for {correlation_type}")
        
        return complete_data
    
    def _calculate_all_statistics_optimized(self, complete_data: pd.DataFrame) -> pd.DataFrame:
        """Calculate statistics for all features using vectorized operations"""
        print("Calculating feature statistics (optimized)...")
        
        # Group by feature and percentile for vectorized calculations
        grouped = complete_data.groupby(['feature_name', 'percentile'])['correlation_value']
        
        # Calculate all statistics at once
        stats_agg = grouped.agg([
            'count', 'mean', 'std', 'median', 'min', 'max',
            lambda x: x.quantile(0.25),
            lambda x: x.quantile(0.75),
            lambda x: x.skew(),
            lambda x: x.kurtosis()
        ]).reset_index()
        
        # Rename columns
        stats_agg.columns = [
            'feature_name', 'percentile', 'sample_size', 'mean_correlation',
            'std_correlation', 'median_correlation', 'min_correlation', 
            'max_correlation', 'percentile_25', 'percentile_75', 'skewness', 'kurtosis'
        ]
        
        # Calculate IQR
        stats_agg['iqr'] = stats_agg['percentile_75'] - stats_agg['percentile_25']
        
        # Add correlation type and other required fields
        stats_agg['correlation_type'] = complete_data['correlation_type'].iloc[0]
        stats_agg['null_count'] = 0  # We filtered out nulls during blob loading
        stats_agg['null_percentage'] = 0.0
        
        print(f"✓ Calculated statistics for {len(stats_agg)} feature-percentile combinations")
        
        return stats_agg
    
    def _analyze_patterns(self, stats_df: pd.DataFrame) -> Tuple[Dict, Dict]:
        """Analyze patterns in feature behavior across percentiles"""
        print("Analyzing correlation patterns...")
        
        patterns = {}
        trend_results = {}
        
        for feature in stats_df['feature_name'].unique():
            feature_stats = stats_df[stats_df['feature_name'] == feature].sort_values('percentile')
            
            if len(feature_stats) < 4:  # Need at least 4 percentiles
                continue
            
            # Calculate trend
            percentiles = feature_stats['percentile'].values
            mean_corrs = feature_stats['mean_correlation'].values
            trend = self.stats_calculator.calculate_trend(percentiles, mean_corrs)
            
            # Calculate stability metrics
            stability_metrics = self.stats_calculator.calculate_stability_metrics(feature_stats)
            
            # Find optimal percentile
            optimal_percentile, optimal_strength = self.stats_calculator.find_optimal_percentile(feature_stats)
            
            # Store results
            feature_pattern = {
                'trend_slope': trend['slope'],
                'trend_r2': trend['r_squared'],
                'trend_p_value': trend['p_value'],
                'correlation_stability': stability_metrics['correlation_stability'],
                'optimal_percentile': optimal_percentile,
                'optimal_strength': optimal_strength,
                'avg_null_percentage': 0.0,  # We filtered nulls
                'percentile_coverage': len(feature_stats)
            }
            
            # Store for pattern classification
            trend_results[feature] = {
                'slope': trend['slope'],
                'r_value': trend['r_value'],
                'correlation_stability': stability_metrics['correlation_stability']
            }
            
            patterns[feature] = feature_pattern
        
        # Classify patterns
        pattern_classifications = self.pattern_classifier.analyze_all_patterns(stats_df, trend_results)
        
        # Merge pattern classifications with pattern data
        for feature, classification in pattern_classifications.items():
            if feature in patterns:
                patterns[feature].update(classification)
        
        print(f"Analyzed patterns for {len(patterns)} features")
        
        return patterns, trend_results
    
    def _calculate_quality_scores(self, patterns: Dict, 
                                stats_df: pd.DataFrame) -> Tuple[Dict, Dict]:
        """Calculate quality scores and assign tiers"""
        print("Calculating quality scores...")
        
        # Get null statistics for each feature (should be 0 since we filtered nulls)
        feature_null_stats = {feature: 0.0 for feature in patterns}
        
        # Score all features
        quality_scores = self.quality_scorer.score_all_features(patterns, feature_null_stats)
        
        # Assign tiers
        quality_scores, tiers = self.quality_scorer.assign_quality_tiers(
            quality_scores, 
            n_tiers=config.N_QUALITY_TIERS
        )
        
        print(f"Assigned {len(quality_scores)} features to {len(tiers)} quality tiers")
        
        return quality_scores, tiers
    
    def _analyze_data_availability(self, stats_df: pd.DataFrame) -> Dict:
        """Analyze data availability across percentiles"""
        availability = {}
        
        for percentile in self.percentiles:
            p_stats = stats_df[stats_df['percentile'] == percentile]
            
            availability[f'percentile_{percentile}'] = {
                'avg_null_percentage': 0.0,  # We filtered nulls
                'features_with_data': len(p_stats),
                'features_mostly_null': 0,
                'avg_sample_size': float(p_stats['sample_size'].mean())
            }
        
        return availability
    
    def analyze_by_competition_type(self, correlation_type: str = 'same_type',
                                  competition_type: str = 'gc',
                                  output_dir: str = None) -> Dict:
        """
        Analyze correlations filtered by competition type (GC, stage, one-day).
        
        Args:
            correlation_type: Type of correlation to analyze
            competition_type: Type of competition to filter by
            output_dir: Directory for output
            
        Returns:
            Analysis report for the specified competition type
        """
        print(f"Analyzing {correlation_type} correlations for {competition_type} races")
        
        # Load complete data
        complete_data = self._load_complete_data(correlation_type)
        
        # Filter by competition type
        filtered_data = self.blob_loader.filter_by_competition_type(complete_data, competition_type)
        
        print(f"Filtered to {len(filtered_data):,} correlation values for {competition_type} races")
        
        # Run analysis on filtered data
        if len(filtered_data) == 0:
            print(f"No data found for {competition_type} races with {correlation_type} correlations")
            return {
                'correlation_type': f"{correlation_type}_{competition_type}",
                'error': 'No data found',
                'timestamp': pd.Timestamp.now().isoformat()
            }
        
        # Calculate statistics for filtered data
        stats_df = self._calculate_all_statistics_optimized(filtered_data)
        
        # Analyze patterns
        patterns, trend_results = self._analyze_patterns(stats_df)
        
        # Calculate quality scores and assign tiers
        quality_scores, tiers = self._calculate_quality_scores(patterns, stats_df)
        
        # Analyze data availability
        data_availability = self._analyze_data_availability(stats_df)
        
        # Generate report
        report_generator = CorrelationReportGenerator(output_dir or config.DEFAULT_OUTPUT_DIR)
        report = report_generator.generate_summary(
            correlation_type=f"{correlation_type}_{competition_type}",
            patterns=patterns,
            quality_scores=quality_scores,
            tiers=tiers,
            stats_df=stats_df,
            data_availability=data_availability,
            percentiles=self.percentiles
        )
        
        # Save report and create visualizations
        report_generator.save_report(report, format='json')
        report_generator.save_report(report, format='markdown')
        report_generator.create_visualizations(report)
        
        print(f"Analysis complete. Results saved to {report_generator.output_dir}")
        
        return report
    
    def close(self):
        """Close database connection"""
        self.blob_loader.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience function for quick analysis
def analyze_correlations_optimized(correlation_type: str = 'same_type', 
                                 db_path: str = None,
                                 output_dir: str = None,
                                 use_new_analyzer: bool = True) -> Dict:
    """
    Quick function to run optimized correlation analysis.
    
    Args:
        correlation_type: Type of correlation to analyze
        db_path: Path to database
        output_dir: Output directory
        use_new_analyzer: Whether to use the new aligned analyzer
        
    Returns:
        Analysis report dictionary
    """
    if use_new_analyzer:
        # Use the new analyzer aligned with race feature N approach
        with CorrelationFeatureAnalyzer(db_path) as analyzer:
            return analyzer.analyze_single_correlation_type(correlation_type)
    else:
        # Use the original analyzer for backward compatibility
        with OptimizedCorrelationAnalyzer(db_path) as analyzer:
            return analyzer.analyze(correlation_type, output_dir)