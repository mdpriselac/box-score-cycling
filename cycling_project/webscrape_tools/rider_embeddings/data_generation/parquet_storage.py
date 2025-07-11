import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
import json
import glob
from datetime import datetime
import pyarrow.parquet as pq
import pyarrow as pa


class ParquetStorage:
    """
    Utilities for managing parquet-based correlation data storage.
    
    Handles merging, partitioning, and optimizing parquet files.
    """
    
    def __init__(self, data_dir: str = "correlation_data"):
        """
        Initialize parquet storage manager.
        
        Args:
            data_dir: Directory containing parquet files
        """
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise ValueError(f"Data directory {data_dir} does not exist")
    
    def list_batch_files(self) -> List[Path]:
        """List all batch parquet files in the data directory."""
        pattern = str(self.data_dir / "correlations_batch_*.parquet")
        files = glob.glob(pattern)
        return sorted([Path(f) for f in files])
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get statistics about stored correlation data."""
        batch_files = self.list_batch_files()
        
        if not batch_files:
            return {
                'total_files': 0,
                'total_size_mb': 0,
                'total_records': 0
            }
        
        total_size = sum(f.stat().st_size for f in batch_files)
        
        # Sample first file for record count estimate
        first_df = pd.read_parquet(batch_files[0])
        avg_records_per_file = len(first_df)
        estimated_total_records = avg_records_per_file * len(batch_files)
        
        # Get unique counts from metadata if available
        metadata_file = self.data_dir / "generation_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                total_processed = metadata.get('total_processed', 0)
        else:
            total_processed = None
        
        return {
            'total_files': len(batch_files),
            'total_size_mb': total_size / (1024 * 1024),
            'estimated_records': estimated_total_records,
            'total_rider_results': total_processed,
            'batch_files': [f.name for f in batch_files],
            'avg_file_size_mb': (total_size / len(batch_files)) / (1024 * 1024) if batch_files else 0
        }
    
    def merge_batches(
        self, 
        output_file: str = "merged_correlations.parquet",
        batch_numbers: Optional[List[int]] = None,
        delete_originals: bool = False
    ) -> Path:
        """
        Merge multiple batch files into a single parquet file.
        
        Args:
            output_file: Name for merged file
            batch_numbers: Specific batch numbers to merge (None = all)
            delete_originals: Whether to delete original batch files
            
        Returns:
            Path to merged file
        """
        batch_files = self.list_batch_files()
        
        if batch_numbers:
            # Filter to specific batches
            batch_files = [
                f for f in batch_files
                if int(f.stem.split('_')[-1]) in batch_numbers
            ]
        
        if not batch_files:
            raise ValueError("No batch files found to merge")
        
        print(f"Merging {len(batch_files)} batch files...")
        
        # Read and concatenate all batches
        dfs = []
        for batch_file in batch_files:
            df = pd.read_parquet(batch_file)
            dfs.append(df)
        
        merged_df = pd.concat(dfs, ignore_index=True)
        
        # Save merged file
        output_path = self.data_dir / output_file
        merged_df.to_parquet(output_path, compression='snappy')
        
        print(f"Merged {len(merged_df)} records into {output_path}")
        
        # Delete originals if requested
        if delete_originals:
            for batch_file in batch_files:
                batch_file.unlink()
            print(f"Deleted {len(batch_files)} original batch files")
        
        return output_path
    
    def partition_by_percentile(
        self, 
        source_file: Optional[str] = None,
        output_dir: str = "partitioned"
    ) -> Path:
        """
        Partition correlation data by percentile for efficient querying.
        
        Args:
            source_file: Source parquet file (None = merge all batches first)
            output_dir: Directory for partitioned output
            
        Returns:
            Path to partitioned dataset
        """
        if source_file is None:
            # Merge all batches first
            source_path = self.merge_batches("temp_merged.parquet")
        else:
            source_path = self.data_dir / source_file
        
        if not source_path.exists():
            raise ValueError(f"Source file {source_path} not found")
        
        output_path = self.data_dir / output_dir
        output_path.mkdir(exist_ok=True)
        
        print(f"Partitioning data by percentile...")
        
        # Read source data
        df = pd.read_parquet(source_path)
        
        # Write partitioned dataset
        df.to_parquet(
            output_path,
            partition_cols=['percentile'],
            compression='snappy'
        )
        
        print(f"Created partitioned dataset at {output_path}")
        
        # Clean up temp file if created
        if source_file is None:
            source_path.unlink()
        
        return output_path
    
    def create_feature_index(
        self,
        source_file: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Create an index of available features per percentile.
        
        Args:
            source_file: Source parquet file to analyze
            
        Returns:
            Dictionary mapping percentile to list of features
        """
        if source_file is None:
            # Try batch files first
            batch_files = self.list_batch_files()
            if batch_files:
                source_path = batch_files[0]
            else:
                # Look for any parquet files
                parquet_files = list(self.data_dir.glob("*.parquet"))
                if not parquet_files:
                    raise ValueError("No parquet files found")
                source_path = parquet_files[0]
        else:
            source_path = self.data_dir / source_file
        
        df = pd.read_parquet(source_path)
        
        # Get unique features per percentile
        feature_index = {}
        
        for percentile in df['percentile'].unique():
            percentile_df = df[df['percentile'] == percentile]
            features = sorted(percentile_df['feature'].unique())
            feature_index[percentile] = features
        
        # Save index
        index_file = self.data_dir / "feature_index.json"
        with open(index_file, 'w') as f:
            json.dump(feature_index, f, indent=2)
        
        print(f"Created feature index with {len(feature_index)} percentiles")
        
        return feature_index
    
    def optimize_storage(
        self,
        source_pattern: str = "correlations_batch_*.parquet",
        chunk_size: int = 10,
        compression: str = 'snappy'
    ) -> List[Path]:
        """
        Optimize storage by merging small batch files into larger chunks.
        
        Args:
            source_pattern: Pattern for files to optimize
            chunk_size: Number of files to merge per chunk
            compression: Compression algorithm
            
        Returns:
            List of optimized file paths
        """
        batch_files = sorted(glob.glob(str(self.data_dir / source_pattern)))
        
        if not batch_files:
            raise ValueError("No files found to optimize")
        
        print(f"Optimizing {len(batch_files)} files into chunks of {chunk_size}...")
        
        optimized_files = []
        
        # Process in chunks
        for i in range(0, len(batch_files), chunk_size):
            chunk_files = batch_files[i:i + chunk_size]
            chunk_number = i // chunk_size
            
            # Read and merge chunk
            dfs = [pd.read_parquet(f) for f in chunk_files]
            merged_df = pd.concat(dfs, ignore_index=True)
            
            # Save optimized chunk
            output_file = self.data_dir / f"optimized_chunk_{chunk_number:03d}.parquet"
            merged_df.to_parquet(output_file, compression=compression)
            
            optimized_files.append(output_file)
            print(f"Created optimized chunk {chunk_number} with {len(merged_df)} records")
        
        # Update metadata
        self._update_optimization_metadata(len(batch_files), len(optimized_files))
        
        return optimized_files
    
    def _update_optimization_metadata(self, original_files: int, optimized_files: int):
        """Update metadata after optimization."""
        metadata_file = self.data_dir / "optimization_metadata.json"
        
        metadata = {
            'optimization_date': datetime.now().isoformat(),
            'original_file_count': original_files,
            'optimized_file_count': optimized_files,
            'reduction_ratio': original_files / optimized_files if optimized_files > 0 else 0
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def validate_data(self, sample_size: int = 1000) -> Dict[str, Any]:
        """
        Validate stored correlation data by checking samples.
        
        Args:
            sample_size: Number of records to sample for validation
            
        Returns:
            Validation report
        """
        batch_files = self.list_batch_files()
        
        if not batch_files:
            # Look for any parquet files
            parquet_files = list(self.data_dir.glob("*.parquet"))
            if not parquet_files:
                return {'valid': False, 'error': 'No parquet files found', 'issues': [], 'summary': {}}
            source_file = parquet_files[0]
        else:
            source_file = batch_files[0]
        
        # Sample from file
        df = pd.read_parquet(source_file)
        
        if len(df) > sample_size:
            df = df.sample(n=sample_size)
        
        # Validation checks
        issues = []
        
        # Check for nulls in critical columns
        critical_cols = ['rider_result_id', 'percentile', 'feature']
        for col in critical_cols:
            null_count = df[col].isna().sum()
            if null_count > 0:
                issues.append(f"{col} has {null_count} null values")
        
        # Check correlation value range
        if 'correlation' in df.columns:
            corr_nulls = df['correlation'].isna()
            valid_corrs = df[~corr_nulls]['correlation']
            
            if len(valid_corrs) > 0:
                out_of_range = ((valid_corrs < -1) | (valid_corrs > 1)).sum()
                if out_of_range > 0:
                    issues.append(f"{out_of_range} correlations outside [-1, 1] range")
        
        # Check data types
        expected_types = {
            'rider_result_id': 'int',
            'n_races': 'int',
            'percentile': 'object',
            'feature': 'object',
            'correlation': 'float'
        }
        
        for col, expected in expected_types.items():
            if col in df.columns:
                actual = str(df[col].dtype)
                if expected not in actual:
                    issues.append(f"{col} has type {actual}, expected {expected}")
        
        return {
            'valid': len(issues) == 0,
            'records_checked': len(df),
            'issues': issues,
            'summary': {
                'unique_riders': df['rider_result_id'].nunique(),
                'unique_percentiles': df['percentile'].nunique(),
                'unique_features': df['feature'].nunique(),
                'null_correlations': df['correlation'].isna().sum()
            }
        }