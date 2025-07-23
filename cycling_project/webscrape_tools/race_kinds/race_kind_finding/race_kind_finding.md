# Background

So far we have taken the following steps:

- First, we built a series of features and statistical measures to measure the distribution of finishing times in bike races. 
- Second, we calculated those metrics across a range of finishing percentiles from 10 to 100. So, for example, a race_feautre_10 table contains finishing time distribution metrics when only considering the top 10% of finishers. Race_feature_50 contains finishing time distribution metrics when only considering the top 50% of finishers, etc. Each smaller percentile is a subset of the preceding set so we get an increasingly competitive selection of riders that we're looking at. You can find the structure of these tables in race_feature_N tables in the database where N can take any value between 10 and 100 in steps of 5.
- Third, we've calculated some gradient metrics across those features for each competition: variance, monotonicity, and slope. We've also calculated some quality metrics such as the percentile at which kurtosis becomes null because the variance of finishing times is 0. You can find this data in the race_feature_gradient table.
- Fourth, we've done some analysis to evaluate these different gradients to see how well they will likely be able to support distinguishing races into kinds. Specifically, we're interested in distinguishing stages, except time trials (which we've excluded from this analysis as races less than 90min/5400 seconds), into different kinds. The text report is at race_kinds/stage_kind_support_analysis/stage_separability_report.txt. The data is stored in the same folder at stage_separability_analysis.json. 



# Next Step

Based on the analysis of gradient features, we want to build a system to sort non time trials stage competitions into kinds. We do not have labeled data.

Your task is to help us design a few different ways to do that. Let's think through some options, design some systems, and write some evaluation tasks to see if we can get our system up and running.