# Overview

Create a rider embedding/kind sorting system based on rider performance measured against various race characteristics.

# Measuring Rider Performance

To measure rider performance we want to look at their place and convert that to a point value that rewards the relative difficulty of finishing higher and higher up in the results of the race. 

The tools for converting a finishing place to a point value can be found at database/uci_points.py. There are two functions in there for rewarding points. We're going to use the proportional points function instead of the actual uci systems. The reason for doing this that I've found the uci points has too much of a zero inflation problem when we get to training models and distinguishing riders because for too many races it doesn't distribute points far enough down the finishing list.

Rider results for each competition are stored in the rider_results table. Within each result we have stored historical performance and competition data for that rider up to that point in time. 

The proportional points earned by the rider in the race are available in the uci_points_proportional column.

The historical data for the rider up to that competition are as follows (column: description)
- rider_age: the rider's age (in years) at the time of the competition
- prior_wt_points_proportional: the prior proportional points earned in wt (world tour race level) races
- prior_pro_points_proportional: the prior proportional points earned in pro (pro tour race level) races
- prior_d1_points_proportional: the prior proportional points earned in d1 (division 1 continental race level) races
- prior_gc_points_proportional: the prior proportional points earned in GC (general classification for stage races) type races
- prior_stage_points_proportional: the prior proportional points earned in stages (individual stages during stage races) type races
- prior_one_day_points_proportional: the prior proportional points earned in one day type races
- prior_wt_races: the count of wt races the rider has participated in so far
- prior_pro_races: the count of pro races the rider has participated in so far
- prior_d1_races: the count of d1 races the rider has participated in so far
- prior_gc_races: the count of gc races the rider has participated in so far
- prior_stage_races: the count of gc races the rider has participated in so far
- prior_one_day_races: the count of gc races the rider has participated in so far
- total_prior_races: the total competitions the rider has participated in
- total_prior_points_proportional: the total points earned by the rider  


# Competition Characteristics

Competition characteristics are determined by the distribution of finishing times. We've also looked at how these distributions look when considering different proportions of finishers across a given competition. To be more specific, we've calculated competition characteristics for each competition when we consider only the top 30 percent, 40 percent, 50 percent, 60 percent, 70 percent, 80 percent, 90 percent of all finishers, as well as the full race results. We've done this because 

Race characteristics are stored in the race_features_N tables, where N represents the proportion of riders that are considered. 

We're going to want to look across all of these race_features tables to see if there are any percentiles that have more useful data for distinguishing riders into groups by their strengths compared to others.

# Rider History and Rider Embeddings

Each rider_result entry has basic performance and participation data that we can use as part of our rider embeddings. That does not need any computation or design yet.

We want to figure out a way here to create rider performance data that is measured against race characteristics so that for each rider result we have a picture of how well the rider up to a given competition has performed relative to race characteristics. 

So, for each rider_result, we want to look back at the rider's history at all prior races.
For each prior race, we want to look at all of the race_features across each proportion of finisheres examined.
For each race_features_N, we want to measure the rider's performance relative to each of the race features.
The result should be a collection of rider_relative_race_feature_N data sets. Once we have a nice collection of those, we can then see which N has a set of features that is the most useful for distinguishing riders into clear, intelligible kinds. The feature selection phase for that should be empirically determined by how the features look.

Once we have a clear picture here we can combine the results with the rider_result derived history for a complete rider result embedding. We can then look into training a global model against these rider result embeddings.

# Key Questions

1. How can we measure rider performance relative to each feature?
2. Should we be scaling feature data before doing rider performance relative to features? or is that pointless/unncessary?
3. Should we be scaling feature data or rider performance relative to feature data when doing empirical feature selection for kind analysis?

