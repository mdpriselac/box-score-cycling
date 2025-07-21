#!/usr/bin/env python3
"""
Regenerate markdown reports from existing JSON analysis files.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from correlation_feature_analysis.correlation_feature_analyzer import CorrelationFeatureAnalyzer

def regenerate_report(json_file_path: str, output_dir: str = None) -> bool:
    """
    Regenerate markdown report from JSON results.
    
    Args:
        json_file_path: Path to the JSON results file
        output_dir: Optional directory to save report (defaults to same dir as JSON)
        
    Returns:
        True if successful, False otherwise
    """
    
    json_path = Path(json_file_path)
    if not json_path.exists():
        print(f"Error: JSON file not found at {json_path}")
        return False
    
    print(f"Loading results from: {json_path}")
    
    try:
        # Load existing results
        with open(json_path, 'r') as f:
            results = json.load(f)
        
        # Create analyzer (just for report generation)
        analyzer = CorrelationFeatureAnalyzer()
        
        # Generate new report
        print("Generating markdown report...")
        report = analyzer._generate_summary_report(results)
        
        # Determine output path
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)
        else:
            output_path = json_path.parent
        
        # Create new report filename
        json_stem = json_path.stem
        if json_stem.endswith('_report'):
            report_filename = f"{json_stem}.md"
        else:
            report_filename = f"{json_stem}_report_regenerated.md"
        
        report_path = output_path / report_filename
        
        # Save report
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(f"✓ Regenerated report: {report_path}")
        
        # Show report preview
        print("\n" + "="*60)
        print("REPORT PREVIEW")
        print("="*60)
        print(report[:1000] + "..." if len(report) > 1000 else report)
        
        return True
        
    except Exception as e:
        print(f"Error regenerating report: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_json_files(results_dir: Path) -> list:
    """Find all JSON analysis files in the results directory"""
    json_files = []
    
    # Look for JSON files
    for json_file in results_dir.glob("*.json"):
        # Skip summary or comparison files
        if 'summary' not in json_file.name.lower() and 'comparison' not in json_file.name.lower():
            json_files.append(json_file)
    
    return sorted(json_files)

def main():
    parser = argparse.ArgumentParser(description='Regenerate markdown reports from JSON analysis files')
    parser.add_argument('--json-file', type=str, 
                       help='Specific JSON file to regenerate report for')
    parser.add_argument('--results-dir', type=str, default='./correlation_analysis_results',
                       help='Directory containing JSON analysis files')
    parser.add_argument('--output-dir', type=str, 
                       help='Directory to save regenerated reports (default: same as input)')
    parser.add_argument('--all', action='store_true',
                       help='Regenerate reports for all JSON files in results directory')
    
    args = parser.parse_args()
    
    if args.json_file:
        # Single file mode
        success = regenerate_report(args.json_file, args.output_dir)
        if not success:
            sys.exit(1)
            
    elif args.all:
        # Batch mode - all JSON files in results directory
        results_dir = Path(args.results_dir)
        if not results_dir.exists():
            print(f"Error: Results directory not found at {results_dir}")
            sys.exit(1)
        
        json_files = find_json_files(results_dir)
        
        if not json_files:
            print(f"No JSON analysis files found in {results_dir}")
            sys.exit(1)
        
        print(f"Found {len(json_files)} JSON files to process:")
        for json_file in json_files:
            print(f"  - {json_file.name}")
        
        success_count = 0
        for json_file in json_files:
            print(f"\n{'='*60}")
            print(f"Processing: {json_file.name}")
            print('='*60)
            
            if regenerate_report(str(json_file), args.output_dir):
                success_count += 1
            else:
                print(f"✗ Failed to regenerate report for {json_file.name}")
        
        print(f"\n{'='*60}")
        print(f"BATCH PROCESSING COMPLETE")
        print(f"{'='*60}")
        print(f"Successfully regenerated: {success_count}/{len(json_files)} reports")
        
        if success_count < len(json_files):
            sys.exit(1)
            
    else:
        print("Error: You must specify either --json-file or --all")
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()