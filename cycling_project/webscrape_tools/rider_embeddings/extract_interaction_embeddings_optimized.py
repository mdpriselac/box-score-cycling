#!/usr/bin/env python3
"""
Optimized Interaction Embeddings Extraction Script

This script generates interaction-based rider embeddings using the enhanced
parallel processing infrastructure from the existing pipeline.

Generates embeddings that represent interactions between:
- Current race features
- Historical correlations between rider performance and race features

Output Structure:
- interaction_embeddings/
  ├── phase1/              # Individual percentile interactions
  │   ├── gc/
  │   │   ├── dot_products.parquet
  │   │   ├── hadamard_products.parquet
  │   │   └── cosine_similarities.parquet
  │   ├── stage/
  │   ├── one_day/
  │   ├── stage_one_day/
  │   └── all/
  └── phase2/              # Matrix-level interactions
      ├── gc/
      ├── stage/
      └── ...
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Tuple
import time
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
from tqdm import tqdm

# Add the project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from rider_embeddings.performance_feature_link.interaction_embeddings import InteractionEmbeddingsCalculator
from rider_embeddings.performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator
from rider_embeddings.performance_optimization.batched_database_loader import BatchedDatabaseLoader

# ====================================================================
# CONFIGURATION SECTION
# ====================================================================

# Race type minimum requirements (same as correlation pipeline)
RACE_TYPE_PERCENTILES = {
    'gc': 60,
    'stage': 60,
    'one_day': 60,
    'stage_one_day': 60,
    'all': 60
}

# Performance optimization settings
OPTIMIZATION_CONFIG = {
    'n_workers': 4,                    # Parallel workers
    'batch_size': 100,                 # Batch size for processing
    'sample_mode': True,               # Set to False for full dataset
    'sample_size': 1000,              # Sample size if in sample mode
    'chunk_size': 50,                 # Size of chunks for parallel processing
    'preload_race_features': True      # Preload all race features for efficiency
}

# Database and output configuration
DB_PATH = "database/database/cycling_races.db"
OUTPUT_DIR = "interaction_embeddings"

# Feature tables to process
FEATURE_TABLES = [
    'race_features_30', 'race_features_40', 'race_features_50',
    'race_features_60', 'race_features_70', 'race_features_80',
    'race_features_90', 'race_features_100'
]

# Race types to process
RACE_TYPES = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']

# Interaction types to calculate
INTERACTION_TYPES = ['dot', 'hadamard', 'cosine']

# ====================================================================
# END CONFIGURATION SECTION
# ====================================================================


def process_rider_chunk_interactions(chunk_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Process a chunk of riders to calculate interaction embeddings.
    
    Args:
        chunk_data: Dictionary containing rider data and configuration
        
    Returns:
        List of interaction embedding results
    """
    rider_result_data = chunk_data['rider_result_data']
    feature_tables = chunk_data['feature_tables']
    calculator_config = chunk_data['calculator_config']
    db_path = chunk_data['db_path']
    chunk_id = chunk_data.get('chunk_id', 'unknown')
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format=f'Worker-{chunk_id}: %(message)s')
    logger = logging.getLogger(f'worker_{chunk_id}')
    
    try:
        logger.info(f"Processing {len(rider_result_data)} riders for interactions")
        
        # Create calculator instances for this worker
        correlation_calculator = RaceTypeCorrelationCalculator(
            db_path=db_path,
            min_races_all=calculator_config['min_races_all'],
            min_races_stage=calculator_config['min_races_stage'],
            min_races_one_day=calculator_config['min_races_one_day'],
            min_races_gc=calculator_config['min_races_gc']
        )
        
        interaction_calculator = InteractionEmbeddingsCalculator(
            db_path=db_path,
            correlation_calculator=correlation_calculator
        )
        
        results = []
        successful = 0
        failed = 0
        
        for rider_result_id, competition_date in rider_result_data:
            try:
                # Calculate interaction embeddings
                result = interaction_calculator.calculate_interaction_embeddings(
                    rider_result_id=rider_result_id,
                    lookback_date=competition_date,
                    feature_tables=feature_tables,
                    interaction_types=INTERACTION_TYPES
                )
                results.append(result)
                successful += 1
                
            except Exception as e:
                failed += 1
                error_result = {
                    'rider_result_id': rider_result_id,
                    'phase1_interactions': {},
                    'phase2_interactions': {},
                    'metadata': {
                        'calculation_date': datetime.now().isoformat(),
                        'warnings': [f"Error processing rider {rider_result_id}: {str(e)}"],
                        'error': str(e)
                    }
                }
                results.append(error_result)
                logger.error(f"Error processing rider {rider_result_id}: {e}")
        
        logger.info(f"Chunk complete: {successful} successful, {failed} failed")
        return results
        
    except Exception as e:
        logger.error(f"Chunk processing failed: {e}")
        return []


def calculate_percentile_minimums(db_path: str, percentile_config: dict) -> dict:
    """Calculate minimum race counts based on percentiles for each race type."""
    import sqlite3
    
    print("Calculating percentile-based minimum race requirements...")
    
    race_type_definitions = {
        'gc': ['gc'],
        'stage': ['stage'],
        'one_day': ['one_day'],
        'stage_one_day': ['stage', 'one_day'],
        'all': ['gc', 'stage', 'one_day']
    }
    
    minimums = {}
    
    with sqlite3.connect(db_path) as conn:
        for race_type, percentile in percentile_config.items():
            competition_types = race_type_definitions[race_type]
            
            # Build the competition type filter
            if len(competition_types) == 1:
                type_filter = f"= '{competition_types[0]}'"
            else:
                type_list = "', '".join(competition_types)
                type_filter = f"IN ('{type_list}')"
            
            # Query to get all prior race counts for this race type
            query = f"""
            WITH race_type_results AS (
                SELECT 
                    rr.id as rider_result_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY rr.rider_id 
                        ORDER BY c.date
                    ) - 1 as prior_races_of_type
                FROM rider_results rr
                JOIN competitions c ON rr.competition_id = c.id
                WHERE c.date <= '2025-01-01'
                AND c.competition_type {type_filter}
            )
            SELECT prior_races_of_type
            FROM race_type_results
            WHERE prior_races_of_type > 0
            """
            
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                minimum_races = int(np.percentile(df['prior_races_of_type'], percentile))
                minimums[race_type] = minimum_races
                
                total_results = len(df)
                eligible_results = len(df[df['prior_races_of_type'] >= minimum_races])
                coverage_pct = (eligible_results / total_results) * 100
                
                print(f"  {race_type}: {percentile}th percentile = {minimum_races} races "
                      f"({eligible_results:,} results, {coverage_pct:.1f}% coverage)")
            else:
                minimums[race_type] = 1
                print(f"  {race_type}: No data found, using minimum of 1")
    
    return minimums


def get_rider_result_sample(db_path: str, sample_size: int, minimums: dict) -> List[Tuple[int, str]]:
    """Get a sample of rider results for testing."""
    import sqlite3
    
    query = """
    WITH eligible_results AS (
        SELECT 
            rr.id as rider_result_id,
            c.date as competition_date,
            c.competition_type,
            ROW_NUMBER() OVER (PARTITION BY rr.rider_id ORDER BY c.date) - 1 as prior_races
        FROM rider_results rr
        JOIN competitions c ON rr.competition_id = c.id
        WHERE c.date >= '2020-01-01' AND c.date <= '2025-01-01'
    )
    SELECT DISTINCT rider_result_id, competition_date
    FROM eligible_results
    WHERE prior_races >= ?
    ORDER BY RANDOM()
    LIMIT ?
    """
    
    min_races = minimums.get('all', 35)
    
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(min_races, sample_size))
        return [(row['rider_result_id'], row['competition_date']) for _, row in df.iterrows()]


def organize_phase1_embeddings(results: List[Dict[str, Any]], output_dir: Path):
    """Organize Phase 1 embeddings by race type and interaction type."""
    phase1_dir = output_dir / 'phase1'
    phase1_dir.mkdir(exist_ok=True, parents=True)
    
    print("\nOrganizing Phase 1 embeddings...")
    
    # Collect all phase 1 data by race type and interaction type
    phase1_data = {
        race_type: {
            interaction: {} for interaction in INTERACTION_TYPES
        } for race_type in RACE_TYPES
    }
    
    for result in results:
        rider_result_id = result['rider_result_id']
        phase1 = result.get('phase1_interactions', {})
        
        for race_type, race_type_data in phase1.items():
            if race_type not in RACE_TYPES:
                continue
                
            for percentile, percentile_data in race_type_data.items():
                for interaction_type, value in percentile_data.items():
                    if interaction_type not in INTERACTION_TYPES:
                        continue
                    
                    # Create key for this embedding
                    key = f"{rider_result_id}_{percentile}"
                    
                    if interaction_type == 'hadamard':
                        # Hadamard is a dict, flatten it
                        for feature, feature_value in value.items():
                            feature_key = f"{key}_{feature}"
                            phase1_data[race_type][interaction_type][feature_key] = {
                                'rider_result_id': rider_result_id,
                                'percentile': percentile,
                                'feature': feature,
                                'value': feature_value
                            }
                    else:
                        # Dot and cosine are scalars
                        phase1_data[race_type][interaction_type][key] = {
                            'rider_result_id': rider_result_id,
                            'percentile': percentile,
                            'value': value
                        }
    
    # Save organized data
    for race_type in RACE_TYPES:
        race_type_dir = phase1_dir / race_type
        race_type_dir.mkdir(exist_ok=True)
        
        for interaction_type in INTERACTION_TYPES:
            data = phase1_data[race_type][interaction_type]
            
            if data:
                # Convert to DataFrame
                df = pd.DataFrame.from_dict(data, orient='index')
                
                # Save as parquet
                output_file = race_type_dir / f"{interaction_type}_products.parquet"
                df.to_parquet(output_file, compression='snappy')
                
                print(f"  Saved {len(df)} {interaction_type} embeddings to {output_file.name}")


def organize_phase2_embeddings(results: List[Dict[str, Any]], output_dir: Path):
    """Organize Phase 2 embeddings by race type."""
    phase2_dir = output_dir / 'phase2'
    phase2_dir.mkdir(exist_ok=True, parents=True)
    
    print("\nOrganizing Phase 2 embeddings...")
    
    # Collect all phase 2 data by race type
    phase2_data = {race_type: [] for race_type in RACE_TYPES}
    
    for result in results:
        rider_result_id = result['rider_result_id']
        phase2 = result.get('phase2_interactions', {})
        
        for race_type, race_type_data in phase2.items():
            if race_type not in RACE_TYPES:
                continue
            
            interactions = race_type_data.get('interactions', {})
            
            # Create embedding record
            record = {
                'rider_result_id': rider_result_id,
                'dot_product': interactions.get('dot', None),
                'cosine_similarity': interactions.get('cosine', None)
            }
            
            # Add flattened Hadamard product if present
            hadamard = interactions.get('hadamard')
            if hadamard is not None and hasattr(hadamard, 'flatten'):
                flattened = hadamard.flatten()
                for i, val in enumerate(flattened):
                    record[f'hadamard_{i}'] = val
            
            phase2_data[race_type].append(record)
    
    # Save organized data
    for race_type in RACE_TYPES:
        if phase2_data[race_type]:
            df = pd.DataFrame(phase2_data[race_type])
            
            race_type_dir = phase2_dir / race_type
            race_type_dir.mkdir(exist_ok=True)
            
            output_file = race_type_dir / 'matrix_interactions.parquet'
            df.to_parquet(output_file, compression='snappy')
            
            print(f"  Saved {len(df)} matrix interactions for {race_type}")


def save_metadata(output_dir: Path, results: List[Dict[str, Any]], config: Dict[str, Any]):
    """Save metadata about the extraction process."""
    metadata = {
        'extraction_date': datetime.now().isoformat(),
        'n_riders_processed': len(results),
        'configuration': config,
        'race_types': RACE_TYPES,
        'feature_tables': FEATURE_TABLES,
        'interaction_types': INTERACTION_TYPES,
        'warnings': []
    }
    
    # Collect warnings
    for result in results:
        warnings = result.get('metadata', {}).get('warnings', [])
        metadata['warnings'].extend(warnings)
    
    # Count unique warnings
    unique_warnings = list(set(metadata['warnings']))
    metadata['unique_warnings'] = unique_warnings
    metadata['n_warnings'] = len(metadata['warnings'])
    
    # Save metadata
    metadata_file = output_dir / 'extraction_metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nSaved metadata to {metadata_file}")


def main():
    """Run the interaction embeddings extraction with parallel processing."""
    print("INTERACTION EMBEDDINGS EXTRACTION")
    print("="*80)
    print("🎯 Extracting interaction-based rider embeddings")
    print("🚀 Using parallel processing for efficiency")
    
    # Display configuration
    print("\nCurrent Configuration:")
    print(f"Sample Mode: {OPTIMIZATION_CONFIG['sample_mode']}")
    if OPTIMIZATION_CONFIG['sample_mode']:
        print(f"Sample Size: {OPTIMIZATION_CONFIG['sample_size']:,} rider results")
    print(f"Workers: {OPTIMIZATION_CONFIG['n_workers']}")
    print(f"Batch Size: {OPTIMIZATION_CONFIG['batch_size']}")
    print(f"Database: {DB_PATH}")
    print(f"Output Directory: {OUTPUT_DIR}")
    
    print(f"\nInteraction Types: {', '.join(INTERACTION_TYPES)}")
    print(f"Race Types: {', '.join(RACE_TYPES)}")
    print(f"Feature Tables: {len(FEATURE_TABLES)}")
    
    if not OPTIMIZATION_CONFIG['sample_mode']:
        confirm = input("\nProcess full dataset? This may take a while. [y/N]: ").strip().lower()
        if confirm != 'y':
            print("Aborted.")
            return
    
    try:
        start_time = time.time()
        
        # Calculate minimum race requirements
        minimums = calculate_percentile_minimums(DB_PATH, RACE_TYPE_PERCENTILES)
        
        calculator_config = {
            'min_races_all': minimums['all'],
            'min_races_stage': minimums['stage'],
            'min_races_one_day': minimums['one_day'],
            'min_races_gc': minimums['gc']
        }
        
        # Get rider results to process
        if OPTIMIZATION_CONFIG['sample_mode']:
            print(f"\nGetting sample of {OPTIMIZATION_CONFIG['sample_size']} rider results...")
            rider_results = get_rider_result_sample(
                DB_PATH, 
                OPTIMIZATION_CONFIG['sample_size'],
                minimums
            )
        else:
            # TODO: Implement full dataset loading
            print("\nFull dataset mode not yet implemented")
            return
        
        print(f"Processing {len(rider_results)} rider results...")
        
        # Split into chunks for parallel processing
        chunk_size = OPTIMIZATION_CONFIG['chunk_size']
        chunks = [
            rider_results[i:i + chunk_size] 
            for i in range(0, len(rider_results), chunk_size)
        ]
        
        print(f"Split into {len(chunks)} chunks of ~{chunk_size} riders each")
        
        # Prepare chunk data for parallel processing
        chunk_data_list = []
        for i, chunk in enumerate(chunks):
            chunk_data = {
                'rider_result_data': chunk,
                'feature_tables': FEATURE_TABLES,
                'calculator_config': calculator_config,
                'db_path': DB_PATH,
                'chunk_id': f"{i+1}/{len(chunks)}"
            }
            chunk_data_list.append(chunk_data)
        
        # Process chunks in parallel
        all_results = []
        
        with ProcessPoolExecutor(max_workers=OPTIMIZATION_CONFIG['n_workers']) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(process_rider_chunk_interactions, chunk_data): i
                for i, chunk_data in enumerate(chunk_data_list)
            }
            
            # Process completed chunks
            with tqdm(total=len(chunks), desc="Processing chunks") as pbar:
                for future in as_completed(future_to_chunk):
                    chunk_idx = future_to_chunk[future]
                    try:
                        results = future.result()
                        all_results.extend(results)
                        pbar.update(1)
                    except Exception as e:
                        print(f"\nError processing chunk {chunk_idx}: {e}")
                        pbar.update(1)
        
        print(f"\nProcessed {len(all_results)} total results")
        
        # Create output directory
        output_path = Path(OUTPUT_DIR)
        output_path.mkdir(exist_ok=True)
        
        # Organize and save results
        organize_phase1_embeddings(all_results, output_path)
        organize_phase2_embeddings(all_results, output_path)
        
        # Save metadata
        save_metadata(output_path, all_results, OPTIMIZATION_CONFIG)
        
        total_time = time.time() - start_time
        
        print("\n" + "="*80)
        print("✅ INTERACTION EMBEDDINGS EXTRACTION COMPLETE!")
        print("="*80)
        print(f"\nTotal processing time: {total_time:.1f} seconds")
        print(f"Average time per rider: {total_time/len(rider_results):.3f} seconds")
        
        print(f"\n📁 OUTPUT STRUCTURE:")
        print(f"  {OUTPUT_DIR}/")
        print(f"  ├── phase1/           # Individual percentile interactions")
        print(f"  │   ├── gc/")
        print(f"  │   ├── stage/")
        print(f"  │   └── ...")
        print(f"  ├── phase2/           # Matrix-level interactions")
        print(f"  │   ├── gc/")
        print(f"  │   └── ...")
        print(f"  └── extraction_metadata.json")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()