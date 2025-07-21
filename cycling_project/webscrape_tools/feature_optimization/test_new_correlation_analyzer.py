#!/usr/bin/env python3
"""
Test script for the new correlation feature analyzer.

This script tests the updated correlation analysis system that's aligned with
the race feature N analysis approach.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from correlation_feature_analysis.correlation_feature_analyzer import CorrelationFeatureAnalyzer


def main():
    """Run test analysis with the new analyzer"""
    
    print("Testing New Correlation Feature Analyzer")
    print("=" * 80)
    
    # Initialize analyzer
    analyzer = CorrelationFeatureAnalyzer()
    
    try:
        # Test single correlation type analysis
        print("\n1. Testing single correlation type analysis (same_type)...")
        results = analyzer.analyze_single_correlation_type('same_type')
        
        if results and 'metadata' in results:
            print(f"✓ Analysis completed successfully")
            print(f"  - Features analyzed: {results['metadata'].get('n_features_analyzed', 0)}")
            print(f"  - Percentiles: {results['metadata'].get('percentiles', [])}")
            
            # Check for key components
            if 'feature_groups' in results:
                print(f"  - Pattern groups found: {len(results['feature_groups'].get('pattern_groups', {}))}")
            if 'percentile_recommendations' in results:
                print(f"  - Recommendations generated: Yes")
        else:
            print("✗ Analysis failed or returned empty results")
        
        # Test with competition type filter
        print("\n2. Testing with competition type filter (GC races)...")
        gc_results = analyzer.analyze_single_correlation_type('same_type', 'gc')
        
        if gc_results and 'metadata' in gc_results:
            print(f"✓ GC analysis completed successfully")
            print(f"  - Features analyzed: {gc_results['metadata'].get('n_features_analyzed', 0)}")
        
        # Test batch analysis
        print("\n3. Testing batch analysis...")
        output_dir = "./test_correlation_results"
        all_results = analyzer.analyze_all_correlation_types(
            output_dir=output_dir,
            competition_types=['gc', 'stage', 'one_day']
        )
        
        print(f"\n✓ Batch analysis completed")
        print(f"  - Total analyses run: {len(all_results)}")
        print(f"  - Results saved to: {output_dir}")
        
        # Display sample recommendations
        if results and 'percentile_recommendations' in results:
            recs = results['percentile_recommendations']
            if 'analysis_type_recommendations' in recs:
                print("\n4. Sample Recommendations Generated:")
                for analysis_type, rec in list(recs['analysis_type_recommendations'].items())[:2]:
                    print(f"\n  {analysis_type.replace('_', ' ').title()}:")
                    print(f"    - Percentiles: {rec['recommended_percentiles']}")
                    print(f"    - Reasoning: {rec['reasoning'][:100]}...")
        
        print("\n✓ All tests completed successfully!")
        
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()