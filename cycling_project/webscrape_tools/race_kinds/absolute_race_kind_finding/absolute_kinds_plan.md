# Background

We've created a series of features for bike race competitions based on the finsihing time distributions of riders. We've calculated these features across different subsets of riders based on how well they finished. For example, in race_feature_10 table, we calculate all of the finishing time features for the top 10% of finishers by place. In the race_feature_25 table, we calculate the finsihing time features when considering the distribution across the top 25% of finishers by place. In the race_feature_55 table, we calculate the finishing time features when considering the distribution across the top 55% of finishers by place, etc. 

Our goal here is to desisng a race kind sorting plan. We've already done the research on which features are likely to support good kind separation in the race_kinds/aboluste_stage_kind_support_analysis folder. Check out the README.md in that file to understand how to use the data we have created there to guide the race kind finding system we're going to create here.

# Plan

We're trying to build a model for classifying stages into kinds. We've found two important patterns that have proved helpful.

First, we want to ignore time trials for our purposes. These are identifiable by their shorter winning_time of under 90 minutes (the winning_time is in seconds). We're going to ignore those competitions for these purposes.

Second, we've found that there's a lot of value in knowing at which point the kurtosis goes Null because there is no variance for that percentage of finishers. For example, if a competition has a null kurtosis value in its race_feature_35 table, that means that the top 35% of riders all finished together with the same finishing time and there is 0 variance in their finishing time. If there is no kurtosis breakdown in any of the race_feature_N tables, then we can say there is no kurtosis breakdown (and if we need to avoid giving a null value, we can call it 0). 

We've found that the races with a kurtosis breakdown at any point look a lot different from races that don't have any breakdown. As a result, we want to to analyze how well features will support separation into kinds across each of these different groups of stages: kurtosis breakdown and no breakdown

So, our goal is to look at the features in the race_feature_N table and answer these questions:

Which tables (ie which N for race_feature_N) should we look at?

Which features should we look at?

Should we select some features at some N values and other features at other N values? 

These questions have been answered in the absolute_stage_kind_support_analysis folder. Again, check the README there for how to use that data. The find_kurtosis_breakdown_point.py file will be useful for filtering kurtosis breakdown and no breakdown races from one another.

# Model

We've already done this project for race_feature_gradients that calculate how these finishing time features change as you include more and more finishers. Our goal here is to look at absolute values. If you look at the race_kinds/race_kind_finding folder, you'll find the following particularly useful files: 

First, the clustering_no_breakdown.py folder performs clustering for races with no kurtosis breakdown based on their gradient metrics. The clusering_with_breakdown.py folder performs clustering for races with kurtosis breakdown.

Second, the evaluate_no_breakdown_clustering.py file performs analysis and reporting on the clustinering done for races with no kurtosis breakdown. The evaluate_with_breakdown.py file performs analysis and reporting on teh clustering done for races with kurtosis breakdown.

Have a look at those and design a similar system with similar reporting for the absolute metrics. 

# Features

The features we want to use for our purposes here include all the features in the race_feature_N tables except: id, competition_id, percentile_analyzed, extraction_date, competition_name, competition_type, race_id, race-name, race_category, race_year, race_date. Those are more information about races rather than features for predictions.

Remember as you design the sql database code that columns that start with a number need to be quoted.

# Pruning and Combining

In earlier iterations of this project one of the consistent things we saw was that feature selection ended up picking the same stat, both normalized and absolute, across all the different inclusion percentages.

I'd like to carry out this kind finding project in the following stages:

- First, I'd liike to focus on each inclusion percentage. Within each inclusion percentage we want to come up with a set of features. The rules for selecting features are as follows: first, start with the highest rated feature from the absolute_stage_kind_support_analysis reports; second, for any stat that has both normalized and absolute, only include one of them, the higher performer; third, get rid of all other features that are correlated with an already included feature at over 90%.

- Second, Now that we have our features, we want to create the kinds for that inclusion percentage based on those features. For each kind we want the feature importances and also which competitions are included in which kinds. When we're running our kind finding algoriths, we want to have our K means clustering algorithm consider 3-8 cluster counts. Let's also get evaluation metrics for each cluster count.

- Third, we now have comprehensive data on kind creation across all our inclusion percentages. For each inclusion percentage we now have: a list of the features used for kind creation, at least k-means based clusters for a range of 3-8 clusters, the competition membership for each cluster, the feature importance for each cluster, the evaluation metrics for each cluster collection. Let's do an initial bit of reporting at this point:
    - what are the features, if any, that appear in all inclusion percentages?
    - For each inclusion percentage, what is the best cluster count by the evaluation metrics? how many other cluster counts are within 10% performance by evaluation metrics of the top cluster count?
    - For each cluster count let's get a comparison between how similar the clusters are across the inclusion percentages when measured by the feature importances for each cluster. To do that we'll probably want a single 'cluster embedding' for all clusters that simply has all features on it as positions and their feature importance as the value. So each cluster for each inclusion percentage will have a a cluster embedding. From there we need to see how well the clusters match for each inclusion percentage. To do that we need to find, we need to correlate clusters. So, for example, if we're looking at the 3 cluster count, we need to have each inclusion cluster be assigned to master-cluster 0, master-cluster 1, or master-cluster 2. Each cluster must be put into one of the master-cluster and no cluster can bet put into more than one master-cluster. We don't need to worry about implementing this yet beyond creating the cluster embeddings for each cluster size and inclusion percentage. Once we have this data we can worry about developing and implementing a master-cluster assigning approach.