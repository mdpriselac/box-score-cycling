"""
Feature Engineering for Cycling Race Predictions

Creates derived features, handles categorical encoding, and applies
type-aware imputation for missing values.

Key features:
1. Rider vs field comparisons (bucket gap, experience ratio)
2. Profile matching (rider best profile vs race dominant profile)
3. Profile-weighted expected bucket
4. Categorical encoding (one-hot and ordinal)
5. Type-aware imputation using engineering_tools/imputation.py patterns
"""

from typing import List, Dict, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""
    # Feature groups to include
    include_rider_features: bool = True
    include_field_features: bool = True
    include_race_profile: bool = True
    include_derived_features: bool = True

    # Encoding options
    encode_competition_type: bool = True  # One-hot encode
    encode_race_category: bool = True  # Ordinal encode
    encode_best_profile: bool = True  # One-hot encode
    encode_race_dominant_profile: bool = True  # One-hot encode

    # Imputation
    impute_missing: bool = True


class FeatureEngineer:
    """
    Creates derived features from raw rider/field/race data.

    Handles:
    - Derived feature creation
    - Categorical encoding
    - Type-aware imputation
    - Feature column tracking for consistent inference
    """

    # Base feature groups
    RIDER_NUMERIC_FEATURES = [
        'age', 'team_bib', 'personal_bib', 'races_career', 'races_this_year',
        'stage_avg_bucket', 'stage_count',
        'one_day_avg_bucket', 'one_day_count',
        'gc_avg_bucket', 'gc_count',
        'wt_avg_bucket', 'wt_count',
        'pro_avg_bucket', 'pro_count',
        'd1_avg_bucket', 'd1_count',
        'sprint_avg_bucket', 'mountain_avg_bucket', 'hilly_avg_bucket',
        'rolling_avg_bucket', 'breakaway_avg_bucket', 'time_trial_avg_bucket',
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

    FIELD_NUMERIC_FEATURES = [
        'field_size',
        'experience_mean', 'experience_median', 'experience_std',
        'experience_min', 'experience_max', 'experience_p25', 'experience_p75',
        'bucket_mean', 'bucket_median', 'bucket_std',
        'bucket_min', 'bucket_max', 'bucket_p25', 'bucket_p75',
        'sprinter_count', 'climber_count', 'hilly_specialist_count',
        'rolling_specialist_count', 'breakaway_specialist_count',
        'time_trialist_count', 'unknown_profile_count'
    ]

    RACE_PROFILE_FEATURES = [
        'race_sprint_score', 'race_mountain_score', 'race_hilly_score',
        'race_rolling_score', 'race_breakaway_score', 'race_time_trial_score'
    ]

    CATEGORICAL_FEATURES = [
        'best_profile', 'race_dominant_profile',
        'competition_type', 'race_category'
    ]

    METADATA_COLS = [
        'rider_id', 'rider_name', 'competition_id',
        'competition_name', 'competition_date'
    ]

    # Age imputation defaults by tour level
    TOUR_LEVEL_AGE_MEDIANS = {
        'wt': 28,
        'pro': 26,
        'd1': 24,
    }
    DEFAULT_AGE = 27

    # Race category ordinal encoding
    RACE_CATEGORY_MAP = {'wt': 0, 'pro': 1, 'd1': 2}

    def __init__(self, config: Optional[FeatureConfig] = None):
        self.config = config or FeatureConfig()
        self.feature_columns: Optional[List[str]] = None
        self._fitted = False

    def fit_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Fit the feature engineer and transform data.

        Call this on training data to learn feature columns.

        Args:
            df: Training data with raw features

        Returns:
            Transformed DataFrame with derived features
        """
        df = self.create_derived_features(df)

        if self.config.impute_missing:
            df = self.apply_imputation(df)

        df = self.encode_categoricals(df, fit=True)

        # Store feature columns (excluding metadata and targets)
        self.feature_columns = self._get_feature_columns(df)
        self._fitted = True

        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform data using fitted feature engineer.

        Args:
            df: Data with raw features

        Returns:
            Transformed DataFrame
        """
        if not self._fitted:
            raise ValueError("FeatureEngineer must be fitted before transform")

        df = self.create_derived_features(df)

        if self.config.impute_missing:
            df = self.apply_imputation(df)

        df = self.encode_categoricals(df, fit=False)

        return df

    def create_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add derived features to the dataset.

        Creates features that combine rider, field, and race information.
        """
        df = df.copy()

        if not self.config.include_derived_features:
            return df

        # 1. Rider vs Field comparisons
        # How does this rider compare to the average of the field?
        df['rider_vs_field_bucket_gap'] = (
            df['stage_avg_bucket'].fillna(5.0) - df['bucket_mean'].fillna(5.0)
        )

        # Rider experience relative to field
        df['rider_vs_field_experience_ratio'] = (
            df['races_career'].fillna(0) / (df['experience_mean'].fillna(50) + 1)
        )

        # 2. Profile match indicator
        # Does the rider's best profile match the race's dominant profile?
        df['profile_match'] = (
            df['best_profile'] == df['race_dominant_profile']
        ).astype(int)

        # 3. Profile-weighted expected bucket
        # Weighted sum of rider's profile-specific averages by race profile scores
        profile_pairs = [
            ('sprint_avg_bucket', 'race_sprint_score'),
            ('mountain_avg_bucket', 'race_mountain_score'),
            ('hilly_avg_bucket', 'race_hilly_score'),
            ('rolling_avg_bucket', 'race_rolling_score'),
            ('breakaway_avg_bucket', 'race_breakaway_score'),
            ('time_trial_avg_bucket', 'race_time_trial_score'),
        ]

        weighted_sum = pd.Series(0.0, index=df.index)
        for rider_col, race_col in profile_pairs:
            rider_val = df[rider_col].fillna(5.0)
            race_val = df[race_col].fillna(0.0)
            weighted_sum += rider_val * race_val

        df['profile_weighted_expected'] = weighted_sum

        # 4. Relevant type average (based on competition_type)
        df['relevant_type_avg_bucket'] = np.where(
            df['competition_type'] == 'stage',
            df['stage_avg_bucket'].fillna(5.0),
            np.where(
                df['competition_type'] == 'one_day',
                df['one_day_avg_bucket'].fillna(5.0),
                df['gc_avg_bucket'].fillna(5.0)
            )
        )

        # 5. Relevant category average (based on race_category)
        df['relevant_category_avg_bucket'] = np.where(
            df['race_category'] == 'wt',
            df['wt_avg_bucket'].fillna(5.0),
            np.where(
                df['race_category'] == 'pro',
                df['pro_avg_bucket'].fillna(5.0),
                df['d1_avg_bucket'].fillna(5.0)
            )
        )

        # 6. Team role indicators (from personal bib number)
        df['is_team_leader'] = (df['personal_bib'] == 1).astype(int)
        df['is_protected_rider'] = df['personal_bib'].isin([1, 2, 3]).astype(int)

        # 7. Experience tier
        df['experience_tier'] = pd.cut(
            df['races_career'].fillna(0),
            bins=[-1, 30, 100, 300, float('inf')],
            labels=[0, 1, 2, 3]  # novice, developing, experienced, veteran
        ).astype(float)

        # 8. Field quality score (higher = stronger field)
        df['field_quality_score'] = (5.0 - df['bucket_mean'].fillna(5.0)) / 2.0

        # 9. Specialist count relevant to race
        specialist_map = {
            'sprint': 'sprinter_count',
            'mountain': 'climber_count',
            'hilly': 'hilly_specialist_count',
            'rolling': 'rolling_specialist_count',
            'breakaway': 'breakaway_specialist_count',
            'time_trial': 'time_trialist_count',
        }

        df['matching_specialists_in_field'] = 0
        for profile, col in specialist_map.items():
            mask = df['race_dominant_profile'] == profile
            if col in df.columns:
                df.loc[mask, 'matching_specialists_in_field'] = df.loc[mask, col]

        # 10. Rider's best profile bucket (the bucket for their strongest profile type)
        df['best_profile_bucket'] = df.apply(
            lambda row: self._get_best_profile_bucket(row), axis=1
        )

        # 11. Form-based derived features
        # Form vs field comparison
        df['form_vs_field_gap'] = (
            df['form_recent_avg_bucket'].fillna(4.0) -
            df['bucket_mean'].fillna(4.0)
        )

        # Form improvement indicator (negative = improving)
        df['is_improving_form'] = (df['form_delta'].fillna(0) < -0.5).astype(int)

        # Fresh vs rusty indicator
        df['is_fresh'] = (df['days_since_last_race'].fillna(90) < 14).astype(int)
        df['is_rusty'] = (df['days_since_last_race'].fillna(90) > 45).astype(int)

        # Form confidence (based on recent race count)
        df['form_confidence'] = df['form_recent_count'].fillna(0) / 5.0

        # 12. Competition-type specialization features

        # 12a. Type experience ratio: what fraction of career in this race type?
        # Normalized to account for stage races generating many more competitions
        # than GC (5-21 stages per 1 GC). Use sqrt to compress the stage inflation.
        stage_ct = df['stage_count'].fillna(0)
        oneday_ct = df['one_day_count'].fillna(0)
        gc_ct = df['gc_count'].fillna(0)
        relevant_type_ct = np.where(
            df['competition_type'] == 'stage', stage_ct,
            np.where(df['competition_type'] == 'one_day', oneday_ct, gc_ct)
        )
        career = df['races_career'].fillna(1).clip(lower=1)
        df['type_experience_ratio'] = np.sqrt(relevant_type_ct) / np.sqrt(career)

        # 12b. GC specialist score: gc_avg shrunk toward neutral (5.0) based on
        # sample size. With few GC races, stays near 5.0; with many, reflects true avg.
        gc_avg = df['gc_avg_bucket'].fillna(5.0)
        shrinkage_k = 10.0
        df['gc_specialist_score'] = (
            gc_ct / (gc_ct + shrinkage_k) * gc_avg +
            shrinkage_k / (gc_ct + shrinkage_k) * 5.0
        )

        # 13. Team-based derived features
        # Is best on team by quality
        df['is_team_best'] = (
            df['stage_avg_bucket'].fillna(5.0) <= df['team_quality_min'].fillna(5.0)
        ).astype(int)

        # Team support depth (quality depth relative to team size)
        df['team_support_ratio'] = (
            df['team_depth'].fillna(0) / (df['team_size'].fillna(1) + 1)
        )

        # Rider vs team quality gap
        df['rider_vs_team_gap'] = (
            df['stage_avg_bucket'].fillna(4.0) -
            df['team_quality_mean'].fillna(4.0)
        )

        return df

    def _get_best_profile_bucket(self, row: pd.Series) -> float:
        """Get the bucket average for the rider's best profile type."""
        best = row.get('best_profile')
        if pd.isna(best) or best == 'unknown':
            return 5.0

        profile_col_map = {
            'sprint': 'sprint_avg_bucket',
            'mountain': 'mountain_avg_bucket',
            'hilly': 'hilly_avg_bucket',
            'rolling': 'rolling_avg_bucket',
            'breakaway': 'breakaway_avg_bucket',
            'time_trial': 'time_trial_avg_bucket',
        }

        col = profile_col_map.get(best)
        if col and col in row.index:
            val = row[col]
            return val if pd.notna(val) else 5.0
        return 5.0

    def apply_imputation(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply type-aware imputation to missing values.

        Uses patterns from engineering_tools/imputation.py.
        """
        df = df.copy()

        # Age imputation by tour level
        if 'age' in df.columns:
            for tour, median_age in self.TOUR_LEVEL_AGE_MEDIANS.items():
                mask = (df['age'].isna() | (df['age'] <= 0)) & (df['race_category'] == tour)
                df.loc[mask, 'age'] = median_age

            # Default for remaining missing
            df['age'] = df['age'].fillna(self.DEFAULT_AGE)
            df.loc[df['age'] <= 0, 'age'] = self.DEFAULT_AGE

        # Bucket averages default to 5.0 (mid-field expectation)
        bucket_cols = [c for c in df.columns if 'avg_bucket' in c]
        for col in bucket_cols:
            df[col] = df[col].fillna(5.0)

        # Count columns default to 0
        count_cols = [c for c in df.columns if '_count' in c]
        for col in count_cols:
            df[col] = df[col].fillna(0)

        # Experience columns
        if 'races_career' in df.columns:
            df['races_career'] = df['races_career'].fillna(0)
        if 'races_this_year' in df.columns:
            df['races_this_year'] = df['races_this_year'].fillna(0)

        # Field features - use reasonable defaults
        field_defaults = {
            'field_size': 100,
            'experience_mean': 50,
            'experience_median': 40,
            'experience_std': 30,
            'experience_min': 0,
            'experience_max': 200,
            'experience_p25': 20,
            'experience_p75': 80,
            'bucket_mean': 5.0,
            'bucket_median': 5.0,
            'bucket_std': 1.5,
            'bucket_min': 1.0,
            'bucket_max': 7.0,
            'bucket_p25': 4.0,
            'bucket_p75': 6.0,
        }
        for col, default in field_defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)

        # Specialist counts default to 0
        specialist_cols = [
            'sprinter_count', 'climber_count', 'hilly_specialist_count',
            'rolling_specialist_count', 'breakaway_specialist_count',
            'time_trialist_count', 'unknown_profile_count'
        ]
        for col in specialist_cols:
            if col in df.columns:
                df[col] = df[col].fillna(0)

        # Race profile scores default to 0 (will sum to less than 1 but that's ok)
        profile_cols = [c for c in df.columns if c.startswith('race_') and c.endswith('_score')]
        for col in profile_cols:
            df[col] = df[col].fillna(0)

        # Categorical defaults
        if 'best_profile' in df.columns:
            df['best_profile'] = df['best_profile'].fillna('unknown')
        if 'race_dominant_profile' in df.columns:
            df['race_dominant_profile'] = df['race_dominant_profile'].fillna('unknown')

        # Bib numbers
        if 'team_bib' in df.columns:
            df['team_bib'] = df['team_bib'].fillna(10)  # High bib = less protected
        if 'personal_bib' in df.columns:
            df['personal_bib'] = df['personal_bib'].fillna(5)  # Middle of pack

        # Form feature imputation
        form_defaults = {
            'form_recent_avg_bucket': 4.0,  # Mid-field expectation
            'form_recent_best_bucket': 4.0,
            'form_recent_count': 0,
            'form_delta': 0.0,  # No change from career
            'form_profile_recent_avg': 4.0,
            'days_since_last_race': 90,  # Cap value (rusty)
        }
        for col, default in form_defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)

        # Team feature imputation
        team_defaults = {
            'team_quality_mean': 4.0,
            'team_quality_median': 4.0,
            'team_quality_std': 1.5,  # Typical team spread
            'team_quality_min': 3.5,
            'team_quality_max': 5.0,
            'team_quality_p25': 3.5,
            'team_quality_p75': 5.0,
            'team_size': 6,  # Typical team size
            'team_depth': 2,
        }
        for col, default in team_defaults.items():
            if col in df.columns:
                df[col] = df[col].fillna(default)

        return df

    # Expected one-hot encoded column names (to ensure consistency)
    COMPETITION_TYPE_COLS = ['comp_type_gc', 'comp_type_one_day', 'comp_type_stage']
    RIDER_PROFILE_COLS = [
        'rider_profile_breakaway', 'rider_profile_hilly', 'rider_profile_mountain',
        'rider_profile_rolling', 'rider_profile_sprint', 'rider_profile_time_trial',
        'rider_profile_unknown'
    ]
    RACE_PROFILE_ENCODED_COLS = [
        'race_profile_breakaway', 'race_profile_hilly', 'race_profile_mountain',
        'race_profile_rolling', 'race_profile_sprint', 'race_profile_time_trial'
    ]

    def encode_categoricals(self, df: pd.DataFrame, fit: bool = True) -> pd.DataFrame:
        """
        Encode categorical features.

        - competition_type: one-hot (3 values: stage, one_day, gc)
        - race_category: ordinal (wt=0, pro=1, d1=2)
        - best_profile: one-hot (7 values)
        - race_dominant_profile: one-hot (6 values)

        Ensures consistent columns across train/inference by adding missing columns.
        """
        df = df.copy()

        # Ordinal encoding for race_category
        if self.config.encode_race_category and 'race_category' in df.columns:
            df['race_category_encoded'] = df['race_category'].map(self.RACE_CATEGORY_MAP)
            df['race_category_encoded'] = df['race_category_encoded'].fillna(1)  # Default to pro

        # One-hot for competition_type
        if self.config.encode_competition_type and 'competition_type' in df.columns:
            df = pd.get_dummies(
                df, columns=['competition_type'],
                prefix='comp_type', dtype=float
            )
            # Ensure all expected columns exist
            for col in self.COMPETITION_TYPE_COLS:
                if col not in df.columns:
                    df[col] = 0.0

        # One-hot for best_profile
        if self.config.encode_best_profile and 'best_profile' in df.columns:
            df = pd.get_dummies(
                df, columns=['best_profile'],
                prefix='rider_profile', dtype=float
            )
            # Ensure all expected columns exist
            for col in self.RIDER_PROFILE_COLS:
                if col not in df.columns:
                    df[col] = 0.0

        # One-hot for race_dominant_profile
        if self.config.encode_race_dominant_profile and 'race_dominant_profile' in df.columns:
            df = pd.get_dummies(
                df, columns=['race_dominant_profile'],
                prefix='race_profile', dtype=float
            )
            # Ensure all expected columns exist
            for col in self.RACE_PROFILE_ENCODED_COLS:
                if col not in df.columns:
                    df[col] = 0.0

        return df

    def _get_feature_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of feature columns (excluding metadata and targets)."""
        exclude_cols = set(self.METADATA_COLS + ['place_bucket', 'time_gap'])

        # Also exclude any remaining categorical columns that weren't encoded
        exclude_cols.update(['race_category'])  # Keep encoded version

        feature_cols = [
            col for col in df.columns
            if col not in exclude_cols
            and not col.endswith('_date')
            and not col.endswith('_name')
        ]

        return feature_cols

    def get_feature_columns(self) -> List[str]:
        """
        Get the list of feature columns for modeling.

        Must call fit_transform first.
        """
        if not self._fitted:
            raise ValueError("FeatureEngineer must be fitted first")
        return self.feature_columns.copy()

    def get_feature_matrix(
        self,
        df: pd.DataFrame,
        include_target: bool = False
    ) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
        """
        Extract feature matrix X and optionally target y.

        Args:
            df: Transformed DataFrame
            include_target: If True, also return target column

        Returns:
            (X, y) tuple where y is None if include_target=False
        """
        if not self._fitted:
            raise ValueError("FeatureEngineer must be fitted first")

        # Create X with all expected feature columns (build dict first to avoid fragmentation)
        feature_data = {}
        for col in self.feature_columns:
            if col in df.columns:
                feature_data[col] = df[col].values
            else:
                # Add missing column with default value
                feature_data[col] = np.zeros(len(df))
        X = pd.DataFrame(feature_data, index=df.index)

        y = None
        if include_target and 'place_bucket' in df.columns:
            y = df['place_bucket'].copy()

        return X, y


def create_training_features(
    df: pd.DataFrame,
    config: Optional[FeatureConfig] = None
) -> Tuple[pd.DataFrame, FeatureEngineer]:
    """
    Convenience function to create training features.

    Args:
        df: Raw training data from data_pipeline
        config: Optional feature configuration

    Returns:
        (transformed_df, feature_engineer) tuple
    """
    engineer = FeatureEngineer(config)
    transformed = engineer.fit_transform(df)
    return transformed, engineer


if __name__ == '__main__':
    # Test the feature engineering
    import sys
    sys.path.insert(0, '..')

    from prediction_tools.data_pipeline import CyclingDataPipeline

    print("Testing FeatureEngineer...")

    # Load sample data
    pipeline = CyclingDataPipeline()
    df = pipeline.load_training_data()
    print(f"Loaded {len(df):,} samples with {len(df.columns)} columns")

    # Apply feature engineering
    engineer = FeatureEngineer()
    df_transformed = engineer.fit_transform(df)

    print(f"\nAfter feature engineering:")
    print(f"  Samples: {len(df_transformed):,}")
    print(f"  Total columns: {len(df_transformed.columns)}")
    print(f"  Feature columns: {len(engineer.get_feature_columns())}")

    # Show derived features
    derived = [
        'rider_vs_field_bucket_gap', 'rider_vs_field_experience_ratio',
        'profile_match', 'profile_weighted_expected',
        'relevant_type_avg_bucket', 'relevant_category_avg_bucket',
        'is_team_leader', 'is_protected_rider', 'experience_tier',
        'field_quality_score', 'matching_specialists_in_field',
        'best_profile_bucket'
    ]
    print(f"\nDerived features:")
    for feat in derived:
        if feat in df_transformed.columns:
            print(f"  {feat}: mean={df_transformed[feat].mean():.3f}")

    # Show encoded columns
    encoded = [c for c in df_transformed.columns if c.startswith(('comp_type_', 'rider_profile_', 'race_profile_'))]
    print(f"\nEncoded columns ({len(encoded)}):")
    for col in encoded[:10]:
        print(f"  {col}")
    if len(encoded) > 10:
        print(f"  ... and {len(encoded) - 10} more")

    # Check for NaN
    nan_counts = df_transformed.isna().sum()
    nan_cols = nan_counts[nan_counts > 0]
    if len(nan_cols) > 0:
        print(f"\nColumns with NaN values:")
        for col, count in nan_cols.items():
            print(f"  {col}: {count}")
    else:
        print("\nNo NaN values in transformed data")
