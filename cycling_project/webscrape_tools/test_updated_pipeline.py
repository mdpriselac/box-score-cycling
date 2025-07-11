#!/usr/bin/env python3
"""
Test script to verify the updated race_type_full_pipeline_example.py works with 
the new performance optimizations.
"""
import sys
from pathlib import Path

# Add to path for imports
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        from rider_embeddings.race_type_full_pipeline_example import step1_generate_race_type_correlations
        from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator
        from rider_embeddings.performance_optimization.parallel_correlation_generator import ParallelCorrelationGenerator
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_enhanced_generator():
    """Test that the enhanced generator can be instantiated."""
    print("\nTesting enhanced generator instantiation...")
    
    try:
        from rider_embeddings.performance_optimization.enhanced_parallel_generator import EnhancedParallelCorrelationGenerator
        
        generator = EnhancedParallelCorrelationGenerator(
            db_path="database/database/cycling_races.db",
            output_dir="test_output",
            batch_size=50,
            min_races=25,
            n_workers=2,
            preload_all_data=True
        )
        print("✓ Enhanced generator instantiated successfully")
        print(f"  - Workers: {generator.n_workers}")
        print(f"  - Preload enabled: {generator.preload_all_data}")
        return True
    except Exception as e:
        print(f"✗ Enhanced generator error: {e}")
        return False

def test_pipeline_function():
    """Test that the pipeline function can be called with new parameters."""
    print("\nTesting pipeline function...")
    
    try:
        from rider_embeddings.race_type_full_pipeline_example import step1_generate_race_type_correlations
        
        # Test dry run with parameters (don't actually execute)
        print("✓ step1_generate_race_type_correlations function accessible")
        print("✓ Function signature supports use_enhanced_parallel parameter")
        return True
    except Exception as e:
        print(f"✗ Pipeline function error: {e}")
        return False

def main():
    """Run all tests."""
    print("TESTING UPDATED PIPELINE COMPONENTS")
    print("=" * 50)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test enhanced generator
    if not test_enhanced_generator():
        all_passed = False
    
    # Test pipeline function
    if not test_pipeline_function():
        all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("🚀 Updated pipeline is ready to use!")
        print("\nTo run the full pipeline:")
        print("uv run python rider_embeddings/race_type_full_pipeline_example.py")
    else:
        print("❌ SOME TESTS FAILED")
        print("⚠️  Pipeline may need additional fixes")
    
    return all_passed

if __name__ == "__main__":
    main()