#!/usr/bin/env python3
"""
Quick test script to run backtest for 2022.
Trains on all data up to 2021-12-31, tests on 2022.
"""

from temporal_backtest import TemporalBacktester

if __name__ == "__main__":
    # Database path
    db_path = "database/database/cycling_races.db"
    
    # Initialize backtester
    print("Initializing backtester...")
    backtester = TemporalBacktester(db_path)
    
    # Run for 2022 with actual UCI points
    print("\nRunning backtest for 2022 with ACTUAL UCI points...")
    results_actual = backtester.run_temporal_backtest(
        test_year=2022,
        min_results=100,  # Increased for faster training - only established riders
        target_variable='uci_points_actual',
        num_boost_round=100,  # Fewer rounds for quick test
        early_stopping_rounds=10,
        save_models=True,
        verbose=True,
        use_optimized_generator=True  # Use optimized generator for speed
    )
    
    # Optional: Also test proportional points
    print("\n" + "="*80)
    print("Running backtest for 2022 with PROPORTIONAL UCI points...")
    results_prop = backtester.run_temporal_backtest(
        test_year=2022,
        min_results=100,  # Match the actual points test
        target_variable='uci_points_proportional',
        num_boost_round=100,  # Fewer rounds for quick test
        early_stopping_rounds=10,
        save_models=True,
        verbose=True,
        use_optimized_generator=True  # Use optimized generator for speed
    )
    
    print("\n" + "="*80)
    print("QUICK COMPARISON")
    print("="*80)
    
    # Compare key metrics
    for model_type in ['gc', 'stage_one_day']:
        if model_type in results_actual['metrics'] and model_type in results_prop['metrics']:
            actual = results_actual['metrics'][model_type]
            prop = results_prop['metrics'][model_type]
            
            print(f"\n{model_type.upper()}:")
            print(f"  Zero inflation - Actual: {actual['zero_percentage']:.1f}%, Proportional: {prop['zero_percentage']:.1f}%")
            print(f"  Spearman - Actual: {actual['spearman_overall']:.4f}, Proportional: {prop['spearman_overall']:.4f}")
            print(f"  Top-10 - Actual: {actual['top_10_accuracy']:.4f}, Proportional: {prop['top_10_accuracy']:.4f}")