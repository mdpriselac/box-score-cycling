import numpy as np
import pandas as pd
from scipy import stats
import sqlite3
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class MonotonicityMetrics:
    spearman_correlation: float
    is_monotonic: bool
    is_increasing: bool
    is_decreasing: bool
    linearity_r2: float
    slope: float
    relative_slope: float  # Slope normalized by mean


class MonotonicityAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        self._conn = None
    
    def get_connection(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn
    
    def close_connection(self):
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def quote_column(self, column_name: str) -> str:
        # Quote columns that start with numbers or contain special characters
        if column_name[0].isdigit() or 'th_percentile' in column_name:
            return f'"{column_name}"'
        return column_name
    
    def get_feature_stats_by_n(self, feature_name: str) -> Dict[int, Dict[str, float]]:
        feature_stats = {}
        quoted_name = self.quote_column(feature_name)
        
        for n in self.n_levels:
            table_name = f"race_features_{n}"
            # SQLite doesn't have STDEV, so we calculate it manually
            query = f"""
            SELECT 
                AVG({quoted_name}) as mean,
                MIN({quoted_name}) as min,
                MAX({quoted_name}) as max,
                COUNT({quoted_name}) as count,
                AVG({quoted_name} * {quoted_name}) as mean_squared
            FROM {table_name}
            WHERE {quoted_name} IS NOT NULL
            """
            
            conn = self.get_connection()
            result = pd.read_sql_query(query, conn)
            if not result.empty and result['count'].iloc[0] > 0:
                mean = result['mean'].iloc[0]
                mean_squared = result['mean_squared'].iloc[0]
                # Calculate standard deviation: sqrt(E[X^2] - E[X]^2)
                variance = mean_squared - mean * mean
                std = np.sqrt(variance) if variance > 0 else 0
                
                feature_stats[n] = {
                    'mean': mean,
                    'std': std,
                    'min': result['min'].iloc[0],
                    'max': result['max'].iloc[0],
                    'count': result['count'].iloc[0]
                }
        
        return feature_stats
    
    def analyze_monotonicity(self, feature_name: str) -> MonotonicityMetrics:
        feature_stats = self.get_feature_stats_by_n(feature_name)
        
        if len(feature_stats) < 2:
            return MonotonicityMetrics(0, False, False, False, 0, 0, 0)
        
        n_values = sorted(feature_stats.keys())
        means = [feature_stats[n]['mean'] for n in n_values]
        
        # Spearman correlation for monotonicity
        spearman_corr, _ = stats.spearmanr(n_values, means)
        
        # Check strict monotonicity
        increasing = all(means[i] <= means[i+1] for i in range(len(means)-1))
        decreasing = all(means[i] >= means[i+1] for i in range(len(means)-1))
        
        # Linearity (R-squared of linear fit)
        slope, intercept, r_value, p_value, std_err = stats.linregress(n_values, means)
        
        # Calculate relative slope
        mean_of_means = np.mean(means)
        relative_slope = slope / mean_of_means if mean_of_means != 0 else 0
        
        return MonotonicityMetrics(
            spearman_correlation=spearman_corr,
            is_monotonic=increasing or decreasing,
            is_increasing=increasing,
            is_decreasing=decreasing,
            linearity_r2=r_value ** 2,
            slope=slope,
            relative_slope=relative_slope
        )
    
    def analyze_feature_trajectories(self, feature_name: str) -> Dict[str, any]:
        feature_stats = self.get_feature_stats_by_n(feature_name)
        
        if len(feature_stats) < 2:
            return {}
        
        n_values = sorted(feature_stats.keys())
        
        # Extract different statistics
        means = [feature_stats[n]['mean'] for n in n_values]
        stds = [feature_stats[n]['std'] for n in n_values]
        cvs = [feature_stats[n]['std'] / feature_stats[n]['mean'] 
               if feature_stats[n]['mean'] != 0 else 0 for n in n_values]
        ranges = [feature_stats[n]['max'] - feature_stats[n]['min'] for n in n_values]
        
        # Analyze trajectories for each statistic
        trajectories = {
            'mean': self._analyze_single_trajectory(n_values, means),
            'std': self._analyze_single_trajectory(n_values, stds),
            'cv': self._analyze_single_trajectory(n_values, cvs),
            'range': self._analyze_single_trajectory(n_values, ranges)
        }
        
        return trajectories
    
    def _analyze_single_trajectory(self, x: List[int], y: List[float]) -> Dict[str, float]:
        if len(x) < 2:
            return {}
        
        # Linear fit
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Polynomial fit (quadratic)
        poly_coeffs = np.polyfit(x, y, 2)
        poly_fit = np.poly1d(poly_coeffs)
        y_pred_poly = poly_fit(x)
        
        # R-squared for polynomial
        ss_res = np.sum((y - y_pred_poly) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2_poly = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        # Detect if there's a clear turning point
        if abs(poly_coeffs[0]) > 0.001:  # Significant quadratic term
            turning_point = -poly_coeffs[1] / (2 * poly_coeffs[0])
            if min(x) <= turning_point <= max(x):
                has_turning_point = True
            else:
                has_turning_point = False
                turning_point = None
        else:
            has_turning_point = False
            turning_point = None
        
        return {
            'linear_slope': slope,
            'linear_r2': r_value ** 2,
            'polynomial_r2': r2_poly,
            'has_turning_point': has_turning_point,
            'turning_point_n': turning_point,
            'is_better_fit_polynomial': r2_poly > r_value ** 2 + 0.1  # Polynomial significantly better
        }
    
    def analyze_all_features(self) -> Dict[str, Dict[str, any]]:
        # Get feature columns
        conn = self.get_connection()
        cursor = conn.execute("PRAGMA table_info(race_features_30)")
        columns = [row[1] for row in cursor.fetchall()]
        exclude_cols = ['id', 'competition_id', 'percentile_analyzed', 'extraction_date',
                       'competition_name', 'competition_type', 'race_id', 'race_name',
                       'race_category', 'race_year', 'race_date']
        feature_columns = [col for col in columns if col not in exclude_cols]
        
        results = {}
        for feature in feature_columns:
            print(f"Analyzing monotonicity for {feature}...")
            results[feature] = {
                'monotonicity': self.analyze_monotonicity(feature),
                'trajectories': self.analyze_feature_trajectories(feature)
            }
        
        return results
    
    def __del__(self):
        self.close_connection()
    
    def classify_features_by_monotonicity(self, results: Dict[str, Dict[str, any]]) -> Dict[str, List[str]]:
        classification = {
            'strictly_increasing': [],
            'strictly_decreasing': [],
            'generally_increasing': [],  # High positive correlation but not strict
            'generally_decreasing': [],  # High negative correlation but not strict
            'u_shaped': [],  # Has turning point with negative then positive slope
            'inverted_u_shaped': [],  # Has turning point with positive then negative slope
            'stable': [],  # Low correlation with N
            'complex': []  # Other patterns
        }
        
        for feature, analysis in results.items():
            mono = analysis['monotonicity']
            traj = analysis['trajectories'].get('mean', {})
            
            if mono.is_increasing:
                classification['strictly_increasing'].append(feature)
            elif mono.is_decreasing:
                classification['strictly_decreasing'].append(feature)
            elif abs(mono.spearman_correlation) < 0.3:
                classification['stable'].append(feature)
            elif traj.get('has_turning_point', False):
                # Check the direction of the parabola
                if mono.slope > 0:  # Initial positive slope
                    classification['inverted_u_shaped'].append(feature)
                else:
                    classification['u_shaped'].append(feature)
            elif mono.spearman_correlation > 0.7:
                classification['generally_increasing'].append(feature)
            elif mono.spearman_correlation < -0.7:
                classification['generally_decreasing'].append(feature)
            else:
                classification['complex'].append(feature)
        
        return classification