"""
Hybrid CPU/GPU Interaction Calculator

This module combines CPU-based correlation calculations with GPU-accelerated 
matrix operations for optimal performance. It uses CPU for correlations 
(where it's more efficient) and GPU for large matrix operations.

Key features:
- CPU correlation calculations (efficient and reliable)
- GPU matrix operations for large batches (where GPU excels)
- Automatic batch size optimization
- Smart fallback mechanisms
- Performance monitoring
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


class HybridInteractionCalculator(OptimizedInteractionCalculator):
    """
    Hybrid calculator that combines CPU correlations with GPU matrix operations.
    
    This approach uses each processor type for what it does best:
    - CPU: Spearman correlations (sequential, efficient on CPU)
    - GPU: Matrix operations (parallel, efficient on GPU for large batches)
    """
    
    def __init__(
        self,
        shared_race_features: Dict[str, Dict[int, Dict[str, float]]],
        shared_rider_histories: Dict[int, List[Dict[str, Any]]],
        calculator_config: Dict[str, Any],
        use_gpu: bool = True,
        gpu_batch_size: int = 500,
        cpu_batch_size: int = 100
    ):
        """
        Initialize the hybrid calculator.
        
        Args:
            shared_race_features: Pre-loaded race features
            shared_rider_histories: Pre-loaded rider histories
            calculator_config: Configuration with minimum race requirements
            use_gpu: Whether to enable GPU acceleration for matrix operations
            gpu_batch_size: Batch size for GPU operations (larger batches)
            cpu_batch_size: Batch size for CPU fallback (smaller batches)
        """
        super().__init__(shared_race_features, shared_rider_histories, calculator_config)
        
        # Ensure min_races is properly set (inherited from parent)
        self.min_races = {
            'gc': calculator_config.get('min_races_gc', 10),
            'stage': calculator_config.get('min_races_stage', 25),
            'one_day': calculator_config.get('min_races_one_day', 15),
            'stage_one_day': calculator_config.get('min_races_stage_one_day', 15),  # Fixed key name
            'all': calculator_config.get('min_races_all', 35)
        }
        
        self.use_gpu = use_gpu
        self.gpu_batch_size = gpu_batch_size
        self.cpu_batch_size = cpu_batch_size
        
        # Initialize GPU components only if enabled
        if self.use_gpu:
            self.metal_accelerator = MetalAccelerator(enable_gpu=use_gpu, batch_size=gpu_batch_size)
            self.batch_processor = GPUBatchProcessor(
                device=self.metal_accelerator.device,
                max_batch_size=gpu_batch_size
            )
            self.gpu_available = self.metal_accelerator.is_gpu_available()
        else:
            self.metal_accelerator = None
            self.batch_processor = None
            self.gpu_available = False
        
        # Performance tracking
        self.performance_stats = {
            'total_batches_processed': 0,
            'cpu_correlation_time': 0.0,
            'gpu_interaction_time': 0.0,
            'cpu_fallback_time': 0.0,
            'gpu_batch_count': 0,
            'cpu_batch_count': 0,
            'cpu_fallback_count': 0
        }
        
        self.logger = logging.getLogger(__name__)
        
        if self.gpu_available:
            self.logger.info(f"Hybrid calculator initialized with GPU acceleration")
            self.logger.info(f"GPU batch size: {gpu_batch_size}, CPU batch size: {cpu_batch_size}")
        else:
            self.logger.info("Hybrid calculator initialized in CPU-only mode")
    
    def calculate_batch_interactions(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str],
        interaction_types: List[str] = ['dot', 'hadamard', 'cosine']
    ) -> List[Dict[str, Any]]:
        """
        Calculate interactions for a batch of riders using hybrid approach.
        
        Args:
            rider_batch: List of (rider_result_id, competition_id) tuples
            feature_tables: List of feature tables to analyze
            interaction_types: Types of interactions to calculate
            
        Returns:
            List of interaction results for each rider
        """
        batch_start_time = time.time()
        batch_size = len(rider_batch)
        
        # Decide whether to use GPU or CPU based on batch size
        if batch_size >= self.gpu_batch_size and self.gpu_available:
            # Use hybrid GPU approach for large batches
            self.logger.info(f"Processing large batch ({batch_size} riders) with hybrid GPU approach")
            try:
                results = self._hybrid_gpu_processing(rider_batch, feature_tables, interaction_types)
                # Only count as GPU if it actually succeeded
                self.performance_stats['gpu_batch_count'] += 1
                self.performance_stats['gpu_interaction_time'] += time.time() - batch_start_time
            except Exception as e:
                self.logger.error(f"Hybrid GPU processing failed: {e}, falling back to CPU")
                results = self._cpu_batch_processing(rider_batch, feature_tables, interaction_types)
                self.performance_stats['cpu_fallback_count'] += 1
                self.performance_stats['cpu_fallback_time'] += time.time() - batch_start_time
        else:
            # Use CPU approach for small batches
            self.logger.info(f"Processing small batch ({batch_size} riders) with CPU approach")
            results = self._cpu_batch_processing(rider_batch, feature_tables, interaction_types)
            self.performance_stats['cpu_batch_count'] += 1
            self.performance_stats['cpu_fallback_time'] += time.time() - batch_start_time
        
        self.performance_stats['total_batches_processed'] += 1
        return results
    
    def _hybrid_gpu_processing(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str],
        interaction_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Process a large batch using hybrid CPU/GPU approach.
        
        Step 1: Calculate correlations on CPU (efficient)
        Step 2: Calculate interactions on GPU (efficient for large matrices)
        """
        # Step 1: Calculate correlations on CPU (batch processing)
        correlation_start = time.time()
        correlations_batch = self._calculate_correlations_batch(rider_batch, feature_tables)
        self.performance_stats['cpu_correlation_time'] += time.time() - correlation_start
        
        # Step 2: Calculate interactions on GPU if we have valid correlations
        if correlations_batch:
            interaction_start = time.time()
            results = self._calculate_gpu_interactions_batch(
                rider_batch, correlations_batch, feature_tables, interaction_types
            )
            self.performance_stats['gpu_interaction_time'] += time.time() - interaction_start
            return results
        else:
            # Fall back to CPU if no correlations
            self.logger.warning("No correlations calculated, falling back to CPU")
            raise ValueError("No correlations calculated for batch")
    
    def _calculate_correlations_batch(
        self,
        rider_batch: List[Tuple[int, int]],
        feature_tables: List[str]
    ) -> Dict[Tuple[int, int], Dict[str, Dict[str, Dict[str, float]]]]:
        """
        Calculate correlations for a batch of riders using optimized CPU approach.
        
        Returns:
            Dictionary mapping (rider_result_id, competition_id) to correlations
        """
        correlations_batch = {}
        
        for rider_result_id, competition_id in rider_batch:
            # Get rider history
            rider_history = self.shared_rider_histories.get(rider_result_id, [])
            
            if not rider_history:
                continue
            
            # Calculate correlations for all race types
            rider_correlations = {}
            
            for race_type in ['stage', 'stage_one_day', 'all']:
                # Get race type specific history
                race_type_history = self._get_race_type_history(rider_history, race_type)
                
                if len(race_type_history) < self.min_races[race_type]:
                    continue
                
                # Calculate correlations using existing optimized method
                correlations = self._calculate_correlations_from_shared_data(
                    race_type_history, feature_tables
                )
                
                if correlations:
                    rider_correlations[race_type] = correlations
            
            if rider_correlations:
                correlations_batch[(rider_result_id, competition_id)] = rider_correlations
        
        return correlations_batch
    
    def _calculate_gpu_interactions_batch(
        self,
        rider_batch: List[Tuple[int, int]],
        correlations_batch: Dict[Tuple[int, int], Dict[str, Dict[str, Dict[str, float]]]],
        feature_tables: List[str],
        interaction_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Calculate interactions for a batch using GPU acceleration.
        
        This method handles the tensor conversion and GPU matrix operations.
        """
        results = []
        
        # Group riders by race type for efficient GPU processing
        race_type_groups = {}
        for rider_result_id, competition_id in rider_batch:
            key = (rider_result_id, competition_id)
            if key in correlations_batch:
                for race_type in correlations_batch[key]:
                    if race_type not in race_type_groups:
                        race_type_groups[race_type] = []
                    race_type_groups[race_type].append((rider_result_id, competition_id))
        
        # Process each race type group
        for race_type, race_type_riders in race_type_groups.items():
            if not race_type_riders:
                continue
            
            # Prepare tensors for GPU processing
            gpu_batch_data = self._prepare_gpu_batch_data(
                race_type_riders, correlations_batch, feature_tables, race_type
            )
            
            if gpu_batch_data is None:
                continue
            
            # Calculate interactions on GPU
            gpu_interactions = self.metal_accelerator.batch_interaction_calculations(
                gpu_batch_data['current_features'],
                gpu_batch_data['correlations']
            )
            
            # Convert GPU results back to individual rider results
            for i, (rider_result_id, competition_id) in enumerate(race_type_riders):
                rider_result = self._create_rider_result_from_gpu(
                    rider_result_id, competition_id, race_type, gpu_interactions, i, 
                    feature_tables, interaction_types
                )
                
                # Add to existing result or create new one
                existing_result = next((r for r in results if r['rider_result_id'] == rider_result_id), None)
                if existing_result:
                    existing_result['phase1_interactions'][race_type] = rider_result['phase1_interactions'][race_type]
                    existing_result['phase2_interactions'][race_type] = rider_result['phase2_interactions'][race_type]
                    existing_result['metadata']['n_races'][race_type] = rider_result['metadata']['n_races'][race_type]
                else:
                    results.append(rider_result)
        
        return results
    
    def _prepare_gpu_batch_data(
        self,
        race_type_riders: List[Tuple[int, int]],
        correlations_batch: Dict[Tuple[int, int], Dict[str, Dict[str, Dict[str, float]]]],
        feature_tables: List[str],
        race_type: str
    ) -> Optional[Dict[str, torch.Tensor]]:
        """
        Prepare batch data for GPU processing.
        """
        batch_size = len(race_type_riders)
        n_percentiles = len(feature_tables)
        n_features = len(self.batch_processor.feature_names)
        
        # Initialize tensors
        current_features = torch.zeros(batch_size, n_percentiles, n_features, dtype=torch.float32)
        correlations = torch.zeros(batch_size, n_percentiles, n_features, dtype=torch.float32)
        
        for i, (rider_result_id, competition_id) in enumerate(race_type_riders):
            key = (rider_result_id, competition_id)
            
            if key not in correlations_batch or race_type not in correlations_batch[key]:
                continue
            
            rider_correlations = correlations_batch[key][race_type]
            
            # Get current race features
            current_race_features = self._get_current_race_features_cached(competition_id, feature_tables)
            
            if not current_race_features:
                continue
            
            # Fill tensors
            for j, feature_table in enumerate(feature_tables):
                # Current features
                if feature_table in current_race_features:
                    for k, feature_name in enumerate(self.batch_processor.feature_names):
                        value = current_race_features[feature_table].get(feature_name, 0.0)
                        current_features[i, j, k] = float(value)
                
                # Correlations
                if feature_table in rider_correlations:
                    for k, feature_name in enumerate(self.batch_processor.feature_names):
                        value = rider_correlations[feature_table].get(feature_name, 0.0)
                        if value is not None:
                            correlations[i, j, k] = float(value)
        
        # Move to GPU
        current_features = current_features.to(self.metal_accelerator.device)
        correlations = correlations.to(self.metal_accelerator.device)
        
        return {
            'current_features': current_features,
            'correlations': correlations
        }
    
    def _create_rider_result_from_gpu(
        self,
        rider_result_id: int,
        competition_id: int,
        race_type: str,
        gpu_interactions: Dict[str, torch.Tensor],
        batch_index: int,
        feature_tables: List[str],
        interaction_types: List[str]
    ) -> Dict[str, Any]:
        """
        Create a rider result from GPU interaction calculations.
        """
        rider_result = {
            'rider_result_id': rider_result_id,
            'phase1_interactions': {},
            'phase2_interactions': {},
            'metadata': {
                'n_races': {},
                'method': 'hybrid_cpu_gpu_interaction_embeddings',
                'calculation_date': datetime.now().isoformat(),
                'interaction_types': interaction_types,
                'feature_tables': feature_tables,
                'warnings': []
            }
        }
        
        # Phase 1: Individual percentile interactions
        phase1 = {}
        for percentile_idx, percentile in enumerate(feature_tables):
            percentile_interactions = {}
            
            if 'dot' in interaction_types:
                percentile_interactions['dot'] = float(gpu_interactions['dot'][batch_index])
            
            if 'hadamard' in interaction_types:
                hadamard_matrix = gpu_interactions['hadamard'][batch_index]
                percentile_interactions['hadamard'] = self._matrix_to_dict(hadamard_matrix)
            
            if 'cosine' in interaction_types:
                percentile_interactions['cosine'] = float(gpu_interactions['cosine'][batch_index])
            
            phase1[percentile] = percentile_interactions
        
        # Phase 2: Matrix-level interactions
        phase2 = {
            'interactions': {},
            'shape': [len(feature_tables), len(self.batch_processor.feature_names)],
            'percentiles': feature_tables,
            'features': self.batch_processor.feature_names
        }
        
        for interaction_type in interaction_types:
            if interaction_type in gpu_interactions:
                value = gpu_interactions[interaction_type][batch_index]
                if isinstance(value, torch.Tensor):
                    if value.dim() == 0:  # Scalar
                        phase2['interactions'][interaction_type] = float(value)
                    else:  # Matrix
                        phase2['interactions'][interaction_type] = value.cpu().numpy()
                else:
                    phase2['interactions'][interaction_type] = value
        
        rider_result['phase1_interactions'][race_type] = phase1
        rider_result['phase2_interactions'][race_type] = phase2
        
        # Add race count
        rider_history = self.shared_rider_histories.get(rider_result_id, [])
        race_type_history = self._get_race_type_history(rider_history, race_type)
        rider_result['metadata']['n_races'][race_type] = len(race_type_history)
        
        return rider_result
    
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
        """
        Fall back to CPU processing for small batches or when GPU fails.
        """
        results = []
        
        for rider_result_id, competition_id in rider_batch:
            result = self.calculate_interaction_embeddings_optimized(
                rider_result_id, competition_id, feature_tables, interaction_types
            )
            results.append(result)
        
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get hybrid performance statistics."""
        stats = self.performance_stats.copy()
        
        # Add GPU accelerator stats if available
        if self.metal_accelerator:
            gpu_stats = self.metal_accelerator.get_performance_stats()
            stats.update(gpu_stats)
        
        # Add batch processor stats if available
        if self.batch_processor:
            batch_stats = self.batch_processor.get_batch_statistics()
            stats.update(batch_stats)
        
        # Calculate efficiency metrics
        if stats['total_batches_processed'] > 0:
            stats['gpu_usage_ratio'] = stats['gpu_batch_count'] / stats['total_batches_processed']
            stats['cpu_usage_ratio'] = stats['cpu_batch_count'] / stats['total_batches_processed']
            stats['cpu_fallback_ratio'] = stats['cpu_fallback_count'] / stats['total_batches_processed']
        
        # Calculate average times
        if stats['gpu_batch_count'] > 0:
            stats['avg_gpu_batch_time'] = stats['gpu_interaction_time'] / stats['gpu_batch_count']
        
        if stats['cpu_batch_count'] > 0:
            stats['avg_cpu_batch_time'] = stats['cpu_fallback_time'] / stats['cpu_batch_count']
        
        stats['hybrid_approach'] = True
        stats['gpu_available'] = self.gpu_available
        
        return stats
    
    def reset_performance_stats(self):
        """Reset all performance statistics."""
        self.performance_stats = {
            'total_batches_processed': 0,
            'cpu_correlation_time': 0.0,
            'gpu_interaction_time': 0.0,
            'cpu_fallback_time': 0.0,
            'gpu_batch_count': 0,
            'cpu_batch_count': 0,
            'cpu_fallback_count': 0
        }
        
        if self.metal_accelerator:
            self.metal_accelerator.reset_performance_stats()
        
        if self.batch_processor:
            self.batch_processor.reset_statistics()