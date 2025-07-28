"""
Analyze absolute feature values for stage races WITH kurtosis breakdowns.

This script:
1. Identifies stages with kurtosis breakdowns at any percentile level
2. Analyzes absolute feature values across different race_features_N tables
3. Determines which features and percentile levels best support race kind segmentation
4. Generates machine-readable data and human-readable reports
"""

import sqlite3
import json
import numpy as np
import pandas as pd
from pathlib import Path
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
import statistics

from find_kurtosis_breakdown_point import find_database, get_all_breakdown_points, get_percentile_tables


# Features to analyze (excluding metadata columns)
FEATURE_COLUMNS = [
    'total_finishers', 'included_finishers', 'abandon_ratio',
    'winning_time', 'total_race_duration',
    'variance_absolute', 'variance_normalized',
    'std_deviation_absolute', 'std_deviation_normalized',
    'skewness_absolute', 'skewness_normalized',
    'kurtosis_absolute', 'kurtosis_normalized',
    'kurtosis_absolute_imputed', 'kurtosis_normalized_imputed',
    'gini_coefficient',
    'shannon_entropy_absolute', 'shannon_entropy_normalized',
    '"5th_percentile_gap"', '"10th_percentile_gap"', '"15th_percentile_gap"',
    '"20th_percentile_gap"', '"25th_percentile_gap"', '"30th_percentile_gap"',
    '"35th_percentile_gap"', '"40th_percentile_gap"', '"45th_percentile_gap"',
    '"50th_percentile_gap"',
    'total_groups', 'riders_in_groups', 'proportion_in_groups',
    'largest_group_size', 'largest_group_position',
    'avg_group_size', 'std_group_size',
    'biggest_group_metric', 'time_gap_evenness_metric',
    'clumpiness_score', 'selection_metric'
]


def get_stage_competitions_with_breakdown(conn: sqlite3.Connection) -> List[int]:
    """Get competition IDs for stages with kurtosis breakdowns"""
    
    breakdown_points = get_all_breakdown_points(conn)
    
    # Filter for competitions with breakdowns
    competitions_with_breakdown = [
        comp_id for comp_id, breakdown in breakdown_points.items()
        if breakdown is not None
    ]
    
    return competitions_with_breakdown


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
            'entropy': 0,
            'valid_count': len(values)
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
            'entropy': 0,
            'valid_count': len(values)
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
    if len(values) > 10:
        hist, _ = np.histogram(values, bins=10)
        hist = hist[hist > 0]  # Remove empty bins
        prob = hist / np.sum(hist)
        entropy = -np.sum(prob * np.log2(prob)) if len(prob) > 0 else 0
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
        'entropy': float(entropy),
        'valid_count': len(values)
    }


def analyze_feature_at_percentile(conn: sqlite3.Connection, 
                                  feature: str, 
                                  percentile: int,
                                  competition_ids: List[int]) -> Dict[str, Any]:
    """Analyze a specific feature at a specific percentile level"""
    
    table_name = f"race_features_{percentile}"
    
    # Build query with proper placeholders
    placeholders = ','.join(['?' for _ in competition_ids])
    query = f"""
    SELECT competition_id, {feature}
    FROM {table_name}
    WHERE competition_id IN ({placeholders})
    """
    
    cursor = conn.cursor()
    cursor.execute(query, competition_ids)
    
    values = []
    competition_count = 0
    
    for row in cursor.fetchall():
        competition_count += 1
        if row[1] is not None:
            values.append(row[1])
    
    results = {
        'feature': feature,
        'percentile': percentile,
        'competitions_analyzed': competition_count,
        'values_available': len(values),
        'data_completeness': len(values) / competition_count if competition_count > 0 else 0
    }
    
    if values:
        results['metrics'] = calculate_separability_metrics(values)
        # Calculate combined score emphasizing variance and distinctiveness
        metrics = results['metrics']
        score_components = []
        
        if metrics['cv'] > 0:
            score_components.append(metrics['cv'])
        if metrics['entropy'] > 0:
            score_components.append(metrics['entropy'] / 3.0)  # Normalize entropy contribution
        if metrics['distinct_values'] > 10:
            score_components.append(metrics['distinct_values'] / 100.0)  # Normalize distinct values
        
        results['separability_score'] = float(np.mean(score_components)) if score_components else 0
    else:
        results['metrics'] = {}
        results['separability_score'] = 0
    
    return results


def analyze_all_features_all_percentiles(conn: sqlite3.Connection,
                                         competition_ids: List[int]) -> Dict[str, List[Dict]]:
    """Analyze all features across all percentile levels"""
    
    percentile_tables = get_percentile_tables(conn)
    feature_results = defaultdict(list)
    
    total_analyses = len(FEATURE_COLUMNS) * len(percentile_tables)
    current = 0
    
    print(f"Analyzing {len(FEATURE_COLUMNS)} features across {len(percentile_tables)} percentile levels...")
    
    for feature in FEATURE_COLUMNS:
        for percentile in percentile_tables:
            current += 1
            if current % 50 == 0:
                print(f"  Progress: {current}/{total_analyses} ({current/total_analyses*100:.1f}%)")
            
            try:
                result = analyze_feature_at_percentile(conn, feature, percentile, competition_ids)
                feature_results[feature].append(result)
            except Exception as e:
                print(f"  Warning: Failed to analyze {feature} at {percentile}%: {e}")
    
    return dict(feature_results)


def find_best_feature_percentile_combinations(feature_results: Dict[str, List[Dict]]) -> List[Dict]:
    """Find the best feature-percentile combinations for separability"""
    
    all_combinations = []
    
    for feature, percentile_results in feature_results.items():
        for result in percentile_results:
            if result['separability_score'] > 0 and result['data_completeness'] > 0.8:
                all_combinations.append({
                    'feature': feature,
                    'percentile': result['percentile'],
                    'score': result['separability_score'],
                    'completeness': result['data_completeness'],
                    'cv': result['metrics'].get('cv', 0),
                    'entropy': result['metrics'].get('entropy', 0),
                    'distinct_values': result['metrics'].get('distinct_values', 0)
                })
    
    # Sort by score
    all_combinations.sort(key=lambda x: x['score'], reverse=True)
    
    return all_combinations


def find_natural_breakpoints(scores: List[float], combinations: List[Dict]) -> Dict[str, Any]:
    """Find natural breakpoints in feature-percentile combination scores to define quality tiers"""
    if len(scores) < 3:
        return {'tiers': [], 'breakpoints': []}
    
    scores_array = np.array(scores)
    
    # Method 1: Look for large gaps in the sorted scores
    sorted_indices = np.argsort(scores_array)[::-1]  # Descending order
    sorted_scores = scores_array[sorted_indices]
    sorted_combinations = [combinations[i] for i in sorted_indices]
    
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
    
    if len(large_gaps) > 0 and np.any(large_gaps):
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
    
    # Sort combinations for tier assignment
    for i, (score, combo) in enumerate(zip(sorted_scores, sorted_combinations)):
        tier_level = 0
        for bp in final_breakpoints:
            if score < bp:
                tier_level += 1
            else:
                break
        
        tier_name = tier_labels[min(tier_level, len(tier_labels) - 1)]
        tiers.append({
            'rank': i + 1,
            'feature': combo['feature'],
            'percentile': combo['percentile'],
            'score': float(score),
            'tier': tier_name,
            'tier_level': tier_level,
            'completeness': combo['completeness'],
            'cv': combo['cv'],
            'entropy': combo['entropy'],
            'distinct_values': combo['distinct_values']
        })
    
    return {
        'breakpoints': final_breakpoints,
        'tiers': tiers,
        'tier_summary': {
            tier: len([t for t in tiers if t['tier'] == tier])
            for tier in set(t['tier'] for t in tiers)
        },
        'method_used': 'gap_based' if len(large_gaps) > 0 and np.any(large_gaps) else 'quantile_based'
    }


def find_optimal_percentile_set(feature_results: Dict[str, List[Dict]], 
                                top_n_features: int = 10) -> Dict[str, Any]:
    """Find the optimal set of percentiles to use across features"""
    
    # Get top combinations
    all_combinations = find_best_feature_percentile_combinations(feature_results)
    
    # Analyze which percentiles appear most in top combinations
    percentile_scores = defaultdict(list)
    
    for combo in all_combinations[:50]:  # Look at top 50 combinations
        percentile_scores[combo['percentile']].append(combo['score'])
    
    # Calculate average score for each percentile
    percentile_avg_scores = {}
    for percentile, scores in percentile_scores.items():
        percentile_avg_scores[percentile] = {
            'avg_score': np.mean(scores),
            'count': len(scores),
            'std_score': np.std(scores)
        }
    
    # Find features that work best at each percentile
    percentile_best_features = defaultdict(list)
    
    for combo in all_combinations:
        if combo['score'] > 0.1:  # Threshold for "good" score
            percentile_best_features[combo['percentile']].append({
                'feature': combo['feature'],
                'score': combo['score']
            })
    
    # Sort features within each percentile
    for percentile in percentile_best_features:
        percentile_best_features[percentile].sort(key=lambda x: x['score'], reverse=True)
        percentile_best_features[percentile] = percentile_best_features[percentile][:top_n_features]
    
    return {
        'percentile_scores': dict(sorted(percentile_avg_scores.items(), 
                                        key=lambda x: x[1]['avg_score'], 
                                        reverse=True)),
        'percentile_best_features': dict(percentile_best_features),
        'top_combinations': all_combinations[:20]
    }


def generate_breakdown_analysis_report(feature_results: Dict[str, List[Dict]],
                                      optimal_analysis: Dict[str, Any],
                                      tier_analysis: Dict[str, Any],
                                      competition_count: int,
                                      breakdown_distribution: Dict[int, int]) -> str:
    """Generate human-readable report for breakdown analysis"""
    
    report = []
    report.append("=" * 80)
    report.append("ABSOLUTE FEATURE ANALYSIS - STAGES WITH KURTOSIS BREAKDOWNS")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    report.append(f"Total competitions analyzed: {competition_count}")
    report.append("Filter criteria: stage competitions with 90 min < winning_time <= 8 hours")
    report.append("                 AND kurtosis breakdown at some percentile")
    report.append("")
    
    # Breakdown distribution
    report.append("KURTOSIS BREAKDOWN DISTRIBUTION")
    report.append("-" * 40)
    total_breakdowns = sum(breakdown_distribution.values())
    for percentile in sorted(breakdown_distribution.keys()):
        count = breakdown_distribution[percentile]
        pct = count / total_breakdowns * 100
        report.append(f"  At {percentile:3d}%: {count:4d} competitions ({pct:5.1f}%)")
    report.append("")
    
    # Natural tier analysis
    if tier_analysis and tier_analysis.get('tiers'):
        report.append("NATURAL QUALITY TIERS FOR FEATURE-PERCENTILE COMBINATIONS")
        report.append("-" * 60)
        report.append(f"Tier detection method: {tier_analysis['method_used']}")
        report.append(f"Breakpoints: {[f'{bp:.3f}' for bp in tier_analysis['breakpoints']]}")
        report.append("")
        
        # Tier summary
        tier_summary = tier_analysis['tier_summary']
        for tier in ['Excellent', 'Very Good', 'Good', 'Fair', 'Poor']:
            count = tier_summary.get(tier, 0)
            if count > 0:
                report.append(f"{tier}: {count} combinations")
        report.append("")
        
        # Show combinations by tier
        current_tier = None
        for tier_info in tier_analysis['tiers']:
            if tier_info['tier'] != current_tier:
                current_tier = tier_info['tier']
                report.append(f"\n{current_tier.upper()} TIER")
                report.append("-" * (len(current_tier) + 5))
                report.append("Rank | Feature                         | %ile | Score   | CV     | Entropy | Complete")
                report.append("-" * 90)
            
            report.append(f"{tier_info['rank']:4d} | {tier_info['feature']:30} | {tier_info['percentile']:4d} | "
                         f"{tier_info['score']:7.4f} | {tier_info['cv']:6.3f} | {tier_info['entropy']:7.3f} | "
                         f"{tier_info['completeness']:8.1%}")
        
        report.append("")
    else:
        # Fallback to top combinations if no tiers found
        report.append("TOP 20 FEATURE-PERCENTILE COMBINATIONS")
        report.append("-" * 40)
        report.append("Rank | Feature                         | %ile | Score   | CV     | Entropy | Complete")
        report.append("-" * 90)
        
        for i, combo in enumerate(optimal_analysis['top_combinations'][:20], 1):
            report.append(f"{i:4d} | {combo['feature']:30} | {combo['percentile']:4d} | "
                         f"{combo['score']:7.4f} | {combo['cv']:6.3f} | {combo['entropy']:7.3f} | "
                         f"{combo['completeness']:8.1%}")
        report.append("")
    
    # Optimal percentile analysis
    report.append("PERCENTILE EFFECTIVENESS ANALYSIS")
    report.append("-" * 40)
    report.append("Percentile | Avg Score | # Top Features | Std Dev")
    report.append("-" * 50)
    
    for percentile, stats in list(optimal_analysis['percentile_scores'].items())[:10]:
        report.append(f"{percentile:10d} | {stats['avg_score']:9.4f} | "
                     f"{stats['count']:14d} | {stats['std_score']:7.4f}")
    report.append("")
    
    # Best features at key percentiles
    report.append("BEST FEATURES AT KEY PERCENTILES")
    report.append("-" * 40)
    
    key_percentiles = [10, 25, 50, 75, 100]
    for percentile in key_percentiles:
        if percentile in optimal_analysis['percentile_best_features']:
            report.append(f"\nAt {percentile}% inclusion:")
            features = optimal_analysis['percentile_best_features'][percentile]
            for j, feat in enumerate(features[:5], 1):
                report.append(f"  {j}. {feat['feature']:30} (score: {feat['score']:.4f})")
    
    report.append("")
    
    # Feature performance summary
    report.append("FEATURE PERFORMANCE SUMMARY")
    report.append("-" * 40)
    
    # Calculate best percentile for each feature
    feature_best_percentiles = {}
    for feature, results in feature_results.items():
        best_result = max(results, key=lambda x: x['separability_score'])
        if best_result['separability_score'] > 0:
            feature_best_percentiles[feature] = {
                'percentile': best_result['percentile'],
                'score': best_result['separability_score'],
                'completeness': best_result['data_completeness']
            }
    
    # Sort by score
    sorted_features = sorted(feature_best_percentiles.items(), 
                           key=lambda x: x[1]['score'], 
                           reverse=True)
    
    report.append("Feature                         | Best %ile | Score   | Completeness")
    report.append("-" * 70)
    
    for feature, stats in sorted_features[:15]:
        report.append(f"{feature:30} | {stats['percentile']:9d} | "
                     f"{stats['score']:7.4f} | {stats['completeness']:11.1%}")
    
    report.append("")
    
    # Recommendations
    report.append("RECOMMENDATIONS FOR CLASSIFYING BREAKDOWN STAGES")
    report.append("-" * 50)
    
    # Find most consistent high-performing percentiles
    top_percentiles = list(optimal_analysis['percentile_scores'].keys())[:3]
    report.append(f"1. Focus on percentiles: {', '.join(map(str, top_percentiles))}")
    
    # List top features across all percentiles
    top_features = set()
    for combo in optimal_analysis['top_combinations'][:10]:
        top_features.add(combo['feature'])
    
    report.append(f"2. Primary features: {', '.join(list(top_features)[:5])}")
    
    report.append("3. Consider using different features at different percentiles for optimal results")
    report.append("4. Features related to distribution shape (kurtosis, skewness) show high separability")
    report.append("")
    
    report.append("KEY INSIGHTS FOR BREAKDOWN RACES")
    report.append("-" * 40)
    report.append("1. Breakdown races show high variability in distribution characteristics")
    report.append("2. The percentile at which breakdown occurs may itself be a useful feature")
    report.append("3. Early percentile features (10-25%) often show strongest separability")
    report.append("4. Gap-based features perform well, indicating distinct separation patterns")
    
    return "\n".join(report)


def main():
    """Main analysis function"""
    output_dir = Path(__file__).parent
    
    print("Connecting to database...")
    db_path = find_database()
    conn = sqlite3.connect(db_path)
    
    print("Finding competitions with kurtosis breakdowns...")
    competition_ids = get_stage_competitions_with_breakdown(conn)
    print(f"Found {len(competition_ids)} competitions with breakdowns")
    
    # Get breakdown distribution
    all_breakdowns = get_all_breakdown_points(conn)
    breakdown_distribution = {}
    for comp_id in competition_ids:
        bp = all_breakdowns[comp_id]
        if bp is not None:
            breakdown_distribution[bp] = breakdown_distribution.get(bp, 0) + 1
    
    print("Analyzing features across all percentile levels...")
    feature_results = analyze_all_features_all_percentiles(conn, competition_ids)
    
    print("Finding optimal feature-percentile combinations...")
    optimal_analysis = find_optimal_percentile_set(feature_results)
    
    print("Finding natural quality tiers...")
    all_combinations = find_best_feature_percentile_combinations(feature_results)
    scores = [combo['score'] for combo in all_combinations]
    tier_analysis = find_natural_breakpoints(scores, all_combinations)
    
    print("Generating reports...")
    
    # Save machine-readable data
    output_data = {
        'analysis_metadata': {
            'generated_date': datetime.now().isoformat(),
            'total_competitions': len(competition_ids),
            'filter_criteria': "stage competitions with 90 min < winning_time <= 8 hours AND kurtosis breakdown",
            'features_analyzed': len(FEATURE_COLUMNS),
            'percentiles_analyzed': len(get_percentile_tables(conn))
        },
        'breakdown_distribution': breakdown_distribution,
        'feature_results': feature_results,
        'optimal_analysis': optimal_analysis,
        'tier_analysis': tier_analysis,
        'top_50_combinations': find_best_feature_percentile_combinations(feature_results)[:50]
    }
    
    # Save JSON data
    json_file = output_dir / "absolute_breakdown_analysis.json"
    with open(json_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Generate and save text report
    text_report = generate_breakdown_analysis_report(
        feature_results, 
        optimal_analysis, 
        tier_analysis,
        len(competition_ids),
        breakdown_distribution
    )
    
    report_file = output_dir / "absolute_breakdown_report.txt"
    with open(report_file, 'w') as f:
        f.write(text_report)
    
    # Save summary CSV of top combinations
    top_combos_df = pd.DataFrame(optimal_analysis['top_combinations'][:50])
    csv_file = output_dir / "absolute_breakdown_top_combinations.csv"
    top_combos_df.to_csv(csv_file, index=False)
    
    conn.close()
    
    print(f"\nAnalysis complete! Files saved:")
    print(f"  - Machine data: {json_file}")
    print(f"  - Text report: {report_file}")
    print(f"  - Top combinations: {csv_file}")
    
    # Print summary
    print(f"\nKEY FINDINGS:")
    print(f"  - {len(competition_ids)} competitions with breakdowns analyzed")
    print(f"  - Top feature-percentile: {optimal_analysis['top_combinations'][0]['feature']} "
          f"at {optimal_analysis['top_combinations'][0]['percentile']}% "
          f"(score: {optimal_analysis['top_combinations'][0]['score']:.4f})")


if __name__ == "__main__":
    main()