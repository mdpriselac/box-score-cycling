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
from rider_experience_features import RiderExperienceFeatures


class FeatureBuilder:
    """Builds complete feature vectors for rider performance prediction."""
    
    def __init__(self, db_path: str):
        """
        Initialize the feature builder.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.result_features = RiderResultFeatures(db_path)
        self.history = RiderHistory(db_path)
        self.experience_calc = RiderExperienceFeatures()
    
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
        
        # Get rider's historical data up to cutoff date
        rider_history = self.history.get_rider_history(rider_id, cutoff_date)
        
        if rider_history.empty:
            # First race - set all experience features to 0
            experience_features = self._get_zero_experience_features()
        else:
            # Calculate experience features from historical data
            experience_features = self._calculate_experience_at_date(
                rider_history, 
                competition_date
            )
        
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
        
        # Add rider age
        complete_features['rider_age_at_race'] = result_features['rider_age']
        
        return complete_features
    
    def _calculate_experience_at_date(self, 
                                     rider_history: pd.DataFrame,
                                     target_date: str) -> Dict:
        """Calculate experience features from historical data."""
        # Filter to only races before the target date
        prior_races = rider_history[rider_history['competition_date'] < target_date]
        
        if len(prior_races) == 0:
            return self._get_zero_experience_features()
        
        # Calculate experience metrics
        total_prior = len(prior_races)
        
        # Competition type counts
        prior_gc = len(prior_races[prior_races['competition_type'] == 'gc'])
        prior_stage = len(prior_races[prior_races['competition_type'] == 'stage'])
        prior_one_day = len(prior_races[prior_races['competition_type'] == 'one_day'])
        
        # Race category counts
        prior_wt = len(prior_races[prior_races['race_category'] == 'wt'])
        prior_pro = len(prior_races[prior_races['race_category'] == 'pro'])
        prior_d1 = len(prior_races[prior_races['race_category'] == 'd1'])
        
        # WT proportion
        wt_proportion = prior_wt / total_prior if total_prior > 0 else 0.0
        
        # Total UCI points
        total_uci_actual = prior_races['uci_points_actual'].sum()
        total_uci_proportional = prior_races['uci_points_proportional'].sum()
        
        return {
            'total_prior_races': total_prior,
            'prior_gc_races': prior_gc,
            'prior_stage_races': prior_stage,
            'prior_one_day_races': prior_one_day,
            'prior_wt_races': prior_wt,
            'prior_pro_races': prior_pro,
            'prior_d1_races': prior_d1,
            'prior_wt_proportion': wt_proportion,
            'total_prior_uci_points_actual': total_uci_actual,
            'total_prior_uci_points_proportional': total_uci_proportional
        }
    
    def _get_zero_experience_features(self) -> Dict:
        """Get zero-valued experience features for a rider's first race."""
        return {
            'total_prior_races': 0,
            'prior_gc_races': 0,
            'prior_stage_races': 0,
            'prior_one_day_races': 0,
            'prior_wt_races': 0,
            'prior_pro_races': 0,
            'prior_d1_races': 0,
            'prior_wt_proportion': 0.0,
            'total_prior_uci_points_actual': 0,
            'total_prior_uci_points_proportional': 0
        }
    
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
        
        experience_features = [
            'total_prior_races',
            'prior_gc_races',
            'prior_stage_races',
            'prior_one_day_races',
            'prior_wt_races',
            'prior_pro_races',
            'prior_d1_races',
            'prior_wt_proportion',
            'total_prior_uci_points_actual',
            'total_prior_uci_points_proportional',
            'rider_age_at_race'
        ]
        
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