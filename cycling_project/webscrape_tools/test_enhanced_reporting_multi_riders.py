import json
from pathlib import Path
import sys
import sqlite3

# Add to path for imports
sys.path.append(str(Path(__file__).parent))
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator
from rider_embeddings.race_type_pipeline_adapter import RaceTypeCorrelationAdapter


def get_multiple_test_riders(db_path: str, count: int = 20):
    """Get multiple rider results for testing clustering."""
    query = """
    SELECT rr.id, c.date, r.name as rider_name
    FROM rider_results rr
    JOIN competitions c ON rr.competition_id = c.id
    JOIN riders r ON rr.rider_id = r.id
    WHERE c.date > '2020-01-01'
    AND EXISTS (
        SELECT 1 FROM rider_results rr2
        JOIN competitions c2 ON rr2.competition_id = c2.id
        WHERE rr2.rider_id = rr.rider_id
        AND c2.date < c.date
        GROUP BY rr2.rider_id
        HAVING COUNT(*) > 50
    )
    ORDER BY RANDOM()
    LIMIT ?
    """
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, (count,))
        return [dict(row) for row in cursor.fetchall()]


def test_enhanced_reporting_with_multiple_riders():
    """Test enhanced reporting with enough riders for clustering."""
    
    print("Testing enhanced reporting with multiple riders for clustering...")
    
    db_path = "database/database/cycling_races.db"
    
    # Get multiple test riders
    print("Getting test riders...")
    test_riders = get_multiple_test_riders(db_path, count=25)
    
    if len(test_riders) < 10:
        print(f"Only found {len(test_riders)} suitable riders, need at least 10 for clustering")
        return
    
    print(f"Found {len(test_riders)} suitable riders")
    
    # Generate correlations for all riders
    print("Generating correlations...")
    calculator = RaceTypeCorrelationCalculator(
        db_path,
        min_races_gc=8,  # Lower thresholds to get more data
        min_races_stage=15,
        min_races_one_day=10,
        min_races_all=25
    )
    
    race_type_results = []
    successful_riders = []
    
    for i, rider_info in enumerate(test_riders):
        print(f"  Processing rider {i+1}/{len(test_riders)}: {rider_info['rider_name']}")
        
        try:
            result = calculator.calculate_feature_relationships(
                rider_result_id=rider_info['id'],
                lookback_date=rider_info['date'],
                feature_tables=['race_features_70', 'race_features_80', 'race_features_90']
            )
            
            # Check if we got valid correlations for at least one race type
            has_valid_data = False
            for race_type, correlations in result['feature_correlations'].items():
                if correlations and result['metadata']['n_races'][race_type] > 0:
                    has_valid_data = True
                    break
            
            if has_valid_data:
                race_type_results.append(result)
                successful_riders.append(rider_info['rider_name'])
            
        except Exception as e:
            print(f"    Error processing rider {rider_info['rider_name']}: {e}")
    
    print(f"\nSuccessfully processed {len(race_type_results)} riders")
    print(f"Riders with data: {', '.join(successful_riders[:5])}{'...' if len(successful_riders) > 5 else ''}")
    
    if len(race_type_results) < 10:
        print("Not enough riders with valid data for clustering analysis")
        return
    
    # Save the multi-rider data
    output_file = "test_multi_rider_correlations.json"
    with open(output_file, 'w') as f:
        json.dump(race_type_results, f, indent=2, default=str)
    print(f"Saved correlation data to {output_file}")
    
    # Test the adapter with enhanced reporting
    print("\nRunning analysis with enhanced reporting...")
    adapter = RaceTypeCorrelationAdapter()
    
    # Try different race types to see which has the best clustering
    race_types_to_test = ['gc', 'stage_one_day', 'all']
    
    for race_type in race_types_to_test:
        print(f"\n{'='*60}")
        print(f"Testing {race_type.upper()} analysis")
        print(f"{'='*60}")
        
        try:
            results = adapter.run_pipeline_for_race_type(
                race_type_results,
                race_type,
                max_features=20,
                k_range=[2, 3, 4, 5]  # Smaller range for testing
            )
            
            if 'error' in results:
                print(f"Error in {race_type} analysis: {results['error']}")
                continue
            
            # Generate report
            from rider_embeddings.feature_selection import FeatureSelectionPipeline
            pipeline = FeatureSelectionPipeline()
            
            report = pipeline.generate_report(results)
            
            # Save the report
            report_file = f"test_enhanced_report_{race_type}.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            
            print(f"Enhanced report saved to: {report_file}")
            
            # Show cluster profiles if they exist
            lines = report.split('\n')
            in_cluster_section = False
            cluster_lines = []
            
            for line in lines:
                if "🏷️  CLUSTER PROFILES:" in line:
                    in_cluster_section = True
                    cluster_lines.append(line)
                elif in_cluster_section and line.strip() == "":
                    # Continue until we hit a major section break
                    if cluster_lines and any("=" in l for l in cluster_lines[-3:]):
                        break
                    cluster_lines.append(line)
                elif in_cluster_section:
                    cluster_lines.append(line)
                    # Stop if we hit the next major section
                    if "COMPARISON WITH OTHER PERCENTILES:" in line:
                        break
            
            if cluster_lines and len(cluster_lines) > 1:
                print(f"\n🏷️  CLUSTER PROFILES for {race_type.upper()}:")
                print("-" * 40)
                for line in cluster_lines[1:]:  # Skip the header
                    if line.strip():
                        print(line)
                break  # Stop after first successful analysis
            else:
                print(f"No cluster profiles found for {race_type}")
                
        except Exception as e:
            print(f"Error analyzing {race_type}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\nTest completed!")


if __name__ == "__main__":
    test_enhanced_reporting_with_multiple_riders()