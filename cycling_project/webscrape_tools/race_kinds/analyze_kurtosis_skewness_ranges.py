"""
Analyze the min and max values for kurtosis and skewness across all race_feature_N tables.
"""

import json
import sqlite3
from typing import Dict, Any


def get_db_connection():
    """Connect to the database."""
    return sqlite3.connect('~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db')


def analyze_kurtosis_skewness_ranges():
    """Get min and max values for kurtosis and skewness across all race_feature_N tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    
    results = {}
    
    for table in race_feature_tables:
        # Get min and max for each metric
        cursor.execute(f"""
            SELECT 
                MIN(kurtosis_absolute) as min_kurtosis_absolute,
                MAX(kurtosis_absolute) as max_kurtosis_absolute,
                MIN(kurtosis_normalized) as min_kurtosis_normalized,
                MAX(kurtosis_normalized) as max_kurtosis_normalized,
                MIN(skewness_absolute) as min_skewness_absolute,
                MAX(skewness_absolute) as max_skewness_absolute,
                MIN(skewness_normalized) as min_skewness_normalized,
                MAX(skewness_normalized) as max_skewness_normalized,
                COUNT(*) as total_count,
                COUNT(CASE WHEN kurtosis_absolute IS NOT NULL THEN 1 END) as non_null_kurtosis_count,
                COUNT(CASE WHEN skewness_absolute IS NOT NULL THEN 1 END) as non_null_skewness_count
            FROM {table}
        """)
        
        row = cursor.fetchone()
        
        # Also get examples of competitions with extreme values
        extreme_examples = {}
        
        # Max kurtosis absolute example
        cursor.execute(f"""
            SELECT competition_id, competition_name, race_category, competition_type, 
                   kurtosis_absolute, kurtosis_normalized, winning_time
            FROM {table}
            WHERE kurtosis_absolute = (SELECT MAX(kurtosis_absolute) FROM {table} WHERE kurtosis_absolute IS NOT NULL)
            LIMIT 1
        """)
        max_kurt_example = cursor.fetchone()
        if max_kurt_example:
            extreme_examples['max_kurtosis_absolute'] = {
                'competition_id': max_kurt_example[0],
                'competition_name': max_kurt_example[1],
                'race_category': max_kurt_example[2],
                'competition_type': max_kurt_example[3],
                'kurtosis_absolute': max_kurt_example[4],
                'kurtosis_normalized': max_kurt_example[5],
                'winning_time': max_kurt_example[6]
            }
        
        # Min kurtosis absolute example
        cursor.execute(f"""
            SELECT competition_id, competition_name, race_category, competition_type, 
                   kurtosis_absolute, kurtosis_normalized, winning_time
            FROM {table}
            WHERE kurtosis_absolute = (SELECT MIN(kurtosis_absolute) FROM {table} WHERE kurtosis_absolute IS NOT NULL)
            LIMIT 1
        """)
        min_kurt_example = cursor.fetchone()
        if min_kurt_example:
            extreme_examples['min_kurtosis_absolute'] = {
                'competition_id': min_kurt_example[0],
                'competition_name': min_kurt_example[1],
                'race_category': min_kurt_example[2],
                'competition_type': min_kurt_example[3],
                'kurtosis_absolute': min_kurt_example[4],
                'kurtosis_normalized': min_kurt_example[5],
                'winning_time': min_kurt_example[6]
            }
        
        # Max skewness absolute example
        cursor.execute(f"""
            SELECT competition_id, competition_name, race_category, competition_type, 
                   skewness_absolute, skewness_normalized, winning_time
            FROM {table}
            WHERE skewness_absolute = (SELECT MAX(skewness_absolute) FROM {table} WHERE skewness_absolute IS NOT NULL)
            LIMIT 1
        """)
        max_skew_example = cursor.fetchone()
        if max_skew_example:
            extreme_examples['max_skewness_absolute'] = {
                'competition_id': max_skew_example[0],
                'competition_name': max_skew_example[1],
                'race_category': max_skew_example[2],
                'competition_type': max_skew_example[3],
                'skewness_absolute': max_skew_example[4],
                'skewness_normalized': max_skew_example[5],
                'winning_time': max_skew_example[6]
            }
        
        # Min skewness absolute example
        cursor.execute(f"""
            SELECT competition_id, competition_name, race_category, competition_type, 
                   skewness_absolute, skewness_normalized, winning_time
            FROM {table}
            WHERE skewness_absolute = (SELECT MIN(skewness_absolute) FROM {table} WHERE skewness_absolute IS NOT NULL)
            LIMIT 1
        """)
        min_skew_example = cursor.fetchone()
        if min_skew_example:
            extreme_examples['min_skewness_absolute'] = {
                'competition_id': min_skew_example[0],
                'competition_name': min_skew_example[1],
                'race_category': min_skew_example[2],
                'competition_type': min_skew_example[3],
                'skewness_absolute': min_skew_example[4],
                'skewness_normalized': min_skew_example[5],
                'winning_time': min_skew_example[6]
            }
        
        results[table] = {
            'min_kurtosis_absolute': row[0],
            'max_kurtosis_absolute': row[1],
            'min_kurtosis_normalized': row[2],
            'max_kurtosis_normalized': row[3],
            'min_skewness_absolute': row[4],
            'max_skewness_absolute': row[5],
            'min_skewness_normalized': row[6],
            'max_skewness_normalized': row[7],
            'total_count': row[8],
            'non_null_kurtosis_count': row[9],
            'non_null_skewness_count': row[10],
            'null_kurtosis_proportion': 1 - (row[9] / row[8]) if row[8] > 0 else 0,
            'null_skewness_proportion': 1 - (row[10] / row[8]) if row[8] > 0 else 0,
            'extreme_examples': extreme_examples
        }
    
    conn.close()
    return results


def generate_report(results: Dict[str, Any]) -> str:
    """Generate a markdown report of the results."""
    report = []
    report.append("# Kurtosis and Skewness Range Analysis\n")
    
    # Summary table
    report.append("## Summary Table\n")
    report.append("| Table | Min Kurt (Abs) | Max Kurt (Abs) | Min Kurt (Norm) | Max Kurt (Norm) | Min Skew (Abs) | Max Skew (Abs) | Min Skew (Norm) | Max Skew (Norm) | Null Kurt % | Null Skew % |")
    report.append("|-------|----------------|----------------|-----------------|-----------------|----------------|----------------|-----------------|-----------------|-------------|-------------|")
    
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    for table in race_feature_tables:
        if table in results:
            r = results[table]
            report.append(f"| {table} | "
                         f"{r['min_kurtosis_absolute']:.2f} | "
                         f"{r['max_kurtosis_absolute']:.2f} | "
                         f"{r['min_kurtosis_normalized']:.2f} | "
                         f"{r['max_kurtosis_normalized']:.2f} | "
                         f"{r['min_skewness_absolute']:.2f} | "
                         f"{r['max_skewness_absolute']:.2f} | "
                         f"{r['min_skewness_normalized']:.2f} | "
                         f"{r['max_skewness_normalized']:.2f} | "
                         f"{r['null_kurtosis_proportion']*100:.1f}% | "
                         f"{r['null_skewness_proportion']*100:.1f}% |")
    
    # Detailed analysis by table
    report.append("\n## Detailed Analysis by Table\n")
    
    race_feature_tables = [f'race_features_{i}' for i in range(10, 101, 5)]
    for table in race_feature_tables:
        if table in results:
            r = results[table]
            report.append(f"\n### {table}\n")
            report.append(f"- Total competitions: {r['total_count']:,}")
            report.append(f"- Non-null kurtosis: {r['non_null_kurtosis_count']:,} ({(r['non_null_kurtosis_count']/r['total_count']*100):.1f}%)")
            report.append(f"- Non-null skewness: {r['non_null_skewness_count']:,} ({(r['non_null_skewness_count']/r['total_count']*100):.1f}%)")
            
            report.append("\n#### Ranges:")
            report.append(f"- Kurtosis (absolute): [{r['min_kurtosis_absolute']:.3f}, {r['max_kurtosis_absolute']:.3f}]")
            report.append(f"- Kurtosis (normalized): [{r['min_kurtosis_normalized']:.3f}, {r['max_kurtosis_normalized']:.3f}]")
            report.append(f"- Skewness (absolute): [{r['min_skewness_absolute']:.3f}, {r['max_skewness_absolute']:.3f}]")
            report.append(f"- Skewness (normalized): [{r['min_skewness_normalized']:.3f}, {r['max_skewness_normalized']:.3f}]")
            
            if r['extreme_examples']:
                report.append("\n#### Extreme Examples:")
                
                for example_type, example in r['extreme_examples'].items():
                    report.append(f"\n**{example_type.replace('_', ' ').title()}:**")
                    report.append(f"- Competition: {example['competition_name']} (ID: {example['competition_id']})")
                    report.append(f"- Type: {example['race_category']} - {example['competition_type']}")
                    report.append(f"- Winning time: {example['winning_time']:.0f} seconds ({example['winning_time']/60:.1f} minutes)")
                    
                    if 'kurtosis' in example_type:
                        report.append(f"- Kurtosis: {example['kurtosis_absolute']:.3f} (absolute), {example['kurtosis_normalized']:.3f} (normalized)")
                    else:
                        report.append(f"- Skewness: {example['skewness_absolute']:.3f} (absolute), {example['skewness_normalized']:.3f} (normalized)")
    
    return "\n".join(report)


def main():
    """Run the analysis and save results."""
    print("Analyzing kurtosis and skewness ranges...")
    
    results = analyze_kurtosis_skewness_ranges()
    
    # Save JSON output
    with open('race_kinds/kurtosis_skewness_ranges.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("Saved JSON output to race_kinds/kurtosis_skewness_ranges.json")
    
    # Generate and save markdown report
    report = generate_report(results)
    with open('race_kinds/kurtosis_skewness_ranges_report.md', 'w') as f:
        f.write(report)
    print("Saved markdown report to race_kinds/kurtosis_skewness_ranges_report.md")
    
    print("Analysis complete!")


if __name__ == "__main__":
    main()