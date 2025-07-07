"""
Test script for race kind analysis tools.

This script demonstrates the basic functionality of the race kind analysis system.
"""

import os
import sys
from race_kind_analysis import RaceKindAnalyzer
from race_kind_evaluation import RaceKindEvaluator
from cross_percentile_analysis import CrossPercentileAnalyzer

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def test_basic_analysis():
    """Test basic race kind analysis functionality."""
    print("\n" + "="*60)
    print("TESTING BASIC RACE KIND ANALYSIS")
    print("="*60)
    
    # Initialize analyzer
    analyzer = RaceKindAnalyzer(DB_PATH)
    
    # Test loading data
    print("\n1. Testing data loading...")
    try:
        data = analyzer.load_data('race_features_70', competition_type='stage')
        print(f"✓ Loaded {len(data)} stage races from 70th percentile table")
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return
    
    # Test feature preparation
    print("\n2. Testing feature preparation...")
    try:
        features = analyzer.prepare_features(scaling_method='robust')
        print(f"✓ Prepared {features.shape[1]} features for {features.shape[0]} races")
    except Exception as e:
        print(f"✗ Error preparing features: {e}")
        return
    
    # Test k-means clustering
    print("\n3. Testing k-means clustering...")
    try:
        kmeans_results = analyzer.kmeans_clustering(range(2, 6))
        print(f"✓ K-means completed. Best k={kmeans_results['best_n_clusters']}, "
              f"silhouette={kmeans_results['best_score']:.3f}")
    except Exception as e:
        print(f"✗ Error in k-means: {e}")
    
    # Test feature-based scoring
    print("\n4. Testing feature-based scoring...")
    try:
        scoring_results = analyzer.feature_based_scoring()
        print("✓ Feature-based scoring completed")
        print("  Race type distribution:")
        import pandas as pd
        type_counts = pd.Series(scoring_results['dominant_type']).value_counts()
        for race_type, count in type_counts.items():
            print(f"    - {race_type}: {count} races")
    except Exception as e:
        print(f"✗ Error in feature-based scoring: {e}")


def test_evaluation():
    """Test race kind evaluation functionality."""
    print("\n" + "="*60)
    print("TESTING RACE KIND EVALUATION")
    print("="*60)
    
    # Initialize evaluator
    evaluator = RaceKindEvaluator(DB_PATH)
    
    # Test getting available tables
    print("\n1. Testing table discovery...")
    try:
        tables = evaluator.get_available_percentile_tables()
        print(f"✓ Found {len(tables)} percentile tables: {', '.join(tables[:3])}...")
    except Exception as e:
        print(f"✗ Error getting tables: {e}")
        return
    
    # Test single percentile evaluation
    print("\n2. Testing single percentile evaluation...")
    try:
        results = evaluator.evaluate_single_percentile(
            'race_features_70',
            competition_type='stage',
            methods=['kmeans', 'feature_based'],
            verbose=False
        )
        print(f"✓ Evaluated {len(results['methods'])} methods on {results['n_races']} races")
    except Exception as e:
        print(f"✗ Error in evaluation: {e}")


def test_cross_percentile():
    """Test cross-percentile analysis functionality."""
    print("\n" + "="*60)
    print("TESTING CROSS-PERCENTILE ANALYSIS")
    print("="*60)
    
    # Initialize analyzer
    analyzer = CrossPercentileAnalyzer(DB_PATH)
    
    # Test finding common competitions
    print("\n1. Testing common competition discovery...")
    try:
        common_comps = analyzer.find_common_competitions(
            min_percentile_coverage=0.7,
            competition_type='stage'
        )
        print(f"✓ Found {len(common_comps)} competitions present in ≥70% of tables")
    except Exception as e:
        print(f"✗ Error finding common competitions: {e}")
        return
    
    # Test feature trajectories
    print("\n2. Testing feature trajectory extraction...")
    try:
        # Use a small subset for testing
        test_comps = list(common_comps)[:20] if len(common_comps) > 20 else common_comps
        trajectories = analyzer.extract_feature_trajectories(
            competition_ids=set(test_comps)
        )
        print(f"✓ Extracted trajectories for {len(trajectories['competition_id'].unique())} competitions")
    except Exception as e:
        print(f"✗ Error extracting trajectories: {e}")
        return
    
    # Test feature stability
    print("\n3. Testing feature stability analysis...")
    try:
        stability = analyzer.analyze_feature_stability()
        print("✓ Feature stability analysis completed")
        print("  Most stable features:")
        import pandas as pd
        stability_df = pd.DataFrame(stability).T.sort_values('stability_score', ascending=False)
        for feature in stability_df.head(3).index:
            print(f"    - {feature}: {stability[feature]['stability_score']:.3f}")
    except Exception as e:
        print(f"✗ Error in stability analysis: {e}")


def main():
    """Run all tests."""
    print("\nRACE KIND ANALYSIS SYSTEM TEST")
    print("==============================")
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"\n✗ Database not found at: {DB_PATH}")
        print("Please ensure the database path is correct.")
        return
    
    # Run tests
    test_basic_analysis()
    test_evaluation()
    test_cross_percentile()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
    print("\nTo run full analysis, use:")
    print("  python database/race_kinds/find_race_kinds.py --mode evaluate")


if __name__ == "__main__":
    main()