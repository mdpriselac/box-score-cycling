import json
from pathlib import Path
import sys

# Add to path for imports
sys.path.append(str(Path(__file__).parent))

def test_cluster_fix():
    """Test the fixed cluster characteristics generation."""
    
    # Load existing correlation data
    multi_rider_file = "test_multi_rider_correlations.json"
    if not Path(multi_rider_file).exists():
        print(f"Multi-rider correlation file {multi_rider_file} not found")
        print("Run test_enhanced_reporting_multi_riders.py first")
        return
    
    with open(multi_rider_file, 'r') as f:
        race_type_results = json.load(f)
    
    print(f"Loaded {len(race_type_results)} riders")
    
    # Test with GC race type
    from rider_embeddings.race_type_pipeline_adapter import RaceTypeCorrelationAdapter
    
    adapter = RaceTypeCorrelationAdapter()
    
    print("\nRunning fixed GC analysis...")
    try:
        gc_results = adapter.run_pipeline_for_race_type(
            race_type_results,
            'gc',
            max_features=20,
            k_range=[2, 3, 4, 5]
        )
        
        if 'error' in gc_results:
            print(f"Error: {gc_results['error']}")
            return
        
        # Check clustering analysis
        clustering = gc_results.get('clustering_analysis', {})
        if 'cluster_characteristics' in clustering:
            cluster_chars = clustering['cluster_characteristics']
            best_percentile = gc_results['recommendations']['summary']['recommended_percentile']
            
            print(f"Best percentile: {best_percentile}")
            
            if best_percentile in cluster_chars:
                percentile_data = cluster_chars[best_percentile]
                if 'cluster_characteristics' in percentile_data:
                    clusters = percentile_data['cluster_characteristics']
                    print(f"Found {len(clusters)} clusters: {list(clusters.keys())}")
                    
                    for cluster_id, cluster_data in clusters.items():
                        print(f"  Cluster {cluster_id}: {cluster_data['size']} riders")
                else:
                    print("No cluster_characteristics in percentile data")
            else:
                print(f"No cluster data for {best_percentile}")
                print(f"Available: {list(cluster_chars.keys())}")
        
        # Generate report
        from rider_embeddings.feature_selection import FeatureSelectionPipeline
        pipeline = FeatureSelectionPipeline()
        
        print("\nGenerating report...")
        report = pipeline.generate_report(gc_results)
        
        # Extract cluster profiles section
        lines = report.split('\n')
        in_profiles = False
        profile_lines = []
        
        for line in lines:
            if "🏷️  CLUSTER PROFILES:" in line:
                in_profiles = True
                profile_lines.append(line)
            elif in_profiles:
                if line.strip() and ("COMPARISON WITH OTHER PERCENTILES" in line or 
                                   "FEATURE SELECTION" in line):
                    break
                profile_lines.append(line)
        
        if profile_lines:
            print("\n" + "="*50)
            print("CLUSTER PROFILES SECTION:")
            print("="*50)
            for line in profile_lines:
                print(line)
        else:
            print("No cluster profiles found")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cluster_fix()