import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
from pathlib import Path
import json
import glob
from datetime import datetime
import pyarrow.parquet as pq
import pyarrow.dataset as ds
from tqdm import tqdm


class CorrelationDataLoader:
    """
    Load correlation data from parquet files for feature selection analysis.
    
    Provides efficient loading and transformation to match the expected
    format for feature selection pipeline.
    """
    
    def __init__(self, data_dir: str = "correlation_data"):
        """
        Initialize data loader.
        
        Args:
            data_dir: Directory containing parquet files
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise ValueError(f"Data directory {data_dir} does not exist")
        
        # Check for partitioned vs batch files
        self.partitioned_path = self.data_dir / "partitioned"
        self.use_partitioned = self.partitioned_path.exists()
        
    def load_for_feature_selection(
        self,
        percentiles: Optional[List[str]] = None,
        rider_result_ids: Optional[List[int]] = None,
        min_races: int = 5,
        sample_size: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Load correlation data in format expected by feature selection pipeline.
        
        Args:
            percentiles: Specific percentiles to load (None = all)
            rider_result_ids: Specific rider results to load (None = all)
            min_races: Minimum number of races required
            sample_size: Optional random sample size
            
        Returns:
            List of correlation results matching CorrelationCalculator output format
        """
        print("Loading correlation data from parquet files...")
        
        # Load raw data
        df = self._load_raw_data(percentiles, rider_result_ids, min_races)
        
        if sample_size and len(df) > sample_size:
            # Sample by unique rider_result_id
            unique_riders = df['rider_result_id'].unique()
            if len(unique_riders) > sample_size:
                sampled_riders = np.random.choice(unique_riders, sample_size, replace=False)
                df = df[df['rider_result_id'].isin(sampled_riders)]
        
        # Transform to expected format
        correlation_results = self._transform_to_correlation_format(df)
        
        print(f"Loaded {len(correlation_results)} rider results")
        
        return correlation_results
    
    def _load_raw_data(
        self,
        percentiles: Optional[List[str]] = None,
        rider_result_ids: Optional[List[int]] = None,
        min_races: int = 5
    ) -> pd.DataFrame:
        """Load raw correlation data from parquet files."""
        if self.use_partitioned:
            # Use partitioned dataset for efficient loading
            dataset = ds.dataset(self.partitioned_path, format='parquet')
            
            # Build filters
            filters = []
            if percentiles:
                filters.append(ds.field('percentile').isin(percentiles))
            if rider_result_ids:
                filters.append(ds.field('rider_result_id').isin(rider_result_ids))
            if min_races:
                filters.append(ds.field('n_races') >= min_races)
            
            # Combine filters
            if filters:
                combined_filter = filters[0]
                for f in filters[1:]:
                    combined_filter = combined_filter & f
                table = dataset.to_table(filter=combined_filter)
            else:
                table = dataset.to_table()
            
            df = table.to_pandas()
            
        else:
            # Load from batch files
            batch_files = sorted(glob.glob(str(self.data_dir / "correlations_batch_*.parquet")))
            
            if not batch_files:
                # Try single merged file
                merged_file = self.data_dir / "merged_correlations.parquet"
                if merged_file.exists():
                    batch_files = [str(merged_file)]
                else:
                    # Try sample files
                    sample_files = list(self.data_dir.glob("*sample*.parquet"))
                    if sample_files:
                        batch_files = [str(sample_files[0])]
                    else:
                        # Try any parquet file
                        all_parquet = list(self.data_dir.glob("*.parquet"))
                        if all_parquet:
                            batch_files = [str(all_parquet[0])]
                        else:
                            raise ValueError("No parquet files found to load")
            
            dfs = []
            for batch_file in tqdm(batch_files, desc="Loading batches"):
                batch_df = pd.read_parquet(batch_file)
                
                # Apply filters
                if percentiles:
                    batch_df = batch_df[batch_df['percentile'].isin(percentiles)]
                if rider_result_ids:
                    batch_df = batch_df[batch_df['rider_result_id'].isin(rider_result_ids)]
                if min_races:
                    batch_df = batch_df[batch_df['n_races'] >= min_races]
                
                dfs.append(batch_df)
            
            df = pd.concat(dfs, ignore_index=True)
        
        return df
    
    def _transform_to_correlation_format(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Transform flat parquet data to correlation calculator output format.
        
        Expected format:
        {
            'rider_result_id': int,
            'feature_correlations': {
                'race_features_100': {
                    'feature1': correlation_value,
                    'feature2': correlation_value,
                    ...
                },
                ...
            },
            'metadata': {
                'n_races': int,
                'method': 'correlation',
                'calculation_date': datetime,
                'warnings': []
            }
        }
        """
        # Group by rider_result_id
        grouped = df.groupby('rider_result_id')
        
        correlation_results = []
        
        for rider_result_id, group in grouped:
            # Initialize result structure
            result = {
                'rider_result_id': int(rider_result_id),
                'feature_correlations': {},
                'metadata': {
                    'n_races': int(group['n_races'].iloc[0]),
                    'method': 'correlation',
                    'calculation_date': group['calculation_date'].iloc[0] if 'calculation_date' in group.columns else datetime.now(),
                    'warnings': []
                }
            }
            
            # Group by percentile
            for percentile, percentile_group in group.groupby('percentile'):
                correlations = {}
                
                for _, row in percentile_group.iterrows():
                    feature = row['feature']
                    correlation = row['correlation']
                    
                    # Handle null correlations
                    if pd.notna(correlation):
                        correlations[feature] = float(correlation)
                    else:
                        correlations[feature] = None
                
                result['feature_correlations'][percentile] = correlations
            
            correlation_results.append(result)
        
        return correlation_results
    
    def get_available_percentiles(self) -> List[str]:
        """Get list of available percentiles in the dataset."""
        if self.use_partitioned:
            # List partition directories
            percentile_dirs = [d.name for d in self.partitioned_path.iterdir() if d.is_dir()]
            return sorted([d.split('=')[1] for d in percentile_dirs if d.startswith('percentile=')])
        else:
            # Load sample to get percentiles
            batch_files = sorted(glob.glob(str(self.data_dir / "correlations_batch_*.parquet")))
            if not batch_files:
                # Try sample files or any parquet
                sample_files = list(self.data_dir.glob("*sample*.parquet"))
                if sample_files:
                    batch_files = [sample_files[0]]
                else:
                    all_parquet = list(self.data_dir.glob("*.parquet"))
                    if all_parquet:
                        batch_files = [all_parquet[0]]
            
            if batch_files:
                sample_df = pd.read_parquet(batch_files[0], columns=['percentile'])
                return sorted(sample_df['percentile'].unique().tolist())
            else:
                return []
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary statistics about available data."""
        # Try to load metadata first
        metadata_file = self.data_dir / "generation_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # Get available percentiles
        percentiles = self.get_available_percentiles()
        
        # Sample data for statistics
        try:
            sample_df = self._load_raw_data()
            # If too large, sample it
            if len(sample_df) > 10000:
                sample_df = sample_df.sample(n=10000)
        except Exception as e:
            print(f"Warning: Could not load data for summary: {e}")
            sample_df = pd.DataFrame()
        
        if len(sample_df) > 0:
            data_statistics = {
                'unique_riders': sample_df['rider_result_id'].nunique(),
                'total_correlations': len(sample_df),
                'avg_races_per_rider': sample_df.groupby('rider_result_id')['n_races'].first().mean(),
                'null_correlation_rate': sample_df['correlation'].isna().mean()
            }
        else:
            data_statistics = {
                'unique_riders': 0,
                'total_correlations': 0,
                'avg_races_per_rider': 0,
                'null_correlation_rate': 0
            }
        
        summary = {
            'generation_metadata': metadata,
            'available_percentiles': percentiles,
            'data_statistics': data_statistics,
            'storage_format': 'partitioned' if self.use_partitioned else 'batch_files'
        }
        
        return summary
    
    def load_for_specific_analysis(
        self,
        percentile: str,
        features: Optional[List[str]] = None,
        min_correlation_strength: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Load data for specific analysis needs.
        
        Args:
            percentile: Specific percentile to load
            features: Specific features to load (None = all)
            min_correlation_strength: Minimum absolute correlation value
            
        Returns:
            DataFrame with filtered correlation data
        """
        # Load data for specific percentile
        df = self._load_raw_data(percentiles=[percentile])
        
        # Filter by features if specified
        if features:
            df = df[df['feature'].isin(features)]
        
        # Filter by correlation strength if specified
        if min_correlation_strength is not None:
            df = df[df['correlation'].abs() >= min_correlation_strength]
        
        return df
    
    def export_for_external_analysis(
        self,
        output_file: str,
        format: str = 'csv',
        percentiles: Optional[List[str]] = None
    ):
        """
        Export correlation data for analysis in external tools.
        
        Args:
            output_file: Output file path
            format: Output format ('csv', 'parquet', 'json')
            percentiles: Specific percentiles to export
        """
        df = self._load_raw_data(percentiles=percentiles)
        
        output_path = Path(output_file)
        
        if format == 'csv':
            df.to_csv(output_path, index=False)
        elif format == 'parquet':
            df.to_parquet(output_path, compression='snappy')
        elif format == 'json':
            # Transform to nested structure
            correlation_results = self._transform_to_correlation_format(df)
            with open(output_path, 'w') as f:
                json.dump(correlation_results, f, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"Exported {len(df)} correlation records to {output_path}")