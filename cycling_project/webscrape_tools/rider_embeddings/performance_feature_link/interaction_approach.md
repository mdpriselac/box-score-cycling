I'd like to set up a new approach to connecting up race features and rider performance.

So far we've focused just on correlating race features to rider performance. We did this in two ways. In one way, we calculated correlations for a rider across all race types. In a second way, we calculated correlations for a rider across only race types of the same race type we're currently examining. For example, if we want to create a data point around a one_day race, we calculate the correlation between rider performance and race features only for all previous one_day races. Etc.

Going forward we will *only* be utilizing the race type approach to correlations. We will look at these race types: gc, stage, one_day, stage_one_day (ie stagse and one days), and all.


For this phase of the project I'd like to add a second layer here to create an interaction based approach to the rider embeddings. I'd like to create this across a few different dimensions of options.

The basic idea is that I want rider embeddings to represent interactions between race features and the correlations between rider performance and race features.

As before we will only be looking at the uci_points_proportional column in a rider_result as the target variable, as the measure of rider performance we're using to calculate correlations with.

So, for any given rider result, we would do the following:
    1. Collect the appropriate race history for the rider by collecting all the previous rider_results. Start by collecting all of the previous rider_results for the rider so we have the materials for creating the all correlation. Using that data set, also create whatever other histories are appropriate given the race type in question (one days if it's a one day, gc if it's a gc, stages if it's a stage, one days and stages if it's a stage_one_day). For each relevant race type you should have a list of rider_results.
    2. Look up the relevant race features for each rider_result by utilizing the competition_id for the rider_result. The competition_id will let you pull the race features from the appropriate race_feature_N tables where represents the proportion of riders used in calculating the race features. N ranges from 30 to 100 in steps of 10. 
    3. For each rider_result in a given race history, for each percentile N, calculate the correlation between that competition's race features at that percentile N (ie that competition_id's entry in the race_feature_N table) and the rider performance.

So far this is the same as we've done so far with the race_type approach to correlations. But I want to add one more step now. The correlations themselves won't be the rider embedding. Instead we're going to precompute a rider interaction between the race features and the rider's correlations. I want to try a few different ways to do this:

Phase 1: Individual Percentiles
- First, for each percentile, N, calculate the dot product of the race_features_N for that competition and the correlation between the race_feature_N and rider performance.
- Second, for each percentile, N, calculate the Hadamard product (elementwise) of the race_features_N for that competition and the correlation between the race_features_N and rider performance.
- Third, for each percentile, N, calculate that cosine similarity/normalized dot product betwen the race_features_N for that competition and the correlation between the race_features_N and rider performance.

Phase 2: All Percentiles
In the next alternative approach, I dont' want to look at individual race_feature_N percentile tables and their correlations with rider performance. Instead, I want to look at all race_feature_N tables considered as a matrix where each percentile is considered as a row vector and then each feature could be considered as a column vector.  Then I want to create a corresponding matrix of correlations with rider performance by combining together all of the the correlations between rider performance and each race_feature_N feature set.

Oce we have these two matrices, I would like to calculate the same statistics: dot product, hadmard product, and cosine similarity/normalized dot product.

As you work through this ,make sure you check out the extract_full_embeddigns_optimized.py to see all of the optimizations that have gone into creating the correlations between rider performance and race features. See if you can build on those materials to create these interaction metrics that we will then add to our race prediction methods later.  Read back through any of the dependencies to get a clear understanding of the designs so far. 
