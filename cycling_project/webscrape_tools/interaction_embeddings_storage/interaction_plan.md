# Overview
Our database system stores race features and correlations between rider performance.

Our goal for this phase of the project is to calculate the interactions between race features and rider correlations to facilitate more effective machine learning for our LightGBM model.

## Race Features
Race features are stored in race_feature_N tables where N represents the percentage of riders considered and ranges from 30 to 100 in steps of 10. 

We're tracking these 37 race features:

total_finishers, included_finishers, abandon_ratio, winning_time, total_race_duration, variance_absolute and _normalized, std_deviation_absolute and _normalized, skewness_absolute and _normalized, kurtosis_absolute and _normalized, gini_coefficient, shannon_entropy_absolute and _normalized, Nth_percentile_gap from 5 to 50 in steps of 5, total_groups, riders_in_groups, largest_group_size, largest_group_position, avg_group_size, std_group_size, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric.

We do have minimum rider requirements in order to calculate these statistics. As a result not all competitions have race_feature_30 data even if they do have race_feature_100 data because when you look only at the top 30 percent of finishers you will not meet the minimum rider requirements (30 riders).

## Rider Correlations

Correlations between rider performance are stored in a somewhat more sophisticated way. For all of the details on how the correlations are stored and whether correlations and race features are missing because of failed rider minimum counts, you must read the database_embeddings_storage/USER_GUIDE.md file. It is detailed and useful for understanding how the rider correlations are stored along with their data quality. 

In the end we essentially can access two matrices, a race_feature matrix, where each row represents a race_feature_N table for a competition and each column is a feature, and a rider performance race feature correlation matrix where each value in the matrix represents the correlation between rider performance and the race_feature_N x race_feature value.


# Interaction Terms

We want to create three different measures of interaction between rider performance correlations and race features:

- dot product (scalar value)
- cosine/normalized dot product (scalar value)
- hadamard product (elementwise matrix)

We want to create these three interaction features for each race_feature_N table and race_feature_N x rider performance correlation table we have.

The storage system in the database for interaction terms should parallel the correlation storage system.

We want to do two things here. First, we want to design the storage system. Second, we want to design an efficient way to create and store the interaction values. We're running on an Apple M1Pro with 16gb memory to utilize so make sure that we can do things as efficiently as possible. 

In addition to the infrastructure we create for migrating the full interaction data sets, I'd like some infrastructure to create the interaction terms on subsets of race_features/correlation. We'll likely do some fine tuning down the road to figure out optimal feature combinations and we'll want to be able to create tailored interaction feature data.