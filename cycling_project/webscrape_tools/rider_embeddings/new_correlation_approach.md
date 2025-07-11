# Current Feature Correlation System

The current system takes a rider result, it looks at the history of the rider up to that point, collects all of the race features from those races and how they correlate with their results, as measured by proportional points method.

This puts us in position to have a dataset that can be regressed by an ML comparing feature correlations up to a given race with the results of that race.

However, the correlations we're getting are across all race types. We're getting how well a rider's points earned correlate with race features of one days, stages, and (crucially) gc races. GC race feature values are quite a bit different from stage and one day feature values.

# Next version for the Correlation System

Instead of calculating one correlation across all race types, i want to calculate correlations across four race types:

gc
stage
one_day
stage_one_day (ie stage or one day races)

So for each rider result, we should pull the race history for the rider up to that point. Using that race history we should create four sub race histories:
    - gc race history
    - stage race history
    - one_day race history
    - stage and one_day race history

Once you have the full race history and these 4 sub histories, create correlations between race features within his history/sub-history and the points earned. So we shoudl have 5 sets of correlations: gc race correlations, stage race correlations, one_day race correlations, stage_one_day race correlations, and all race correlations.

For figuring out an optimal data set we also need to work through each percentile table.

So, the overall pattern should be something like:

For each rider result, extract rider history up to that date. Each history should have its own minimum race day requirement because there are more stages than one days and more one days than gc races. In general the defaults can be set to something like 35 minimum for all races, 25 minimum for stages, 15 minimum for one_days, 10 minimum for gc.

For each race in the rider history up to that date, collect the requested percentile tables for each race_feature_N table.

Now, for each race type, go through and do all the correlations. 

The result should be a dataset that is organized in this sort of fashion:

each rider result can be paired with a dataset that has

Each race type:
    each percentile_N:
        each feature correlation


For the next phase in the rider_embedding development, we can run the percentile table and feature selection for each race type.

Once we hae our selection done we should have a dataset for each race type that gives us our rider embedding for that race type. From there we can combine the rider embedding with other race information and then train a model that learns to predict points earned from race features + rider embedding + basic race information

