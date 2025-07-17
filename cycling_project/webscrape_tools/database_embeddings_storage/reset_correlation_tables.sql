-- Fastest reset: Drop and recreate tables
-- This is often faster than DELETE for very large tables

-- Drop everything
DROP INDEX IF EXISTS idx_lookup;
DROP INDEX IF EXISTS idx_rider_comp_type;
DROP INDEX IF EXISTS idx_competition_access;
DROP INDEX IF EXISTS idx_feature_name;

DROP TABLE IF EXISTS rider_correlations_denorm;
DROP TABLE IF EXISTS rider_correlations_blob;
DROP TABLE IF EXISTS correlation_data_quality;
DROP TABLE IF EXISTS race_history_thresholds;
DROP TABLE IF EXISTS processing_checkpoint;
DROP TABLE IF EXISTS processing_log;

-- Recreate from the original script
-- (You can run create_correlation_tables.sql after this)