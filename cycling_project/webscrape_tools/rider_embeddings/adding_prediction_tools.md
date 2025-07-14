# Overview

So far we have created embeddings and stored their data.

Next we want to see how well embeddings help a predictive model perform.

# Background Information

For background information on the shape of the project so far, read rider_embeddings/rider_embeddings_overview.md

For information on how the rider embedding system works, check out the rider_embeddings/README.md and rider_embeddings/USER_GUIDE.md

Finally, to understand the shape and location of the data that we've produced through this system, check out the rider_embeddings/rider_embedding_data_usage.md file.

Note that we have created different rider embeddings for each race type: gc, stage, one_day, stage_one_day, and all. Each embedding is tied to a rider_result from the db. That means we need to create a different prediction model fore each 

We're going to build models in the same fashion as we have done before. For the basic structure for how our models should be built, check out rider_performance/rider_performance_model.py and rider_performance_model.md

# Model Inputs

To create inputs to our model we need combine the rider embedding data that we've created with the information that's already stored in our database. The rider embedding data that we've created pairs rider embeddings with rider_results.

For our data to train and test on, we want to go through each rider result and do collect the following inputs:

1. Rider embedding data
2. rider_result data, except: place, time_gap, bib_number (and other more metadata type entries like created_at, id, competition_id, rider_id, team_id), and any of the historical data from columns that end with _actual
3. The tour level, taken from the competition table for this competition. This data should be label encoded with the lowest level being d1, the middle level being pro, and the highest level beting wt.

We only want to train a given race_type model on races of its same type. However, we'll include all the rider_result derived historical data for other race_types in the input features. That is, for example, when training the one_day model, we'll include the prior_gc_points_proportional and prior_stage_races (as well as the stage and stage_one_day columns) in addition to the prior_one_day_points_proportional and prior_one_day_races.

The target that we're trying to predict and learn from is uci_points_proportional

# Model Training and Testing

We want to be able to sort training and test data by year so that we can train on prior data and test on later data. For example, I want to be able to pass the training script a year and an optional race type (if no race type is passed, we'll train all race type models) and have the following behavior happen:

1. We train the model on all data from before the specified year
2. We test the model on all data from the specified year
3. We generate a report that gives a full report for each race_type:
    - how many rider_results were in the training set
    - how many competitions were in the training set
    - how many rider_results were in the test set
    - how many competitions were in the test set
    - For each race_type model trained, give the full feature importance results for all features. Do not truncate this in the reporting.

Create all of this model training infrastructure within the rider_embedding folder as the embedding_performance_prediction folder