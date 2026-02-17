"""
Centralized imputation module for cycling analytics project.

Provides type-aware imputation defaults and utility functions for handling
missing data consistently across the codebase.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
import logging
import re

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS - AGE IMPUTATION
# =============================================================================

TOUR_LEVEL_AGE_MEDIANS: Dict[str, int] = {
    'wt': 28,   # World Tour riders tend to be more experienced
    'pro': 26,  # Pro riders slightly younger
    'd1': 24,   # Development/D1 riders youngest
}
DEFAULT_AGE: int = 27  # Fallback when tour level unknown

# =============================================================================
# CONSTANTS - NEW RIDER BUCKET DEFAULTS
# =============================================================================

NEW_RIDER_BASE_BY_TOUR: Dict[str, float] = {
    'wt': 5.5,
    'pro': 5.0,
    'd1': 4.5,
}
DEFAULT_NEW_RIDER_BASE: float = 5.0

BIB_ADJUSTMENTS: Dict[str, float] = {
    'leader': -1.5,      # personal_bib == 1
    'protected': -0.5,   # personal_bib in [2, 3]
    'support': 0.3,      # personal_bib in [7, 8]
    'default': 0.0,      # personal_bib in [4, 5, 6]
}

AGE_ADJUSTMENTS: Dict[str, float] = {
    'young': 0.3,   # age <= 23 (still developing)
    'prime': 0.0,   # 24 <= age <= 30 (peak performance years)
    'veteran': 0.2, # age > 30 (slight decline expected)
}

NEW_RIDER_MIN_PREDICTION: float = 3.0
NEW_RIDER_MAX_PREDICTION: float = 6.0

# =============================================================================
# CONSTANTS - FEATURE TYPE DEFINITIONS
# =============================================================================

class FeatureType:
    """Enumeration of feature types for imputation."""
    PROPORTION = 'proportion'
    COUNT = 'count'
    SUM = 'sum'
    CATEGORICAL = 'categorical'
    CONTINUOUS = 'continuous'
    AGE = 'age'


# Feature type patterns - order matters (more specific patterns first)
FEATURE_TYPE_PATTERNS: List[tuple] = [
    # PROPORTION patterns
    (r'.*proportion.*', FeatureType.PROPORTION),
    (r'.*rate.*', FeatureType.PROPORTION),
    (r'.*success.*', FeatureType.PROPORTION),
    (r'.*pct.*', FeatureType.PROPORTION),
    (r'.*percent.*', FeatureType.PROPORTION),

    # CATEGORICAL patterns
    (r'.*cluster.*', FeatureType.CATEGORICAL),
    (r'.*label.*', FeatureType.CATEGORICAL),
    (r'.*encoded.*', FeatureType.CATEGORICAL),
    (r'.*category.*', FeatureType.CATEGORICAL),
    (r'rkf_cluster.*', FeatureType.CATEGORICAL),

    # SUM patterns
    (r'.*points.*', FeatureType.SUM),
    (r'.*total.*', FeatureType.SUM),

    # COUNT patterns
    (r'.*races.*', FeatureType.COUNT),
    (r'.*count.*', FeatureType.COUNT),
    (r'.*_n$', FeatureType.COUNT),
    (r'.*_num$', FeatureType.COUNT),

    # AGE patterns
    (r'.*age.*', FeatureType.AGE),
    (r'rider_age.*', FeatureType.AGE),
]

# Default values by feature type
FEATURE_TYPE_DEFAULTS: Dict[str, Union[float, int]] = {
    FeatureType.PROPORTION: 0.0,
    FeatureType.COUNT: 0,
    FeatureType.SUM: 0,
    FeatureType.CATEGORICAL: -1,  # Unknown signal
    FeatureType.CONTINUOUS: 0.0,  # Mean-centered assumption
    FeatureType.AGE: DEFAULT_AGE,
}

# =============================================================================
# AGE IMPUTATION FUNCTIONS
# =============================================================================

def get_age_by_tour_level(tour_level: Optional[str] = None) -> int:
    """
    Get the median age for a given tour level.

    Args:
        tour_level: Tour level string ('wt', 'pro', 'd1') or None

    Returns:
        Median age for the tour level, or DEFAULT_AGE if unknown
    """
    if tour_level is None:
        logger.debug(f"No tour level provided, using default age: {DEFAULT_AGE}")
        return DEFAULT_AGE

    tour_level_lower = tour_level.lower().strip()
    age = TOUR_LEVEL_AGE_MEDIANS.get(tour_level_lower, DEFAULT_AGE)

    if tour_level_lower not in TOUR_LEVEL_AGE_MEDIANS:
        logger.warning(f"Unknown tour level '{tour_level}', using default age: {DEFAULT_AGE}")

    return age


def impute_age(
    current_age: Optional[int],
    tour_level: Optional[str] = None,
    log_imputation: bool = True
) -> int:
    """
    Impute missing age using tour-level median.

    Args:
        current_age: Current age value (may be None or 0)
        tour_level: Tour level for context-aware imputation
        log_imputation: Whether to log when imputation occurs

    Returns:
        Imputed or original age value
    """
    # Check if age needs imputation (None or 0 are considered missing)
    if current_age is not None and current_age > 0:
        return current_age

    imputed_age = get_age_by_tour_level(tour_level)

    if log_imputation:
        logger.info(f"Imputing age: tour_level={tour_level} -> age={imputed_age}")

    return imputed_age

# =============================================================================
# NEW RIDER DEFAULT PREDICTION FUNCTIONS
# =============================================================================

def get_bib_adjustment(personal_bib: Optional[int]) -> float:
    """
    Get the bib-based adjustment for new rider prediction.

    Args:
        personal_bib: Personal bib number (1-8 typically)

    Returns:
        Adjustment value to add to base prediction
    """
    if personal_bib is None:
        return BIB_ADJUSTMENTS['default']

    if personal_bib == 1:
        return BIB_ADJUSTMENTS['leader']
    elif personal_bib in [2, 3]:
        return BIB_ADJUSTMENTS['protected']
    elif personal_bib in [7, 8]:
        return BIB_ADJUSTMENTS['support']
    else:
        return BIB_ADJUSTMENTS['default']


def get_age_adjustment(age: Optional[int]) -> float:
    """
    Get the age-based adjustment for new rider prediction.

    Args:
        age: Rider age (already imputed if necessary)

    Returns:
        Adjustment value to add to base prediction
    """
    if age is None:
        return AGE_ADJUSTMENTS['prime']  # Assume prime if unknown

    if age <= 23:
        return AGE_ADJUSTMENTS['young']
    elif age <= 30:
        return AGE_ADJUSTMENTS['prime']
    else:
        return AGE_ADJUSTMENTS['veteran']


def extract_personal_bib(bib_number: Optional[Union[str, int]]) -> Optional[int]:
    """
    Extract the personal bib number from a raw bib number.

    The personal bib is the last digit of the bib number.

    Args:
        bib_number: Raw bib number (string or int)

    Returns:
        Personal bib number (1-8 typically) or None if invalid
    """
    if bib_number is None:
        return None

    try:
        bib_str = str(bib_number).strip()
        if not bib_str:
            return None
        return int(bib_str[-1])
    except (ValueError, IndexError):
        return None


def calculate_new_rider_default(
    tour_level: Optional[str] = None,
    personal_bib: Optional[int] = None,
    age: Optional[int] = None,
    log_calculation: bool = False
) -> float:
    """
    Calculate context-aware default prediction for new riders.

    Uses tour level, bib number, and age to create a more informed
    default than the hardcoded 6.0 previously used.

    Args:
        tour_level: Tour level ('wt', 'pro', 'd1')
        personal_bib: Personal bib number (1-8)
        age: Rider age (will be imputed if None)
        log_calculation: Whether to log the calculation details

    Returns:
        Default prediction value clamped to [3.0, 6.0]
    """
    # Get base by tour level
    tour_lower = tour_level.lower().strip() if tour_level else None
    base = NEW_RIDER_BASE_BY_TOUR.get(tour_lower, DEFAULT_NEW_RIDER_BASE)

    # Impute age if necessary for adjustment calculation
    if age is None or age <= 0:
        age = get_age_by_tour_level(tour_level)

    # Calculate adjustments
    bib_adj = get_bib_adjustment(personal_bib)
    age_adj = get_age_adjustment(age)

    # Compute result
    result = base + bib_adj + age_adj

    # Clamp to valid range
    clamped = max(NEW_RIDER_MIN_PREDICTION, min(NEW_RIDER_MAX_PREDICTION, result))

    if log_calculation:
        logger.debug(
            f"New rider default: base={base} (tour={tour_level}) + "
            f"bib_adj={bib_adj} (bib={personal_bib}) + "
            f"age_adj={age_adj} (age={age}) = {result} -> clamped to {clamped}"
        )

    return clamped

# =============================================================================
# TYPE-AWARE FILLNA FUNCTIONS
# =============================================================================

def infer_feature_type(feature_name: str) -> str:
    """
    Infer the feature type from its name using pattern matching.

    Args:
        feature_name: Name of the feature column

    Returns:
        Feature type string
    """
    feature_lower = feature_name.lower()

    for pattern, feature_type in FEATURE_TYPE_PATTERNS:
        if re.match(pattern, feature_lower):
            return feature_type

    # Default to CONTINUOUS if no pattern matches
    return FeatureType.CONTINUOUS


def get_default_for_feature(
    feature_name: str,
    tour_level: Optional[str] = None
) -> Union[float, int]:
    """
    Get the appropriate default value for a feature.

    Args:
        feature_name: Name of the feature column
        tour_level: Tour level for age imputation context

    Returns:
        Default value appropriate for the feature type
    """
    feature_type = infer_feature_type(feature_name)

    if feature_type == FeatureType.AGE:
        return get_age_by_tour_level(tour_level)

    return FEATURE_TYPE_DEFAULTS[feature_type]


def smart_fillna(
    df: pd.DataFrame,
    feature_columns: Optional[List[str]] = None,
    tour_level: Optional[str] = None,
    log_imputation: bool = False
) -> pd.DataFrame:
    """
    Apply type-aware fillna to a DataFrame.

    Uses feature name patterns to determine appropriate default values
    for different types of features.

    Args:
        df: DataFrame to fill missing values in
        feature_columns: Specific columns to fill. If None, fills all columns.
        tour_level: Tour level for age imputation context
        log_imputation: Whether to log imputation details

    Returns:
        DataFrame with missing values filled
    """
    result = df.copy()

    columns_to_fill = feature_columns if feature_columns else df.columns.tolist()

    imputation_summary = {}

    for col in columns_to_fill:
        if col not in result.columns:
            continue

        missing_count = result[col].isna().sum()
        if missing_count == 0:
            continue

        default_value = get_default_for_feature(col, tour_level)
        result[col] = result[col].fillna(default_value)

        if log_imputation:
            feature_type = infer_feature_type(col)
            imputation_summary[col] = {
                'type': feature_type,
                'default': default_value,
                'count': missing_count
            }

    if log_imputation and imputation_summary:
        logger.info(f"Imputation summary: {imputation_summary}")

    return result


def get_feature_type_mapping(feature_columns: List[str]) -> Dict[str, str]:
    """
    Get a mapping of feature names to their inferred types.

    Useful for debugging and understanding how features will be imputed.

    Args:
        feature_columns: List of feature column names

    Returns:
        Dictionary mapping feature names to their types
    """
    return {col: infer_feature_type(col) for col in feature_columns}
