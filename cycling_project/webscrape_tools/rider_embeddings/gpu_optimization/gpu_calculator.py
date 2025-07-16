"""
GPU-Optimized Interaction Calculator

This module provides a GPU-accelerated version of the interaction embeddings calculator
that processes riders in batches for optimal GPU utilization.

Key features:
- Batch processing for GPU efficiency
- Automatic fallback to CPU when needed
- Memory management and optimization
- Performance monitoring and statistics
- Compatibility with existing data structures
"""

import torch
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
import time

# Import parent classes and modules
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from database_optimization.optimized_calculator import OptimizedInteractionCalculator
from gpu_optimization.metal_accelerator import MetalAccelerator
from gpu_optimization.batch_processor import GPUBatchProcessor


class GPUOptimizedInteractionCalculator(OptimizedInteractionCalculator):
    """
    GPU-accelerated interaction embeddings calculator.
    
    This class extends the database-optimized calculator with GPU acceleration
    for matrix operations, providing significant performance improvements for
    batch processing of rider embeddings.
    """
    
    def __init__(
        self,
        shared_race_features: Dict[str, Dict[int, Dict[str, float]]],
        shared_rider_histories: Dict[int, List[Dict[str, Any]]],
        calculator_config: Dict[str, Any],
        use_gpu: bool = True,
        gpu_batch_size: int = 32
    ):
        """
        Initialize the GPU-optimized calculator.
        
        Args:
            shared_race_features: Pre-loaded race features
            shared_rider_histories: Pre-loaded rider histories
            calculator_config: Configuration with minimum race requirements
            use_gpu: Whether to enable GPU acceleration
            gpu_batch_size: Batch size for GPU operations
        """
        super().__init__(shared_race_features, shared_rider_histories, calculator_config)
        
        self.use_gpu = use_gpu
        self.gpu_batch_size = gpu_batch_size
        
        # Initialize GPU components
        self.metal_accelerator = MetalAccelerator(enable_gpu=use_gpu, batch_size=gpu_batch_size)
        self.batch_processor = GPUBatchProcessor(
            device=self.metal_accelerator.device,
            max_batch_size=gpu_batch_size
        )
        
        # Performance tracking
        self.gpu_stats = {
            'total_batches_processed': 0,
            'gpu_batch_time': 0.0,
            'cpu_fallback_time': 0.0,
            'gpu_batch_count': 0,
            'cpu_fallback_count': 0
        }
        
        self.logger = logging.getLogger(__name__)
        
        if self.metal_accelerator.is_gpu_available():
            self.logger.info(f"GPU acceleration enabled with batch size {gpu_batch_size}")
        else:
            self.logger.info("GPU acceleration disabled, using CPU mode")
    
    def calculate_batch_interactions(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str],
        interaction_types: List[str] = ['dot', 'hadamard', 'cosine']
    ) -> List[Dict[str, Any]]:
        """
        Calculate interactions for a batch of riders using GPU acceleration.
        
        Args:
            rider_batch: List of (rider_result_id, competition_id) tuples
            feature_tables: List of feature tables to analyze
            interaction_types: Types of interactions to calculate
            
        Returns:
            List of interaction results for each rider
        """
        batch_start_time = time.time()
        
        # Fall back to CPU for small batches or when GPU is unavailable
        if len(rider_batch) <= 16 or not self.metal_accelerator.is_gpu_available():
            return self._cpu_batch_processing(rider_batch, feature_tables, interaction_types)
        
        try:
            # GPU batch processing
            results = self._gpu_batch_processing(rider_batch, feature_tables, interaction_types)
            
            # Update statistics
            self.gpu_stats['gpu_batch_count'] += 1
            self.gpu_stats['gpu_batch_time'] += time.time() - batch_start_time
            self.gpu_stats['total_batches_processed'] += 1
            
            return results
            
        except Exception as e:
            self.logger.warning(f"GPU batch processing failed: {e}, falling back to CPU")
            
            # Fall back to CPU
            results = self._cpu_batch_processing(rider_batch, feature_tables, interaction_types)
            
            # Update statistics
            self.gpu_stats['cpu_fallback_count'] += 1
            self.gpu_stats['cpu_fallback_time'] += time.time() - batch_start_time
            self.gpu_stats['total_batches_processed'] += 1
            
            return results
    
    def _gpu_batch_processing(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str],
        interaction_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Process a batch of riders using GPU acceleration."""
        
        # Process each race type separately for better memory efficiency
        race_types = ['stage', 'stage_one_day', 'all']  # Focus on most common types
        results = []
        
        for rider_result_id, competition_id in rider_batch:
            rider_result = {
                'rider_result_id': rider_result_id,
                'phase1_interactions': {},
                'phase2_interactions': {},
                'metadata': {
                    'n_races': {},
                    'method': 'gpu_optimized_interaction_embeddings',
                    'calculation_date': datetime.now().isoformat(),
                    'interaction_types': interaction_types,
                    'feature_tables': feature_tables,
                    'warnings': []
                }
            }
            
            # Get current race features
            current_features = self._get_current_race_features_cached(competition_id, feature_tables)
            
            if not current_features:
                rider_result['metadata']['warnings'].append("Current race features not found")
                results.append(rider_result)
                continue
            
            # Get rider history
            rider_history = self.shared_rider_histories.get(rider_result_id, [])
            
            if not rider_history:
                rider_result['metadata']['warnings'].append("No rider history found")
                results.append(rider_result)
                continue
            
            # Process each race type
            for race_type in race_types:
                # Get race type specific history
                race_type_history = self._get_race_type_history(rider_history, race_type)
                
                if len(race_type_history) < self.min_races[race_type]:
                    continue
                
                # Calculate correlations using CPU (more efficient)
                correlations = self._calculate_correlations_optimized(
                    race_type_history, feature_tables, race_type
                )
                
                if not correlations:
                    continue
                
                # Calculate interactions
                phase1, phase2 = self._calculate_gpu_interactions(
                    current_features, correlations, interaction_types
                )
                
                rider_result['phase1_interactions'][race_type] = phase1
                rider_result['phase2_interactions'][race_type] = phase2
                rider_result['metadata']['n_races'][race_type] = len(race_type_history)
            
            results.append(rider_result)
        
        return results
    
    
    def _calculate_gpu_interactions(
        self,
        current_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, float]],
        interaction_types: List[str]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Calculate interactions using GPU acceleration."""
        
        # Convert to tensor format
        feature_tensors, corr_tensors = self._convert_to_interaction_tensors(
            current_features, correlations
        )
        
        if feature_tensors is None or corr_tensors is None:
            return {}, {}
        
        # Calculate interactions on GPU
        gpu_interactions = self.metal_accelerator.batch_interaction_calculations(
            feature_tensors, corr_tensors
        )
        
        # Phase 1: Individual percentile interactions
        phase1 = {}
        for percentile in current_features.keys():
            percentile_interactions = {}
            
            if 'dot' in interaction_types:
                percentile_interactions['dot'] = float(gpu_interactions['dot'][0])
            
            if 'hadamard' in interaction_types:
                hadamard_matrix = gpu_interactions['hadamard'][0]  # [n_percentiles, n_features]
                percentile_interactions['hadamard'] = self._matrix_to_dict(hadamard_matrix)
            
            if 'cosine' in interaction_types:
                percentile_interactions['cosine'] = float(gpu_interactions['cosine'][0])
            
            phase1[percentile] = percentile_interactions
        
        # Phase 2: Matrix-level interactions
        phase2 = {
            'interactions': {},
            'shape': feature_tensors.shape[-2:],
            'percentiles': list(current_features.keys()),
            'features': self.batch_processor.feature_names
        }
        
        for interaction_type in interaction_types:
            if interaction_type in gpu_interactions:
                value = gpu_interactions[interaction_type][0]
                if isinstance(value, torch.Tensor):
                    if value.dim() == 0:  # Scalar
                        phase2['interactions'][interaction_type] = float(value)
                    else:  # Matrix
                        phase2['interactions'][interaction_type] = value.cpu().numpy()
                else:
                    phase2['interactions'][interaction_type] = value
        
        return phase1, phase2
    
    
    def _convert_to_interaction_tensors(
        self,
        current_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, float]]
    ) -> Tuple[Optional[torch.Tensor], Optional[torch.Tensor]]:
        """Convert current features and correlations to tensor format."""
        
        if not current_features or not correlations:
            return None, None
        
        # Get common percentiles
        common_percentiles = set(current_features.keys()) & set(correlations.keys())
        if not common_percentiles:
            return None, None
        
        percentiles = sorted(common_percentiles)
        
        # Build tensors
        feature_matrix = []
        corr_matrix = []
        
        for percentile in percentiles:
            # Current features
            feature_row = []
            for feature_name in self.batch_processor.feature_names:
                value = current_features[percentile].get(feature_name, 0.0)
                feature_row.append(float(value))
            feature_matrix.append(feature_row)
            
            # Correlations
            corr_row = []
            for feature_name in self.batch_processor.feature_names:
                value = correlations[percentile].get(feature_name, 0.0)
                if value is None:
                    value = 0.0
                corr_row.append(float(value))
            corr_matrix.append(corr_row)
        
        # Convert to tensors (add batch dimension)
        feature_tensor = torch.tensor([feature_matrix], dtype=torch.float32, device=self.metal_accelerator.device)
        corr_tensor = torch.tensor([corr_matrix], dtype=torch.float32, device=self.metal_accelerator.device)
        
        return feature_tensor, corr_tensor
    
    def _matrix_to_dict(self, matrix: torch.Tensor) -> Dict[str, float]:
        """Convert matrix to dictionary format for Hadamard products."""
        result = {}
        
        # Flatten matrix and map to feature names
        flat_matrix = matrix.flatten()
        for i, value in enumerate(flat_matrix):
            feature_idx = i % len(self.batch_processor.feature_names)
            percentile_idx = i // len(self.batch_processor.feature_names)
            
            feature_name = self.batch_processor.feature_names[feature_idx]
            key = f"{feature_name}_{percentile_idx}"
            result[key] = float(value)
        
        return result
    
    def _get_race_type_history(
        self,
        rider_history: List[Dict[str, Any]],
        race_type: str
    ) -> List[Dict[str, Any]]:
        """Get race type specific history."""
        if race_type == 'all':
            return rider_history
        
        race_type_map = {
            'gc': ['gc'],
            'stage': ['stage'],
            'one_day': ['one_day'],
            'stage_one_day': ['stage', 'one_day']
        }
        
        allowed_types = race_type_map.get(race_type, [])
        return [race for race in rider_history if race['competition_type'] in allowed_types]
    
    def _cpu_batch_processing(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str],
        interaction_types: List[str]
    ) -> List[Dict[str, Any]]:
        """Fall back to CPU processing for small batches."""
        results = []
        
        for rider_result_id, competition_id in rider_batch:
            result = self.calculate_interaction_embeddings_optimized(
                rider_result_id, competition_id, feature_tables, interaction_types
            )
            results.append(result)
        
        return results
    
    def get_gpu_performance_stats(self) -> Dict[str, Any]:
        """Get GPU performance statistics."""
        stats = self.gpu_stats.copy()
        
        # Add accelerator stats
        stats.update(self.metal_accelerator.get_performance_stats())
        
        # Add batch processor stats
        stats.update(self.batch_processor.get_batch_statistics())
        
        # Calculate efficiency metrics
        if stats['total_batches_processed'] > 0:
            stats['gpu_usage_ratio'] = stats['gpu_batch_count'] / stats['total_batches_processed']
            stats['avg_gpu_batch_time'] = stats['gpu_batch_time'] / max(stats['gpu_batch_count'], 1)
            stats['avg_cpu_fallback_time'] = stats['cpu_fallback_time'] / max(stats['cpu_fallback_count'], 1)
        
        return stats
    
    def reset_gpu_stats(self):
        """Reset GPU performance statistics."""
        self.gpu_stats = {
            'total_batches_processed': 0,
            'gpu_batch_time': 0.0,
            'cpu_fallback_time': 0.0,
            'gpu_batch_count': 0,
            'cpu_fallback_count': 0
        }
        
        self.metal_accelerator.reset_performance_stats()
        self.batch_processor.reset_statistics()
    
    def benchmark_gpu_performance(self, sample_size: int = 100) -> Dict[str, Any]:
        """Benchmark GPU vs CPU performance."""
        return self.metal_accelerator.benchmark_gpu_vs_cpu(
            batch_size=min(sample_size, self.gpu_batch_size),
            n_races=100,
            n_features=37
        )