"""
Optimized Interaction Calculator

This module provides an optimized version of the interaction embeddings calculator
that uses pre-loaded shared data instead of making database queries.

Key optimizations:
- Uses pre-loaded race features from shared memory
- Uses pre-loaded rider histories from shared memory
- Eliminates all database I/O during calculation
- Maintains the same API as the original calculator

Usage:
    calculator = OptimizedInteractionCalculator(
        shared_race_features, 
        shared_rider_histories, 
        calculator_config
    )
    result = calculator.calculate_interaction_embeddings_optimized(
        rider_result_id, competition_id, feature_tables
    )
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import warnings
import logging

# Import the parent class methods we want to reuse
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from performance_feature_link.interaction_embeddings import InteractionEmbeddingsCalculator


class OptimizedInteractionCalculator:
    """
    Optimized interaction embeddings calculator that uses pre-loaded shared data.
    
    This calculator eliminates all database I/O by using pre-loaded race features
    and rider histories, providing significant performance improvements.
    """
    
    def __init__(
        self, 
        shared_race_features: Dict[str, Dict[int, Dict[str, float]]], 
        shared_rider_histories: Dict[int, List[Dict[str, Any]]], 
        calculator_config: Dict[str, Any]
    ):
        """
        Initialize the optimized calculator with shared data.
        
        Args:
            shared_race_features: Pre-loaded race features
                Structure: {table_name: {competition_id: {feature_name: value}}}
            shared_rider_histories: Pre-loaded rider histories
                Structure: {rider_result_id: [list of historical race results]}
            calculator_config: Configuration with minimum race requirements
        """
        self.shared_race_features = shared_race_features
        self.shared_rider_histories = shared_rider_histories
        self.calculator_config = calculator_config
        self.logger = logging.getLogger(__name__)
        
        # Set up minimum race requirements
        self.min_races = {
            'gc': calculator_config.get('min_races_gc', 10),
            'stage': calculator_config.get('min_races_stage', 25),
            'one_day': calculator_config.get('min_races_one_day', 15),
            'stage_one_day': calculator_config.get('min_races_one_day', 15),
            'all': calculator_config.get('min_races_all', 35)
        }
        
        # Race type definitions
        self.race_types = {
            'gc': ['gc'],
            'stage': ['stage'],
            'one_day': ['one_day'],
            'stage_one_day': ['stage', 'one_day'],
            'all': ['gc', 'stage', 'one_day']
        }
        
        # Create a base calculator instance for method reuse
        # We'll use object.__new__ to avoid database validation
        self._base_calculator = object.__new__(InteractionEmbeddingsCalculator)
    
    def calculate_interaction_embeddings_optimized(
        self,
        rider_result_id: int,
        competition_id: int,
        feature_tables: List[str],
        interaction_types: List[str] = ['dot', 'hadamard', 'cosine']
    ) -> Dict[str, Any]:
        """
        Calculate interaction embeddings using pre-loaded shared data.
        
        Args:
            rider_result_id: ID from the rider_results table
            competition_id: ID of the competition for current race features
            feature_tables: List of race_features_N tables to analyze
            interaction_types: Types of interactions to calculate
            
        Returns:
            Dictionary with interaction embeddings for both phases
        """
        # Get current race features from shared data
        current_race_features = self._get_current_race_features_cached(competition_id, feature_tables)
        
        if not current_race_features:
            return self._empty_result(rider_result_id, "Current race features not found")
        
        # Get rider history from shared data
        rider_history = self.shared_rider_histories.get(rider_result_id, [])
        
        if not rider_history:
            return self._empty_result(rider_result_id, "No rider history found")
        
        # Calculate correlations using shared data
        correlations = self._calculate_correlations_from_shared_data(
            rider_history, feature_tables
        )
        
        if not correlations:
            return self._empty_result(rider_result_id, "No correlations calculated")
        
        # Phase 1: Individual percentile interactions
        phase1_interactions = self._calculate_phase1_interactions(
            current_race_features, correlations, interaction_types
        )
        
        # Phase 2: All percentiles matrix interactions
        phase2_interactions = self._calculate_phase2_interactions(
            current_race_features, correlations, interaction_types
        )
        
        return {
            'rider_result_id': rider_result_id,
            'phase1_interactions': phase1_interactions,
            'phase2_interactions': phase2_interactions,
            'metadata': {
                'n_races': self._count_races_by_type(rider_history),
                'method': 'optimized_interaction_embeddings',
                'calculation_date': datetime.now().isoformat(),
                'interaction_types': interaction_types,
                'feature_tables': feature_tables,
                'warnings': []
            }
        }
    
    def _get_current_race_features_cached(
        self, 
        competition_id: int, 
        feature_tables: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Get race features from shared cache."""
        race_features = {}
        
        for table in feature_tables:
            if table in self.shared_race_features:
                features = self.shared_race_features[table].get(competition_id, {})
                if features:
                    race_features[table] = features
        
        return race_features
    
    def _calculate_correlations_from_shared_data(
        self, 
        rider_history: List[Dict[str, Any]], 
        feature_tables: List[str]
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """Calculate correlations using shared race features data."""
        
        # Segment history by race type
        race_type_histories = self._segment_history_by_race_type(rider_history)
        
        # Calculate correlations for each race type
        correlations = {}
        
        for race_type, history in race_type_histories.items():
            if len(history) < self.min_races[race_type]:
                continue
            
            race_type_correlations = {}
            
            for feature_table in feature_tables:
                # Get features for competitions in history
                valid_history = []
                features_data = {}
                
                for h in history:
                    comp_id = h['competition_id']
                    if (feature_table in self.shared_race_features and 
                        comp_id in self.shared_race_features[feature_table]):
                        valid_history.append(h)
                        features_data[comp_id] = self.shared_race_features[feature_table][comp_id]
                
                if len(valid_history) >= self.min_races[race_type]:
                    # Calculate correlations
                    table_correlations = self._calculate_table_correlations_optimized(
                        valid_history, features_data, race_type
                    )
                    race_type_correlations[feature_table] = table_correlations
            
            if race_type_correlations:
                correlations[race_type] = race_type_correlations
        
        return correlations
    
    def _calculate_table_correlations_optimized(
        self, 
        history: List[Dict[str, Any]], 
        features_data: Dict[int, Dict[str, float]],
        race_type: str
    ) -> Dict[str, float]:
        """Calculate correlations using pre-loaded features data."""
        
        # Extract performance data
        points = np.array([float(h['uci_points_proportional']) for h in history], dtype=float)
        
        # Check for zero variance
        if np.std(points) == 0:
            return {}
        
        # Get all feature names
        all_features = set()
        for features in features_data.values():
            all_features.update(features.keys())
        
        correlations = {}
        
        for feature_name in all_features:
            # Extract feature values
            feature_values = []
            for h in history:
                comp_id = h['competition_id']
                value = features_data[comp_id].get(feature_name)
                # Ensure consistent float type for numpy array
                if value is not None:
                    feature_values.append(float(value))
                else:
                    feature_values.append(np.nan)
            
            feature_array = np.array(feature_values, dtype=float)
            
            # Calculate correlation if enough valid values
            min_required = self.min_races[race_type]
            valid_mask = ~(np.isnan(feature_array) | np.isnan(points))
            
            if np.sum(valid_mask) >= min_required:
                valid_points = points[valid_mask]
                valid_features = feature_array[valid_mask]
                
                if (len(valid_features) >= min_required and 
                    np.std(valid_features) > 1e-10 and 
                    np.std(valid_points) > 1e-10):
                    
                    # Calculate Spearman correlation
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        corr, p_value = stats.spearmanr(valid_points, valid_features)
                    
                    correlations[feature_name] = float(corr) if not np.isnan(corr) else None
                else:
                    correlations[feature_name] = None
            else:
                correlations[feature_name] = None
        
        return correlations
    
    def _calculate_phase1_interactions(
        self,
        current_race_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, Dict[str, float]]],
        interaction_types: List[str]
    ) -> Dict[str, Any]:
        """Calculate Phase 1 interactions using base calculator methods."""
        return self._base_calculator._calculate_phase1_interactions(
            current_race_features, correlations, interaction_types
        )
    
    def _calculate_phase2_interactions(
        self,
        current_race_features: Dict[str, Dict[str, float]],
        correlations: Dict[str, Dict[str, Dict[str, float]]],
        interaction_types: List[str]
    ) -> Dict[str, Any]:
        """Calculate Phase 2 interactions using base calculator methods."""
        return self._base_calculator._calculate_phase2_interactions(
            current_race_features, correlations, interaction_types
        )
    
    def _segment_history_by_race_type(
        self, 
        history: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Segment history by race type."""
        segmented = {}
        
        for race_type, competition_types in self.race_types.items():
            if race_type == 'all':
                segmented[race_type] = history
            else:
                segmented[race_type] = [
                    h for h in history if h['competition_type'] in competition_types
                ]
        
        return segmented
    
    def _count_races_by_type(self, history: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count races by type."""
        segmented = self._segment_history_by_race_type(history)
        return {race_type: len(hist) for race_type, hist in segmented.items()}
    
    def _empty_result(self, rider_result_id: int, warning: str) -> Dict[str, Any]:
        """Create empty result with warning."""
        return {
            'rider_result_id': rider_result_id,
            'phase1_interactions': {},
            'phase2_interactions': {},
            'metadata': {
                'calculation_date': datetime.now().isoformat(),
                'warnings': [warning],
                'method': 'optimized_interaction_embeddings',
                'n_races': {race_type: 0 for race_type in self.race_types}
            }
        }
    
    def get_performance_statistics(self) -> Dict[str, Any]:
        """Get performance statistics about the cached data."""
        return {
            'shared_race_features': {
                'tables_count': len(self.shared_race_features),
                'total_competitions': len(set().union(
                    *[table_data.keys() for table_data in self.shared_race_features.values()]
                )),
                'tables': list(self.shared_race_features.keys())
            },
            'shared_rider_histories': {
                'riders_count': len(self.shared_rider_histories),
                'total_historical_races': sum(len(history) for history in self.shared_rider_histories.values()),
                'riders_with_no_history': sum(1 for history in self.shared_rider_histories.values() if len(history) == 0)
            },
            'calculator_config': self.calculator_config,
            'min_races_requirements': self.min_races
        }
    
    def validate_shared_data(self) -> Dict[str, Any]:
        """Validate the integrity of shared data."""
        validation_results = {
            'race_features_valid': True,
            'rider_histories_valid': True,
            'issues': []
        }
        
        # Validate race features
        for table_name, table_data in self.shared_race_features.items():
            if not table_data:
                validation_results['race_features_valid'] = False
                validation_results['issues'].append(f"Empty data for table {table_name}")
            
            # Check for consistent feature names
            if table_data:
                feature_names = set()
                for comp_id, features in table_data.items():
                    if feature_names and set(features.keys()) != feature_names:
                        validation_results['race_features_valid'] = False
                        validation_results['issues'].append(f"Inconsistent features in table {table_name}")
                        break
                    feature_names = set(features.keys())
        
        # Validate rider histories
        for rider_result_id, history in self.shared_rider_histories.items():
            if not isinstance(history, list):
                validation_results['rider_histories_valid'] = False
                validation_results['issues'].append(f"Invalid history format for rider {rider_result_id}")
            
            # Check history structure
            for race in history:
                required_fields = ['competition_id', 'uci_points_proportional', 'competition_type']
                if not all(field in race for field in required_fields):
                    validation_results['rider_histories_valid'] = False
                    validation_results['issues'].append(f"Missing fields in history for rider {rider_result_id}")
                    break
        
        validation_results['overall_valid'] = (
            validation_results['race_features_valid'] and 
            validation_results['rider_histories_valid']
        )
        
        return validation_results