import json
from pathlib import Path
import sys

# Add to path for imports
sys.path.append(str(Path(__file__).parent))
from rider_embeddings.feature_selection import FeatureSelectionPipeline

def debug_existing_results():
    """Debug existing analysis results to see cluster data."""
    
    # Look for existing analysis files
    analysis_dir = Path("race_type_analysis")
    if not analysis_dir.exists():
        print("No race_type_analysis directory found")
        return
    
    analysis_files = list(analysis_dir.glob("*_analysis_results.json"))
    if not analysis_files:
        print("No analysis result files found")
        return
    
    for analysis_file in analysis_files:
        print(f"\n{'='*50}")
        print(f"Checking: {analysis_file.name}")
        print(f"{'='*50}")
        
        with open(analysis_file, 'r') as f:
            results = json.load(f)
        
        # Check if this has cluster data
        if 'clustering_analysis' not in results:
            print("No clustering analysis")
            continue
            
        clustering = results['clustering_analysis']
        if 'cluster_characteristics' not in clustering:
            print("No cluster characteristics")
            continue
        
        cluster_chars = clustering['cluster_characteristics']
        best_percentile = results.get('recommendations', {}).get('summary', {}).get('recommended_percentile')
        
        print(f"Best percentile: {best_percentile}")
        print(f"Available percentiles: {list(cluster_chars.keys())}")
        
        if best_percentile and best_percentile in cluster_chars:
            percentile_data = cluster_chars[best_percentile]
            print(f"Percentile data keys: {list(percentile_data.keys())}")
            
            if 'cluster_characteristics' in percentile_data:
                clusters = percentile_data['cluster_characteristics']
                print(f"Found {len(clusters)} clusters: {list(clusters.keys())}")
                
                for cluster_id, cluster_data in clusters.items():
                    print(f"  Cluster {cluster_id}: {cluster_data['size']} riders")
                
                # Try generating report with debug output
                print("\nGenerating report with debug...")
                pipeline = FeatureSelectionPipeline()
                report = pipeline.generate_report(results)
                
                # Look for cluster profiles in the report
                lines = report.split('\n')
                in_profiles = False
                profile_lines = []
                
                for line in lines:
                    if "🏷️  CLUSTER PROFILES:" in line:
                        in_profiles = True
                        profile_lines.append(line)
                    elif in_profiles:
                        if line.strip() and not line.startswith("   "):
                            break  # End of cluster section
                        profile_lines.append(line)
                
                if profile_lines:
                    print("\nCluster profiles from report:")
                    for line in profile_lines:
                        print(line)
                else:
                    print("No cluster profiles found in report")
                
                break  # Process only first valid file
        else:
            print(f"No data for best percentile {best_percentile}")

if __name__ == "__main__":
    debug_existing_results()