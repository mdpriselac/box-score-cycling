#!/usr/bin/env python3
"""
Train embedding-based performance prediction models.

Usage:
    # Using optimized embeddings (default)
    python train_embedding_models.py --year 2023
    python train_embedding_models.py --year 2023 --race-type gc
    python train_embedding_models.py --year 2023 --save-models
    
    # Using full embeddings with percentile
    python train_embedding_models.py --year 2023 --use-full-embeddings --percentile race_features_90
    python train_embedding_models.py --year 2023 --race-type gc --use-full-embeddings --percentile race_features_90
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Optional
import json
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from rider_embeddings.embedding_performance_prediction.data_preparation import EmbeddingDataPreparation
from rider_embeddings.embedding_performance_prediction.embedding_model import EmbeddingPerformanceModel
from rider_embeddings.embedding_performance_prediction.model_reporter import ModelReporter


def train_single_race_type(
    race_type: str,
    test_year: int,
    prep: EmbeddingDataPreparation,
    reporter: ModelReporter,
    save_model: bool = False,
    model_dir: str = "models",
    percentile: Optional[str] = None
) -> Dict:
    """
    Train model for a single race type.
    
    Args:
        race_type: Race type to train
        test_year: Year to use for testing
        prep: Data preparation instance
        reporter: Model reporter instance
        save_model: Whether to save the trained model
        model_dir: Directory to save models
        percentile: For full embeddings, which percentile to use
        
    Returns:
        Dictionary with training results
    """
    print(f"\n{'='*60}")
    print(f"Training {race_type.upper()} Model")
    print(f"{'='*60}")
    
    try:
        # Prepare data
        print(f"\nPreparing data for {race_type}...")
        if prep.use_full_embeddings:
            print(f"Using FULL embeddings with percentile: {percentile}")
        else:
            print("Using OPTIMIZED embeddings")
        
        full_data = prep.prepare_race_type_data(race_type, percentile=percentile)
        
        # Split by year
        train_df, test_df = prep.split_by_year(full_data, test_year)
        
        # Get dataset statistics
        train_stats = prep.get_dataset_stats(train_df)
        test_stats = prep.get_dataset_stats(test_df)
        
        # Check if we have enough data
        if len(train_df) < 100:
            print(f"⚠️  Warning: Only {len(train_df)} training samples for {race_type}")
            return {
                'race_type': race_type,
                'status': 'skipped',
                'reason': f'Insufficient training data ({len(train_df)} samples)'
            }
        
        if len(test_df) < 10:
            print(f"⚠️  Warning: Only {len(test_df)} test samples for {race_type}")
            return {
                'race_type': race_type,
                'status': 'skipped',
                'reason': f'Insufficient test data ({len(test_df)} samples)'
            }
        
        # Create and train model
        model = EmbeddingPerformanceModel(race_type=race_type)
        training_info = model.train(
            train_df=train_df,
            valid_df=test_df,
            verbose=True
        )
        
        # Generate report
        report = reporter.generate_training_report(
            model=model,
            train_stats=train_stats,
            test_stats=test_stats,
            test_year=test_year,
            save_file=True
        )
        
        # Print summary
        reporter.print_training_summary(model, train_stats, test_stats)
        
        # Export feature importance
        reporter.export_feature_importance_csv(model)
        
        # Save model if requested
        if save_model:
            if prep.use_full_embeddings:
                model_name = f"{race_type}_model_{test_year}_full_{percentile.replace('race_features_', '')}"
            else:
                model_name = f"{race_type}_model_{test_year}"
            model_path = Path(model_dir) / model_name
            model_path.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(model_path))
            print(f"✅ Model saved to: {model_path}")
        
        return {
            'race_type': race_type,
            'status': 'success',
            'model_performance': training_info['performance_metrics'],
            'dataset_info': {
                'training': train_stats,
                'test': test_stats
            }
        }
        
    except Exception as e:
        print(f"❌ Error training {race_type} model: {str(e)}")
        return {
            'race_type': race_type,
            'status': 'failed',
            'error': str(e)
        }


def main():
    parser = argparse.ArgumentParser(
        description="Train embedding-based performance prediction models"
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="Year to use for testing (will train on all years before this)"
    )
    parser.add_argument(
        "--race-type",
        type=str,
        choices=['gc', 'stage', 'one_day', 'stage_one_day', 'all'],
        help="Specific race type to train (if not specified, trains all)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="database/database/cycling_races.db",
        help="Path to the cycling database"
    )
    parser.add_argument(
        "--embedding-path",
        type=str,
        default="race_type_optimized_data",
        help="Path to embedding data folder"
    )
    parser.add_argument(
        "--save-models",
        action="store_true",
        help="Save trained models to disk"
    )
    parser.add_argument(
        "--model-dir",
        type=str,
        default="models",
        help="Directory to save models"
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="reports",
        help="Directory to save reports"
    )
    parser.add_argument(
        "--use-full-embeddings",
        action="store_true",
        help="Use full embeddings instead of optimized embeddings"
    )
    parser.add_argument(
        "--percentile",
        type=str,
        help="For full embeddings, which percentile to use (e.g., race_features_90)"
    )
    parser.add_argument(
        "--full-embeddings-path",
        type=str,
        default="race_type_full_embeddings",
        help="Path to full embeddings data folder"
    )
    
    args = parser.parse_args()
    
    # Validate year
    current_year = datetime.now().year
    if args.year < 2010 or args.year > current_year:
        print(f"❌ Invalid year: {args.year}. Must be between 2010 and {current_year}")
        sys.exit(1)
    
    # Validate full embeddings arguments
    if args.use_full_embeddings and not args.percentile:
        print("❌ When using --use-full-embeddings, you must specify --percentile (e.g., race_features_90)")
        sys.exit(1)
    
    # Check if database exists
    if not Path(args.db_path).exists():
        print(f"❌ Database not found: {args.db_path}")
        sys.exit(1)
    
    # Check if embedding path exists
    if args.use_full_embeddings:
        embedding_path = Path(args.full_embeddings_path)
        if not embedding_path.exists():
            print(f"❌ Full embeddings data folder not found: {args.full_embeddings_path}")
            sys.exit(1)
    else:
        embedding_path = Path(args.embedding_path)
        if not embedding_path.exists():
            print(f"❌ Optimized embeddings data folder not found: {args.embedding_path}")
            sys.exit(1)
    
    # Initialize components
    print("Initializing data preparation and reporting components...")
    prep = EmbeddingDataPreparation(
        db_path=args.db_path,
        embedding_base_path=args.embedding_path,
        use_full_embeddings=args.use_full_embeddings,
        full_embeddings_path=args.full_embeddings_path
    )
    reporter = ModelReporter(output_dir=args.report_dir)
    
    # Determine which race types to train
    if args.race_type:
        race_types = [args.race_type]
    else:
        race_types = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
    
    print(f"\nTraining models for year {args.year}")
    print(f"Race types: {', '.join(race_types)}")
    print(f"Database: {args.db_path}")
    if args.use_full_embeddings:
        print(f"Embeddings: {args.full_embeddings_path} (FULL)")
        print(f"Percentile: {args.percentile}")
    else:
        print(f"Embeddings: {args.embedding_path} (OPTIMIZED)")
    
    # Train models
    results = {}
    for race_type in race_types:
        result = train_single_race_type(
            race_type=race_type,
            test_year=args.year,
            prep=prep,
            reporter=reporter,
            save_model=args.save_models,
            model_dir=args.model_dir,
            percentile=args.percentile
        )
        results[race_type] = result
    
    # Generate consolidated report if multiple race types
    if len(results) > 1:
        print("\nGenerating consolidated report...")
        reporter.generate_multi_race_type_report(
            results=results,
            test_year=args.year,
            save_file=True
        )
    
    # Print final summary
    print("\n" + "="*60)
    print("TRAINING SUMMARY")
    print("="*60)
    
    success_count = sum(1 for r in results.values() if r['status'] == 'success')
    failed_count = sum(1 for r in results.values() if r['status'] == 'failed')
    skipped_count = sum(1 for r in results.values() if r['status'] == 'skipped')
    
    print(f"\nTotal models: {len(results)}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"⚠️  Skipped: {skipped_count}")
    
    if failed_count > 0:
        print("\nFailed models:")
        for race_type, result in results.items():
            if result['status'] == 'failed':
                print(f"  - {race_type}: {result.get('error', 'Unknown error')}")
    
    if skipped_count > 0:
        print("\nSkipped models:")
        for race_type, result in results.items():
            if result['status'] == 'skipped':
                print(f"  - {race_type}: {result.get('reason', 'Unknown reason')}")
    
    print(f"\nReports saved to: {reporter.output_dir}/")
    if args.save_models:
        print(f"Models saved to: {args.model_dir}/")
    
    print("\n✨ Training complete!")


if __name__ == "__main__":
    main()