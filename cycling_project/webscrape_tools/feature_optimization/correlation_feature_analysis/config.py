"""
Configuration constants for correlation feature analysis.
"""

# Percentile levels to analyze
PERCENTILES = [30, 40, 50, 60, 70, 80, 90, 100]

# Correlation types available in the database
CORRELATION_TYPES = ['all_races', 'same_type', 'stage_one_days']

# Database configuration
CHUNK_SIZE = 100000  # Number of rows to load per chunk for memory efficiency

# Quality score weights
QUALITY_WEIGHTS = {
    'strength': 0.4,      # Weight for correlation strength
    'stability': 0.3,     # Weight for stability across percentiles
    'availability': 0.3   # Weight for data availability (inverse of NULL percentage)
}

# Pattern classification thresholds
PATTERN_THRESHOLDS = {
    'stability_threshold': 0.02,      # Std dev threshold for "highly stable" classification
    'trend_slope_threshold': 0.001,   # Minimum slope for trend detection
    'trend_r_threshold': 0.7          # Minimum r-value for trend significance
}

# Pattern penalty factors
PATTERN_PENALTIES = {
    'highly_variable': 0.7,     # Penalty for highly variable patterns
    'insufficient_data': 0.5,   # Penalty for insufficient data
    'complex': 0.9,            # Penalty for complex patterns
    'default': 1.0             # No penalty for good patterns
}

# Number of quality tiers
N_QUALITY_TIERS = 3

# Feature lists (from database schema)
# NOTE: The order here MUST match the order used when creating the correlation matrices
# in database_embeddings_storage. The quotes around percentile gap features are removed
# here since we're using them as Python identifiers, not SQL column names.
RACE_FEATURES = [
    # Basic Race Statistics
    'total_finishers', 'included_finishers', 'abandon_ratio',
    'winning_time', 'total_race_duration',
    
    # Performance Distribution
    'variance_absolute', 'variance_normalized',
    'std_deviation_absolute', 'std_deviation_normalized',
    'skewness_absolute', 'skewness_normalized',
    'kurtosis_absolute', 'kurtosis_normalized',
    'gini_coefficient',
    'shannon_entropy_absolute', 'shannon_entropy_normalized',
    
    # Time Gap Analysis
    '"5th_percentile_gap"', '"10th_percentile_gap"', '"15th_percentile_gap"',
    '"20th_percentile_gap"', '"25th_percentile_gap"', '"30th_percentile_gap"',
    '"35th_percentile_gap"', '"40th_percentile_gap"', '"45th_percentile_gap"',
    '"50th_percentile_gap"',
    
    # Group Dynamics
    'total_groups', 'riders_in_groups', 'proportion_in_groups',
    'largest_group_size', 'largest_group_position',
    'avg_group_size', 'std_group_size',
    'biggest_group_metric', 'time_gap_evenness_metric',
    'clumpiness_score', 'selection_metric'
]

# Output configuration
DEFAULT_OUTPUT_DIR = "correlation_analysis_output"
VISUALIZATION_DPI = 300
FIGURE_SIZE = (12, 8)

# Report configuration
TOP_N_FEATURES = 10  # Number of top features to show in reports
MAX_RECOMMENDATIONS = 5  # Maximum recommendations per percentile

# Database paths (relative to webscrape_tools directory)
DEFAULT_DB_PATH = "../database/database/cycling_races.db"