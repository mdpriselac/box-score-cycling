"""
Analyze race data to understand null kurtosis/skewness values, finisher counts, and identify time trials.
"""

import json
import sqlite3
from collections import defaultdict
from typing import Dict, List, Tuple


def get_db_connection():
    """Connect to the database."""
    return sqlite3.connect('~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db')


def analyze_null_kurtosis_skewness():
    """Analyze null kurtosis and skewness values across race features."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total counts by tour level and race type
    cursor.execute("""
        SELECT race_category, competition_type, COUNT(DISTINCT competition_id) as total_count
        FROM race_features_100
        GROUP BY race_category, competition_type
    """)
    
    total_counts = {}
    for row in cursor.fetchall():
        key = f"{row[0]}_{row[1]}"
        total_counts[key] = row[2]
    
    # Analyze null values for each race_feature_N table
    null_analysis = {}
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    
    for table in race_feature_tables:
        null_analysis[table] = {
            'by_tour_level': defaultdict(lambda: {'null_count': 0, 'total_count': 0}),
            'by_race_type': defaultdict(lambda: {'null_count': 0, 'total_count': 0}),
            'by_combination': defaultdict(lambda: {'null_count': 0, 'total_count': 0}),
            'detailed_analysis': []
        }
        
        # Get competitions with null kurtosis or skewness
        cursor.execute(f"""
            SELECT competition_id, race_category, competition_type, 
                   kurtosis_absolute, kurtosis_normalized,
                   skewness_absolute, skewness_normalized,
                   variance_absolute, variance_normalized,
                   total_finishers, included_finishers,
                   std_deviation_absolute, std_deviation_normalized
            FROM {table}
            WHERE kurtosis_absolute IS NULL OR kurtosis_normalized IS NULL 
               OR skewness_absolute IS NULL OR skewness_normalized IS NULL
        """)
        
        null_competitions = cursor.fetchall()
        
        # Analyze causes of null values
        cause_counts = {'no_variance': 0, 'insufficient_distinct_times': 0, 'mystery': 0}
        
        for comp in null_competitions:
            comp_id, tour_level, race_type = comp[0], comp[1], comp[2]
            variance_abs, variance_norm = comp[7], comp[8]
            std_abs, std_norm = comp[11], comp[12]
            
            # Get distinct finishing times for this competition
            cursor.execute("""
                SELECT COUNT(DISTINCT time_gap) as distinct_times
                FROM rider_results
                WHERE competition_id = ? AND time_gap IS NOT NULL
            """, (comp_id,))
            
            distinct_times_result = cursor.fetchone()
            distinct_times = distinct_times_result[0] if distinct_times_result else 0
            
            # Determine cause
            cause = "mystery"
            if variance_abs == 0 or variance_norm == 0:
                cause = "no_variance"
            elif distinct_times < 3:  # Need at least 3 distinct values for skewness/kurtosis
                cause = "insufficient_distinct_times"
            
            cause_counts[cause] += 1
            
            null_analysis[table]['detailed_analysis'].append({
                'competition_id': comp_id,
                'tour_level': tour_level,
                'race_type': race_type,
                'cause': cause,
                'variance_absolute': variance_abs,
                'variance_normalized': variance_norm,
                'total_finishers': comp[9],
                'included_finishers': comp[10],
                'distinct_finishing_times': distinct_times
            })
        
            # Update counts
            null_analysis[table]['by_tour_level'][tour_level]['null_count'] += 1
            null_analysis[table]['by_race_type'][race_type]['null_count'] += 1
            combo_key = f"{tour_level}_{race_type}"
            null_analysis[table]['by_combination'][combo_key]['null_count'] += 1
        
        null_analysis[table]['cause_counts'] = cause_counts
        
        # Get total counts for this table
        cursor.execute(f"""
            SELECT race_category, competition_type, COUNT(DISTINCT competition_id) as count
            FROM {table}
            GROUP BY race_category, competition_type
        """)
        
        for row in cursor.fetchall():
            tour_level, race_type = row[0], row[1]
            count = row[2]
            
            null_analysis[table]['by_tour_level'][tour_level]['total_count'] += count
            null_analysis[table]['by_race_type'][race_type]['total_count'] += count
            combo_key = f"{tour_level}_{race_type}"
            null_analysis[table]['by_combination'][combo_key]['total_count'] = count
    
    # Overall analysis - competitions with at least one null value
    overall_nulls = defaultdict(set)
    
    for table in race_feature_tables:
        cursor.execute(f"""
            SELECT competition_id, race_category, competition_type
            FROM {table}
            WHERE kurtosis_absolute IS NULL OR kurtosis_normalized IS NULL 
               OR skewness_absolute IS NULL OR skewness_normalized IS NULL
        """)
        
        for row in cursor.fetchall():
            combo_key = f"{row[1]}_{row[2]}"
            overall_nulls[combo_key].add(row[0])
    
    # Calculate overall statistics
    overall_analysis = {
        'by_combination': {}
    }
    
    for combo_key, comp_ids in overall_nulls.items():
        null_count = len(comp_ids)
        total_count = total_counts.get(combo_key, 0)
        proportion = null_count / total_count if total_count > 0 else 0
        
        overall_analysis['by_combination'][combo_key] = {
            'null_count': null_count,
            'total_count': total_count,
            'proportion': proportion
        }
    
    conn.close()
    return null_analysis, overall_analysis


def analyze_finisher_counts():
    """Analyze the drop-off in competition counts across race_feature_N tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    finisher_analysis = {}
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    
    # Get counts for each table by tour level and race type
    for table in race_feature_tables:
        cursor.execute(f"""
            SELECT race_category, competition_type, COUNT(DISTINCT competition_id) as count
            FROM {table}
            GROUP BY race_category, competition_type
        """)
        
        finisher_analysis[table] = {
            'by_tour_level': defaultdict(int),
            'by_race_type': defaultdict(int),
            'by_combination': {},
            'total': 0
        }
        
        for row in cursor.fetchall():
            tour_level, race_type, count = row[0], row[1], row[2]
            finisher_analysis[table]['by_tour_level'][tour_level] += count
            finisher_analysis[table]['by_race_type'][race_type] += count
            combo_key = f"{tour_level}_{race_type}"
            finisher_analysis[table]['by_combination'][combo_key] = count
            finisher_analysis[table]['total'] += count
    
    # Calculate drop-off rates
    drop_off_analysis = {
        'overall': {},
        'by_tour_level': defaultdict(dict),
        'by_race_type': defaultdict(dict),
        'by_combination': defaultdict(dict)
    }
    
    base_counts = finisher_analysis['race_features_100']
    
    # Skip race_features_100 since it's the baseline
    other_tables = [t for t in race_feature_tables if t != 'race_features_100']
    for table in other_tables:
        current_counts = finisher_analysis[table]
        
        # Overall drop-off
        drop_off_analysis['overall'][table] = {
            'count': current_counts['total'],
            'drop_from_100': 1 - (current_counts['total'] / base_counts['total']) if base_counts['total'] > 0 else 0
        }
        
        # By tour level
        for tour_level in base_counts['by_tour_level']:
            base = base_counts['by_tour_level'][tour_level]
            current = current_counts['by_tour_level'].get(tour_level, 0)
            drop_off_analysis['by_tour_level'][tour_level][table] = {
                'count': current,
                'drop_from_100': 1 - (current / base) if base > 0 else 0
            }
        
        # By race type
        for race_type in base_counts['by_race_type']:
            base = base_counts['by_race_type'][race_type]
            current = current_counts['by_race_type'].get(race_type, 0)
            drop_off_analysis['by_race_type'][race_type][table] = {
                'count': current,
                'drop_from_100': 1 - (current / base) if base > 0 else 0
            }
        
        # By combination
        for combo_key in base_counts['by_combination']:
            base = base_counts['by_combination'][combo_key]
            current = current_counts['by_combination'].get(combo_key, 0)
            drop_off_analysis['by_combination'][combo_key][table] = {
                'count': current,
                'drop_from_100': 1 - (current / base) if base > 0 else 0
            }
    
    conn.close()
    return finisher_analysis, drop_off_analysis


def analyze_time_trials():
    """Analyze stage races shorter than 90 minutes to identify potential time trials."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all stage races under 90 minutes (5400 seconds)
    cursor.execute("""
        SELECT c.id, c.winning_time, rf.race_category
        FROM competitions c
        JOIN race_features_100 rf ON c.id = rf.competition_id
        WHERE c.competition_type = 'stage' 
          AND c.winning_time < 5400 
          AND c.winning_time > 0
    """)
    
    time_trial_data = cursor.fetchall()
    
    # Create histogram buckets (10-minute intervals from 0 to 90)
    buckets = [(i*600, (i+1)*600) for i in range(9)]  # 0-10, 10-20, ..., 80-90
    bucket_labels = [f"{i*10}-{(i+1)*10}" for i in range(9)]
    
    # Initialize histogram data
    histogram = {
        'overall': {label: 0 for label in bucket_labels},
        'by_tour_level': {
            'wt': {label: 0 for label in bucket_labels},
            'pro': {label: 0 for label in bucket_labels},
            'd1': {label: 0 for label in bucket_labels}
        }
    }
    
    # Count by tour level
    tour_level_counts = {'wt': 0, 'pro': 0, 'd1': 0}
    
    # Fill histogram
    for comp_id, winning_time, tour_level in time_trial_data:
        # Find appropriate bucket
        for i, (start, end) in enumerate(buckets):
            if start <= winning_time < end:
                histogram['overall'][bucket_labels[i]] += 1
                if tour_level in histogram['by_tour_level']:
                    histogram['by_tour_level'][tour_level][bucket_labels[i]] += 1
                    tour_level_counts[tour_level] += 1
                break
    
    # Calculate distributions (proportions)
    total_count = len(time_trial_data)
    distribution = {
        'overall': {
            'count': total_count,
            'histogram': histogram['overall'],
            'distribution': {k: v/total_count if total_count > 0 else 0 
                           for k, v in histogram['overall'].items()}
        },
        'by_tour_level': {}
    }
    
    for tour_level in ['wt', 'pro', 'd1']:
        count = tour_level_counts[tour_level]
        distribution['by_tour_level'][tour_level] = {
            'count': count,
            'histogram': histogram['by_tour_level'][tour_level],
            'distribution': {k: v/count if count > 0 else 0 
                           for k, v in histogram['by_tour_level'][tour_level].items()}
        }
    
    conn.close()
    return distribution


def generate_markdown_report(null_analysis, overall_null_analysis, finisher_analysis, 
                           drop_off_analysis, time_trial_analysis):
    """Generate a comprehensive markdown report."""
    report = []
    report.append("# Race Data Analysis Report\n")
    
    # Section 1: Null Kurtosis and Skewness Analysis
    report.append("## 1. Null Kurtosis and Skewness Analysis\n")
    
    # Overall summary
    report.append("### Overall Summary\n")
    report.append("Competitions with at least one null kurtosis/skewness value:\n")
    report.append("| Tour Level | Race Type | Null Count | Total Count | Proportion |")
    report.append("|------------|-----------|------------|-------------|------------|")
    
    for combo_key, stats in sorted(overall_null_analysis['by_combination'].items()):
        tour_level, race_type = combo_key.split('_', 1)
        report.append(f"| {tour_level} | {race_type} | {stats['null_count']} | "
                     f"{stats['total_count']} | {stats['proportion']:.3f} |")
    
    # Detailed analysis by race_feature_N
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    for table in race_feature_tables:
        if table in null_analysis:
            report.append(f"\n### {table}\n")
            
            # Cause analysis
            if 'cause_counts' in null_analysis[table]:
                report.append("#### Causes of Null Values:")
                for cause in ['no_variance', 'insufficient_distinct_times', 'mystery']:
                    count = null_analysis[table]['cause_counts'].get(cause, 0)
                    report.append(f"- {cause}: {count} competitions")
            
            # Tour level x Race type matrix
            report.append("\n#### Null Value Distribution Matrix:")
            report.append("| Tour Level | Race Type | Null Count | Total Count | Proportion |")
            report.append("|------------|-----------|------------|-------------|------------|")
            
            for combo_key, stats in sorted(null_analysis[table]['by_combination'].items()):
                tour_level, race_type = combo_key.split('_', 1)
                null_count = stats['null_count']
                total_count = stats['total_count']
                proportion = null_count / total_count if total_count > 0 else 0
                report.append(f"| {tour_level} | {race_type} | {null_count} | "
                             f"{total_count} | {proportion:.3f} |")
    
    # Section 2: Finisher Count Analysis
    report.append("\n## 2. Reduced Finisher Count Analysis\n")
    
    # Overall drop-off
    report.append("### Overall Competition Count Drop-off\n")
    report.append("| Table | Count | Drop from race_features_100 |")
    report.append("|-------|-------|----------------------------|")
    report.append(f"| race_features_100 | {finisher_analysis['race_features_100']['total']} | 0.000 |")
    
    race_feature_tables_except_100 = [f'race_features_{i}' for i in range(10, 100, 5)]
    for table in race_feature_tables_except_100:
        stats = drop_off_analysis['overall'].get(table, {})
        report.append(f"| {table} | {stats.get('count', 0)} | "
                     f"{stats.get('drop_from_100', 0):.3f} |")
    
    # By race type
    report.append("\n### Drop-off by Race Type\n")
    for race_type in ['gc', 'one_day', 'stage']:
        if race_type in drop_off_analysis['by_race_type']:
            report.append(f"\n#### {race_type}:")
            report.append("| Table | Count | Drop from 100 |")
            report.append("|-------|-------|---------------|")
            base_count = finisher_analysis['race_features_100']['by_race_type'].get(race_type, 0)
            report.append(f"| race_features_100 | {base_count} | 0.000 |")
            
            for table in race_feature_tables_except_100:
                stats = drop_off_analysis['by_race_type'][race_type].get(table, {})
                report.append(f"| {table} | {stats.get('count', 0)} | "
                             f"{stats.get('drop_from_100', 0):.3f} |")
    
    # By tour level
    report.append("\n### Drop-off by Tour Level\n")
    for tour_level in ['wt', 'pro', 'd1']:
        if tour_level in drop_off_analysis['by_tour_level']:
            report.append(f"\n#### {tour_level}:")
            report.append("| Table | Count | Drop from 100 |")
            report.append("|-------|-------|---------------|")
            base_count = finisher_analysis['race_features_100']['by_tour_level'].get(tour_level, 0)
            report.append(f"| race_features_100 | {base_count} | 0.000 |")
            
            for table in race_feature_tables_except_100:
                stats = drop_off_analysis['by_tour_level'][tour_level].get(table, {})
                report.append(f"| {table} | {stats.get('count', 0)} | "
                             f"{stats.get('drop_from_100', 0):.3f} |")
    
    # By combination
    report.append("\n### Drop-off by Tour Level x Race Type\n")
    for combo_key, table_stats in sorted(drop_off_analysis['by_combination'].items()):
        tour_level, race_type = combo_key.split('_', 1)
        report.append(f"\n#### {tour_level} - {race_type}:")
        report.append("| Table | Count | Drop from 100 |")
        report.append("|-------|-------|---------------|")
        base_count = finisher_analysis['race_features_100']['by_combination'].get(combo_key, 0)
        report.append(f"| race_features_100 | {base_count} | 0.000 |")
        
        for table in race_feature_tables_except_100:
            stats = table_stats.get(table, {})
            report.append(f"| {table} | {stats.get('count', 0)} | "
                         f"{stats.get('drop_from_100', 0):.3f} |")
    
    # Section 3: Time Trial Analysis
    report.append("\n## 3. Time Trial Analysis (Sub-90 Minute Stage Races)\n")
    
    # Overall histogram
    report.append("### Overall Distribution\n")
    report.append(f"Total sub-90 minute stage races: {time_trial_analysis['overall']['count']}\n")
    report.append("| Time Range (min) | Count | Proportion |")
    report.append("|------------------|-------|------------|")
    
    for time_range in ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90']:
        count = time_trial_analysis['overall']['histogram'][time_range]
        prop = time_trial_analysis['overall']['distribution'][time_range]
        report.append(f"| {time_range} | {count} | {prop:.3f} |")
    
    # By tour level
    report.append("\n### Distribution by Tour Level\n")
    for tour_level in ['wt', 'pro', 'd1']:
        data = time_trial_analysis['by_tour_level'][tour_level]
        report.append(f"\n#### {tour_level.upper()}")
        report.append(f"Total: {data['count']} races\n")
        report.append("| Time Range (min) | Count | Proportion |")
        report.append("|------------------|-------|------------|")
        
        for time_range in ['0-10', '10-20', '20-30', '30-40', '40-50', '50-60', '60-70', '70-80', '80-90']:
            count = data['histogram'][time_range]
            prop = data['distribution'][time_range]
            report.append(f"| {time_range} | {count} | {prop:.3f} |")
    
    return "\n".join(report)


def main():
    """Run all analyses and generate outputs."""
    print("Starting race data analysis...")
    
    # Run analyses
    print("Analyzing null kurtosis/skewness values...")
    null_analysis, overall_null_analysis = analyze_null_kurtosis_skewness()
    
    print("Analyzing finisher counts...")
    finisher_analysis, drop_off_analysis = analyze_finisher_counts()
    
    print("Analyzing time trials...")
    time_trial_analysis = analyze_time_trials()
    
    # Convert defaultdicts and tuple keys to regular dicts with string keys for JSON serialization
    def convert_for_json(obj):
        if isinstance(obj, defaultdict):
            return {k: convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if isinstance(k, tuple):
                    new_key = f"{k[0]}_{k[1]}"
                else:
                    new_key = str(k)
                new_dict[new_key] = convert_for_json(v)
            return new_dict
        elif isinstance(obj, list):
            return [convert_for_json(item) for item in obj]
        else:
            return obj
    
    # Prepare JSON output
    json_output = {
        'null_kurtosis_skewness_analysis': {
            'by_race_feature_table': convert_for_json(null_analysis),
            'overall_summary': convert_for_json(overall_null_analysis)
        },
        'finisher_count_analysis': {
            'counts_by_table': convert_for_json(finisher_analysis),
            'drop_off_analysis': convert_for_json(drop_off_analysis)
        },
        'time_trial_analysis': convert_for_json(time_trial_analysis)
    }
    
    # Save JSON
    with open('race_kinds/race_data_analysis.json', 'w') as f:
        json.dump(json_output, f, indent=2, default=str)
    print("Saved JSON output to race_kinds/race_data_analysis.json")
    
    # Generate and save markdown report
    report = generate_markdown_report(null_analysis, overall_null_analysis, 
                                    finisher_analysis, drop_off_analysis, 
                                    time_trial_analysis)
    
    with open('race_kinds/race_data_analysis_report.md', 'w') as f:
        f.write(report)
    print("Saved markdown report to race_kinds/race_data_analysis_report.md")
    
    print("Analysis complete!")


if __name__ == "__main__":
    main()