"""
Generalized script to create race kind features using configurable models for different competition types.

This script allows you to specify different model paths for each race type (one_day, stage, gc)
and creates race kind features based on the competition type. It also exports key table information
for the rider performance system.
"""

import os
import sys
import json
import argparse
import sqlite3
import pandas as pd
from datetime import datetime
from typing import Dict, Optional
from race_kind_models import RaceKindModelManager

# Database path
DB_PATH = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"


def create_race_kind_features(
    one_day_model_path: str,
    stage_model_path: str,
    gc_model_path: str,
    output_table: str = "race_kind_features_unified",
    export_path: Optional[str] = None
):
    """
    Create race kind features for different competition types using specified models.
    
    Args:
        one_day_model_path: Path to model for one-day races
        stage_model_path: Path to model for stage races  
        gc_model_path: Path to model for GC races
        output_table: Name of the output table
        export_path: Optional path to export key table information
    """
    
    model_manager = RaceKindModelManager(DB_PATH)
    
    # Validate model paths
    model_paths = {
        'one_day': one_day_model_path,
        'stage': stage_model_path,
        'gc': gc_model_path
    }
    
    for comp_type, model_path in model_paths.items():
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found for {comp_type}: {model_path}")
    
    # Load model metadata to get feature columns and determine table structure
    print("Loading model metadata...")
    model_configs = {}
    all_feature_columns = set()
    max_clusters_needed = 0
    
    for comp_type, model_path in model_paths.items():
        model_data = model_manager.load_model(model_path)
        source_table = f"race_features_{model_data['percentile']}"
        
        # Determine number of clusters from the model
        model = model_data['model']
        if hasattr(model, 'n_clusters'):
            n_clusters = model.n_clusters
        elif hasattr(model, 'cluster_centers_'):
            n_clusters = len(model.cluster_centers_)
        else:
            # Fallback: assume 4 clusters if we can't determine
            n_clusters = 4
            print(f"  Warning: Could not determine cluster count for {comp_type}, using default of 4")
        
        max_clusters_needed = max(max_clusters_needed, n_clusters)
        
        model_configs[comp_type] = {
            'model_path': model_path,
            'source_table': source_table,
            'algorithm': model_data['algorithm'],
            'percentile': model_data['percentile'],
            'feature_columns': model_data['feature_columns'],
            'n_clusters': n_clusters
        }
        
        all_feature_columns.update(model_data['feature_columns'])
        
        print(f"  {comp_type}: {model_data['algorithm']} {model_data['percentile']}th percentile -> {source_table} ({n_clusters} clusters)")
    
    print(f"\nDynamically determined max_clusters: {max_clusters_needed}")
    
    # Create unified race kind features table
    print(f"\nCreating unified race kind features table: {output_table}")
    
    # Use the first model's info as template (we'll store individual model info in metadata)
    template_config = list(model_configs.values())[0]
    
    model_manager.create_race_kind_features_table(
        table_name=output_table,
        algorithm=template_config['algorithm'],
        percentile=template_config['percentile'],
        feature_columns=list(all_feature_columns),
        max_clusters=max_clusters_needed,
        metadata={
            'description': f'Unified race kind features using configurable models for different competition types',
            'model_configurations': {
                comp_type: {
                    'model_path': config['model_path'],
                    'source_table': config['source_table'],
                    'algorithm': config['algorithm'],
                    'percentile': config['percentile'],
                    'n_clusters': config['n_clusters']
                }
                for comp_type, config in model_configs.items()
            },
            'all_feature_columns': list(all_feature_columns),
            'max_clusters': max_clusters_needed
        }
    )
    
    # Process each competition type with its specified model
    total_races_processed = 0
    
    for comp_type, config in model_configs.items():
        print(f"\nProcessing {comp_type} races with {config['algorithm']} {config['percentile']}th percentile model...")
        
        try:
            n_races = model_manager.predict_and_store_new_races(
                model_path=config['model_path'],
                source_table=config['source_table'],
                target_table=output_table,
                competition_type=comp_type,
                max_clusters=max_clusters_needed
            )
            print(f"Successfully processed {n_races} {comp_type} races")
            total_races_processed += n_races
        except Exception as e:
            print(f"Error processing {comp_type} races: {e}")
            raise
    
    print(f"\n✅ Race kind features created in table: {output_table}")
    print(f"Total races processed: {total_races_processed}")
    
    # Export key table information if requested
    if export_path:
        export_key_table_info(output_table, export_path, model_configs, max_clusters_needed)
    
    # Show a sample of the results
    show_sample_results(output_table)

def export_key_table_info(table_name: str, export_path: str, model_configs: Dict, max_clusters: int):
    """
    Export key table information for the rider performance system.
    
    Args:
        table_name: Name of the race kind features table
        export_path: Path to export the information
        model_configs: Dictionary of model configurations
        max_clusters: Maximum number of clusters determined from models
    """
    print(f"\nExporting key table information to: {export_path}")
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get table schema
    schema_query = f"PRAGMA table_info({table_name})"
    schema_df = pd.read_sql_query(schema_query, conn)
    
    # Get sample data
    sample_query = f"""
    SELECT * FROM {table_name}
    LIMIT 10
    """
    sample_df = pd.read_sql_query(sample_query, conn)
    
    # Get statistics by competition type
    stats_query = f"""
    SELECT 
        COALESCE(rf70.competition_type, rf40.competition_type) as competition_type,
        COUNT(*) as race_count,
        rkf.cluster_label,
        COUNT(*) as cluster_count,
        AVG(rkf.local_density) as avg_local_density,
        AVG(rkf.boundary_distance) as avg_boundary_distance
    FROM {table_name} rkf
    LEFT JOIN race_features_70 rf70 ON rkf.competition_id = rf70.competition_id
    LEFT JOIN race_features_40 rf40 ON rkf.competition_id = rf40.competition_id
    WHERE rf70.competition_id IS NOT NULL OR rf40.competition_id IS NOT NULL
    GROUP BY COALESCE(rf70.competition_type, rf40.competition_type), rkf.cluster_label
    ORDER BY competition_type, cluster_label
    """
    stats_df = pd.read_sql_query(stats_query, conn)
    
    # Prepare export data
    export_data = {
        'metadata': {
            'table_name': table_name,
            'database_path': DB_PATH,
            'export_timestamp': pd.Timestamp.now().isoformat(),
            'model_configurations': model_configs,
            'max_clusters': max_clusters
        },
        'schema': {
            'columns': schema_df.to_dict('records'),
            'primary_key': 'competition_id'
        },
        'usage_instructions': {
            'join_pattern': f"""
            -- Join with race features for complete data
            SELECT 
                rkf.*,
                COALESCE(rf70.race_name, rf40.race_name) as race_name,
                COALESCE(rf70.competition_name, rf40.competition_name) as competition_name,
                COALESCE(rf70.competition_type, rf40.competition_type) as competition_type,
                COALESCE(rf70.race_category, rf40.race_category) as race_category
            FROM {table_name} rkf
            LEFT JOIN race_features_70 rf70 ON rkf.competition_id = rf70.competition_id
            LEFT JOIN race_features_40 rf40 ON rkf.competition_id = rf40.competition_id
            WHERE rf70.competition_id IS NOT NULL OR rf40.competition_id IS NOT NULL
            """,
            'key_features': [
                'cluster_label: Primary cluster assignment',
                'cluster_0, cluster_1, cluster_2, cluster_3: One-hot encoded cluster membership',
                'distance_to_cluster_0, distance_to_cluster_1, etc.: Distance to each cluster center',
                'local_density: How typical the race is within its cluster',
                'boundary_distance: Distance to nearest different cluster'
            ],
            'competition_type_models': {
                comp_type: f"Uses {config['algorithm']} {config['percentile']}th percentile model"
                for comp_type, config in model_configs.items()
            }
        },
        'statistics': {
            'by_competition_type_and_cluster': stats_df.to_dict('records'),
            'total_races': len(sample_df)
        },
        'sample_data': sample_df.to_dict('records')
    }
    
    # Write to file
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    with open(export_path, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"✅ Key table information exported to: {export_path}")
    
    conn.close()

def show_sample_results(table_name: str):
    """Show sample results from the created table."""
    print("\nSample results:")
    
    conn = sqlite3.connect(DB_PATH)
    
    query = f"""
    SELECT 
        rkf.competition_id,
        rkf.cluster_label,
        rkf.local_density,
        rkf.boundary_distance,
        COALESCE(rf70.race_name, rf40.race_name) as race_name,
        COALESCE(rf70.competition_name, rf40.competition_name) as competition_name,
        COALESCE(rf70.competition_type, rf40.competition_type) as competition_type,
        COALESCE(rf70.race_category, rf40.race_category) as race_category
    FROM {table_name} rkf
    LEFT JOIN race_features_70 rf70 ON rkf.competition_id = rf70.competition_id
    LEFT JOIN race_features_40 rf40 ON rkf.competition_id = rf40.competition_id
    WHERE rf70.competition_id IS NOT NULL OR rf40.competition_id IS NOT NULL
    ORDER BY COALESCE(rf70.competition_type, rf40.competition_type), rkf.cluster_label
    LIMIT 15
    """
    
    try:
        sample_df = pd.read_sql_query(query, conn)
        print(sample_df.to_string(index=False))
    except Exception as e:
        print(f"Error showing sample: {e}")
    
    conn.close()

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description='Create race kind features using configurable models for different competition types'
    )
    
    parser.add_argument(
        '--one-day-model', 
        required=True,
        help='Path to model for one-day races'
    )
    
    parser.add_argument(
        '--stage-model', 
        required=True,
        help='Path to model for stage races'
    )
    
    parser.add_argument(
        '--gc-model', 
        required=True,
        help='Path to model for GC races'
    )
    
    parser.add_argument(
        '--output-table', 
        default='race_kind_features_unified',
        help='Name of the output table (default: race_kind_features_unified)'
    )
    
    parser.add_argument(
        '--export-path',
        help='Path to export key table information JSON file (default: auto-generated in race_kind_feature_guide/)'
    )
    
    
    args = parser.parse_args()
    
    # Generate default export path if not provided
    if args.export_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = os.path.join(os.path.dirname(__file__), 'race_kind_feature_guide')
        os.makedirs(export_dir, exist_ok=True)
        args.export_path = os.path.join(export_dir, f'config_{timestamp}.json')
        print(f"No export path specified. Using: {args.export_path}")
    
    try:
        create_race_kind_features(
            one_day_model_path=args.one_day_model,
            stage_model_path=args.stage_model,
            gc_model_path=args.gc_model,
            output_table=args.output_table,
            export_path=args.export_path
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()