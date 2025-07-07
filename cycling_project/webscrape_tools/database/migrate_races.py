#!/usr/bin/env python3
"""
Migrate race data from pickle files to SQLite database.

This script reads the hierarchical directory structure of pickle files
and migrates all race data to the normalized SQLite database.
"""

import pickle
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime
import sys
import os

# Add parent directories to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from cycling_project.webscrape_tools.create_race_data import Race, Stage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RaceMigrator:
    """Handles migration of race data from pickle files to SQLite database."""
    
    def __init__(self, source_dir: str, db_path: str):
        """
        Initialize the migrator.
        
        Args:
            source_dir: Root directory containing year folders with pickle files
            db_path: Path to the SQLite database
        """
        self.source_dir = Path(source_dir)
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Caches for avoiding duplicate lookups
        self.rider_cache = {}  # fc_rider_id -> db_id
        self.team_cache = {}   # fc_team_id -> db_id
        
        # Statistics
        self.stats = {
            'races_processed': 0,
            'competitions_created': 0,
            'riders_created': 0,
            'teams_created': 0,
            'results_created': 0,
            'errors': 0
        }
        
    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        logger.info(f"Connected to database: {self.db_path}")
        
    def disconnect(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")
            
    def migrate_all(self):
        """Migrate all race data from the source directory."""
        try:
            self.connect()
            
            # Get all year directories
            year_dirs = sorted([d for d in self.source_dir.iterdir() 
                              if d.is_dir() and d.name.isdigit()])
            
            logger.info(f"Found {len(year_dirs)} year directories to process")
            
            for year_dir in year_dirs:
                self.migrate_year(year_dir)
                
            # Commit final changes
            self.conn.commit()
            
            # Print statistics
            self.print_statistics()
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self.disconnect()
            
    def migrate_year(self, year_dir: Path):
        """Migrate all races for a given year."""
        year = year_dir.name
        logger.info(f"Processing year: {year}")
        
        # Process each category
        for category in ['wt', 'pro', 'd1']:
            category_dir = year_dir / category
            if category_dir.exists():
                self.migrate_category(category_dir, category)
            else:
                logger.warning(f"Category directory not found: {category_dir}")
                
    def migrate_category(self, category_dir: Path, category: str):
        """Migrate all races in a category directory."""
        pkl_files = list(category_dir.glob('*.pkl'))
        logger.info(f"Found {len(pkl_files)} races in {category_dir}")
        
        for pkl_file in pkl_files:
            try:
                self.migrate_race(pkl_file, category)
                
                # Commit every 10 races to avoid large transactions
                if self.stats['races_processed'] % 10 == 0:
                    self.conn.commit()
                    logger.debug("Committed transaction")
                    
            except Exception as e:
                logger.error(f"Error migrating {pkl_file}: {e}")
                self.stats['errors'] += 1
                # Continue with next race
                
    def migrate_race(self, pkl_file: Path, category: str):
        """Migrate a single race from a pickle file."""
        logger.debug(f"Migrating race: {pkl_file}")
        
        # Load the race object
        with open(pkl_file, 'rb') as f:
            race = pickle.load(f)
            
        # Insert the race
        race_id = self.insert_race(race, category)
        
        if race.stage_race:
            # Process stage race
            self.process_stage_race(race, race_id)
        else:
            # Process one-day race
            self.process_one_day_race(race, race_id)
            
        self.stats['races_processed'] += 1
        
    def insert_race(self, race: Race, category: str) -> int:
        """Insert a race record and return its ID."""
        # Parse date if available
        race_date = None
        if race.date:
            try:
                if isinstance(race.date, datetime):
                    race_date = race.date.date()
                else:
                    race_date = datetime.strptime(str(race.date), '%Y-%m-%d').date()
            except:
                logger.warning(f"Could not parse date for {race.name}: {race.date}")
                
        # Insert race
        self.cursor.execute("""
            INSERT INTO races (fc_race_id, name, year, date, category, is_stage_race, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            race.fc_race_id,
            race.name,
            race.year,
            race_date,
            category,
            race.stage_race,
            race.url
        ))
        
        return self.cursor.lastrowid
        
    def process_one_day_race(self, race: Race, race_id: int):
        """Process a one-day race."""
        # Create competition entry
        competition_id = self.insert_competition(
            race_id=race_id,
            name=race.name,
            competition_type='one_day',
            date=race.date,
            winning_time=race.race_time,
            url=race.url
        )
        
        # Insert results
        if race.results:
            self.insert_results(competition_id, race.results, race.date)
            
    def process_stage_race(self, race: Race, race_id: int):
        """Process a stage race with multiple stages."""
        # Insert GC if it has results
        if race.results:
            gc_competition_id = self.insert_competition(
                race_id=race_id,
                name="GC",
                competition_type='gc',
                date=race.date,
                winning_time=race.race_time,
                url=race.url
            )
            self.insert_results(gc_competition_id, race.results, race.date)
            
        # Process each stage
        for i, stage in enumerate(race.stages, 1):
            # Skip GC stages - they're already processed above
            if stage.name.strip().upper() == 'GC':
                logger.debug(f"Skipping duplicate GC stage for {race.name}")
                continue
                
            # Determine stage number
            stage_num = None
            if stage.name.startswith("Stage:"):
                try:
                    stage_num = int(stage.name.split("Stage:")[1].strip().split()[0])
                except:
                    stage_num = i
                    
            # Insert stage competition
            stage_competition_id = self.insert_competition(
                race_id=race_id,
                name=stage.name,
                stage_number=stage_num,
                competition_type='stage',
                date=stage.date,
                winning_time=stage.race_time or stage.time,  # Handle legacy field
                url=stage.url
            )
            
            # Insert stage results
            if stage.results:
                self.insert_results(stage_competition_id, stage.results, stage.date)
                
    def insert_competition(self, race_id: int, name: str, competition_type: str,
                          date: Any, winning_time: Optional[float], url: str,
                          stage_number: Optional[int] = None) -> int:
        """Insert a competition record and return its ID."""
        # Parse date if needed
        comp_date = None
        if date:
            try:
                if isinstance(date, datetime):
                    comp_date = date.date()
                elif isinstance(date, str):
                    comp_date = datetime.strptime(date, '%Y-%m-%d').date()
                else:
                    comp_date = date
            except:
                logger.warning(f"Could not parse competition date: {date}")
                
        self.cursor.execute("""
            INSERT INTO competitions (race_id, name, stage_number, competition_type, 
                                    date, winning_time, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            race_id,
            name,
            stage_number,
            competition_type,
            comp_date,
            winning_time,
            url
        ))
        
        self.stats['competitions_created'] += 1
        return self.cursor.lastrowid
        
    def insert_results(self, competition_id: int, results: List[Dict], 
                      competition_date: Any):
        """Insert all results for a competition."""
        # Count only actual finishers (not DNF, DNS, etc.)
        total_finishers = sum(1 for r in results 
                            if r.get('place', '').isdigit())
        
        for result in results:
            try:
                # Get or create rider
                rider_id = self.get_or_create_rider(
                    result.get('rider_id'),
                    result.get('name'),
                    result.get('dob')
                )
                
                # Get or create team
                team_id = None
                if result.get('team_id') and result.get('team'):
                    team_id = self.get_or_create_team(
                        result.get('team_id'),
                        result.get('team')
                    )
                    
                # Calculate age
                rider_age = None
                if result.get('dob') and competition_date:
                    try:
                        birth_year = int(result['dob'])
                        if isinstance(competition_date, str):
                            comp_year = int(competition_date[:4])
                        elif isinstance(competition_date, datetime):
                            comp_year = competition_date.year
                        else:
                            comp_year = None
                            
                        if comp_year and birth_year:
                            rider_age = comp_year - birth_year
                    except:
                        pass
                        
                # Skip DNF, DNS, OOT, DSQ results
                place_str = result.get('place', '')
                if place_str in ['DNF', 'DNS', 'OOT', 'DSQ'] or not place_str.isdigit():
                    continue
                    
                # Calculate percentile
                place = int(place_str)
                percentile = 100.0 * (total_finishers - place + 1) / total_finishers
                
                # Handle gap value - it might be empty or missing
                gap_value = result.get('gap')
                if gap_value is not None and gap_value != '':
                    try:
                        time_gap = float(gap_value)
                    except ValueError:
                        time_gap = None
                else:
                    time_gap = None
                
                # Insert result
                self.cursor.execute("""
                    INSERT INTO rider_results (competition_id, rider_id, team_id, place, 
                                             time_gap, bib_number, rider_age, percentile)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    competition_id,
                    rider_id,
                    team_id,
                    place,
                    time_gap,
                    result.get('bib_number'),
                    rider_age,
                    round(percentile, 2)
                ))
                
                self.stats['results_created'] += 1
                
            except Exception as e:
                logger.error(f"Error inserting result for {result.get('name')}: {e}")
                
    def get_or_create_rider(self, fc_rider_id: Optional[str], name: str, 
                           birth_year: Optional[str]) -> int:
        """Get existing rider ID or create new rider."""
        if not fc_rider_id:
            fc_rider_id = f"unknown_{name.replace(' ', '_')}"
            
        # Check cache first
        if fc_rider_id in self.rider_cache:
            return self.rider_cache[fc_rider_id]
            
        # Check database
        self.cursor.execute("SELECT id FROM riders WHERE fc_rider_id = ?", (fc_rider_id,))
        result = self.cursor.fetchone()
        
        if result:
            rider_id = result[0]
        else:
            # Create new rider
            birth_year_int = None
            if birth_year:
                try:
                    birth_year_int = int(birth_year)
                except:
                    pass
                    
            self.cursor.execute("""
                INSERT INTO riders (fc_rider_id, name, birth_year)
                VALUES (?, ?, ?)
            """, (fc_rider_id, name, birth_year_int))
            
            rider_id = self.cursor.lastrowid
            self.stats['riders_created'] += 1
            
        # Cache the result
        self.rider_cache[fc_rider_id] = rider_id
        return rider_id
        
    def get_or_create_team(self, fc_team_id: str, name: str) -> int:
        """Get existing team ID or create new team."""
        # Check cache first
        if fc_team_id in self.team_cache:
            return self.team_cache[fc_team_id]
            
        # Check database
        self.cursor.execute("SELECT id FROM teams WHERE fc_team_id = ?", (fc_team_id,))
        result = self.cursor.fetchone()
        
        if result:
            team_id = result[0]
        else:
            # Create new team
            self.cursor.execute("""
                INSERT INTO teams (fc_team_id, name)
                VALUES (?, ?)
            """, (fc_team_id, name))
            
            team_id = self.cursor.lastrowid
            self.stats['teams_created'] += 1
            
        # Cache the result
        self.team_cache[fc_team_id] = team_id
        return team_id
        
    def print_statistics(self):
        """Print migration statistics."""
        logger.info("\n" + "="*50)
        logger.info("Migration Statistics:")
        logger.info(f"  Races processed: {self.stats['races_processed']}")
        logger.info(f"  Competitions created: {self.stats['competitions_created']}")
        logger.info(f"  Riders created: {self.stats['riders_created']}")
        logger.info(f"  Teams created: {self.stats['teams_created']}")
        logger.info(f"  Results created: {self.stats['results_created']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        logger.info("="*50 + "\n")


def main():
    """Main entry point for the migration script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate race data to SQLite database")
    parser.add_argument("--source-dir", default="~/cycling_data/scraped_data",
                        help="Root directory containing pickle files")
    parser.add_argument("--db-path", default="database/cycling_races.db",
                        help="Path to the SQLite database")
    parser.add_argument("--year", help="Migrate only a specific year")
    parser.add_argument("--category", choices=['wt', 'pro', 'd1'],
                        help="Migrate only a specific category")
    
    args = parser.parse_args()
    
    # Create migrator
    migrator = RaceMigrator(args.source_dir, args.db_path)
    
    if args.year:
        # Migrate specific year
        year_dir = Path(args.source_dir) / args.year
        if not year_dir.exists():
            logger.error(f"Year directory not found: {year_dir}")
            return
            
        migrator.connect()
        if args.category:
            # Migrate specific category in year
            category_dir = year_dir / args.category
            if category_dir.exists():
                migrator.migrate_category(category_dir, args.category)
            else:
                logger.error(f"Category directory not found: {category_dir}")
        else:
            # Migrate all categories in year
            migrator.migrate_year(year_dir)
        migrator.disconnect()
    else:
        # Migrate everything
        migrator.migrate_all()


if __name__ == "__main__":
    main()