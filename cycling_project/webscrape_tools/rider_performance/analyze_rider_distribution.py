#!/usr/bin/env python3
"""
Analyze rider result distribution to determine optimal min_results threshold.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt

def analyze_rider_distribution(db_path: str, cutoff_date: str):
    """Analyze distribution of results per rider."""
    
    conn = sqlite3.connect(db_path)
    
    # Get rider result counts up to cutoff date
    query = """
    SELECT 
        rider_id,
        COUNT(*) as result_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'gc' THEN rr.id END) as gc_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'stage' THEN rr.id END) as stage_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'one_day' THEN rr.id END) as one_day_count,
        SUM(CASE WHEN r.category = 'wt' THEN 1 ELSE 0 END) as wt_count
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    WHERE c.date <= ?
    GROUP BY rider_id
    ORDER BY result_count DESC
    """
    
    df = pd.read_sql_query(query, conn, params=[cutoff_date])
    conn.close()
    
    # Calculate cumulative statistics
    thresholds = [10, 20, 30, 40, 50, 75, 100, 150, 200, 250, 300, 400, 500]

    print(f"Rider Distribution Analysis (up to {cutoff_date})")
    print("="*70)
    print(f"Total riders with any results: {len(df):,}")
    print("\nResults per rider distribution:")
    print(f"  Mean: {df['result_count'].mean():.1f}")
    print(f"  Median: {df['result_count'].median():.0f}")
    print(f"  75th percentile: {df['result_count'].quantile(0.75):.0f}")
    print(f"  90th percentile: {df['result_count'].quantile(0.90):.0f}")
    
    print("\nRiders and data volume by minimum result threshold:")
    print("-"*70)
    print("Min Results | Riders | Total Pairs | Avg Results/Rider | % WT Races")
    print("-"*70)
    
    for threshold in thresholds:
        qualified = df[df['result_count'] >= threshold]
        total_pairs = qualified['result_count'].sum()
        avg_results = qualified['result_count'].mean() if len(qualified) > 0 else 0
        avg_wt_pct = (qualified['wt_count'].sum() / total_pairs * 100) if total_pairs > 0 else 0
        
        print(f"{threshold:>11} | {len(qualified):>6,} | {total_pairs:>11,} | {avg_results:>17.1f} | {avg_wt_pct:>10.1f}%")
    
    # Analyze rider quality
    print("\nTop riders by result count:")
    print("-"*70)
    top_riders = df.head(20)
    for _, rider in top_riders.iterrows():
        wt_pct = (rider['wt_count'] / rider['result_count'] * 100) if rider['result_count'] > 0 else 0
        print(f"Rider {rider['rider_id']:>6}: {rider['result_count']:>4} results "
              f"(GC:{rider['gc_count']:>3}, Stage:{rider['stage_count']:>4}, 1-Day:{rider['one_day_count']:>3}) "
              f"WT:{wt_pct:>4.0f}%")
    
    # Create visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Histogram of results per rider
    ax1.hist(df['result_count'], bins=50, range=(0, 200), alpha=0.7, edgecolor='black')
    ax1.set_xlabel('Number of Results')
    ax1.set_ylabel('Number of Riders')
    ax1.set_title('Distribution of Results per Rider')
    ax1.axvline(x=30, color='red', linestyle='--', label='30 results')
    ax1.axvline(x=50, color='orange', linestyle='--', label='50 results')
    ax1.legend()
    
    # Cumulative riders and data volume
    sorted_riders = df.sort_values('result_count', ascending=False)
    cumulative_riders = range(1, len(sorted_riders) + 1)
    cumulative_results = sorted_riders['result_count'].cumsum()
    
    ax2.plot(cumulative_riders, cumulative_results, 'b-', linewidth=2)
    ax2.set_xlabel('Number of Riders (sorted by result count)')
    ax2.set_ylabel('Cumulative Number of Results')
    ax2.set_title('Cumulative Data Volume by Top Riders')
    ax2.grid(True, alpha=0.3)
    
    # Mark key thresholds
    for threshold in [30, 50, 100]:
        n_riders = len(df[df['result_count'] >= threshold])
        if n_riders > 0:
            cum_results = df[df['result_count'] >= threshold]['result_count'].sum()
            ax2.plot(n_riders, cum_results, 'ro', markersize=8)
            ax2.annotate(f'{threshold}+ results\n({n_riders:,} riders)', 
                        xy=(n_riders, cum_results), 
                        xytext=(n_riders+100, cum_results),
                        arrowprops=dict(arrowstyle='->', color='red'))
    
    plt.tight_layout()
    plt.savefig('rider_performance/rider_distribution_analysis.png', dpi=150)
    plt.close()
    
    return df

def get_optimal_threshold(db_path: str, cutoff_date: str, target_pairs: int = 300000):
    """Find threshold that gives approximately target number of pairs."""
    
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        rider_id,
        COUNT(*) as result_count
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    WHERE c.date <= ?
    GROUP BY rider_id
    """
    
    df = pd.read_sql_query(query, conn, params=[cutoff_date])
    conn.close()
    
    # Test different thresholds
    for threshold in range(10, 101, 5):
        qualified = df[df['result_count'] >= threshold]
        total_pairs = qualified['result_count'].sum()
        
        if total_pairs <= target_pairs:
            print(f"\nOptimal threshold for ~{target_pairs:,} pairs: {threshold} minimum results")
            print(f"This gives {len(qualified):,} riders with {total_pairs:,} total pairs")
            return threshold
    
    return 100

if __name__ == "__main__":
    db_path = "database/database/cycling_races.db"
    
    # Analyze for 2010 data (what 2011 model would train on)
    print("Analyzing rider distribution for 2022 training data...")
    df_2010 = analyze_rider_distribution(db_path, "2021-12-31")
    
    # Find optimal threshold
    optimal = get_optimal_threshold(db_path, "2021-12-31", target_pairs=300000)
    
    print(f"\nRECOMMENDATION:")
    print(f"Use min_results={optimal} for faster training while keeping quality riders")