"""
Adapter for running race_type correlation results through the existing pipeline.

This module provides utilities to:
1. Extract individual race_type data from RaceTypeCorrelationCalculator results
2. Run each race_type through the existing feature selection pipeline
3. Generate meta-reports combining results from all race types
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from .feature_selection import FeatureSelectionPipeline
from .data_generation import CorrelationDataGenerator, ParquetStorage, CorrelationDataLoader
from .performance_feature_link.race_type_correlation_method import RaceTypeCorrelationCalculator


class RaceTypeCorrelationAdapter:
    """
    Adapter to run race_type correlation results through the existing pipeline.
    """
    
    def __init__(self):
        self.pipeline = FeatureSelectionPipeline()
        
    def extract_race_type_data(
        self, 
        race_type_results: List[Dict[str, Any]], 
        race_type: str
    ) -> List[Dict[str, Any]]:
        """
        Extract data for a specific race type and reformat to match original pipeline.
        
        Args:
            race_type_results: Results from RaceTypeCorrelationCalculator
            race_type: Race type to extract ('gc', 'stage', 'one_day', 'stage_one_day', 'all')
            
        Returns:
            List of correlation results formatted for original pipeline
        """
        extracted_results = []
        
        for result in race_type_results:
            # Skip if race_type not in results
            if race_type not in result['feature_correlations']:
                continue
                
            # Create new result with race_type data elevated
            extracted = {
                'rider_result_id': result['rider_result_id'],
                'feature_correlations': result['feature_correlations'][race_type],
                'metadata': {
                    'n_races': result['metadata']['n_races'][race_type],
                    'method': f"{result['metadata']['method']}_{race_type}",
                    'calculation_date': result['metadata']['calculation_date'],
                    'warnings': [w for w in result['metadata']['warnings'] if race_type in w],
                    'race_type': race_type
                }
            }
            
            # Only include if we have data
            if extracted['feature_correlations'] and extracted['metadata']['n_races'] > 0:
                extracted_results.append(extracted)
        
        return extracted_results
    
    def run_pipeline_for_race_type(
        self,
        race_type_results: List[Dict[str, Any]],
        race_type: str,
        max_features: int = 25,
        k_range: List[int] = None
    ) -> Dict[str, Any]:
        """
        Run the feature selection pipeline for a specific race type.
        
        Args:
            race_type_results: Results from RaceTypeCorrelationCalculator
            race_type: Race type to analyze
            max_features: Maximum features to recommend
            k_range: Range of k values for clustering
            
        Returns:
            Feature selection results for the race type
        """
        # Extract race type data
        extracted_data = self.extract_race_type_data(race_type_results, race_type)
        
        if not extracted_data:
            return {
                'race_type': race_type,
                'error': f'No valid data for race type {race_type}',
                'timestamp': datetime.now().isoformat()
            }
        
        print(f"\nAnalyzing {race_type} races ({len(extracted_data)} riders)...")
        
        # Run standard pipeline
        try:
            results = self.pipeline.analyze_all(
                correlation_results=extracted_data,
                k_range=k_range,
                max_features=max_features
            )
            results['race_type'] = race_type
            return results
            
        except Exception as e:
            return {
                'race_type': race_type,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_all_race_types(
        self,
        race_type_results: List[Dict[str, Any]],
        race_types: List[str] = None,
        max_features: int = 25,
        k_range: List[int] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Run pipeline for all race types.
        
        Args:
            race_type_results: Results from RaceTypeCorrelationCalculator
            race_types: List of race types to analyze (default: all)
            max_features: Maximum features to recommend
            k_range: Range of k values for clustering
            
        Returns:
            Dictionary mapping race_type to analysis results
        """
        if race_types is None:
            race_types = ['gc', 'stage', 'one_day', 'stage_one_day', 'all']
        
        all_results = {}
        
        for race_type in race_types:
            print(f"\n{'='*60}")
            print(f"Processing {race_type.upper()} races")
            print(f"{'='*60}")
            
            results = self.run_pipeline_for_race_type(
                race_type_results, 
                race_type, 
                max_features, 
                k_range
            )
            all_results[race_type] = results
        
        return all_results
    
    def generate_meta_report(
        self, 
        all_results: Dict[str, Dict[str, Any]],
        output_dir: str = "race_type_analysis"
    ) -> str:
        """
        Generate a comprehensive meta-report combining all race type results.
        
        Args:
            all_results: Dictionary of race_type → analysis results
            output_dir: Directory to save individual reports and meta-report
            
        Returns:
            Path to the meta-report file
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Save individual race type results
        for race_type, results in all_results.items():
            if 'error' not in results:
                # Save detailed results
                result_file = output_path / f"{race_type}_analysis_results.json"
                self.pipeline.save_results(results, str(result_file), include_raw_data=True)
                
                # Generate and save report
                report = self.pipeline.generate_report(results)
                report_file = output_path / f"{race_type}_analysis_report.txt"
                with open(report_file, 'w') as f:
                    f.write(report)
        
        # Generate meta-report
        meta_report = self._create_meta_report(all_results)
        meta_report_file = output_path / "meta_analysis_report.txt"
        with open(meta_report_file, 'w') as f:
            f.write(meta_report)
        
        # Save meta-analysis summary
        meta_summary = self._create_meta_summary(all_results)
        meta_summary_file = output_path / "meta_analysis_summary.json"
        with open(meta_summary_file, 'w') as f:
            json.dump(meta_summary, f, indent=2, default=str)
        
        print(f"\nMeta-report saved to: {meta_report_file}")
        return str(meta_report_file)
    
    def _create_meta_report(self, all_results: Dict[str, Dict[str, Any]]) -> str:
        """Create comprehensive meta-report text."""
        report = []
        report.append("RACE TYPE CORRELATION META-ANALYSIS REPORT")
        report.append("=" * 70)
        report.append("")
        report.append(f"Analysis Date: {datetime.now().isoformat()}")
        report.append(f"Race Types Analyzed: {', '.join(all_results.keys())}")
        report.append("")
        
        # Summary table
        report.append("SUMMARY OF RECOMMENDATIONS BY RACE TYPE")
        report.append("=" * 70)
        report.append("")
        
        summary_data = []
        headers = ['Race Type', 'Best Percentile', 'Features', 'Clusters', 'Silhouette', 'Riders']
        
        for race_type, results in all_results.items():
            if 'error' in results:
                summary_data.append([
                    race_type.upper(),
                    'ERROR',
                    '-',
                    '-',
                    '-',
                    '-'
                ])
            else:
                rec = results.get('recommendations', {}).get('summary', {})
                best_percentile = rec.get('recommended_percentile', 'N/A')
                feature_count = rec.get('feature_count', 0)
                
                # Get clustering info
                clustering = results.get('clustering_analysis', {})
                percentile_analysis = clustering.get('percentile_analyses', {}).get(best_percentile, {})
                optimal_k = percentile_analysis.get('optimal_k', 'N/A')
                
                silhouette = 'N/A'
                if optimal_k != 'N/A' and optimal_k in percentile_analysis.get('clustering_results', {}):
                    silhouette = f"{percentile_analysis['clustering_results'][optimal_k]['silhouette_score']:.3f}"
                
                rider_count = results.get('analysis_metadata', {}).get('total_rider_results', 0)
                
                summary_data.append([
                    race_type.upper(),
                    best_percentile.split('_')[-1] if best_percentile else 'N/A',
                    str(feature_count),
                    str(optimal_k),
                    silhouette,
                    str(rider_count)
                ])
        
        # Format table
        col_widths = [max(len(str(row[i])) for row in [headers] + summary_data) + 2 
                      for i in range(len(headers))]
        
        # Header
        header_line = ''.join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
        report.append(header_line)
        report.append('-' * sum(col_widths))
        
        # Data rows
        for row in summary_data:
            report.append(''.join(f"{str(d):<{w}}" for d, w in zip(row, col_widths)))
        
        report.append("")
        
        # Detailed comparisons
        report.append("FEATURE COMPARISONS ACROSS RACE TYPES")
        report.append("=" * 70)
        report.append("")
        
        # Extract recommended features for each race type
        race_type_features = {}
        for race_type, results in all_results.items():
            if 'error' not in results:
                features = results.get('recommendations', {}).get('summary', {}).get('recommended_features', [])
                if features:
                    race_type_features[race_type] = set(features)
        
        if race_type_features:
            # Find common and unique features
            all_features = set()
            for features in race_type_features.values():
                all_features.update(features)
            
            # Common features across all race types
            common_features = all_features.copy()
            for features in race_type_features.values():
                common_features.intersection_update(features)
            
            report.append(f"Total unique features across all race types: {len(all_features)}")
            report.append(f"Features common to all race types: {len(common_features)}")
            report.append("")
            
            if common_features:
                report.append("UNIVERSALLY IMPORTANT FEATURES:")
                for i, feature in enumerate(sorted(common_features), 1):
                    report.append(f"  {i:2d}. {feature}")
                report.append("")
            
            # Race type specific features
            report.append("RACE TYPE SPECIFIC FEATURES:")
            report.append("-" * 40)
            
            for race_type, features in sorted(race_type_features.items()):
                unique_features = features - common_features
                if unique_features:
                    report.append(f"\n{race_type.upper()} specific features ({len(unique_features)}):")
                    for feature in sorted(unique_features)[:10]:  # Top 10
                        report.append(f"  - {feature}")
        
        report.append("")
        
        # Clustering comparison
        report.append("CLUSTERING QUALITY COMPARISON")
        report.append("=" * 70)
        report.append("")
        
        clustering_summary = []
        for race_type, results in all_results.items():
            if 'error' not in results and 'clustering_analysis' in results:
                best_percentile = results['recommendations']['summary'].get('recommended_percentile')
                if best_percentile:
                    clustering_data = results['clustering_analysis']['percentile_analyses'].get(best_percentile, {})
                    optimal_k = clustering_data.get('optimal_k', 'N/A')
                    
                    if optimal_k != 'N/A' and optimal_k in clustering_data.get('clustering_results', {}):
                        cluster_results = clustering_data['clustering_results'][optimal_k]
                        clustering_summary.append({
                            'race_type': race_type,
                            'k': optimal_k,
                            'silhouette': cluster_results['silhouette_score'],
                            'sizes': cluster_results['cluster_sizes']
                        })
        
        if clustering_summary:
            # Sort by silhouette score
            clustering_summary.sort(key=lambda x: x['silhouette'], reverse=True)
            
            report.append("Ranked by clustering quality (silhouette score):")
            for i, cluster_info in enumerate(clustering_summary, 1):
                report.append(f"\n{i}. {cluster_info['race_type'].upper()}")
                report.append(f"   Clusters: {cluster_info['k']}")
                report.append(f"   Silhouette: {cluster_info['silhouette']:.4f}")
                report.append(f"   Cluster sizes: {cluster_info['sizes']}")
                
                # Interpret quality
                if cluster_info['silhouette'] > 0.5:
                    quality = "Excellent separation"
                elif cluster_info['silhouette'] > 0.3:
                    quality = "Good separation"
                else:
                    quality = "Moderate separation"
                report.append(f"   Quality: {quality}")
        
        report.append("")
        report.append("="*70)
        report.append("END OF META-ANALYSIS REPORT")
        
        return "\n".join(report)
    
    def _create_meta_summary(self, all_results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Create JSON summary of meta-analysis."""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'race_types_analyzed': list(all_results.keys()),
            'recommendations': {},
            'feature_overlap': {},
            'clustering_summary': {},
            'errors': {}
        }
        
        # Collect recommendations and features
        all_features = set()
        race_type_features = {}
        
        for race_type, results in all_results.items():
            if 'error' in results:
                summary['errors'][race_type] = results['error']
            else:
                rec = results.get('recommendations', {}).get('summary', {})
                summary['recommendations'][race_type] = {
                    'percentile': rec.get('recommended_percentile'),
                    'feature_count': rec.get('feature_count'),
                    'features': rec.get('recommended_features', [])
                }
                
                features = set(rec.get('recommended_features', []))
                if features:
                    race_type_features[race_type] = features
                    all_features.update(features)
        
        # Calculate feature overlap
        if race_type_features:
            # Common features
            common_features = all_features.copy()
            for features in race_type_features.values():
                common_features.intersection_update(features)
            
            summary['feature_overlap'] = {
                'total_unique_features': len(all_features),
                'common_to_all': list(common_features),
                'common_count': len(common_features),
                'overlap_matrix': {}
            }
            
            # Pairwise overlap
            race_types = list(race_type_features.keys())
            for i, rt1 in enumerate(race_types):
                for rt2 in race_types[i+1:]:
                    overlap = race_type_features[rt1].intersection(race_type_features[rt2])
                    key = f"{rt1}_vs_{rt2}"
                    summary['feature_overlap']['overlap_matrix'][key] = {
                        'count': len(overlap),
                        'percentage': len(overlap) / min(len(race_type_features[rt1]), 
                                                        len(race_type_features[rt2])) * 100
                    }
        
        return summary


class RaceTypeDataGenerator(CorrelationDataGenerator):
    """
    Extended data generator that handles race_type correlation results.
    """
    
    def __init__(
        self, 
        db_path: str,
        output_dir: str = "race_type_correlation_data",
        batch_size: int = 100,
        min_races_all: int = 35,
        min_races_stage: int = 25,
        min_races_one_day: int = 15,
        min_races_gc: int = 10
    ):
        """Initialize with race type specific parameters."""
        # Don't call parent __init__ yet
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.batch_size = batch_size
        
        # Set min_races to the minimum of all thresholds for the sample query
        self.min_races = min(min_races_gc, min_races_one_day, min_races_stage, min_races_all)
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize race type calculator instead of regular calculator
        self.calculator = RaceTypeCorrelationCalculator(
            db_path,
            min_races_all=min_races_all,
            min_races_stage=min_races_stage,
            min_races_one_day=min_races_one_day,
            min_races_gc=min_races_gc
        )
        
        # Setup logging
        self._setup_logging()
    
    def _flatten_correlation_result(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Flatten race type correlation result into list of records for parquet storage.
        
        Each record represents one rider-race_type-percentile-feature correlation.
        """
        flat_records = []
        
        rider_result_id = result['rider_result_id']
        calculation_date = result['metadata']['calculation_date']
        
        # Iterate through race types
        for race_type, percentile_data in result['feature_correlations'].items():
            n_races = result['metadata']['n_races'][race_type]
            
            # Iterate through percentiles within each race type
            for percentile, correlations in percentile_data.items():
                for feature, correlation in correlations.items():
                    record = {
                        'rider_result_id': rider_result_id,
                        'race_type': race_type,
                        'percentile': percentile,
                        'feature': feature,
                        'correlation': correlation,
                        'n_races': n_races,
                        'calculation_date': calculation_date
                    }
                    flat_records.append(record)
        
        return flat_records
    
    def _save_batch(self, batch_data: List[Dict[str, Any]], batch_number: int):
        """Save batch data to parquet file with race_type column."""
        df = pd.DataFrame(batch_data)
        
        # Convert types for efficient storage
        df['rider_result_id'] = df['rider_result_id'].astype('int32')
        df['n_races'] = df['n_races'].astype('int16')
        df['race_type'] = df['race_type'].astype('category')
        df['percentile'] = df['percentile'].astype('category')
        df['feature'] = df['feature'].astype('category')
        
        # Save to parquet
        output_file = self.output_dir / f"race_type_correlations_batch_{batch_number:04d}.parquet"
        df.to_parquet(output_file, compression='snappy')
        
        self.logger.info(f"Saved batch {batch_number} with {len(df)} records")