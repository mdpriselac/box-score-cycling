"""
Module for building feature vectors for rider performance prediction.

This module provides a single-entry point interface for getting all features
needed for a rider-competition pair, which can then be used for both
individual predictions and bulk dataset generation.

Key function: get_prediction_features() returns a complete feature vector
for a single rider result including experience features calculated up to 
the race date.
"""

import sqlite3
import pandas as pd
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta

from rider_result_features import RiderResultFeatures
from rider_history import RiderHistory
from enhanced_rider_experience import EnhancedRiderExperience


class FeatureBuilder:
    """Builds complete feature vectors for rider performance prediction."""
    
    def __init__(self, db_path: str, use_enhanced_experience: bool = True):
        """
        Initialize the feature builder.
        
        Args:
            db_path: Path to the SQLite database
            use_enhanced_experience: Whether to use enhanced experience features (default: True)
        """
        self.db_path = db_path
        self.result_features = RiderResultFeatures(db_path)
        self.history = RiderHistory(db_path)
        
        # Experience features are now pre-computed in the database
        self.experience_feature_names = self._get_experience_feature_names_from_db()
    
    def _get_experience_feature_names_from_db(self) -> List[str]:
        """Dynamically get experience feature names from the database schema."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(rider_results)")
            columns = cursor.fetchall()
            
            # Find columns that are experience features (added by the migration)
            experience_columns = []
            for column in columns:
                col_name = column[1]  # Column name is at index 1
                if (col_name.startswith('prior_') or 
                    col_name.startswith('total_prior_') or
                    col_name == 'rider_age' or
                    col_name.endswith('_success_rate')):
                    experience_columns.append(col_name)
            
            # Add calculated features that we derive from the base data
            calculated_features = ['overall_success_rate', 'prior_wt_success_rate', 
                                 'prior_gc_success_rate', 'prior_stage_success_rate', 
                                 'prior_one_day_success_rate']
            
            # Combine and return unique features
            all_features = list(set(experience_columns + calculated_features))
            return sorted(all_features)
            
        finally:
            conn.close()
    
    def get_prediction_features(self, 
                               rider_id: int,
                               competition_id: int,
                               cutoff_date: Optional[str] = None) -> Optional[Dict]:
        """
        Get complete feature vector for a single rider-competition pair.
        
        This is the main entry point for getting features for prediction.
        
        Args:
            rider_id: The rider ID
            competition_id: The competition ID
            cutoff_date: Optional date cutoff for experience calculation.
                        If None, uses the competition date minus 1 day.
                        Format: 'YYYY-MM-DD'
            
        Returns:
            Dictionary containing all features and target variables, or None if not found
            
        Example return:
        {
            # Metadata
            'rider_id': 1000,
            'competition_id': 12345,
            'competition_type': 'stage',
            'race_category': 'wt',
            
            # Race features (prefixed with rf_)
            'rf_clumpiness_score': 0.85,
            'rf_variance_absolute': 120.5,
            ...
            
            # Race kind features (prefixed with rkf_)
            'rkf_cluster_label': 2,
            'rkf_local_density': 0.95,
            ...
            
            # Experience features
            'total_prior_races': 156,
            'prior_wt_races': 89,
            'prior_wt_proportion': 0.57,
            ...
            
            # Target variables
            'uci_points_actual': 25,
            'uci_points_proportional': 30.5
        }
        """
        # First, get the result ID for this rider-competition pair
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Get result ID and competition date
            query = """
            SELECT rr.id, c.date, c.competition_type
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ? AND rr.competition_id = ?
            """
            cursor.execute(query, (rider_id, competition_id))
            result = cursor.fetchone()
            
            if not result:
                return None
                
            result_id, competition_date, competition_type = result
            
        finally:
            conn.close()
        
        # If no cutoff date provided, use competition date minus 1 day
        if cutoff_date is None:
            comp_dt = datetime.strptime(competition_date, '%Y-%m-%d')
            cutoff_dt = comp_dt - timedelta(days=1)
            cutoff_date = cutoff_dt.strftime('%Y-%m-%d')
        
        # Get the race features and basic info for this result
        result_features = self.result_features.get_features_for_result(result_id)
        if not result_features:
            return None
        
        # Get experience features from pre-computed database values
        experience_features = self._get_experience_features_from_db(rider_id, competition_id)
        
        # Combine all features
        complete_features = {
            # Metadata
            'rider_id': rider_id,
            'rider_name': result_features['rider_name'],
            'competition_id': competition_id,
            'competition_name': result_features['competition_name'],
            'competition_type': competition_type,
            'race_name': result_features['race_name'],
            'race_category': result_features['race_category'],
            'race_year': result_features['race_year'],
            'competition_date': competition_date,
            'place': result_features['place'],
            
            # Target variables
            'uci_points_actual': result_features['uci_points_actual'],
            'uci_points_proportional': result_features['uci_points_proportional']
        }
        
        # Add race features (rf_*)
        for key, value in result_features.items():
            if key.startswith('rf_'):
                complete_features[key] = value
        
        # Add race kind features (rkf_*)
        for key, value in result_features.items():
            if key.startswith('rkf_'):
                complete_features[key] = value
        
        # Add experience features
        complete_features.update(experience_features)
        
        return complete_features
    
    def _get_experience_features_from_db(self, rider_id: int, competition_id: int) -> Dict:
        """Get experience features from pre-computed database values."""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get pre-computed experience features directly from database
            query = """
            SELECT 
                prior_wt_points_actual, prior_wt_points_proportional,
                prior_pro_points_actual, prior_pro_points_proportional,
                prior_d1_points_actual, prior_d1_points_proportional,
                prior_gc_points_actual, prior_gc_points_proportional,
                prior_stage_points_actual, prior_stage_points_proportional,
                prior_one_day_points_actual, prior_one_day_points_proportional,
                prior_wt_races, prior_pro_races, prior_d1_races,
                prior_gc_races, prior_stage_races, prior_one_day_races,
                total_prior_races, total_prior_points_actual,
                total_prior_points_proportional, prior_wt_proportion,
                rider_age
            FROM rider_results
            WHERE rider_id = ? AND competition_id = ?
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, competition_id))
            row = cursor.fetchone()
            
            if row:
                # Map database columns to feature names
                experience_features = {
                    'prior_wt_points_actual': row[0],
                    'prior_wt_points_proportional': row[1],
                    'prior_pro_points_actual': row[2],
                    'prior_pro_points_proportional': row[3],
                    'prior_d1_points_actual': row[4],
                    'prior_d1_points_proportional': row[5],
                    'prior_gc_points_actual': row[6],
                    'prior_gc_points_proportional': row[7],
                    'prior_stage_points_actual': row[8],
                    'prior_stage_points_proportional': row[9],
                    'prior_one_day_points_actual': row[10],
                    'prior_one_day_points_proportional': row[11],
                    'prior_wt_races': row[12],
                    'prior_pro_races': row[13],
                    'prior_d1_races': row[14],
                    'prior_gc_races': row[15],
                    'prior_stage_races': row[16],
                    'prior_one_day_races': row[17],
                    'total_prior_races': row[18],
                    'total_prior_points_actual': row[19],
                    'total_prior_points_proportional': row[20],
                    'prior_wt_proportion': row[21],
                    'rider_age': row[22]
                }
                
                # Calculate success rates from the base data
                total_races = experience_features['total_prior_races']
                if total_races > 0:
                    experience_features['overall_success_rate'] = (
                        1.0 if experience_features['total_prior_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_wt_success_rate'] = (
                        1.0 if experience_features['prior_wt_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_gc_success_rate'] = (
                        1.0 if experience_features['prior_gc_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_stage_success_rate'] = (
                        1.0 if experience_features['prior_stage_points_actual'] > 0 else 0.0
                    )
                    experience_features['prior_one_day_success_rate'] = (
                        1.0 if experience_features['prior_one_day_points_actual'] > 0 else 0.0
                    )
                else:
                    experience_features['overall_success_rate'] = 0.0
                    experience_features['prior_wt_success_rate'] = 0.0
                    experience_features['prior_gc_success_rate'] = 0.0
                    experience_features['prior_stage_success_rate'] = 0.0
                    experience_features['prior_one_day_success_rate'] = 0.0
                
                return experience_features
            else:
                # No result found - return zero features
                return self._get_zero_experience_features()
                
        finally:
            conn.close()
    
    def _get_zero_experience_features(self) -> Dict:
        """Get zero-valued experience features for a rider's first race."""
        zero_features = {}
        for feature_name in self.experience_feature_names:
            # Special handling for proportion/rate features (should be 0.0)
            if 'proportion' in feature_name or 'rate' in feature_name:
                zero_features[feature_name] = 0.0
            else:
                zero_features[feature_name] = 0
        return zero_features
    
    def get_feature_names(self, competition_type: str) -> Dict[str, List[str]]:
        """
        Get the feature names for a specific competition type.
        
        Args:
            competition_type: 'gc', 'stage', or 'one_day'
            
        Returns:
            Dictionary with 'race_features', 'race_kind_features', and 'experience_features'
        """
        # Get configuration-based feature names
        feature_info = self.result_features.get_feature_info()
        
        if competition_type == 'gc':
            race_features = [f'rf_{col}' for col in feature_info['gc_features']]
        elif competition_type in ['stage', 'one_day']:
            # Stage and one-day use the same features
            race_features = [f'rf_{col}' for col in feature_info['stage_features']]
        else:
            raise ValueError(f"Unknown competition type: {competition_type}")
        
        race_kind_features = [f'rkf_{col}' for col in feature_info['race_kind_features']]
        
        # Use dynamic experience feature names from the calculator
        experience_features = self.experience_feature_names
        
        return {
            'race_features': race_features,
            'race_kind_features': race_kind_features,
            'experience_features': experience_features
        }
    
    def build_bulk_dataset(self,
                          rider_competition_pairs: List[Tuple[int, int]],
                          cutoff_date: Optional[str] = None) -> pd.DataFrame:
        """
        Build features for multiple rider-competition pairs.
        
        This is a convenience method that uses get_prediction_features()
        internally for each pair.
        
        Args:
            rider_competition_pairs: List of (rider_id, competition_id) tuples
            cutoff_date: Optional cutoff date for all pairs
            
        Returns:
            DataFrame with all feature vectors
        """
        features_list = []
        
        for i, (rider_id, competition_id) in enumerate(rider_competition_pairs):
            if i % 100 == 0:
                print(f"Processing pair {i+1}/{len(rider_competition_pairs)}")
            
            features = self.get_prediction_features(rider_id, competition_id, cutoff_date)
            if features:
                features_list.append(features)
        
        if not features_list:
            return pd.DataFrame()
        
        return pd.DataFrame(features_list)


if __name__ == "__main__":
    # Test the feature builder
    db_path = "database/database/cycling_races.db"
    builder = FeatureBuilder(db_path)
    
    # Test single prediction features
    print("Testing single prediction features...")
    
    # You'll need to provide valid rider_id and competition_id from your database
    test_rider_id = 1000
    test_competition_id = 1000  # You may need to find a valid competition_id
    
    features = builder.get_prediction_features(
        rider_id=test_rider_id,
        competition_id=test_competition_id
    )
    
    if features:
        print(f"\nFeatures for rider {features['rider_name']} in {features['competition_name']}:")
        print(f"Competition type: {features['competition_type']}")
        print(f"Total features: {len(features)}")
        
        # Show feature breakdown
        race_features = [k for k in features.keys() if k.startswith('rf_')]
        race_kind_features = [k for k in features.keys() if k.startswith('rkf_')]
        experience_features = [k for k in features.keys() if k.startswith(('prior_', 'total_prior'))]
        
        print(f"\nFeature breakdown:")
        print(f"  Race features: {len(race_features)}")
        print(f"  Race kind features: {len(race_kind_features)}")
        print(f"  Experience features: {len(experience_features)}")
        
        print(f"\nExperience summary:")
        print(f"  Prior races: {features.get('total_prior_races', 0)}")
        print(f"  Prior WT races: {features.get('prior_wt_races', 0)}")
        print(f"  Prior UCI points: {features.get('total_prior_uci_points_actual', 0)}")
        
        print(f"\nTarget variables:")
        print(f"  Actual UCI points: {features['uci_points_actual']}")
        print(f"  Proportional UCI points: {features['uci_points_proportional']}")
        
        # Test feature names method
        print(f"\nFeature names for {features['competition_type']} competitions:")
        feature_names = builder.get_feature_names(features['competition_type'])
        for category, names in feature_names.items():
            print(f"  {category}: {len(names)} features")
    else:
        print("No features found - check that the rider_id and competition_id are valid")
    
    # Test bulk dataset building
    print("\n" + "="*50)
    print("Testing bulk dataset building...")
    
    # Get some valid rider-competition pairs for testing
    conn = sqlite3.connect(db_path)
    query = """
    SELECT DISTINCT rr.rider_id, rr.competition_id
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    WHERE c.date BETWEEN '2023-01-01' AND '2023-12-31'
    LIMIT 10
    """
    pairs = pd.read_sql_query(query, conn).values.tolist()
    conn.close()
    
    if pairs:
        print(f"Building features for {len(pairs)} rider-competition pairs...")
        bulk_df = builder.build_bulk_dataset(pairs)
        
        if not bulk_df.empty:
            print(f"Built dataset with {len(bulk_df)} rows and {len(bulk_df.columns)} columns")
            print(f"Competition types: {bulk_df['competition_type'].value_counts().to_dict()}")
            print(f"Race categories: {bulk_df['race_category'].value_counts().to_dict()}")