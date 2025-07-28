"""
Utility to find kurtosis breakdown points across race_features_N tables.
A breakdown occurs when kurtosis becomes NULL due to zero variance.
"""

import sqlite3
from pathlib import Path
import os
from typing import Dict, Optional, List, Tuple

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def find_database():
    """Find the SQLite database file"""
    if HAS_DOTENV:
        load_dotenv()
        db_path = os.getenv('DB_PATH')
        if db_path and os.path.exists(db_path):
            return db_path
    
    # Go up three levels from current directory to find db
    db_path = Path(__file__).parent.parent.parent.parent / "database" / "database" / "cycling_races.db"
    if db_path.exists():
        return str(db_path)
    
    raise FileNotFoundError("Database not found")


def get_percentile_tables(conn: sqlite3.Connection) -> List[int]:
    """Get all available race_features_N tables"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'race_features_%'
        AND name NOT LIKE '%gradients'
        ORDER BY name
    """)
    
    tables = []
    for row in cursor.fetchall():
        table_name = row[0]
        try:
            percentile = int(table_name.split('_')[-1])
            tables.append(percentile)
        except ValueError:
            continue
    
    return sorted(tables)


def find_kurtosis_breakdown_for_competition(conn: sqlite3.Connection, 
                                           competition_id: int,
                                           percentile_tables: List[int]) -> Optional[int]:
    """
    Find the percentile at which kurtosis breaks down (becomes NULL) for a competition.
    Returns the percentile value or None if no breakdown occurs.
    """
    null_percentiles = []
    for percentile in percentile_tables:
        table_name = f"race_features_{percentile}"
        
        query = f"""
        SELECT kurtosis_normalized
        FROM {table_name}
        WHERE competition_id = ?
        """
        
        cursor = conn.cursor()
        cursor.execute(query, (competition_id,))
        result = cursor.fetchone()
        
        if result and result[0] is None:
            # Found the breakdown point
            null_percentiles.append(percentile)
    
    #if len(null_percentiles) > 0:
    if len(null_percentiles) > 0:
        return max(null_percentiles)  # Return the highest percentile with breakdown
    else:
        return None

def get_all_breakdown_points(conn: sqlite3.Connection) -> Dict[int, Optional[int]]:
    """
    Get breakdown points for all stage competitions with winning_time > 90 minutes.
    Returns dict mapping competition_id to breakdown percentile (or None).
    """
    
    # Get list of available percentile tables
    percentile_tables = get_percentile_tables(conn)
    
    # Get all stage competitions with winning_time > 90 minutes
    query = """
    SELECT DISTINCT rf.competition_id
    FROM race_features_100 rf
    WHERE rf.competition_type = 'stage'
    AND rf.winning_time > 5400  -- More than 90 minutes
    AND rf.winning_time <= 28800  -- 8 hours or less (8 * 60 * 60 = 28800 seconds)
    ORDER BY rf.competition_id
    """
    
    cursor = conn.cursor()
    cursor.execute(query)
    competition_ids = [row[0] for row in cursor.fetchall()]
    
    # Find breakdown point for each competition
    breakdown_points = {}
    for comp_id in competition_ids:
        breakdown_point = find_kurtosis_breakdown_for_competition(conn, comp_id, percentile_tables)
        breakdown_points[comp_id] = breakdown_point
    
    return breakdown_points


def summarize_breakdown_distribution(breakdown_points: Dict[int, Optional[int]]) -> Dict:
    """Summarize the distribution of breakdown points"""
    
    # Count competitions with and without breakdowns
    with_breakdown = sum(1 for bp in breakdown_points.values() if bp is not None)
    without_breakdown = sum(1 for bp in breakdown_points.values() if bp is None)
    
    # Distribution of breakdown points
    breakdown_distribution = {}
    for bp in breakdown_points.values():
        if bp is not None:
            breakdown_distribution[bp] = breakdown_distribution.get(bp, 0) + 1
    
    return {
        'total_competitions': len(breakdown_points),
        'with_breakdown': with_breakdown,
        'without_breakdown': without_breakdown,
        'breakdown_percentage': with_breakdown / len(breakdown_points) * 100 if breakdown_points else 0,
        'breakdown_distribution': dict(sorted(breakdown_distribution.items()))
    }


def main():
    """Test the breakdown point detection"""
    db_path = find_database()
    conn = sqlite3.connect(db_path)
    
    print("Finding kurtosis breakdown points for all stage competitions...")
    breakdown_points = get_all_breakdown_points(conn)
    
    summary = summarize_breakdown_distribution(breakdown_points)
    
    print(f"\nSummary:")
    print(f"Total competitions: {summary['total_competitions']}")
    print(f"With breakdown: {summary['with_breakdown']} ({summary['breakdown_percentage']:.1f}%)")
    print(f"Without breakdown: {summary['without_breakdown']}")
    
    if summary['breakdown_distribution']:
        print(f"\nBreakdown distribution:")
        for percentile, count in summary['breakdown_distribution'].items():
            print(f"  At {percentile}%: {count} competitions")
    
    conn.close()


if __name__ == "__main__":
    main()