import numpy as np
import pandas as pd
from scipy import stats
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class VariabilityMetrics:
    mean: float
    std: float
    cv: float  # Coefficient of variation
    range: float
    iqr: float  # Interquartile range
    skewness: float
    kurtosis: float
    gini: float
    entropy: float


class FeatureVariabilityAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        self._feature_columns = None
        self._conn = None
        
    @property
    def feature_columns(self) -> List[str]:
        if self._feature_columns is None:
            conn = self.get_connection()
            cursor = conn.execute("PRAGMA table_info(race_features_30)")
            columns = [row[1] for row in cursor.fetchall()]
            # Extract only the feature columns (exclude metadata)
            exclude_cols = ['id', 'competition_id', 'percentile_analyzed', 'extraction_date',
                           'competition_name', 'competition_type', 'race_id', 'race_name',
                           'race_category', 'race_year', 'race_date']
            self._feature_columns = [col for col in columns if col not in exclude_cols]
        return self._feature_columns
    
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
    
    def get_feature_values(self, feature_name: str, n: int) -> np.ndarray:
        table_name = f"race_features_{n}"
        quoted_name = self.quote_column(feature_name)
        query = f"""
        SELECT {quoted_name} as feature_value
        FROM {table_name} 
        WHERE {quoted_name} IS NOT NULL
        """
        
        conn = self.get_connection()
        df = pd.read_sql_query(query, conn)
        return df['feature_value'].values
    
    def calculate_gini(self, values: np.ndarray) -> float:
        if len(values) == 0:
            return 0
        
        sorted_values = np.sort(values)
        n = len(values)
        
        # Handle case where all values are zero
        if np.sum(sorted_values) == 0:
            return 0
            
        index = np.arange(1, n + 1)
        return (2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n
    
    def calculate_variability_metrics(self, values: np.ndarray) -> VariabilityMetrics:
        if len(values) == 0:
            return VariabilityMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0)
        
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        # Handle edge cases for CV calculation
        cv = std_val / mean_val if mean_val != 0 else 0
        
        # Calculate entropy using histogram
        hist, _ = np.histogram(values, bins=20)
        hist_normalized = hist + 1e-10  # Avoid log(0)
        entropy = stats.entropy(hist_normalized)
        
        return VariabilityMetrics(
            mean=mean_val,
            std=std_val,
            cv=cv,
            range=np.max(values) - np.min(values),
            iqr=np.percentile(values, 75) - np.percentile(values, 25),
            skewness=stats.skew(values),
            kurtosis=stats.kurtosis(values),
            gini=self.calculate_gini(values),
            entropy=entropy
        )
    
    def analyze_feature_across_n(self, feature_name: str) -> Tuple[Dict[int, VariabilityMetrics], Dict[str, float]]:
        metrics = {}
        
        for n in self.n_levels:
            try:
                values = self.get_feature_values(feature_name, n)
                metrics[n] = self.calculate_variability_metrics(values)
            except Exception as e:
                print(f"Error analyzing {feature_name} at N={n}: {e}")
                continue
        
        # Calculate trends across N
        if len(metrics) >= 2:
            trends = self.calculate_trends(metrics)
        else:
            trends = {}
        
        return metrics, trends
    
    def calculate_trends(self, metrics: Dict[int, VariabilityMetrics]) -> Dict[str, float]:
        n_values = sorted(metrics.keys())
        
        # Extract metric values
        means = [metrics[n].mean for n in n_values]
        cvs = [metrics[n].cv for n in n_values]
        entropies = [metrics[n].entropy for n in n_values]
        
        # Calculate linear trends
        mean_trend = self._calculate_linear_trend(n_values, means)
        cv_trend = self._calculate_linear_trend(n_values, cvs)
        entropy_trend = self._calculate_linear_trend(n_values, entropies)
        
        return {
            'mean_slope': mean_trend['slope'],
            'mean_r2': mean_trend['r2'],
            'cv_slope': cv_trend['slope'],
            'cv_r2': cv_trend['r2'],
            'entropy_slope': entropy_trend['slope'],
            'entropy_r2': entropy_trend['r2']
        }
    
    def _calculate_linear_trend(self, x: List[int], y: List[float]) -> Dict[str, float]:
        if len(x) < 2:
            return {'slope': 0, 'r2': 0}
        
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            return {
                'slope': slope,
                'r2': r_value ** 2
            }
        except:
            return {'slope': 0, 'r2': 0}
    
    def analyze_all_features(self) -> Dict[str, Tuple[Dict[int, VariabilityMetrics], Dict[str, float]]]:
        results = {}
        
        for feature in self.feature_columns:
            print(f"Analyzing variability for {feature}...")
            metrics, trends = self.analyze_feature_across_n(feature)
            results[feature] = (metrics, trends)
        
        return results
    
    def __del__(self):
        self.close_connection()