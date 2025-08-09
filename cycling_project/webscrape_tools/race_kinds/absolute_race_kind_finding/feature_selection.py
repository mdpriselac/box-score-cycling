"""
Feature selection module for absolute race kind clustering.
Selects optimal features for each inclusion percentage based on:
1. Separability scores from prior analysis
2. Avoiding redundancy between normalized/absolute versions
3. Removing highly correlated features (>90%)
"""

import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
import json
import os
from typing import Dict, List, Tuple, Set
from scipy.stats import pearsonr
import warnings
warnings.filterwarnings('ignore')

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


class FeatureSelector:
    """Handles feature selection for each inclusion percentage."""
    
    def __init__(self, db_path: str = None, has_breakdown: bool = None):
        """Initialize with database connection."""
        if db_path is None:
            db_path = self.find_database()
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        # Use all available percentiles - the JSON files have all of them
        self.percentiles = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]
        self.selected_features_by_percentile = {}
        self.feature_scores_by_percentile = {}
        
    def find_database(self):
        """Find the SQLite database file."""
        if HAS_DOTENV:
            load_dotenv()
            db_path = os.getenv('DB_PATH')
            if db_path and os.path.exists(db_path):
                return db_path
        
        # Go up to find db
        db_path = Path(__file__).parent.parent.parent / "database" / "database" / "cycling_races.db"
        if db_path.exists():
            return str(db_path)
        
        raise FileNotFoundError("Database not found")
    
    def load_analysis_scores(self, has_breakdown: bool) -> Dict:
        """Load separability scores from prior analysis - from JSON for complete data."""
        analysis_dir = Path(__file__).parent.parent / "absolute_stage_kind_support_analysis"
        
        if has_breakdown:
            json_file = analysis_dir / "absolute_breakdown_analysis.json"
        else:
            json_file = analysis_dir / "absolute_no_breakdown_analysis.json"
        
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        # Organize scores by percentile and feature
        scores_by_percentile = {}
        
        # Initialize empty dicts for each percentile
        for percentile in self.percentiles:
            scores_by_percentile[percentile] = {}
        
        # Extract scores from the JSON structure
        for feature_name, feature_data in data['feature_results'].items():
            if isinstance(feature_data, list):
                for entry in feature_data:
                    if 'percentile' in entry and 'separability_score' in entry:
                        perc = entry['percentile']
                        if perc in self.percentiles:
                            # Clean up feature name - remove quotes if present
                            clean_feature = feature_name.strip('"')
                            scores_by_percentile[perc][clean_feature] = entry['separability_score']
        
        return scores_by_percentile
    
    def get_available_features(self, percentile: int) -> List[str]:
        """Get list of available features from race_features_N table."""
        table_name = f"race_features_{percentile}"
        
        # Get column names
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        # Exclude non-feature columns and non-existent imputed columns
        exclude_cols = [
            'id', 'competition_id', 'percentile_analyzed', 'extraction_date',
            'competition_name', 'competition_type', 'race_id', 'race_name',
            'race_category', 'race_year', 'race_date',
            'kurtosis_absolute_imputed', 'kurtosis_normalized_imputed'  # These don't exist
        ]
        
        features = []
        for col in columns:
            col_name = col[1]
            if col_name not in exclude_cols:
                features.append(col_name)
        
        return features
    
    def load_feature_data(self, percentile: int, features: List[str], 
                         has_breakdown: bool, min_finishers: int = 40) -> pd.DataFrame:
        """Load feature data for a specific percentile."""
        table_name = f"race_features_{percentile}"
        
        # Build query with properly quoted column names and table prefix
        quoted_features = []
        for f in features:
            if f[0].isdigit():
                quoted_features.append(f'rf."{f}"')
            else:
                quoted_features.append(f'rf.{f}')
        
        feature_cols = ', '.join(quoted_features)
        
        # Build the query based on breakdown status
        if has_breakdown:
            # Find races with kurtosis breakdown
            query = f"""
            WITH breakdown_races AS (
                SELECT DISTINCT competition_id
                FROM (
                    SELECT competition_id, 
                           kurtosis_normalized,
                           percentile_analyzed
                    FROM race_features_10
                    WHERE kurtosis_normalized IS NULL
                    UNION ALL
                    SELECT competition_id,
                           kurtosis_normalized,
                           percentile_analyzed
                    FROM race_features_15
                    WHERE kurtosis_normalized IS NULL
                    UNION ALL
                    SELECT competition_id,
                           kurtosis_normalized,
                           percentile_analyzed
                    FROM race_features_20
                    WHERE kurtosis_normalized IS NULL
                    UNION ALL
                    SELECT competition_id,
                           kurtosis_normalized,
                           percentile_analyzed
                    FROM race_features_25
                    WHERE kurtosis_normalized IS NULL
                )
            )
            SELECT rf.competition_id, {feature_cols}
            FROM {table_name} rf
            INNER JOIN race_features_100 rf100 ON rf.competition_id = rf100.competition_id
            WHERE rf.competition_id IN (SELECT competition_id FROM breakdown_races)
            AND rf.total_finishers >= {min_finishers}
            AND rf100.winning_time >= 5400
            AND rf100.winning_time <= 28800
            """
        else:
            # Find races without kurtosis breakdown
            query = f"""
            WITH no_breakdown_races AS (
                SELECT DISTINCT rf100.competition_id
                FROM race_features_100 rf100
                WHERE NOT EXISTS (
                    SELECT 1 FROM race_features_10 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
                ) AND NOT EXISTS (
                    SELECT 1 FROM race_features_15 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
                ) AND NOT EXISTS (
                    SELECT 1 FROM race_features_20 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
                ) AND NOT EXISTS (
                    SELECT 1 FROM race_features_25 WHERE competition_id = rf100.competition_id AND kurtosis_normalized IS NULL
                )
            )
            SELECT rf.competition_id, {feature_cols}
            FROM {table_name} rf
            INNER JOIN race_features_100 rf100 ON rf.competition_id = rf100.competition_id
            WHERE rf.competition_id IN (SELECT competition_id FROM no_breakdown_races)
            AND rf.total_finishers >= {min_finishers}
            AND rf100.winning_time >= 5400
            AND rf100.winning_time <= 28800
            """
        
        df = pd.read_sql_query(query, self.conn)
        return df
    
    def calculate_correlation_matrix(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate correlation matrix for features."""
        # Remove competition_id column if present
        feature_data = data.drop(columns=['competition_id'], errors='ignore')
        
        # Handle missing values
        feature_data = feature_data.fillna(feature_data.mean())
        
        # Calculate correlation matrix
        corr_matrix = feature_data.corr(method='pearson')
        
        return corr_matrix
    
    def select_features_for_percentile(self, percentile: int, has_breakdown: bool,
                                      correlation_threshold: float = 0.9) -> List[str]:
        """
        Select features for a specific percentile following the rules:
        1. Start with highest rated feature from analysis
        2. For stats with both normalized and absolute, only include higher performer
        3. Remove features correlated > 90% with already included features
        """
        # Load scores from analysis
        scores = self.load_analysis_scores(has_breakdown)
        percentile_scores = scores.get(percentile, {})
        
        if not percentile_scores:
            print(f"No scores found for percentile {percentile}")
            return []
        
        # Get available features
        available_features = self.get_available_features(percentile)
        
        # Filter to only features with scores
        scored_features = [(f, percentile_scores.get(f, 0)) for f in available_features 
                          if f in percentile_scores]
        
        # Sort by score (highest first)
        scored_features.sort(key=lambda x: x[1], reverse=True)
        
        if not scored_features:
            print(f"No scored features available for percentile {percentile}")
            return []
        
        # Load data for correlation calculation
        all_features = [f[0] for f in scored_features]
        data = self.load_feature_data(percentile, all_features, has_breakdown)
        
        if data.empty:
            print(f"No data available for percentile {percentile}")
            return []
        
        # Calculate correlation matrix
        corr_matrix = self.calculate_correlation_matrix(data)
        
        # Feature selection process
        selected_features = []
        excluded_features = set()
        
        for feature, score in scored_features:
            if feature in excluded_features:
                continue
            
            # Check if this is a normalized/absolute pair
            base_name = feature.replace('_normalized', '').replace('_absolute', '')
            is_normalized = '_normalized' in feature
            is_absolute = '_absolute' in feature
            
            if is_normalized or is_absolute:
                # Find the pair
                if is_normalized:
                    pair_feature = base_name + '_absolute'
                else:
                    pair_feature = base_name + '_normalized'
                
                # If pair exists and has higher score, skip this one
                if pair_feature in percentile_scores:
                    if percentile_scores[pair_feature] > score:
                        excluded_features.add(feature)
                        continue
                    else:
                        # Exclude the pair
                        excluded_features.add(pair_feature)
            
            # Check correlation with already selected features
            should_exclude = False
            for selected in selected_features:
                if selected in corr_matrix.columns and feature in corr_matrix.columns:
                    correlation = abs(corr_matrix.loc[feature, selected])
                    if correlation > correlation_threshold:
                        should_exclude = True
                        break
            
            if not should_exclude:
                selected_features.append(feature)
                excluded_features.add(feature)
        
        return selected_features
    
    def select_all_features(self, has_breakdown: bool) -> Dict[int, List[str]]:
        """Select features for all percentiles."""
        results = {}
        
        for percentile in self.percentiles:
            print(f"\nSelecting features for percentile {percentile}...")
            features = self.select_features_for_percentile(percentile, has_breakdown)
            results[percentile] = features
            print(f"Selected {len(features)} features: {features[:5]}...")  # Show first 5
        
        self.selected_features_by_percentile = results
        return results
    
    def save_selection_results(self, has_breakdown: bool):
        """Save feature selection results to file."""
        output_dir = Path(__file__).parent / "feature_selection_results"
        output_dir.mkdir(exist_ok=True)
        
        suffix = "with_breakdown" if has_breakdown else "no_breakdown"
        output_file = output_dir / f"selected_features_{suffix}.json"
        
        # Prepare data for saving
        save_data = {
            'has_breakdown': has_breakdown,
            'percentiles': self.percentiles,
            'feature_selections': self.selected_features_by_percentile,
            'feature_counts': {p: len(features) 
                              for p, features in self.selected_features_by_percentile.items()}
        }
        
        with open(output_file, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        print(f"\nFeature selection results saved to {output_file}")
        
        # Also save a summary CSV
        summary_data = []
        for percentile, features in self.selected_features_by_percentile.items():
            for feature in features:
                summary_data.append({
                    'percentile': percentile,
                    'feature': feature,
                    'has_breakdown': has_breakdown
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_file = output_dir / f"feature_summary_{suffix}.csv"
            summary_df.to_csv(summary_file, index=False)
            print(f"Feature summary saved to {summary_file}")
    
    def analyze_common_features(self) -> Dict:
        """Analyze which features appear across multiple percentiles."""
        feature_counts = {}
        
        for percentile, features in self.selected_features_by_percentile.items():
            for feature in features:
                if feature not in feature_counts:
                    feature_counts[feature] = []
                feature_counts[feature].append(percentile)
        
        # Find features that appear in all percentiles
        universal_features = [f for f, percs in feature_counts.items() 
                            if len(percs) == len(self.percentiles)]
        
        # Find features that appear in most percentiles (>75%)
        common_features = [f for f, percs in feature_counts.items() 
                         if len(percs) > len(self.percentiles) * 0.75]
        
        return {
            'universal_features': universal_features,
            'common_features': common_features,
            'feature_frequency': feature_counts
        }


def main():
    """Run feature selection for both breakdown and no-breakdown races."""
    
    # Process races with breakdown
    print("="*50)
    print("Processing races WITH kurtosis breakdown...")
    print("="*50)
    
    selector_breakdown = FeatureSelector()
    selector_breakdown.select_all_features(has_breakdown=True)
    selector_breakdown.save_selection_results(has_breakdown=True)
    
    # Analyze common features
    analysis_breakdown = selector_breakdown.analyze_common_features()
    print(f"\nUniversal features (appear in all percentiles): {analysis_breakdown['universal_features']}")
    print(f"Common features (>75% of percentiles): {len(analysis_breakdown['common_features'])} features")
    
    # Process races without breakdown
    print("\n" + "="*50)
    print("Processing races WITHOUT kurtosis breakdown...")
    print("="*50)
    
    selector_no_breakdown = FeatureSelector()
    selector_no_breakdown.select_all_features(has_breakdown=False)
    selector_no_breakdown.save_selection_results(has_breakdown=False)
    
    # Analyze common features
    analysis_no_breakdown = selector_no_breakdown.analyze_common_features()
    print(f"\nUniversal features (appear in all percentiles): {analysis_no_breakdown['universal_features']}")
    print(f"Common features (>75% of percentiles): {len(analysis_no_breakdown['common_features'])} features")


if __name__ == "__main__":
    main()