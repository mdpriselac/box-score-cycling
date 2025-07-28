"""
Compare absolute feature analysis results between stages with and without kurtosis breakdowns.

This script:
1. Loads analysis results from both breakdown and no-breakdown analyses
2. Compares feature effectiveness between the two groups
3. Identifies features that work well for both or are specific to one group
4. Generates comparative reports and recommendations
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict


def load_analysis_results(analysis_dir: Path) -> Tuple[Dict, Dict]:
    """Load both breakdown and no-breakdown analysis results"""
    
    breakdown_file = analysis_dir / "absolute_breakdown_analysis.json"
    no_breakdown_file = analysis_dir / "absolute_no_breakdown_analysis.json"
    
    if not breakdown_file.exists():
        raise FileNotFoundError(f"Breakdown analysis file not found: {breakdown_file}")
    
    if not no_breakdown_file.exists():
        raise FileNotFoundError(f"No-breakdown analysis file not found: {no_breakdown_file}")
    
    with open(breakdown_file, 'r') as f:
        breakdown_results = json.load(f)
    
    with open(no_breakdown_file, 'r') as f:
        no_breakdown_results = json.load(f)
    
    return breakdown_results, no_breakdown_results


def compare_feature_effectiveness(breakdown_results: Dict, 
                                  no_breakdown_results: Dict) -> Dict[str, Any]:
    """Compare feature effectiveness between breakdown and no-breakdown groups"""
    
    # Get top combinations from both analyses
    breakdown_combos = breakdown_results.get('top_50_combinations', [])
    no_breakdown_combos = no_breakdown_results.get('top_50_combinations', [])
    
    # Create feature-percentile lookup for both groups
    breakdown_lookup = {}
    for combo in breakdown_combos:
        key = f"{combo['feature']}_{combo['percentile']}"
        breakdown_lookup[key] = combo['score']
    
    no_breakdown_lookup = {}
    for combo in no_breakdown_combos:
        key = f"{combo['feature']}_{combo['percentile']}"
        no_breakdown_lookup[key] = combo['score']
    
    # Find all unique feature-percentile combinations
    all_combinations = set(breakdown_lookup.keys()) | set(no_breakdown_lookup.keys())
    
    comparison_data = []
    for combo_key in all_combinations:
        feature, percentile = combo_key.rsplit('_', 1)
        breakdown_score = breakdown_lookup.get(combo_key, 0)
        no_breakdown_score = no_breakdown_lookup.get(combo_key, 0)
        
        comparison_data.append({
            'feature': feature,
            'percentile': int(percentile),
            'breakdown_score': breakdown_score,
            'no_breakdown_score': no_breakdown_score,
            'score_difference': breakdown_score - no_breakdown_score,
            'total_score': breakdown_score + no_breakdown_score,
            'breakdown_only': breakdown_score > 0 and no_breakdown_score == 0,
            'no_breakdown_only': breakdown_score == 0 and no_breakdown_score > 0,
            'both_groups': breakdown_score > 0 and no_breakdown_score > 0
        })
    
    # Sort by total score
    comparison_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    return {
        'comparison_data': comparison_data,
        'breakdown_specific': [c for c in comparison_data if c['breakdown_only']],
        'no_breakdown_specific': [c for c in comparison_data if c['no_breakdown_only']],
        'universal_features': [c for c in comparison_data if c['both_groups']],
        'breakdown_advantages': [c for c in comparison_data if c['score_difference'] > 0.1],
        'no_breakdown_advantages': [c for c in comparison_data if c['score_difference'] < -0.05]
    }


def analyze_percentile_preferences(breakdown_results: Dict, 
                                   no_breakdown_results: Dict) -> Dict[str, Any]:
    """Analyze which percentiles work best for each group"""
    
    breakdown_percentile_scores = defaultdict(list)
    no_breakdown_percentile_scores = defaultdict(list)
    
    # Collect scores by percentile for breakdown group
    for combo in breakdown_results.get('top_50_combinations', []):
        breakdown_percentile_scores[combo['percentile']].append(combo['score'])
    
    # Collect scores by percentile for no-breakdown group
    for combo in no_breakdown_results.get('top_50_combinations', []):
        no_breakdown_percentile_scores[combo['percentile']].append(combo['score'])
    
    # Calculate averages
    breakdown_percentile_avg = {
        p: np.mean(scores) for p, scores in breakdown_percentile_scores.items()
    }
    no_breakdown_percentile_avg = {
        p: np.mean(scores) for p, scores in no_breakdown_percentile_scores.items()
    }
    
    # Find best percentiles for each group
    breakdown_best_percentiles = sorted(breakdown_percentile_avg.items(), 
                                       key=lambda x: x[1], reverse=True)[:5]
    no_breakdown_best_percentiles = sorted(no_breakdown_percentile_avg.items(), 
                                          key=lambda x: x[1], reverse=True)[:5]
    
    return {
        'breakdown_percentile_scores': dict(breakdown_percentile_scores),
        'no_breakdown_percentile_scores': dict(no_breakdown_percentile_scores),
        'breakdown_percentile_avg': breakdown_percentile_avg,
        'no_breakdown_percentile_avg': no_breakdown_percentile_avg,
        'breakdown_best_percentiles': breakdown_best_percentiles,
        'no_breakdown_best_percentiles': no_breakdown_best_percentiles
    }


def identify_feature_categories(comparison: Dict[str, Any]) -> Dict[str, List]:
    """Categorize features based on their effectiveness patterns"""
    
    categories = {
        'breakdown_specialists': [],
        'no_breakdown_specialists': [],
        'universal_strong': [],
        'universal_weak': [],
        'percentile_sensitive': []
    }
    
    # Group by feature to analyze patterns
    feature_patterns = defaultdict(list)
    for combo in comparison['comparison_data']:
        feature_patterns[combo['feature']].append(combo)
    
    for feature, combos in feature_patterns.items():
        # Calculate total effectiveness
        total_breakdown = sum(c['breakdown_score'] for c in combos)
        total_no_breakdown = sum(c['no_breakdown_score'] for c in combos)
        total_combined = total_breakdown + total_no_breakdown
        
        # Find best combo for this feature
        best_combo = max(combos, key=lambda x: x['total_score'])
        
        if total_combined == 0:
            continue
        
        # Categorize based on patterns
        breakdown_ratio = total_breakdown / total_combined
        
        if breakdown_ratio > 0.8 and total_breakdown > 0.1:
            categories['breakdown_specialists'].append({
                'feature': feature,
                'breakdown_score': total_breakdown,
                'no_breakdown_score': total_no_breakdown,
                'best_percentile': best_combo['percentile'],
                'best_score': best_combo['total_score']
            })
        elif breakdown_ratio < 0.2 and total_no_breakdown > 0.05:
            categories['no_breakdown_specialists'].append({
                'feature': feature,
                'breakdown_score': total_breakdown,
                'no_breakdown_score': total_no_breakdown,
                'best_percentile': best_combo['percentile'],
                'best_score': best_combo['total_score']
            })
        elif total_breakdown > 0.1 and total_no_breakdown > 0.05:
            categories['universal_strong'].append({
                'feature': feature,
                'breakdown_score': total_breakdown,
                'no_breakdown_score': total_no_breakdown,
                'best_percentile': best_combo['percentile'],
                'best_score': best_combo['total_score']
            })
        
        # Check for percentile sensitivity
        percentile_scores = [c['total_score'] for c in combos]
        if len(percentile_scores) > 1 and np.std(percentile_scores) > 0.05:
            categories['percentile_sensitive'].append({
                'feature': feature,
                'score_std': np.std(percentile_scores),
                'score_range': max(percentile_scores) - min(percentile_scores),
                'best_percentile': best_combo['percentile']
            })
    
    # Sort each category
    for category in ['breakdown_specialists', 'no_breakdown_specialists', 'universal_strong']:
        categories[category].sort(key=lambda x: x['best_score'], reverse=True)
    
    categories['percentile_sensitive'].sort(key=lambda x: x['score_range'], reverse=True)
    
    return categories


def generate_comparison_report(breakdown_results: Dict,
                              no_breakdown_results: Dict,
                              comparison: Dict[str, Any],
                              percentile_analysis: Dict[str, Any],
                              feature_categories: Dict[str, List]) -> str:
    """Generate comprehensive comparison report"""
    
    report = []
    report.append("=" * 90)
    report.append("COMPARATIVE ANALYSIS: BREAKDOWN vs NO-BREAKDOWN STAGES")
    report.append("=" * 90)
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Dataset summary
    report.append("DATASET SUMMARY")
    report.append("-" * 40)
    breakdown_count = breakdown_results['analysis_metadata']['total_competitions']
    no_breakdown_count = no_breakdown_results['analysis_metadata']['total_competitions']
    total_count = breakdown_count + no_breakdown_count
    
    report.append(f"Total competitions analyzed: {total_count}")
    report.append(f"  With breakdowns: {breakdown_count} ({breakdown_count/total_count*100:.1f}%)")
    report.append(f"  Without breakdowns: {no_breakdown_count} ({no_breakdown_count/total_count*100:.1f}%)")
    report.append("")
    
    # Overall effectiveness comparison
    report.append("OVERALL EFFECTIVENESS COMPARISON")
    report.append("-" * 40)
    
    breakdown_top_scores = [c['breakdown_score'] for c in comparison['comparison_data'][:10]]
    no_breakdown_top_scores = [c['no_breakdown_score'] for c in comparison['comparison_data'][:10]]
    
    avg_breakdown = np.mean([s for s in breakdown_top_scores if s > 0])
    avg_no_breakdown = np.mean([s for s in no_breakdown_top_scores if s > 0])
    
    report.append(f"Average top-10 separability scores:")
    report.append(f"  Breakdown races: {avg_breakdown:.4f}")
    report.append(f"  No-breakdown races: {avg_no_breakdown:.4f}")
    report.append(f"  Ratio (breakdown/no-breakdown): {avg_breakdown/avg_no_breakdown:.2f}")
    report.append("")
    
    # Top universal features
    report.append("TOP 15 UNIVERSAL FEATURE-PERCENTILE COMBINATIONS")
    report.append("-" * 40)
    report.append("Rank | Feature                         | %ile | Breakdown | No-Break | Total   | Difference")
    report.append("-" * 100)
    
    universal_features = [c for c in comparison['comparison_data'] if c['both_groups']][:15]
    for i, combo in enumerate(universal_features, 1):
        report.append(f"{i:4d} | {combo['feature']:30} | {combo['percentile']:4d} | "
                     f"{combo['breakdown_score']:9.4f} | {combo['no_breakdown_score']:8.4f} | "
                     f"{combo['total_score']:7.4f} | {combo['score_difference']:10.4f}")
    
    report.append("")
    
    # Breakdown-specific features
    report.append("TOP BREAKDOWN-SPECIFIC FEATURES")
    report.append("-" * 40)
    
    breakdown_specific = comparison['breakdown_specific'][:10]
    if breakdown_specific:
        for combo in breakdown_specific:
            report.append(f"  {combo['feature']:30} at {combo['percentile']:3d}% (score: {combo['breakdown_score']:.4f})")
    else:
        report.append("  None found - all effective features also work for no-breakdown races")
    
    report.append("")
    
    # No-breakdown-specific features
    report.append("TOP NO-BREAKDOWN-SPECIFIC FEATURES")
    report.append("-" * 40)
    
    no_breakdown_specific = comparison['no_breakdown_specific'][:10]
    if no_breakdown_specific:
        for combo in no_breakdown_specific:
            report.append(f"  {combo['feature']:30} at {combo['percentile']:3d}% (score: {combo['no_breakdown_score']:.4f})")
    else:
        report.append("  None found - all effective features also work for breakdown races")
    
    report.append("")
    
    # Percentile preferences
    report.append("PERCENTILE PREFERENCES BY GROUP")
    report.append("-" * 40)
    
    report.append("Best percentiles for breakdown races:")
    for percentile, score in percentile_analysis['breakdown_best_percentiles'][:5]:
        report.append(f"  {percentile:3d}%: {score:.4f}")
    
    report.append("\nBest percentiles for no-breakdown races:")
    for percentile, score in percentile_analysis['no_breakdown_best_percentiles'][:5]:
        report.append(f"  {percentile:3d}%: {score:.4f}")
    
    report.append("")
    
    # Feature categories
    report.append("FEATURE CATEGORIZATION")
    report.append("-" * 40)
    
    # Breakdown specialists
    report.append(f"\nBreakdown Specialists ({len(feature_categories['breakdown_specialists'])} features):")
    for feat in feature_categories['breakdown_specialists'][:5]:
        report.append(f"  {feat['feature']:30} (breakdown: {feat['breakdown_score']:.3f}, "
                     f"no-breakdown: {feat['no_breakdown_score']:.3f})")
    
    # Universal strong features
    report.append(f"\nUniversal Strong Features ({len(feature_categories['universal_strong'])} features):")
    for feat in feature_categories['universal_strong'][:5]:
        report.append(f"  {feat['feature']:30} (breakdown: {feat['breakdown_score']:.3f}, "
                     f"no-breakdown: {feat['no_breakdown_score']:.3f})")
    
    # Percentile sensitive features
    report.append(f"\nPercentile Sensitive Features ({len(feature_categories['percentile_sensitive'])} features):")
    for feat in feature_categories['percentile_sensitive'][:5]:
        report.append(f"  {feat['feature']:30} (range: {feat['score_range']:.3f}, "
                     f"best at {feat['best_percentile']}%)")
    
    report.append("")
    
    # Recommendations
    report.append("STRATEGIC RECOMMENDATIONS")
    report.append("-" * 40)
    
    report.append("1. UNIFIED MODEL APPROACH:")
    if universal_features:
        top_universal = [f['feature'] for f in feature_categories['universal_strong'][:3]]
        report.append(f"   Use universal features: {', '.join(top_universal)}")
        
        common_percentiles = set(percentile_analysis['breakdown_best_percentiles'][0:2]) & \
                           set(percentile_analysis['no_breakdown_best_percentiles'][0:2])
        if common_percentiles:
            report.append(f"   Focus on percentiles: {', '.join(map(str, sorted(common_percentiles)))}")
    
    report.append("\n2. SEPARATE MODEL APPROACH:")
    report.append(f"   First classify breakdown vs no-breakdown using breakdown-point detection")
    
    if feature_categories['breakdown_specialists']:
        breakdown_features = [f['feature'] for f in feature_categories['breakdown_specialists'][:3]]
        report.append(f"   For breakdown races, emphasize: {', '.join(breakdown_features)}")
    
    if feature_categories['no_breakdown_specialists']:
        no_breakdown_features = [f['feature'] for f in feature_categories['no_breakdown_specialists'][:3]]
        report.append(f"   For no-breakdown races, emphasize: {', '.join(no_breakdown_features)}")
    else:
        report.append(f"   For no-breakdown races, use universal features with adjusted thresholds")
    
    report.append("\n3. FEATURE ENGINEERING:")
    report.append("   - Breakdown point itself is a strong discriminator")
    report.append("   - Consider percentile-specific feature combinations")
    report.append("   - Gap-based features show strong separability across both groups")
    
    report.append("\n4. PRACTICAL IMPLEMENTATION:")
    best_overall_percentiles = sorted(set(
        [p for p, _ in percentile_analysis['breakdown_best_percentiles'][:3]] +
        [p for p, _ in percentile_analysis['no_breakdown_best_percentiles'][:3]]
    ))
    report.append(f"   - Primary percentiles to analyze: {', '.join(map(str, best_overall_percentiles))}")
    report.append(f"   - Universal features provide good baseline performance")
    report.append(f"   - Specialized features can improve within-group discrimination")
    
    return "\n".join(report)


def main():
    """Main comparison function"""
    analysis_dir = Path(__file__).parent
    
    print("Loading analysis results...")
    try:
        breakdown_results, no_breakdown_results = load_analysis_results(analysis_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please run the individual analysis scripts first:")
        print("  1. python analyze_absolute_stages_with_breakdown.py")
        print("  2. python analyze_absolute_stages_no_breakdown.py")
        return
    
    print("Comparing feature effectiveness...")
    comparison = compare_feature_effectiveness(breakdown_results, no_breakdown_results)
    
    print("Analyzing percentile preferences...")
    percentile_analysis = analyze_percentile_preferences(breakdown_results, no_breakdown_results)
    
    print("Categorizing features...")
    feature_categories = identify_feature_categories(comparison)
    
    print("Generating comparison report...")
    
    # Save comprehensive comparison data
    output_data = {
        'analysis_metadata': {
            'generated_date': datetime.now().isoformat(),
            'breakdown_competitions': breakdown_results['analysis_metadata']['total_competitions'],
            'no_breakdown_competitions': no_breakdown_results['analysis_metadata']['total_competitions']
        },
        'comparison': comparison,
        'percentile_analysis': percentile_analysis,
        'feature_categories': feature_categories
    }
    
    # Save JSON data
    json_file = analysis_dir / "absolute_comparison_analysis.json"
    with open(json_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    # Generate and save comparison report
    comparison_report = generate_comparison_report(
        breakdown_results,
        no_breakdown_results,
        comparison,
        percentile_analysis,
        feature_categories
    )
    
    report_file = analysis_dir / "absolute_comparison_report.txt"
    with open(report_file, 'w') as f:
        f.write(comparison_report)
    
    # Save comparison data as CSV
    comparison_df = pd.DataFrame(comparison['comparison_data'])
    csv_file = analysis_dir / "absolute_feature_comparison.csv"
    comparison_df.to_csv(csv_file, index=False)
    
    print(f"\nComparison complete! Files saved:")
    print(f"  - Machine data: {json_file}")
    print(f"  - Text report: {report_file}")
    print(f"  - Comparison CSV: {csv_file}")
    
    # Print summary
    print(f"\nKEY FINDINGS:")
    breakdown_count = breakdown_results['analysis_metadata']['total_competitions']
    no_breakdown_count = no_breakdown_results['analysis_metadata']['total_competitions']
    print(f"  - {breakdown_count} breakdown vs {no_breakdown_count} no-breakdown competitions")
    print(f"  - {len(comparison['universal_features'])} universal feature-percentile combinations")
    print(f"  - {len(feature_categories['breakdown_specialists'])} breakdown-specialist features")
    print(f"  - {len(feature_categories['universal_strong'])} universally strong features")


if __name__ == "__main__":
    main()