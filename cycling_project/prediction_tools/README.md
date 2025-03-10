# Prediction Tools

## Conceptual Overview

### Starting Simple: Predicted Place as Average Prior Finishing Place

The first prediction method is to simply take each rider in a race and predict their finishing place bucket (see the engineering_tools README for information on the finishing place buckets) based on their average finishing place for all races up prior to that race.

We can predict their finishign bucket in two related ways. First, we just predict a bucket for each individual as the average prior finishing bucket. Second, we take the average prior finishing buckets, order them, assign places by average prior finishing bucket, and then finally bucket them. These give us individual based and race based predictions.

To start, we simply take all race and tour types and put them into one average and use that average to predict all race and tour types. 

This baseline acheives the following performance: 

- If we were to randomly assign buckets to individuals, using prior average elminiates 88% of the error (measured as MSE) compared to randomly assigning buckets. 

- Given the bucket design, however, the vast majority of riders will be receiving a 6 for their finishing bucket (ie there are usually about 130-140 riders in a race and all riders over 30 who finish will receive a 6). Compared to a simple strategy of predicting 6, predicting individual finishing buckets by aveage prior finishing bucket reduces error by about 18%.

- When we move to predicting whole races by prior average finishing bucket, we reduce the error for individual finishing buckets by a bit under 30%.

### Population Level Model

Average finishing position is simple enough as a baseline, but we can add more sophisticated versions. For example, we can predict race types based on only previous race types (e.g. only get average GC finishing places to predict future GC races) or we can predict tour types baed on only previous tour types of the same example (e.g. only get average predictions from previous World Tour races to use in the average finishing place for World Tour races). Or we could drill down to Race-Tour type combinations (e.g. only use previous GC World Tour average finishing position to predict GC World Tour races.)

There's another piece of easily accessible information that is relevant to riders, however: the information on their bibs. Not all races (especially before around 2013) have bib number information, but this information is generally available pre-race for prediction purposes so we'll include it here.

Each team is given a number (the first 1 or 2 digits on the rider bib) based on how they performed in the prior year's race. Each rider is given a number (the last digit on the rider bib) that generally describes their leadership position in the team (1 is a team leader).

The next approach will develop a population based model. Here's how it will work:

For each year, we will go through each tour. For each tour we will go through each race. For each race, if it's a stage race we'll go through each stage. For each race result we'll go through each rider and collect the following information:

- team bib number
- rider bib number
- average gc finishing position for all prior gc races in their career
- average stage finishing position for all prior stages in their career
- average one day finishing position for all prior races in their career
- average World Tour finishing position for all prior races in their career
- average Pro tour finishing position for all prior races in their career
- average .1 tour finishing positino for all prior races in their career
- actual finishing position bucket in this race

If we're predicting a given year, e.g. 2019, we'll collect this data for every year prior.

To train our model we'll then train a linear regression model based on all of these inputs as the features with the actual finishing position bucket as the target variable. 

Then for each race in 2019 we'll go through each rider who took place in the race and feed their features into the regression to get a bucket place prediction for each rider in a race. From there, as before, we can predict a race order as well.

So, all together, we're taking 3 steps forwards from a simple average based prediction:

- We're incorporating more fine grained information about average finishing position by looking at average finishing positions in all three race types and all three tour types. 
- We're going to train and predict on specific race types (e.g. when we build our dataset to train a linear regression for predicting GC races, we'll only train on GC results (although for now we can keep the fine grained average finishing data from all previous races, not just GC races as that might prove useful for the regression model)). This will reduce the amount of training data we build the model on.
- We're going to incorporate bib information. This will reduce the amount of training data we build the model on as not all previous races published bib information.

When we do these three things we get some solid improvements:

For GC races, for example, individual predictions eliminate 23% of the error compared to Guess 6, and for Race predictions we beat random placements by 42%.

For one day races, individual predictions beat the Guess 6 by 18%, which is similar to average prior place strategy, but now the race prediction bumps up to 37% improvement over random compared to only 30% with the prior average finishing position.

Our two simple approaches have drawbacks and benefits:

- The Population Level approach has a lot of input as it trains on every rider result to learn a relationship across bib, different finishing averages, and finishing places. The data is also richer: it includes bib numbers, specific race and tour type finishing places.
- The Average History approach means tht predictions aren't based on as much training data (only the data of each individual rider), and it isn't as fine grained but the prediction is tailored to each individual rider.

Next we'll combine the strengths of these approache: we'll train a model for each rider based on richer information set. For now the informatoin that we feed into the individual rider training will be the information we used for the population level model. However, over time, we'll start adding in other information: previous race history at specific events, race course specific information, and competitor information, race date information. As the features are getting more complex, we're also going to be experimenting with different regression tools.



# To Work On

Next steps have different dimesions to work on.

Continuing in individual model direction:
    - incorporate more data into the individual prediction algorithms. For example, for the next case, also incorporate tour level into the prediction system by one hot encoding it. 
    - From there we can incorporate age (normalize to 28). 
    - We can incorporate bib and team numbers. 
    - Incorporate a race_type finishing bucket proportion system ie what proportion do they finish in a given race bucket for the race_type that we're predicting.
    - Create a time scaling feature to discount older results beyond 3 years.
    - Incorporate a specific race history to that particular race (applicable in one_days and gc only)


Aiming towards a population level model direction:
    - Have each rider represented by their 5 race char dim coefficients, each race_type can have its own model trained with race_characteristics and tour_level against bucketed place. That way you train one model and can predict whole races quickly with the same model.
    - Can progressively incoporate more information into this model: age, team and personal bib numbers.
    - Since this model will have lots of data to work with, could train a more sophisticaed model, an ordinal regression model with sample weights, for example. 