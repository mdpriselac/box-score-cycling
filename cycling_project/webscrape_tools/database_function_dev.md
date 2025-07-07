# Background

We have a basic database set up. It contains tables that represent:

- High level race objects. These race objects contain basic information about races like dates and race types. We also use high level race objects to track the same races over time (year to year) as they'll have the same ids

- Competitions. These are types of actual race and are contained by high level race objects. These can be one day races, general classifications for stage races, and stages within stage races. Each competition will have information like date, results, and total time.

- Riders. This has basic information about riders like their name and birthdate.

- Rider Results. There is one rider result entry for each competition. It contains their place (absolute finishing place as well as finishing percentile) and time gap from the winner (absolute, in seconds as well as percentage)

For more information on the structure of the database and how to access it, read the `db_migration_update_1.md`

# Next steps: Developing Data Refining Tools

The big picture aim of the project is to develop an analytics and prediction system for bike races. We have now established the basic database. For the next phase of the project we want to develop a suite of tools for creating race and rider features to develop our analytics models. 

## Race feature development
- minimum 30 finishers to pull a time distribution
- track the total race duration/finish for any given competition
- track the time distributions for any given competition
- track/calculate the abandon ratio, ie the proportion of finishers with a dns/dnf/oot/dsq etc.
- track race/tour level and race type for each competition
- generate race features derived from finish time distributions along the following lines:

- Finishing Time Distribution Features
    - given a proportion to examine (ie if we set the proportion to .5, we're going to calculate the race statistics only on the top 50th percentile performers and better by place, ie 1 to half way down the finishing places; if we set the proportion to .75 we're going to calculate the race statistics only on the top 75th percetile performers and better, ie 1st place to the 75th percentile finisher)
    - Key statistics
        - finishing time statistical measures:
            - variance (normalized and absolute)
            - standard deviations (normalized and absolute)
            - skewness (normalized and absolute)
            -kurtosis (normalized and absolute)
            - gini coefficient
            - shannon entropy (normalized and absolute)
        - Engineered Metrics:
            - biggest_group_metric
            - time_gap_evenness_metric
            - clumpiness_score

## Evaluating Race Features by searching for Race Kinds
- Once we've developed all of our race features, we want to evaluate how good our measures are by seeing how well the resulting characterizations of races allows us to distinguish them into kinds.
- One of the meta variables we'll work with is the percentile of riders to examine.
- A second meta variable we'll work with is exactly which features to include. Which are duplicative of each other? Which afford clear distinctions between groups of races?
- So, across percentiles, starting with at looking at only the top 25th percentile performers and better and moving up to the full race in steps of 5 percentile points, we want to see if we get any percentiles that are particularly effective at pushing groups into kinds.
- Once we have a stable grasp on how to group races into kinds, we'll want to have a clear function that can rate each race with respect to the kinds. We'll want to both have a categorization score (ie we sort each competition into one type of race or another) and we'll also want the scores for how well a given race fits within a kind.


## Rider Data Augmentation
We need a few different tools for creating and collecting rider data.

- given a rider result, generate a uci points earned score
    - see the database/uci_points.py file
    - there are two options for generating poitns: the actual uci schedule, or a schedule that assigns points to deeper places for lower level races as a proportion of the top level scoring system. E.g. a d1 race gives points all the way to 60th place on this system (instead of only 15) but the point value assigned to positions is some fixed percentage of the points assigned in higher level races, e.g. 5% of a Tour de France finish in that place.
- generating rider history given a date to get prior history up to that date of rider results
    - even better if we can generate back N time units (ie previous 3 months, previous year, previous 2 years, etc).
    - We can use this to train rider specific models 
    or generic rider models.
- Once we have the race feature development feature ready, create a rider performance profile based on performance in races of a given feature set
    - could be interesting to see if we landed on some generic rider type profiles. ie some grouping in the rider models for cases when you have a sufficient sample size.
    - let's not create this quite yet.

# Order of Work

1. Let's start with developing the race feature creation infrastruction. 
    - We have successfully created this aspect of the project. Using the build_percentile_tables.py file, which draws on classes and functions from files in the database directory, we have created a series of race feature tables in the database across several different rider performance percentiles (30, 40, 50, 60, 70, 80, 90, full race). The tables are named 'race_feature_N' where N is the percentile. So the race feature table races that include all riders is race_features_100, the race feautre table for races that include up to the 70th percentile finishing position is called race_features_70. 
2. Once we can test and reliably generate race features across races, we'll start looking at developing race kinds.
    - This phase of the project is essentially complete. By utilizing the database/rice_kinds/find_race_kinds.py script we can perform automatic feature selection from the race feature database, feed the features into a race kind analysis system, and then select an optimal percentile + clustering algorithm for our race kinds.
    - Now that we know we can find good clusters, we need two next steps to prepare for rider data:
        - First, we need to know the features that are being used to support the good clustering. These will be race characterstics that can be used as prediction inputs for rider performance when using UCI points as the dependent variable.
        - Second, we need to get the model out of the clustering algorithm. This will allow us to create both categorical data for each race (ie which cluster it belongs to) and also more fine grained cluster score data (ie something like the probability that a given race with its characteristics belongs to each of the given clusters)
3. Once we have a clear picture of race kinds, we can start working on the rider data.
    - Several targets for rider analyses:
        - rider models should be developed against predicted UCI points (both versions to see which fares better)
        - potential inputs:
            - career uci earnings
            - total races by level
            - normalized races by level (ie proportion of races at each level)
            - age
            - race features
            - race cluster
            - race cluster scores
        - We could try to cluster riders 
            - by uci earnings
            - by uci earnings/race
            - by their strenghts and weaknesses/scaling with race clusters
            - by their strengths and weakness/scaling with race features
4. Once we have an account of riders, we can add strength of field (or even a more fine grained, do we have a lot of climbers, or a lot of strong sprinter specialists, etc.) in a race to factor that into predictions.
5. Our overall prediction model should take in rider characteristics, race characteristics (including this field strength stuff) and a yield rider level predictions. Then we can see from there if we can spit out a race prediction (at least for top 30) by just ordering the rider level predictions