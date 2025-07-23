"""
Race Feature Gradients Prototype Implementation

This module demonstrates how to calculate feature gradients across percentiles
for race classification purposes.
"""

import json
import sqlite3
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class GradientMetrics:
    """Container for gradient metrics of a single feature."""
    values: List[Optional[float]]
    imputed_flags: List[bool]
    slope: float
    volatility: float
    monotonicity: float
    
    def to_dict(self):
        """Convert to dictionary for database storage."""
        return {
            'values': json.dumps([v if v is not None else None for v in self.values]),
            'imputed_flags': json.dumps(self.imputed_flags),
            'slope': self.slope,
            'volatility': self.volatility,
            'monotonicity': self.monotonicity
        }


class RaceFeatureGradientCalculator:
    """Calculate feature gradients across percentiles for race analysis."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.percentiles = list(range(10, 101, 5))  # 10, 15, 20, ..., 100
        self.feature_columns = [
            'variance_absolute', 'variance_normalized',
            'std_deviation_absolute', 'std_deviation_normalized',
            'skewness_absolute', 'skewness_normalized',
            'kurtosis_absolute', 'kurtosis_normalized',
            'gini_coefficient', 'shannon_entropy_absolute',
            'clumpiness_score', 'selection_metric', 
            'biggest_group_metric', 'time_gap_evenness_metric'
        ]
    
    def calculate_competition_gradients(self, competition_id: int) -> Dict:
        """Calculate all feature gradients for a single competition."""
        # Fetch data across all percentiles
        feature_data = self._fetch_percentile_data(competition_id)
        
        if not feature_data:
            return None
        
        # Determine valid percentiles
        valid_percentiles = sorted(feature_data.keys())
        missing_percentiles = [p for p in self.percentiles if p not in valid_percentiles]
        
        if len(valid_percentiles) < 3:
            return None  # Insufficient data for gradients
        
        # Calculate gradients for each feature
        gradients = {}
        
        for feature in self.feature_columns:
            # Extract values across percentiles
            values_dict = {p: feature_data[p].get(feature) for p in self.percentiles}
            
            # Impute missing values
            imputed_values, imputed_flags = self._impute_feature_values(
                values_dict, competition_id, feature
            )
            
            # Calculate gradient metrics
            metrics = self._calculate_gradient_metrics(imputed_values, self.percentiles)
            
            if metrics:
                gradients[feature] = GradientMetrics(
                    values=imputed_values,
                    imputed_flags=imputed_flags,
                    **metrics
                )
        
        # Calculate derived features
        derived_features = self._calculate_derived_features(gradients, valid_percentiles)
        
        return {
            'competition_id': competition_id,
            'valid_percentiles': json.dumps(valid_percentiles),
            'missing_percentiles': json.dumps(missing_percentiles),
            'percentile_coverage_ratio': len(valid_percentiles) / len(self.percentiles),
            'lowest_valid_percentile': min(valid_percentiles),
            'gradients': gradients,
            **derived_features
        }
    
    def _fetch_percentile_data(self, competition_id: int) -> Dict:
        """Fetch feature data across all percentile tables."""
        conn = sqlite3.connect(self.db_path)
        feature_data = {}
        
        for percentile in self.percentiles:
            table_name = f"race_features_{percentile}"
            
            query = f"""
            SELECT {', '.join(self.feature_columns)}
            FROM {table_name}
            WHERE competition_id = ?
            """
            
            try:
                df = pd.read_sql_query(query, conn, params=(competition_id,))
                if not df.empty:
                    feature_data[percentile] = df.iloc[0].to_dict()
            except Exception:
                # Table might not exist or competition not in this percentile
                continue
        
        conn.close()
        return feature_data
    
    def _impute_feature_values(
        self, 
        values_dict: Dict[int, Optional[float]], 
        competition_id: int,
        feature: str
    ) -> Tuple[List[Optional[float]], List[bool]]:
        """Impute missing values using various strategies."""
        values = []
        imputed_flags = []
        
        for percentile in self.percentiles:
            value = values_dict.get(percentile)
            
            if value is not None:
                values.append(value)
                imputed_flags.append(False)
            else:
                # Try imputation strategies
                imputed_value = self._impute_single_value(
                    percentile, values_dict, competition_id, feature
                )
                values.append(imputed_value)
                imputed_flags.append(True)
        
        return values, imputed_flags
    
    def _impute_single_value(
        self,
        percentile: int,
        values_dict: Dict[int, Optional[float]],
        competition_id: int,
        feature: str
    ) -> Optional[float]:
        """Impute a single missing value using hierarchical strategies."""
        
        # Strategy 1: Linear interpolation from neighbors
        prev_p, next_p = None, None
        for p in sorted(values_dict.keys()):
            if p < percentile and values_dict[p] is not None:
                prev_p = p
            elif p > percentile and values_dict[p] is not None:
                next_p = p
                break
        
        if prev_p and next_p:
            # Linear interpolation
            weight = (percentile - prev_p) / (next_p - prev_p)
            return values_dict[prev_p] + weight * (values_dict[next_p] - values_dict[prev_p])
        
        # Strategy 2: Use nearest valid neighbor
        valid_percentiles = [p for p, v in values_dict.items() if v is not None]
        if valid_percentiles:
            nearest = min(valid_percentiles, key=lambda p: abs(p - percentile))
            return values_dict[nearest]
        
        # Strategy 3: Use similar race median (would need to implement)
        # For now, return 0 for kurtosis/skewness, None for others
        if 'kurtosis' in feature or 'skewness' in feature:
            return 0.0
        
        return None
    
    def _calculate_gradient_metrics(
        self, 
        values: List[Optional[float]], 
        percentiles: List[int]
    ) -> Optional[Dict]:
        """Calculate gradient metrics from a series of values."""
        # Filter out None values
        valid_pairs = [(p, v) for p, v in zip(percentiles, values) if v is not None]
        
        if len(valid_pairs) < 3:
            return None
        
        valid_percentiles, valid_values = zip(*valid_pairs)
        valid_percentiles = np.array(valid_percentiles)
        valid_values = np.array(valid_values)
        
        # Overall slope using linear regression
        slope, intercept = np.polyfit(valid_percentiles, valid_values, 1)
        
        # Volatility (standard deviation of step changes)
        if len(valid_values) > 1:
            steps = np.diff(valid_values)
            volatility = np.std(steps)
        else:
            volatility = 0.0
        
        # Monotonicity score
        if len(valid_values) > 1:
            steps = np.diff(valid_values)
            increasing = sum(1 for s in steps if s > 0)
            decreasing = sum(1 for s in steps if s < 0)
            total_steps = len(steps)
            monotonicity = (increasing - decreasing) / total_steps if total_steps > 0 else 0
        else:
            monotonicity = 0.0
        
        return {
            'slope': float(slope),
            'volatility': float(volatility),
            'monotonicity': float(monotonicity)
        }
    
    def _calculate_derived_features(
        self, 
        gradients: Dict[str, GradientMetrics],
        valid_percentiles: List[int]
    ) -> Dict[str, float]:
        """Calculate high-level features from gradients."""
        
        # Feature stability score
        volatilities = [g.volatility for g in gradients.values() if g.volatility is not None]
        avg_volatility = np.mean(volatilities) if volatilities else 0
        feature_stability_score = 1 / (1 + avg_volatility)
        
        # Early selection indicator
        early_selection_indicator = 0.0
        if 'variance_normalized' in gradients:
            values = gradients['variance_normalized'].values
            early_indices = [i for i, p in enumerate(self.percentiles) if 10 <= p <= 30]
            all_indices = [i for i, p in enumerate(self.percentiles) if p in valid_percentiles]
            
            if len(all_indices) > 1:
                early_changes = sum(abs(values[i] - values[i-1]) 
                                  for i in early_indices[1:] 
                                  if i < len(values) and values[i] is not None and values[i-1] is not None)
                total_changes = sum(abs(values[i] - values[i-1]) 
                                  for i in all_indices[1:] 
                                  if i < len(values) and values[i] is not None and values[i-1] is not None)
                early_selection_indicator = early_changes / total_changes if total_changes > 0 else 0
        
        # Progressive selection score
        progressive_selection_score = 0.0
        if 'selection_metric' in gradients:
            values = [v for v in gradients['selection_metric'].values if v is not None]
            if len(values) > 1:
                max_step = max(abs(values[i] - values[i-1]) for i in range(1, len(values)))
                total_range = max(values) - min(values) if values else 0
                progressive_selection_score = 1 - (max_step / total_range) if total_range > 0 else 0
        
        return {
            'feature_stability_score': feature_stability_score,
            'early_selection_indicator': early_selection_indicator,
            'progressive_selection_score': progressive_selection_score
        }


def create_gradients_table(db_path: str):
    """Create the race_feature_gradients table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # For brevity, showing a simplified version - full version in design doc
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS race_feature_gradients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        competition_id INTEGER NOT NULL UNIQUE,
        extraction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Coverage metrics
        valid_percentiles TEXT,
        missing_percentiles TEXT,
        percentile_coverage_ratio REAL,
        lowest_valid_percentile INTEGER,
        
        -- Gradient metrics for key features (simplified)
        variance_normalized_values TEXT,
        variance_normalized_slope REAL,
        variance_normalized_volatility REAL,
        variance_normalized_monotonicity REAL,
        
        kurtosis_normalized_values TEXT,
        kurtosis_normalized_imputed_flags TEXT,
        kurtosis_normalized_slope REAL,
        kurtosis_normalized_volatility REAL,
        kurtosis_normalized_monotonicity REAL,
        
        selection_metric_values TEXT,
        selection_metric_slope REAL,
        selection_metric_volatility REAL,
        selection_metric_monotonicity REAL,
        
        -- Derived features
        feature_stability_score REAL,
        early_selection_indicator REAL,
        progressive_selection_score REAL,
        
        FOREIGN KEY (competition_id) REFERENCES competitions(id)
    )
    """)
    
    conn.commit()
    conn.close()


# Example usage
if __name__ == "__main__":
    db_path = "/path/to/database.db"
    
    # Create calculator
    calculator = RaceFeatureGradientCalculator(db_path)
    
    # Calculate gradients for a competition
    competition_id = 1234
    gradient_data = calculator.calculate_competition_gradients(competition_id)
    
    if gradient_data:
        print(f"Competition {competition_id} gradient analysis:")
        print(f"Valid percentiles: {gradient_data['valid_percentiles']}")
        print(f"Coverage ratio: {gradient_data['percentile_coverage_ratio']:.2%}")
        print(f"Feature stability: {gradient_data['feature_stability_score']:.3f}")
        print(f"Early selection: {gradient_data['early_selection_indicator']:.3f}")
        print(f"Progressive selection: {gradient_data['progressive_selection_score']:.3f}")