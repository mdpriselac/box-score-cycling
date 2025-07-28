"""
Analyze how well gradient features support separation of stage races into kinds

This script:
1. Filters for stage competitions with winning_time > 90 minutes (non-TT)
2. Analyzes each gradient feature category for separability potential
3. Generates machine-readable data and human-readable reports
"""

import sqlite3
import json
import numpy as np
import pandas as pd
from pathlib import Path
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


def find_database():
    """Find the SQLite database file"""
    if HAS_DOTENV:
        load_dotenv()
        db_path = os.getenv('DB_PATH')
        if db_path and os.path.exists(db_path):
            return db_path
    
    # Go up two levels from current directory to find db
    db_path = Path(__file__).parent.parent.parent / "database" / "database" / "cycling_races.db"
    if db_path.exists():
        return str(db_path)
    
    raise FileNotFoundError("Database not found")


def get_stage_competition_data(db_path: str) -> pd.DataFrame:
    """Get stage competitions with winning_time > 90 minutes"""
    conn = sqlite3.connect(db_path)
    
    query = """
    SELECT 
        rfg.*,
        rf100.winning_time,
        COALESCE(rfg.kurtosis_null_percentile, 0) as kurtosis_breakdown_point,
        COALESCE(rfg.variance_zero_percentile, 0) as variance_breakdown_point
    FROM race_feature_gradients rfg
    JOIN race_features_100 rf100 ON rfg.competition_id = rf100.competition_id
    WHERE rfg.competition_type = 'stage'
    AND rf100.winning_time > 5400  -- More than 90 minutes (filters out TTs)
    AND rfg.variance_normalized_values IS NOT NULL  -- Has gradient data
    ORDER BY rfg.total_finishers DESC
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    return df


def parse_gradient_values(json_str: str) -> List[float]:
    """Parse JSON gradient values safely"""
    if pd.isna(json_str) or json_str is None:
        return []
    try:
        return json.loads(json_str)
    except:
        return []


def calculate_separability_metrics(values: List[float]) -> Dict[str, float]:
    """Calculate various metrics to assess separability potential"""
    if len(values) < 2:
        return {
            'range': 0,
            'std': 0,
            'cv': 0,
            'iqr': 0,
            'mad': 0,
            'percentile_90_10_ratio': 1,
            'outlier_ratio': 0,
            'distinct_values': 0,
            'entropy': 0
        }
    
    values = np.array(values)
    values = values[~np.isnan(values)]  # Remove NaN values
    
    if len(values) < 2:
        return {
            'range': 0,
            'std': 0,
            'cv': 0,
            'iqr': 0,
            'mad': 0,
            'percentile_90_10_ratio': 1,
            'outlier_ratio': 0,
            'distinct_values': 0,
            'entropy': 0
        }
    
    # Basic statistics
    mean_val = np.mean(values)
    std_val = np.std(values)
    
    # Range and spread metrics
    range_val = np.max(values) - np.min(values)
    cv = std_val / abs(mean_val) if mean_val != 0 else 0
    
    # Percentile-based metrics
    p10, p25, p75, p90 = np.percentile(values, [10, 25, 75, 90])
    iqr = p75 - p25
    percentile_ratio = p90 / p10 if p10 != 0 else 1
    
    # Median Absolute Deviation
    mad = np.median(np.abs(values - np.median(values)))
    
    # Outlier detection (IQR method)
    q1, q3 = np.percentile(values, [25, 75])
    iqr_val = q3 - q1
    lower_bound = q1 - 1.5 * iqr_val
    upper_bound = q3 + 1.5 * iqr_val
    outliers = np.sum((values < lower_bound) | (values > upper_bound))
    outlier_ratio = outliers / len(values)
    
    # Distinct values (for assessing granularity)
    distinct_values = len(np.unique(values))
    
    # Entropy (information content)
    # Bin values into deciles for entropy calculation
    if len(values) > 10:
        hist, _ = np.histogram(values, bins=10)
        hist = hist[hist > 0]  # Remove empty bins
        prob = hist / np.sum(hist)
        entropy = -np.sum(prob * np.log2(prob))
    else:
        entropy = 0
    
    return {
        'range': float(range_val),
        'std': float(std_val),
        'cv': float(cv),
        'iqr': float(iqr),
        'mad': float(mad),
        'percentile_90_10_ratio': float(percentile_ratio),
        'outlier_ratio': float(outlier_ratio),
        'distinct_values': int(distinct_values),
        'entropy': float(entropy)
    }


def analyze_gradient_feature_category(df: pd.DataFrame, feature_prefix: str) -> Dict[str, Any]:
    """Analyze a specific gradient feature category"""
    
    # Get all columns for this feature
    slope_col = f"{feature_prefix}_slope"
    volatility_col = f"{feature_prefix}_volatility"
    monotonicity_col = f"{feature_prefix}_monotonicity"
    directional_changes_col = f"{feature_prefix}_directional_changes"
    values_col = f"{feature_prefix}_values"
    
    results = {
        'feature_name': feature_prefix,
        'total_competitions': len(df),
        'competitions_with_data': 0,
        'slope_analysis': {},
        'volatility_analysis': {},
        'monotonicity_analysis': {},
        'directional_changes_analysis': {},
        'values_analysis': {},
        'combined_separability_score': 0,
        'quality_indicators': {}
    }
    
    # Check data availability
    slope_available = slope_col in df.columns and not df[slope_col].isna().all()
    volatility_available = volatility_col in df.columns and not df[volatility_col].isna().all()
    monotonicity_available = monotonicity_col in df.columns and not df[monotonicity_col].isna().all()
    directional_changes_available = directional_changes_col in df.columns and not df[directional_changes_col].isna().all()
    values_available = values_col in df.columns and not df[values_col].isna().all()
    
    if not any([slope_available, volatility_available, monotonicity_available, directional_changes_available, values_available]):
        return results
    
    results['competitions_with_data'] = len(df[df[slope_col].notna()]) if slope_available else 0
    
    # Analyze slope
    if slope_available:
        slope_values = df[slope_col].dropna().tolist()
        results['slope_analysis'] = calculate_separability_metrics(slope_values)
    
    # Analyze volatility
    if volatility_available:
        volatility_values = df[volatility_col].dropna().tolist()
        results['volatility_analysis'] = calculate_separability_metrics(volatility_values)
    
    # Analyze monotonicity
    if monotonicity_available:
        monotonicity_values = df[monotonicity_col].dropna().tolist()
        results['monotonicity_analysis'] = calculate_separability_metrics(monotonicity_values)
    
    # Analyze directional changes
    if directional_changes_available:
        directional_changes_values = df[directional_changes_col].dropna().tolist()
        results['directional_changes_analysis'] = calculate_separability_metrics(directional_changes_values)
    
    # Analyze values arrays (gradient evolution patterns)
    if values_available:
        all_values = []
        gradient_ranges = []
        gradient_patterns = []
        
        for idx, row in df.iterrows():
            if pd.notna(row[values_col]):
                values = parse_gradient_values(row[values_col])
                if len(values) > 1:
                    all_values.extend(values)
                    gradient_ranges.append(max(values) - min(values))
                    # Pattern: early vs late change
                    if len(values) >= 4:
                        early_change = abs(values[1] - values[0]) if len(values) > 1 else 0
                        late_change = abs(values[-1] - values[-2]) if len(values) > 1 else 0
                        gradient_patterns.append(early_change / (late_change + 1e-10))
        
        results['values_analysis'] = {
            'all_values': calculate_separability_metrics(all_values),
            'gradient_ranges': calculate_separability_metrics(gradient_ranges),
            'pattern_ratios': calculate_separability_metrics(gradient_patterns)
        }
    
    # Calculate combined separability score
    # Higher score = better potential for separating race kinds
    score_components = []
    
    if slope_available and results['slope_analysis'].get('cv', 0) > 0:
        score_components.append(results['slope_analysis']['cv'])
    
    if volatility_available and results['volatility_analysis'].get('cv', 0) > 0:
        score_components.append(results['volatility_analysis']['cv'])
    
    if monotonicity_available and results['monotonicity_analysis'].get('std', 0) > 0:
        score_components.append(results['monotonicity_analysis']['std'])
    
    if directional_changes_available and results['directional_changes_analysis'].get('cv', 0) > 0:
        score_components.append(results['directional_changes_analysis']['cv'])
    
    if values_available and results['values_analysis'].get('gradient_ranges', {}).get('cv', 0) > 0:
        score_components.append(results['values_analysis']['gradient_ranges']['cv'])
    
    results['combined_separability_score'] = float(np.mean(score_components)) if score_components else 0
    
    # Quality indicators
    results['quality_indicators'] = {
        'data_completeness': results['competitions_with_data'] / results['total_competitions'],
        'has_slope_data': slope_available,
        'has_volatility_data': volatility_available,
        'has_monotonicity_data': monotonicity_available,
        'has_directional_changes_data': directional_changes_available,
        'has_values_data': values_available,
        'feature_coverage': sum([slope_available, volatility_available, monotonicity_available, directional_changes_available, values_available]) / 5
    }
    
    return results


def analyze_quality_indicator_feature(df: pd.DataFrame, feature_name: str) -> Dict[str, Any]:
    """Analyze a quality indicator feature (kurtosis_breakdown_point, variance_breakdown_point)"""
    
    results = {
        'feature_name': feature_name,
        'total_competitions': len(df),
        'competitions_with_data': len(df),  # Always 100% because we treat NULL as 0
        'combined_separability_score': 0,
        'quality_indicators': {},
        'breakdown_analysis': {}
    }
    
    if feature_name not in df.columns:
        return results
    
    values = df[feature_name].tolist()
    
    # Calculate separability metrics
    separability = calculate_separability_metrics(values)
    results['separability_analysis'] = separability
    results['combined_separability_score'] = separability.get('entropy', 0)  # Use entropy as primary score
    
    # Analyze breakdown patterns
    value_counts = df[feature_name].value_counts().sort_index()
    results['breakdown_analysis'] = {
        'distribution': value_counts.to_dict(),
        'no_breakdown_count': int(value_counts.get(0, 0)),
        'no_breakdown_percentage': float(value_counts.get(0, 0) / len(df) * 100),
        'distinct_breakdown_points': len(value_counts) - (1 if 0 in value_counts else 0)
    }
    
    # Quality indicators
    results['quality_indicators'] = {
        'data_completeness': 1.0,  # Always complete with 0 for NULL
        'feature_coverage': 1.0,
        'has_breakdown_data': True,
        'interpretability': 'high'  # These are highly interpretable
    }
    
    return results


def find_natural_breakpoints(scores: List[float], feature_names: List[str]) -> Dict[str, Any]:
    """Find natural breakpoints in feature scores to define quality tiers"""
    if len(scores) < 3:
        return {'tiers': [], 'breakpoints': []}
    
    scores_array = np.array(scores)
    
    # Method 1: Look for large gaps in the sorted scores
    sorted_indices = np.argsort(scores_array)[::-1]  # Descending order
    sorted_scores = scores_array[sorted_indices]
    sorted_names = [feature_names[i] for i in sorted_indices]
    
    # Calculate gaps between consecutive scores
    gaps = np.diff(sorted_scores)
    gap_sizes = np.abs(gaps)
    
    # Find significant gaps (larger than median gap * 1.5)
    median_gap = np.median(gap_sizes) if len(gap_sizes) > 0 else 0
    large_gaps = gap_sizes > (median_gap * 1.5)
    
    # Method 2: Use quantile-based approach as backup
    q75 = np.percentile(scores, 75)
    q50 = np.percentile(scores, 50) 
    q25 = np.percentile(scores, 25)
    
    # Method 3: Look for natural clusters using score distribution
    score_std = np.std(scores)
    score_mean = np.mean(scores)
    
    # Define breakpoints
    breakpoints = []
    tier_names = []
    
    if len(large_gaps) > 0:
        # Use gap-based method
        gap_indices = np.where(large_gaps)[0]
        for gap_idx in gap_indices[:3]:  # Use up to 3 major gaps
            breakpoints.append(sorted_scores[gap_idx + 1])
    else:
        # Use quantile-based method
        breakpoints = [q75, q50, q25]
    
    # Remove breakpoints that are too close together
    breakpoints = sorted(set(breakpoints), reverse=True)
    final_breakpoints = []
    for bp in breakpoints:
        if not final_breakpoints or (final_breakpoints[-1] - bp) > (score_std * 0.2):
            final_breakpoints.append(bp)
    
    # Create tiers
    tiers = []
    tier_labels = ['Excellent', 'Very Good', 'Good', 'Fair', 'Poor']
    
    # Sort scores for tier assignment
    for i, (score, name) in enumerate(zip(sorted_scores, sorted_names)):
        tier_level = 0
        for bp in final_breakpoints:
            if score < bp:
                tier_level += 1
            else:
                break
        
        tier_name = tier_labels[min(tier_level, len(tier_labels) - 1)]
        tiers.append({
            'rank': i + 1,
            'feature': name,
            'score': float(score),
            'tier': tier_name,
            'tier_level': tier_level
        })
    
    return {
        'breakpoints': final_breakpoints,
        'tiers': tiers,
        'tier_summary': {
            tier: len([t for t in tiers if t['tier'] == tier])
            for tier in set(t['tier'] for t in tiers)
        },
        'method_used': 'gap_based' if len(large_gaps) > 0 else 'quantile_based'
    }


def generate_comparison_analysis(all_results: Dict[str, Dict]) -> Dict[str, Any]:
    """Generate comparative analysis across all features"""
    
    # Rank features by separability potential
    feature_scores = []
    for feature_name, results in all_results.items():
        if results['combined_separability_score'] > 0:
            feature_scores.append({
                'feature': feature_name,
                'score': results['combined_separability_score'],
                'completeness': results['quality_indicators']['data_completeness'],
                'coverage': results['quality_indicators']['feature_coverage']
            })
    
    feature_scores.sort(key=lambda x: x['score'], reverse=True)
    
    # Find natural breakpoints in scores
    scores_only = [f['score'] for f in feature_scores if f['score'] > 0]
    feature_names = [f['feature'] for f in feature_scores if f['score'] > 0]
    
    breakpoint_analysis = find_natural_breakpoints(scores_only, feature_names)
    
    # Calculate overall statistics
    all_scores = [f['score'] for f in feature_scores if f['score'] > 0]
    completeness_scores = [f['completeness'] for f in feature_scores]
    
    comparison = {
        'total_features_analyzed': len(all_results),
        'features_with_data': len(feature_scores),
        'feature_ranking': feature_scores,
        'top_5_features': feature_scores[:5],
        'natural_tiers': breakpoint_analysis,
        'score_statistics': {
            'mean_score': float(np.mean(all_scores)) if all_scores else 0,
            'std_score': float(np.std(all_scores)) if all_scores else 0,
            'max_score': float(np.max(all_scores)) if all_scores else 0,
            'min_score': float(np.min(all_scores)) if all_scores else 0
        },
        'completeness_statistics': {
            'mean_completeness': float(np.mean(completeness_scores)),
            'min_completeness': float(np.min(completeness_scores)),
            'features_with_100_percent': sum(1 for c in completeness_scores if c >= 0.99)
        }
    }
    
    return comparison


def generate_text_report(df: pd.DataFrame, all_results: Dict[str, Dict], 
                        comparison: Dict[str, Any]) -> str:
    """Generate human-readable analysis report"""
    
    report = []
    report.append("=" * 80)
    report.append("STAGE RACE GRADIENT FEATURE SEPARABILITY ANALYSIS")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    report.append(f"Total stage competitions analyzed: {len(df)}")
    report.append(f"Filter criteria: competition_type='stage' AND winning_time > 90 minutes")
    report.append(f"Average finishers per race: {df['total_finishers'].mean():.1f}")
    report.append(f"Finisher range: {df['total_finishers'].min()}-{df['total_finishers'].max()}")
    report.append(f"Race categories: {', '.join(df['race_category'].value_counts().index.tolist())}")
    report.append("")
    
    # Overall findings
    report.append("KEY FINDINGS")
    report.append("-" * 40)
    report.append(f"Features analyzed: {comparison['total_features_analyzed']}")
    report.append(f"Features with separability potential: {comparison['features_with_data']}")
    report.append(f"Average separability score: {comparison['score_statistics']['mean_score']:.4f}")
    report.append(f"Best performing feature: {comparison['top_5_features'][0]['feature']} (score: {comparison['top_5_features'][0]['score']:.4f})")
    report.append("")
    
    # Natural tiers
    if comparison.get('natural_tiers', {}).get('tiers'):
        report.append("NATURAL FEATURE QUALITY TIERS")
        report.append("-" * 40)
        report.append(f"Breakpoint method: {comparison['natural_tiers']['method_used']}")
        report.append(f"Breakpoints found: {[f'{bp:.3f}' for bp in comparison['natural_tiers']['breakpoints']]}")
        report.append("")
        
        # Show tier summary
        tier_summary = comparison['natural_tiers']['tier_summary']
        for tier, count in tier_summary.items():
            report.append(f"{tier}: {count} features")
        report.append("")
        
        report.append("FEATURES BY TIER")
        report.append("-" * 40)
        report.append("Tier      | Rank | Feature Name                    | Score   | Completeness")
        report.append("-" * 80)
        
        for tier_info in comparison['natural_tiers']['tiers']:
            tier = tier_info['tier']
            rank = tier_info['rank']
            feature = tier_info['feature']
            score = tier_info['score']
            
            # Get completeness from feature ranking
            completeness = next((f['completeness'] for f in comparison['feature_ranking'] if f['feature'] == feature), 1.0)
            
            report.append(f"{tier:<9} | {rank:4d} | {feature:<30} | {score:7.4f} | {completeness:11.1%}")
    else:
        # Fallback to original ranking if no tiers found
        report.append("TOP 10 FEATURES FOR RACE KIND SEPARATION")
        report.append("-" * 40)
        report.append("Rank | Feature Name                    | Score   | Completeness | Coverage")
        report.append("-" * 75)
        
        for i, feature in enumerate(comparison['feature_ranking'][:10], 1):
            report.append(f"{i:4d} | {feature['feature']:<30} | {feature['score']:7.4f} | {feature['completeness']:11.1%} | {feature['coverage']:7.1%}")
    
    report.append("")
    
    # Detailed feature analysis
    report.append("DETAILED FEATURE ANALYSIS")
    report.append("-" * 40)
    
    for feature_name in comparison['feature_ranking'][:5]:  # Top 5 features
        feature_name = feature_name['feature']
        results = all_results[feature_name]
        
        report.append(f"\n{feature_name.upper()}")
        report.append("~" * len(feature_name))
        report.append(f"Competitions with data: {results['competitions_with_data']}/{results['total_competitions']} ({results['quality_indicators']['data_completeness']:.1%})")
        report.append(f"Combined separability score: {results['combined_separability_score']:.4f}")
        
        # Check if this is a gradient feature or quality indicator
        if 'slope_analysis' in results:
            # Gradient feature analysis
            if results['slope_analysis']:
                slope = results['slope_analysis']
                report.append(f"  Slope - Range: {slope.get('range', 0):.2e}, CV: {slope.get('cv', 0):.3f}, Std: {slope.get('std', 0):.2e}")
            
            # Volatility analysis  
            if results['volatility_analysis']:
                vol = results['volatility_analysis']
                report.append(f"  Volatility - Range: {vol.get('range', 0):.2e}, CV: {vol.get('cv', 0):.3f}, Std: {vol.get('std', 0):.2e}")
            
            # Monotonicity analysis
            if results['monotonicity_analysis']:
                mono = results['monotonicity_analysis']
                report.append(f"  Monotonicity - Range: {mono.get('range', 0):.3f}, Std: {mono.get('std', 0):.3f}, Distinct: {mono.get('distinct_values', 0)}")
            
            # Directional changes analysis
            if results['directional_changes_analysis']:
                dc = results['directional_changes_analysis']
                report.append(f"  Directional Changes - Range: {dc.get('range', 0):.0f}, CV: {dc.get('cv', 0):.3f}, Std: {dc.get('std', 0):.2f}")
        
        elif 'breakdown_analysis' in results:
            # Quality indicator analysis
            breakdown = results['breakdown_analysis']
            separability = results.get('separability_analysis', {})
            report.append(f"  No breakdown: {breakdown.get('no_breakdown_count', 0)} races ({breakdown.get('no_breakdown_percentage', 0):.1f}%)")
            report.append(f"  Breakdown points: {breakdown.get('distinct_breakdown_points', 0)} distinct values")
            report.append(f"  Entropy: {separability.get('entropy', 0):.3f}, Std: {separability.get('std', 0):.1f}")
    
    report.append("")
    
    # Recommendations
    report.append("RECOMMENDATIONS FOR RACE KIND CLASSIFICATION")
    report.append("-" * 50)
    
    top_features = [f['feature'] for f in comparison['feature_ranking'][:3]]
    report.append(f"1. Primary features for classification: {', '.join(top_features)}")
    
    high_coverage = [f['feature'] for f in comparison['feature_ranking'] if f['completeness'] >= 0.95][:5]
    report.append(f"2. Features with excellent data coverage: {', '.join(high_coverage)}")
    
    if comparison['score_statistics']['max_score'] > 0.1:
        report.append("3. Strong separability potential detected - proceed with clustering analysis")
    elif comparison['score_statistics']['max_score'] > 0.05:
        report.append("3. Moderate separability potential - combine multiple features for classification")
    else:
        report.append("3. Limited separability - may need additional feature engineering")
    
    report.append("")
    report.append("NEXT STEPS")
    report.append("-" * 40)
    report.append("1. Perform clustering analysis on top-ranked features")
    report.append("2. Validate clusters against known race characteristics")
    report.append("3. Develop machine learning classifier using selected features")
    report.append("4. Test classification accuracy on held-out data")
    
    return "\n".join(report)


def main():
    """Main analysis function"""
    output_dir = Path(__file__).parent
    
    print("Loading stage competition data...")
    db_path = find_database()
    df = get_stage_competition_data(db_path)
    
    print(f"Found {len(df)} stage competitions with winning_time > 90 minutes")
    
    # Define features to analyze (gradient features + quality indicators)
    gradient_features = [
        'variance_normalized',
        'variance_absolute', 
        'skewness_normalized',
        'skewness_absolute',
        'kurtosis_normalized',
        'kurtosis_absolute',
        'gini_coefficient',
        'clumpiness_score',
        'selection_metric',
        'biggest_group_metric',
        'nth_percentile_gap_5',
        'nth_percentile_gap_25',
        'nth_percentile_gap_50'
    ]
    
    # Add quality indicators as features (treat NULL as 0 = "no breakdown")
    quality_features = [
        'kurtosis_breakdown_point',
        'variance_breakdown_point'
    ]
    
    all_features = gradient_features + quality_features
    
    print("Analyzing all features...")
    all_results = {}
    
    # Analyze gradient features
    for i, feature in enumerate(gradient_features, 1):
        print(f"  [{i:2d}/{len(all_features)}] {feature}")
        all_results[feature] = analyze_gradient_feature_category(df, feature)
    
    # Analyze quality indicators
    for i, feature in enumerate(quality_features, len(gradient_features) + 1):
        print(f"  [{i:2d}/{len(all_features)}] {feature}")
        all_results[feature] = analyze_quality_indicator_feature(df, feature)
    
    print("Generating comparative analysis...")
    comparison = generate_comparison_analysis(all_results)
    
    print("Creating reports...")
    
    # Save machine-readable data
    output_data = {
        'analysis_metadata': {
            'generated_date': datetime.now().isoformat(),
            'total_competitions': len(df),
            'filter_criteria': "competition_type='stage' AND winning_time > 90 minutes",
            'gradient_features_analyzed': len(gradient_features),
            'quality_features_analyzed': len(quality_features),
            'total_features_analyzed': len(all_features)
        },
        'dataset_summary': {
            'total_competitions': len(df),
            'avg_finishers': float(df['total_finishers'].mean()),
            'finisher_range': [int(df['total_finishers'].min()), int(df['total_finishers'].max())],
            'race_categories': df['race_category'].value_counts().to_dict()
        },
        'feature_analysis': all_results,
        'comparative_analysis': comparison
    }
    
    # Save JSON data
    json_file = output_dir / "stage_separability_analysis.json"
    with open(json_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Generate and save text report
    text_report = generate_text_report(df, all_results, comparison)
    report_file = output_dir / "stage_separability_report.txt"
    with open(report_file, 'w') as f:
        f.write(text_report)
    
    # Save raw data for further analysis
    csv_file = output_dir / "stage_competitions_data.csv"
    df.to_csv(csv_file, index=False)
    
    print(f"\nAnalysis complete! Files saved:")
    print(f"  - Machine data: {json_file}")
    print(f"  - Text report: {report_file}")
    print(f"  - Raw data: {csv_file}")
    
    # Print key findings
    print(f"\nKEY FINDINGS:")
    print(f"  - {len(df)} stage competitions analyzed")
    print(f"  - Top feature: {comparison['top_5_features'][0]['feature']} (score: {comparison['top_5_features'][0]['score']:.4f})")
    print(f"  - {comparison['features_with_data']}/{comparison['total_features_analyzed']} features show separability potential")


if __name__ == "__main__":
    main()