#!/usr/bin/env python3
"""
Quick test script to see what rider results come out of the race type specific queries.
Tests the same logic used in the enhanced parallel generator.
"""

import sqlite3
from pathlib import Path

def test_race_type_queries():
    """Test the race type specific queries with sample data."""
    
    db_path = "database/database/cycling_races.db"
    
    # Same config as the pipeline example
    race_type_configs = {
        'gc': {
            'competition_types': ['gc'],
            'min_races': 20
        },
        'stage': {
            'competition_types': ['stage'],
            'min_races': 100
        },
        'one_day': {
            'competition_types': ['one_day'],
            'min_races': 30
        },
        'stage_one_day': {
            'competition_types': ['stage', 'one_day'],
            'min_races': 30
        },
        'all': {
            'competition_types': ['gc', 'stage', 'one_day'],
            'min_races': 150
        }
    }
    
    print("Testing race type specific queries...")
    print("=" * 60)
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        for race_type, config in race_type_configs.items():
            print(f"\n{race_type.upper()} RACE TYPE:")
            print(f"  Competition types: {config['competition_types']}")
            print(f"  Minimum prior races: {config['min_races']}")
            
            competition_types = config['competition_types']
            min_races = config['min_races']
            
            # Build the competition type filter
            if len(competition_types) == 1:
                type_filter = f"= '{competition_types[0]}'"
            else:
                type_list = "', '".join(competition_types)
                type_filter = f"IN ('{type_list}')"
            
            # Optimized query using window functions instead of correlated subqueries
            query = f"""
            WITH race_type_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    rr.rider_id,
                    c.date as competition_date,
                    c.competition_type,
                    c.name as competition_name,
                    -- Use window function to count prior races - much faster
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.rider_id 
                        ORDER BY c.date
                    ) - 1 as prior_races_of_type
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date <= '2025-01-01'
                AND c.competition_type {type_filter}
                ORDER BY rr.rider_id, c.date
            )
            SELECT 
                rider_result_id, 
                rider_id,
                competition_date,
                competition_type,
                competition_name,
                prior_races_of_type
            FROM race_type_results
            WHERE prior_races_of_type >= ?
            ORDER BY rider_result_id
            LIMIT 50
            """
            
            cursor.execute(query, (min_races,))
            results = cursor.fetchall()
            
            print(f"  Found {len(results)} eligible results (showing first 50)")
            
            if results:
                print("  Sample results:")
                for i, row in enumerate(results[:10]):  # Show first 10
                    print(f"    {i+1:2d}. Rider {row['rider_id']:6d} | Result {row['rider_result_id']:8d} | "
                          f"{row['competition_date']} | {row['competition_type']:8s} | "
                          f"Prior: {row['prior_races_of_type']:3d} | {row['competition_name'][:40]}")
                
                if len(results) > 10:
                    print(f"    ... and {len(results) - 10} more")
                
                # Get total count for this race type using optimized query
                count_query = f"""
                WITH race_type_results AS (
                    SELECT 
                        rr.id as rider_result_id,
                        ROW_NUMBER() OVER (
                            PARTITION BY rr.rider_id 
                            ORDER BY c.date
                        ) - 1 as prior_races_of_type
                    FROM rider_results rr
                    JOIN competitions c ON rr.competition_id = c.id
                    WHERE c.date <= '2025-01-01'
                    AND c.competition_type {type_filter}
                )
                SELECT COUNT(*) as total_eligible
                FROM race_type_results
                WHERE prior_races_of_type >= ?
                """
                
                cursor.execute(count_query, (min_races,))
                total_count = cursor.fetchone()['total_eligible']
                print(f"  Total eligible results for {race_type}: {total_count:,}")
            else:
                print("  No eligible results found!")
    
    print("\n" + "=" * 60)
    print("Test complete!")

if __name__ == "__main__":
    test_race_type_queries()