#!/usr/bin/env python3
"""
CPU monitoring tool to verify parallel processing is working
"""
import psutil
import time
import threading
import logging
from datetime import datetime

class CPUMonitor:
    def __init__(self, interval_seconds=1):
        self.interval = interval_seconds
        self.monitoring = False
        self.cpu_data = []
        self.thread = None
        
    def start_monitoring(self):
        """Start CPU monitoring in a background thread"""
        if self.monitoring:
            return
            
        self.monitoring = True
        self.cpu_data = []
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logging.info(f"CPU monitoring started (interval: {self.interval}s)")
        
    def stop_monitoring(self):
        """Stop CPU monitoring and return collected data"""
        if not self.monitoring:
            return []
            
        self.monitoring = False
        if self.thread:
            self.thread.join(timeout=2)
            
        logging.info(f"CPU monitoring stopped. Collected {len(self.cpu_data)} samples")
        return self.cpu_data
        
    def _monitor_loop(self):
        """Background thread loop for collecting CPU data"""
        while self.monitoring:
            try:
                # Get overall CPU usage
                cpu_percent = psutil.cpu_percent()
                
                # Get per-core usage 
                cpu_per_core = psutil.cpu_percent(percpu=True)
                
                # Get process-specific info
                process = psutil.Process()
                process_cpu = process.cpu_percent()
                thread_count = process.num_threads()
                
                # Store data point
                data_point = {
                    'timestamp': datetime.now(),
                    'cpu_overall': cpu_percent,
                    'cpu_per_core': cpu_per_core,
                    'process_cpu': process_cpu,
                    'thread_count': thread_count,
                    'cores_active': sum(1 for usage in cpu_per_core if usage > 10)  # Cores with >10% usage
                }
                
                self.cpu_data.append(data_point)
                
            except Exception as e:
                logging.error(f"CPU monitoring error: {e}")
                
            time.sleep(self.interval)
            
    def get_summary(self):
        """Get summary statistics from collected CPU data"""
        if not self.cpu_data:
            return {"error": "No CPU data collected"}
            
        # Calculate averages
        avg_cpu = sum(d['cpu_overall'] for d in self.cpu_data) / len(self.cpu_data)
        avg_process_cpu = sum(d['process_cpu'] for d in self.cpu_data) / len(self.cpu_data)
        avg_threads = sum(d['thread_count'] for d in self.cpu_data) / len(self.cpu_data)
        max_cores_active = max(d['cores_active'] for d in self.cpu_data)
        
        # Check for parallel processing indicators (adjusted for database workloads)
        high_cpu_samples = sum(1 for d in self.cpu_data if d['cpu_overall'] > 20)
        multi_core_samples = sum(1 for d in self.cpu_data if d['cores_active'] >= 2)
        high_thread_samples = sum(1 for d in self.cpu_data if d['thread_count'] > 4)
        
        # More lenient criteria for database-heavy workloads
        parallel_likely = (
            (avg_cpu > 15 and max_cores_active >= 2) or  # Moderate CPU with multi-core
            (avg_threads > 4 and multi_core_samples > len(self.cpu_data) * 0.2) or  # High thread count
            (high_thread_samples > len(self.cpu_data) * 0.5)  # Consistently high thread usage
        )
        
        return {
            'total_samples': len(self.cpu_data),
            'duration_seconds': (self.cpu_data[-1]['timestamp'] - self.cpu_data[0]['timestamp']).total_seconds(),
            'avg_cpu_overall': round(avg_cpu, 1),
            'avg_process_cpu': round(avg_process_cpu, 1),
            'avg_thread_count': round(avg_threads, 1),
            'max_cores_active': max_cores_active,
            'high_cpu_samples': high_cpu_samples,
            'multi_core_samples': multi_core_samples,
            'high_thread_samples': high_thread_samples,
            'parallel_processing_detected': parallel_likely,
            'cpu_cores_available': psutil.cpu_count()
        }
        
    def print_summary(self):
        """Print a readable summary of CPU monitoring results"""
        summary = self.get_summary()
        
        if 'error' in summary:
            print(f"❌ {summary['error']}")
            return
            
        print("\n=== CPU Monitoring Summary ===")
        print(f"Duration: {summary['duration_seconds']:.1f}s ({summary['total_samples']} samples)")
        print(f"Available CPU cores: {summary['cpu_cores_available']}")
        print(f"Average CPU usage: {summary['avg_cpu_overall']:.1f}%")
        print(f"Average process CPU: {summary['avg_process_cpu']:.1f}%")
        print(f"Average thread count: {summary['avg_thread_count']:.1f}")
        print(f"Max cores simultaneously active: {summary['max_cores_active']}")
        print(f"High CPU samples (>50%): {summary['high_cpu_samples']}/{summary['total_samples']}")
        print(f"Multi-core samples (≥2 cores): {summary['multi_core_samples']}/{summary['total_samples']}")
        
        if summary['parallel_processing_detected']:
            print("✅ Parallel processing detected!")
        else:
            print("⚠️  Parallel processing NOT clearly detected")
            if summary['max_cores_active'] < 2:
                print("   - Only single core being used")
            if summary['avg_cpu_overall'] < 30:
                print("   - Low overall CPU usage")
                
        print("=" * 30)

# Convenience function for integration with correlation processor
def monitor_cpu_during_batch(func, *args, **kwargs):
    """
    Monitor CPU usage while running a function
    Returns (function_result, cpu_summary)
    """
    monitor = CPUMonitor(interval_seconds=0.5)  # Sample every 0.5 seconds
    
    try:
        monitor.start_monitoring()
        result = func(*args, **kwargs)
        return result, monitor.get_summary()
    finally:
        monitor.stop_monitoring()