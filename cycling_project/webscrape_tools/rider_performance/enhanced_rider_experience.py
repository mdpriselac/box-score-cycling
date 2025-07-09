"""
Enhanced rider experience features for improved global model performance.

This module extends the basic experience features with:
1. Points-based experience (quality of performance at each level)
2. Rider-race interaction features (performance profiles against race characteristics)

The goal is to provide much richer rider representations that enable a global model
to better understand rider quality and predict performance.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import warnings

# Suppress numpy warnings about empty slices and divide by zero
warnings.filterwarnings('ignore', category=RuntimeWarning, message='Mean of empty slice')
warnings.filterwarnings('ignore', category=RuntimeWarning, message='invalid value encountered')


class EnhancedRiderExperience:
    """
    Advanced rider experience feature calculator.
    
    Provides sophisticated rider representations including:
    - Performance-based experience metrics (not just counts)
    - Rider-race interaction profiles
    - Historical success patterns
    """
    
    def __init__(self, race_feature_columns: Optional[List[str]] = None,
                 race_kind_feature_columns: Optional[List[str]] = None):
        """
        Initialize enhanced experience calculator.
        
        Args:
            race_feature_columns: List of race feature column names (rf_*)
            race_kind_feature_columns: List of race kind feature column names (rkf_*)
        """
        self.race_feature_columns = race_feature_columns or []
        self.race_kind_feature_columns = race_kind_feature_columns or []
        
        # Load configuration if not provided
        if not self.race_feature_columns or not self.race_kind_feature_columns:
            self._load_feature_configuration()
        
        # Use ALL available race features for interaction analysis (no hardcoding)
        self.key_race_features = self.race_feature_columns if self.race_feature_columns else []
        
        # Use ALL available race kind features for interaction analysis (no hardcoding)
        self.key_race_kind_features = self.race_kind_feature_columns if self.race_kind_feature_columns else []
    
    def _load_feature_configuration(self):
        """Load feature configuration from the latest config file."""
        import json
        import os
        from pathlib import Path
        
        config_dir = Path("database/race_kinds/race_kind_feature_guide")
        
        if not config_dir.exists():
            print(f"Warning: Configuration directory not found: {config_dir}")
            return
            
        config_files = list(config_dir.glob("config_*.json"))
        if not config_files:
            print(f"Warning: No configuration files found in {config_dir}")
            return
            
        # Get the latest configuration file
        latest_config_file = max(config_files, key=os.path.getctime)
        
        try:
            with open(latest_config_file) as f:
                config = json.load(f)
            
            # Extract feature columns for race features (combine all competition types)
            model_configs = config['metadata']['model_configurations']
            all_race_features = set()
            
            for comp_type in ['gc', 'stage', 'one_day']:
                if comp_type in model_configs:
                    all_race_features.update(model_configs[comp_type]['feature_columns'])
            
            self.race_feature_columns = list(all_race_features)
            
            # Extract race kind feature columns from schema (exclude competition_id)
            self.race_kind_feature_columns = [
                col['name'] for col in config['schema']['columns'] 
                if col['name'] != 'competition_id'
            ]
            
        except Exception as e:
            print(f"Warning: Could not load configuration from {latest_config_file}: {e}")
    
    def add_experience_features(self, rider_history_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add comprehensive experience features to rider history data.
        
        Args:
            rider_history_df: DataFrame with rider history including race features
            
        Returns:
            DataFrame with enhanced experience features added
        """
        if rider_history_df.empty:
            return rider_history_df
        
        # Verify required columns
        required_columns = [
            'rider_id', 'competition_date', 'competition_type', 'race_category',
            'uci_points_actual', 'uci_points_proportional', 'result_id'
        ]
        
        missing_columns = [col for col in required_columns if col not in rider_history_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Auto-detect race feature columns if not provided
        if not self.race_feature_columns:
            self.race_feature_columns = [col for col in rider_history_df.columns if col.startswith('rf_')]
        
        if not self.race_kind_feature_columns:
            self.race_kind_feature_columns = [col for col in rider_history_df.columns if col.startswith('rkf_')]
        
        print(f"Processing enhanced experience features for {rider_history_df['rider_id'].nunique()} riders...")
        
        # Process each rider
        df = rider_history_df.copy().sort_values(['rider_id', 'competition_date'])
        enhanced_features = []
        
        for rider_id in df['rider_id'].unique():
            rider_df = df[df['rider_id'] == rider_id].copy()
            rider_enhanced = self._calculate_enhanced_rider_experience(rider_df)
            enhanced_features.append(rider_enhanced)
        
        # Combine results
        enhanced_df = pd.concat(enhanced_features, ignore_index=True)
        
        # Merge with original data, preserving basic rider info
        enhanced_cols = ['result_id'] + self._get_enhanced_feature_names()
        final_df = df.merge(
            enhanced_df[enhanced_cols],
            on='result_id',
            how='left'
        )
        
        return final_df
    
    def _calculate_enhanced_rider_experience(self, rider_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate enhanced experience features for a single rider."""
        rider_df = rider_df.sort_values('competition_date')
        
        # Initialize enhanced feature structure
        enhanced_features = {
            'result_id': rider_df['result_id'].values,
        }
        
        # Add all enhanced feature columns - initialize all as empty lists
        all_feature_names = self._get_enhanced_feature_names()
        for feature_name in all_feature_names:
            if feature_name != 'result_id':
                enhanced_features[feature_name] = []
        
        # Calculate features for each race
        for i in range(len(rider_df)):
            prior_results = rider_df.iloc[:i]
            current_race = rider_df.iloc[i]
            
            if len(prior_results) == 0:
                # First race - no prior experience
                self._add_zero_experience_features(enhanced_features, current_race)
            else:
                # Calculate enhanced features
                self._calculate_points_based_features(enhanced_features, prior_results)
                self._calculate_performance_quality_features(enhanced_features, prior_results, current_race)
                self._calculate_race_interaction_features(enhanced_features, prior_results, current_race)
        
        # Verify all arrays have the same length before creating DataFrame
        result_length = len(rider_df)
        mismatched_features = []
        for feature_name in all_feature_names:
            if feature_name != 'result_id':
                if len(enhanced_features[feature_name]) != result_length:
                    mismatched_features.append(f"'{feature_name}' has length {len(enhanced_features[feature_name])}")
                    # Pad with zeros if needed
                    while len(enhanced_features[feature_name]) < result_length:
                        enhanced_features[feature_name].append(0)
        
        if mismatched_features:
            print(f"Warning: {len(mismatched_features)} features had incorrect lengths (expected {result_length})")
            print(f"First 10 mismatched features: {mismatched_features[:10]}")
        
        return pd.DataFrame(enhanced_features)
    
    def _calculate_points_based_features(self, features: Dict, prior_results: pd.DataFrame):
        """Calculate points-based experience features instead of just counts."""
        
        # Points earned by competition type
        for comp_type in ['gc', 'stage', 'one_day']:
            type_results = prior_results[prior_results['competition_type'] == comp_type]
            
            # Ensure feature keys exist
            comp_features = [
                f'prior_{comp_type}_points_actual',
                f'prior_{comp_type}_points_proportional',
                f'prior_{comp_type}_success_rate',
                f'prior_{comp_type}_races'
            ]
            for feature in comp_features:
                if feature not in features:
                    features[feature] = []
            
            if len(type_results) > 0:
                features[f'prior_{comp_type}_points_actual'].append(type_results['uci_points_actual'].sum())
                features[f'prior_{comp_type}_points_proportional'].append(type_results['uci_points_proportional'].sum())
                # Calculate success rate with proper handling for empty results
                successes = (type_results['uci_points_actual'] > 0)
                if len(successes) > 0:
                    success_rate = successes.mean()
                else:
                    success_rate = 0.0
                features[f'prior_{comp_type}_success_rate'].append(success_rate)
                features[f'prior_{comp_type}_races'].append(len(type_results))
            else:
                features[f'prior_{comp_type}_points_actual'].append(0)
                features[f'prior_{comp_type}_points_proportional'].append(0)
                features[f'prior_{comp_type}_success_rate'].append(0)
                features[f'prior_{comp_type}_races'].append(0)
        
        # Points earned by race category
        for category in ['wt', 'pro', 'd1']:
            cat_results = prior_results[prior_results['race_category'] == category]
            
            # Ensure feature keys exist
            cat_features = [
                f'prior_{category}_points_actual',
                f'prior_{category}_points_proportional',
                f'prior_{category}_success_rate',
                f'prior_{category}_races'
            ]
            for feature in cat_features:
                if feature not in features:
                    features[feature] = []
            
            if len(cat_results) > 0:
                features[f'prior_{category}_points_actual'].append(cat_results['uci_points_actual'].sum())
                features[f'prior_{category}_points_proportional'].append(cat_results['uci_points_proportional'].sum())
                # Calculate success rate with proper handling for empty results
                successes = (cat_results['uci_points_actual'] > 0)
                if len(successes) > 0:
                    success_rate = successes.mean()
                else:
                    success_rate = 0.0
                features[f'prior_{category}_success_rate'].append(success_rate)
                features[f'prior_{category}_races'].append(len(cat_results))
            else:
                features[f'prior_{category}_points_actual'].append(0)
                features[f'prior_{category}_points_proportional'].append(0)
                features[f'prior_{category}_success_rate'].append(0)
                features[f'prior_{category}_races'].append(0)
    
    def _calculate_performance_quality_features(self, features: Dict, prior_results: pd.DataFrame, current_race: pd.Series):
        """Calculate overall performance quality metrics."""
        total_races = len(prior_results)
        
        # Ensure feature keys exist
        quality_features = [
            'total_prior_races', 'total_prior_uci_points_actual', 'total_prior_uci_points_proportional',
            'overall_success_rate', 'points_variance', 'rider_age_at_race', 'prior_wt_proportion'
        ]
        for feature in quality_features:
            if feature not in features:
                features[feature] = []
        
        if total_races > 0:
            # Overall performance metrics
            features['total_prior_races'].append(total_races)
            features['total_prior_uci_points_actual'].append(prior_results['uci_points_actual'].sum())
            features['total_prior_uci_points_proportional'].append(prior_results['uci_points_proportional'].sum())
            # Calculate overall success rate with proper handling
            successes = (prior_results['uci_points_actual'] > 0)
            if len(successes) > 0:
                overall_success_rate = successes.mean()
            else:
                overall_success_rate = 0.0
            features['overall_success_rate'].append(overall_success_rate)
            
            # Performance consistency (variance only)
            if total_races > 1:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    point_variance = prior_results['uci_points_actual'].var()
                    if pd.isna(point_variance):
                        point_variance = 0
            else:
                point_variance = 0
            features['points_variance'].append(point_variance)
            
            # Add rider age from current race
            features['rider_age_at_race'].append(current_race.get('rider_age', 0))
            
            # Calculate WT proportion (for compatibility with basic features)
            wt_races = len(prior_results[prior_results['race_category'] == 'wt'])
            wt_proportion = wt_races / total_races if total_races > 0 else 0.0
            features['prior_wt_proportion'].append(wt_proportion)
        else:
            # Zero values for first race
            for feature in quality_features:
                if feature == 'rider_age_at_race':
                    features[feature].append(current_race.get('rider_age', 0))
                else:
                    features[feature].append(0)
    
    def _calculate_race_interaction_features(self, features: Dict, prior_results: pd.DataFrame, current_race: pd.Series):
        """Calculate rider-race interaction features."""
        
        # Ensure all race interaction feature keys exist
        for feature_name in self.key_race_features:
            performance_key = f'rider_vs_{feature_name}_performance'
            success_key = f'rider_vs_{feature_name}_success_rate'
            if performance_key not in features:
                features[performance_key] = []
            if success_key not in features:
                features[success_key] = []
        
        for feature_name in self.key_race_kind_features:
            performance_key = f'rider_vs_{feature_name}_performance'
            if performance_key not in features:
                features[performance_key] = []
            # Only cluster_label gets affinity metric
            if feature_name == 'cluster_label':
                affinity_key = f'rider_vs_{feature_name}_affinity'
                if affinity_key not in features:
                    features[affinity_key] = []
        
        if len(prior_results) == 0:
            # No prior experience - append zeros for all features
            for feature_name in self.key_race_features:
                features[f'rider_vs_{feature_name}_performance'].append(0)
                features[f'rider_vs_{feature_name}_success_rate'].append(0)
            
            for feature_name in self.key_race_kind_features:
                features[f'rider_vs_{feature_name}_performance'].append(0)
                # Only cluster_label gets affinity metric
                if feature_name == 'cluster_label':
                    features[f'rider_vs_{feature_name}_affinity'].append(0)
            return
        
        # Analyze performance against race features - ensure we append exactly one value per feature
        for feature_name in self.key_race_features:
            rf_col = f'rf_{feature_name}'
            if rf_col in prior_results.columns:
                self._calculate_feature_interaction(features, prior_results, rf_col, feature_name, current_race)
            else:
                # Feature not available - append zeros
                features[f'rider_vs_{feature_name}_performance'].append(0)
                features[f'rider_vs_{feature_name}_success_rate'].append(0)
        
        # Analyze performance against race kind features - ensure we append exactly one value per feature
        for feature_name in self.key_race_kind_features:
            rkf_col = f'rkf_{feature_name}'
            if rkf_col in prior_results.columns:
                self._calculate_race_kind_interaction(features, prior_results, rkf_col, feature_name, current_race)
            else:
                # Feature not available - append zeros
                features[f'rider_vs_{feature_name}_performance'].append(0)
                # Only cluster_label gets affinity metric
                if feature_name == 'cluster_label':
                    features[f'rider_vs_{feature_name}_affinity'].append(0)
    
    def _calculate_feature_interaction(self, features: Dict, prior_results: pd.DataFrame, 
                                     feature_col: str, feature_name: str, current_race: pd.Series):
        """Calculate interaction between rider performance and a specific race feature."""
        
        # Calculate correlation between race feature value and rider points earned
        if len(prior_results) >= 3:  # Need minimum samples for meaningful correlation
            # Check if there's variance in both columns to avoid divide by zero warnings
            feature_variance = prior_results[feature_col].var()
            points_variance = prior_results['uci_points_actual'].var()
            
            if feature_variance > 0 and points_variance > 0:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    correlation = prior_results[feature_col].corr(prior_results['uci_points_actual'])
                    if pd.isna(correlation):
                        correlation = 0
            else:
                correlation = 0
        else:
            correlation = 0
        
        # Ensure the feature key exists in the dictionary
        performance_key = f'rider_vs_{feature_name}_performance'
        if performance_key not in features:
            features[performance_key] = []
        features[performance_key].append(correlation)
        
        # Calculate success rate in high vs low feature value races
        if len(prior_results) >= 5:
            median_value = prior_results[feature_col].median()
            high_feature_races = prior_results[prior_results[feature_col] >= median_value]
            
            if len(high_feature_races) > 0:
                successes = (high_feature_races['uci_points_actual'] > 0)
                if len(successes) > 0:
                    high_feature_success = successes.mean()
                else:
                    high_feature_success = 0
            else:
                high_feature_success = 0
        else:
            high_feature_success = 0
        
        # Ensure the feature key exists in the dictionary
        success_key = f'rider_vs_{feature_name}_success_rate'
        if success_key not in features:
            features[success_key] = []
        features[success_key].append(high_feature_success)
    
    def _calculate_race_kind_interaction(self, features: Dict, prior_results: pd.DataFrame,
                                       feature_col: str, feature_name: str, current_race: pd.Series):
        """Calculate interaction with race kind features (often categorical)."""
        
        if feature_name == 'cluster_label':
            # For cluster labels, calculate performance in each cluster
            cluster_performance = {}
            for cluster in prior_results[feature_col].unique():
                cluster_races = prior_results[prior_results[feature_col] == cluster]
                if len(cluster_races) > 0:
                    points = cluster_races['uci_points_actual']
                    if len(points) > 0:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", RuntimeWarning)
                            mean_points = points.mean()
                            if pd.isna(mean_points):
                                mean_points = 0
                        cluster_performance[cluster] = mean_points
                    else:
                        cluster_performance[cluster] = 0
            
            # Find best cluster performance
            if cluster_performance:
                best_performance = max(cluster_performance.values())
                
                # Calculate affinity for current race cluster
                current_cluster = current_race.get(feature_col, -1)
                current_affinity = cluster_performance.get(current_cluster, 0)
            else:
                best_performance = 0
                current_affinity = 0
            
            # Ensure the feature keys exist in the dictionary
            performance_key = f'rider_vs_{feature_name}_performance'
            affinity_key = f'rider_vs_{feature_name}_affinity'
            
            if performance_key not in features:
                features[performance_key] = []
            if affinity_key not in features:
                features[affinity_key] = []
                
            features[performance_key].append(best_performance)
            features[affinity_key].append(current_affinity)
        else:
            # For continuous race kind features - calculate performance correlation
            if len(prior_results) >= 3:
                # Check if there's variance in both columns to avoid divide by zero warnings
                feature_variance = prior_results[feature_col].var()
                points_variance = prior_results['uci_points_actual'].var()
                
                if feature_variance > 0 and points_variance > 0:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", RuntimeWarning)
                        correlation = prior_results[feature_col].corr(prior_results['uci_points_actual'])
                        if pd.isna(correlation):
                            correlation = 0
                else:
                    correlation = 0
            else:
                correlation = 0
            
            # Ensure the feature keys exist in the dictionary
            performance_key = f'rider_vs_{feature_name}_performance'
            
            if performance_key not in features:
                features[performance_key] = []
                
            features[performance_key].append(correlation)
            # No affinity metric for continuous race kind features
    
    def _add_zero_experience_features(self, features: Dict, current_race: pd.Series):
        """Add zero values for all features when no prior experience exists."""
        all_feature_names = self._get_enhanced_feature_names()
        for feature_name in all_feature_names:
            if feature_name != 'result_id':
                # Ensure feature key exists
                if feature_name not in features:
                    features[feature_name] = []
                    
                # Special handling for rider age - get from current race
                if feature_name == 'rider_age_at_race':
                    features[feature_name].append(current_race.get('rider_age', 0))
                else:
                    features[feature_name].append(0)
    
    def _get_enhanced_feature_names(self) -> List[str]:
        """Get comprehensive list of enhanced feature names."""
        feature_names = []
        
        # Points-based features by competition type
        for comp_type in ['gc', 'stage', 'one_day']:
            feature_names.extend([
                f'prior_{comp_type}_points_actual',
                f'prior_{comp_type}_points_proportional',
                f'prior_{comp_type}_success_rate',
                f'prior_{comp_type}_races'
            ])
        
        # Points-based features by race category
        for category in ['wt', 'pro', 'd1']:
            feature_names.extend([
                f'prior_{category}_points_actual',
                f'prior_{category}_points_proportional',
                f'prior_{category}_success_rate',
                f'prior_{category}_races'
            ])
        
        # Overall performance quality features
        feature_names.extend([
            'total_prior_races',
            'total_prior_uci_points_actual',
            'total_prior_uci_points_proportional',
            'overall_success_rate',
            'points_variance',
            'rider_age_at_race',  # Preserve age information
            'prior_wt_proportion'  # For compatibility with basic features
        ])
        
        # Race interaction features
        for feature_name in self.key_race_features:
            feature_names.extend([
                f'rider_vs_{feature_name}_performance',
                f'rider_vs_{feature_name}_success_rate'
            ])
        
        for feature_name in self.key_race_kind_features:
            feature_names.append(f'rider_vs_{feature_name}_performance')
            # Only cluster_label gets affinity metric
            if feature_name == 'cluster_label':
                feature_names.append(f'rider_vs_{feature_name}_affinity')
        
        return feature_names


if __name__ == "__main__":
    # Example usage / testing
    print("Enhanced Rider Experience Features")
    print("This module provides sophisticated rider representations for global models")
    print(f"Enhanced features include {len(EnhancedRiderExperience()._get_enhanced_feature_names())} different metrics")