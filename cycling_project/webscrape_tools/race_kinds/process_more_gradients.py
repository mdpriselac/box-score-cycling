"""
Process more diverse competitions for gradient analysis
"""

import sys
sys.path.append('..')

from process_gradients import enhanced_gradient_calculation, insert_gradient_data, find_database
from gradient_calculator import GradientCalculator
import sqlite3


def get_diverse_competitions(db_path: str, limit: int = 200):
    """Get diverse competitions across categories and sizes"""
    conn = sqlite3.connect(db_path)
    
    query = """
    WITH ranked_competitions AS (
        SELECT 
            rf100.competition_id,
            rf100.race_category,
            rf100.total_finishers,
            rf100.competition_type,
            ROW_NUMBER() OVER (PARTITION BY rf100.race_category ORDER BY rf100.total_finishers DESC) as rank_in_category
        FROM race_features_100 rf100
        LEFT JOIN race_feature_gradients rfg ON rf100.competition_id = rfg.competition_id
        WHERE rfg.competition_id IS NULL  -- Not yet processed
        AND rf100.race_category IN ('wt', 'pro', 'd1', '21', '22', '23')
    )
    SELECT 
        competition_id,
        race_category,
        total_finishers,
        competition_type
    FROM ranked_competitions
    WHERE rank_in_category <= 50  -- Top 50 from each category
    ORDER BY 
        CASE race_category 
            WHEN 'wt' THEN 1 
            WHEN 'pro' THEN 2
            WHEN 'd1' THEN 3
            WHEN '21' THEN 4
            WHEN '22' THEN 5
            WHEN '23' THEN 6
        END,
        total_finishers DESC
    LIMIT ?
    """
    
    cursor = conn.execute(query, (limit,))
    competitions = cursor.fetchall()
    conn.close()
    
    return competitions


def main():
    """Process diverse competitions"""
    db_path = find_database()
    print(f"Using database: {db_path}")
    
    calculator = GradientCalculator(db_path)
    
    # Get diverse competitions
    print("Getting diverse competitions...")
    competitions = get_diverse_competitions(db_path, limit=200)
    print(f"Found {len(competitions)} unprocessed competitions")
    
    # Show distribution
    by_category = {}
    for comp_id, cat, finishers, comp_type in competitions:
        if cat not in by_category:
            by_category[cat] = 0
        by_category[cat] += 1
    
    print("\nDistribution by category:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count} competitions")
    
    # Process competitions
    print("\nProcessing competitions...")
    success_count = 0
    errors = []
    
    for i, (comp_id, cat, finishers, comp_type) in enumerate(competitions):
        try:
            if i % 10 == 0:
                print(f"Progress: {i}/{len(competitions)} ({i/len(competitions)*100:.1f}%)")
            
            gradient_data = enhanced_gradient_calculation(calculator, comp_id)
            
            if gradient_data:
                insert_gradient_data(db_path, gradient_data)
                success_count += 1
            else:
                errors.append((comp_id, "Insufficient data"))
                
        except Exception as e:
            errors.append((comp_id, str(e)))
    
    print(f"\nProcessed {success_count}/{len(competitions)} competitions successfully")
    
    if errors:
        print(f"\nErrors encountered: {len(errors)}")
        print("Sample errors:")
        for comp_id, error in errors[:5]:
            print(f"  Competition {comp_id}: {error}")
    
    # Show updated summary
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("""
        SELECT 
            race_category,
            COUNT(*) as count,
            AVG(percentile_coverage_ratio) as avg_coverage
        FROM race_feature_gradients
        GROUP BY race_category
        ORDER BY count DESC
    """)
    
    print("\nUpdated gradient table summary by category:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} competitions (avg coverage: {row[2]:.1%})")
    
    conn.close()


if __name__ == "__main__":
    main()