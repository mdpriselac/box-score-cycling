I've made a few changes:

1. In the get_competition_ids function from race_feature_database.py, I updated the min_finishers default to 40 to make sure we're only looking at competitions where at least 40 riders/results are in the set we consider.

2. In the extract_race_features function in race_feature_extraction.py, I changed line 231 so that we only return data when we have at least 10 finishers for a given percentile.

3. In the calculate_skewness function in the statistical_measures.py file, I changed it so that it returns 0 when there's zero variance.

I want the tables to have two few more columns added during the create of race_feature tables: kurtosis_absolute_imputed and kurtosis_normalized_imputed (nullable). We will later on sort out a way to impute kurtosis values once all the race features are calculated. These should all be null for now. This is the main thing I need you to adjust the create_feature_table function in the race_feature_database.py file to add these columns.

So, read through race_feature_database.py file to get started and understand how the system can run to create race_feature_N tables for each percentile N from 5 to 100 in steps of 5 (the functions should be set to this as a default). Then clear out existing race_feature_N tables (I've backed up the database, don't worry). Then give me the all clear to run the script to create the new race_feature tables and we'll get going.