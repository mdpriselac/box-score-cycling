"""
Monitor WAL file size during processing
Usage: uv run python monitor_wal.py [interval_seconds]
"""
import os
import sqlite3
import sys
import time
from datetime import datetime

def check_wal_status(db_path, show_details=False):
    """Check WAL file status and return size info"""
    
    # Check for WAL file
    wal_path = db_path + "-wal"
    shm_path = db_path + "-shm"
    
    wal_size = 0
    shm_size = 0
    
    if os.path.exists(wal_path):
        wal_size = os.path.getsize(wal_path)
    
    if os.path.exists(shm_path):
        shm_size = os.path.getsize(shm_path)
    
    if show_details:
        # Check database settings
        with sqlite3.connect(db_path) as conn:
            journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            wal_autocheckpoint = conn.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            
            print(f"Journal mode: {journal_mode}")
            print(f"WAL autocheckpoint: {wal_autocheckpoint} pages ({(wal_autocheckpoint * page_size) / (1024 * 1024):.1f} MB)")
            print(f"Page size: {page_size:,} bytes")
    
    return wal_size, shm_size

def monitor_wal(db_path, interval=30):
    """Monitor WAL file size continuously"""
    print(f"Monitoring WAL file size every {interval} seconds...")
    print("Press Ctrl+C to stop")
    print()
    
    # Show initial settings
    check_wal_status(db_path, show_details=True)
    print()
    print("Timestamp               WAL Size      SHM Size")
    print("-" * 50)
    
    try:
        while True:
            wal_size, shm_size = check_wal_status(db_path)
            timestamp = datetime.now().strftime('%H:%M:%S')
            
            wal_mb = wal_size / (1024 * 1024)
            shm_kb = shm_size / 1024
            
            status = ""
            if wal_mb > 10:
                status = " ⚠️  Large WAL!"
            elif wal_mb > 5:
                status = " ⚡ Growing"
            
            print(f"{timestamp}     {wal_mb:8.2f} MB    {shm_kb:6.1f} KB{status}")
            
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
        
        # Final check
        wal_size, shm_size = check_wal_status(db_path)
        print(f"\nFinal WAL size: {wal_size / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    db_path = "../database/database/cycling_races.db"
    interval = 30
    
    if len(sys.argv) > 1:
        interval = int(sys.argv[1])
    
    monitor_wal(db_path, interval)