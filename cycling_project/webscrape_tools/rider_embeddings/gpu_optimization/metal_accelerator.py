"""
Metal Performance Shaders (MPS) Accelerator for Interaction Embeddings

This module provides GPU acceleration for matrix operations using Apple's MPS
through PyTorch. It handles batch processing of interaction computations only.

Key features:
- Automatic GPU detection and fallback
- Parallel interaction computations (dot, Hadamard, cosine)
- Memory-efficient tensor operations
- Performance monitoring and benchmarking

Note: Correlation calculations are handled by CPU for better performance.
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
import logging
import time


class MetalAccelerator:
    """
    GPU accelerator using Apple Metal Performance Shaders for matrix operations.
    
    This class provides GPU-accelerated versions of the core mathematical operations
    used in interaction embeddings calculation.
    """
    
    def __init__(self, enable_gpu: bool = True, batch_size: int = 50):
        """
        Initialize the Metal accelerator.
        
        Args:
            enable_gpu: Whether to enable GPU acceleration
            batch_size: Default batch size for GPU operations
        """
        self.logger = logging.getLogger(__name__)
        self.batch_size = batch_size
        
        # Check MPS availability
        self.mps_available = torch.backends.mps.is_available()
        self.gpu_enabled = enable_gpu and self.mps_available
        
        if self.gpu_enabled:
            self.device = torch.device('mps')
            self.logger.info("Metal GPU acceleration enabled")
        else:
            self.device = torch.device('cpu')
            if enable_gpu and not self.mps_available:
                self.logger.warning("MPS not available, falling back to CPU")
            else:
                self.logger.info("GPU acceleration disabled, using CPU")
        
        # Performance tracking
        self.performance_stats = {
            'gpu_operations': 0,
            'cpu_fallbacks': 0,
            'total_gpu_time': 0.0,
            'total_cpu_time': 0.0
        }
    
    def is_gpu_available(self) -> bool:
        """Check if GPU acceleration is available and enabled."""
        return self.gpu_enabled
    
    
    
    
    
    
    def batch_interaction_calculations(
        self,
        race_features: torch.Tensor,      # [batch_size, n_percentiles, n_features]
        correlations: torch.Tensor        # [batch_size, n_percentiles, n_features]
    ) -> Dict[str, torch.Tensor]:
        """
        Calculate all interaction types in parallel on GPU.
        
        Args:
            race_features: Current race features [batch_size, n_percentiles, n_features]
            correlations: Historical correlations [batch_size, n_percentiles, n_features]
            
        Returns:
            Dictionary with interaction results
        """
        if not self.gpu_enabled:
            return self._cpu_interaction_calculations(race_features, correlations)
        
        start_time = time.time()
        
        try:
            # Move to GPU if not already there
            if race_features.device != self.device:
                race_features = race_features.to(self.device)
            if correlations.device != self.device:
                correlations = correlations.to(self.device)
            
            results = {}
            
            # Dot products (Frobenius inner product)
            results['dot'] = torch.sum(race_features * correlations, dim=(1, 2))
            
            # Hadamard products (element-wise multiplication)
            results['hadamard'] = race_features * correlations
            
            # Cosine similarity (normalized dot product)
            results['cosine'] = self._batch_cosine_similarity(race_features, correlations)
            
            self.performance_stats['gpu_operations'] += 1
            self.performance_stats['total_gpu_time'] += time.time() - start_time
            
            return results
            
        except Exception as e:
            self.logger.warning(f"GPU interaction calculation failed: {e}, falling back to CPU")
            self.performance_stats['cpu_fallbacks'] += 1
            return self._cpu_interaction_calculations(race_features, correlations)
    
    def _batch_cosine_similarity(
        self, 
        race_features: torch.Tensor, 
        correlations: torch.Tensor
    ) -> torch.Tensor:
        """Calculate cosine similarity between flattened matrices."""
        # Flatten matrices for cosine calculation
        flat_features = race_features.flatten(start_dim=1)  # [batch_size, n_elements]
        flat_correlations = correlations.flatten(start_dim=1)  # [batch_size, n_elements]
        
        # Calculate norms
        features_norm = torch.norm(flat_features, p=2, dim=1)
        correlations_norm = torch.norm(flat_correlations, p=2, dim=1)
        
        # Calculate dot products
        dot_products = torch.sum(flat_features * flat_correlations, dim=1)
        
        # Calculate cosine similarity
        denominator = features_norm * correlations_norm
        cosine_sim = torch.where(
            denominator > 1e-10,
            dot_products / denominator,
            torch.tensor(0.0, device=race_features.device)
        )
        
        return cosine_sim
    
    def _cpu_interaction_calculations(
        self, 
        race_features: torch.Tensor, 
        correlations: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """CPU fallback for interaction calculations."""
        start_time = time.time()
        
        results = {}
        
        # Convert to CPU if needed
        race_features = race_features.cpu()
        correlations = correlations.cpu()
        
        # Dot products
        results['dot'] = torch.sum(race_features * correlations, dim=(1, 2))
        
        # Hadamard products
        results['hadamard'] = race_features * correlations
        
        # Cosine similarity
        results['cosine'] = self._batch_cosine_similarity(race_features, correlations)
        
        self.performance_stats['total_cpu_time'] += time.time() - start_time
        return results
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for monitoring."""
        stats = self.performance_stats.copy()
        
        if stats['gpu_operations'] > 0:
            stats['avg_gpu_time'] = stats['total_gpu_time'] / stats['gpu_operations']
        else:
            stats['avg_gpu_time'] = 0.0
        
        if stats['cpu_fallbacks'] > 0:
            stats['avg_cpu_time'] = stats['total_cpu_time'] / stats['cpu_fallbacks']
        else:
            stats['avg_cpu_time'] = 0.0
        
        stats['gpu_enabled'] = self.gpu_enabled
        stats['mps_available'] = self.mps_available
        stats['device'] = str(self.device)
        
        return stats
    
    def reset_performance_stats(self):
        """Reset performance statistics."""
        self.performance_stats = {
            'gpu_operations': 0,
            'cpu_fallbacks': 0,
            'total_gpu_time': 0.0,
            'total_cpu_time': 0.0
        }
    
    def benchmark_gpu_vs_cpu(self, batch_size: int = 32, n_races: int = 100, n_features: int = 37) -> Dict[str, float]:
        """
        Benchmark GPU vs CPU performance.
        
        Args:
            batch_size: Number of riders in batch
            n_races: Number of races per rider
            n_features: Number of features per race
            
        Returns:
            Performance comparison results
        """
        # Create test data
        performance_data = torch.randn(batch_size, n_races)
        features_data = torch.randn(batch_size, n_races, n_features)
        
        # Test GPU performance (interaction calculations only)
        if self.gpu_enabled:
            gpu_start = time.time()
            # Create test interaction data
            race_features = torch.randn(batch_size, 8, n_features)  # 8 percentiles
            correlations = torch.randn(batch_size, 8, n_features)
            
            gpu_results = self.batch_interaction_calculations(
                race_features.to(self.device),
                correlations.to(self.device)
            )
            gpu_time = time.time() - gpu_start
        else:
            gpu_time = float('inf')
        
        # Test CPU performance (interaction calculations only)
        cpu_start = time.time()
        race_features = torch.randn(batch_size, 8, n_features)
        correlations = torch.randn(batch_size, 8, n_features)
        cpu_results = self._cpu_interaction_calculations(race_features, correlations)
        cpu_time = time.time() - cpu_start
        
        return {
            'gpu_time': gpu_time,
            'cpu_time': cpu_time,
            'speedup': cpu_time / gpu_time if gpu_time > 0 else 0.0,
            'gpu_available': self.gpu_enabled
        }