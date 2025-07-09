#!/usr/bin/env python3
"""
Analyze rider result distribution for 2019-2024 backtesting with higher volume targets.
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def analyze_rider_distribution_multi_year(db_path: str, test_years: list = [2019, 2020, 2021, 2022, 2023, 2024]):
    """Analyze distribution for multiple test years."""
    
    print("RIDER DISTRIBUTION ANALYSIS FOR MULTIPLE YEARS")
    print("="*80)
    
    results = {}
    
    for year in test_years:
        cutoff_date = f"{year-1}-12-31"
        print(f"\n{'='*60}")
        print(f"ANALYSIS FOR {year} BACKTEST (training up to {cutoff_date})")
        print(f"{'='*60}")
        
        df = analyze_single_year(db_path, cutoff_date, year)
        results[year] = df
        
        # Get optimal thresholds for different target volumes
        print(f"\nOPTIMAL THRESHOLDS FOR {year}:")
        print("-"*50)
        target_volumes = [300000, 500000, 750000, 1000000]
        
        for target in target_volumes:
            optimal = get_optimal_threshold(db_path, cutoff_date, target)
            print(f"  {target:>7,} pairs: min_results = {optimal}")
    
    # Create comparison visualization
    create_multi_year_comparison(results, test_years)
    
    return results

def analyze_single_year(db_path: str, cutoff_date: str, test_year: int):
    """Analyze distribution for a single year."""
    
    conn = sqlite3.connect(db_path)
    
    # Get rider result counts up to cutoff date
    query = """
    SELECT 
        rider_id,
        COUNT(*) as result_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'gc' THEN rr.id END) as gc_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'stage' THEN rr.id END) as stage_count,
        COUNT(DISTINCT CASE WHEN c.competition_type = 'one_day' THEN rr.id END) as one_day_count,
        SUM(CASE WHEN r.category = 'wt' THEN 1 ELSE 0 END) as wt_count,
        MIN(c.date) as first_race,
        MAX(c.date) as last_race
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    JOIN races r ON c.race_id = r.id
    WHERE c.date <= ?
    GROUP BY rider_id
    ORDER BY result_count DESC
    """
    
    df = pd.read_sql_query(query, conn, params=[cutoff_date])
    
    # Calculate years active
    df['years_active'] = (pd.to_datetime(df['last_race']) - pd.to_datetime(df['first_race'])).dt.days / 365.25
    df['races_per_year'] = df['result_count'] / df['years_active'].clip(lower=1)
    
    conn.close()
    
    # Extended threshold analysis for higher volumes
    thresholds = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500]
    
    print(f"Total riders with any results: {len(df):,}")
    print(f"Training data spans: 2010-01-01 to {cutoff_date}")
    print(f"Years of data available: {(pd.to_datetime(cutoff_date) - pd.to_datetime('2010-01-01')).days / 365.25:.1f}")
    
    print("\nResults per rider distribution:")
    print(f"  Mean: {df['result_count'].mean():.1f}")
    print(f"  Median: {df['result_count'].median():.0f}")
    print(f"  75th percentile: {df['result_count'].quantile(0.75):.0f}")
    print(f"  90th percentile: {df['result_count'].quantile(0.90):.0f}")
    print(f"  95th percentile: {df['result_count'].quantile(0.95):.0f}")
    print(f"  99th percentile: {df['result_count'].quantile(0.99):.0f}")
    
    print("\nRiders and data volume by minimum result threshold:")
    print("-"*90)
    print("Min Results | Riders | Total Pairs | Avg Results/Rider | % WT Races | Avg Races/Year")
    print("-"*90)
    
    for threshold in thresholds:
        qualified = df[df['result_count'] >= threshold]
        total_pairs = qualified['result_count'].sum()
        avg_results = qualified['result_count'].mean() if len(qualified) > 0 else 0
        avg_wt_pct = (qualified['wt_count'].sum() / total_pairs * 100) if total_pairs > 0 else 0
        avg_races_per_year = qualified['races_per_year'].mean() if len(qualified) > 0 else 0
        
        print(f"{threshold:>11} | {len(qualified):>6,} | {total_pairs:>11,} | {avg_results:>17.1f} | {avg_wt_pct:>10.1f}% | {avg_races_per_year:>13.1f}")
    
    # Analyze rider quality tiers
    print("\nRider Quality Analysis:")
    print("-"*70)
    
    # Professional tier (lots of WT races)
    pro_tier = df[(df['wt_count'] >= 20) & (df['result_count'] >= 50)]
    print(f"Professional tier (50+ races, 20+ WT): {len(pro_tier):,} riders, {pro_tier['result_count'].sum():,} pairs")
    
    # Semi-professional tier
    semi_pro = df[(df['wt_count'] >= 5) & (df['result_count'] >= 30) & (df['result_count'] < 50)]
    print(f"Semi-pro tier (30-49 races, 5+ WT): {len(semi_pro):,} riders, {semi_pro['result_count'].sum():,} pairs")
    
    # Amateur tier
    amateur = df[(df['result_count'] >= 15) & (df['result_count'] < 30)]
    print(f"Amateur tier (15-29 races): {len(amateur):,} riders, {amateur['result_count'].sum():,} pairs")
    
    return df

def get_optimal_threshold(db_path: str, cutoff_date: str, target_pairs: int = 500000):
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
    for threshold in range(5, 201, 2):
        qualified = df[df['result_count'] >= threshold]
        total_pairs = qualified['result_count'].sum()
        
        if total_pairs <= target_pairs:
            return threshold
    
    return 200

def create_multi_year_comparison(results: dict, test_years: list):
    """Create comparison visualization across years."""
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 15))
    
    # Plot 1: Total available data by year
    years = []
    total_riders = []
    total_pairs = []
    
    for year in test_years:
        if year in results:
            df = results[year]
            years.append(year)
            total_riders.append(len(df))
            total_pairs.append(df['result_count'].sum())
    
    ax1.bar(years, total_pairs, alpha=0.7, color='skyblue', edgecolor='black')
    ax1.set_xlabel('Test Year')
    ax1.set_ylabel('Total Available Training Pairs')
    ax1.set_title('Total Training Data Available by Test Year')
    ax1.ticklabel_format(style='plain', axis='y')
    
    # Add value labels on bars
    for i, (year, pairs) in enumerate(zip(years, total_pairs)):
        ax1.text(year, pairs + max(total_pairs)*0.01, f'{pairs:,}', 
                ha='center', va='bottom', fontweight='bold')
    
    # Plot 2: Riders by threshold comparison
    thresholds = [10, 20, 30, 50, 75, 100, 150, 200]
    
    for year in test_years:
        if year in results:
            df = results[year]
            rider_counts = []
            for threshold in thresholds:
                qualified = df[df['result_count'] >= threshold]
                rider_counts.append(len(qualified))
            
            ax2.plot(thresholds, rider_counts, marker='o', label=f'{year}', linewidth=2)
    
    ax2.set_xlabel('Minimum Results Threshold')
    ax2.set_ylabel('Number of Qualified Riders')
    ax2.set_title('Qualified Riders by Threshold Across Years')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_yscale('log')
    
    # Plot 3: Data volume by threshold
    for year in test_years:
        if year in results:
            df = results[year]
            pair_counts = []
            for threshold in thresholds:
                qualified = df[df['result_count'] >= threshold]
                pair_counts.append(qualified['result_count'].sum())
            
            ax3.plot(thresholds, pair_counts, marker='s', label=f'{year}', linewidth=2)
    
    ax3.set_xlabel('Minimum Results Threshold')
    ax3.set_ylabel('Total Training Pairs')
    ax3.set_title('Training Data Volume by Threshold Across Years')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.ticklabel_format(style='plain', axis='y')
    
    # Plot 4: Recommended thresholds for target volumes
    target_volumes = [300000, 500000, 750000, 1000000]
    
    for target in target_volumes:
        optimal_thresholds = []
        for year in test_years:
            if year in results:
                cutoff_date = f"{year-1}-12-31"
                optimal = get_optimal_threshold("database/database/cycling_races.db", cutoff_date, target)
                optimal_thresholds.append(optimal)
        
        ax4.plot(years, optimal_thresholds, marker='d', label=f'{target:,} pairs', linewidth=2)
    
    ax4.set_xlabel('Test Year')
    ax4.set_ylabel('Recommended Min Results Threshold')
    ax4.set_title('Recommended Thresholds for Target Training Volumes')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('rider_performance/multi_year_rider_analysis.png', dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\nVisualization saved to: rider_performance/multi_year_rider_analysis.png")

def get_recommendations(db_path: str, test_years: list = [2019, 2020, 2021, 2022, 2023, 2024]):
    """Get specific recommendations for the test years."""
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR BACKTEST CONFIGURATION")
    print("="*80)
    
    recommendations = {}
    
    for year in test_years:
        cutoff_date = f"{year-1}-12-31"
        
        # Get thresholds for different target volumes
        targets = {
            'Conservative (300K)': 300000,
            'Moderate (500K)': 500000,
            'Aggressive (750K)': 750000,
            'Maximum (1M)': 1000000
        }
        
        year_recs = {}
        
        for label, target in targets.items():
            threshold = get_optimal_threshold(db_path, cutoff_date, target)
            year_recs[label] = {'threshold': threshold, 'target': target}
        
        recommendations[year] = year_recs
        
        print(f"\n{year} BACKTEST RECOMMENDATIONS:")
        print("-" * 50)
        
        for label, rec in year_recs.items():
            print(f"  {label:20}: min_results = {rec['threshold']:2d} → ~{rec['target']:,} pairs")
    
    # Overall recommendation
    print(f"\n{'='*50}")
    print("OVERALL RECOMMENDATION:")
    print("="*50)
    print("For systematic evaluation across all years:")
    print("  • Conservative: min_results = 20-30 (consistent ~300-500K pairs)")
    print("  • Aggressive:   min_results = 10-15 (consistent ~750K-1M pairs)")
    print("  • Maximum:      min_results = 5-10  (1M+ pairs, longer training)")
    print("\nStart with Conservative for development, then scale up.")
    
    return recommendations

if __name__ == "__main__":
    db_path = "database/database/cycling_races.db"
    test_years = [2019, 2020, 2021, 2022, 2023, 2024]
    
    # Run comprehensive analysis
    results = analyze_rider_distribution_multi_year(db_path, test_years)
    
    # Get specific recommendations
    recommendations = get_recommendations(db_path, test_years)