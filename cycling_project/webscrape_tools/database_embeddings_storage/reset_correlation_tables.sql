-- Fastest reset: Drop and recreate tables
-- This is often faster than DELETE for very large tables

-- Drop everything
DROP TABLE IF EXISTS rider_correlations_blob;
DROP TABLE IF EXISTS correlation_data_quality;
DROP TABLE IF EXISTS race_history_thresholds;
DROP TABLE IF EXISTS processing_checkpoint;
DROP TABLE IF EXISTS processing_log;

-- Recreate from the original script
-- (You can run create_correlation_tables.sql after this)