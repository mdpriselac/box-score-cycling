#!/usr/bin/env python3

import argparse
import sys
import warnings
from pathlib import Path
from datetime import datetime

from correlation_feature_analysis.correlation_feature_analyzer import CorrelationFeatureAnalyzer

# Suppress sklearn warnings
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")


def main():
    parser = argparse.ArgumentParser(description='Analyze correlation features by competition type (race-type-first approach)')
    parser.add_argument('--db-path', type=str, default='../database/database/cycling_races.db',
                       help='Path to the SQLite database')
    parser.add_argument('--output-dir', type=str, default='./correlation_analysis_results',
                       help='Directory to save analysis results')
    parser.add_argument('--competition-types', type=str, nargs='+',
                       choices=['gc', 'stage', 'one_day'],
                       default=['gc', 'stage', 'one_day'],
                       help='Competition types to analyze (race-type-first approach)')
    
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
    analyzer = CorrelationFeatureAnalyzer(str(db_path))
    
    # Show available correlation types in database
    print("\nChecking correlation type availability...")
    import sqlite3
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("""
                SELECT DISTINCT correlation_type, COUNT(*) as count 
                FROM rider_correlations_blob 
                GROUP BY correlation_type 
                ORDER BY correlation_type
            """)
            available_data = cursor.fetchall()
            
        print("Available correlation data in database:")
        for corr_type, count in available_data:
            print(f"  - {corr_type}: {count:,} total entries")
    except Exception as e:
        print(f"Could not check database: {e}")
        print("Proceeding with analysis...")
    
    # Filter to only analyze requested competition types
    requested_types = set(args.competition_types)
    
    # Show what correlations will be analyzed for each competition type
    print(f"\nCompetition type analysis plan:")
    for comp_type in requested_types:
        relevant_correlations = analyzer.competition_type_configs[comp_type]['relevant_correlations']
        description = analyzer.competition_type_configs[comp_type]['description']
        print(f"  - {comp_type} ({description}): {relevant_correlations}")
    
    try:
        if len(requested_types) == 1:
            # Single competition type analysis
            competition_type = list(requested_types)[0]
            print(f"\n{'='*60}")
            print(f"Running Single Competition Type Analysis: {competition_type}")
            print(f"{'='*60}")
            
            results = analyzer.analyze_single_competition_type(competition_type)
            
            # Save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            json_path = output_dir / f"correlation_analysis_{competition_type}_{timestamp}.json"
            analyzer._save_results(results, output_dir, competition_type)
            print(f"\nDetailed results saved")
            
            report = analyzer._generate_summary_report(results)
            report_path = output_dir / f"correlation_analysis_{competition_type}_report_{timestamp}.md"
            with open(report_path, 'w') as f:
                f.write(report)
            print(f"Summary report saved to: {report_path}")
            
            # Print summary to console
            print("\n" + "="*60)
            print("ANALYSIS SUMMARY")
            print("="*60)
            print(report[:1000] + "..." if len(report) > 1000 else report)
            
        else:
            # Multi-competition type analysis
            print(f"\n{'='*60}")
            print(f"Running Multi-Competition Type Analysis")
            print(f"Competition types: {', '.join(requested_types)}")
            print(f"{'='*60}")
            
            all_results = analyzer.analyze_all_competition_types(
                str(output_dir), 
                competition_types=list(requested_types)
            )
            
            print(f"\n{'='*60}")
            print("MULTI-COMPETITION TYPE ANALYSIS COMPLETED")
            print(f"{'='*60}")
            print(f"Results saved to: {output_dir.absolute()}")
            print(f"Competition types analyzed: {list(requested_types)}")
            for competition_type in requested_types:
                relevant_correlations = analyzer.competition_type_configs[competition_type]['relevant_correlations']
                print(f"  - {competition_type}: {relevant_correlations}")
        
    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()