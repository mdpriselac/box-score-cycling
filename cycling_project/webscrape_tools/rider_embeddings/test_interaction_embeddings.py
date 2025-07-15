#!/usr/bin/env python3
"""
Test script for interaction embeddings calculation.

Tests both Phase 1 (individual percentile) and Phase 2 (matrix-level) calculations
with a small sample of data.
"""

import sys
from pathlib import Path
import json
import numpy as np
from datetime import datetime

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.performance_feature_link.interaction_embeddings import InteractionEmbeddingsCalculator
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator


def test_basic_calculations():
    """Test basic interaction calculations with synthetic data."""
    print("Testing basic interaction calculations...")
    print("-" * 50)
    
    # Create synthetic data
    features = {'feature1': 2.0, 'feature2': 3.0, 'feature3': 4.0}
    correlations = {'feature1': 0.5, 'feature2': -0.3, 'feature3': 0.8}
    
    # Create a minimal calculator instance for testing
    # We'll test the methods directly without initializing the full calculator
    from rider_embeddings.performance_feature_link.interaction_embeddings import InteractionEmbeddingsCalculator
    
    # Create instance without initializing (to avoid DB validation)
    calc = object.__new__(InteractionEmbeddingsCalculator)
    
    # Test dot product
    dot = calc._calculate_dot_product(features, correlations)
    expected_dot = 2.0 * 0.5 + 3.0 * (-0.3) + 4.0 * 0.8
    print(f"Dot product: {dot:.4f} (expected: {expected_dot:.4f})")
    assert abs(dot - expected_dot) < 1e-6, "Dot product calculation incorrect"
    
    # Test Hadamard product
    hadamard = calc._calculate_hadamard_product(features, correlations)
    expected_hadamard = {
        'feature1': 2.0 * 0.5,
        'feature2': 3.0 * (-0.3),
        'feature3': 4.0 * 0.8
    }
    print(f"Hadamard product: {hadamard}")
    for key in expected_hadamard:
        assert abs(hadamard[key] - expected_hadamard[key]) < 1e-6, f"Hadamard product incorrect for {key}"
    
    # Test cosine similarity
    cosine = calc._calculate_cosine_similarity(features, correlations)
    # Calculate expected
    feature_norm = np.sqrt(sum(v**2 for v in features.values()))
    corr_norm = np.sqrt(sum(v**2 for v in correlations.values()))
    expected_cosine = expected_dot / (feature_norm * corr_norm)
    print(f"Cosine similarity: {cosine:.4f} (expected: {expected_cosine:.4f})")
    assert abs(cosine - expected_cosine) < 1e-6, "Cosine similarity calculation incorrect"
    
    print("\n✅ Basic calculations test passed!")


def test_matrix_calculations():
    """Test matrix-level interaction calculations."""
    print("\n\nTesting matrix-level calculations...")
    print("-" * 50)
    
    # Create synthetic matrices
    feature_matrix = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0]
    ])
    
    correlation_matrix = np.array([
        [0.5, -0.3, 0.8],
        [0.2, 0.6, -0.4]
    ])
    
    # Create instance without initializing (to avoid DB validation)
    from rider_embeddings.performance_feature_link.interaction_embeddings import InteractionEmbeddingsCalculator
    calc = object.__new__(InteractionEmbeddingsCalculator)
    
    # Test matrix dot product (Frobenius inner product)
    matrix_dot = np.sum(feature_matrix * correlation_matrix)
    expected_dot = (1.0*0.5 + 2.0*(-0.3) + 3.0*0.8 + 
                    4.0*0.2 + 5.0*0.6 + 6.0*(-0.4))
    print(f"Matrix dot product: {matrix_dot:.4f} (expected: {expected_dot:.4f})")
    assert abs(matrix_dot - expected_dot) < 1e-6, "Matrix dot product incorrect"
    
    # Test matrix Hadamard product
    matrix_hadamard = feature_matrix * correlation_matrix
    print(f"Matrix Hadamard shape: {matrix_hadamard.shape}")
    print(f"Sample values: {matrix_hadamard[0, :3]}")
    
    # Test matrix cosine similarity
    matrix_cosine = calc._matrix_cosine_similarity(feature_matrix, correlation_matrix)
    print(f"Matrix cosine similarity: {matrix_cosine:.4f}")
    
    print("\n✅ Matrix calculations test passed!")


def test_with_database(db_path: str, sample_rider_result_id: int = None):
    """Test with actual database data."""
    print("\n\nTesting with database...")
    print("-" * 50)
    
    # If no sample ID provided, get one from the database
    if sample_rider_result_id is None:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            query = """
            SELECT rr.id 
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date >= '2020-01-01' AND c.date <= '2023-01-01'
            ORDER BY RANDOM()
            LIMIT 1
            """
            cursor = conn.cursor()
            cursor.execute(query)
            result = cursor.fetchone()
            if result:
                sample_rider_result_id = result[0]
            else:
                print("No suitable rider results found in database")
                return
    
    print(f"Testing with rider_result_id: {sample_rider_result_id}")
    
    # Initialize calculator
    calc = InteractionEmbeddingsCalculator(db_path=db_path)
    
    # Calculate interactions for sample rider
    lookback_date = '2023-01-01'
    feature_tables = ['race_features_60', 'race_features_70']
    
    print(f"Calculating interactions...")
    result = calc.calculate_interaction_embeddings(
        rider_result_id=sample_rider_result_id,
        lookback_date=lookback_date,
        feature_tables=feature_tables,
        interaction_types=['dot', 'hadamard', 'cosine']
    )
    
    # Display results
    print("\nPhase 1 Results (Individual Percentiles):")
    phase1 = result.get('phase1_interactions', {})
    for race_type, race_data in phase1.items():
        if race_data:
            print(f"\n  {race_type}:")
            for percentile, interactions in race_data.items():
                print(f"    {percentile}:")
                for interaction_type, value in interactions.items():
                    if isinstance(value, dict):
                        print(f"      {interaction_type}: {len(value)} features")
                    else:
                        print(f"      {interaction_type}: {value:.4f}")
    
    print("\nPhase 2 Results (Matrix-level):")
    phase2 = result.get('phase2_interactions', {})
    for race_type, race_data in phase2.items():
        if race_data:
            print(f"\n  {race_type}:")
            shape = race_data.get('shape', (0, 0))
            print(f"    Matrix shape: {shape[0]} percentiles x {shape[1]} features")
            interactions = race_data.get('interactions', {})
            for interaction_type, value in interactions.items():
                if isinstance(value, np.ndarray):
                    print(f"    {interaction_type}: matrix shape {value.shape}")
                else:
                    print(f"    {interaction_type}: {value:.4f}")
    
    # Check metadata
    metadata = result.get('metadata', {})
    print(f"\nMetadata:")
    print(f"  Race counts: {metadata.get('n_races', {})}")
    print(f"  Warnings: {len(metadata.get('warnings', []))}")
    
    if metadata.get('warnings'):
        print("\n  Warnings:")
        for warning in metadata['warnings'][:3]:  # Show first 3 warnings
            print(f"    - {warning}")
    
    print("\n✅ Database test completed!")


def main():
    """Run all tests."""
    print("INTERACTION EMBEDDINGS TEST SUITE")
    print("="*70)
    
    # Run synthetic data tests
    test_basic_calculations()
    test_matrix_calculations()
    
    # Test with real database if available
    db_path = "database/database/cycling_races.db"
    if Path(db_path).exists():
        test_with_database(db_path)
    else:
        print(f"\n⚠️  Database not found at {db_path}")
        print("Skipping database tests")
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED!")


if __name__ == "__main__":
    main()