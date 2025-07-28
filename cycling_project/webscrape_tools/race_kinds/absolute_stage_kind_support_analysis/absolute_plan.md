# Background

We've created a series of features for bike race competitions based on the finsihing time distributions of riders. We've calculated these features across different subsets of riders based on how well they finished. For example, in race_feature_10 table, we calculate all of the finishing time features for the top 10% of finishers by place. In the race_feature_25 table, we calculate the finsihing time features when considering the distribution across the top 25% of finishers by place. In the race_feature_55 table, we calculate the finishing time features when considering the distribution across the top 55% of finishers by place, etc. 

# Plan

We're trying to build a model for classifying stages into kinds. We've found two important patterns that have proved helpful.

First, we want to ignore time trials for our purposes. These are identifiable by their shorter winning_time of under 90 minutes (the winning_time is in seconds). We're going to ignore those competitions for these purposes.

Second, we've found that there's a lot of value in knowing at which point the kurtosis goes Null because there is no variance for that percentage of finishers. For example, if a competition has a null kurtosis value in its race_feature_35 table, that means that the top 35% of riders all finished together with the same finishing time and there is 0 variance in their finishing time. If there is no kurtosis breakdown in any of the race_feature_N tables, then we can say there is no kurtosis breakdown (and if we need to avoid giving a null value, we can call it 0). 

We've found that the races with a kurtosis breakdown at any point look a lot different from races that don't have any breakdown. As a result, we want to to analyze how well features will support separation into kinds across each of these different groups of stages: kurtosis breakdown and no breakdown

So, our goal is to look at the features in the race_feature_N table and answer these questions:

Which tables (ie which N for race_feature_N) should we look at?

Which features should we look at?

Should we select some features at some N values and other features at other N values? 

We want to find race_feature_N x feature combinations that will best support dividing non time trial stages into kinds for both stages with kurtosis breakdowns (at some point) and stages without any kurtosis breakdown.

# Model

We've already done this project for race_feature_gradients that calculate how these finishing time features change as you include more and more finishers. Our goal here is to look at absolute values. If you look at the race_kinds/stage_kind_support_analysis.py folder, you'll find two particularly useful files. The analyze_stages_no_breakdown.py file and the analyze_stages_with_breakdown.py file. Those will give you an idea of the important human readable and manchine readable reports we want to generate here for absolute values.

# Features

The features we want to use for our purposes here include all the features in the race_feature_N tables except: id, competition_id, percentile_analyzed, extraction_date, competition_name, competition_type, race_id, race-name, race_category, race_year, race_date. Those are more information about races rather than features for predictions.