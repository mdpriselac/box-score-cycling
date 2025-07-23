import os
import sys

# Try to import dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ dotenv loaded successfully")
except ImportError:
    print("✗ dotenv not available, using hardcoded path")

# Get database path
db_path = os.getenv('DB_PATH')
if db_path:
    print(f"✓ DB_PATH from env: {db_path}")
    print(f"✓ File exists: {os.path.exists(db_path)}")
else:
    print("✗ No DB_PATH in environment")
    # Try hardcoded path
    db_path = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"
    print(f"Using hardcoded path: {db_path}")
    print(f"File exists: {os.path.exists(db_path)}")

# Test database connection
try:
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT COUNT(*) FROM race_features_100")
    count = cursor.fetchone()[0]
    print(f"✓ Database connected. Found {count} records in race_features_100")
    conn.close()
except Exception as e:
    print(f"✗ Database error: {e}")