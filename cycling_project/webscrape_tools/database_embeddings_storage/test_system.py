"""
Test script for the correlation processing system.
Validates the complete pipeline with a small batch before full processing.
"""
import logging
import sys
import os
from datetime import datetime

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import ProcessingConfig
from threshold_calculator import ThresholdCalculator
from race_features_loader import RaceFeaturesLoader
from correlation_processor import CorrelationProcessor
from checkpoint_manager import CheckpointManager
from memory_manager import MemoryManager

def setup_test_logging():
    """Setup logging for testing"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

def test_database_connection():
    """Test database connection and basic queries"""
    print("Testing database connection...")
    
    config = ProcessingConfig()
    
    try:
        import sqlite3
        with sqlite3.connect(config.DB_PATH) as conn:
            # Test basic queries
            competitions = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()[0]
            riders = conn.execute("SELECT COUNT(*) FROM riders").fetchone()[0]
            results = conn.execute("SELECT COUNT(*) FROM rider_results").fetchone()[0]
            
            print(f"✓ Database connected successfully")
            print(f"  Competitions: {competitions:,}")
            print(f"  Riders: {riders:,}")
            print(f"  Rider Results: {results:,}")
            
            # Check race features tables
            feature_tables = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name LIKE 'race_features_%'
                ORDER BY name
            """).fetchall()
            
            print(f"  Race Feature Tables: {len(feature_tables)}")
            for table in feature_tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {table[0]}").fetchone()[0]
                print(f"    {table[0]}: {count:,} records")
            
            return True
            
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def test_threshold_calculation():
    """Test threshold calculation system"""
    print("\nTesting threshold calculation...")
    
    config = ProcessingConfig()
    calculator = ThresholdCalculator(config.DB_PATH, config)
    
    try:
        # Calculate thresholds
        thresholds = calculator.calculate_thresholds()
        
        print("✓ Thresholds calculated successfully:")
        for column, threshold in thresholds.items():
            print(f"  {column}: {threshold} races")
        
        # Validate thresholds
        if calculator.validate_thresholds():
            print("✓ Threshold validation passed")
        else:
            print("✗ Threshold validation failed")
            return False
        
        # Get summary
        summary = calculator.get_thresholds_summary()
        print("✓ Threshold summary generated")
        
        return True
        
    except Exception as e:
        print(f"✗ Threshold calculation failed: {e}")
        return False

def test_race_features_loading():
    """Test race features loading system"""
    print("\nTesting race features loading...")
    
    config = ProcessingConfig()
    loader = RaceFeaturesLoader(config.DB_PATH, config)
    
    try:
        # Load features
        features_cache = loader.preload_race_features()
        
        print(f"✓ Loaded features for {len(features_cache)} competitions")
        
        # Validate cache
        if loader.validate_features_cache():
            print("✓ Features cache validation passed")
        else:
            print("✗ Features cache validation failed")
            return False
        
        # Get stats
        stats = loader.get_cache_stats()
        print(f"✓ Cache stats: {stats}")
        
        # Test a specific competition
        if features_cache:
            sample_comp_id = next(iter(features_cache.keys()))
            sample_features = loader.get_race_features(sample_comp_id)
            print(f"✓ Sample features shape: {sample_features.shape}")
        
        return True
        
    except Exception as e:
        print(f"✗ Race features loading failed: {e}")
        return False

def test_small_batch_processing():
    """Test processing with a very small batch"""
    print("\nTesting small batch processing...")
    
    config = ProcessingConfig()
    # Override config for small test
    config.COMPETITION_BATCH_SIZE = 2
    config.CHECKPOINT_FREQUENCY = 1
    
    processor = CorrelationProcessor(config.DB_PATH, config)
    
    try:
        # Get a few competitions to test
        import sqlite3
        with sqlite3.connect(config.DB_PATH) as conn:
            test_competitions = conn.execute("""
                SELECT DISTINCT c.id as competition_id, c.date as competition_date, c.competition_type
                FROM competitions c
                JOIN rider_results rr ON c.id = rr.competition_id
                WHERE rr.total_prior_races > 0
                ORDER BY c.date
                LIMIT 3
            """).fetchall()
        
        if not test_competitions:
            print("✗ No suitable test competitions found")
            return False
        
        print(f"✓ Found {len(test_competitions)} test competitions")
        
        # Calculate thresholds
        processor.threshold_calculator.calculate_thresholds()
        
        # Load features
        processor.features_loader.preload_race_features()
        
        # Process one small batch
        test_batch = [{'competition_id': r[0], 'competition_date': r[1], 'race_type': r[2]} 
                     for r in test_competitions]
        
        results = processor._process_competition_batch(test_batch)
        
        print(f"✓ Processed batch, got {len(results)} correlation results")
        
        if results:
            # Test writing results
            processor._write_results_batch(results[:2])  # Write just first 2
            print("✓ Successfully wrote test results to database")
            
            # Verify data was written
            with sqlite3.connect(config.DB_PATH) as conn:
                denorm_count = conn.execute("SELECT COUNT(*) FROM rider_correlations_denorm").fetchone()[0]
                blob_count = conn.execute("SELECT COUNT(*) FROM rider_correlations_blob").fetchone()[0]
                
                print(f"✓ Verification: {denorm_count} denormalized records, {blob_count} blob records")
        
        return True
        
    except Exception as e:
        print(f"✗ Small batch processing failed: {e}")
        logging.exception("Detailed error:")
        return False

def test_checkpoint_system():
    """Test checkpoint and resume functionality"""
    print("\nTesting checkpoint system...")
    
    config = ProcessingConfig()
    manager = CheckpointManager(config.DB_PATH, config)
    
    try:
        # Clear any existing checkpoints
        manager.clear_checkpoints()
        
        # Save a test checkpoint
        test_comp_id = 100
        manager.save_checkpoint(test_comp_id)
        print("✓ Checkpoint saved")
        
        # Load checkpoint
        checkpoint = manager.load_checkpoint()
        if checkpoint and checkpoint['last_competition_id'] == test_comp_id:
            print("✓ Checkpoint loaded successfully")
        else:
            print("✗ Checkpoint loading failed")
            return False
        
        # Get progress stats
        stats = manager.get_progress_stats()
        print(f"✓ Progress stats: {stats['progress_percent']:.1f}% complete")
        
        return True
        
    except Exception as e:
        print(f"✗ Checkpoint system test failed: {e}")
        return False

def cleanup_test_data():
    """Clean up any test data created during testing"""
    print("\nCleaning up test data...")
    
    config = ProcessingConfig()
    
    try:
        import sqlite3
        with sqlite3.connect(config.DB_PATH) as conn:
            # Remove test correlation data
            conn.execute("DELETE FROM rider_correlations_denorm")
            conn.execute("DELETE FROM rider_correlations_blob")
            conn.execute("DELETE FROM processing_checkpoint")
            conn.execute("DELETE FROM processing_log")
            conn.commit()
        
        print("✓ Test data cleaned up")
        return True
        
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=== Correlation Processing System Test ===")
    
    setup_test_logging()
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Threshold Calculation", test_threshold_calculation),
        ("Race Features Loading", test_race_features_loading),
        ("Small Batch Processing", test_small_batch_processing),
        ("Checkpoint System", test_checkpoint_system)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        
        try:
            if test_func():
                passed += 1
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
            logging.exception("Detailed error:")
    
    # Cleanup
    cleanup_test_data()
    
    print(f"\n{'='*50}")
    print(f"TEST SUMMARY: {passed}/{total} tests passed")
    print('='*50)
    
    if passed == total:
        print("🎉 All tests passed! System is ready for full processing.")
        return 0
    else:
        print("❌ Some tests failed. Please fix issues before running full processing.")
        return 1

if __name__ == "__main__":
    sys.exit(main())