import numpy as np
import pandas as pd
import sqlite3
from typing import Dict, List, Optional, Union
from .feature_variability_analyzer import FeatureVariabilityAnalyzer
from .monotonicity_analyzer import MonotonicityAnalyzer
from .distinctiveness_analyzer import DistinctivenessAnalyzer
from .feature_pattern_classifier import FeaturePatternClassifier


class RaceTypeFilteredVariabilityAnalyzer(FeatureVariabilityAnalyzer):
    def __init__(self, db_path: str, race_type_filter: Optional[Union[str, List[str]]] = None):
        super().__init__(db_path)
        self.race_type_filter = race_type_filter
    
    def _build_race_type_condition(self) -> str:
        """Build the SQL WHERE condition for race type filtering"""
        if not self.race_type_filter:
            return ""
        
        if isinstance(self.race_type_filter, str):
            return f" AND competition_type = '{self.race_type_filter}'"
        elif isinstance(self.race_type_filter, list):
            types_str = "', '".join(self.race_type_filter)
            return f" AND competition_type IN ('{types_str}')"
        else:
            return ""
    
    def get_feature_values(self, feature_name: str, n: int) -> np.ndarray:
        table_name = f"race_features_{n}"
        quoted_name = self.quote_column(feature_name)
        race_type_condition = self._build_race_type_condition()
        
        query = f"""
        SELECT {quoted_name} as feature_value
        FROM {table_name} 
        WHERE {quoted_name} IS NOT NULL{race_type_condition}
        """
        
        conn = self.get_connection()
        df = pd.read_sql_query(query, conn)
        return df['feature_value'].values


class RaceTypeFilteredMonotonicityAnalyzer(MonotonicityAnalyzer):
    def __init__(self, db_path: str, race_type_filter: Optional[Union[str, List[str]]] = None):
        super().__init__(db_path)
        self.race_type_filter = race_type_filter
    
    def _build_race_type_condition(self) -> str:
        """Build the SQL WHERE condition for race type filtering"""
        if not self.race_type_filter:
            return ""
        
        if isinstance(self.race_type_filter, str):
            return f" AND competition_type = '{self.race_type_filter}'"
        elif isinstance(self.race_type_filter, list):
            types_str = "', '".join(self.race_type_filter)
            return f" AND competition_type IN ('{types_str}')"
        else:
            return ""
    
    def get_feature_stats_by_n(self, feature_name: str) -> Dict[int, Dict[str, float]]:
        feature_stats = {}
        quoted_name = self.quote_column(feature_name)
        race_type_condition = self._build_race_type_condition()
        
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
            WHERE {quoted_name} IS NOT NULL{race_type_condition}
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


class RaceTypeFilteredDistinctivenessAnalyzer(DistinctivenessAnalyzer):
    def __init__(self, db_path: str, race_type_filter: Optional[Union[str, List[str]]] = None):
        super().__init__(db_path)
        self.race_type_filter = race_type_filter
    
    def _build_race_type_condition(self) -> str:
        """Build the SQL WHERE condition for race type filtering"""
        if not self.race_type_filter:
            return ""
        
        if isinstance(self.race_type_filter, str):
            return f" AND competition_type = '{self.race_type_filter}'"
        elif isinstance(self.race_type_filter, list):
            types_str = "', '".join(self.race_type_filter)
            return f" AND competition_type IN ('{types_str}')"
        else:
            return ""
    
    def get_feature_values(self, feature_name: str, n: int) -> np.ndarray:
        table_name = f"race_features_{n}"
        quoted_name = self.quote_column(feature_name)
        race_type_condition = self._build_race_type_condition()
        
        query = f"""
        SELECT {quoted_name} as feature_value
        FROM {table_name} 
        WHERE {quoted_name} IS NOT NULL{race_type_condition}
        """
        
        conn = self.get_connection()
        df = pd.read_sql_query(query, conn)
        return df['feature_value'].values
    
    def calculate_information_gain_across_n(self, feature_name: str, target_feature: str = 'abandon_ratio') -> Dict[int, float]:
        ig_scores = {}
        
        for n in self.n_levels:
            try:
                table_name = f"race_features_{n}"
                quoted_feature = self.quote_column(feature_name)
                quoted_target = self.quote_column(target_feature)
                race_type_condition = self._build_race_type_condition()
                
                query = f"""
                SELECT {quoted_feature} as feature_value, {quoted_target} as target_value
                FROM {table_name}
                WHERE {quoted_feature} IS NOT NULL AND {quoted_target} IS NOT NULL{race_type_condition}
                """
                
                conn = self.get_connection()
                df = pd.read_sql_query(query, conn)
                
                if len(df) < 10:
                    continue
                
                X = df['feature_value'].values
                y = df['target_value'].values
                
                # Discretize both variables for MI calculation
                from sklearn.preprocessing import KBinsDiscretizer
                from sklearn.metrics import mutual_info_score
                from scipy import stats
                
                discretizer_x = KBinsDiscretizer(n_bins=10, encode='ordinal', strategy='quantile', subsample=None)
                discretizer_y = KBinsDiscretizer(n_bins=5, encode='ordinal', strategy='quantile', subsample=None)
                
                X_discrete = discretizer_x.fit_transform(X.reshape(-1, 1)).ravel()
                y_discrete = discretizer_y.fit_transform(y.reshape(-1, 1)).ravel()
                
                # Calculate mutual information
                mi_score = mutual_info_score(X_discrete, y_discrete)
                
                # Normalize by the entropy of the target
                target_entropy = stats.entropy(np.histogram(y_discrete, bins=5)[0] + 1e-10)
                normalized_mi = mi_score / target_entropy if target_entropy > 0 else 0
                
                ig_scores[n] = normalized_mi
                
            except Exception as e:
                print(f"Error calculating information gain for {feature_name} at N={n}: {e}")
                continue
        
        return ig_scores


class RaceTypeFilteredPatternClassifier(FeaturePatternClassifier):
    def __init__(self, db_path: str, race_type_filter: Optional[Union[str, List[str]]] = None):
        self.db_path = db_path
        self.n_levels = [30, 40, 50, 60, 70, 80, 90, 100]
        self.race_type_filter = race_type_filter
        
        # Use filtered analyzers
        self.variability_analyzer = RaceTypeFilteredVariabilityAnalyzer(db_path, race_type_filter)
        self.monotonicity_analyzer = RaceTypeFilteredMonotonicityAnalyzer(db_path, race_type_filter)
    
    def get_feature_stats_across_n(self, feature_name: str) -> Dict[int, Dict[str, float]]:
        stats_by_n = {}
        quoted_name = self.variability_analyzer.quote_column(feature_name)
        race_type_condition = self.variability_analyzer._build_race_type_condition()
        
        for n in self.n_levels:
            table_name = f"race_features_{n}"
            query = f"""
            SELECT 
                {quoted_name} as value
            FROM {table_name}
            WHERE {quoted_name} IS NOT NULL{race_type_condition}
            """
            
            conn = self.variability_analyzer.get_connection()
            df = pd.read_sql_query(query, conn)
                
            if len(df) > 0:
                values = df['value'].values
                
                # Calculate entropy
                hist, _ = np.histogram(values, bins=20)
                hist_normalized = hist / np.sum(hist) + 1e-10
                entropy = -np.sum(hist_normalized * np.log(hist_normalized))
                
                from scipy import stats
                stats_by_n[n] = {
                    'mean': np.mean(values),
                    'variance': np.var(values),
                    'std': np.std(values),
                    'cv': np.std(values) / np.mean(values) if np.mean(values) != 0 else 0,
                    'entropy': entropy,
                    'skewness': stats.skew(values),
                    'kurtosis': stats.kurtosis(values)
                }
        
        return stats_by_n