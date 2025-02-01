# Engineer Tools

The engineer_tools module so far has two sets of tools for woring with and preparing the data. First, a tool for creating buckets for places. Second, a tool for extracting the characteristics of a race based on the distribution of finishing times. 

## Place Buckets

In the place_handling module there is a the place_bucketer function. It takes in a rider place (as either a string or int) and returns a bucket (as an it). This is a way of label encoding the finishing place of each rider. The buckets are designed to track (roughly) the important break points in the values of points awarded to finishing places by the UCI. Currently the structure is set up as follows:

Finishing Position:Bucket

Winner: 0
Podium: 1
Top 5: 2
Top 10: 3
Top 15: 4
Top 30: 5
Finish outside of top 30: 6
DNF/DNS/OTL: 7

## Race Characteristics

One of the core goals of this project is to see how much information can be extracted about races based on the distribution of finishing times: how spread out? how clumpy? Is it a sprint finish? how long is the race? etc. 

The extract_finishing_time_distributions function takes in a Race or Stage object and extracts a set of data as long as there is finishing time data. The data is returned as a dictionary of dictionaries organized by theme.

First is the max_group_data dictionary. This contains information about how big the biggest group was and how influential it was on the race. The data it contains is:
    - max_group_size: how many riders are in the biggest group size
    - max_group_proportion: how many of the riders that started the race ended in the biggest group.
    - max_group_finish_time_percentile: what is the percentile finishing time to the (if there are ties in the max group size, this takes the fastest finishing group of that size)
    - max_group_position: the finishing place of the rider who finishes first in the biggest group (if there are ties in the max group size, this takes the fastest finishing group of that size)
    - max_group_zscore: what is the finishing time zscore for the biggest group (again, if ties in group size, takes the fastest finishing group of that size)
    - max_group_gap_to_winner: the time gap from the winner to the biggest group 

Second is the group_data dictinoary. This is data about the number, size, and finishing time distributions of groups in the races.
    - group_count: how many groups were there in the race. A group here is just defined as a unique finishing time, so individual riders count as groups for these purposes.
    - avg_group_size: the average group size
    - stdev_group_size: the standard deviation in group sizes
    - avg_group_gap: the average time gap between groups
    - stdev_group_gap: the standard deviation in gaps between groups
    - proportion_grouped: the proportion of riders who do not finish solo (this is the one sense in which groups mean more than one rider)

Third is the distribution_data dictionary. This is zscore information about finishing times. The idea here is to see how finishing times 
    - winner_zscore: winner's finishing time zscore
    - last_zscore: last finishing time zscore
    - 5th_percentile_zscore, 10th_percentile_zscore, 25th, 50th, 75th, 90th, 95th percentile: zscores for the different percentile finishing times. The idea is to get an idea of how different finishign groups spread around the finishing time range.

Fourth is the finish_time_data dictionary. This is about the raw finishing times rather than distributions or the biggest group.
    - avg_gap: rather than look at average gaps between groups this is average individual gaps.
    - stdev_gap: individual stdev gaps
    - winning_time: how long was the race. This is good for identifying time trials and very hard races.
    - gap_to_last: how far back was the last place finisher from the winner
    - finishing_times_filled_proportion: all possible times are defined as each second from winner to last finisher. This statistic is the percentage of possible times that are filled as in they have a rider or riders who finished on that time. This is supposed to give us an estimate of how spread out the finishing was.
    - non_finisher_proportion: how many of the racers DNF/DNS/OTL the race. Gives us an estimate of how hard/grueling the race was.

The Race Characteristics can be used for engineering further metrics about races or directly grouping races together, or directly feeding in to rider performance prediction training and predictions.