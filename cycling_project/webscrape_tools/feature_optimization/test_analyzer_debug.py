#!/usr/bin/env python3
"""
Debug script for the correlation analyzer
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from correlation_feature_analysis.correlation_feature_analyzer import CorrelationFeatureAnalyzer

def main():
    print("Testing Correlation Feature Analyzer")
    print("=" * 50)
    
    try:
        # Initialize analyzer
        print("1. Initializing analyzer...")
        analyzer = CorrelationFeatureAnalyzer()
        print("✓ Analyzer initialized")
        
        # Test data loading
        print("\n2. Testing data loading...")
        complete_data = analyzer._load_complete_data('all_races')
        print(f"✓ Data loaded: {len(complete_data)} rows")
        print(f"Columns: {list(complete_data.columns)}")
        
        # Test first few rows
        print("\n3. Sample data:")
        print(complete_data.head())
        
        print("\n✓ Basic data loading test successful!")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'analyzer' in locals():
            analyzer.close()

if __name__ == "__main__":
    main()