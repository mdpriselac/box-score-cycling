"""
Checkpoint manager for resume functionality in correlation processing.
Allows the system to be interrupted and resumed at any time.
"""
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict
from config import ProcessingConfig

class CheckpointManager:
    def __init__(self, db_path: str, config: ProcessingConfig):
        self.db_path = db_path
        self.config = config
    
    def save_checkpoint(self, last_competition_id: int):
        """Save current processing state"""
        
        with sqlite3.connect(self.db_path) as conn:
            # Get processing statistics
            stats = conn.execute("""
                SELECT 
                    COUNT(DISTINCT rider_id) as riders_processed,
                    COUNT(DISTINCT competition_id) as competitions_processed,
                    COUNT(*) as correlations_calculated
                FROM rider_correlations_denorm
            """).fetchone()
            
            conn.execute("""
                INSERT OR REPLACE INTO processing_checkpoint
                (checkpoint_name, last_processed_competition_id, 
                 last_processed_date, total_processed, total_remaining)
                VALUES (?, ?, ?, ?, NULL)
            """, (
                self.config.CHECKPOINT_NAME,
                last_competition_id,
                datetime.now().isoformat(),
                stats[2] if stats else 0  # total correlations
            ))
            conn.commit()
        
        logging.info(f"Checkpoint saved at competition {last_competition_id}")
    
    def load_checkpoint(self) -> Optional[Dict]:
        """Load the most recent checkpoint"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT last_processed_competition_id, last_processed_date, total_processed
                FROM processing_checkpoint
                WHERE checkpoint_name = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.config.CHECKPOINT_NAME,)).fetchone()
            
            if result:
                return {
                    'last_competition_id': result[0],
                    'last_processed_date': result[1],
                    'total_processed': result[2]
                }
        
        return None
    
    def finalize(self):
        """Mark processing as complete"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE processing_checkpoint
                SET last_processed_date = ?
                WHERE checkpoint_name = ?
            """, (datetime.now().isoformat(), self.config.CHECKPOINT_NAME))
            conn.commit()
        
        logging.info("Processing marked as complete")
    
    def get_progress_stats(self) -> Dict:
        """Get progress statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Get total competitions to process
            total_comps = conn.execute("""
                SELECT COUNT(DISTINCT id) FROM competitions
            """).fetchone()[0]
            
            # Get processed competitions
            processed = conn.execute("""
                SELECT COUNT(DISTINCT competition_id) FROM rider_correlations_denorm
            """).fetchone()[0]
            
            # Get latest checkpoint
            checkpoint = self.load_checkpoint()
            
            return {
                'total_competitions': total_comps,
                'processed_competitions': processed,
                'remaining_competitions': total_comps - processed,
                'progress_percent': (processed / total_comps * 100) if total_comps > 0 else 0,
                'latest_checkpoint': checkpoint
            }
    
    def clear_checkpoints(self):
        """Clear all checkpoints for this process"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM processing_checkpoint
                WHERE checkpoint_name = ?
            """, (self.config.CHECKPOINT_NAME,))
            conn.commit()
        
        logging.info("Checkpoints cleared")
    
    def validate_checkpoint(self, competition_id: int) -> bool:
        """Validate that a checkpoint is reasonable"""
        with sqlite3.connect(self.db_path) as conn:
            # Check that the competition exists
            exists = conn.execute("""
                SELECT COUNT(*) FROM competitions WHERE id = ?
            """, [competition_id]).fetchone()[0]
            
            if not exists:
                logging.error(f"Competition {competition_id} does not exist")
                return False
            
            # Check that we have some correlations for earlier competitions
            correlations_count = conn.execute("""
                SELECT COUNT(*) FROM rider_correlations_denorm
                WHERE competition_id <= ?
            """, [competition_id]).fetchone()[0]
            
            if correlations_count == 0:
                logging.warning(f"No correlations found for competitions <= {competition_id}")
            
            return True