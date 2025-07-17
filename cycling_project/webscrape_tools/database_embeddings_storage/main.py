"""
Main processing script for rider correlation database migration.
Entry point for running the complete correlation processing pipeline.
"""
import logging
import sys
import os
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ProcessingConfig
from correlation_processor import CorrelationProcessor
from threshold_calculator import ThresholdCalculator
from memory_manager import MemoryManager

def setup_logging():
    """Configure logging for the processing pipeline"""
    log_filename = f"correlation_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    
    logging.info(f"Logging initialized. Log file: {log_filename}")

def validate_environment():
    """Validate that the environment is ready for processing"""
    # Check memory
    memory_stats = MemoryManager.get_memory_stats()
    logging.info(f"System memory: {memory_stats['total_gb']:.1f}GB total, {memory_stats['available_gb']:.1f}GB available")
    
    if memory_stats['available_gb'] < 4.0:
        logging.warning("Low available memory. Consider closing other applications.")
    
    # Check database exists
    config = ProcessingConfig()
    if not os.path.exists(config.DB_PATH):
        logging.error(f"Database not found at {config.DB_PATH}")
        return False
    
    logging.info(f"Database found at {config.DB_PATH}")
    return True

def main():
    """Main entry point for correlation processing"""
    print("=== Rider Correlation Database Migration ===")
    print("Setting up logging...")
    setup_logging()
    
    logging.info("Starting rider correlation processing pipeline")
    
    # Validate environment
    if not validate_environment():
        logging.error("Environment validation failed")
        return 1
    
    # Initialize configuration
    config = ProcessingConfig()
    logging.info(f"Configuration initialized with {len(config.PERCENTILES)} percentiles and {config.NUM_FEATURES} features")
    
    # Log memory before starting
    MemoryManager.log_memory_usage("at startup")
    
    try:
        # Create processor
        processor = CorrelationProcessor(
            db_path=config.DB_PATH,
            config=config
        )
        
        # Run processing (will automatically resume if interrupted)
        logging.info("Starting correlation processing...")
        processor.run(resume=True)
        
        logging.info("=== Processing completed successfully ===")
        
        # Log final statistics
        stats = processor.checkpoint_manager.get_progress_stats()
        logging.info(f"Final stats: {stats['processed_competitions']}/{stats['total_competitions']} competitions processed ({stats['progress_percent']:.1f}%)")
        
        return 0
        
    except KeyboardInterrupt:
        logging.info("Processing interrupted by user. Checkpoint saved for resume.")
        return 0
        
    except Exception as e:
        logging.error(f"Processing failed with error: {str(e)}", exc_info=True)
        return 1
    
    finally:
        MemoryManager.log_memory_usage("at shutdown")

def view_progress():
    """View current processing progress"""
    config = ProcessingConfig()
    from checkpoint_manager import CheckpointManager
    
    checkpoint_manager = CheckpointManager(config.DB_PATH, config)
    stats = checkpoint_manager.get_progress_stats()
    
    print("=== Processing Progress ===")
    print(f"Total competitions: {stats['total_competitions']}")
    print(f"Processed: {stats['processed_competitions']}")
    print(f"Remaining: {stats['remaining_competitions']}")
    print(f"Progress: {stats['progress_percent']:.1f}%")
    
    if stats['latest_checkpoint']:
        print(f"Latest checkpoint: Competition {stats['latest_checkpoint']['last_competition_id']}")
        print(f"Last processed: {stats['latest_checkpoint']['last_processed_date']}")

def view_thresholds():
    """View calculated thresholds"""
    config = ProcessingConfig()
    calculator = ThresholdCalculator(config.DB_PATH, config)
    
    try:
        summary = calculator.get_thresholds_summary()
        
        print("=== Calculated Race History Thresholds ===")
        print("-" * 60)
        print(f"{'Column':<25} {'Percentile':<12} {'Min Races':<10} {'Eligible':<10}")
        print("-" * 60)
        
        for column, data in summary.items():
            print(f"{column:<25} Top {data['percentile']:<8.0f}% {data['min_races']:<10} {data['eligible_results']:<10,}")
        
    except Exception as e:
        print(f"Error viewing thresholds: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "progress":
            view_progress()
        elif sys.argv[1] == "thresholds":
            view_thresholds()
        else:
            print("Usage: python main.py [progress|thresholds]")
            sys.exit(1)
    else:
        sys.exit(main())