"""
Race features pre-loading system for correlation processing.
Efficiently loads all race features into memory for fast access during processing.
"""
import numpy as np
import pandas as pd
import sqlite3
import logging
from typing import Dict, List
from config import ProcessingConfig

class RaceFeaturesLoader:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
        self.race_features_cache: Dict[int, np.ndarray] = {}
        self.percentile_availability: Dict[int, List[int]] = {}
        
    def preload_race_features(self) -> Dict[int, np.ndarray]:
        """Pre-load all race features into memory"""
        logging.info("Pre-loading race features...")
        
        # Load each percentile table separately to track availability
        all_competitions = set()
        percentile_data = {}
        
        for percentile in self.config.PERCENTILES:
            query = f"""
                SELECT competition_id, {', '.join(self.config.RACE_FEATURES)}
                FROM race_features_{percentile}
            """
            
            with sqlite3.connect(self.db_path) as conn:
                # Use M1-optimized settings
                conn.execute("PRAGMA cache_size = -2000000")  # 2GB cache
                conn.execute("PRAGMA temp_store = MEMORY")
                conn.execute("PRAGMA mmap_size = 2147483648")  # 2GB mmap
                
                df = pd.read_sql_query(query, conn)
                percentile_data[percentile] = df
                all_competitions.update(df['competition_id'].unique())
        
        # Track which percentiles are available for each competition
        self.percentile_availability = {}
        
        # Build feature matrices for all competitions
        for comp_id in all_competitions:
            feature_matrix = np.full((len(self.config.PERCENTILES), self.config.NUM_FEATURES), np.nan)
            availability = []
            
            for idx, percentile in enumerate(self.config.PERCENTILES):
                comp_data = percentile_data[percentile]
                percentile_comp_data = comp_data[comp_data['competition_id'] == comp_id]
                
                if len(percentile_comp_data) > 0:
                    # Extract features based on the feature list
                    feature_values = []
                    for feature in self.config.RACE_FEATURES:
                        if feature in percentile_comp_data.columns:
                            feature_values.append(percentile_comp_data[feature].iloc[0])
                        else:
                            feature_values.append(0.0)  # Default for missing features
                    
                    feature_matrix[idx, :len(feature_values)] = feature_values[:self.config.NUM_FEATURES]
                    availability.append(1)
                else:
                    availability.append(0)
            
            self.race_features_cache[comp_id] = feature_matrix
            self.percentile_availability[comp_id] = availability
        
        logging.info(f"Loaded {len(self.race_features_cache)} competition features")
        return self.race_features_cache
    
    def get_race_features(self, competition_id: int) -> np.ndarray:
        """Get race features for a specific competition"""
        return self.race_features_cache.get(competition_id)
    
    def get_percentile_availability(self, competition_id: int) -> List[int]:
        """Get percentile availability for a specific competition"""
        return self.percentile_availability.get(competition_id, [])
    
    def validate_features_cache(self) -> bool:
        """Validate that the features cache has expected structure"""
        if not self.race_features_cache:
            logging.error("Race features cache is empty")
            return False
        
        # Check a few random competitions
        sample_ids = list(self.race_features_cache.keys())[:5]
        for comp_id in sample_ids:
            matrix = self.race_features_cache[comp_id]
            expected_shape = (len(self.config.PERCENTILES), self.config.NUM_FEATURES)
            if matrix.shape != expected_shape:
                logging.error(f"Competition {comp_id} has shape {matrix.shape}, expected {expected_shape}")
                return False
            
            # Check for reasonable values (not all zeros or NaN)
            if np.all(matrix == 0) or np.any(np.isnan(matrix)):
                logging.warning(f"Competition {comp_id} has suspicious values")
        
        logging.info(f"Features cache validation passed for {len(self.race_features_cache)} competitions")
        return True
    
    def get_cache_stats(self) -> Dict:
        """Get statistics about the loaded cache"""
        if not self.race_features_cache:
            return {"status": "empty"}
        
        total_comps = len(self.race_features_cache)
        sample_matrix = next(iter(self.race_features_cache.values()))
        matrix_size = sample_matrix.nbytes
        total_memory_mb = (total_comps * matrix_size) / (1024 * 1024)
        
        return {
            "competitions_loaded": total_comps,
            "matrix_shape": sample_matrix.shape,
            "estimated_memory_mb": total_memory_mb,
            "features_per_competition": sample_matrix.size
        }
    
    def clear_cache(self):
        """Clear the features cache to free memory"""
        self.race_features_cache.clear()
        logging.info("Race features cache cleared")
    
    def optimize_cache(self, max_competitions: int = 5000):
        """Optimize cache size if it grows too large"""
        if len(self.race_features_cache) > max_competitions:
            # Keep most recent competitions (highest IDs)
            sorted_comps = sorted(self.race_features_cache.keys(), reverse=True)
            keep_comps = sorted_comps[:max_competitions]
            
            new_cache = {comp_id: self.race_features_cache[comp_id] for comp_id in keep_comps}
            
            removed = len(self.race_features_cache) - len(new_cache)
            self.race_features_cache = new_cache
            
            logging.info(f"Optimized cache: removed {removed} old competitions, kept {len(new_cache)}")
        
        return self.race_features_cache