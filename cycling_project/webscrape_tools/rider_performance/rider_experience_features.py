"""
Module for calculating rider experience features from rider history data.

This module works as a post-processing step that takes the DataFrame output from 
RiderHistory and adds cumulative experience features based on chronological race history.

Integration Flow:
Database → RiderHistory → RiderExperienceFeatures → ML Model

The RiderHistory module already joins all necessary database tables and provides:
- rider_id, rider_name, rider_age
- competition_id, competition_name, competition_type, competition_date
- race_name, race_category, race_year
- place, time_gap, percentile
- uci_points_actual, uci_points_proportional
- All race features (rf_*) and race kind features (rkf_*)

This module adds cumulative experience metrics calculated from the chronologically
sorted race history up to each race date.
"""

import pandas as pd
from typing import Dict, List
import numpy as np


class RiderExperienceFeatures:
    """
    Calculates cumulative experience features for rider results.
    
    Takes DataFrame output from RiderHistory and adds experience metrics
    based on each rider's prior race history up to each race date.
    """
    
    def __init__(self):
        """Initialize the experience feature calculator."""
        pass
    
    def add_experience_features(self, rider_history_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add experience features to rider history data.
        
        Args:
            rider_history_df: DataFrame from RiderHistory.get_rider_history() or 
                            RiderHistory.get_all_rider_histories()
                            
        Expected columns in input DataFrame:
        - rider_id: Rider identifier
        - competition_date: Date of competition (for chronological sorting)
        - competition_type: 'gc', 'stage', or 'one_day'
        - race_category: 'wt', 'pro', or 'd1'
        - rider_age: Age of rider at time of race
        - uci_points_actual: Actual UCI points earned
        - uci_points_proportional: Proportional UCI points earned
        - result_id: Unique result identifier (for merging)
            
        Returns:
            DataFrame with additional experience feature columns:
            - total_prior_races: Total races completed before this race
            - prior_gc_races: GC races completed before this race
            - prior_stage_races: Stage races completed before this race
            - prior_one_day_races: One-day races completed before this race
            - prior_wt_races: WT races completed before this race
            - prior_pro_races: Pro races completed before this race
            - prior_d1_races: D1 races completed before this race
            - prior_wt_proportion: Proportion of prior races that were WT level
            - total_prior_uci_points_actual: Total actual UCI points earned before this race
            - total_prior_uci_points_proportional: Total proportional UCI points earned before this race
            - rider_age_at_race: Rider age at time of race (same as rider_age)
        """
        if rider_history_df.empty:
            return rider_history_df
        
        # Verify required columns exist
        required_columns = [
            'rider_id', 'competition_date', 'competition_type', 'race_category',
            'rider_age', 'uci_points_actual', 'uci_points_proportional', 'result_id'
        ]
        
        missing_columns = [col for col in required_columns if col not in rider_history_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Make a copy to avoid modifying original
        df = rider_history_df.copy()
        
        # Ensure proper sorting by rider and date
        df = df.sort_values(['rider_id', 'competition_date'])
        
        # Calculate experience features for each rider
        experience_features = []
        
        for rider_id in df['rider_id'].unique():
            rider_df = df[df['rider_id'] == rider_id].copy()
            rider_experience = self._calculate_rider_experience(rider_df)
            experience_features.append(rider_experience)
        
        # Combine all rider experience features
        experience_df = pd.concat(experience_features, ignore_index=True)
        
        # Merge back with original data
        # Use result_id as the key to maintain exact alignment
        final_df = df.merge(
            experience_df[['result_id'] + self._get_experience_column_names()],
            on='result_id',
            how='left'
        )
        
        return final_df
    
    def _calculate_rider_experience(self, rider_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate experience features for a single rider."""
        rider_df = rider_df.sort_values('competition_date')
        
        # Initialize experience feature columns
        experience_features = {
            'result_id': rider_df['result_id'].values,
            'total_prior_races': [],
            'prior_gc_races': [],
            'prior_stage_races': [],
            'prior_one_day_races': [],
            'prior_wt_races': [],
            'prior_pro_races': [],
            'prior_d1_races': [],
            'prior_wt_proportion': [],
            'total_prior_uci_points_actual': [],
            'total_prior_uci_points_proportional': [],
            'rider_age_at_race': []
        }
        
        # Calculate cumulative features for each result
        for i in range(len(rider_df)):
            # Get all prior results (everything before index i)
            prior_results = rider_df.iloc[:i]
            
            # Total prior races
            total_prior = len(prior_results)
            experience_features['total_prior_races'].append(total_prior)
            
            if total_prior == 0:
                # First race - no prior experience
                experience_features['prior_gc_races'].append(0)
                experience_features['prior_stage_races'].append(0)
                experience_features['prior_one_day_races'].append(0)
                experience_features['prior_wt_races'].append(0)
                experience_features['prior_pro_races'].append(0)
                experience_features['prior_d1_races'].append(0)
                experience_features['prior_wt_proportion'].append(0.0)
                experience_features['total_prior_uci_points_actual'].append(0)
                experience_features['total_prior_uci_points_proportional'].append(0)
            else:
                # Calculate competition type experience
                prior_gc = len(prior_results[prior_results['competition_type'] == 'gc'])
                prior_stage = len(prior_results[prior_results['competition_type'] == 'stage'])
                prior_one_day = len(prior_results[prior_results['competition_type'] == 'one_day'])
                
                experience_features['prior_gc_races'].append(prior_gc)
                experience_features['prior_stage_races'].append(prior_stage)
                experience_features['prior_one_day_races'].append(prior_one_day)
                
                # Calculate race category experience
                prior_wt = len(prior_results[prior_results['race_category'] == 'wt'])
                prior_pro = len(prior_results[prior_results['race_category'] == 'pro'])
                prior_d1 = len(prior_results[prior_results['race_category'] == 'd1'])
                
                experience_features['prior_wt_races'].append(prior_wt)
                experience_features['prior_pro_races'].append(prior_pro)
                experience_features['prior_d1_races'].append(prior_d1)
                
                # Calculate WT proportion
                wt_proportion = prior_wt / total_prior if total_prior > 0 else 0.0
                experience_features['prior_wt_proportion'].append(wt_proportion)
                
                # Calculate total UCI points earned
                total_uci_actual = prior_results['uci_points_actual'].sum()
                total_uci_proportional = prior_results['uci_points_proportional'].sum()
                
                experience_features['total_prior_uci_points_actual'].append(total_uci_actual)
                experience_features['total_prior_uci_points_proportional'].append(total_uci_proportional)
            
            # Age at race time (copy from existing rider_age column)
            current_age = rider_df.iloc[i]['rider_age']
            experience_features['rider_age_at_race'].append(current_age)
        
        return pd.DataFrame(experience_features)
    
    def _get_experience_column_names(self) -> List[str]:
        """Get the list of experience feature column names."""
        return [
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
    
    def get_feature_info(self) -> Dict:
        """Get information about the experience features."""
        return {
            'experience_features': self._get_experience_column_names(),
            'feature_descriptions': {
                'total_prior_races': 'Total number of races completed before this race',
                'prior_gc_races': 'Number of GC races completed before this race',
                'prior_stage_races': 'Number of stage races completed before this race',
                'prior_one_day_races': 'Number of one-day races completed before this race',
                'prior_wt_races': 'Number of WT races completed before this race',
                'prior_pro_races': 'Number of Pro races completed before this race',
                'prior_d1_races': 'Number of D1 races completed before this race',
                'prior_wt_proportion': 'Proportion of prior races that were WT level',
                'total_prior_uci_points_actual': 'Total actual UCI points earned before this race',
                'total_prior_uci_points_proportional': 'Total proportional UCI points earned before this race',
                'rider_age_at_race': 'Rider age at time of this race (same as rider_age)'
            }
        }


def create_training_dataset(rider_history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convenience function to create a complete training dataset with experience features.
    
    This function takes the output from RiderHistory and adds all experience features
    to create a dataset ready for machine learning.
    
    Args:
        rider_history_df: DataFrame from RiderHistory.get_rider_history() or 
                         RiderHistory.get_all_rider_histories()
        
    Returns:
        DataFrame ready for machine learning with all original features plus
        experience features
    """
    experience_calculator = RiderExperienceFeatures()
    return experience_calculator.add_experience_features(rider_history_df)


if __name__ == "__main__":
    # Test the module
    from rider_history import RiderHistory
    
    db_path = "database/database/cycling_races.db"
    history = RiderHistory(db_path)
    
    # Test with a single rider
    test_rider_id = 1000
    test_date = "2023-12-31"
    
    print(f"Testing experience features for rider {test_rider_id}")
    
    # Get rider history
    rider_df = history.get_rider_history(test_rider_id, test_date)
    print(f"Original data: {len(rider_df)} results")
    
    if not rider_df.empty:
        print(f"Original columns: {len(rider_df.columns)}")
        print(f"Key columns present: {set(['rider_id', 'competition_date', 'competition_type', 'race_category', 'rider_age', 'uci_points_actual', 'uci_points_proportional', 'result_id']).issubset(set(rider_df.columns))}")
        
        # Add experience features
        experience_calc = RiderExperienceFeatures()
        enhanced_df = experience_calc.add_experience_features(rider_df)
        
        print(f"Enhanced data: {len(enhanced_df)} results")
        print(f"Enhanced columns: {len(enhanced_df.columns)}")
        print(f"New columns added: {len(enhanced_df.columns) - len(rider_df.columns)}")
        
        # Show feature info
        feature_info = experience_calc.get_feature_info()
        print(f"Experience features: {feature_info['experience_features']}")
        
        # Show sample of experience progression
        sample_cols = ['competition_date', 'competition_name', 'total_prior_races', 
                      'prior_wt_races', 'prior_wt_proportion', 'total_prior_uci_points_actual']
        print("\nSample of experience progression:")
        print(enhanced_df[sample_cols].head(10))
        
        # Test with the convenience function
        print("\nTesting convenience function:")
        training_df = create_training_dataset(rider_df)
        print(f"Training dataset: {len(training_df)} results, {len(training_df.columns)} columns")
    
    # Test with multiple riders (small sample)
    print(f"\nTesting with multiple riders (min 20 results)")
    multi_rider_df = history.get_all_rider_histories(test_date, min_results=20)
    print(f"Multi-rider data: {len(multi_rider_df)} results from {multi_rider_df['rider_id'].nunique()} riders")
    
    if not multi_rider_df.empty:
        # Take a small sample for testing
        sample_riders = multi_rider_df['rider_id'].unique()[:5]  # Smaller sample for testing
        sample_df = multi_rider_df[multi_rider_df['rider_id'].isin(sample_riders)]
        
        print(f"Sample data: {len(sample_df)} results from {len(sample_riders)} riders")
        
        enhanced_sample = create_training_dataset(sample_df)
        print(f"Enhanced sample: {len(enhanced_sample)} results")
        
        # Show experience distribution
        print("\nExperience distribution:")
        print(enhanced_sample['total_prior_races'].describe())
        print(f"WT proportion range: {enhanced_sample['prior_wt_proportion'].min():.3f} to {enhanced_sample['prior_wt_proportion'].max():.3f}")
        
        # Show sample of final columns
        print(f"\nFinal dataset columns ({len(enhanced_sample.columns)} total):")
        experience_cols = [col for col in enhanced_sample.columns if col.startswith(('total_prior', 'prior_'))]
        print(f"Experience columns: {experience_cols}")