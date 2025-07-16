"""
GPU Batch Processor for Interaction Embeddings

This module handles the preparation and processing of rider data in batches
optimized for GPU acceleration. It manages tensor conversion and batch
organization for efficient GPU interaction calculations.

Key features:
- Intelligent batch sizing based on GPU memory
- Memory-efficient data preparation for interactions
- Tensor conversion for GPU operations
- Simplified batch processing (correlations handled by CPU)
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
import logging
from dataclasses import dataclass


@dataclass
class BatchMetrics:
    """Metrics for batch processing performance."""
    batch_size: int
    max_races: int
    n_features: int
    padding_efficiency: float
    memory_usage_mb: float
    preparation_time: float


class GPUBatchProcessor:
    """
    Processes rider data in batches optimized for GPU acceleration.
    
    This class handles the complex task of converting irregular rider histories
    into padded tensor format suitable for GPU batch processing.
    """
    
    def __init__(self, device: torch.device, max_batch_size: int = 64):
        """
        Initialize the batch processor.
        
        Args:
            device: Target device for tensors (CPU or MPS)
            max_batch_size: Maximum batch size for memory management
        """
        self.device = device
        self.max_batch_size = max_batch_size
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.batch_metrics: List[BatchMetrics] = []
        
        # Feature configuration
        self.feature_names = [
            'total_finishers', 'included_finishers', 'abandon_ratio', 
            'winning_time', 'total_race_duration',
            'variance_absolute', 'variance_normalized',
            'std_deviation_absolute', 'std_deviation_normalized',
            'skewness_absolute', 'skewness_normalized',
            'kurtosis_absolute', 'kurtosis_normalized',
            'gini_coefficient',
            'shannon_entropy_absolute', 'shannon_entropy_normalized',
            '5th_percentile_gap', '10th_percentile_gap', '15th_percentile_gap',
            '20th_percentile_gap', '25th_percentile_gap', '30th_percentile_gap',
            '35th_percentile_gap', '40th_percentile_gap', '45th_percentile_gap',
            '50th_percentile_gap',
            'total_groups', 'riders_in_groups', 'proportion_in_groups',
            'largest_group_size', 'largest_group_position', 'avg_group_size',
            'std_group_size', 'biggest_group_metric', 'time_gap_evenness_metric',
            'clumpiness_score', 'selection_metric'
        ]
        self.n_features = len(self.feature_names)
    
    
    def prepare_interaction_batch(
        self,
        rider_batch: List[Tuple[int, int]],
        shared_race_features: Dict[str, Dict[int, Dict[str, float]]],
        correlations_batch: torch.Tensor,
        feature_tables: List[str]
    ) -> Dict[str, torch.Tensor]:
        """
        Prepare a batch of current race features for interaction calculation.
        
        Args:
            rider_batch: List of (rider_result_id, competition_id) tuples
            shared_race_features: Pre-loaded race features
            correlations_batch: Computed correlations tensor
            feature_tables: List of feature tables to process
            
        Returns:
            Dictionary with prepared tensors for interaction calculation
        """
        n_percentiles = len(feature_tables)
        batch_size = len(rider_batch)
        
        # Prepare current race features tensor
        current_features = torch.zeros(batch_size, n_percentiles, self.n_features, dtype=torch.float32)
        
        for batch_idx, (rider_result_id, competition_id) in enumerate(rider_batch):
            for percentile_idx, feature_table in enumerate(feature_tables):
                if feature_table in shared_race_features:
                    comp_features = shared_race_features[feature_table].get(competition_id, {})
                    
                    # Extract features in consistent order
                    feature_values = []
                    for feature_name in self.feature_names:
                        value = comp_features.get(feature_name, 0.0)
                        feature_values.append(float(value))
                    
                    current_features[batch_idx, percentile_idx] = torch.tensor(feature_values, dtype=torch.float32)
        
        # Move to target device
        current_features = current_features.to(self.device)
        
        return {
            'current_features': current_features,
            'correlations': correlations_batch,
            'batch_size': batch_size,
            'n_percentiles': n_percentiles,
            'rider_ids': [rid for rid, _ in rider_batch],
            'competition_ids': [cid for _, cid in rider_batch]
        }
    
    
    def _create_empty_batch(self, batch_size: int) -> Dict[str, torch.Tensor]:
        """Create an empty batch for cases with no data."""
        return {
            'performance': torch.zeros(batch_size, 1, dtype=torch.float32, device=self.device),
            'features': torch.zeros(batch_size, 1, self.n_features, dtype=torch.float32, device=self.device),
            'masks': torch.zeros(batch_size, 1, dtype=torch.bool, device=self.device),
            'batch_size': batch_size,
            'max_races': 0,
            'rider_ids': [],
            'competition_ids': [],
            'metrics': BatchMetrics(
                batch_size=batch_size,
                max_races=0,
                n_features=self.n_features,
                padding_efficiency=0.0,
                memory_usage_mb=0.0,
                preparation_time=0.0
            )
        }
    
    def _estimate_memory_usage(self, *tensors: torch.Tensor) -> float:
        """Estimate memory usage of tensors in MB."""
        total_bytes = sum(tensor.numel() * tensor.element_size() for tensor in tensors)
        return total_bytes / (1024 * 1024)  # Convert to MB
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """Get statistics about batch processing performance."""
        if not self.batch_metrics:
            return {}
        
        metrics = self.batch_metrics
        
        return {
            'total_batches': len(metrics),
            'avg_batch_size': sum(m.batch_size for m in metrics) / len(metrics),
            'avg_max_races': sum(m.max_races for m in metrics) / len(metrics),
            'avg_padding_efficiency': sum(m.padding_efficiency for m in metrics) / len(metrics),
            'avg_memory_usage_mb': sum(m.memory_usage_mb for m in metrics) / len(metrics),
            'avg_preparation_time': sum(m.preparation_time for m in metrics) / len(metrics),
            'total_preparation_time': sum(m.preparation_time for m in metrics),
            'max_memory_usage_mb': max(m.memory_usage_mb for m in metrics),
            'min_padding_efficiency': min(m.padding_efficiency for m in metrics),
            'max_padding_efficiency': max(m.padding_efficiency for m in metrics)
        }
    
    def reset_statistics(self):
        """Reset batch processing statistics."""
        self.batch_metrics = []
    
    def optimize_batch_size(
        self,
        sample_rider_batch: List[Tuple[int, int]],
        shared_rider_histories: Dict[int, List[Dict[str, Any]]],
        target_memory_mb: float = 512.0
    ) -> int:
        """
        Determine optimal batch size based on memory constraints.
        
        Args:
            sample_rider_batch: Sample of rider data for testing
            shared_rider_histories: Pre-loaded rider histories
            target_memory_mb: Target memory usage in MB
            
        Returns:
            Optimal batch size
        """
        # Test different batch sizes using interaction batches
        test_sizes = [8, 16, 32, 64, 128]
        optimal_size = self.max_batch_size
        
        for test_size in test_sizes:
            if test_size > len(sample_rider_batch):
                continue
            
            # Test with subset
            test_batch = sample_rider_batch[:test_size]
            
            try:
                # Prepare test batch (simplified for interaction calculations)
                batch_size = len(test_batch)
                n_percentiles = 8
                
                # Estimate memory usage for interaction calculations
                current_features = torch.zeros(batch_size, n_percentiles, self.n_features, dtype=torch.float32)
                correlations = torch.zeros(batch_size, n_percentiles, self.n_features, dtype=torch.float32)
                
                memory_usage = self._estimate_memory_usage(current_features, correlations)
                
                if memory_usage <= target_memory_mb:
                    optimal_size = test_size
                else:
                    break
                    
            except Exception as e:
                self.logger.warning(f"Batch size {test_size} failed: {e}")
                break
        
        self.logger.info(f"Optimal batch size determined: {optimal_size}")
        return optimal_size