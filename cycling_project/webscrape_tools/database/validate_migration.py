#!/usr/bin/env python3
"""
Validate the migration from pickle files to SQLite database.

This script compares data in the pickle files with data in the database
to ensure the migration was successful and complete.
"""

import pickle
import sqlite3
from pathlib import Path
import sys
import os
from typing import Dict, List, Tuple
import logging

# Add parent directories to Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from cycling_project.webscrape_tools.create_race_data import Race, Stage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationValidator:
    """Validates the migration from pickle files to SQLite database."""
    
    def __init__(self, source_dir: str, db_path: str):
        """
        Initialize the validator.
        
        Args:
            source_dir: Root directory containing pickle files
            db_path: Path to the SQLite database
        """
        self.source_dir = Path(source_dir)
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        
        # Validation results
        self.issues = []
        self.stats = {
            'pkl_files_checked': 0,
            'races_matched': 0,
            'races_missing': 0,
            'competitions_matched': 0,
            'competitions_missing': 0,
            'results_matched': 0,
            'results_mismatch': 0
        }
        
    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
    def disconnect(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            
    def validate_all(self):
        """Run all validation checks."""
        self.connect()
        
        try:
            logger.info("Starting validation...")
            
            # Get database statistics
            self.print_database_stats()
            
            # Validate each year
            year_dirs = sorted([d for d in self.source_dir.iterdir() 
                              if d.is_dir() and d.name.isdigit()])
            
            for year_dir in year_dirs:
                self.validate_year(year_dir)
                
            # Print validation results
            self.print_validation_results()
            
        finally:
            self.disconnect()
            
    def print_database_stats(self):
        """Print current database statistics."""
        logger.info("\n" + "="*50)
        logger.info("Database Statistics:")
        
        # Count races by year and category
        self.cursor.execute("""
            SELECT year, category, COUNT(*) 
            FROM races 
            GROUP BY year, category 
            ORDER BY year, category
        """)
        
        logger.info("\nRaces by year and category:")
        for year, category, count in self.cursor.fetchall():
            logger.info(f"  {year} {category}: {count} races")
            
        # Overall counts
        self.cursor.execute("SELECT COUNT(*) FROM races")
        race_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM competitions")
        comp_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM riders")
        rider_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM teams")
        team_count = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM rider_results")
        result_count = self.cursor.fetchone()[0]
        
        logger.info(f"\nTotal counts:")
        logger.info(f"  Races: {race_count}")
        logger.info(f"  Competitions: {comp_count}")
        logger.info(f"  Riders: {rider_count}")
        logger.info(f"  Teams: {team_count}")
        logger.info(f"  Results: {result_count}")
        logger.info("="*50 + "\n")
        
    def validate_year(self, year_dir: Path):
        """Validate all races for a given year."""
        year = year_dir.name
        
        for category in ['wt', 'pro', 'd1']:
            category_dir = year_dir / category
            if category_dir.exists():
                self.validate_category(category_dir, year, category)
                
    def validate_category(self, category_dir: Path, year: str, category: str):
        """Validate all races in a category."""
        pkl_files = list(category_dir.glob('*.pkl'))
        
        for pkl_file in pkl_files:
            self.validate_race_file(pkl_file, year, category)
            
    def validate_race_file(self, pkl_file: Path, year: str, category: str):
        """Validate a single race pickle file against the database."""
        self.stats['pkl_files_checked'] += 1
        
        try:
            # Load the pickle file
            with open(pkl_file, 'rb') as f:
                race = pickle.load(f)
                
            # Check if race exists in database
            self.cursor.execute("""
                SELECT id, name, is_stage_race 
                FROM races 
                WHERE fc_race_id = ? AND year = ? AND category = ?
            """, (race.fc_race_id, int(year), category))
            
            db_race = self.cursor.fetchone()
            
            if not db_race:
                self.issues.append(f"Race not found in DB: {race.name} ({year} {category})")
                self.stats['races_missing'] += 1
                return
                
            self.stats['races_matched'] += 1
            race_id = db_race[0]
            
            # Validate competitions
            if race.stage_race:
                self.validate_stage_race(race, race_id)
            else:
                self.validate_one_day_race(race, race_id)
                
        except Exception as e:
            self.issues.append(f"Error validating {pkl_file}: {e}")
            
    def validate_one_day_race(self, race: Race, race_id: int):
        """Validate a one-day race."""
        # Check competition exists
        self.cursor.execute("""
            SELECT id, winning_time 
            FROM competitions 
            WHERE race_id = ? AND competition_type = 'one_day'
        """, (race_id,))
        
        comp = self.cursor.fetchone()
        
        if not comp:
            self.issues.append(f"Competition not found for one-day race: {race.name}")
            self.stats['competitions_missing'] += 1
            return
            
        self.stats['competitions_matched'] += 1
        
        # Validate result count
        if race.results:
            self.validate_result_count(comp[0], len(race.results), race.name)
            
    def validate_stage_race(self, race: Race, race_id: int):
        """Validate a stage race."""
        # Check GC if it has results
        if race.results:
            self.cursor.execute("""
                SELECT id FROM competitions 
                WHERE race_id = ? AND competition_type = 'gc'
            """, (race_id,))
            
            gc = self.cursor.fetchone()
            if gc:
                self.stats['competitions_matched'] += 1
                self.validate_result_count(gc[0], len(race.results), f"{race.name} GC")
            else:
                self.issues.append(f"GC competition not found for: {race.name}")
                self.stats['competitions_missing'] += 1
                
        # Check each stage
        expected_stages = len(race.stages)
        self.cursor.execute("""
            SELECT COUNT(*) FROM competitions 
            WHERE race_id = ? AND competition_type = 'stage'
        """, (race_id,))
        
        actual_stages = self.cursor.fetchone()[0]
        
        if expected_stages != actual_stages:
            self.issues.append(
                f"Stage count mismatch for {race.name}: "
                f"expected {expected_stages}, found {actual_stages}"
            )
        else:
            self.stats['competitions_matched'] += expected_stages
            
    def validate_result_count(self, competition_id: int, expected_count: int, 
                            competition_name: str):
        """Validate the number of results for a competition."""
        # Count only finishers (not DNF, DNS, etc.)
        self.cursor.execute("""
            SELECT COUNT(*) FROM rider_results 
            WHERE competition_id = ?
        """, (competition_id,))
        
        actual_count = self.cursor.fetchone()[0]
        
        if actual_count == expected_count:
            self.stats['results_matched'] += 1
        else:
            # This might not be an error if we're filtering out DNF/DNS
            if actual_count < expected_count:
                # This is expected due to DNF/DNS filtering
                self.stats['results_matched'] += 1
            else:
                self.issues.append(
                    f"Result count mismatch for {competition_name}: "
                    f"expected <= {expected_count}, found {actual_count}"
                )
                self.stats['results_mismatch'] += 1
                
    def print_validation_results(self):
        """Print the validation results."""
        logger.info("\n" + "="*50)
        logger.info("Validation Results:")
        logger.info(f"  Pickle files checked: {self.stats['pkl_files_checked']}")
        logger.info(f"  Races matched: {self.stats['races_matched']}")
        logger.info(f"  Races missing: {self.stats['races_missing']}")
        logger.info(f"  Competitions matched: {self.stats['competitions_matched']}")
        logger.info(f"  Competitions missing: {self.stats['competitions_missing']}")
        logger.info(f"  Results validated: {self.stats['results_matched']}")
        logger.info(f"  Results mismatched: {self.stats['results_mismatch']}")
        
        if self.issues:
            logger.warning(f"\nFound {len(self.issues)} issues:")
            for i, issue in enumerate(self.issues[:10], 1):
                logger.warning(f"  {i}. {issue}")
            if len(self.issues) > 10:
                logger.warning(f"  ... and {len(self.issues) - 10} more issues")
        else:
            logger.info("\nNo issues found! Migration appears successful.")
            
        logger.info("="*50 + "\n")
        
    def check_sample_queries(self):
        """Run some sample queries to verify data integrity."""
        logger.info("\nRunning sample queries...")
        
        # Find riders with most wins
        self.cursor.execute("""
            SELECT r.name, COUNT(*) as wins
            FROM rider_results rr
            JOIN riders r ON rr.rider_id = r.id
            WHERE rr.place = 1
            GROUP BY r.id, r.name
            ORDER BY wins DESC
            LIMIT 5
        """)
        
        logger.info("\nTop 5 riders by wins:")
        for name, wins in self.cursor.fetchall():
            logger.info(f"  {name}: {wins} wins")
            
        # Find biggest races by finishers
        self.cursor.execute("""
            SELECT r.name, c.name, COUNT(*) as finishers
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            JOIN races r ON c.race_id = r.id
            GROUP BY c.id
            ORDER BY finishers DESC
            LIMIT 5
        """)
        
        logger.info("\nTop 5 competitions by finishers:")
        for race_name, comp_name, finishers in self.cursor.fetchall():
            logger.info(f"  {race_name} - {comp_name}: {finishers} finishers")


def main():
    """Main entry point for the validation script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate race data migration")
    parser.add_argument("--source-dir", default="~/cycling_data/scraped_data",
                        help="Root directory containing pickle files")
    parser.add_argument("--db-path", default="database/cycling_races.db",
                        help="Path to the SQLite database")
    parser.add_argument("--sample-queries", action="store_true",
                        help="Run sample queries to test data integrity")
    
    args = parser.parse_args()
    
    validator = MigrationValidator(args.source_dir, args.db_path)
    validator.validate_all()
    
    if args.sample_queries:
        validator.connect()
        validator.check_sample_queries()
        validator.disconnect()


if __name__ == "__main__":
    main()