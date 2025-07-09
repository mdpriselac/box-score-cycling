🎯 Key Hyperparameters to Adjust

1. Core Training Parameters (in test_backtest_2011.py)

# Conservative approach
num_boost_round=100,          # Fewer rounds = less overfitting
early_stopping_rounds=10,     # Stop early = less overfitting

# Aggressive approach  
num_boost_round=500,          # More rounds = more learning
early_stopping_rounds=50,     # Allow more rounds before stopping

2. Classification Stage Parameters (lines 66-82)

# Current (balanced)
'num_leaves': 31,             # Tree complexity
'learning_rate': 0.05,        # Learning speed
'feature_fraction': 0.9,      # Feature sampling
'bagging_fraction': 0.8,      # Sample sampling
'min_data_in_leaf': 20,       # Minimum samples per leaf

# CONSERVATIVE (less overfitting)
'num_leaves': 15,             # Simpler trees
'learning_rate': 0.03,        # Slower learning
'feature_fraction': 0.8,      # Less feature sampling
'bagging_fraction': 0.7,      # Less sample sampling  
'min_data_in_leaf': 50,       # More samples per leaf
'max_depth': 5,               # Limit tree depth

# AGGRESSIVE (more learning capacity)
'num_leaves': 63,             # More complex trees
'learning_rate': 0.1,         # Faster learning
'feature_fraction': 0.95,     # More feature sampling
'bagging_fraction': 0.9,      # More sample sampling
'min_data_in_leaf': 10,       # Fewer samples per leaf
'max_depth': -1,              # No depth limit

3. Regression Stage Parameters (lines 84-101)

# Current (balanced)
'num_leaves': 63,
'learning_rate': 0.05,
'reg_alpha': 0.1,             # L1 regularization
'reg_lambda': 0.1,            # L2 regularization
'min_data_in_leaf': 10,

# CONSERVATIVE (prevent overfitting)
'num_leaves': 31,
'learning_rate': 0.03,
'reg_alpha': 0.3,             # Stronger L1 regularization
'reg_lambda': 0.3,            # Stronger L2 regularization
'min_data_in_leaf': 30,
'max_depth': 6,

# AGGRESSIVE (more learning capacity)
'num_leaves': 127,
'learning_rate': 0.1,
'reg_alpha': 0.01,            # Weaker regularization
'reg_lambda': 0.01,           # Weaker regularization
'min_data_in_leaf': 5,
'max_depth': -1,

🔧 How to Implement This

Option 1: Modify test_backtest_2011.py

Create different parameter configurations:

# Conservative configuration
results_conservative = backtester.run_temporal_backtest(
    test_year=2019,
    min_results=125,
    target_variable='uci_points_actual',
    num_boost_round=100,        # Less training
    early_stopping_rounds=10,   # Early stopping
    save_models=True,
    verbose=True,
    use_optimized_generator=True
)

# Aggressive configuration  
results_aggressive = backtester.run_temporal_backtest(
    test_year=2019,
    min_results=125,
    target_variable='uci_points_actual',
    num_boost_round=500,        # More training
    early_stopping_rounds=50,   # Allow more rounds
    save_models=True,
    verbose=True,
    use_optimized_generator=True
)

Option 2: Create Parameter Presets in RiderPerformanceModel

Add these methods to the RiderPerformanceModel class:

def set_conservative_params(self):
    """Set conservative parameters to prevent overfitting."""
    self.classifier_params.update({
        'num_leaves': 15,
        'learning_rate': 0.03,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.7,
        'min_data_in_leaf': 50,
        'max_depth': 5,
        'reg_alpha': 0.2,
        'reg_lambda': 0.2
    })

    self.regressor_params.update({
        'num_leaves': 31,
        'learning_rate': 0.03,
        'reg_alpha': 0.3,
        'reg_lambda': 0.3,
        'min_data_in_leaf': 30,
        'max_depth': 6
    })

def set_aggressive_params(self):
    """Set aggressive parameters for maximum learning capacity."""
    self.classifier_params.update({
        'num_leaves': 63,
        'learning_rate': 0.1,
        'feature_fraction': 0.95,
        'bagging_fraction': 0.9,
        'min_data_in_leaf': 10,
        'max_depth': -1,
        'reg_alpha': 0.05,
        'reg_lambda': 0.05
    })

    self.regressor_params.update({
        'num_leaves': 127,
        'learning_rate': 0.1,
        'reg_alpha': 0.01,
        'reg_lambda': 0.01,
        'min_data_in_leaf': 5,
        'max_depth': -1
    })

Option 3: Parameter Sweep Testing

Create a script that tests different parameter combinations:

param_configs = {
    'conservative': {
        'num_boost_round': 100,
        'early_stopping_rounds': 10,
        'model_params': 'conservative'
    },
    'balanced': {
        'num_boost_round': 200,
        'early_stopping_rounds': 20,
        'model_params': 'default'
    },
    'aggressive': {
        'num_boost_round': 500,
        'early_stopping_rounds': 50,
        'model_params': 'aggressive'
    }
}

for config_name, config in param_configs.items():
    print(f"\n{'='*60}")
    print(f"TESTING {config_name.upper()} CONFIGURATION")
    print(f"{'='*60}")

    results = backtester.run_temporal_backtest(
        test_year=2019,
        min_results=125,
        target_variable='uci_points_actual',
        **config
    )

📊 Expected Trade-offs

Conservative Settings

- Pros: More stable, less overfitting, generalizes better
- Cons: May underfit complex patterns, lower peak performance
- Best for: Initial development, when you have limited data

Aggressive Settings

- Pros: Can learn complex patterns, higher peak performance potential
- Cons: More prone to overfitting, may not generalize well
- Best for: When you have lots of data (500K+ pairs), final tuning

🎯 My Recommendation

Start with Conservative parameters for your 2019-2024 backtesting to establish a baseline, then gradually move to Aggressive as you increase data volume. This will help you understand
the impact of both data size and model complexity on performance.

Would you like me to help you implement any of these approaches?
