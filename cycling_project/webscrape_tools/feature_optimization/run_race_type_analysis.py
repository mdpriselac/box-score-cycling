#!/usr/bin/env python3

import argparse
import sys
import warnings
from pathlib import Path
from datetime import datetime

from race_feature_n_analysis.race_type_analyzer import RaceTypeAnalyzer

# Suppress sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")


def main():
    parser = argparse.ArgumentParser(description='Analyze race features by race type across different N percentile thresholds')
    parser.add_argument('--db-path', type=str, default='../database/database/cycling_races.db',
                       help='Path to the SQLite database')
    parser.add_argument('--output-dir', type=str, default='./race_type_analysis_results',
                       help='Directory to save analysis results')
    parser.add_argument('--race-types', type=str, nargs='+', 
                       choices=['gc', 'stage', 'one_day', 'stage_one_day', 'all_types'],
                       default=['gc', 'stage', 'one_day', 'stage_one_day', 'all_types'],
                       help='Race types to analyze')
    
    args = parser.parse_args()
    
    # Check if database exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Initialize analyzer
    print(f"Initializing analyzer with database: {db_path}")
    analyzer = RaceTypeAnalyzer(str(db_path))
    
    # Show available race types in database
    print("\nChecking race type availability...")
    import sqlite3
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute("SELECT DISTINCT competition_type, COUNT(*) as count FROM race_features_50 GROUP BY competition_type ORDER BY count DESC")
        available_types = cursor.fetchall()
        
    print("Available race types in database:")
    for race_type, count in available_types:
        print(f"  - {race_type}: {count} races")
    
    # Filter to only analyze requested and available race types
    requested_types = set(args.race_types)
    
    # Check if requested race types make sense
    available_type_names = {row[0] for row in available_types}
    for race_type in requested_types:
        if race_type not in ['all_types', 'stage_one_day']:  # These are special cases
            if race_type not in available_type_names:
                print(f"Warning: Race type '{race_type}' not found in database")
    
    try:
        if len(requested_types) == 1:
            # Single race type analysis
            race_type = list(requested_types)[0]
            print(f"\n{'='*60}")
            print(f"Running Single Race Type Analysis: {race_type}")
            print(f"{'='*60}")
            
            results = analyzer.analyze_single_race_type(race_type)
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            json_path = output_dir / f"race_analysis_{race_type}_{timestamp}.json"
            analyzer._save_results(results, json_path)
            print(f"\nDetailed results saved to: {json_path}")
            
            report = analyzer._generate_summary_report(results)
            report_path = output_dir / f"race_analysis_{race_type}_report_{timestamp}.md"
            with open(report_path, 'w') as f:
                f.write(report)
            print(f"Summary report saved to: {report_path}")
            
            # Print summary to console
            print("\n" + "="*60)
            print("ANALYSIS SUMMARY")
            print("="*60)
            print(report)
            
        else:
            # Multi-race type analysis
            print(f"\n{'='*60}")
            print(f"Running Multi-Race Type Analysis")
            print(f"Race types: {', '.join(requested_types)}")
            print(f"{'='*60}")
            
            # Temporarily filter analyzer's race type configs to only requested types
            original_configs = analyzer.race_type_configs.copy()
            analyzer.race_type_configs = {k: v for k, v in original_configs.items() if k in requested_types}
            
            all_results = analyzer.analyze_all_race_types(str(output_dir))
            
            # Restore original configs
            analyzer.race_type_configs = original_configs
            
            print(f"\n{'='*60}")
            print("MULTI-RACE TYPE ANALYSIS COMPLETED")
            print(f"{'='*60}")
            print(f"Results saved to: {output_dir.absolute()}")
            print(f"Race types analyzed: {list(all_results.keys())}")
        
    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()