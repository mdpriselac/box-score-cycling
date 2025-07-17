# Goals

Now that we've done some good experimentation, we're going to be focusing on a more permanent way to handle our data. We're going to store the correlation data in our db to make access to it quick and stable. 

For instructions on the system, you must read and follow the instructions at `rider_embeddings/migrating_embedding_system_to_db.md`

# Race Features

The race features we want to use for our correlations from teh race_feature_N tables are the following:

total_finishers, included_finishers, abandon_ratio, winning_time, total_race_duration, variance_absolute and _normalized, std_deviation_absolute and _normalized, skewness_absolute, and _normalized, kurtosis_absolute and _normalized, gini_coefficient, shannon_entropy_absolute and _normalized, Nth_percentile_gap for each percentile from 5 to 50 by steps of 5, total_groups, riders_in_groups, proportion_in_groups, largest_group_size, largest_group_position, avg_group_size, std_group_size, biggest_group_metric, time_gap_evenness_metric, clumpiness_score, selection_metric

Those are the key features, that count may differ from the instructions you find in the  instructions file but these are the latest up to date features to focus on.

# SQL Confirmation and Testing

Before you commit code to a script for accessing a DB, verify it first with direct sqlite3 commands.

Verify any sql commands or table structures for yourself. The instructions were written with some decent but not perfectly accurate understanding of our database structure. Acquire as much information as you need directly through sql commands to work with the db.

# Locations

Save any and all files to a folder, database_embeddings_storage
