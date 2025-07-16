We're going to add the ability to train and predict models that use interaction features from our data set. To do that we want to add some optional choices to our training pipeline.

# Feature Sets

We want to be able to choose to include or ignore four different feature sets when training our model. Each data point in our training comes from a rider_result entry. That entry has some basic data and then some links to other tables, like competition, that give us some basic data. The target that we're predicting for each rider_result is the uci_points_proportioanl value.


## Rider Database Features

From the rider_result table we can collect some basic rider information. Here is the list that we want (13 features):
- rider_age, prior_wt_points_proportional, prior_pro_points_proportional, prior_d1_points_proportional, prior_gc_points_proportional, prior_stage_points_proportional, prior_one_day_points_proportional, prior_wt_races, prior_pro_races, prior_d1_races, prior_gc_races, prior_stage_races, prior_one_day_races

The existing model system in the rider_embeddings/embedding_performance_prediction is already designed to use these. Make sure to check for any existing pieces here that can be imported or reused.

## Race Database Features

Each rider_result is connected by its competition_id to a competition. the competition is linked to a race object in the races table. The races table contains a category value. That's the tour level. We want to label encode this information: wt is the highest level tour, pro is the medium level tour, d1 is the lowest level tour. This is the only feature we want at this time that is a basic race database feature.
- The existing model system in the rider_embeddings/embedding_performance_prediction is already designed to use these. Make sure to check for any existing pieces here that can be imported or reused.

## Race Features

In addition to the basic race database features, we also have statistical and engineered race features. These are calculated and stored across a range of proportions of riders. This data is stored in tables named race_feature_N where N is the the proportion of riders considered. It ranges from 30 to 100 in steps of 10. race_featuers_40, for example, contains the race features data as calculated when considering only the top 40% of riders in the race. Rider embedding data is *also* calculated relative to these race featuers as it's calculated as a correlation between rider performance and race_features at a given percentile/proportion. 

There are around 35 features in this cateogry:
- total_finishers, included_finishers, abandon_ratio, winning_time, total_race_duration, variance_absolute and _normalized, std_deviation_absolute and _normalized, kurtosis_absolute and _normalized, gini_coefficient, shannon_entropy_absolute and _normalized, Nth_percentile_gap where N ranges from 5 to 50 in steps of 5, total_groups, riders_in_groups, proportion_in_groups, largest_group_position, avg_group_size, std_group_size, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric.

The existing model system in the rider_embeddings/embedding_performance_prediction is already designed to use these. Make sure to check for any existing pieces here that can be imported or reused.


## Rider Embedding Data

We have created two forms of rider embedding data that we want to choose from. One option is just the full feature embedding data. These embeddings are the same shape as the full race_feature data as they are simply the correlation of rider performance with each race feature. To use this data, the current system requires teh user to choose which race_feature_N table to use for race_feature and rider_embeddings. 

The second option is the optimized feature selection set of features. These will be a much smaller subset of features that have been selected through a pipeline that considers, for each percentile race_feature table, which has the highest quality correlation data, and then from among all of the percentiles which best supports rider clustering. Each race_type will have a different size of features and rider embeddings here and each will use a predetermined race_feature_N table for race features and rider embeddings.

The existing model system in the rider_embeddings/embedding_performance_prediction is already designed to use these. Make sure to check for any existing pieces here that can be imported or reused.

## Rider-Race Interaction Data

This is the new data that we want to add in. Read the rider_embeddings/interaction_data_access_instructions.md file to undertand how that data is stored and made accessible.

We have a few different types of interaction data. For each rider_result we have an interaction metric or vector that is the: dot product of race and rider features (a single scalar), the cosine similarity products of those race and rider features (a single scalar), and the hadamard_products of the race and rider features (a vector that represents an elementwise comparison of race and rider feature vectors).

To use those data points we will need to specify a race_feature_N percentile to use.

We also have a special version of these where we consider the race features across all percentiles together in comparison to the correlations with rider performance with each of those race_feature x percentile values. Let's call this the all option.

# Design Requirements

## Model Requirements
Our goal for this system is to be able to pick and choose what data sets to train a model with. 
    - rider database 
    - race database 
    - race features
    - rider embedding features
        - either full (in which case we need a percentile) or optimized
    - interaction features
        - which (or which combination) of 3 interaction metrics
        - which percentile (or all) to consider

By default the settings should be to use the rider database, race database and all of the interaction features, with a setting to use just one of the percentile tables for the interaction features (70) instead of the all

## Where to work

Create an embed_interaction_model.py file that adapts the work done in embedding_model.py to the current design requirements.