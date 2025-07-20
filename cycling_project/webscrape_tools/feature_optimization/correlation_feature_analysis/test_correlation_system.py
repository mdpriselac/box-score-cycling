"""
Test suite for correlation feature analysis system.

Run this script to verify all components work correctly.
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

# Add the parent directory to path for imports
current_dir = Path(__file__).parent
sys.path.append(str(current_dir.parent.parent))

from correlation_feature_analysis.data_loader import CorrelationDataLoader
from correlation_feature_analysis.statistics_calculator import CorrelationStatisticsCalculator
from correlation_feature_analysis.pattern_classifier import CorrelationPatternClassifier
from correlation_feature_analysis.quality_scorer import CorrelationQualityScorer
from correlation_feature_analysis.correlation_analyzer import CorrelationAnalyzer
from correlation_feature_analysis import config


def test_database_connection():
    """Test basic connectivity and data availability"""
    print("Testing database connection...")
    
    try:
        with CorrelationDataLoader(config.DEFAULT_DB_PATH) as loader:
            # Test basic queries
            features = loader.get_feature_list()
            percentiles = loader.get_available_percentiles()
            correlation_types = loader.get_correlation_types()
            
            print(f"✓ Found {len(features)} features")
            print(f"✓ Found {len(percentiles)} percentiles: {percentiles}")
            print(f"✓ Found {len(correlation_types)} correlation types: {correlation_types}")
            
            # Test data quality summary
            quality_summary = loader.get_data_quality_summary('all_races')
            print(f"✓ Data quality summary: {len(quality_summary)} rows")
            
            # Verify expected values
            assert len(features) == 37, f"Expected 37 features, got {len(features)}"
            assert len(percentiles) == 8, f"Expected 8 percentiles, got {len(percentiles)}"
            assert 'all_races' in correlation_types, "Missing 'all_races' correlation type"
            
            print("✓ Database connection test passed")
            return True
            
    except Exception as e:
        print(f"✗ Database connection test failed: {e}")
        return False


def test_statistics_calculator():
    """Test statistics calculation functionality"""
    print("\nTesting statistics calculator...")
    
    try:
        # Create sample data
        sample_data = pd.DataFrame({
            'correlation_value': np.random.normal(0.2, 0.1, 1000),
            'total_count': [1000] * 1000,
            'null_count': [50] * 1000
        })
        
        calc = CorrelationStatisticsCalculator()
        
        # Test feature stats calculation
        stats = calc.calculate_feature_stats('test_feature', 50, 'all_races', sample_data)
        assert stats is not None, "Stats calculation returned None"
        assert 'mean_correlation' in stats, "Missing mean_correlation"
        assert 'sample_size' in stats, "Missing sample_size"
        assert stats['sample_size'] == 1000, f"Expected 1000 samples, got {stats['sample_size']}"
        
        # Test trend calculation
        percentiles = np.array([30, 40, 50, 60, 70, 80, 90, 100])
        values = np.array([0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45])
        trend = calc.calculate_trend(percentiles, values)
        
        assert 'slope' in trend, "Missing slope in trend"
        assert 'r_squared' in trend, "Missing r_squared in trend"
        assert trend['slope'] > 0, "Expected positive slope"
        
        print("✓ Statistics calculator test passed")
        return True
        
    except Exception as e:
        print(f"✗ Statistics calculator test failed: {e}")
        return False


def test_pattern_classifier():
    """Test pattern classification logic"""
    print("\nTesting pattern classifier...")
    
    try:
        classifier = CorrelationPatternClassifier()
        
        # Test stable pattern
        stable_corrs = np.array([0.2, 0.21, 0.19, 0.20, 0.21, 0.20, 0.19, 0.20])
        pattern = classifier.classify_pattern(0.0001, 0.1, stable_corrs, 0.95)
        assert pattern in ['highly_stable', 'stable'], f"Expected stable pattern, got {pattern}"
        
        # Test elite-focused pattern
        elite_corrs = np.array([0.5, 0.4, 0.3, 0.2, 0.15, 0.1, 0.05, 0.02])
        pattern = classifier.classify_pattern(-0.05, -0.9, elite_corrs, 0.7)
        assert pattern == 'elite_focused', f"Expected elite_focused, got {pattern}"
        
        # Test mass-inclusive pattern
        mass_corrs = np.array([0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.55, 0.6])
        pattern = classifier.classify_pattern(0.05, 0.9, mass_corrs, 0.7)
        assert pattern == 'mass_inclusive', f"Expected mass_inclusive, got {pattern}"
        
        print("✓ Pattern classifier test passed")
        return True
        
    except Exception as e:
        print(f"✗ Pattern classifier test failed: {e}")
        return False


def test_quality_scorer():
    """Test quality scoring functionality"""
    print("\nTesting quality scorer...")
    
    try:
        scorer = CorrelationQualityScorer()
        
        # Test single feature scoring
        feature_pattern = {
            'optimal_strength': 0.4,
            'correlation_stability': 0.8,
            'pattern_classification': 'stable'
        }
        
        score = scorer.calculate_quality_score(feature_pattern, 0.1)
        assert 'overall_score' in score, "Missing overall_score"
        assert 'strength_score' in score, "Missing strength_score"
        assert 0 <= score['overall_score'] <= 1, f"Score out of range: {score['overall_score']}"
        
        # Test tier assignment
        patterns = {
            'feature_a': {'optimal_strength': 0.8, 'correlation_stability': 0.9, 'pattern_classification': 'stable'},
            'feature_b': {'optimal_strength': 0.4, 'correlation_stability': 0.6, 'pattern_classification': 'stable'},
            'feature_c': {'optimal_strength': 0.1, 'correlation_stability': 0.3, 'pattern_classification': 'variable'}
        }
        
        null_stats = {'feature_a': 0.1, 'feature_b': 0.2, 'feature_c': 0.5}
        quality_scores = scorer.score_all_features(patterns, null_stats)
        quality_scores, tiers = scorer.assign_quality_tiers(quality_scores)
        
        assert len(tiers) == 3, f"Expected 3 tiers, got {len(tiers)}"
        assert 'feature_a' in tiers['tier_1_high_quality'], "feature_a should be in tier 1"
        
        print("✓ Quality scorer test passed")
        return True
        
    except Exception as e:
        print(f"✗ Quality scorer test failed: {e}")
        return False


def test_single_feature_analysis():
    """Test analysis for a single feature"""
    print("\nTesting single feature analysis...")
    
    try:
        with CorrelationDataLoader(config.DEFAULT_DB_PATH) as loader:
            # Get data for one feature
            chunk_gen = loader.load_correlation_data('all_races', chunk_size=50000)
            first_chunk = next(chunk_gen)
            
            # Filter to one feature
            test_feature = 'abandon_ratio'
            feature_data = first_chunk[first_chunk['feature_name'] == test_feature]
            
            if len(feature_data) == 0:
                print("⚠ No data found for abandon_ratio, trying another feature")
                test_feature = first_chunk['feature_name'].iloc[0]
                feature_data = first_chunk[first_chunk['feature_name'] == test_feature]
            
            # Check we have data for multiple percentiles
            percentiles_found = feature_data['percentile'].unique()
            assert len(percentiles_found) >= 4, f"Expected at least 4 percentiles, found {len(percentiles_found)}"
            
            # Test statistics calculation
            calc = CorrelationStatisticsCalculator()
            
            for percentile in percentiles_found[:3]:  # Test first 3 percentiles
                p_data = feature_data[feature_data['percentile'] == percentile]
                stats = calc.calculate_feature_stats(test_feature, percentile, 'all_races', p_data)
                
                if stats:
                    assert abs(stats['mean_correlation']) <= 1.0, "Correlation out of range"
                    assert stats['sample_size'] > 0, "No samples found"
            
            print(f"✓ Single feature analysis test passed for {test_feature}")
            return True
            
    except Exception as e:
        print(f"✗ Single feature analysis test failed: {e}")
        return False


def test_full_pipeline():
    """Test the complete analysis pipeline on a small subset"""
    print("\nTesting full analysis pipeline...")
    
    try:
        # Run analysis on the smallest correlation type first
        analyzer = CorrelationAnalyzer(config.DEFAULT_DB_PATH)
        
        # Use a small test by limiting to specific features if possible
        print("Running analysis on 'same_type' correlation type...")
        
        # This will run the full pipeline
        report = analyzer.analyze('same_type', 'test_output')
        
        # Verify report structure
        required_keys = [
            'analysis_date', 'correlation_type', 'total_features',
            'pattern_distribution', 'tier_distribution', 'top_features',
            'feature_details', 'quality_tiers', 'recommendations'
        ]
        
        for key in required_keys:
            assert key in report, f"Missing required key: {key}"
        
        # Check tier distribution adds up
        tier_sum = sum(report['tier_distribution'].values())
        assert tier_sum == report['total_features'], "Tier counts don't match total features"
        
        # Verify output files exist
        output_path = Path('test_output')
        assert output_path.exists(), "Output directory not created"
        
        json_file = output_path / f"correlation_quality_report_{report['correlation_type']}.json"
        assert json_file.exists(), "JSON report not created"
        
        print(f"✓ Full pipeline test passed - analyzed {report['total_features']} features")
        print(f"✓ Report saved to {json_file}")
        
        analyzer.close()
        return True
        
    except Exception as e:
        print(f"✗ Full pipeline test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("Running Correlation Feature Analysis Test Suite")
    print("=" * 60)
    
    tests = [
        test_database_connection,
        test_statistics_calculator,
        test_pattern_classifier,
        test_quality_scorer,
        test_single_feature_analysis,
        test_full_pipeline
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The correlation analysis system is ready to use.")
        return True
    else:
        print("❌ Some tests failed. Please check the issues above.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)