#!/usr/bin/env python3
"""
Create the SQLite database schema for cycling race data.

This script creates all tables, indexes, and constraints needed for the 
cycling race database migration.
"""

import sqlite3
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_database(db_path: str) -> None:
    """
    Create the SQLite database with all tables and indexes.
    
    Args:
        db_path: Path where the database file should be created
    """
    # Ensure the directory exists
    db_file = Path(db_path)
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Creating database at: {db_path}")
    
    # Connect to database (creates file if it doesn't exist)
    conn = sqlite3.connect(db_path)
    
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")
    
    cursor = conn.cursor()
    
    try:
        # Create races table
        logger.info("Creating races table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS races (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fc_race_id TEXT NOT NULL,
                name TEXT NOT NULL,
                year INTEGER NOT NULL,
                date DATE,
                category TEXT NOT NULL CHECK(category IN ('wt', 'pro', 'd1')),
                is_stage_race BOOLEAN NOT NULL,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create competitions table
        logger.info("Creating competitions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS competitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                stage_number INTEGER,
                competition_type TEXT NOT NULL CHECK(competition_type IN ('one_day', 'stage', 'gc')),
                date DATE,
                winning_time REAL,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (race_id) REFERENCES races(id) ON DELETE CASCADE
            )
        """)
        
        # Create riders table
        logger.info("Creating riders table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS riders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fc_rider_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                birth_year INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create teams table
        logger.info("Creating teams table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fc_team_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create rider_results table
        logger.info("Creating rider_results table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rider_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competition_id INTEGER NOT NULL,
                rider_id INTEGER NOT NULL,
                team_id INTEGER,
                place INTEGER NOT NULL,
                time_gap REAL,
                bib_number TEXT,
                rider_age INTEGER,
                percentile REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
                FOREIGN KEY (rider_id) REFERENCES riders(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE SET NULL,
                UNIQUE(competition_id, rider_id)
            )
        """)
        
        # Create rider_team_history table (for future use)
        logger.info("Creating rider_team_history table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rider_team_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rider_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                FOREIGN KEY (rider_id) REFERENCES riders(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                UNIQUE(rider_id, team_id, year)
            )
        """)
        
        # Create indexes
        logger.info("Creating indexes...")
        
        # Races indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_fc_id_year ON races(fc_race_id, year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_year_category ON races(year, category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_races_name ON races(name)")
        
        # Competitions indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitions_race_id ON competitions(race_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitions_race_stage ON competitions(race_id, stage_number)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitions_date ON competitions(date)")
        
        # Riders indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_riders_fc_id ON riders(fc_rider_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_riders_name ON riders(name)")
        
        # Teams indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_teams_fc_id ON teams(fc_team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name)")
        
        # Rider results indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_competition_place ON rider_results(competition_id, place)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_rider_competition ON rider_results(rider_id, competition_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_team ON rider_results(team_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_percentile ON rider_results(percentile)")
        
        # Create useful views
        logger.info("Creating views...")
        
        # View for race results with all details
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_race_results AS
            SELECT 
                r.name AS race_name,
                r.year,
                r.category,
                c.name AS competition_name,
                c.competition_type,
                c.date,
                rid.name AS rider_name,
                rid.fc_rider_id,
                t.name AS team_name,
                rr.place,
                rr.time_gap,
                rr.percentile,
                rr.rider_age,
                rr.bib_number
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            JOIN riders rid ON rr.rider_id = rid.id
            LEFT JOIN teams t ON rr.team_id = t.id
        """)
        
        # View for rider statistics
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS v_rider_stats AS
            SELECT 
                rid.id AS rider_id,
                rid.name AS rider_name,
                COUNT(DISTINCT rr.competition_id) AS races_completed,
                COUNT(CASE WHEN rr.place = 1 THEN 1 END) AS wins,
                COUNT(CASE WHEN rr.place <= 3 THEN 1 END) AS podiums,
                COUNT(CASE WHEN rr.place <= 10 THEN 1 END) AS top_10s,
                ROUND(AVG(rr.percentile), 2) AS avg_percentile,
                MIN(r.year) AS first_year,
                MAX(r.year) AS last_year
            FROM riders rid
            JOIN rider_results rr ON rid.id = rr.rider_id
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            GROUP BY rid.id, rid.name
        """)
        
        # Commit all changes
        conn.commit()
        logger.info("Database created successfully!")
        
        # Print summary
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Created {len(tables)} tables: {', '.join([t[0] for t in tables])}")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cursor.fetchall()
        logger.info(f"Created {len(indexes)} indexes")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = cursor.fetchall()
        logger.info(f"Created {len(views)} views: {', '.join([v[0] for v in views])}")
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def drop_database(db_path: str) -> None:
    """
    Drop all tables in the database (useful for testing).
    
    Args:
        db_path: Path to the database file
    """
    logger.warning(f"Dropping all tables in database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    # Drop each table
    for table in tables:
        logger.info(f"Dropping table: {table[0]}")
        cursor.execute(f"DROP TABLE IF EXISTS {table[0]}")
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Create the cycling race database")
    parser.add_argument("--db-path", default="database/cycling_races.db", 
                        help="Path to the database file (default: database/cycling_races.db)")
    parser.add_argument("--drop", action="store_true", 
                        help="Drop all tables before creating (WARNING: destroys data)")
    
    args = parser.parse_args()
    
    if args.drop:
        response = input("Are you sure you want to drop all tables? This will destroy all data! (yes/no): ")
        if response.lower() == "yes":
            drop_database(args.db_path)
        else:
            logger.info("Drop operation cancelled")
            exit(0)
    
    create_database(args.db_path)