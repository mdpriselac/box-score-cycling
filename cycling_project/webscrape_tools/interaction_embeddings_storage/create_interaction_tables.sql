-- Create tables for storing interaction terms between race features and rider correlations

-- Drop existing tables if they exist (for clean setup)
DROP TABLE IF EXISTS rider_interactions_scalar;
DROP TABLE IF EXISTS rider_interactions_hadamard;
DROP TABLE IF EXISTS interaction_processing_status;
DROP TABLE IF EXISTS interaction_experiments;
DROP TABLE IF EXISTS interaction_processing_checkpoint;
DROP TABLE IF EXISTS interaction_processing_log;

-- Table for scalar interactions (dot product and cosine similarity)
CREATE TABLE rider_interactions_scalar (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,  -- 'all_races', 'same_type', 'stage_one_days'
    percentile INTEGER NOT NULL,     -- 30, 40, 50, 60, 70, 80, 90, 100
    interaction_type TEXT NOT NULL,  -- 'dot_product', 'cosine_similarity'
    interaction_value REAL,          -- NULL if percentile unavailable
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, interaction_type),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- Table for Hadamard product (element-wise interactions)
CREATE TABLE rider_interactions_hadamard (
    rider_result_id INTEGER NOT NULL,
    competition_id INTEGER NOT NULL,
    rider_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentile INTEGER NOT NULL,
    feature_idx INTEGER NOT NULL,     -- 0-36
    feature_name TEXT NOT NULL,
    interaction_value REAL,           -- NULL if percentile unavailable
    
    PRIMARY KEY (rider_result_id, correlation_type, percentile, feature_idx),
    FOREIGN KEY (rider_result_id) REFERENCES rider_results(id),
    FOREIGN KEY (competition_id) REFERENCES competitions(id),
    FOREIGN KEY (rider_id) REFERENCES riders(id)
);

-- Table for tracking processing status
CREATE TABLE interaction_processing_status (
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentiles_processed TEXT NOT NULL,  -- JSON array [1,1,0,0,0,0,0,0]
    scalar_computed BOOLEAN DEFAULT 0,
    hadamard_computed BOOLEAN DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (rider_result_id, correlation_type)
);

-- Table for experimental subset calculations
CREATE TABLE interaction_experiments (
    experiment_id TEXT NOT NULL,
    rider_result_id INTEGER NOT NULL,
    correlation_type TEXT NOT NULL,
    percentile INTEGER NOT NULL,
    feature_subset TEXT NOT NULL,      -- JSON array of feature indices
    interaction_type TEXT NOT NULL,
    interaction_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (experiment_id, rider_result_id, correlation_type, percentile, interaction_type)
);

-- Processing checkpoint for resume capability
CREATE TABLE interaction_processing_checkpoint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_competition_id INTEGER NOT NULL,
    last_rider_result_id INTEGER NOT NULL,
    competitions_processed INTEGER NOT NULL,
    rider_results_processed INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing log for monitoring
CREATE TABLE interaction_processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_level TEXT NOT NULL,
    message TEXT NOT NULL,
    competition_id INTEGER,
    rider_result_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance

-- Scalar interactions indexes
CREATE INDEX idx_scalar_lookup ON rider_interactions_scalar(competition_id, rider_id, correlation_type);
CREATE INDEX idx_scalar_rider ON rider_interactions_scalar(rider_id, competition_id);
CREATE INDEX idx_scalar_interaction_type ON rider_interactions_scalar(interaction_type, correlation_type);

-- Hadamard interactions indexes
CREATE INDEX idx_hadamard_lookup ON rider_interactions_hadamard(competition_id, rider_id, correlation_type);
CREATE INDEX idx_hadamard_feature ON rider_interactions_hadamard(feature_name, correlation_type);
CREATE INDEX idx_hadamard_rider ON rider_interactions_hadamard(rider_id, competition_id);
CREATE INDEX idx_hadamard_percentile ON rider_interactions_hadamard(percentile, correlation_type);

-- Processing status indexes
CREATE INDEX idx_proc_status ON interaction_processing_status(scalar_computed, hadamard_computed);
CREATE INDEX idx_proc_status_type ON interaction_processing_status(correlation_type);

-- Experiment indexes
CREATE INDEX idx_experiment_id ON interaction_experiments(experiment_id);
CREATE INDEX idx_experiment_rider ON interaction_experiments(rider_result_id, experiment_id);

-- Log indexes
CREATE INDEX idx_log_level ON interaction_processing_log(log_level);
CREATE INDEX idx_log_competition ON interaction_processing_log(competition_id);
CREATE INDEX idx_log_created ON interaction_processing_log(created_at);