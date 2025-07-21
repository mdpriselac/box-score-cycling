-- Drop script for rider correlation storage system
-- Mirrors create_correlation_tables.sql for clean reset

-- Drop all correlation tables
DROP TABLE IF EXISTS rider_correlations_blob;
DROP TABLE IF EXISTS correlation_data_quality;
DROP TABLE IF EXISTS race_history_thresholds;
DROP TABLE IF EXISTS processing_checkpoint;
DROP TABLE IF EXISTS processing_log;

-- Verify tables are dropped (for manual verification)
-- .tables should not show these tables anymore