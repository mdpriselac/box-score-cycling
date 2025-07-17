"""
Check which competitions are missing from race_features tables
"""
import sqlite3
import logging

def check_missing_competitions(db_path: str):
    """Check which competitions from rider_results are missing from race_features tables"""
    
    with sqlite3.connect(db_path) as conn:
        # Get all unique competition IDs from rider_results
        rider_results_comps = conn.execute("""
            SELECT DISTINCT competition_id 
            FROM rider_results 
            WHERE competition_id IS NOT NULL
            ORDER BY competition_id
        """).fetchall()
        
        # Get all unique competition IDs from race_features_30 (representative table)
        race_features_comps = conn.execute("""
            SELECT DISTINCT competition_id 
            FROM race_features_30 
            WHERE competition_id IS NOT NULL
            ORDER BY competition_id
        """).fetchall()
        
        rider_comp_set = set(r[0] for r in rider_results_comps)
        features_comp_set = set(r[0] for r in race_features_comps)
        
        # Find missing competitions
        missing_comps = rider_comp_set - features_comp_set
        
        print(f"Total competitions in rider_results: {len(rider_comp_set)}")
        print(f"Total competitions in race_features: {len(features_comp_set)}")
        print(f"Missing competitions: {len(missing_comps)}")
        
        if missing_comps:
            print("\nMissing competition IDs:")
            for comp_id in sorted(missing_comps)[:20]:  # Show first 20
                # Get more info about the missing competition
                info = conn.execute("""
                    SELECT c.id, c.name, c.date, c.competition_type, COUNT(rr.id) as result_count
                    FROM competitions c
                    LEFT JOIN rider_results rr ON c.id = rr.competition_id
                    WHERE c.id = ?
                    GROUP BY c.id
                """, (comp_id,)).fetchone()
                
                if info:
                    print(f"  {info[0]}: {info[1]} ({info[2]}) - {info[3]} - {info[4]} results")
                else:
                    print(f"  {comp_id}: No competition info found")
            
            if len(missing_comps) > 20:
                print(f"  ... and {len(missing_comps) - 20} more")
                
        # Check specific problematic competitions
        problematic_ids = [8991, 9048, 8964, 9588]
        print(f"\nChecking specific problematic competitions: {problematic_ids}")
        for comp_id in problematic_ids:
            exists_in_results = conn.execute(
                "SELECT COUNT(*) FROM rider_results WHERE competition_id = ?", 
                (comp_id,)
            ).fetchone()[0]
            exists_in_features = conn.execute(
                "SELECT COUNT(*) FROM race_features_30 WHERE competition_id = ?", 
                (comp_id,)
            ).fetchone()[0]
            print(f"  Competition {comp_id}: {exists_in_results} results, {exists_in_features} in features")

if __name__ == "__main__":
    check_missing_competitions("../database/database/cycling_races.db")