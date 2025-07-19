import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, mutual_info_score
from sklearn.preprocessing import KBinsDiscretizer
import sqlite3
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DistinctivenessMetrics:
    entropy_score: float
    clustering_score: float
    spread_score: float
    overall_distinctiveness: float


class DistinctivenessAnalyzer:
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
    
    def calculate_distinctiveness(self, feature_name: str, n: int) -> DistinctivenessMetrics:
        values = self.get_feature_values(feature_name, n)
        
        if len(values) < 2:
            return DistinctivenessMetrics(0, 0, 0, 0)
        
        # Method 1: Normalized entropy (0-1, higher = more distinctive)
        hist, bin_edges = np.histogram(values, bins=min(50, len(np.unique(values))))
        # Add small constant to avoid log(0)
        hist_normalized = hist / np.sum(hist) + 1e-10
        entropy = -np.sum(hist_normalized * np.log(hist_normalized))
        max_entropy = np.log(len(hist))  # Maximum possible entropy
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        # Method 2: Silhouette coefficient if we cluster races
        clustering_score = 0
        if len(np.unique(values)) > 1:
            try:
                # Determine optimal number of clusters (between 2 and 5)
                n_clusters = min(5, len(np.unique(values)))
                if n_clusters >= 2 and len(values) > n_clusters:
                    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
                    clusters = kmeans.fit_predict(values.reshape(-1, 1))
                    if len(np.unique(clusters)) > 1:
                        clustering_score = silhouette_score(values.reshape(-1, 1), clusters)
            except:
                clustering_score = 0
        
        # Method 3: Inter-quartile range relative to range
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        range_val = np.max(values) - np.min(values)
        spread_score = iqr / range_val if range_val > 0 else 0
        
        # Combine scores
        overall_distinctiveness = np.mean([normalized_entropy, max(0, clustering_score), spread_score])
        
        return DistinctivenessMetrics(
            entropy_score=normalized_entropy,
            clustering_score=clustering_score,
            spread_score=spread_score,
            overall_distinctiveness=overall_distinctiveness
        )
    
    def analyze_distinctiveness_trajectory(self, feature_name: str) -> Dict[str, any]:
        trajectory = {}
        
        for n in self.n_levels:
            try:
                trajectory[n] = self.calculate_distinctiveness(feature_name, n)
            except Exception as e:
                print(f"Error calculating distinctiveness for {feature_name} at N={n}: {e}")
                continue
        
        if len(trajectory) < 2:
            return {'trajectory': trajectory, 'peak_n': None, 'distinctiveness_range': 0, 'distinctiveness_stability': 0}
        
        # Analyze the trajectory
        scores = [trajectory[n].overall_distinctiveness for n in sorted(trajectory.keys())]
        
        # Find peak distinctiveness
        peak_n = max(trajectory.keys(), key=lambda n: trajectory[n].overall_distinctiveness)
        
        # Calculate range and stability
        distinctiveness_range = max(scores) - min(scores)
        mean_score = np.mean(scores)
        distinctiveness_stability = 1 - (np.std(scores) / mean_score) if mean_score > 0 else 0
        
        return {
            'trajectory': trajectory,
            'peak_n': peak_n,
            'peak_score': trajectory[peak_n].overall_distinctiveness,
            'distinctiveness_range': distinctiveness_range,
            'distinctiveness_stability': distinctiveness_stability,
            'mean_distinctiveness': mean_score
        }
    
    def calculate_information_gain_across_n(self, feature_name: str, target_feature: str = 'abandon_ratio') -> Dict[int, float]:
        ig_scores = {}
        
        for n in self.n_levels:
            try:
                table_name = f"race_features_{n}"
                quoted_feature = self.quote_column(feature_name)
                quoted_target = self.quote_column(target_feature)
                query = f"""
                SELECT {quoted_feature} as feature_value, {quoted_target} as target_value
                FROM {table_name}
                WHERE {quoted_feature} IS NOT NULL AND {quoted_target} IS NOT NULL
                """
                
                conn = self.get_connection()
                df = pd.read_sql_query(query, conn)
                
                if len(df) < 10:
                    continue
                
                X = df['feature_value'].values
                y = df['target_value'].values
                
                # Discretize both variables for MI calculation
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
    
    def analyze_feature_discriminative_power(self, feature_name: str) -> Dict[str, any]:
        # Analyze distinctiveness trajectory
        distinctiveness = self.analyze_distinctiveness_trajectory(feature_name)
        
        # Calculate information gain with multiple targets
        targets = ['abandon_ratio', 'gini_coefficient', 'selection_metric']
        ig_results = {}
        
        for target in targets:
            ig_scores = self.calculate_information_gain_across_n(feature_name, target)
            if ig_scores:
                ig_results[target] = {
                    'scores': ig_scores,
                    'mean_ig': np.mean(list(ig_scores.values())),
                    'max_ig': max(ig_scores.values()),
                    'optimal_n': max(ig_scores.keys(), key=ig_scores.get)
                }
        
        # Determine optimal N range based on both distinctiveness and information gain
        combined_scores = {}
        for n in self.n_levels:
            if n in distinctiveness['trajectory']:
                dist_score = distinctiveness['trajectory'][n].overall_distinctiveness
                ig_score = np.mean([ig_results[t]['scores'].get(n, 0) for t in ig_results if t in ig_results])
                combined_scores[n] = (dist_score + ig_score) / 2
        
        if combined_scores:
            optimal_n = max(combined_scores.keys(), key=combined_scores.get)
            optimal_range = [n for n, score in combined_scores.items() if score >= 0.8 * combined_scores[optimal_n]]
        else:
            optimal_n = None
            optimal_range = []
        
        return {
            'distinctiveness': distinctiveness,
            'information_gain': ig_results,
            'optimal_n': optimal_n,
            'optimal_range': sorted(optimal_range) if optimal_range else [],
            'combined_scores': combined_scores
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
            print(f"Analyzing distinctiveness for {feature}...")
            results[feature] = self.analyze_feature_discriminative_power(feature)
        
        return results
    
    def __del__(self):
        self.close_connection()
    
    def rank_features_by_distinctiveness(self, results: Dict[str, Dict[str, any]]) -> List[Tuple[str, float]]:
        rankings = []
        
        for feature, analysis in results.items():
            # Calculate overall score combining distinctiveness and information gain
            dist_score = analysis['distinctiveness']['mean_distinctiveness']
            
            # Average information gain across all targets
            ig_scores = []
            for target_results in analysis['information_gain'].values():
                if 'mean_ig' in target_results:
                    ig_scores.append(target_results['mean_ig'])
            
            avg_ig = np.mean(ig_scores) if ig_scores else 0
            
            # Combined score
            combined_score = (dist_score + avg_ig) / 2
            rankings.append((feature, combined_score))
        
        # Sort by score (descending)
        rankings.sort(key=lambda x: x[1], reverse=True)
        
        return rankings