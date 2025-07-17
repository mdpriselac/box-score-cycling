"""
Monitoring and progress tracking tools for correlation processing.
Provides real-time monitoring of processing progress and system health.
"""
import sqlite3
import time
import logging
from datetime import datetime
from typing import Dict
from config import ProcessingConfig
from memory_manager import MemoryManager

class ProcessingMonitor:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
    
    def monitor_progress(self, interval: int = 30):
        """Monitor processing progress in real-time"""
        print("=== Real-time Processing Monitor ===")
        print("Press Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                self._display_current_stats()
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
    
    def _display_current_stats(self):
        """Display current processing statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Get latest stats from last hour
            stats = conn.execute("""
                SELECT 
                    MAX(batch_number) as last_batch,
                    SUM(riders_processed) as total_riders,
                    SUM(correlations_calculated) as total_correlations,
                    AVG(processing_time_seconds) as avg_time,
                    AVG(memory_usage_mb) as avg_memory
                FROM processing_log
                WHERE created_at > datetime('now', '-1 hour')
            """).fetchone()
            
            # Get checkpoint info
            checkpoint = conn.execute("""
                SELECT last_processed_competition_id, last_processed_date
                FROM processing_checkpoint
                WHERE checkpoint_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.config.CHECKPOINT_NAME,)).fetchone()
            
            # Get overall progress
            progress = conn.execute("""
                SELECT 
                    COUNT(DISTINCT competition_id) as processed_comps,
                    (SELECT COUNT(*) FROM competitions) as total_comps,
                    COUNT(*) as total_correlations
                FROM rider_correlations_denorm
            """).fetchone()
        
        # Display stats
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n[{timestamp}]")
        print("-" * 50)
        
        if stats[0] is not None:  # Has recent activity
            print(f"Last Batch: {stats[0]}")
            print(f"Recent Riders: {stats[1]:,}")
            print(f"Recent Correlations: {stats[2]:,}")
            print(f"Avg Processing Time: {stats[3]:.2f}s")
            print(f"Avg Memory Usage: {stats[4]:.1f}MB")
        else:
            print("No recent activity detected")
        
        if progress:
            processed, total, correlations = progress
            progress_pct = (processed / total * 100) if total > 0 else 0
            print(f"Overall Progress: {processed:,}/{total:,} competitions ({progress_pct:.1f}%)")
            print(f"Total Correlations: {correlations:,}")
        
        if checkpoint:
            print(f"Last Checkpoint: Competition {checkpoint[0]} at {checkpoint[1]}")
        
        # Memory stats
        memory = MemoryManager.get_memory_stats()
        print(f"System Memory: {memory['used_gb']:.1f}GB/{memory['total_gb']:.1f}GB ({memory['percent_used']:.1f}%)")
        
        print("-" * 50)
    
    def get_detailed_progress_report(self) -> Dict:
        """Get a detailed progress report"""
        with sqlite3.connect(self.db_path) as conn:
            # Processing log summary
            log_stats = conn.execute("""
                SELECT 
                    COUNT(*) as total_batches,
                    SUM(competitions_processed) as total_competitions,
                    SUM(riders_processed) as total_riders,
                    SUM(correlations_calculated) as total_correlations,
                    AVG(processing_time_seconds) as avg_batch_time,
                    MAX(memory_usage_mb) as peak_memory,
                    MIN(created_at) as start_time,
                    MAX(created_at) as last_activity
                FROM processing_log
            """).fetchone()
            
            # Correlation type breakdown
            corr_breakdown = conn.execute("""
                SELECT 
                    correlation_type,
                    COUNT(DISTINCT rider_id) as unique_riders,
                    COUNT(DISTINCT competition_id) as unique_competitions,
                    COUNT(*) as total_values,
                    AVG(race_count) as avg_race_count
                FROM rider_correlations_denorm
                GROUP BY correlation_type
            """).fetchall()
            
            # Recent performance (last 10 batches)
            recent_perf = conn.execute("""
                SELECT 
                    AVG(processing_time_seconds) as avg_time,
                    AVG(correlations_calculated) as avg_correlations,
                    AVG(memory_usage_mb) as avg_memory
                FROM (
                    SELECT * FROM processing_log 
                    ORDER BY created_at DESC 
                    LIMIT 10
                )
            """).fetchone()
            
            # Thresholds info
            thresholds = conn.execute("""
                SELECT threshold_name, percentile, min_races
                FROM race_history_thresholds
                ORDER BY threshold_name
            """).fetchall()
        
        return {
            'log_stats': {
                'total_batches': log_stats[0],
                'total_competitions': log_stats[1], 
                'total_riders': log_stats[2],
                'total_correlations': log_stats[3],
                'avg_batch_time': log_stats[4],
                'peak_memory_mb': log_stats[5],
                'start_time': log_stats[6],
                'last_activity': log_stats[7]
            },
            'correlation_breakdown': [
                {
                    'type': row[0],
                    'unique_riders': row[1],
                    'unique_competitions': row[2],
                    'total_values': row[3],
                    'avg_race_count': row[4]
                } for row in corr_breakdown
            ],
            'recent_performance': {
                'avg_time': recent_perf[0],
                'avg_correlations': recent_perf[1],
                'avg_memory_mb': recent_perf[2]
            },
            'thresholds': [
                {
                    'name': row[0],
                    'percentile': row[1], 
                    'min_races': row[2]
                } for row in thresholds
            ]
        }
    
    def export_progress_report(self, filename: str = None):
        """Export a detailed progress report to file"""
        if filename is None:
            filename = f"progress_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        report = self.get_detailed_progress_report()
        
        with open(filename, 'w') as f:
            f.write("=== Rider Correlation Processing Report ===\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Overall stats
            f.write("OVERALL STATISTICS\n")
            f.write("-" * 40 + "\n")
            log_stats = report['log_stats']
            f.write(f"Total Batches Processed: {log_stats['total_batches']:,}\n")
            f.write(f"Total Competitions: {log_stats['total_competitions']:,}\n")
            f.write(f"Total Riders: {log_stats['total_riders']:,}\n")
            f.write(f"Total Correlations: {log_stats['total_correlations']:,}\n")
            f.write(f"Average Batch Time: {log_stats['avg_batch_time']:.2f}s\n")
            f.write(f"Peak Memory Usage: {log_stats['peak_memory_mb']:.1f}MB\n")
            f.write(f"Processing Started: {log_stats['start_time']}\n")
            f.write(f"Last Activity: {log_stats['last_activity']}\n\n")
            
            # Correlation breakdown
            f.write("CORRELATION TYPE BREAKDOWN\n")
            f.write("-" * 40 + "\n")
            for corr in report['correlation_breakdown']:
                f.write(f"{corr['type']}:\n")
                f.write(f"  Unique Riders: {corr['unique_riders']:,}\n")
                f.write(f"  Unique Competitions: {corr['unique_competitions']:,}\n")
                f.write(f"  Total Values: {corr['total_values']:,}\n")
                f.write(f"  Avg Race Count: {corr['avg_race_count']:.1f}\n\n")
            
            # Thresholds
            f.write("RACE HISTORY THRESHOLDS\n")
            f.write("-" * 40 + "\n")
            for threshold in report['thresholds']:
                f.write(f"{threshold['name']}: Top {threshold['percentile']:.0f}% (>= {threshold['min_races']} races)\n")
        
        print(f"Progress report exported to {filename}")

def main():
    """Main function for running monitor"""
    import sys
    
    config = ProcessingConfig()
    monitor = ProcessingMonitor(config.DB_PATH, config)
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "report":
            monitor.export_progress_report()
        elif sys.argv[1] == "watch":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            monitor.monitor_progress(interval)
        else:
            print("Usage: python monitor.py [report|watch [interval]]")
    else:
        monitor.monitor_progress()

if __name__ == "__main__":
    main()