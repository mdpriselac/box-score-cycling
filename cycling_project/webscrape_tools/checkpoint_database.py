"""
Checkpoint the WAL file to reconcile the database.
"""

import sqlite3
import sys
import os


def checkpoint_database(db_path):
    """Force a checkpoint to merge WAL into main database"""
    
    print(f"Attempting to checkpoint database: {db_path}")
    
    # Check file sizes before
    db_size = os.path.getsize(db_path) / (1024**3)  # GB
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    
    wal_size = 0
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path) / (1024**3)  # GB
        
    print(f"Before checkpoint:")
    print(f"  Main DB: {db_size:.1f} GB")
    print(f"  WAL file: {wal_size:.1f} GB")
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        
        # Try PRAGMA wal_checkpoint
        print("\nRunning WAL checkpoint...")
        result = conn.execute("PRAGMA wal_checkpoint(FULL)").fetchone()
        print(f"Checkpoint result: {result}")
        
        # The result is (busy, checkpointed_frames, total_frames)
        if result:
            busy, checkpointed, total = result
            if busy == 0:
                print(f"✓ Successfully checkpointed {checkpointed} of {total} frames")
            else:
                print(f"⚠ Database busy, only checkpointed {checkpointed} of {total} frames")
        
        # Check if we can truncate the WAL
        print("\nAttempting to truncate WAL...")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        
        conn.close()
        
        # Check file sizes after
        db_size_after = os.path.getsize(db_path) / (1024**3)
        wal_size_after = 0
        if os.path.exists(wal_path):
            wal_size_after = os.path.getsize(wal_path) / (1024**3)
            
        print(f"\nAfter checkpoint:")
        print(f"  Main DB: {db_size_after:.1f} GB")
        print(f"  WAL file: {wal_size_after:.1f} GB")
        
        if wal_size_after < wal_size:
            print(f"✓ Reduced WAL by {wal_size - wal_size_after:.1f} GB")
        else:
            print("⚠ WAL size unchanged - database may be in use")
            
    except sqlite3.OperationalError as e:
        print(f"✗ Error: {e}")
        print("\nThe database is likely locked by another process.")
        print("Please close all applications using the database and try again.")
        return False
    
    return True


if __name__ == "__main__":
    db_path = "database/database/cycling_races.db"
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    print("=== SQLite WAL Checkpoint Tool ===")
    print("\nWARNING: This will merge the WAL file into the main database.")
    print("Make sure no other processes are writing to the database!")
    
    response = input("\nContinue? (y/n): ")
    if response.lower() == 'y':
        checkpoint_database(db_path)
    else:
        print("Checkpoint cancelled.")