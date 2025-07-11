# Rider Embeddings Pipeline - User Guide

## 🚀 Quick Start

### One-Command Full Pipeline
```bash
cd webscrape_tools
uv run python rider_embeddings/full_pipeline_example.py
```
Choose 'S' for sample (500 riders) or 'F' for full dataset.

### Expected Outputs
- **Correlation data**: Parquet files with rider-feature correlations
- **Analysis results**: JSON with feature selection recommendations  
- **Report**: Human-readable analysis with explanations
- **Optimized dataset**: Final correlation data ready for modeling

---

## 📋 Step-by-Step Usage

### Step 1: Generate Correlation Data

#### Quick Sample (for testing)
```python
from rider_embeddings.data_generation import CorrelationDataGenerator

generator = CorrelationDataGenerator("database/database/cycling_races.db")
generator.generate_sample(sample_size=500)
```

#### Full Production Run
```python
generator.generate_all_correlations(
    feature_tables=['race_features_30', 'race_features_40', ..., 'race_features_100'],
    resume=True  # Can resume if interrupted
)
```

**Key Parameters:**
- `sample_size`: Number of riders (500-5000 for testing, None for all)
- `min_races`: Minimum rider history (default: 5, higher = better quality)
- `batch_size`: Memory management (default: 100, lower if memory issues)

### Step 2: Optimize Storage

```python
from rider_embeddings.data_generation import ParquetStorage

storage = ParquetStorage("correlation_data")

# Merge batch files
storage.merge_batches()

# Create partitioned dataset for fast queries
storage.partition_by_percentile()

# Validate data quality
validation = storage.validate_data()
```

### Step 3: Run Feature Selection

```python
from rider_embeddings.data_generation import CorrelationDataLoader
from rider_embeddings.feature_selection import FeatureSelectionPipeline

# Load data
loader = CorrelationDataLoader("correlation_data")
correlation_results = loader.load_for_feature_selection()

# Run analysis
pipeline = FeatureSelectionPipeline()
results = pipeline.analyze_all(correlation_results, max_features=25)

# Generate report
report = pipeline.generate_report(results)
print(report)
```

### Step 4: Export Final Dataset

```python
# Get recommendations
best_percentile = results['recommendations']['summary']['recommended_percentile']
features = results['recommendations']['summary']['recommended_features']

# Export optimized data
optimized_df = loader.load_for_specific_analysis(
    percentile=best_percentile,
    features=features
)
```

---

## ⚙️ Key Adjustable Parameters

### 1. **Correlation Generation Parameters**

#### `min_races` (Default: 5)
**What it does:** Minimum rider history required for correlation calculation

**Tradeoffs:**
- **Higher (8-15):** Better correlation quality, fewer riders
- **Lower (3-5):** More riders included, noisier correlations

**Recommendation:** Use 5-8 for exploratory analysis, 10+ for production

#### `feature_tables` 
**What it does:** Which race_features_N percentiles to analyze

**Options:**
- **All percentiles:** `['race_features_30', ..., 'race_features_100']`
- **Focused range:** `['race_features_70', 'race_features_80', 'race_features_90']`
- **Elite only:** `['race_features_50', 'race_features_60']`

**Tradeoffs:**
- **More percentiles:** Better selection options, longer processing
- **Fewer percentiles:** Faster processing, may miss optimal choice

### 2. **Feature Selection Parameters**

#### `correlation_threshold` (Default: 0.8)
**What it does:** Threshold for considering features redundant

**Tradeoffs:**
- **Higher (0.85-0.9):** Keeps more features, may include redundant ones
- **Lower (0.7-0.75):** More aggressive redundancy removal, may lose useful info

**Recommendation:** 0.75-0.8 for most cases, 0.7 for very high-dimensional data

#### `max_features` (Default: 25)
**What it does:** Maximum features to recommend

**Tradeoffs:**
- **More (30-40):** More information, risk of overfitting
- **Fewer (15-20):** Simpler models, may lose important patterns

**Recommendation:** 20-30 for classification, 15-25 for interpretation

#### `k_range` (Default: [3,4,5,6,7])
**What it does:** Range of cluster numbers to test

**Tradeoffs:**
- **Wider range:** Better optimal k detection, longer processing
- **Focused range:** Faster, may miss optimal clustering

### 3. **Quality vs Speed Tradeoffs**

#### Sample Sizes
| Size | Riders | Processing Time | Quality |
|------|--------|----------------|---------|
| Demo | 500 | 5 minutes | Good for testing |
| Medium | 2000-5000 | 30-60 minutes | Good analysis |
| Full | 10000+ | 2-6 hours | Best results |

#### Memory vs Performance
- **Batch size 50:** Lower memory, slower processing
- **Batch size 200:** Higher memory, faster processing

---

## 🎯 Advanced Customization

### Custom Correlation Methods

Create your own performance-feature linking method:

```python
from rider_embeddings.performance_feature_link.base import PerformanceFeatureLinkBase

class MyCustomMethod(PerformanceFeatureLinkBase):
    def calculate_feature_relationships(self, rider_result_id, lookback_date, feature_tables):
        # Your custom logic here
        return {
            'rider_result_id': rider_result_id,
            'feature_correlations': {...},
            'metadata': {...}
        }
```

### Custom Feature Selection Weights

```python
# Emphasize correlation quality over clustering
correlation_weights = {
    'mean_abs_correlation': 0.5,
    'correlation_variance': 0.3,
    'non_null_rate': 0.2
}

# Emphasize feature discriminative power
feature_weights = {
    'discriminative_power': 0.5,
    'mean_abs_correlation': 0.3,
    'sample_size': 0.2
}

pipeline = FeatureSelectionPipeline()
results = pipeline.analyze_all(
    correlation_results, 
    correlation_weights=correlation_weights,
    feature_weights=feature_weights
)
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. **Memory Issues**
**Symptoms:** Process killed, out of memory errors
**Solutions:**
- Reduce `batch_size` to 50-100
- Use sample mode first
- Process in smaller chunks

#### 2. **No Valid Correlations**
**Symptoms:** Empty feature_correlations, warnings about insufficient data
**Solutions:**
- Lower `min_races` parameter
- Check database for sufficient rider history
- Verify race_features tables exist

#### 3. **Poor Clustering Results**
**Symptoms:** Low silhouette scores, warnings about cluster quality
**Solutions:**
- Increase sample size
- Try different `correlation_threshold`
- Check for sufficient rider diversity

#### 4. **Pipeline Interruption**
**Symptoms:** Process stops mid-generation
**Solutions:**
- Use `resume=True` in generate_all_correlations
- Check checkpoint.json for progress
- Restart from last checkpoint

### Performance Optimization

#### For Large Datasets (10,000+ riders)
```python
# Use aggressive redundancy removal
pipeline = FeatureSelectionPipeline(correlation_threshold=0.7)

# Limit feature tables
feature_tables = ['race_features_70', 'race_features_80', 'race_features_90']

# Use smaller k range
results = pipeline.analyze_all(correlation_results, k_range=[3,4,5])
```

#### For Quick Experimentation
```python
# Small sample with focused analysis
generator.generate_sample(sample_size=200)
loader.load_for_feature_selection(sample_size=150)
```

---

## 📊 Interpreting Results

### Quality Indicators

#### Correlation Quality Metrics
- **Signal Strength > 0.3:** Good rider differentiation
- **Feature Coverage > 70%:** Sufficient data completeness
- **Mean Correlation > 0.15:** Meaningful relationships

#### Clustering Quality Metrics
- **Silhouette Score > 0.5:** Excellent separation
- **Silhouette Score > 0.3:** Good separation
- **Silhouette Score < 0.2:** Poor separation, consider different parameters

### Warning Signs
- **High null correlation rate (>30%):** May need lower `min_races`
- **Very few recommended features (<10):** May need higher `correlation_threshold`
- **Poor clustering across all percentiles:** May need more diverse data

---

## 🔄 Workflow Recommendations

### Development Workflow
1. **Start small:** 500-rider sample with 2-3 percentiles
2. **Validate approach:** Check correlation quality and clustering
3. **Scale up:** 2000-rider sample with all percentiles
4. **Production run:** Full dataset with optimized parameters

### Production Workflow
1. **Generate full dataset:** All riders, all percentiles
2. **Optimize storage:** Partition by percentile, validate data
3. **Run comprehensive analysis:** All methods, detailed reporting
4. **Export final dataset:** Ready for model training

### Experimentation Workflow
1. **Quick samples:** Test different parameters rapidly
2. **A/B comparisons:** Compare different correlation methods
3. **Parameter sweeps:** Test ranges of thresholds and limits
4. **Validation:** Cross-check results with domain knowledge

---

## 📁 File Organization

### Recommended Directory Structure
```
project/
├── correlation_data/           # Generated correlation data
│   ├── demo_sample_correlations.parquet
│   ├── merged_correlations.parquet
│   ├── partitioned/           # Partitioned by percentile
│   ├── feature_selection_results.json
│   └── feature_selection_report.txt
├── optimized_export/          # Final optimized dataset
│   ├── optimized_correlations.parquet
│   ├── optimized_correlations.csv
│   └── export_config.json
└── logs/                      # Processing logs
```

### Key Files
- **`generation_metadata.json`:** Information about correlation generation
- **`feature_selection_results.json`:** Complete analysis results
- **`feature_selection_report.txt`:** Human-readable findings
- **`checkpoint.json`:** Resume information for interrupted runs

---

## 🎓 Best Practices

### Before Starting
1. **Verify database:** Ensure race_features tables exist and contain data
2. **Check disk space:** Full datasets can be several GB
3. **Plan computing time:** Full runs can take hours

### During Processing
1. **Monitor progress:** Check logs for warnings or errors
2. **Validate intermediate results:** Use `validate_data()` regularly
3. **Save checkpoints:** Don't skip the resume functionality

### After Analysis
1. **Review report thoroughly:** Understand why recommendations were made
2. **Validate with domain knowledge:** Do the results make cycling sense?
3. **Document parameters:** Record settings for reproducibility

### For Production Use
1. **Version your data:** Keep track of which analysis produced which results
2. **Test on subsets first:** Validate approach before full processing
3. **Monitor quality metrics:** Track correlation and clustering quality over time

---

## 🚨 Important Notes

### Data Requirements
- **Minimum riders:** 100+ for meaningful analysis
- **Minimum races per rider:** 5+ for reliable correlations  
- **Database integrity:** All referenced tables must exist

### Computational Requirements
- **RAM:** 4-8GB for samples, 16-32GB for full datasets
- **Storage:** 2-5GB for samples, 20-50GB for full datasets
- **Time:** Minutes for samples, hours for full datasets

### Result Validity
- Results are only as good as the underlying race_features data
- Correlation does not imply causation in rider performance
- Consider cycling domain knowledge when interpreting clusters

This pipeline provides a data-driven approach to rider characterization, but human expertise remains essential for validation and interpretation!