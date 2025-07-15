#!/usr/bin/env python3
"""
Interaction-based Rider Embeddings Calculator

This module creates rider embeddings based on interactions between race features
and correlations between rider performance and race features.

Two phases of interaction calculation:
1. Individual Percentiles: Calculate interactions for each percentile separately
2. All Percentiles: Calculate interactions across all percentiles as matrices

Interaction types:
- Dot product
- Hadamard product (element-wise)
- Cosine similarity (normalized dot product)
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import warnings
from pathlib import Path
import sqlite3
import json
import logging
from tqdm import tqdm

from .race_type_correlation_method import RaceTypeCorrelationCalculator


class InteractionEmbeddingsCalculator:
    """
    Calculate interaction-based rider embeddings combining race features
    with performance correlations.
    """
    
    def __init__(
        self, 
        db_path: str,
        correlation_calculator: Optional[RaceTypeCorrelationCalculator] = None,
        min_races_config: Optional[Dict[str, int]] = None
    ):
        """
        Initialize the interaction embeddings calculator.
        
        Args:
            db_path: Path to the cycling races database
            correlation_calculator: Optional pre-configured correlation calculator
            min_races_config: Optional minimum race requirements by type
        """
        self.db_path = db_path
        
        # Use provided calculator or create default
        if correlation_calculator:
            self.correlation_calculator = correlation_calculator
        else:
            min_config = min_races_config or {
                'min_races_all': 35,
                'min_races_stage': 25,
                'min_races_one_day': 15,
                'min_races_gc': 10
            }
            self.correlation_calculator = RaceTypeCorrelationCalculator(
                db_path=db_path,
                **min_config
            )
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
    def calculate_interaction_embeddings(
        self,
        rider_result_id: int,
        lookback_date: str,
        feature_tables: List[str],
        interaction_types: List[str] = ['dot', 'hadamard', 'cosine']
    ) -> Dict[str, Any]:
        """
        Calculate interaction embeddings for a rider result.
        
        Args:
            rider_result_id: ID from the rider_results table
            lookback_date: Date string (YYYY-MM-DD) to calculate history up to
            feature_tables: List of race_features_N tables to analyze
            interaction_types: Types of interactions to calculate
            
        Returns:
            Dictionary with interaction embeddings for both phases
        """
        # Get the current race features (the race we're making embeddings for)
        current_race_features = self._get_current_race_features(
            rider_result_id, feature_tables
        )
        
        if not current_race_features:
            return self._empty_result(rider_result_id, "Current race features not found")
        
        # Calculate correlations using existing infrastructure
        correlation_results = self.correlation_calculator.calculate_feature_relationships(
            rider_result_id, lookback_date, feature_tables
        )
        
        if not correlation_results['feature_correlations']:
            return self._empty_result(
                rider_result_id, 
                "No correlations calculated",
                metadata=correlation_results['metadata']
            )
        
        # Phase 1: Individual percentile interactions
        phase1_interactions = self._calculate_phase1_interactions(
            current_race_features,
            correlation_results['feature_correlations'],
            interaction_types
        )
        
        # Phase 2: All percentiles matrix interactions
        phase2_interactions = self._calculate_phase2_interactions(
            current_race_features,
            correlation_results['feature_correlations'],
            interaction_types
        )
        
        return {
            'rider_result_id': rider_result_id,
            'phase1_interactions': phase1_interactions,
            'phase2_interactions': phase2_interactions,
            'metadata': {
                **correlation_results['metadata'],
                'interaction_types': interaction_types,
                'feature_tables': feature_tables,
                'calculation_date': datetime.now().isoformat()
            }
        }
    
    def _get_current_race_features(
        self, 
        rider_result_id: int,
        feature_tables: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """
        Get race features for the current competition.
        
        Returns:
            Dictionary mapping percentile -> {feature_name: value}
        """
        # Get competition_id for this rider_result
        query = """
        SELECT competition_id 
        FROM rider_results 
        WHERE id = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (rider_result_id,))
            result = cursor.fetchone()
            
            if not result:
                return {}
            
            competition_id = result[0]
            
            # Get features from each table
            race_features = {}
            for table in feature_tables:
                features = self._get_features_for_competition(
                    conn, competition_id, table
                )
                if features:
                    race_features[table] = features
            
            return race_features
    
    def _get_features_for_competition(
        self,
        conn: sqlite3.Connection,
        competition_id: int,
        feature_table: str
    ) -> Dict[str, float]:
        """Get features for a single competition from a feature table."""
        query = f"SELECT * FROM {feature_table} WHERE competition_id = ?"
        
        cursor = conn.cursor()
        cursor.execute(query, (competition_id,))
        row = cursor.fetchone()
        
        if not row:
            return {}
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        # Convert to dictionary, excluding competition_id
        features = {}
        for i, col_name in enumerate(column_names):
            if col_name != 'competition_id':
                features[col_name] = row[i]
        
        return features
    
    def _calculate_phase1_interactions(
        self,
        current_race_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, Dict[str, float]]],
        interaction_types: List[str]
    ) -> Dict[str, Any]:
        """
        Phase 1: Calculate interactions for individual percentiles.
        
        For each race type and percentile, calculate interactions between
        the current race's features and the rider's historical correlations.
        """
        phase1_results = {}
        
        for race_type, race_type_correlations in correlations.items():
            race_type_interactions = {}
            
            for percentile, percentile_correlations in race_type_correlations.items():
                if percentile not in current_race_features:
                    continue
                
                current_features = current_race_features[percentile]
                
                # Calculate each interaction type
                interactions = {}
                for interaction_type in interaction_types:
                    if interaction_type == 'dot':
                        interactions['dot'] = self._calculate_dot_product(
                            current_features, percentile_correlations
                        )
                    elif interaction_type == 'hadamard':
                        interactions['hadamard'] = self._calculate_hadamard_product(
                            current_features, percentile_correlations
                        )
                    elif interaction_type == 'cosine':
                        interactions['cosine'] = self._calculate_cosine_similarity(
                            current_features, percentile_correlations
                        )
                
                race_type_interactions[percentile] = interactions
            
            phase1_results[race_type] = race_type_interactions
        
        return phase1_results
    
    def _calculate_phase2_interactions(
        self,
        current_race_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, Dict[str, float]]],
        interaction_types: List[str]
    ) -> Dict[str, Any]:
        """
        Phase 2: Calculate interactions across all percentiles as matrices.
        
        Create matrices where rows are percentiles and columns are features,
        then calculate matrix-level interactions.
        """
        phase2_results = {}
        
        for race_type, race_type_correlations in correlations.items():
            # Get sorted percentiles and features
            percentiles = sorted(race_type_correlations.keys())
            
            # Get all unique features across percentiles
            all_features = set()
            for percentile_corrs in race_type_correlations.values():
                all_features.update(percentile_corrs.keys())
            features = sorted(all_features)
            
            if not features or not percentiles:
                continue
            
            # Build feature matrix for current race
            feature_matrix = self._build_feature_matrix(
                current_race_features, percentiles, features
            )
            
            # Build correlation matrix
            correlation_matrix = self._build_correlation_matrix(
                race_type_correlations, percentiles, features
            )
            
            # Skip if matrices are empty
            if feature_matrix.size == 0 or correlation_matrix.size == 0:
                continue
            
            # Calculate matrix interactions
            interactions = {}
            for interaction_type in interaction_types:
                if interaction_type == 'dot':
                    # Matrix dot product (Frobenius inner product)
                    interactions['dot'] = np.sum(feature_matrix * correlation_matrix)
                elif interaction_type == 'hadamard':
                    # Element-wise product matrix
                    interactions['hadamard'] = feature_matrix * correlation_matrix
                elif interaction_type == 'cosine':
                    # Matrix cosine similarity
                    interactions['cosine'] = self._matrix_cosine_similarity(
                        feature_matrix, correlation_matrix
                    )
            
            phase2_results[race_type] = {
                'interactions': interactions,
                'shape': (len(percentiles), len(features)),
                'percentiles': percentiles,
                'features': features
            }
        
        return phase2_results
    
    def _calculate_dot_product(
        self,
        features: Dict[str, float],
        correlations: Dict[str, float]
    ) -> float:
        """Calculate dot product between features and correlations."""
        # Get common features
        common_features = set(features.keys()) & set(correlations.keys())
        
        if not common_features:
            return 0.0
        
        dot_product = sum(
            features[f] * correlations[f] 
            for f in common_features 
            if features[f] is not None and correlations[f] is not None
        )
        
        return dot_product
    
    def _calculate_hadamard_product(
        self,
        features: Dict[str, float],
        correlations: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate element-wise (Hadamard) product."""
        # Get common features
        common_features = set(features.keys()) & set(correlations.keys())
        
        hadamard = {}
        for f in common_features:
            if features[f] is not None and correlations[f] is not None:
                hadamard[f] = features[f] * correlations[f]
        
        return hadamard
    
    def _calculate_cosine_similarity(
        self,
        features: Dict[str, float],
        correlations: Dict[str, float]
    ) -> float:
        """Calculate cosine similarity (normalized dot product)."""
        # Get common features
        common_features = set(features.keys()) & set(correlations.keys())
        
        if not common_features:
            return 0.0
        
        # Calculate dot product and norms
        dot_product = 0.0
        feature_norm_sq = 0.0
        corr_norm_sq = 0.0
        
        for f in common_features:
            if features[f] is not None and correlations[f] is not None:
                dot_product += features[f] * correlations[f]
                feature_norm_sq += features[f] ** 2
                corr_norm_sq += correlations[f] ** 2
        
        # Calculate cosine similarity
        if feature_norm_sq > 0 and corr_norm_sq > 0:
            return dot_product / (np.sqrt(feature_norm_sq) * np.sqrt(corr_norm_sq))
        else:
            return 0.0
    
    def _build_feature_matrix(
        self,
        race_features: Dict[str, Dict[str, float]],
        percentiles: List[str],
        features: List[str]
    ) -> np.ndarray:
        """Build matrix of race features (percentiles x features)."""
        matrix = np.zeros((len(percentiles), len(features)))
        
        for i, percentile in enumerate(percentiles):
            if percentile in race_features:
                for j, feature in enumerate(features):
                    value = race_features[percentile].get(feature)
                    if value is not None:
                        matrix[i, j] = value
        
        return matrix
    
    def _build_correlation_matrix(
        self,
        correlations: Dict[str, Dict[str, float]],
        percentiles: List[str],
        features: List[str]
    ) -> np.ndarray:
        """Build matrix of correlations (percentiles x features)."""
        matrix = np.zeros((len(percentiles), len(features)))
        
        for i, percentile in enumerate(percentiles):
            if percentile in correlations:
                for j, feature in enumerate(features):
                    value = correlations[percentile].get(feature)
                    if value is not None:
                        matrix[i, j] = value
        
        return matrix
    
    def _matrix_cosine_similarity(
        self,
        matrix1: np.ndarray,
        matrix2: np.ndarray
    ) -> float:
        """Calculate cosine similarity between two matrices."""
        # Flatten matrices
        vec1 = matrix1.flatten()
        vec2 = matrix2.flatten()
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 > 0 and norm2 > 0:
            return dot_product / (norm1 * norm2)
        else:
            return 0.0
    
    def _empty_result(
        self, 
        rider_result_id: int, 
        warning: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Create an empty result with a warning."""
        base_metadata = {
            'calculation_date': datetime.now().isoformat(),
            'warnings': [warning]
        }
        
        if metadata:
            base_metadata.update(metadata)
            base_metadata['warnings'] = metadata.get('warnings', []) + [warning]
        
        return {
            'rider_result_id': rider_result_id,
            'phase1_interactions': {},
            'phase2_interactions': {},
            'metadata': base_metadata
        }