# Goals

The basic goal is to predict rider performances.

The performance of a rider is to be measured by their expected point total earned in a race. The more points the better the finish. The inputs to our prediction system will be set by rider and race.

Once we have this individual rider prediction system in place, i would like to use it to be able to characterize riders. The characterization of riders should allow us to do two things:
    - determine an overall field strength for a given race (relative to its race features).
    - sort riders into kinds by their relative strengths as determined by the kinds of races that they excel at.

## Representing Rider Success

Rider performance is to be calculated from rider results by taking the place of the rider and converting it to a point value. We have two types of point values: option 1 is the uci point scheme for all competition types and tour levels as implemented in 2026; option 2 takes the point assignments to top wt level races and then simply discounts that for lower level tours. The reason we want to try with option 2 is that it provides more points lower down while also reflecting that lower races are less impressive of a win. The overall idea of our first rider performance prediction system is to predict how well each kind of rider does at different races based on the characteristics and level of that race. We want to capture the fact that doing well in lesser competititons is not as predictive of outcomes when the level elevates.  The option 1 uci sytem does that by simply not giving out points as deep down the finishing place order. The option 2 approach we're going to test against gives out points with uniform depth but simply gives out fewer points.

The database/uci_points.py file has the infrastructure for calculating each type of point from a rider result.

## Rider Performance Features

The inputs to our rider prediction sytem will be as follows:
    - rider age, 
    - rider experience, in three varieties: 
            -total competitions completed so far
            - total competitions of the competition type completed so far (stage, gc, one day)
            - type and proportion of total competitions that are wt so far 
    - tour level (wt, pro, d1)
    - race type (stage, gc, one day)
    - the relevant race features that were used for creating race kinds of this race type (as determined by the race kind model)
    - the race kind features (ie which type of race this is, and other metrics related to the race kind)


# Background Information

For information on the data to draw on, read the `rider_performance_data_access_instructions.md` file. it will tell you how to find the data on race features and race kind features in the database that we need to use.

To understand more about the database itself, feel free to directly use sqlite3 to query the structure of the database. It is located at `~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db`

# Infrastructure requirements

To make predictions with this system, we'll need to be able to collect a rider history up to the date of the race that's being predicted, build and train the model on the historical data, and then deploy it against the inputs from the given race. So, we'll need a tool that can be given a date, pull all rider results prior to that date, and then generate the training data based on those rider results. That will require pulling race features and race kind features for past competitions in the history of the rider. 

We'll also want to implement a minimum race result history requriement before just returning a generic prediction result (we can get that by finding something like the 60th percentile point total for a given race)

As for what kind of algorithms to use for the prediction model, I'm open to discussion and having multiple chocies to look at. A key requirement here is that whatever underlying algorithm/model type we use, it needs to be paired with an appropriate way to characterize the riders as described above.

Once we have the basic system working we may well want to go back and revise it to have something like a rolling window where we weight more recent years more heavily in the prediction system.

For development purposes, I want to evaluate our prediction system by having it do three rounds of predictions: predict all 2022 competitions, predict all 2023 competitions, and predict all 2024 competitions. 