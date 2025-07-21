# Investigation Plan: 27 vs 37 Features Discrepancy

## Problem Statement

The correlation analysis system expects 37 race features based on `config.RACE_FEATURES`, but the actual blob data contains correlation matrices with only 27 features. This represents a discrepancy of 10 missing features.

## Current Diagnosis

### Observed Evidence
- **Expected**: 37 features as defined in `correlation_feature_analysis/config.py`
- **Actual**: 27 features in the stored correlation matrices
- **Location**: `blob_data_loader.py:67` expects matrix shape `(8, 37)` but receives `(8, 27)`
- **Impact**: System processes 27 features correctly, but 10 features are silently missing from analysis

### Root Cause Analysis
The discrepancy likely originated during the **correlation matrix creation process** in the `database_embeddings_storage` system, where features were filtered out before storage for one or more of these reasons:

1. **Data Quality Filtering**: Features with insufficient data across riders/races
2. **Correlation Filtering**: Features with extremely high correlation to other features (multicollinearity removal)
3. **Statistical Filtering**: Features with poor correlation reliability or significance
4. **Memory Optimization**: Features deemed less important to reduce storage size

### Code Location Analysis
- **Definition**: `config.RACE_FEATURES` contains the full theoretical feature set
- **Storage**: `rider_correlations_blob` table contains compressed 8×27 matrices
- **Processing**: `blob_data_loader.py` assumes 37 features but actually processes 27

## Investigation Plan

### Phase 1: Identify Missing Features
1. **Extract actual feature list** from correlation matrices
   - Modify `blob_data_loader.py` to capture actual matrix dimensions
   - Compare first 27 features from `config.RACE_FEATURES` with actual stored features
   - Identify which 10 features are missing (likely the last 10 in the list)

2. **Document feature mapping**
   - Create a mapping between `config.RACE_FEATURES` index and actual stored feature index
   - Determine if missing features are at the end or scattered throughout

### Phase 2: Trace Feature Filtering History
1. **Review database_embeddings_storage code**
   - Check `../database_embeddings_storage/` for correlation matrix creation logic
   - Look for feature filtering, selection, or exclusion criteria
   - Review any feature quality analysis or correlation thresholding

2. **Check documentation**
   - Review `../database_embeddings_storage/USER_GUIDE.md` for feature filtering information
   - Check for any configuration files that define which features to include/exclude

### Phase 3: Validate Feature Quality
1. **Analyze missing features**
   - Determine which specific features are missing (e.g., certain percentile gaps, group dynamics metrics)
   - Assess whether these features would add analytical value
   - Check if missing features have known data quality issues

2. **Statistical validation**
   - If original raw data is available, calculate correlation reliability for missing features
   - Compare correlation strength and stability of missing vs included features

### Phase 4: Implement Solution
1. **Short-term fix**
   - Update `config.RACE_FEATURES` to match the actual 27 stored features
   - Ensure all system components use consistent feature lists
   - Update documentation to reflect actual feature set

2. **Long-term options**
   - **Option A**: Recreate correlation matrices with all 37 features (if data quality permits)
   - **Option B**: Formally document feature exclusion criteria and maintain 27-feature set
   - **Option C**: Hybrid approach - keep 27 core features, add select additional features if valuable

## Action Items

### Immediate (Next Session)
- [ ] Modify blob data loader to report actual matrix dimensions
- [ ] Extract and document the 27 actual features
- [ ] Identify which 10 features from `config.RACE_FEATURES` are missing

### Short Term (Within 1-2 Sessions)
- [ ] Review database_embeddings_storage code for feature filtering logic
- [ ] Update `config.RACE_FEATURES` to match reality
- [ ] Update system documentation to reflect true feature count

### Medium Term (Future Development)
- [ ] Assess analytical impact of missing features
- [ ] Decide whether to recreate matrices with additional features
- [ ] Implement feature quality validation pipeline

## Risk Assessment

### Low Risk
- Current system functions correctly with 27 features
- Analysis quality is maintained with available features
- No immediate system failures

### Medium Risk
- Documentation mismatch could confuse future developers
- Some analytical insights may be missing from excluded features
- Feature count assumptions may exist elsewhere in codebase

### Mitigation Strategy
- Document the discrepancy clearly in all relevant files
- Ensure consistent feature counting across all system components
- Maintain flexibility to add features in future versions

## Expected Outcomes

1. **Clear understanding** of which 10 features are missing and why
2. **Consistent documentation** across all system components
3. **Informed decision** on whether to expand feature set or accept current limitations
4. **Robust feature management** for future system development

---

*This investigation plan addresses the 27 vs 37 feature discrepancy while maintaining system functionality and providing a clear path forward for resolution.*