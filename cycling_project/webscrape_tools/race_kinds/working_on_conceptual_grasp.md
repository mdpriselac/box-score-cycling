# Metrics

We have a series of statistics and engineered features that we are using to characterize bike races by the distributions of rider finishing times.

To understand the statistics we're using, see this file: statistical_measures.py

To understand the engineered feautres we've created, see this file: engineered_metrics.py

The docstrings for each engineered metric has a basic description of the idea behind each metric.

# Metrics across finisher subsets

We calculate our finishing time distribution across different subsets of the race finishers. The race_feature_100 table contains the finishing time distribution across all finishers in a competition. The race_feature_90 table contains the finishing time distribution across the top 90% (by place) riders of a competition. Etc. until we get to the race_feature_10 table, which contains the finishing time distribution metrics calculated across only the top 10% of finishers. We have race_feature_N tables for each N from 10 to 100 in steps of 5 for each competition in our database.

What's important to recognize is that all of our finishing time metrics are calculated solely with respect to the group of finishers. For example, suppose we have a 200 rider race. In the race_feature_100 table, the 5th_percentile_gap represents the time gap between the winner and the 10th place rider, the 5th_percentile_gap in the race_feature_50 represents the time gap between the winner and the 5th place finisher, and in the race_feature_20 table, the 5th_percentile_gap represents the gap between the winner and the 2nd place rider.

This same patter applies to all of our metrics. So, the biggest_group_metric in a competition's race_feature_100 table represents the biggest group metric as calculated for the whole race's finishing time distribution whereas the biggest_group_metric in the race_feature_10 table represents the biggest group metric as calculated only when looking at the top 10% of finishers by place.

# Gradients

In addition to calculating the race finishing time distribution metrics across the different percentages of finishers, we have also calculated the gradients for our race features. In particular, we're calculating the slope, volatility, and monotonicity of each each metric in a competition as you move from the race_feature_10 value for that metric to the race_feature_100 value for that metric. For the actual calculation of the gradient metrics see the gradient_calculator.py file in the race_kinds folder.

# A conceptual overview for interpreation

We've put to use our gradients to help us break races into kinds. Each of these kinds is defined as a cluster which has its own distinctive feature importances. What we need from you is a nice, clear, conceptual explanation of how to interpret cluster feature importances. We need these explanations:

For each finishing time distribution metric:
    For each gradient metric:
        - What does the value of the gradient metric tell us? If it's positive? if it's negative? If it's near zero?
        - If this metric is one of a cluster's most important features, what does that tell us about the races in this cluster? If the metric for the cluster is well above the population mean, what does that say about the cluster? If the metric for the cluster is well below the population mean, what doe sthat say about the cluster?

As you answer these questions, don't worry about trying to interpret the kind of race you might think a cluster represents. Instead just try to be a clear as you can and use examples whether from bike racing or not.