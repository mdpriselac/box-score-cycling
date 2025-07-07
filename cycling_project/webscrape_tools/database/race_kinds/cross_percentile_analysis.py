"""
Cross-Percentile Race Kind Analysis

This module analyzes race kinds across different percentile levels to find
stable patterns and understand how race characteristics change with field depth.
"""

import numpy as np
import pandas as pd
import sqlite3
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import spearmanr
from typing import Dict, List, Tuple, Optional, Set
import warnings
warnings.filterwarnings('ignore')


class CrossPercentileAnalyzer:
    """
    Analyzes race patterns across different percentile cutoffs.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize the analyzer.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.percentile_tables = self._get_percentile_tables()
        self.common_competitions = None
        self.feature_trajectories = None
        
    def _get_percentile_tables(self) -> List[str]:
        """Get ordered list of percentile tables."""
        conn = sqlite3.connect(self.db_path)
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name LIKE 'race_features_%'
        ORDER BY CAST(SUBSTR(name, 15) AS INTEGER)
        """
        tables = pd.read_sql_query(query, conn)['name'].tolist()
        conn.close()
        return tables
    
    def find_common_competitions(
        self,
        min_percentile_coverage: float = 0.8,
        competition_type: Optional[str] = None
    ) -> Set[int]:
        """
        Find competitions that appear across multiple percentile tables.
        
        Args:
            min_percentile_coverage: Minimum fraction of tables a competition must appear in
            competition_type: Filter by competition type
            
        Returns:
            Set of competition IDs that meet the coverage requirement
        """
        competition_counts = {}
        
        for table in self.percentile_tables:
            conn = sqlite3.connect(self.db_path)
            
            query = f"SELECT DISTINCT competition_id FROM {table}"
            params = []
            
            if competition_type is not None:
                if competition_type == 'stage_one_day':
                    query += " WHERE competition_type IN ('stage', 'one_day')"
                else:
                    query += " WHERE competition_type = ?"
                    params.append(competition_type)
            
            comp_ids = pd.read_sql_query(query, conn, params=params)['competition_id'].tolist()
            conn.close()
            
            for comp_id in comp_ids:
                competition_counts[comp_id] = competition_counts.get(comp_id, 0) + 1
        
        # Filter competitions by coverage
        min_tables = int(len(self.percentile_tables) * min_percentile_coverage)
        self.common_competitions = {
            comp_id for comp_id, count in competition_counts.items()
            if count >= min_tables
        }
        
        return self.common_competitions
    
    def extract_feature_trajectories(
        self,
        features: List[str] = None,
        competition_ids: Set[int] = None
    ) -> pd.DataFrame:
        """
        Extract how features change across percentiles for each competition.
        
        Args:
            features: List of features to track (None for default set)
            competition_ids: Set of competition IDs to analyze (None for common competitions)
            
        Returns:
            DataFrame with feature trajectories
        """
        if features is None:
            features = [
                'selection_metric', 'biggest_group_metric', 'clumpiness_score',
                'gini_coefficient', 'variance_normalized', 'proportion_in_groups'
            ]
        
        if competition_ids is None:
            if self.common_competitions is None:
                self.find_common_competitions()
            competition_ids = self.common_competitions
        
        trajectories = []
        
        for table in self.percentile_tables:
            percentile = int(table.split('_')[-1])
            
            conn = sqlite3.connect(self.db_path)
            
            # Build query for features
            feature_cols = ', '.join(features)
            query = f"""
            SELECT competition_id, competition_name, race_name, 
                   competition_type, race_category, {feature_cols}
            FROM {table}
            WHERE competition_id IN ({','.join('?' * len(competition_ids))})
            """
            
            df = pd.read_sql_query(query, conn, params=list(competition_ids))
            df['percentile'] = percentile
            trajectories.append(df)
            
            conn.close()
        
        self.feature_trajectories = pd.concat(trajectories, ignore_index=True)
        return self.feature_trajectories
    
    def analyze_feature_stability(self) -> Dict[str, Dict[str, float]]:
        """
        Analyze how stable each feature is across percentiles.
        
        Returns:
            Dictionary with stability metrics for each feature
        """
        if self.feature_trajectories is None:
            raise ValueError("No feature trajectories loaded. Run extract_feature_trajectories first.")
        
        feature_cols = [col for col in self.feature_trajectories.columns 
                       if col not in ['competition_id', 'competition_name', 'race_name',
                                     'competition_type', 'race_category', 'percentile']]
        
        stability_metrics = {}
        
        for feature in feature_cols:
            # Calculate coefficient of variation for each competition
            cv_values = []
            
            for comp_id in self.feature_trajectories['competition_id'].unique():
                comp_data = self.feature_trajectories[
                    self.feature_trajectories['competition_id'] == comp_id
                ]
                
                if len(comp_data) > 1:
                    values = comp_data[feature].values
                    if np.mean(values) != 0:
                        cv = np.std(values) / np.abs(np.mean(values))
                        cv_values.append(cv)
            
            stability_metrics[feature] = {
                'mean_cv': float(np.mean(cv_values)) if cv_values else 0,
                'std_cv': float(np.std(cv_values)) if cv_values else 0,
                'median_cv': float(np.median(cv_values)) if cv_values else 0,
                'stability_score': 1 / (1 + np.mean(cv_values)) if cv_values else 0
            }
        
        return stability_metrics
    
    def find_percentile_invariant_kinds(
        self,
        n_clusters: int = 4,
        stability_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Find race kinds that remain consistent across percentiles.
        
        Args:
            n_clusters: Number of clusters to find
            stability_threshold: Minimum stability score for a kind to be considered invariant
            
        Returns:
            Dictionary with invariant race kinds and their characteristics
        """
        if self.feature_trajectories is None:
            raise ValueError("No feature trajectories loaded. Run extract_feature_trajectories first.")
        
        # Get stability metrics
        stability_metrics = self.analyze_feature_stability()
        
        # Select stable features
        stable_features = [
            feat for feat, metrics in stability_metrics.items()
            if metrics['stability_score'] >= stability_threshold
        ]
        
        if not stable_features:
            print("Warning: No features meet stability threshold. Using top 3 most stable.")
            sorted_features = sorted(
                stability_metrics.items(),
                key=lambda x: x[1]['stability_score'],
                reverse=True
            )
            stable_features = [feat[0] for feat in sorted_features[:3]]
        
        results = {
            'stable_features': stable_features,
            'stability_metrics': {f: stability_metrics[f] for f in stable_features},
            'clusters_by_percentile': {},
            'invariant_competitions': []
        }
        
        # Cluster at each percentile using stable features
        scaler = StandardScaler()
        
        for percentile in self.feature_trajectories['percentile'].unique():
            pct_data = self.feature_trajectories[
                self.feature_trajectories['percentile'] == percentile
            ].copy()
            
            # Scale features
            feature_data = pct_data[stable_features].fillna(0)
            scaled_features = scaler.fit_transform(feature_data)
            
            # Cluster
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            pct_data['cluster'] = kmeans.fit_predict(scaled_features)
            
            results['clusters_by_percentile'][percentile] = pct_data[
                ['competition_id', 'competition_name', 'cluster']
            ]
        
        # Find competitions that stay in same cluster across percentiles
        cluster_consistency = {}
        
        for comp_id in self.common_competitions:
            clusters = []
            for percentile, data in results['clusters_by_percentile'].items():
                comp_cluster = data[data['competition_id'] == comp_id]['cluster'].values
                if len(comp_cluster) > 0:
                    clusters.append(comp_cluster[0])
            
            if clusters:
                # Check if competition stays in same cluster
                if len(set(clusters)) == 1:
                    cluster_consistency[comp_id] = {
                        'cluster': clusters[0],
                        'consistency': 1.0
                    }
                else:
                    # Calculate consistency as fraction in mode cluster
                    mode_cluster = max(set(clusters), key=clusters.count)
                    consistency = clusters.count(mode_cluster) / len(clusters)
                    cluster_consistency[comp_id] = {
                        'cluster': mode_cluster,
                        'consistency': consistency
                    }
        
        # Get invariant competitions
        results['invariant_competitions'] = [
            {
                'competition_id': comp_id,
                'cluster': info['cluster'],
                'consistency': info['consistency']
            }
            for comp_id, info in cluster_consistency.items()
            if info['consistency'] >= 0.8
        ]
        
        return results
    
    def analyze_percentile_effects(
        self,
        features: List[str] = None
    ) -> pd.DataFrame:
        """
        Analyze how race characteristics change with percentile depth.
        
        Args:
            features: Features to analyze (None for default set)
            
        Returns:
            DataFrame with percentile effect analysis
        """
        if self.feature_trajectories is None:
            raise ValueError("No feature trajectories loaded. Run extract_feature_trajectories first.")
        
        if features is None:
            features = [col for col in self.feature_trajectories.columns 
                       if col not in ['competition_id', 'competition_name', 'race_name',
                                     'competition_type', 'race_category', 'percentile']]
        
        # Calculate mean values at each percentile
        percentile_means = self.feature_trajectories.groupby('percentile')[features].mean()
        
        # Calculate correlations with percentile
        correlations = {}
        for feature in features:
            corr, p_value = spearmanr(
                percentile_means.index,
                percentile_means[feature]
            )
            correlations[feature] = {
                'correlation': corr,
                'p_value': p_value,
                'trend': 'increasing' if corr > 0.3 else 'decreasing' if corr < -0.3 else 'stable'
            }
        
        # Create summary DataFrame
        summary_data = []
        for feature in features:
            row = {
                'feature': feature,
                'correlation_with_percentile': correlations[feature]['correlation'],
                'p_value': correlations[feature]['p_value'],
                'trend': correlations[feature]['trend'],
                'value_at_30': percentile_means.loc[30, feature] if 30 in percentile_means.index else None,
                'value_at_70': percentile_means.loc[70, feature] if 70 in percentile_means.index else None,
                'value_at_100': percentile_means.loc[100, feature] if 100 in percentile_means.index else None,
            }
            
            # Calculate relative change
            if row['value_at_30'] and row['value_at_100'] and row['value_at_30'] != 0:
                row['relative_change_30_to_100'] = (
                    (row['value_at_100'] - row['value_at_30']) / row['value_at_30']
                )
            else:
                row['relative_change_30_to_100'] = None
            
            summary_data.append(row)
        
        return pd.DataFrame(summary_data)
    
    def create_race_kind_trajectories(
        self,
        method: str = 'kmeans',
        n_kinds: int = 4
    ) -> Dict[str, Any]:
        """
        Track how races move between kinds as percentile changes.
        
        Args:
            method: Clustering method to use
            n_kinds: Number of race kinds
            
        Returns:
            Dictionary with trajectory analysis
        """
        if self.feature_trajectories is None:
            raise ValueError("No feature trajectories loaded. Run extract_feature_trajectories first.")
        
        from race_kind_analysis import RaceKindAnalyzer
        
        trajectories = {}
        transitions = []
        
        # Track cluster assignments across percentiles
        for i, table in enumerate(self.percentile_tables):
            percentile = int(table.split('_')[-1])
            
            # Initialize analyzer
            analyzer = RaceKindAnalyzer(self.db_path)
            analyzer.load_data(table)
            
            # Only analyze competitions in our common set
            analyzer.data = analyzer.data[
                analyzer.data['competition_id'].isin(self.common_competitions)
            ]
            
            if len(analyzer.data) < 10:
                continue
            
            analyzer.prepare_features()
            
            # Cluster
            if method == 'kmeans':
                results = analyzer.kmeans_clustering(range(n_kinds, n_kinds+1))
                labels = results['cluster_results'][n_kinds]['labels']
            else:
                # Add other methods as needed
                continue
            
            # Store assignments
            for idx, (_, row) in enumerate(analyzer.data.iterrows()):
                comp_id = row['competition_id']
                
                if comp_id not in trajectories:
                    trajectories[comp_id] = {
                        'competition_name': row['competition_name'],
                        'race_name': row['race_name'],
                        'assignments': {}
                    }
                
                trajectories[comp_id]['assignments'][percentile] = int(labels[idx])
                
                # Track transitions
                if i > 0:
                    prev_percentile = int(self.percentile_tables[i-1].split('_')[-1])
                    if prev_percentile in trajectories[comp_id]['assignments']:
                        prev_cluster = trajectories[comp_id]['assignments'][prev_percentile]
                        curr_cluster = int(labels[idx])
                        
                        if prev_cluster != curr_cluster:
                            transitions.append({
                                'competition_id': comp_id,
                                'from_percentile': prev_percentile,
                                'to_percentile': percentile,
                                'from_cluster': prev_cluster,
                                'to_cluster': curr_cluster
                            })
        
        # Analyze transition patterns
        transition_df = pd.DataFrame(transitions)
        
        if not transition_df.empty:
            transition_matrix = pd.crosstab(
                transition_df['from_cluster'],
                transition_df['to_cluster'],
                normalize='index'
            )
        else:
            transition_matrix = pd.DataFrame()
        
        return {
            'trajectories': trajectories,
            'transitions': transitions,
            'transition_matrix': transition_matrix,
            'n_stable_races': sum(
                1 for t in trajectories.values()
                if len(set(t['assignments'].values())) == 1
            ),
            'n_transitioning_races': sum(
                1 for t in trajectories.values()
                if len(set(t['assignments'].values())) > 1
            )
        }
    
    def generate_cross_percentile_report(
        self,
        output_path: str = 'database/race_kinds/reports/cross_percentile_analysis.md'
    ) -> str:
        """
        Generate a comprehensive cross-percentile analysis report.
        
        Args:
            output_path: Path for the output report
            
        Returns:
            Path to the generated report
        """
        # Ensure we have data
        if self.common_competitions is None:
            self.find_common_competitions()
        
        if self.feature_trajectories is None:
            self.extract_feature_trajectories()
        
        # Run analyses
        stability_analysis = self.analyze_feature_stability()
        percentile_effects = self.analyze_percentile_effects()
        invariant_kinds = self.find_percentile_invariant_kinds()
        trajectories = self.create_race_kind_trajectories()
        
        # Generate report
        with open(output_path, 'w') as f:
            f.write("# Cross-Percentile Race Kind Analysis\n\n")
            f.write(f"Analysis Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            f.write(f"- Analyzed {len(self.common_competitions)} competitions across {len(self.percentile_tables)} percentile levels\n")
            f.write(f"- Percentile levels: {', '.join(t.split('_')[-1] + 'th' for t in self.percentile_tables)}\n\n")
            
            # Feature Stability
            f.write("## Feature Stability Analysis\n\n")
            f.write("How consistent are race features across different percentile cutoffs?\n\n")
            
            stability_df = pd.DataFrame(stability_analysis).T
            stability_df = stability_df.sort_values('stability_score', ascending=False)
            
            f.write("| Feature | Stability Score | Mean CV |\n")
            f.write("|---------|----------------|----------|\n")
            for feature, metrics in stability_df.iterrows():
                f.write(f"| {feature} | {metrics['stability_score']:.3f} | {metrics['mean_cv']:.3f} |\n")
            
            # Percentile Effects
            f.write("\n## Percentile Effects on Race Characteristics\n\n")
            f.write("How do race features change as we include more of the field?\n\n")
            
            increasing = percentile_effects[percentile_effects['trend'] == 'increasing']
            decreasing = percentile_effects[percentile_effects['trend'] == 'decreasing']
            
            if not increasing.empty:
                f.write("### Features that increase with field depth:\n")
                for _, row in increasing.iterrows():
                    f.write(f"- **{row['feature']}**: {row['value_at_30']:.3f} → {row['value_at_100']:.3f} ")
                    if row['relative_change_30_to_100']:
                        f.write(f"({row['relative_change_30_to_100']:+.1%} change)\n")
                    else:
                        f.write("\n")
            
            if not decreasing.empty:
                f.write("\n### Features that decrease with field depth:\n")
                for _, row in decreasing.iterrows():
                    f.write(f"- **{row['feature']}**: {row['value_at_30']:.3f} → {row['value_at_100']:.3f} ")
                    if row['relative_change_30_to_100']:
                        f.write(f"({row['relative_change_30_to_100']:+.1%} change)\n")
                    else:
                        f.write("\n")
            
            # Invariant Race Kinds
            f.write("\n## Percentile-Invariant Race Kinds\n\n")
            f.write(f"Found {len(invariant_kinds['invariant_competitions'])} races that maintain consistent classification across percentiles.\n\n")
            f.write(f"Stable features used: {', '.join(invariant_kinds['stable_features'])}\n\n")
            
            if invariant_kinds['invariant_competitions']:
                # Group by cluster
                cluster_groups = {}
                for comp in invariant_kinds['invariant_competitions']:
                    cluster = comp['cluster']
                    if cluster not in cluster_groups:
                        cluster_groups[cluster] = []
                    cluster_groups[cluster].append(comp['competition_id'])
                
                f.write("### Invariant Race Groups:\n\n")
                for cluster, comp_ids in sorted(cluster_groups.items()):
                    f.write(f"**Kind {cluster}** ({len(comp_ids)} races)\n")
                    # Get example races
                    example_df = self.feature_trajectories[
                        (self.feature_trajectories['competition_id'].isin(comp_ids[:5])) &
                        (self.feature_trajectories['percentile'] == 70)
                    ][['race_name', 'competition_name']].drop_duplicates()
                    
                    for _, race in example_df.iterrows():
                        f.write(f"- {race['race_name']} - {race['competition_name']}\n")
                    f.write("\n")
            
            # Race Trajectories
            f.write("## Race Kind Trajectories\n\n")
            f.write(f"- Stable races (same kind across percentiles): {trajectories['n_stable_races']}\n")
            f.write(f"- Transitioning races: {trajectories['n_transitioning_races']}\n\n")
            
            if not trajectories['transition_matrix'].empty:
                f.write("### Transition Patterns\n\n")
                f.write("How races move between kinds as percentile changes:\n\n")
                f.write(trajectories['transition_matrix'].to_markdown())
            
            # Conclusions
            f.write("\n\n## Key Findings\n\n")
            f.write("1. **Most stable features**: ")
            f.write(", ".join(stability_df.head(3).index.tolist()))
            f.write("\n\n2. **Percentile effects**: ")
            if len(increasing) > len(decreasing):
                f.write("Including more of the field generally increases race heterogeneity")
            else:
                f.write("Race characteristics remain relatively stable across percentiles")
            f.write("\n\n3. **Race kind stability**: ")
            stability_pct = trajectories['n_stable_races'] / len(trajectories['trajectories']) * 100
            f.write(f"{stability_pct:.1f}% of races maintain consistent classification")
        
        print(f"\nCross-percentile report generated: {output_path}")
        return output_path