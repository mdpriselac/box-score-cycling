"""
Example Usage of Race Feature Extraction System

This script demonstrates how to use the race feature extraction modules
to analyze cycling race data.
"""

import pandas as pd
from race_feature_extraction import extract_race_features, extract_features_for_percentile_range
from race_feature_database import (
    get_competition_ids,
    build_feature_database,
    load_features_for_analysis,
    get_feature_summary
)

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def example_single_competition():
    """Example: Extract features for a single competition."""
    print("\n1. SINGLE COMPETITION EXAMPLE")
    print("-" * 40)
    
    # Get a competition from 2024
    comp_ids = get_competition_ids(DB_PATH, year=2024, category='wt', min_finishers=50)
    
    if comp_ids:
        comp_id = comp_ids[0]
        
        # Extract features at 50% percentile
        features = extract_race_features(comp_id, 0.5, DB_PATH)
        
        print(f"Competition: {features['competition_name']}")
        print(f"Type: {features['competition_type']}")
        print(f"Date: {features['race_date']}")
        print(f"Total finishers: {features['total_finishers']}")
        print(f"Analyzed: Top {features['percentile_analyzed']:.0%} ({features['included_finishers']} riders)")
        print(f"\nKey Metrics:")
        print(f"  - Abandon ratio: {features['abandon_ratio']:.2%}")
        print(f"  - Biggest group metric: {features['biggest_group_metric']:.3f}")
        print(f"  - Clumpiness score: {features['clumpiness_score']:.3f}")
        print(f"  - Selection metric: {features['selection_metric']:.3f}")
        print(f"  - Gini coefficient: {features['gini_coefficient']:.3f}")


def example_percentile_analysis():
    """Example: Analyze how features change with percentile cutoff."""
    print("\n2. PERCENTILE ANALYSIS EXAMPLE")
    print("-" * 40)
    
    # Get a mountain stage
    comp_ids = get_competition_ids(DB_PATH, year=2024, competition_type='stage', min_finishers=100)
    
    if comp_ids:
        comp_id = comp_ids[0]
        
        # Extract features across percentiles
        df = extract_features_for_percentile_range(
            comp_id, DB_PATH,
            start_percentile=0.25,
            end_percentile=1.0,
            step=0.25
        )
        
        if not df.empty:
            print(f"Competition: {df.iloc[0]['competition_name']}")
            print("\nHow metrics change with percentile cutoff:")
            print(df[['percentile_analyzed', 'included_finishers', 
                     'biggest_group_metric', 'clumpiness_score', 
                     'selection_metric']].to_string(index=False))


def example_batch_analysis():
    """Example: Analyze multiple competitions."""
    print("\n3. BATCH ANALYSIS EXAMPLE")
    print("-" * 40)
    
    # Build a small feature database for 2024 World Tour one-day races
    print("Building feature database for 2024 WT one-day races...")
    
    # Get one-day race competitions
    comp_ids = get_competition_ids(
        DB_PATH, 
        year=2024, 
        category='wt', 
        competition_type='one_day',
        min_finishers=50
    )[:10]  # Just first 10 for example
    
    if comp_ids:
        # Process at multiple percentiles
        summary = build_feature_database(
            DB_PATH,
            years=[2024],
            percentiles=[0.5],  # Just 50% for speed
            table_name="example_features",
            rebuild=True
        )
        
        print(f"\nProcessed {len(comp_ids)} competitions")
        
        # Load and analyze
        features_df = load_features_for_analysis(
            DB_PATH,
            table_name="example_features",
            percentile=0.5
        )
        
        if not features_df.empty:
            print(f"\nRace characteristics summary:")
            summary_stats = features_df[['biggest_group_metric', 'clumpiness_score', 
                                        'selection_metric', 'time_gap_evenness_metric']].describe()
            print(summary_stats.round(3))


def example_race_type_comparison():
    """Example: Compare different race types."""
    print("\n4. RACE TYPE COMPARISON EXAMPLE")
    print("-" * 40)
    
    race_types = ['one_day', 'stage', 'gc']
    results = []
    
    for race_type in race_types:
        comp_ids = get_competition_ids(
            DB_PATH,
            year=2024,
            competition_type=race_type,
            min_finishers=50
        )[:5]  # Just 5 of each type
        
        for comp_id in comp_ids:
            try:
                features = extract_race_features(comp_id, 0.5, DB_PATH)
                results.append({
                    'type': race_type,
                    'biggest_group': features['biggest_group_metric'],
                    'clumpiness': features['clumpiness_score'],
                    'selection': features['selection_metric']
                })
            except:
                continue
    
    if results:
        df = pd.DataFrame(results)
        print("\nAverage metrics by race type:")
        print(df.groupby('type').mean().round(3))


if __name__ == "__main__":
    print("RACE FEATURE EXTRACTION EXAMPLES")
    print("=" * 40)
    
    # Run examples
    example_single_competition()
    example_percentile_analysis()
    example_race_type_comparison()
    
    print("\n" + "=" * 40)
    print("Examples complete!")
    print("\nNext steps:")
    print("- Use build_feature_database() to process full years")
    print("- Analyze percentile effects on race classification")
    print("- Develop race clustering algorithms")
    print("- Create rider performance profiles based on race types")