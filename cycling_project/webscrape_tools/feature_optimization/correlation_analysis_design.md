# Correlation Feature Quality Analysis System

## Project Overview

This system analyzes the quality and behavior of correlations between rider performance and race features across different percentile levels. It's designed to help us understand which race features are actually predictive of rider performance and at what competitive depths they work best.

### Context Within the Larger Project

We have two complementary analysis systems:

1. **Race Feature N-Analysis** (already built): Examines how race features behave statistically as we expand from analyzing top 30% of riders to all riders
2. **Correlation Quality Analysis** (this system): Examines how well each feature correlates with rider performance at different percentile levels

The end goal is to integrate both systems to select optimal features for machine learning models that predict race outcomes. A feature might be statistically stable (from N-analysis) but have weak predictive power (from correlation analysis), or vice versa.

### What This System Does

1. **Analyzes correlation patterns**: For each feature, examines how its correlation with rider performance changes across percentiles (30%, 40%, ..., 100%)

2. **Classifies correlation behaviors**:
   - **Highly stable**: Consistent correlation across all percentiles
   - **Elite-focused**: Strong correlation for top riders, weakens as more riders included
   - **Mass-inclusive**: Weak for elite, strengthens with broader field
   - **Middle-peak**: Optimal at middle percentiles
   - **Highly variable**: Unstable, unreliable correlations

3. **Assigns quality scores** based on:
   - Correlation strength (how predictive)
   - Stability (how consistent across percentiles)
   - Data availability (how much NULL data)

4. **Creates quality tiers**: Similar to the N-analysis system, features are ranked into three tiers

## Quick Testing Strategy

### 1. Database Connection Test
```python
# Test basic connectivity and data availability
def test_database_connection():
    analyzer = CorrelationQualityAnalyzer("path/to/db")
    
    # Check if we can query the data
    test_query = """
    SELECT COUNT(DISTINCT feature_name) as feature_count,
           COUNT(DISTINCT percentile) as percentile_count,
           COUNT(*) as total_rows
    FROM rider_correlations_denorm
    WHERE correlation_type = 'all_races'
    """
    
    result = pd.read_sql_query(test_query, analyzer.conn)
    print(f"Features: {result['feature_count'][0]}")
    print(f"Percentiles: {result['percentile_count'][0]}")
    print(f"Total rows: {result['total_rows'][0]}")
    
    # Should see 37 features, 8 percentiles
    assert result['feature_count'][0] == 37
    assert result['percentile_count'][0] == 8
```

### 2. Single Feature Analysis Test
```python
# Test analysis for one feature to verify calculations
def test_single_feature_analysis():
    analyzer = CorrelationQualityAnalyzer("path/to/db")
    
    # Pick a known feature
    test_feature = 'abandon_ratio'
    
    # Get stats for just this feature
    stats_df = analyzer.analyze_all_features('all_races')
    feature_stats = stats_df[stats_df['feature_name'] == test_feature]
    
    print(f"\nStats for {test_feature}:")
    print(feature_stats[['percentile', 'mean_correlation', 'std_correlation', 'sample_size']])
    
    # Verify we have data for multiple percentiles
    assert len(feature_stats) >= 4
    
    # Check that statistics are reasonable
    assert all(abs(feature_stats['mean_correlation']) <= 1.0)
    assert all(feature_stats['sample_size'] > 0)
```

### 3. Pattern Classification Test
```python
# Test pattern classification logic
def test_pattern_classification():
    analyzer = CorrelationQualityAnalyzer("path/to/db")
    
    # Test with known patterns
    test_cases = [
        # (slope, r_value, correlations, stability, expected_pattern)
        (0.0001, 0.1, np.array([0.2, 0.21, 0.19, 0.20]), 0.95, 'stable'),
        (-0.002, -0.8, np.array([0.5, 0.4, 0.3, 0.2]), 0.7, 'elite_focused'),
        (0.002, 0.8, np.array([0.2, 0.3, 0.4, 0.5]), 0.7, 'mass_inclusive'),
    ]
    
    for slope, r_value, corrs, stability, expected in test_cases:
        pattern = analyzer._classify_pattern(slope, r_value, corrs, stability)
        print(f"Expected: {expected}, Got: {pattern}")
        assert pattern == expected
```

### 4. Memory Usage Test
```python
# Test chunked reading for memory efficiency
def test_memory_efficient_loading():
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    analyzer = CorrelationQualityAnalyzer("path/to/db")
    stats_df = analyzer.analyze_all_features('all_races')
    
    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory
    
    print(f"Memory increase: {memory_increase:.2f} MB")
    print(f"Rows processed: {len(stats_df)}")
    
    # Should stay under reasonable limit (e.g., 500MB for full dataset)
    assert memory_increase < 500
```

### 5. End-to-End Report Generation Test
```python
# Test full pipeline
def test_full_report_generation():
    analyzer = CorrelationQualityAnalyzer("path/to/db")
    
    # Generate report for smallest correlation type first
    report = analyzer.generate_summary_report('same_type')
    
    # Verify report structure
    required_keys = [
        'analysis_date', 'correlation_type', 'total_features',
        'pattern_distribution', 'tier_distribution', 'top_features',
        'feature_details', 'quality_tiers', 'recommendations'
    ]
    
    for key in required_keys:
        assert key in report, f"Missing required key: {key}"
    
    # Check tier distribution adds up
    tier_sum = sum(report['tier_distribution'].values())
    assert tier_sum == report['total_features']
    
    # Save and verify output
    analyzer.save_report(report, "test_output")
    assert Path("test_output/correlation_quality_report_same_type.json").exists()
```

## Modularization Instructions

Break the monolithic `CorrelationQualityAnalyzer` into these modules:

### 1. `data_loader.py`
```python
class CorrelationDataLoader:
    """Handles all database interactions and data loading"""
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        
    def load_correlation_data(self, correlation_type: str, chunk_size: int = 100000):
        """Load correlation data in chunks"""
        pass
        
    def get_feature_list(self):
        """Get list of all features in database"""
        pass
        
    def get_data_quality_summary(self):
        """Quick summary of data availability"""
        pass
```

### 2. `statistics_calculator.py`
```python
class CorrelationStatisticsCalculator:
    """Calculates statistical measures for correlations"""
    
    @staticmethod
    def calculate_feature_stats(feature_data: pd.DataFrame) -> CorrelationStats:
        """Calculate comprehensive stats for a feature"""
        pass
        
    @staticmethod
    def calculate_trend(percentiles: np.array, values: np.array) -> dict:
        """Calculate trend statistics"""
        pass
```

### 3. `pattern_classifier.py`
```python
class CorrelationPatternClassifier:
    """Classifies correlation patterns across percentiles"""
    
    def classify_pattern(self, feature_stats: pd.DataFrame) -> str:
        """Classify the correlation pattern"""
        pass
        
    def analyze_all_patterns(self, stats_df: pd.DataFrame) -> Dict:
        """Analyze patterns for all features"""
        pass
```

### 4. `quality_scorer.py`
```python
class CorrelationQualityScorer:
    """Calculates quality scores and assigns tiers"""
    
    def calculate_quality_score(self, feature_pattern: dict) -> dict:
        """Calculate multi-component quality score"""
        pass
        
    def assign_quality_tiers(self, quality_scores: dict) -> tuple:
        """Assign features to quality tiers"""
        pass
```

### 5. `report_generator.py`
```python
class CorrelationReportGenerator:
    """Generates reports and visualizations"""
    
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        
    def generate_summary(self, analysis_results: dict) -> dict:
        """Generate summary report"""
        pass
        
    def create_visualizations(self, report: dict):
        """Create all visualization plots"""
        pass
        
    def save_report(self, report: dict, format: str = 'json'):
        """Save report in specified format"""
        pass
```

### 6. `correlation_analyzer.py` (Main orchestrator)
```python
class CorrelationAnalyzer:
    """Main analyzer that orchestrates all components"""
    
    def __init__(self, db_path: str):
        self.data_loader = CorrelationDataLoader(db_path)
        self.stats_calculator = CorrelationStatisticsCalculator()
        self.pattern_classifier = CorrelationPatternClassifier()
        self.quality_scorer = CorrelationQualityScorer()
        
    def analyze(self, correlation_type: str = 'all_races'):
        """Run complete analysis pipeline"""
        pass
```

### 7. `config.py`
```python
# Configuration constants
PERCENTILES = [30, 40, 50, 60, 70, 80, 90, 100]
CORRELATION_TYPES = ['all_races', 'same_type', 'stage_one_days']
CHUNK_SIZE = 100000

# Quality score weights
QUALITY_WEIGHTS = {
    'strength': 0.4,
    'stability': 0.3,
    'availability': 0.3
}

# Pattern classification thresholds
PATTERN_THRESHOLDS = {
    'stability_threshold': 0.02,
    'trend_slope_threshold': 0.001,
    'trend_r_threshold': 0.7
}
```

## Next Steps

1. **Run the test suite** to verify each component works with your data
2. **Modularize the code** as outlined above for better maintainability
3. **Profile performance** on the full dataset - the chunked loading should handle large data efficiently
4. **Generate initial reports** for each correlation type to understand your data
5. **Review the output** with the team to validate the patterns make sense

Once this system is working well, we'll integrate it with the N-analysis system to create a unified feature selection framework that considers both statistical behavior and predictive power.

## Key Performance Indicators

The system should:
- Process ~2-3GB of correlation data without memory issues
- Generate complete analysis in under 5 minutes
- Produce reproducible quality scores
- Handle NULL values gracefully (some percentiles may not exist for smaller competitions)
- Output both human-readable reports and machine-readable JSON