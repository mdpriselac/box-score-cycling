"""
Memory management utilities for the correlation processing system.
Monitors memory usage and optimizes performance for M1 Pro systems.
"""
import psutil
import logging
from typing import Dict, Any

class MemoryManager:
    @staticmethod
    def check_memory_pressure(threshold_gb: float = 12.0) -> bool:
        """Check if memory usage is approaching threshold"""
        memory = psutil.virtual_memory()
        used_gb = memory.used / (1024 ** 3)
        return used_gb > threshold_gb
    
    @staticmethod
    def get_memory_stats() -> Dict[str, float]:
        """Get current memory statistics"""
        memory = psutil.virtual_memory()
        return {
            'total_gb': memory.total / (1024 ** 3),
            'used_gb': memory.used / (1024 ** 3),
            'available_gb': memory.available / (1024 ** 3),
            'percent_used': memory.percent
        }
    
    @staticmethod
    def optimize_race_features_cache(cache: Dict, max_size: int = 5000) -> Dict:
        """Optimize race features cache if it grows too large"""
        if len(cache) > max_size:
            # Keep most recent competitions
            sorted_comps = sorted(cache.keys(), reverse=True)
            keep_comps = sorted_comps[:max_size]
            
            new_cache = {comp_id: cache[comp_id] for comp_id in keep_comps}
            
            removed = len(cache) - len(new_cache)
            logging.info(f"Removed {removed} old competitions from cache")
            
            return new_cache
        
        return cache
    
    @staticmethod
    def log_memory_usage(context: str = ""):
        """Log current memory usage with context"""
        stats = MemoryManager.get_memory_stats()
        logging.info(f"Memory usage {context}: {stats['used_gb']:.1f}GB/{stats['total_gb']:.1f}GB ({stats['percent_used']:.1f}%)")
    
    @staticmethod
    def should_force_gc(threshold_percent: float = 85.0) -> bool:
        """Determine if garbage collection should be forced"""
        memory = psutil.virtual_memory()
        return memory.percent > threshold_percent
    
    @staticmethod
    def estimate_batch_memory(batch_size: int, features_per_comp: int = 280) -> float:
        """Estimate memory requirements for a batch"""
        # Rough estimate: 8 bytes per float, plus overhead
        estimated_mb = (batch_size * features_per_comp * 8 * 2) / (1024 * 1024)  # 2x for safety
        return estimated_mb
    
    @staticmethod
    def get_optimal_batch_size(available_memory_gb: float, max_batch_size: int = 200) -> int:
        """Calculate optimal batch size based on available memory"""
        # Reserve 2GB for system and other processes
        usable_memory_gb = max(0.5, available_memory_gb - 2.0)
        
        # Estimate memory per competition processing
        memory_per_comp_mb = 2.0  # Conservative estimate
        max_comps_by_memory = int((usable_memory_gb * 1024) / memory_per_comp_mb)
        
        optimal_size = min(max_batch_size, max_comps_by_memory)
        return max(10, optimal_size)  # Minimum batch size of 10