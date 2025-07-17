-- Database schema for rider correlation storage system
-- Based on migrating_embedding_system_to_db.md specifications

-- Option A: Denormalized correlation storage (RECOMMENDED)
-- One row per correlation value for fast access
CREATE TABLE IF NOT EXISTS rider_correlations_denorm (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL, -- 'all_races', 'same_type', 'stage_one_days'
    percentile INTEGER NOT NULL, -- 30, 40, 50, 60, 70, 80, 90, 100
    feature_idx INTEGER NOT NULL, -- 0-36
    feature_name TEXT NOT NULL, -- e.g., 'abandon_ratio', 'winning_time'
    correlation_value REAL,
    race_count INTEGER NOT NULL,
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, feature_idx),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- Indexes for fast access patterns
CREATE INDEX IF NOT EXISTS idx_lookup ON rider_correlations_denorm (competition_id, rider_id, correlation_type);
CREATE INDEX IF NOT EXISTS idx_rider_comp_type ON rider_correlations_denorm (rider_id, competition_id, correlation_type);
CREATE INDEX IF NOT EXISTS idx_competition_access ON rider_correlations_denorm (competition_id, correlation_type);
CREATE INDEX IF NOT EXISTS idx_feature_name ON rider_correlations_denorm (feature_name, correlation_type);

-- Data quality tracking table
CREATE TABLE IF NOT EXISTS correlation_data_quality (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    total_races INTEGER NOT NULL,
    races_with_features INTEGER NOT NULL,
    missing_competition_ids TEXT, -- JSON array of missing competition IDs
    percentile_availability TEXT, -- JSON array of 0s and 1s per percentile
    data_completeness REAL NOT NULL, -- races_with_features / total_races
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (rider_result_id, correlation_type),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id)
);

-- Percentile thresholds table (populated during preprocessing)
CREATE TABLE IF NOT EXISTS race_history_thresholds (
    threshold_name TEXT PRIMARY KEY,
    percentile REAL NOT NULL,
    min_races INTEGER NOT NULL,
    total_riders INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backup BLOB storage for analysis/verification
CREATE TABLE IF NOT EXISTS rider_correlations_blob (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    correlation_matrix BLOB NOT NULL, -- Compressed numpy array
    race_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(rider_result_id, correlation_type),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- Processing checkpoint table (simplified - no rider history tracking needed)
CREATE TABLE IF NOT EXISTS processing_checkpoint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    checkpoint_name TEXT NOT NULL,
    last_processed_competition_id INTEGER,
    last_processed_date TEXT,
    total_processed INTEGER,
    total_remaining INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(checkpoint_name)
);

-- Processing log for monitoring
CREATE TABLE IF NOT EXISTS processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_number INTEGER,
    competitions_processed INTEGER,
    riders_processed INTEGER,
    correlations_calculated INTEGER,
    processing_time_seconds REAL,
    memory_usage_mb REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add the combined stage_one_days column if it doesn't exist
-- ALTER TABLE rider_results ADD COLUMN prior_stage_one_days INTEGER DEFAULT 0;