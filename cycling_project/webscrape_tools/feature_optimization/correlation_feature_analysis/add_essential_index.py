"""
Add the essential index for correlation analysis performance.
"""

import sqlite3
import sys
from pathlib import Path


def add_essential_index(db_path: str):
    """Add the correlation_type + percentile index"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Adding essential index to {db_path}...")
    
    try:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_corr_type_percentile 
            ON rider_correlations_denorm (correlation_type, percentile)
        """)
        conn.commit()
        print("✓ Created correlation_type + percentile index")
        
        # Check if it was created
        result = cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' 
            AND name='idx_corr_type_percentile'
        """).fetchone()
        
        if result:
            print("✓ Index confirmed in database")
        else:
            print("⚠ Index may already exist")
            
    except Exception as e:
        print(f"Error creating index: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    # Default database path
    db_path = "../../database/database/cycling_races.db"
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    add_essential_index(db_path)
    print("Ready to test performance!")