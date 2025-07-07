
"""
Example queries for the cycling race database.

This script demonstrates common patterns and useful queries
for analyzing cycling race data in the SQLite database.
"""

import sqlite3
from pathlib import Path
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RaceAnalyzer:
    """Provides methods for analyzing cycling race data."""
    
    def __init__(self, db_path: str):
        """
        Initialize the analyzer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to the database."""
        self.conn = sqlite3.connect(self.db_path)
        logger.info(f"Connected to database: {self.db_path}")
        
    def disconnect(self):
        """Disconnect from the database."""
        if self.conn:
            self.conn.close()
            logger.info("Disconnected from database")
            
    def query_to_df(self, query: str, params=None) -> pd.DataFrame:
        """Execute a query and return results as a pandas DataFrame."""
        return pd.read_sql_query(query, self.conn, params=params or [])
        
    def rider_performance_summary(self, rider_name: str = None):
        """Get performance summary for a rider or all riders."""
        query = """
        SELECT 
            r.name as rider_name,
            COUNT(DISTINCT rr.competition_id) as races_completed,
            COUNT(CASE WHEN rr.place = 1 THEN 1 END) as wins,
            COUNT(CASE WHEN rr.place <= 3 THEN 1 END) as podiums,
            COUNT(CASE WHEN rr.place <= 10 THEN 1 END) as top_10s,
            ROUND(AVG(rr.percentile), 2) as avg_percentile,
            MIN(races.year) as first_year,
            MAX(races.year) as last_year
        FROM riders r
        JOIN rider_results rr ON r.id = rr.rider_id
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races races ON c.race_id = races.id
        """
        
        params = []
        if rider_name:
            query += " WHERE r.name LIKE ?"
            params.append(f"%{rider_name}%")
            
        query += """
        GROUP BY r.id, r.name
        ORDER BY wins DESC, podiums DESC
        """
        
        return self.query_to_df(query, params)
        
    def race_winners_by_year(self, year: int = None):
        """Get race winners for a specific year or all years."""
        query = """
        SELECT 
            races.year,
            races.name as race_name,
            races.category,
            c.name as competition_name,
            c.competition_type,
            riders.name as winner,
            teams.name as team,
            rr.time_gap
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races races ON c.race_id = races.id
        JOIN riders riders ON rr.rider_id = riders.id
        LEFT JOIN teams teams ON rr.team_id = teams.id
        WHERE rr.place = 1
        """
        
        params = []
        if year:
            query += " AND races.year = ?"
            params.append(year)
            
        query += " ORDER BY races.year DESC, races.date, c.stage_number"
        
        return self.query_to_df(query, params)
        
    def dominant_performances(self, min_percentile: float = 95.0):
        """Find dominant performances (high percentile finishes)."""
        query = """
        SELECT 
            riders.name as rider,
            races.name as race,
            c.name as competition,
            races.year,
            rr.place,
            rr.percentile,
            rr.time_gap,
            teams.name as team
        FROM rider_results rr
        JOIN riders riders ON rr.rider_id = riders.id
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races races ON c.race_id = races.id
        LEFT JOIN teams teams ON rr.team_id = teams.id
        WHERE rr.percentile >= ?
        ORDER BY rr.percentile DESC, races.year DESC
        """
        
        return self.query_to_df(query, [min_percentile])
        
    def team_performance(self, year: int = None):
        """Analyze team performance by wins and podiums."""
        query = """
        SELECT 
            teams.name as team,
            COUNT(DISTINCT rr.rider_id) as riders_used,
            COUNT(CASE WHEN rr.place = 1 THEN 1 END) as wins,
            COUNT(CASE WHEN rr.place <= 3 THEN 1 END) as podiums,
            COUNT(CASE WHEN rr.place <= 10 THEN 1 END) as top_10s,
            ROUND(AVG(rr.percentile), 2) as avg_percentile
        FROM teams teams
        JOIN rider_results rr ON teams.id = rr.team_id
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races races ON c.race_id = races.id
        """
        
        params = []
        if year:
            query += " WHERE races.year = ?"
            params.append(year)
            
        query += """
        GROUP BY teams.id, teams.name
        HAVING COUNT(rr.id) >= 10  -- Only teams with significant participation
        ORDER BY wins DESC, podiums DESC
        """
        
        return self.query_to_df(query, params)
        
    def race_competitiveness(self, race_name: str = None):
        """Analyze race competitiveness by time gaps."""
        query = """
        SELECT 
            races.name as race,
            c.name as competition,
            races.year,
            COUNT(rr.id) as finishers,
            MIN(rr.time_gap) as min_gap,
            AVG(rr.time_gap) as avg_gap,
            MAX(rr.time_gap) as max_gap,
            -- Time gap at 10th place
            (SELECT time_gap FROM rider_results 
             WHERE competition_id = c.id AND place = 10) as gap_at_10th
        FROM races races
        JOIN competitions c ON races.id = c.race_id
        JOIN rider_results rr ON c.id = rr.competition_id
        """
        
        params = []
        if race_name:
            query += " WHERE races.name LIKE ?"
            params.append(f"%{race_name}%")
            
        query += """
        GROUP BY races.id, c.id
        HAVING finishers >= 20  -- Only races with substantial fields
        ORDER BY races.year DESC, avg_gap
        """
        
        return self.query_to_df(query, params)
        
    def rider_development(self, rider_name: str):
        """Track a rider's performance over time."""
        query = """
        SELECT 
            races.year,
            races.name as race,
            c.name as competition,
            rr.place,
            rr.percentile,
            rr.rider_age,
            teams.name as team
        FROM rider_results rr
        JOIN riders riders ON rr.rider_id = riders.id
        JOIN competitions c ON rr.competition_id = c.id
        JOIN races races ON c.race_id = races.id
        LEFT JOIN teams teams ON rr.team_id = teams.id
        WHERE riders.name LIKE ?
        ORDER BY races.year, races.date, c.stage_number
        """
        
        return self.query_to_df(query, [f"%{rider_name}%"])
        
    def stage_race_analysis(self, race_name: str):
        """Analyze stage race results and GC changes."""
        query = """
        SELECT 
            c.name as stage,
            c.stage_number,
            c.competition_type,
            riders.name as winner,
            rr.time_gap as gap_to_first,
            teams.name as team,
            -- GC position for this rider if available
            (SELECT place FROM rider_results gc_rr 
             JOIN competitions gc ON gc_rr.competition_id = gc.id 
             WHERE gc.race_id = c.race_id 
             AND gc.competition_type = 'gc' 
             AND gc_rr.rider_id = rr.rider_id) as gc_position
        FROM competitions c
        JOIN races races ON c.race_id = races.id
        JOIN rider_results rr ON c.id = rr.competition_id
        JOIN riders riders ON rr.rider_id = riders.id
        LEFT JOIN teams teams ON rr.team_id = teams.id
        WHERE races.name LIKE ? 
        AND rr.place = 1  -- Only stage winners
        ORDER BY c.stage_number, c.competition_type
        """
        
        return self.query_to_df(query, [f"%{race_name}%"])
        
    def nationality_analysis(self):
        """Analyze performance by rider nationality (if available in names)."""
        # This is a simplified version - real nationality would need additional data
        query = """
        SELECT 
            CASE 
                WHEN riders.name LIKE '% van %' OR riders.name LIKE '% de %' THEN 'Dutch/Belgian'
                WHEN riders.name LIKE '%sson %' OR riders.name LIKE '%sen %' THEN 'Nordic'
                WHEN riders.name LIKE '%ez %' OR riders.name LIKE '%o %' THEN 'Spanish/Portuguese'
                WHEN riders.name LIKE '%i %' OR riders.name LIKE '%o %' THEN 'Italian'
                ELSE 'Other'
            END as nationality_group,
            COUNT(DISTINCT riders.id) as rider_count,
            COUNT(CASE WHEN rr.place = 1 THEN 1 END) as wins,
            ROUND(AVG(rr.percentile), 2) as avg_percentile
        FROM riders riders
        JOIN rider_results rr ON riders.id = rr.rider_id
        GROUP BY nationality_group
        ORDER BY wins DESC
        """
        
        return self.query_to_df(query)
        
    def database_summary(self):
        """Get overall database statistics."""
        queries = {
            'races_by_year': """
                SELECT year, category, COUNT(*) as race_count
                FROM races 
                GROUP BY year, category 
                ORDER BY year, category
            """,
            'competitions_by_type': """
                SELECT competition_type, COUNT(*) as count
                FROM competitions
                GROUP BY competition_type
            """,
            'results_by_year': """
                SELECT races.year, COUNT(rr.id) as result_count
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                JOIN races races ON c.race_id = races.id
                GROUP BY races.year
                ORDER BY races.year
            """
        }
        
        results = {}
        for name, query in queries.items():
            results[name] = self.query_to_df(query)
            
        return results


def main():
    """Demonstrate various query examples."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run example queries on cycling database")
    parser.add_argument("--db-path", default="database/database/cycling_races.db",
                        help="Path to the SQLite database")
    parser.add_argument("--rider", help="Analyze specific rider")
    parser.add_argument("--race", help="Analyze specific race")
    parser.add_argument("--year", type=int, help="Focus on specific year")
    parser.add_argument("--export", help="Export results to CSV file")
    
    args = parser.parse_args()
    
    analyzer = RaceAnalyzer(args.db_path)
    analyzer.connect()
    
    try:
        # Run different analyses based on arguments
        if args.rider:
            logger.info(f"Analyzing rider: {args.rider}")
            df = analyzer.rider_development(args.rider)
            print(f"\n{args.rider} Race History:")
            print(df.to_string(index=False))
            
            # Also show summary
            summary = analyzer.rider_performance_summary(args.rider)
            print(f"\n{args.rider} Summary:")
            print(summary.to_string(index=False))
            
        elif args.race:
            logger.info(f"Analyzing race: {args.race}")
            
            # Stage race analysis if it's a stage race
            stage_df = analyzer.stage_race_analysis(args.race)
            if not stage_df.empty:
                print(f"\n{args.race} Stage Winners:")
                print(stage_df.to_string(index=False))
            
            # Race competitiveness
            comp_df = analyzer.race_competitiveness(args.race)
            print(f"\n{args.race} Competitiveness:")
            print(comp_df.to_string(index=False))
            
        else:
            # General analysis
            logger.info("Running general database analysis...")
            
            # Database summary
            summary = analyzer.database_summary()
            for name, df in summary.items():
                print(f"\n{name.replace('_', ' ').title()}:")
                print(df.to_string(index=False))
            
            # Top performers
            if args.year:
                winners = analyzer.race_winners_by_year(args.year)
                print(f"\n{args.year} Race Winners:")
                print(winners.head(20).to_string(index=False))
                
                teams = analyzer.team_performance(args.year)
                print(f"\n{args.year} Team Performance:")
                print(teams.head(10).to_string(index=False))
            else:
                # All-time top riders
                riders = analyzer.rider_performance_summary()
                print(f"\nTop Riders (All Time):")
                print(riders.head(20).to_string(index=False))
                
                # Dominant performances
                dominant = analyzer.dominant_performances()
                print(f"\nMost Dominant Performances:")
                print(dominant.head(20).to_string(index=False))
                
    finally:
        analyzer.disconnect()


if __name__ == "__main__":
    main()