import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import json
from tqdm import tqdm
import logging
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))
from rider_embeddings.performance_feature_link.correlation_method import CorrelationCalculator


class CorrelationDataGenerator:
    """
    Generate correlation data for all rider results and save to parquet files.
    
    Handles batch processing, progress tracking, and error recovery.
    """
    
    def __init__(
        self, 
        db_path: str,
        output_dir: str = "correlation_data",
        batch_size: int = 100,
        min_races: int = 5
    ):
        """
        Initialize the correlation data generator.
        
        Args:
            db_path: Path to the cycling database
            output_dir: Directory to save parquet files
            batch_size: Number of rider results to process per batch
            min_races: Minimum races required for correlation calculation
        """
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        self.min_races = min_races
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize correlation calculator
        self.calculator = CorrelationCalculator(db_path, min_races)
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration."""
        log_file = self.output_dir / "generation.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def get_eligible_rider_results(self, limit: Optional[int] = None) -> List[Tuple[int, str]]:
        """
        Get all rider results eligible for correlation calculation.
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of (rider_result_id, competition_date) tuples
        """
        query = """
        SELECT rr.id, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE EXISTS (
            SELECT 1 
            FROM rider_results rr2
            JOIN competitions c2 ON rr2.competition_id = c2.id
            WHERE rr2.rider_id = rr.rider_id
            AND c2.date < c.date
            GROUP BY rr2.rider_id
            HAVING COUNT(*) >= ?
        )
        ORDER BY rr.id
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (self.min_races,))
            return cursor.fetchall()
    
    def load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint file if it exists."""
        checkpoint_file = self.output_dir / "checkpoint.json"
        
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        
        return {
            'last_processed_id': 0,
            'processed_count': 0,
            'batch_number': 0,
            'start_time': datetime.now().isoformat()
        }
    
    def save_checkpoint(self, checkpoint: Dict[str, Any]):
        """Save checkpoint for resume capability."""
        checkpoint_file = self.output_dir / "checkpoint.json"
        
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint, f, indent=2)
    
    def generate_all_correlations(
        self, 
        feature_tables: List[str] = None,
        limit: Optional[int] = None,
        resume: bool = True
    ):
        """
        Generate correlations for all eligible rider results.
        
        Args:
            feature_tables: List of race_features_N tables to analyze
            limit: Optional limit on number of rider results to process
            resume: Whether to resume from checkpoint
        """
        if feature_tables is None:
            feature_tables = [
                'race_features_30', 'race_features_40', 'race_features_50',
                'race_features_60', 'race_features_70', 'race_features_80',
                'race_features_90', 'race_features_100'
            ]
        
        # Load checkpoint if resuming
        checkpoint = self.load_checkpoint() if resume else {
            'last_processed_id': 0,
            'processed_count': 0,
            'batch_number': 0,
            'start_time': datetime.now().isoformat()
        }
        
        self.logger.info(f"Starting correlation generation...")
        self.logger.info(f"Feature tables: {feature_tables}")
        
        if resume and checkpoint['last_processed_id'] > 0:
            self.logger.info(f"Resuming from rider_result_id {checkpoint['last_processed_id']}")
        
        # Get eligible rider results
        eligible_results = self.get_eligible_rider_results(limit)
        
        # Filter out already processed if resuming
        if resume:
            eligible_results = [
                (rr_id, date) for rr_id, date in eligible_results
                if rr_id > checkpoint['last_processed_id']
            ]
        
        total_to_process = len(eligible_results)
        self.logger.info(f"Found {total_to_process} rider results to process")
        
        # Process in batches
        batch_data = []
        
        with tqdm(total=total_to_process, desc="Generating correlations") as pbar:
            for i, (rr_id, competition_date) in enumerate(eligible_results):
                try:
                    # Calculate correlations
                    result = self.calculator.calculate_feature_relationships(
                        rr_id, competition_date, feature_tables
                    )
                    
                    # Convert to flat structure for parquet
                    flat_result = self._flatten_correlation_result(result)
                    batch_data.extend(flat_result)
                    
                    # Update checkpoint
                    checkpoint['last_processed_id'] = rr_id
                    checkpoint['processed_count'] += 1
                    
                    # Save batch if needed
                    if len(batch_data) >= self.batch_size * len(feature_tables):
                        self._save_batch(batch_data, checkpoint['batch_number'])
                        checkpoint['batch_number'] += 1
                        batch_data = []
                        self.save_checkpoint(checkpoint)
                    
                except Exception as e:
                    self.logger.error(f"Error processing rider_result {rr_id}: {e}")
                
                pbar.update(1)
        
        # Save final batch
        if batch_data:
            self._save_batch(batch_data, checkpoint['batch_number'])
            checkpoint['batch_number'] += 1
            self.save_checkpoint(checkpoint)
        
        # Save generation metadata
        self._save_generation_metadata(checkpoint, feature_tables)
        
        self.logger.info(f"Correlation generation complete!")
        self.logger.info(f"Processed {checkpoint['processed_count']} rider results")
        self.logger.info(f"Saved {checkpoint['batch_number']} batches to {self.output_dir}")
    
    def _flatten_correlation_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten correlation result into list of records for parquet storage.
        
        Each record represents one rider-percentile-feature correlation.
        """
        flat_records = []
        
        rider_result_id = result['rider_result_id']
        n_races = result['metadata']['n_races']
        calculation_date = result['metadata']['calculation_date']
        
        for percentile, correlations in result['feature_correlations'].items():
            for feature, correlation in correlations.items():
                record = {
                    'rider_result_id': rider_result_id,
                    'percentile': percentile,
                    'feature': feature,
                    'correlation': correlation,
                    'n_races': n_races,
                    'calculation_date': calculation_date
                }
                flat_records.append(record)
        
        return flat_records
    
    def _save_batch(self, batch_data: List[Dict[str, Any]], batch_number: int):
        """Save batch data to parquet file."""
        df = pd.DataFrame(batch_data)
        
        # Convert types for efficient storage
        df['rider_result_id'] = df['rider_result_id'].astype('int32')
        df['n_races'] = df['n_races'].astype('int16')
        df['percentile'] = df['percentile'].astype('category')
        df['feature'] = df['feature'].astype('category')
        
        # Save to parquet
        output_file = self.output_dir / f"correlations_batch_{batch_number:04d}.parquet"
        df.to_parquet(output_file, compression='snappy')
        
        self.logger.info(f"Saved batch {batch_number} with {len(df)} records")
    
    def _save_generation_metadata(self, checkpoint: Dict[str, Any], feature_tables: List[str]):
        """Save metadata about the generation run."""
        metadata = {
            'generation_complete': datetime.now().isoformat(),
            'start_time': checkpoint['start_time'],
            'total_processed': checkpoint['processed_count'],
            'total_batches': checkpoint['batch_number'],
            'feature_tables': feature_tables,
            'min_races': self.min_races,
            'batch_size': self.batch_size
        }
        
        metadata_file = self.output_dir / "generation_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def generate_sample(
        self, 
        sample_size: int = 1000,
        feature_tables: List[str] = None,
        output_name: str = "sample"
    ):
        """
        Generate correlations for a sample of rider results.
        
        Useful for testing and development.
        
        Args:
            sample_size: Number of rider results to sample
            feature_tables: List of feature tables to analyze
            output_name: Name for output file
        """
        if feature_tables is None:
            feature_tables = ['race_features_80', 'race_features_100']
        
        self.logger.info(f"Generating sample correlation data for {sample_size} rider results")
        
        # Get random sample of eligible results
        query = """
        SELECT rr.id, c.date as competition_date
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE EXISTS (
            SELECT 1 
            FROM rider_results rr2
            JOIN competitions c2 ON rr2.competition_id = c2.id
            WHERE rr2.rider_id = rr.rider_id
            AND c2.date < c.date
            GROUP BY rr2.rider_id
            HAVING COUNT(*) >= ?
        )
        ORDER BY RANDOM()
        LIMIT ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (self.min_races, sample_size))
            sample_results = cursor.fetchall()
        
        # Generate correlations
        all_data = []
        successful_count = 0
        
        for rr_id, competition_date in tqdm(sample_results, desc="Processing sample"):
            try:
                result = self.calculator.calculate_feature_relationships(
                    rr_id, competition_date, feature_tables
                )
                
                # Only add if we got valid correlations
                if result['feature_correlations']:
                    flat_result = self._flatten_correlation_result(result)
                    all_data.extend(flat_result)
                    successful_count += 1
                    
            except Exception as e:
                self.logger.error(f"Error processing rider_result {rr_id}: {e}")
        
        self.logger.info(f"Successfully processed {successful_count}/{len(sample_results)} rider results")
        
        # Save sample data
        df = pd.DataFrame(all_data)
        output_file = self.output_dir / f"{output_name}_correlations.parquet"
        df.to_parquet(output_file, compression='snappy')
        
        self.logger.info(f"Saved sample data with {len(df)} records to {output_file}")
        
        # Save sample metadata
        metadata = {
            'type': 'sample',
            'sample_size': sample_size,
            'actual_riders': len(sample_results),
            'total_records': len(df),
            'feature_tables': feature_tables,
            'generation_date': datetime.now().isoformat()
        }
        
        metadata_file = self.output_dir / f"{output_name}_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)