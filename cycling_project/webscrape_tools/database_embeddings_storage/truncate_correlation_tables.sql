-- Fast truncation script for rider correlation storage system
-- Uses DELETE (equivalent to TRUNCATE in SQLite) which is faster than DROP/CREATE

-- Turn off some safety features for speed
PRAGMA synchronous = OFF;
PRAGMA journal_mode = MEMORY;

-- Clear all data from tables (equivalent to TRUNCATE)
DELETE FROM rider_correlations_denorm;
DELETE FROM rider_correlations_blob;
DELETE FROM correlation_data_quality;
DELETE FROM race_history_thresholds;
DELETE FROM processing_checkpoint;
DELETE FROM processing_log;

-- Reset any auto-increment sequences
DELETE FROM sqlite_sequence WHERE name IN (
    'rider_correlations_blob',
    'processing_checkpoint', 
    'processing_log'
);

-- Turn safety features back on
PRAGMA synchronous = NORMAL;
PRAGMA journal_mode = WAL;

-- Optional: VACUUM to reclaim space (comment out if you want to skip this for speed)
-- VACUUM;