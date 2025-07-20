"""
Main correlation analyzer module that orchestrates all components.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .data_loader import CorrelationDataLoader
from .statistics_calculator import CorrelationStatisticsCalculator
from .pattern_classifier import CorrelationPatternClassifier
from .quality_scorer import CorrelationQualityScorer
from .report_generator import CorrelationReportGenerator
from . import config


class CorrelationAnalyzer:
    """Main analyzer that orchestrates all components"""
    
    def __init__(self, db_path: str = None):
        """
        Initialize the correlation analyzer.
        
        Args:
            db_path: Path to the database (defaults to config.DEFAULT_DB_PATH)
        """
        self.db_path = db_path or config.DEFAULT_DB_PATH
        self.data_loader = CorrelationDataLoader(self.db_path)
        self.stats_calculator = CorrelationStatisticsCalculator()
        self.pattern_classifier = CorrelationPatternClassifier(
            stability_threshold=config.PATTERN_THRESHOLDS['stability_threshold'],
            trend_slope_threshold=config.PATTERN_THRESHOLDS['trend_slope_threshold'],
            trend_r_threshold=config.PATTERN_THRESHOLDS['trend_r_threshold']
        )
        self.quality_scorer = CorrelationQualityScorer(config.QUALITY_WEIGHTS)
        self.percentiles = config.PERCENTILES
    
    def analyze(self, correlation_type: str = 'all_races', 
                output_dir: str = None) -> Dict:
        """
        Run complete analysis pipeline.
        
        Args:
            correlation_type: Type of correlation to analyze
            output_dir: Directory for output (defaults to config.DEFAULT_OUTPUT_DIR)
            
        Returns:
            Complete analysis report dictionary
        """
        print(f"Starting correlation analysis for type: {correlation_type}")
        
        # 1. Calculate statistics for all features
        stats_df = self._calculate_all_statistics(correlation_type)
        
        # 2. Analyze patterns
        patterns, trend_results = self._analyze_patterns(stats_df)
        
        # 3. Calculate quality scores and assign tiers
        quality_scores, tiers = self._calculate_quality_scores(patterns, stats_df)
        
        # 4. Analyze data availability
        data_availability = self._analyze_data_availability(stats_df)
        
        # 5. Generate report
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
        
        # 6. Save report and create visualizations
        report_generator.save_report(report, format='json')
        report_generator.save_report(report, format='markdown')
        report_generator.create_visualizations(report)
        
        print(f"Analysis complete. Results saved to {report_generator.output_dir}")
        
        return report
    
    def _calculate_all_statistics(self, correlation_type: str) -> pd.DataFrame:
        """Calculate statistics for all feature-percentile combinations"""
        print("Calculating feature statistics...")
        
        all_chunks = []
        
        # Load data in chunks
        for chunk in self.data_loader.load_correlation_data(correlation_type, config.CHUNK_SIZE):
            all_chunks.append(chunk)
        
        # Combine all chunks
        df = pd.concat(all_chunks, ignore_index=True)
        
        # Calculate statistics for each feature-percentile combination
        results = []
        
        for feature in df['feature_name'].unique():
            for percentile in self.percentiles:
                feature_data = df[(df['feature_name'] == feature) & 
                                (df['percentile'] == percentile)]
                
                if len(feature_data) > 0:
                    stats = self.stats_calculator.calculate_feature_stats(
                        feature, percentile, correlation_type, feature_data
                    )
                    if stats:
                        results.append(stats)
        
        stats_df = pd.DataFrame(results)
        print(f"Calculated statistics for {len(stats_df)} feature-percentile combinations")
        
        return stats_df
    
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
            
            # Calculate average null percentage
            avg_null_percentage = feature_stats['null_percentage'].mean()
            
            # Store results
            feature_pattern = {
                'trend_slope': trend['slope'],
                'trend_r2': trend['r_squared'],
                'trend_p_value': trend['p_value'],
                'correlation_stability': stability_metrics['correlation_stability'],
                'optimal_percentile': optimal_percentile,
                'optimal_strength': optimal_strength,
                'avg_null_percentage': avg_null_percentage,
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
        
        # Get null statistics for each feature
        feature_null_stats = {}
        for feature in patterns:
            feature_stats = stats_df[stats_df['feature_name'] == feature]
            feature_null_stats[feature] = feature_stats['null_percentage'].mean()
        
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
                'avg_null_percentage': float(p_stats['null_percentage'].mean()),
                'features_with_data': int(len(p_stats[p_stats['null_percentage'] < 0.5])),
                'features_mostly_null': int(len(p_stats[p_stats['null_percentage'] > 0.8])),
                'avg_sample_size': float(p_stats['sample_size'].mean())
            }
        
        return availability
    
    def analyze_all_correlation_types(self, output_dir: str = None) -> Dict[str, Dict]:
        """
        Analyze all correlation types and generate comparison.
        
        Args:
            output_dir: Directory for output
            
        Returns:
            Dictionary mapping correlation types to their reports
        """
        all_reports = {}
        
        for corr_type in config.CORRELATION_TYPES:
            print(f"\n{'='*60}")
            print(f"Analyzing {corr_type}")
            print(f"{'='*60}")
            
            report = self.analyze(corr_type, output_dir)
            all_reports[corr_type] = report
            
            # Print summary
            print(f"\nSummary for {corr_type}:")
            print(f"Total features: {report['total_features']}")
            print(f"Tier distribution: {report['tier_distribution']}")
            print(f"Top 5 features: {report['top_features']['by_overall_quality'][:5]}")
        
        return all_reports
    
    def close(self):
        """Close database connection"""
        self.data_loader.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Convenience function for quick analysis
def analyze_correlations(correlation_type: str = 'all_races', 
                        db_path: str = None,
                        output_dir: str = None) -> Dict:
    """
    Quick function to run correlation analysis.
    
    Args:
        correlation_type: Type of correlation to analyze
        db_path: Path to database
        output_dir: Output directory
        
    Returns:
        Analysis report dictionary
    """
    with CorrelationAnalyzer(db_path) as analyzer:
        return analyzer.analyze(correlation_type, output_dir)