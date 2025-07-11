import json
import sys
from pathlib import Path

def view_results(file_path="test_race_type_correlation_output.json"):
    """View correlation results in a more readable format."""
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    print("=" * 80)
    print("RACE TYPE CORRELATION RESULTS")
    print("=" * 80)
    
    # Rider info
    if 'rider_info' in data:
        print(f"\nRider: {data['rider_info']['rider_name']} (ID: {data['rider_info']['rider_id']})")
        print(f"Competition Date: {data['rider_info']['competition_date']}")
    
    print(f"\nRider Result ID: {data['rider_result_id']}")
    print(f"Calculation Method: {data['metadata']['method']}")
    print(f"Calculation Date: {data['metadata']['calculation_date']}")
    
    # Race counts
    print("\nRACE COUNTS BY TYPE:")
    for race_type, count in data['metadata']['n_races'].items():
        print(f"  {race_type:15} : {count:3d} races")
    
    # Warnings
    if data['metadata']['warnings']:
        print("\nWARNINGS:")
        for warning in data['metadata']['warnings']:
            print(f"  - {warning}")
    
    # Correlation details
    print("\n" + "=" * 80)
    print("CORRELATION DETAILS BY RACE TYPE")
    print("=" * 80)
    
    for race_type, race_correlations in data['feature_correlations'].items():
        print(f"\n{'='*40}")
        print(f"RACE TYPE: {race_type.upper()}")
        print(f"{'='*40}")
        
        for percentile, features in race_correlations.items():
            print(f"\n{percentile}:")
            
            # Count valid correlations
            valid_corrs = [(k, v) for k, v in features.items() if v is not None]
            print(f"  Total features: {len(features)}")
            print(f"  Valid correlations: {len(valid_corrs)}")
            
            if valid_corrs:
                # Sort by absolute value
                sorted_by_abs = sorted(valid_corrs, key=lambda x: abs(x[1]), reverse=True)
                
                print(f"\n  STRONGEST CORRELATIONS (by absolute value):")
                for i, (feat, corr) in enumerate(sorted_by_abs[:10]):
                    print(f"    {i+1:2d}. {feat:30} : {corr:7.4f}")
                
                # Show distribution
                positive = sum(1 for _, v in valid_corrs if v > 0)
                negative = sum(1 for _, v in valid_corrs if v < 0)
                print(f"\n  CORRELATION DISTRIBUTION:")
                print(f"    Positive correlations: {positive}")
                print(f"    Negative correlations: {negative}")
                
                # Correlation strength breakdown
                very_strong = sum(1 for _, v in valid_corrs if abs(v) > 0.7)
                strong = sum(1 for _, v in valid_corrs if 0.5 < abs(v) <= 0.7)
                moderate = sum(1 for _, v in valid_corrs if 0.3 < abs(v) <= 0.5)
                weak = sum(1 for _, v in valid_corrs if abs(v) <= 0.3)
                
                print(f"\n  CORRELATION STRENGTH:")
                print(f"    Very Strong (|r| > 0.7): {very_strong}")
                print(f"    Strong (0.5 < |r| <= 0.7): {strong}")
                print(f"    Moderate (0.3 < |r| <= 0.5): {moderate}")
                print(f"    Weak (|r| <= 0.3): {weak}")

    print("\n" + "=" * 80)
    print("END OF REPORT")
    print("=" * 80)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        view_results(sys.argv[1])
    else:
        view_results()