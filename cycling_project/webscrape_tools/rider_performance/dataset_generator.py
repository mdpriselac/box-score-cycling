"""
Integration module for generating training datasets for the global rider performance models.

This module uses FeatureBuilder to create datasets for the two global models:
1. GC Model Dataset: Uses race_features_70 and is trained on GC races
2. Stage/One-day Model Dataset: Uses race_features_40 and is trained on Stage/One-day races

Each dataset includes:
- Competition type specific race features
- Unified race kind features  
- Rider experience features
- Both UCI point target variables
"""

import pandas as pd
import sqlite3
from typing import Dict, Tuple, Optional, List
from datetime import datetime
import numpy as np
import os

from feature_builder import FeatureBuilder


class DatasetGenerator:
    """Generates training datasets for the global rider performance models."""
    
    def __init__(self, db_path: str):
        """
        Initialize the dataset generator.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.feature_builder = FeatureBuilder(db_path)
    
    def generate_datasets(self, 
                         cutoff_date: str,
                         min_results: int = 5,
                         min_uci_points: int = 0,
                         target_variable: str = 'uci_points_actual') -> Dict[str, pd.DataFrame]:
        """
        Generate both training datasets for the global models.
        
        Args:
            cutoff_date: Date cutoff in 'YYYY-MM-DD' format
            min_results: Minimum number of results required for a rider to be included
            min_uci_points: Minimum UCI points threshold for filtering low-performing results
            target_variable: Target variable ('uci_points_actual' or 'uci_points_proportional')
            
        Returns:
            Dictionary with 'gc_dataset' and 'stage_one_day_dataset' keys
        """
        print(f"Generating datasets with cutoff date: {cutoff_date}")
        print(f"Minimum results per rider: {min_results}")
        print(f"Target variable: {target_variable}")
        
        # Get all rider-competition pairs up to cutoff date
        pairs = self._get_rider_competition_pairs(cutoff_date, min_results)
        
        if not pairs:
            return {'gc_dataset': pd.DataFrame(), 'stage_one_day_dataset': pd.DataFrame()}
        
        print(f"Found {len(pairs)} rider-competition pairs to process")
        
        # Build features for all pairs using FeatureBuilder
        print("Building features for all pairs...")
        dataset = self.feature_builder.build_bulk_dataset(pairs, cutoff_date)
        
        if dataset.empty:
            return {'gc_dataset': pd.DataFrame(), 'stage_one_day_dataset': pd.DataFrame()}
        
        print(f"Built dataset with {len(dataset)} results")
        
        # Apply UCI points filtering if specified
        if min_uci_points > 0:
            print(f"Filtering results with < {min_uci_points} {target_variable}...")
            dataset = dataset[dataset[target_variable] >= min_uci_points]
            print(f"Filtered dataset: {len(dataset)} results remain")
        
        # Split by competition type
        gc_dataset = dataset[dataset['competition_type'] == 'gc'].copy()
        stage_one_day_dataset = dataset[
            dataset['competition_type'].isin(['stage', 'one_day'])
        ].copy()
        
        print(f"Final GC dataset: {len(gc_dataset)} results")
        print(f"Final Stage/One-day dataset: {len(stage_one_day_dataset)} results")
        
        # Add target variable indicator
        gc_dataset['target_variable'] = target_variable
        stage_one_day_dataset['target_variable'] = target_variable
        
        return {
            'gc_dataset': gc_dataset,
            'stage_one_day_dataset': stage_one_day_dataset
        }
    
    def _get_rider_competition_pairs(self, cutoff_date: str, min_results: int) -> List[Tuple[int, int]]:
        """Get all rider-competition pairs that meet the criteria."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            # First, find riders who have enough results up to cutoff date
            rider_query = """
            SELECT rider_id, COUNT(*) as result_count
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date <= ?
            GROUP BY rider_id
            HAVING COUNT(*) >= ?
            """
            
            cursor = conn.cursor()
            cursor.execute(rider_query, (cutoff_date, min_results))
            qualified_riders = {row[0] for row in cursor.fetchall()}
            
            if not qualified_riders:
                return []
            
            print(f"Found {len(qualified_riders)} riders with >= {min_results} results")
            
            # Get all rider-competition pairs for qualified riders up to cutoff
            pairs_query = """
            SELECT DISTINCT rr.rider_id, rr.competition_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date <= ?
            AND rr.rider_id IN ({})
            ORDER BY rr.rider_id, c.date
            """.format(','.join('?' * len(qualified_riders)))
            
            cursor.execute(pairs_query, [cutoff_date] + list(qualified_riders))
            pairs = [(row[0], row[1]) for row in cursor.fetchall()]
            
            return pairs
            
        finally:
            conn.close()
    
    def get_feature_columns(self, dataset: pd.DataFrame, competition_type: str) -> Dict[str, List[str]]:
        """
        Get the feature columns for a specific dataset.
        
        Args:
            dataset: The dataset to analyze
            competition_type: 'gc' or 'stage_one_day'
            
        Returns:
            Dictionary with feature column names by category
        """
        if dataset.empty:
            return {
                'race_features': [],
                'race_kind_features': [],
                'experience_features': [],
                'metadata_features': [],
                'target_features': []
            }
        
        # Categorize columns
        race_features = [col for col in dataset.columns if col.startswith('rf_')]
        race_kind_features = [col for col in dataset.columns if col.startswith('rkf_')]
        experience_features = [col for col in dataset.columns 
                             if col.startswith(('prior_', 'total_prior', 'rider_age_at_race'))]
        
        metadata_features = [
            'rider_id', 'rider_name', 'competition_id', 'competition_name',
            'competition_type', 'race_name', 'race_category', 'race_year',
            'competition_date', 'place', 'target_variable'
        ]
        
        target_features = ['uci_points_actual', 'uci_points_proportional']
        
        # Filter to only existing columns
        metadata_features = [col for col in metadata_features if col in dataset.columns]
        target_features = [col for col in target_features if col in dataset.columns]
        
        return {
            'race_features': race_features,
            'race_kind_features': race_kind_features,
            'experience_features': experience_features,
            'metadata_features': metadata_features,
            'target_features': target_features
        }
    
    def get_feature_summary(self, datasets: Dict[str, pd.DataFrame]) -> Dict:
        """
        Get summary information about the generated datasets.
        
        Args:
            datasets: Dictionary containing the generated datasets
            
        Returns:
            Dictionary with summary statistics
        """
        summary = {}
        
        for dataset_name, dataset in datasets.items():
            if dataset.empty:
                summary[dataset_name] = {
                    'num_results': 0,
                    'num_riders': 0,
                    'feature_counts': {},
                    'target_stats': {}
                }
                continue
            
            # Get feature columns
            feature_cols = self.get_feature_columns(
                dataset, 
                'gc' if dataset_name == 'gc_dataset' else 'stage_one_day'
            )
            
            # Get target variable statistics
            target_stats = {}
            for target_col in ['uci_points_actual', 'uci_points_proportional']:
                if target_col in dataset.columns:
                    target_stats[target_col] = {
                        'mean': dataset[target_col].mean(),
                        'std': dataset[target_col].std(),
                        'min': dataset[target_col].min(),
                        'max': dataset[target_col].max(),
                        'zeros': (dataset[target_col] == 0).sum(),
                        'non_zeros': (dataset[target_col] > 0).sum()
                    }
            
            summary[dataset_name] = {
                'num_results': len(dataset),
                'num_riders': dataset['rider_id'].nunique() if 'rider_id' in dataset.columns else 0,
                'date_range': {
                    'start': dataset['competition_date'].min() if 'competition_date' in dataset.columns else None,
                    'end': dataset['competition_date'].max() if 'competition_date' in dataset.columns else None
                },
                'competition_types': dataset['competition_type'].value_counts().to_dict() if 'competition_type' in dataset.columns else {},
                'race_categories': dataset['race_category'].value_counts().to_dict() if 'race_category' in dataset.columns else {},
                'feature_counts': {
                    'race_features': len(feature_cols['race_features']),
                    'race_kind_features': len(feature_cols['race_kind_features']),
                    'experience_features': len(feature_cols['experience_features']),
                    'total_features': len(feature_cols['race_features']) + 
                                    len(feature_cols['race_kind_features']) + 
                                    len(feature_cols['experience_features'])
                },
                'target_stats': target_stats,
                'sample_race_features': feature_cols['race_features'][:5],
                'sample_race_kind_features': feature_cols['race_kind_features'][:5],
                'sample_experience_features': feature_cols['experience_features'][:5]
            }
        
        return summary
    
    def save_datasets(self, datasets: Dict[str, pd.DataFrame], output_dir: str = "rider_performance/datasets"):
        """
        Save the generated datasets to CSV files.
        
        Args:
            datasets: Dictionary containing the generated datasets
            output_dir: Directory to save the datasets
        """
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for dataset_name, dataset in datasets.items():
            if not dataset.empty:
                filename = f"{dataset_name}_{timestamp}.csv"
                filepath = os.path.join(output_dir, filename)
                dataset.to_csv(filepath, index=False)
                print(f"Saved {dataset_name}: {filepath} ({len(dataset)} rows)")
            else:
                print(f"Skipped empty dataset: {dataset_name}")
    
    def generate_backtest_datasets(self, 
                                  test_years: List[int] = [2022, 2023, 2024],
                                  min_results: int = 5) -> Dict[int, Dict[str, pd.DataFrame]]:
        """
        Generate datasets for backtesting on specific years.
        
        Args:
            test_years: List of years to generate test datasets for
            min_results: Minimum number of results required for a rider
            
        Returns:
            Dictionary with structure: {year: {'train_gc': df, 'train_stage_one_day': df, 
                                             'test_gc': df, 'test_stage_one_day': df}}
        """
        backtest_datasets = {}
        
        for year in test_years:
            print(f"\n{'='*50}")
            print(f"Generating backtest datasets for {year}")
            print(f"{'='*50}")
            
            # Training cutoff: end of previous year
            train_cutoff = f"{year-1}-12-31"
            
            # Get training data
            print(f"\nGenerating training data (up to {train_cutoff})...")
            train_datasets = self.generate_datasets(
                cutoff_date=train_cutoff,
                min_results=min_results,
                target_variable='uci_points_actual'
            )
            
            # For test data, we need pairs from the target year
            test_start = f"{year}-01-01"
            test_end = f"{year}-12-31"
            
            print(f"\nGenerating test data ({test_start} to {test_end})...")
            
            # Get test pairs (races in the target year for riders we've seen before)
            test_pairs = self._get_test_pairs(train_cutoff, test_start, test_end)
            
            if test_pairs:
                # Build features for test pairs using training cutoff for experience
                test_dataset = self.feature_builder.build_bulk_dataset(test_pairs, train_cutoff)
                
                if not test_dataset.empty:
                    # Split by competition type
                    gc_test = test_dataset[test_dataset['competition_type'] == 'gc']
                    stage_one_day_test = test_dataset[
                        test_dataset['competition_type'].isin(['stage', 'one_day'])
                    ]
                    
                    backtest_datasets[year] = {
                        'train_gc': train_datasets['gc_dataset'],
                        'train_stage_one_day': train_datasets['stage_one_day_dataset'],
                        'test_gc': gc_test,
                        'test_stage_one_day': stage_one_day_test
                    }
                    
                    print(f"Test GC: {len(gc_test)} results")
                    print(f"Test Stage/One-day: {len(stage_one_day_test)} results")
            else:
                print("No test pairs found")
        
        return backtest_datasets
    
    def _get_test_pairs(self, train_cutoff: str, test_start: str, test_end: str) -> List[Tuple[int, int]]:
        """Get rider-competition pairs for test period (riders must have history before train_cutoff)."""
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT DISTINCT rr.rider_id, rr.competition_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date BETWEEN ? AND ?
            AND rr.rider_id IN (
                SELECT DISTINCT rider_id
                FROM rider_results rr2
                JOIN competitions c2 ON rr2.competition_id = c2.id
                WHERE c2.date <= ?
            )
            ORDER BY c.date
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (test_start, test_end, train_cutoff))
            pairs = [(row[0], row[1]) for row in cursor.fetchall()]
            
            return pairs
            
        finally:
            conn.close()


if __name__ == "__main__":
    # Test the refactored dataset generator
    db_path = "database/database/cycling_races.db"
    generator = DatasetGenerator(db_path)
    
    # Generate datasets for a recent date
    print("="*50)
    print("GENERATING MAIN DATASETS")
    print("="*50)
    
    datasets = generator.generate_datasets(
        cutoff_date="2023-12-31",
        min_results=10,
        target_variable='uci_points_actual'
    )
    
    # Get summary
    summary = generator.get_feature_summary(datasets)
    
    print("\n" + "="*50)
    print("DATASET SUMMARY")
    print("="*50)
    
    for dataset_name, stats in summary.items():
        print(f"\n{dataset_name.upper()}:")
        print(f"  Results: {stats['num_results']:,}")
        print(f"  Riders: {stats['num_riders']:,}")
        print(f"  Date range: {stats.get('date_range', {}).get('start', 'N/A')} to {stats.get('date_range', {}).get('end', 'N/A')}")
        print(f"  Competition types: {stats.get('competition_types', {})}")
        print(f"  Race categories: {stats.get('race_categories', {})}")
        print(f"  Feature counts: {stats['feature_counts']}")
        
        if stats['target_stats']:
            print(f"  Target variable stats (uci_points_actual):")
            actual_stats = stats['target_stats'].get('uci_points_actual', {})
            print(f"    Mean: {actual_stats.get('mean', 0):.2f}")
            print(f"    Std: {actual_stats.get('std', 0):.2f}")
            print(f"    Zero points: {actual_stats.get('zeros', 0):,}")
            print(f"    Non-zero points: {actual_stats.get('non_zeros', 0):,}")
    
    # Test feature column extraction
    print("\n" + "="*50)
    print("FEATURE COLUMNS")
    print("="*50)
    
    for dataset_name, dataset in datasets.items():
        if not dataset.empty:
            feature_cols = generator.get_feature_columns(
                dataset,
                'gc' if dataset_name == 'gc_dataset' else 'stage_one_day'
            )
            print(f"\n{dataset_name}:")
            for category, cols in feature_cols.items():
                if cols:
                    print(f"  {category}: {len(cols)} columns")
                    if len(cols) <= 5:
                        print(f"    {cols}")
    
    # Save datasets
    print("\n" + "="*50)
    print("SAVING DATASETS")
    print("="*50)
    
    generator.save_datasets(datasets)
    
    # Test backtest generation with just one year
    print("\n" + "="*50)
    print("TESTING BACKTEST GENERATION")
    print("="*50)
    
    backtest_data = generator.generate_backtest_datasets(
        test_years=[2023],
        min_results=10
    )
    
    for year, year_datasets in backtest_data.items():
        print(f"\n{year} Backtest Summary:")
        for dataset_name, dataset in year_datasets.items():
            print(f"  {dataset_name}: {len(dataset)} results")