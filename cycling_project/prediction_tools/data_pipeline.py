"""
Data Pipeline for Cycling Race Predictions

Provides efficient data loading from pre-computed feature tables
with temporal train/validation/test splits.

Key features:
1. Loads rider features from rider_competition_snapshots
2. Loads field features from competition_field_features
3. Joins with rider_results for target variables (place_bucket, time_gap)
4. Supports temporal splitting for proper evaluation
"""

import sqlite3
import os
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Literal, Dict
from pathlib import Path
import pandas as pd
import numpy as np

try:
    from dotenv import load_dotenv
    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False


@dataclass
class DataConfig:
    """Configuration for data loading."""
    db_path: Optional[str] = None  # Auto-detect if None
    start_date: str = '2018-01-01'  # Training data start
    min_races_career: int = 10  # Minimum career races for reliable features
    competition_types: List[str] = field(default_factory=lambda: ['stage', 'one_day', 'gc'])
    race_categories: List[str] = field(default_factory=lambda: ['wt', 'pro', 'd1'])
    require_race_profile: bool = True  # Require race profile scores
    exclude_dnf_for_time_gap: bool = True  # Exclude DNF when predicting time gap
    # Stage 0: optionally include raw gradient / null-marker / race-shape
    # columns from race_feature_gradients and race_features_100. Off by default
    # so production paths are unchanged.
    include_gradient_features: bool = False
    # Stage 1: optionally include one-day race cluster memberships from
    # race_cluster_v1_scores. Clusters are populated only for one_day rows;
    # stage/gc rows get NULL cluster scores which are imputed to 0.
    # cluster_variant picks which GMM fit to read from the table (the offline
    # script writes 'race_only' and 'joint' in the same run).
    # current_fold_label is set per fold by the ExperimentRunner so that the
    # cluster JOIN pulls the scoring from the GMM fitted on that fold's
    # training races specifically. Must be provided when clusters are on.
    include_race_clusters: bool = False
    cluster_variant: str = 'joint'
    current_fold_label: Optional[str] = None
    # Stage-race state: optionally include within-race state features from
    # rider_race_state (current GC standings, in-race stage form, fatigue,
    # tactical flags — all strictly from stages completed BEFORE the target
    # stage). Joined for competition_type='stage' rows only; stage-1 rows,
    # one-day races, gc rows and riders without complete prior-stage coverage
    # come through NULL and feature_engineering imputes neutral defaults plus
    # a race_state_missing flag. Off by default so production is unchanged.
    include_race_state: bool = False


class CyclingDataPipeline:
    """
    Unified data loading pipeline for cycling race predictions.

    Loads pre-computed features from:
    - rider_competition_snapshots: Rider historical features at each race
    - competition_field_features: Field-level aggregates and race profiles
    - rider_results: Target variables (place_bucket, time_gap)

    Example usage:
        pipeline = CyclingDataPipeline()
        df = pipeline.load_training_data()
        train, val, test = pipeline.get_temporal_split(df)
    """

    # Column definitions
    RIDER_FEATURE_COLS = [
        'rider_id', 'rider_name', 'age', 'team_bib', 'personal_bib',
        'races_career', 'races_this_year',
        'stage_avg_bucket', 'stage_count',
        'one_day_avg_bucket', 'one_day_count',
        'gc_avg_bucket', 'gc_count',
        'wt_avg_bucket', 'wt_count',
        'pro_avg_bucket', 'pro_count',
        'd1_avg_bucket', 'd1_count',
        'sprint_avg_bucket', 'mountain_avg_bucket', 'hilly_avg_bucket',
        'rolling_avg_bucket', 'breakaway_avg_bucket', 'time_trial_avg_bucket',
        'best_profile',
        # Form features
        'form_recent_avg_bucket', 'form_recent_best_bucket',
        'form_recent_count', 'form_delta',
        'form_profile_recent_avg', 'days_since_last_race',
        # Team features
        'team_quality_mean', 'team_quality_median', 'team_quality_std',
        'team_quality_min', 'team_quality_max',
        'team_quality_p25', 'team_quality_p75',
        'team_size', 'team_depth',
    ]

    FIELD_FEATURE_COLS = [
        'field_size',
        'experience_mean', 'experience_median', 'experience_std',
        'experience_min', 'experience_max', 'experience_p25', 'experience_p75',
        'bucket_mean', 'bucket_median', 'bucket_std',
        'bucket_min', 'bucket_max', 'bucket_p25', 'bucket_p75',
        'sprinter_count', 'climber_count', 'hilly_specialist_count',
        'rolling_specialist_count', 'breakaway_specialist_count',
        'time_trialist_count', 'unknown_profile_count'
    ]

    RACE_PROFILE_COLS = [
        'race_sprint_score', 'race_mountain_score', 'race_hilly_score',
        'race_rolling_score', 'race_breakaway_score', 'race_time_trial_score',
        'race_dominant_profile'
    ]

    # Stage 0 feature groups (only used when config.include_gradient_features=True).
    # All column names verified against the live schema.
    # From race_feature_gradients: raw slopes / volatility / monotonicity.
    GRADIENT_FEATURE_COLS = [
        'variance_normalized_slope',
        'variance_normalized_volatility',
        'variance_normalized_monotonicity',
        'clumpiness_score_slope',
        'clumpiness_score_volatility',
        'biggest_group_metric_slope',
        'biggest_group_metric_volatility',
        'selection_metric_slope',
        'selection_metric_volatility',
        'gini_coefficient_slope',
        'skewness_normalized_slope',
    ]
    # From race_feature_gradients: null-awareness markers exposed so LightGBM
    # can learn the interaction between slope shape and coverage.
    GRADIENT_NULL_MARKER_COLS = [
        'percentile_coverage_ratio',
        'lowest_valid_percentile',
        'highest_null_percentile',
        'kurtosis_null_percentile',
        'variance_zero_percentile',
    ]
    # From race_features_100: race-level scalars not currently exposed downstream.
    RACE_SHAPE_COLS = [
        'winning_time',
        'abandon_ratio',
    ]

    # Stage 1: maximum cluster columns the race_cluster_v1_scores table
    # holds. Must match the schema written by
    # ``cycling_project.prediction_tools.experiments.stage1_race_clustering``.
    # Clusters are stored only for one_day rows; stage / gc rows produce
    # NULL on the LEFT JOIN and feature_engineering imputes those to 0.
    MAX_CLUSTERS = 12

    # Stage-race state features from rider_race_state (only used when
    # config.include_race_state=True). Must stay in sync with
    # engineering_tools.stage_race_state.STATE_FEATURE_COLUMNS (unit-tested);
    # duplicated here so prediction_tools stays free of engineering_tools
    # imports, matching the gradient-feature pattern above.
    RACE_STATE_FEATURE_COLS = [
        'gc_rank_current', 'gc_gap_to_leader_s', 'gc_gap_to_podium_s',
        'gc_gap_to_rank10_s', 'gc_rank_pctile', 'is_race_leader',
        'team_best_gc_rank', 'is_team_gc_leader', 'teammates_top10_count',
        'team_has_gc_top5',
        'last_stage_bucket', 'last_stage_pctile', 'best_stage_bucket_so_far',
        'mean_stage_pctile_so_far', 'stage_top10_count_so_far',
        'stages_completed', 'pct_race_complete', 'cum_time_raced_s',
        'is_post_rest_day', 'field_attrition',
        'gc_gap_gt_10min', 'lost_big_time_last_stage',
    ]

    METADATA_COLS = [
        'competition_id', 'competition_name', 'competition_date',
        'competition_type', 'race_category'
    ]

    TARGET_COLS = ['place_bucket', 'time_gap']

    def __init__(self, config: Optional[DataConfig] = None):
        self.config = config or DataConfig()
        self.db_path = self._find_database(self.config.db_path)

    def _find_database(self, db_path: Optional[str] = None) -> str:
        """Find the SQLite database file."""
        if db_path and os.path.isfile(db_path):
            return db_path

        if HAS_DOTENV:
            load_dotenv()
            env_path = os.getenv('DB_PATH')
            # Only use if it's a file that exists (not a directory)
            if env_path and os.path.isfile(env_path):
                return env_path

        # Search in common locations
        possible_paths = [
            Path(__file__).parent.parent / "webscrape_tools" / "database" / "database" / "cycling_races.db",
            Path(__file__).parent.parent / "cycling_races.db",
        ]
        for path in possible_paths:
            if path.exists() and path.is_file():
                return str(path)

        raise FileNotFoundError(
            "Database not found. Searched: " +
            ", ".join(str(p) for p in possible_paths)
        )

    def _get_connection(self) -> sqlite3.Connection:
        """Create a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_training_data(
        self,
        target: Literal['bucket', 'time_gap', 'both'] = 'both',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_races_career: Optional[int] = None,
        competition_types: Optional[List[str]] = None,
        race_categories: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load complete training dataset with rider + field + race profile features.

        Args:
            target: Which target variable(s) to include
            start_date: Override config start date
            end_date: Optional end date filter
            min_races_career: Override minimum career races filter
            competition_types: Override competition type filter
            race_categories: Override race category filter

        Returns:
            DataFrame with features and target variable(s)
        """
        start_date = start_date or self.config.start_date
        min_races = min_races_career or self.config.min_races_career
        comp_types = competition_types or self.config.competition_types
        categories = race_categories or self.config.race_categories

        # Build SQL query
        query = self._build_training_query(
            target=target,
            start_date=start_date,
            end_date=end_date,
            min_races_career=min_races,
            competition_types=comp_types,
            race_categories=categories
        )

        conn = self._get_connection()
        try:
            df = pd.read_sql_query(query, conn)
        finally:
            conn.close()

        # Convert date column
        df['competition_date'] = pd.to_datetime(df['competition_date'])

        return df

    def _build_gradient_clauses(self) -> Tuple[str, str]:
        """
        Build SELECT and JOIN fragments for Stage 0 gradient features.

        Returns ('', '') when include_gradient_features is off, so existing
        queries are untouched. When on, returns a SELECT fragment that pulls
        11 gradient columns, 5 null markers, 2 race-shape columns, and a
        derived race_profile_missing flag, plus LEFT JOINs onto
        race_feature_gradients and race_features_100. LEFT JOINs (not inner
        joins) so races without a gradient row still come through — the flag
        column tells the model they are missing.
        """
        if not self.config.include_gradient_features:
            return '', ''

        gradient_parts = [f'rfg.{c}' for c in self.GRADIENT_FEATURE_COLS]
        gradient_parts += [f'rfg.{c}' for c in self.GRADIENT_NULL_MARKER_COLS]
        gradient_parts += [f'rf100.{c}' for c in self.RACE_SHAPE_COLS]
        gradient_parts.append(
            '(CASE WHEN rfg.competition_id IS NULL THEN 1 ELSE 0 END) '
            'AS race_profile_missing'
        )
        select_fragment = ', '.join(gradient_parts)

        join_fragment = (
            'LEFT JOIN race_feature_gradients rfg '
            'ON rfg.competition_id = cff.competition_id\n'
            '        LEFT JOIN race_features_100 rf100 '
            'ON rf100.competition_id = cff.competition_id'
        )
        return select_fragment, join_fragment

    def _build_cluster_clauses(self) -> Tuple[str, str]:
        """
        Build SELECT and JOIN fragments for Stage 1 one-day cluster features.

        Returns ('', '') when include_race_clusters is off. When on,
        requires config.current_fold_label to be set (the ExperimentRunner
        is responsible for setting it per fold). The JOIN pulls cluster
        scores from the GMM fitted on that specific fold's training races,
        because cluster identity is NOT stable across folds. The JOIN is
        LEFT so non-one-day rows (stage / gc) come through with NULL
        cluster columns, which feature_engineering then imputes to 0.
        """
        if not self.config.include_race_clusters:
            return '', ''
        fold_label = self.config.current_fold_label
        if not fold_label:
            raise ValueError(
                'include_race_clusters=True but current_fold_label is not set. '
                'The caller (ExperimentRunner / training.py) must set this per fold '
                'before loading training data.'
            )
        variant = self.config.cluster_variant
        if variant not in ('race_only', 'joint'):
            raise ValueError(
                f'cluster_variant must be race_only or joint, got {variant!r}'
            )

        cluster_parts = [
            f'rcl.cluster_{i}_score' for i in range(self.MAX_CLUSTERS)
        ]
        cluster_parts.append('rcl.cluster_dominant AS race_cluster_dominant')
        cluster_parts.append('rcl.k_chosen AS race_cluster_k_chosen')
        select_fragment = ', '.join(cluster_parts)

        # fold_label and variant are controlled values (not user input),
        # inlined here for consistency with the rest of this file which
        # uses f-string substitution for similar controlled fields.
        join_fragment = (
            f"LEFT JOIN race_cluster_v1_scores rcl\n"
            f"            ON rcl.competition_id = cff.competition_id\n"
            f"            AND rcl.fold_label = '{fold_label}'\n"
            f"            AND rcl.variant = '{variant}'"
        )
        return select_fragment, join_fragment

    def _build_race_state_clauses(self) -> Tuple[str, str]:
        """
        Build SELECT and JOIN fragments for stage-race state features.

        Returns ('', '') when include_race_state is off. When on, pulls the
        22 state columns plus a derived race_state_missing flag. The JOIN is
        restricted to competition_type='stage' rows (Phase 1: gc rows keep
        their pre-race behavior; the mid-race GC head is a separate model),
        and is LEFT so rows without state — stage 1, one-day, gc, riders
        without complete prior-stage coverage, suspect races — come through
        as NULL with the flag set.
        """
        if not self.config.include_race_state:
            return '', ''

        state_parts = [f'rrs.{c}' for c in self.RACE_STATE_FEATURE_COLS]
        state_parts.append(
            '(CASE WHEN rrs.competition_id IS NULL THEN 1 ELSE 0 END) '
            'AS race_state_missing'
        )
        select_fragment = ', '.join(state_parts)

        join_fragment = (
            "LEFT JOIN rider_race_state rrs "
            "ON rrs.rider_id = rcs.rider_id "
            "AND rrs.competition_id = cff.competition_id "
            "AND cff.competition_type = 'stage'"
        )
        return select_fragment, join_fragment

    def _build_training_query(
        self,
        target: str,
        start_date: str,
        end_date: Optional[str],
        min_races_career: int,
        competition_types: List[str],
        race_categories: List[str]
    ) -> str:
        """Build the SQL query for training data."""

        # Select columns
        rider_cols = ', '.join([f'rcs.{c}' for c in self.RIDER_FEATURE_COLS])
        field_cols = ', '.join([f'cff.{c}' for c in self.FIELD_FEATURE_COLS])
        profile_cols = ', '.join([f'cff.{c}' for c in self.RACE_PROFILE_COLS])
        metadata_cols = ', '.join([f'cff.{c}' for c in self.METADATA_COLS])

        # Stage 0 gradient features (empty strings when flag is off)
        gradient_select, gradient_join = self._build_gradient_clauses()
        gradient_select_line = (
            f',\n            {gradient_select}' if gradient_select else ''
        )

        # Stage 1 cluster features (empty strings when flag is off)
        cluster_select, cluster_join = self._build_cluster_clauses()
        cluster_select_line = (
            f',\n            {cluster_select}' if cluster_select else ''
        )

        # Stage-race state features (empty strings when flag is off)
        state_select, state_join = self._build_race_state_clauses()
        state_select_line = (
            f',\n            {state_select}' if state_select else ''
        )

        # Target columns
        target_cols = 'rr.place_bucket'
        if target in ('time_gap', 'both'):
            target_cols += ', rr.time_gap'

        # Build WHERE conditions
        conditions = [
            f"cff.competition_date >= '{start_date}'",
            f"rcs.races_career >= {min_races_career}",
            "rr.place_bucket IS NOT NULL"
        ]

        if end_date:
            conditions.append(f"cff.competition_date <= '{end_date}'")

        if self.config.require_race_profile:
            conditions.append("cff.race_sprint_score IS NOT NULL")

        # Competition type filter
        if competition_types:
            type_list = ', '.join([f"'{t}'" for t in competition_types])
            conditions.append(f"cff.competition_type IN ({type_list})")

        # Race category filter
        if race_categories:
            cat_list = ', '.join([f"'{c}'" for c in race_categories])
            conditions.append(f"cff.race_category IN ({cat_list})")

        where_clause = ' AND '.join(conditions)

        query = f"""
        SELECT
            {rider_cols},
            {field_cols},
            {profile_cols},
            {metadata_cols},
            {target_cols}{gradient_select_line}{cluster_select_line}{state_select_line}
        FROM rider_competition_snapshots rcs
        JOIN competition_field_features cff
            ON rcs.competition_id = cff.competition_id
        JOIN rider_results rr
            ON rcs.rider_id = rr.rider_id
            AND rcs.competition_id = rr.competition_id
        {gradient_join}
        {cluster_join}
        {state_join}
        WHERE {where_clause}
        ORDER BY cff.competition_date, cff.competition_id, rcs.rider_id
        """

        return query

    def get_temporal_split(
        self,
        df: pd.DataFrame,
        train_end: str = '2022-12-31',
        val_end: str = '2023-06-30',
        date_col: str = 'competition_date'
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split data temporally for proper evaluation.

        Args:
            df: Full dataset
            train_end: Last date for training set (inclusive)
            val_end: Last date for validation set (inclusive)
            date_col: Name of date column

        Returns:
            (train, validation, test) DataFrames
        """
        train_end_dt = pd.to_datetime(train_end)
        val_end_dt = pd.to_datetime(val_end)

        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
            df = df.copy()
            df[date_col] = pd.to_datetime(df[date_col])

        train = df[df[date_col] <= train_end_dt].copy()
        val = df[(df[date_col] > train_end_dt) & (df[date_col] <= val_end_dt)].copy()
        test = df[df[date_col] > val_end_dt].copy()

        return train, val, test

    def load_race_startlist(
        self,
        competition_id: int,
        include_targets: bool = False
    ) -> pd.DataFrame:
        """
        Load all riders for a specific competition.

        Used for inference - predicting a race given its start list.

        Args:
            competition_id: ID of the competition
            include_targets: If True, include actual results (for evaluation)

        Returns:
            DataFrame with rider and race features
        """
        conn = self._get_connection()

        try:
            # Build query
            rider_cols = ', '.join([f'rcs.{c}' for c in self.RIDER_FEATURE_COLS])
            field_cols = ', '.join([f'cff.{c}' for c in self.FIELD_FEATURE_COLS])
            profile_cols = ', '.join([f'cff.{c}' for c in self.RACE_PROFILE_COLS])
            metadata_cols = ', '.join([f'cff.{c}' for c in self.METADATA_COLS])

            target_clause = ', rr.place_bucket, rr.time_gap' if include_targets else ''

            # Stage 0 gradient features (empty strings when flag is off)
            gradient_select, gradient_join = self._build_gradient_clauses()
            gradient_select_line = (
                f',\n                {gradient_select}' if gradient_select else ''
            )

            # Stage 1 cluster features (empty strings when flag is off)
            cluster_select, cluster_join = self._build_cluster_clauses()
            cluster_select_line = (
                f',\n                {cluster_select}' if cluster_select else ''
            )

            # Stage-race state features (empty strings when flag is off)
            state_select, state_join = self._build_race_state_clauses()
            state_select_line = (
                f',\n                {state_select}' if state_select else ''
            )

            query = f"""
            SELECT
                {rider_cols},
                {field_cols},
                {profile_cols},
                {metadata_cols}
                {target_clause}{gradient_select_line}{cluster_select_line}{state_select_line}
            FROM rider_competition_snapshots rcs
            JOIN competition_field_features cff
                ON rcs.competition_id = cff.competition_id
            {'JOIN' if include_targets else 'LEFT JOIN'} rider_results rr
                ON rcs.rider_id = rr.rider_id
                AND rcs.competition_id = rr.competition_id
            {gradient_join}
            {cluster_join}
            {state_join}
            WHERE rcs.competition_id = ?
            ORDER BY rcs.rider_id
            """

            df = pd.read_sql_query(query, conn, params=[competition_id])

        finally:
            conn.close()

        return df

    def load_races_in_range(
        self,
        start_date: str,
        end_date: str,
        competition_types: Optional[List[str]] = None,
        race_categories: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Get competitions in a date range.

        Args:
            start_date: Start of date range
            end_date: End of date range
            competition_types: Filter by competition type
            race_categories: Filter by race category

        Returns:
            DataFrame with competition metadata
        """
        conn = self._get_connection()

        try:
            conditions = [
                f"competition_date >= '{start_date}'",
                f"competition_date <= '{end_date}'"
            ]

            if competition_types:
                type_list = ', '.join([f"'{t}'" for t in competition_types])
                conditions.append(f"competition_type IN ({type_list})")

            if race_categories:
                cat_list = ', '.join([f"'{c}'" for c in race_categories])
                conditions.append(f"race_category IN ({cat_list})")

            where_clause = ' AND '.join(conditions)

            query = f"""
            SELECT
                competition_id, competition_name, competition_date,
                competition_type, race_category, field_size,
                race_dominant_profile
            FROM competition_field_features
            WHERE {where_clause}
            ORDER BY competition_date
            """

            df = pd.read_sql_query(query, conn)

        finally:
            conn.close()

        df['competition_date'] = pd.to_datetime(df['competition_date'])
        return df

    def get_data_summary(self) -> dict:
        """Get summary statistics about the available data."""
        conn = self._get_connection()

        try:
            summary = {}

            # Count rider snapshots
            cursor = conn.execute(
                "SELECT COUNT(*) FROM rider_competition_snapshots"
            )
            summary['total_rider_snapshots'] = cursor.fetchone()[0]

            # Count competitions
            cursor = conn.execute(
                "SELECT COUNT(*) FROM competition_field_features"
            )
            summary['total_competitions'] = cursor.fetchone()[0]

            # Date range
            cursor = conn.execute("""
                SELECT MIN(competition_date), MAX(competition_date)
                FROM competition_field_features
            """)
            row = cursor.fetchone()
            summary['date_range'] = (row[0], row[1])

            # Competition type breakdown
            cursor = conn.execute("""
                SELECT competition_type, COUNT(*)
                FROM competition_field_features
                GROUP BY competition_type
            """)
            summary['by_competition_type'] = dict(cursor.fetchall())

            # Race category breakdown
            cursor = conn.execute("""
                SELECT race_category, COUNT(*)
                FROM competition_field_features
                GROUP BY race_category
            """)
            summary['by_race_category'] = dict(cursor.fetchall())

        finally:
            conn.close()

        return summary


def load_training_data(
    start_date: str = '2018-01-01',
    min_races_career: int = 10,
    **kwargs
) -> pd.DataFrame:
    """
    Convenience function to load training data.

    Args:
        start_date: Start date for training data
        min_races_career: Minimum career races filter
        **kwargs: Additional arguments passed to CyclingDataPipeline.load_training_data

    Returns:
        Training DataFrame
    """
    config = DataConfig(
        start_date=start_date,
        min_races_career=min_races_career
    )
    pipeline = CyclingDataPipeline(config)
    return pipeline.load_training_data(**kwargs)


if __name__ == '__main__':
    # Test the pipeline
    print("Testing CyclingDataPipeline...")

    pipeline = CyclingDataPipeline()
    print(f"Database: {pipeline.db_path}")

    # Get data summary
    summary = pipeline.get_data_summary()
    print(f"\nData Summary:")
    print(f"  Total rider snapshots: {summary['total_rider_snapshots']:,}")
    print(f"  Total competitions: {summary['total_competitions']:,}")
    print(f"  Date range: {summary['date_range']}")
    print(f"  By competition type: {summary['by_competition_type']}")
    print(f"  By race category: {summary['by_race_category']}")

    # Load sample data
    print("\nLoading training data (2018+, min 10 career races)...")
    df = pipeline.load_training_data()
    print(f"  Loaded {len(df):,} samples")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Date range: {df['competition_date'].min()} to {df['competition_date'].max()}")

    # Test temporal split
    train, val, test = pipeline.get_temporal_split(df)
    print(f"\nTemporal split:")
    print(f"  Train: {len(train):,} samples ({train['competition_date'].min()} to {train['competition_date'].max()})")
    print(f"  Val:   {len(val):,} samples ({val['competition_date'].min()} to {val['competition_date'].max()})")
    print(f"  Test:  {len(test):,} samples ({test['competition_date'].min()} to {test['competition_date'].max()})")

    # Show sample
    print(f"\nSample columns:")
    print(df.columns.tolist())
