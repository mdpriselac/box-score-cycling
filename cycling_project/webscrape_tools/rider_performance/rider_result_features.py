"""
Module for collecting all features for a single rider result including both types of UCI points.
Automatically reads the latest configuration to determine which features to use for each competition type.
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.uci_points import get_actual_uci_place_points, get_top_tier_based_points


class RiderResultFeatures:
    """Collects all features for a single rider result including race features, 
    race kind features, and both types of UCI points."""
    
    def __init__(self, db_path: str):
        """
        Initialize the feature collector.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.config = self._load_latest_config()
        
        # Extract feature columns for each competition type from config
        model_configs = self.config['metadata']['model_configurations']
        self.gc_features = model_configs['gc']['feature_columns']
        self.stage_features = model_configs['stage']['feature_columns']  
        self.one_day_features = model_configs['one_day']['feature_columns']
        
        # Race kind feature columns from schema (exclude competition_id)
        self.race_kind_columns = [
            col['name'] for col in self.config['schema']['columns'] 
            if col['name'] != 'competition_id'
        ]
    
    def _load_latest_config(self) -> Dict:
        """Load the latest configuration JSON file."""
        config_dir = Path("database/race_kinds/race_kind_feature_guide")
        
        if not config_dir.exists():
            raise FileNotFoundError(f"Configuration directory not found: {config_dir}")
            
        config_files = list(config_dir.glob("config_*.json"))
        if not config_files:
            raise FileNotFoundError("No configuration files found in race_kind_feature_guide/")
            
        # Get the latest config file by creation time
        latest_config = max(config_files, key=os.path.getctime)
        
        with open(latest_config) as f:
            return json.load(f)
    
    def get_features_for_result(self, result_id: int) -> Optional[Dict]:
        """
        Get all features for a single rider result.
        
        Args:
            result_id: The ID from the rider_results table
            
        Returns:
            Dictionary containing all features and metadata, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        try:
            # First get the basic result info
            result_query = """
            SELECT 
                rr.*,
                c.name as competition_name,
                c.competition_type,
                c.date as competition_date,
                r.name as race_name,
                r.category as race_category,
                r.year as race_year,
                r.fc_race_id,
                rid.name as rider_name
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            JOIN riders rid ON rr.rider_id = rid.id
            WHERE rr.id = ?
            """
            
            cursor = conn.cursor()
            cursor.execute(result_query, (result_id,))
            result_row = cursor.fetchone()
            
            if not result_row:
                return None
                
            # Convert to dict
            result_data = dict(result_row)
            
            # Get the appropriate feature columns for this competition type
            competition_type = result_data['competition_type']
            if competition_type == 'gc':
                race_features_table = self.config['metadata']['model_configurations']['gc']['source_table']
                feature_columns = self.gc_features
            elif competition_type == 'stage':
                race_features_table = self.config['metadata']['model_configurations']['stage']['source_table']
                feature_columns = self.stage_features
            elif competition_type == 'one_day':
                race_features_table = self.config['metadata']['model_configurations']['one_day']['source_table']
                feature_columns = self.one_day_features
            else:
                raise ValueError(f"Unknown competition type: {competition_type}")
            
            # Get race features (only the relevant ones)
            race_features = self._get_race_features(
                conn, 
                result_data['competition_id'], 
                race_features_table,
                feature_columns
            )
            
            # Get race kind features
            race_kind_features = self._get_race_kind_features(
                conn,
                result_data['competition_id']
            )
            
            # Calculate both types of UCI points
            uci_points = self._calculate_uci_points(
                place=result_data['place'],
                race_type=result_data['competition_type'],
                race_level=result_data['race_category'],
                fc_race_id=result_data['fc_race_id']
            )
            
            # Combine all features
            features = {
                # Basic info
                'result_id': result_id,
                'rider_id': result_data['rider_id'],
                'rider_name': result_data['rider_name'],
                'competition_id': result_data['competition_id'],
                'competition_name': result_data['competition_name'],
                'competition_type': result_data['competition_type'],
                'race_name': result_data['race_name'],
                'race_category': result_data['race_category'],
                'race_year': result_data['race_year'],
                'competition_date': result_data['competition_date'],
                
                # Result info
                'place': result_data['place'],
                'time_gap': result_data['time_gap'],
                'percentile': result_data['percentile'],
                'rider_age': result_data['rider_age'],
                
                # UCI points
                'uci_points_actual': uci_points['actual'],
                'uci_points_proportional': uci_points['proportional'],
                
                # Feature source info
                'race_features_source': race_features_table,
                'feature_columns_used': feature_columns
            }
            
            # Add race features (only the relevant ones)
            if race_features:
                for col in feature_columns:
                    features[f'rf_{col}'] = race_features.get(col)
            else:
                # Fill with None if no race features found
                for col in feature_columns:
                    features[f'rf_{col}'] = None
                    
            # Add race kind features
            if race_kind_features:
                for col in self.race_kind_columns:
                    features[f'rkf_{col}'] = race_kind_features.get(col)
            else:
                # Fill with None if no race kind features found
                for col in self.race_kind_columns:
                    features[f'rkf_{col}'] = None
            
            return features
            
        finally:
            conn.close()
    
    def _get_race_features(self, conn: sqlite3.Connection, competition_id: int, 
                          table_name: str, feature_columns: List[str]) -> Optional[Dict]:
        """Get race features from the appropriate percentile table."""
        if not feature_columns:
            return None
            
        # Quote column names to handle names with numbers/special characters
        quoted_columns = [f'"{col}"' for col in feature_columns]
        
        query = f"""
        SELECT {', '.join(quoted_columns)}
        FROM {table_name}
        WHERE competition_id = ?
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (competition_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(zip(feature_columns, row))
        return None
    
    def _get_race_kind_features(self, conn: sqlite3.Connection, 
                                competition_id: int) -> Optional[Dict]:
        """Get race kind features from the unified table."""
        if not self.race_kind_columns:
            return None
            
        # Use the table name from the config
        table_name = self.config['metadata']['table_name']
        
        # First check which columns actually exist in the table
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Filter to only request columns that exist
        columns_to_query = [col for col in self.race_kind_columns 
                           if col in existing_columns]
        
        if not columns_to_query:
            return None
            
        # Quote column names to handle names with numbers/special characters
        quoted_columns = [f'"{col}"' for col in columns_to_query]
        
        query = f"""
        SELECT {', '.join(quoted_columns)}
        FROM {table_name}
        WHERE competition_id = ?
        """
        
        cursor.execute(query, (competition_id,))
        row = cursor.fetchone()
        
        if row:
            return dict(zip(columns_to_query, row))
        return None
    
    def _calculate_uci_points(self, place: int, race_type: str, 
                             race_level: str, fc_race_id: int) -> Dict[str, int]:
        """Calculate both types of UCI points."""
        try:
            actual_points = get_actual_uci_place_points(place, race_type, race_level, fc_race_id)
        except (ValueError, KeyError) as e:
            print(f"Warning: Could not calculate actual UCI points for race_id {fc_race_id}: {e}")
            actual_points = 0
            
        try:
            proportional_points = get_top_tier_based_points(place, race_type, race_level, fc_race_id)
        except (ValueError, KeyError) as e:
            print(f"Warning: Could not calculate proportional UCI points for race_id {fc_race_id}: {e}")
            proportional_points = 0
            
        return {
            'actual': actual_points,
            'proportional': proportional_points
        }
    
    def get_feature_info(self) -> Dict:
        """Get information about the features being used."""
        return {
            'gc_features': self.gc_features,
            'stage_features': self.stage_features,
            'one_day_features': self.one_day_features,
            'race_kind_features': self.race_kind_columns,
            'config_source': self.config['metadata']['export_timestamp'],
            'race_kind_table': self.config['metadata']['table_name']
        }


if __name__ == "__main__":
    # Test the module
    db_path = "database/database/cycling_races.db"
    
    try:
        collector = RiderResultFeatures(db_path)
        
        # Show feature info
        feature_info = collector.get_feature_info()
        print("Feature configuration:")
        print(f"GC features ({len(feature_info['gc_features'])}): {feature_info['gc_features']}")
        print(f"Stage features ({len(feature_info['stage_features'])}): {feature_info['stage_features']}")
        print(f"One-day features ({len(feature_info['one_day_features'])}): {feature_info['one_day_features']}")
        print(f"Race kind features ({len(feature_info['race_kind_features'])}): {feature_info['race_kind_features']}")
        print(f"Config from: {feature_info['config_source']}")
        print(f"Race kind table: {feature_info['race_kind_table']}")
        
        # Test with a sample result ID
        test_result_id = 1000
        features = collector.get_features_for_result(test_result_id)
        
        if features:
            print(f"\nFeatures for result {test_result_id}:")
            print(f"Rider: {features['rider_name']}")
            print(f"Competition: {features['competition_name']} ({features['competition_type']})")
            print(f"Place: {features['place']}")
            print(f"UCI Points - Actual: {features['uci_points_actual']}, Proportional: {features['uci_points_proportional']}")
            print(f"Race features from: {features['race_features_source']}")
            print(f"Features used: {len(features['feature_columns_used'])}")
            print(f"Race features available: {sum(1 for k in features if k.startswith('rf_') and features[k] is not None)}")
            print(f"Race kind features available: {sum(1 for k in features if k.startswith('rkf_') and features[k] is not None)}")
        else:
            print(f"No result found with ID {test_result_id}")
            
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the configuration files exist in database/race_kinds/race_kind_feature_guide/")