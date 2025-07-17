"""
Percentile threshold calculation system for rider correlation processing.
Calculates race count thresholds based on percentiles to ensure we're working
with experienced riders only.
"""
import sqlite3
import logging
from typing import Dict
from config import ProcessingConfig

class ThresholdCalculator:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
        
    def calculate_thresholds(self) -> Dict[str, int]:
        """Calculate actual race count thresholds from percentiles"""
        logging.info("Calculating percentile-based thresholds...")
        
        with sqlite3.connect(self.db_path) as conn:
            # First, ensure we have the combined stage_one_days column
            self._ensure_stage_one_days_column(conn)
            
            # Calculate thresholds for each column
            for column, percentile in self.config.MIN_RACE_PERCENTILES.items():
                threshold = self._calculate_column_threshold(conn, column, percentile)
                self.config.MIN_RACES[column] = threshold
                
                # Store in database for reference
                self._store_threshold(conn, column, percentile, threshold)
            
            conn.commit()
        
        logging.info(f"Calculated thresholds: {self.config.MIN_RACES}")
        return self.config.MIN_RACES
    
    def _ensure_stage_one_days_column(self, conn: sqlite3.Connection):
        """Ensure the prior_stage_one_days column exists and is populated"""
        try:
            conn.execute("""
                ALTER TABLE rider_results 
                ADD COLUMN prior_stage_one_days INTEGER DEFAULT 0
            """)
            
            # Update if column was just added
            conn.execute("""
                UPDATE rider_results
                SET prior_stage_one_days = prior_stage_races + prior_one_day_races
            """)
            conn.commit()
            logging.info("Added and populated prior_stage_one_days column")
        except sqlite3.OperationalError:
            # Column already exists, but make sure it's populated
            result = conn.execute("""
                SELECT COUNT(*) FROM rider_results 
                WHERE prior_stage_one_days = 0 
                AND (prior_stage_races > 0 OR prior_one_day_races > 0)
            """).fetchone()
            
            if result[0] > 0:
                conn.execute("""
                    UPDATE rider_results
                    SET prior_stage_one_days = prior_stage_races + prior_one_day_races
                    WHERE prior_stage_one_days = 0
                """)
                conn.commit()
                logging.info("Updated existing prior_stage_one_days column")
    
    def _calculate_column_threshold(self, conn: sqlite3.Connection, 
                                  column: str, percentile: float) -> int:
        """Calculate the threshold value for a specific column and percentile"""
        # Get the value at the percentile (e.g., for 10th percentile cutoff)
        # First get the total count and calculate offset
        total_count = conn.execute(f"""
            SELECT COUNT(*) FROM rider_results WHERE {column} > 0
        """).fetchone()[0]
        
        if total_count == 0:
            return 5  # Default
        
        offset = int(total_count * (100 - percentile) / 100)
        
        query = f"""
            SELECT {column}
            FROM rider_results
            WHERE {column} > 0
            ORDER BY {column}
            LIMIT 1
            OFFSET ?
        """
        
        result = conn.execute(query, [offset]).fetchone()
        threshold = result[0] if result else 5  # Default to 5 if no data
        
        return threshold
    
    def _store_threshold(self, conn: sqlite3.Connection, column: str, 
                        percentile: float, threshold: int):
        """Store the calculated threshold in the database"""
        conn.execute("""
            INSERT OR REPLACE INTO race_history_thresholds
            (threshold_name, percentile, min_races, total_riders)
            VALUES (?, ?, ?, (SELECT COUNT(DISTINCT rider_id) FROM rider_results))
        """, (column, percentile, threshold))
    
    def get_thresholds_summary(self) -> Dict:
        """Get a summary of calculated thresholds with distribution info"""
        summary = {}
        
        with sqlite3.connect(self.db_path) as conn:
            # Get stored thresholds
            thresholds = conn.execute("""
                SELECT threshold_name, percentile, min_races, total_riders
                FROM race_history_thresholds
                ORDER BY threshold_name
            """).fetchall()
            
            for threshold_name, percentile, min_races, total_riders in thresholds:
                # Get distribution info for this threshold
                stats = conn.execute(f"""
                    SELECT 
                        COUNT(*) as total_eligible,
                        AVG({threshold_name}) as avg_races,
                        MAX({threshold_name}) as max_races
                    FROM rider_results
                    WHERE {threshold_name} >= ?
                """, [min_races]).fetchone()
                
                summary[threshold_name] = {
                    'percentile': percentile,
                    'min_races': min_races,
                    'total_riders': total_riders,
                    'eligible_results': stats[0],
                    'avg_races_eligible': stats[1],
                    'max_races': stats[2]
                }
        
        return summary
    
    def validate_thresholds(self) -> bool:
        """Validate that thresholds are reasonable"""
        with sqlite3.connect(self.db_path) as conn:
            for column, threshold in self.config.MIN_RACES.items():
                # Check that we have sufficient data
                count = conn.execute(f"""
                    SELECT COUNT(DISTINCT rider_id)
                    FROM rider_results
                    WHERE {column} >= ?
                """, [threshold]).fetchone()[0]
                
                if count < 100:  # Arbitrary minimum  
                    logging.warning(f"Low rider count ({count}) for {column} >= {threshold}")
                    return False
                    
                logging.info(f"{column}: {count} riders with >= {threshold} races")
        
        return True