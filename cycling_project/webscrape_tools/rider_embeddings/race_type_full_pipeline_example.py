#!/usr/bin/env python3
"""
Complete pipeline example for race type correlations:
Generate → Store → Load → Feature Selection → Meta-Report

This script demonstrates the full workflow for race-type-specific analysis.
"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.race_type_pipeline_adapter import (
    RaceTypeCorrelationAdapter, 
    RaceTypeDataGenerator
)
from rider_embeddings.data_generation import ParquetStorage, CorrelationDataLoader
from rider_embeddings.performance_feature_link import RaceTypeCorrelationCalculator


def step1_generate_race_type_correlations(
    db_path: str, 
    output_dir: str = "race_type_correlation_data", 
    sample_mode: bool = True
):
    """
    Step 1: Generate race type correlation data
    """
    print("\n" + "="*60)
    print("STEP 1: GENERATING RACE TYPE CORRELATION DATA")
    print("="*60)
    
    # Initialize generator with race-type-specific thresholds
    generator = RaceTypeDataGenerator(
        db_path=db_path,
        output_dir=output_dir,
        batch_size=100,
        min_races_all=100,
        min_races_stage=50,
        min_races_one_day=15,
        min_races_gc=10
    )
    
    if sample_mode:
        # Generate sample for testing
        print("Generating sample race type correlation data...")
        generator.generate_sample(
            sample_size=5000,  # 5000 riders for demo
            feature_tables=[ 'race_features_30','race_features_40'
                'race_features_50', 'race_features_60', 
                'race_features_70', 'race_features_80', 
                'race_features_90'
            ],
            output_name="race_type_demo_sample"
        )
    else:
        # Generate full dataset
        print("Generating full race type correlation dataset...")
        print("WARNING: This may take several hours for large databases!")
        
        generator.generate_all_correlations(
            feature_tables=None,  # All percentiles
            limit=None,  # All eligible riders
            resume=True  # Enable checkpointing
        )
    
    print(f"✓ Race type correlation data generated in {output_dir}")
    return output_dir


def step2_load_and_transform_data(data_dir: str) -> list:
    """
    Step 2: Load race type correlation data and transform for analysis
    
    Note: For race type data, we need to handle the extra 'race_type' column
    """
    print("\n" + "="*60)
    print("STEP 2: LOADING AND TRANSFORMING RACE TYPE DATA")
    print("="*60)
    
    # For this example, we'll load the parquet data directly
    # and reconstruct the race type correlation format
    import pandas as pd
    import glob
    
    # Find the latest sample or batch file
    parquet_files = list(Path(data_dir).glob("*.parquet"))
    if not parquet_files:
        raise ValueError(f"No parquet files found in {data_dir}")
    
    # Load the data
    print(f"Loading from {parquet_files[0]}")
    df = pd.read_parquet(parquet_files[0])
    
    print(f"Loaded {len(df)} correlation records")
    print(f"Race types in data: {df['race_type'].unique()}")
    
    # Transform back to race type correlation format
    race_type_results = []
    
    # Group by rider_result_id
    for rider_result_id, rider_df in df.groupby('rider_result_id'):
        result = {
            'rider_result_id': int(rider_result_id),
            'feature_correlations': {},
            'metadata': {
                'n_races': {},
                'method': 'race_type_correlation',
                'calculation_date': rider_df.iloc[0]['calculation_date'],
                'warnings': []
            }
        }
        
        # Group by race_type
        for race_type, race_type_df in rider_df.groupby('race_type'):
            result['feature_correlations'][race_type] = {}
            result['metadata']['n_races'][race_type] = int(race_type_df.iloc[0]['n_races'])
            
            # Group by percentile
            for percentile, percentile_df in race_type_df.groupby('percentile'):
                correlations = {}
                for _, row in percentile_df.iterrows():
                    if pd.notna(row['correlation']):
                        correlations[row['feature']] = float(row['correlation'])
                
                if correlations:
                    result['feature_correlations'][race_type][percentile] = correlations
        
        race_type_results.append(result)
    
    print(f"Transformed into {len(race_type_results)} rider results")
    return race_type_results


def step3_run_race_type_analysis(race_type_results: list, output_dir: str = "race_type_analysis"):
    """
    Step 3: Run feature selection analysis for each race type
    """
    print("\n" + "="*60)
    print("STEP 3: RUNNING RACE TYPE FEATURE SELECTION ANALYSIS")
    print("="*60)
    
    # Initialize adapter
    adapter = RaceTypeCorrelationAdapter()
    
    # Run analysis for all race types
    all_results = adapter.run_all_race_types(
        race_type_results,
        race_types=['gc', 'stage', 'one_day', 'stage_one_day', 'all'],
        max_features=25,
        k_range=[3, 4, 5, 6, 7]
    )
    
    # Generate comprehensive meta-report
    print("\n" + "="*60)
    print("STEP 4: GENERATING META-REPORT")
    print("="*60)
    
    report_path = adapter.generate_meta_report(all_results, output_dir)
    
    return all_results, report_path


def step4_export_optimized_datasets(
    all_results: dict, 
    race_type_results: list,
    output_dir: str = "race_type_optimized_data"
):
    """
    Step 4: Export optimized datasets for each race type
    """
    print("\n" + "="*60)
    print("STEP 5: EXPORTING OPTIMIZED DATASETS")
    print("="*60)
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    adapter = RaceTypeCorrelationAdapter()
    
    for race_type, analysis_results in all_results.items():
        if 'error' not in analysis_results:
            # Get recommended features
            recommendations = analysis_results.get('recommendations', {}).get('summary', {})
            best_percentile = recommendations.get('recommended_percentile')
            best_features = recommendations.get('recommended_features', [])
            
            if best_percentile and best_features:
                print(f"\nExporting {race_type} optimized dataset...")
                print(f"  Percentile: {best_percentile}")
                print(f"  Features: {len(best_features)}")
                
                # Extract race type data
                extracted_data = adapter.extract_race_type_data(race_type_results, race_type)
                
                # Create optimized dataset
                optimized_records = []
                for result in extracted_data:
                    if best_percentile in result['feature_correlations']:
                        record = {
                            'rider_result_id': result['rider_result_id'],
                            'n_races': result['metadata']['n_races']
                        }
                        
                        # Add only recommended features
                        correlations = result['feature_correlations'][best_percentile]
                        for feature in best_features:
                            if feature in correlations:
                                record[f'corr_{feature}'] = correlations[feature]
                        
                        optimized_records.append(record)
                
                if optimized_records:
                    # Save as parquet and CSV
                    import pandas as pd
                    opt_df = pd.DataFrame(optimized_records)
                    
                    parquet_file = output_path / f"{race_type}_optimized.parquet"
                    csv_file = output_path / f"{race_type}_optimized.csv"
                    
                    opt_df.to_parquet(parquet_file, compression='snappy')
                    opt_df.to_csv(csv_file, index=False)
                    
                    # Save configuration
                    config = {
                        'race_type': race_type,
                        'percentile': best_percentile,
                        'features': best_features,
                        'n_riders': len(opt_df),
                        'export_date': datetime.now().isoformat()
                    }
                    
                    config_file = output_path / f"{race_type}_config.json"
                    with open(config_file, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    print(f"  ✓ Exported to {parquet_file.name}")
    
    print(f"\n✓ Optimized datasets exported to {output_dir}")


def main():
    """Run the complete race type pipeline."""
    print("RACE TYPE CORRELATION PIPELINE")
    print("="*80)
    
    # Configuration
    db_path = "database/database/cycling_races.db"
    
    # Check if running in sample or full mode
    mode = input("\nRun in Sample mode (S) or Full mode (F)? [S/F]: ").strip().upper()
    sample_mode = mode != 'F'
    
    if sample_mode:
        print("\n🔬 Running in SAMPLE mode (5000 riders)")
    else:
        print("\n⚠️  Running in FULL mode (this may take hours)")
        confirm = input("Are you sure? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    
    try:
        # Step 1: Generate correlations
        data_dir = step1_generate_race_type_correlations(
            db_path, 
            sample_mode=sample_mode
        )
        
        # Step 2: Load and transform data
        race_type_results = step2_load_and_transform_data(data_dir)
        
        # Step 3: Run analysis and generate meta-report
        all_results, report_path = step3_run_race_type_analysis(race_type_results)
        
        # Step 4: Export optimized datasets
        step4_export_optimized_datasets(all_results, race_type_results)
        
        print("\n" + "="*80)
        print("✅ PIPELINE COMPLETE!")
        print("="*80)
        print(f"\nKey outputs:")
        print(f"  - Race type correlation data: {data_dir}/")
        print(f"  - Analysis results and reports: race_type_analysis/")
        print(f"  - Optimized datasets: race_type_optimized_data/")
        print(f"  - Meta-report: {report_path}")
        
        # Print summary from meta-report
        print("\n📊 QUICK SUMMARY:")
        with open(report_path, 'r') as f:
            lines = f.readlines()
            in_summary = False
            for line in lines:
                if "SUMMARY OF RECOMMENDATIONS" in line:
                    in_summary = True
                elif in_summary and line.strip() == "":
                    break
                elif in_summary:
                    print(line.rstrip())
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()