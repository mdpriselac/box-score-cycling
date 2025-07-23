"""
Race Feature Gradient Calculator

This module implements the core functionality for calculating gradients of race features
across percentiles, handling edge cases, and computing derived metrics.
"""

import json
import sqlite3
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GradientMetrics:
    """Container for gradient metrics of a single feature"""
    values: List[float]
    slope: float
    volatility: float
    monotonicity: float
    imputed_flags: Optional[List[bool]] = None


class GradientCalculator:
    """Calculate and analyze gradients of race features across percentiles"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.percentiles = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        
    def calculate_gradient_metrics(self, values: List[Optional[float]], 
                                 percentiles: List[int]) -> Optional[GradientMetrics]:
        """
        Calculate gradient metrics for a feature across percentiles
        
        Args:
            values: Feature values at each percentile (may contain None)
            percentiles: Corresponding percentile values
            
        Returns:
            GradientMetrics object or None if insufficient data
        """
        # Remove None values and align percentiles
        valid_pairs = [(p, v) for p, v in zip(percentiles, values) if v is not None]
        
        if len(valid_pairs) < 3:
            return None  # Insufficient data
        
        valid_percentiles, valid_values = zip(*valid_pairs)
        valid_percentiles = np.array(valid_percentiles)
        valid_values = np.array(valid_values)
        
        # Overall slope using linear regression
        slope, intercept = np.polyfit(valid_percentiles, valid_values, 1)
        
        # Step-to-step volatility
        if len(valid_values) > 1:
            steps = np.diff(valid_values)
            volatility = np.std(steps) if len(steps) > 0 else 0
            
            # Monotonicity score
            increasing = sum(1 for s in steps if s > 0)
            decreasing = sum(1 for s in steps if s < 0)
            total_steps = len(steps)
            
            if total_steps > 0:
                monotonicity = (increasing - decreasing) / total_steps
            else:
                monotonicity = 0
        else:
            volatility = 0
            monotonicity = 0
        
        return GradientMetrics(
            values=valid_values.tolist(),
            slope=slope,
            volatility=volatility,
            monotonicity=monotonicity
        )
    
    def impute_missing_values(self, values: List[Optional[float]], 
                            feature_name: str,
                            competition_id: int) -> Tuple[List[float], List[bool]]:
        """
        Impute missing values using the strategy defined in the design doc
        
        Returns:
            Tuple of (imputed_values, imputation_flags)
        """
        imputed_values = []
        imputation_flags = []
        
        for i, val in enumerate(values):
            if val is not None:
                imputed_values.append(val)
                imputation_flags.append(False)
            else:
                # Try linear interpolation
                imputed_val = self._try_linear_interpolation(values, i)
                
                # If that fails, try similar race median
                if imputed_val is None:
                    imputed_val = self._get_similar_race_median(
                        feature_name, self.percentiles[i], competition_id
                    )
                
                # If that fails, use endpoint extension
                if imputed_val is None:
                    imputed_val = self._endpoint_extension(values, i)
                
                # Last resort: zero
                if imputed_val is None:
                    imputed_val = 0.0
                
                imputed_values.append(imputed_val)
                imputation_flags.append(True)
        
        return imputed_values, imputation_flags
    
    def _try_linear_interpolation(self, values: List[Optional[float]], 
                                index: int) -> Optional[float]:
        """Try to linearly interpolate between adjacent valid values"""
        n = len(values)
        
        # Find previous and next valid values
        prev_idx = None
        next_idx = None
        
        for i in range(index - 1, -1, -1):
            if values[i] is not None:
                prev_idx = i
                break
                
        for i in range(index + 1, n):
            if values[i] is not None:
                next_idx = i
                break
        
        if prev_idx is not None and next_idx is not None:
            # Linear interpolation
            prev_val = values[prev_idx]
            next_val = values[next_idx]
            weight = (index - prev_idx) / (next_idx - prev_idx)
            return prev_val + weight * (next_val - prev_val)
        
        return None
    
    def _endpoint_extension(self, values: List[Optional[float]], 
                          index: int) -> Optional[float]:
        """Use nearest valid value"""
        # Search outward from index
        for distance in range(1, len(values)):
            if index - distance >= 0 and values[index - distance] is not None:
                return values[index - distance]
            if index + distance < len(values) and values[index + distance] is not None:
                return values[index + distance]
        return None
    
    def _get_similar_race_median(self, feature_name: str, 
                               percentile: int, 
                               competition_id: int) -> Optional[float]:
        """Get median value from similar races at same percentile"""
        # This would query the database for similar races
        # For now, returning None to use other imputation methods
        return None
    
    def find_data_quality_indicators(self, feature_data: Dict[int, Any]) -> Dict[str, int]:
        """
        Find key data quality indicators:
        - Where variance hits zero
        - Where kurtosis becomes null
        - Where monotonicity breaks
        - Lowest valid percentile
        """
        indicators = {
            'variance_zero_percentile': None,
            'kurtosis_null_percentile': None,
            'monotonicity_break_percentile': None,
            'lowest_valid_percentile': 100
        }
        
        # Check each percentile from high to low
        for p in sorted(self.percentiles, reverse=True):
            if p in feature_data:
                data = feature_data[p]
                
                # Update lowest valid percentile
                indicators['lowest_valid_percentile'] = p
                
                # Check variance
                if data.get('variance_normalized') == 0 and indicators['variance_zero_percentile'] is None:
                    indicators['variance_zero_percentile'] = p
                
                # Check kurtosis
                if data.get('kurtosis_normalized') is None and indicators['kurtosis_null_percentile'] is None:
                    indicators['kurtosis_null_percentile'] = p
        
        return indicators
    
    def calculate_selectivity_point(self, variance_values: List[float], 
                                  percentiles: List[int],
                                  threshold: float = 0.05) -> Optional[int]:
        """Find the percentile where normalized variance drops below threshold"""
        for p, var in zip(percentiles, variance_values):
            if var < threshold:
                return p
        return None
    
    def calculate_selectivity_metrics(self, variance_values: List[float],
                                    percentiles: List[int],
                                    selectivity_point: Optional[int]) -> Dict[str, float]:
        """Calculate metrics around the selectivity point"""
        if selectivity_point is None:
            return {
                'selectivity_sharpness': 0,
                'pre_selectivity_slope': 0,
                'post_selectivity_slope': 0
            }
        
        # Find index of selectivity point
        sp_idx = None
        for i, p in enumerate(percentiles):
            if p == selectivity_point:
                sp_idx = i
                break
        
        if sp_idx is None or sp_idx < 3:
            return {
                'selectivity_sharpness': 0,
                'pre_selectivity_slope': 0,
                'post_selectivity_slope': 0
            }
        
        # Calculate pre-selectivity slope (3 points before)
        pre_values = variance_values[max(0, sp_idx-3):sp_idx]
        pre_percentiles = percentiles[max(0, sp_idx-3):sp_idx]
        
        if len(pre_values) >= 2:
            pre_slope, _ = np.polyfit(pre_percentiles, pre_values, 1)
        else:
            pre_slope = 0
        
        # Calculate post-selectivity slope
        post_values = variance_values[sp_idx:min(len(variance_values), sp_idx+3)]
        post_percentiles = percentiles[sp_idx:min(len(percentiles), sp_idx+3)]
        
        if len(post_values) >= 2:
            post_slope, _ = np.polyfit(post_percentiles, post_values, 1)
        else:
            post_slope = 0
        
        # Sharpness: ratio of slopes
        if pre_slope != 0:
            sharpness = abs(post_slope / pre_slope)
        else:
            sharpness = 1.0 if abs(post_slope) > 0.01 else 0
        
        return {
            'selectivity_sharpness': min(sharpness, 1.0),
            'pre_selectivity_slope': pre_slope,
            'post_selectivity_slope': post_slope
        }
    
    def calculate_gradient_derived_features(self, all_gradients: Dict[str, GradientMetrics],
                                          selectivity_point: Optional[int]) -> Dict[str, float]:
        """Calculate high-level features from all gradients"""
        # Feature stability score
        volatilities = [g.volatility for g in all_gradients.values() if g]
        avg_volatility = np.mean(volatilities) if volatilities else 0
        feature_stability = 1 / (1 + avg_volatility)
        
        # Early selection indicator
        # For now, using a simplified version
        early_selection = 0.5  # Placeholder
        
        # Progressive selection score
        progressive_score = 0.5  # Placeholder
        
        # Racing intensity score
        racing_intensity = selectivity_point / 100 if selectivity_point else 1.0
        
        return {
            'feature_stability_score': feature_stability,
            'early_selection_indicator': early_selection,
            'progressive_selection_score': progressive_score,
            'racing_intensity_score': racing_intensity
        }
    
    def process_competition(self, competition_id: int) -> Dict[str, Any]:
        """
        Process a single competition to generate all gradient data
        
        Returns complete gradient data ready for database insertion
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # Get competition metadata
            metadata = self._get_competition_metadata(conn, competition_id)
            if not metadata:
                return None
            
            # Collect feature data across percentiles
            feature_data = self._collect_feature_data(conn, competition_id)
            
            # Determine valid percentiles
            valid_percentiles = sorted([p for p in feature_data.keys()])
            missing_percentiles = [p for p in self.percentiles if p not in valid_percentiles]
            
            if len(valid_percentiles) < 3:
                return None  # Insufficient data
            
            # Calculate coverage metrics
            coverage_ratio = len(valid_percentiles) / len(self.percentiles)
            lowest_valid = min(valid_percentiles)
            
            # Find data quality indicators
            quality_indicators = self.find_data_quality_indicators(feature_data)
            
            # Process each feature
            gradients = {}
            
            # Variance
            variance_norm_values = [feature_data[p].get('variance_normalized') 
                                   for p in self.percentiles if p in feature_data]
            gradients['variance_normalized'] = self.calculate_gradient_metrics(
                variance_norm_values, valid_percentiles
            )
            
            # Calculate selectivity point
            if gradients['variance_normalized']:
                selectivity_point = self.calculate_selectivity_point(
                    gradients['variance_normalized'].values,
                    valid_percentiles
                )
                selectivity_metrics = self.calculate_selectivity_metrics(
                    gradients['variance_normalized'].values,
                    valid_percentiles,
                    selectivity_point
                )
            else:
                selectivity_point = None
                selectivity_metrics = {}
            
            # Calculate other features (simplified for now)
            # In full implementation, would process all features
            
            # Calculate derived features
            derived_features = self.calculate_gradient_derived_features(
                gradients, selectivity_point
            )
            
            # Prepare result
            result = {
                'competition_id': competition_id,
                'valid_percentiles': json.dumps(valid_percentiles),
                'missing_percentiles': json.dumps(missing_percentiles),
                'percentile_coverage_ratio': coverage_ratio,
                'lowest_valid_percentile': lowest_valid,
                'highest_null_percentile': quality_indicators.get('lowest_valid_percentile'),
                'variance_zero_percentile': quality_indicators.get('variance_zero_percentile'),
                'kurtosis_null_percentile': quality_indicators.get('kurtosis_null_percentile'),
                'monotonicity_break_percentile': quality_indicators.get('monotonicity_break_percentile'),
                'selectivity_point': selectivity_point,
                **selectivity_metrics,
                **derived_features,
                **metadata
            }
            
            # Add gradient metrics
            if gradients.get('variance_normalized'):
                g = gradients['variance_normalized']
                result.update({
                    'variance_normalized_values': json.dumps(g.values),
                    'variance_normalized_slope': g.slope,
                    'variance_normalized_volatility': g.volatility,
                    'variance_normalized_monotonicity': g.monotonicity
                })
            
            return result
            
        finally:
            conn.close()
    
    def _get_competition_metadata(self, conn: sqlite3.Connection, 
                                competition_id: int) -> Dict[str, Any]:
        """Get competition metadata from the database"""
        query = """
        SELECT 
            competition_name,
            competition_type,
            race_id,
            race_name,
            race_category,
            race_year,
            race_date,
            total_finishers
        FROM race_features_100
        WHERE competition_id = ?
        """
        
        cursor = conn.execute(query, (competition_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def _collect_feature_data(self, conn: sqlite3.Connection, 
                            competition_id: int) -> Dict[int, Dict[str, Any]]:
        """Collect feature data across all percentiles"""
        feature_data = {}
        
        for percentile in self.percentiles:
            table_name = f'race_features_{percentile}'
            
            query = f"""
            SELECT 
                variance_normalized,
                variance_absolute,
                skewness_normalized,
                skewness_absolute,
                kurtosis_normalized,
                kurtosis_absolute,
                gini_coefficient,
                clumpiness_score,
                selection_metric,
                biggest_group_metric,
                "5th_percentile_gap",
                "25th_percentile_gap",
                "50th_percentile_gap"
            FROM {table_name}
            WHERE competition_id = ?
            """
            
            try:
                cursor = conn.execute(query, (competition_id,))
                row = cursor.fetchone()
                
                if row:
                    feature_data[percentile] = dict(row)
            except sqlite3.OperationalError:
                # Table might not exist
                continue
        
        return feature_data