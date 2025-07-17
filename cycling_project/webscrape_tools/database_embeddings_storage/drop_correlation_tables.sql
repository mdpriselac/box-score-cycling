-- Drop script for rider correlation storage system
-- Mirrors create_correlation_tables.sql for clean reset

-- Drop indexes first
DROP INDEX IF EXISTS idx_lookup;
DROP INDEX IF EXISTS idx_rider_comp_type;
DROP INDEX IF EXISTS idx_competition_access;
DROP INDEX IF EXISTS idx_feature_name;

-- Drop all correlation tables
DROP TABLE IF EXISTS rider_correlations_denorm;
DROP TABLE IF EXISTS rider_correlations_blob;
DROP TABLE IF EXISTS correlation_data_quality;
DROP TABLE IF EXISTS race_history_thresholds;
DROP TABLE IF EXISTS processing_checkpoint;
DROP TABLE IF EXISTS processing_log;

-- Verify tables are dropped (for manual verification)
-- .tables should not show these tables anymore