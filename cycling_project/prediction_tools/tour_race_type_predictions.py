#In addition to bib, team number, average finishing place, we're now also going to add in specific data for riders that takes into account how they perform in different types of races and different types of tours. Perhaps next we can add into the model how they perform in different times of the year (ie by month).

# One way to get more precise data:
# Create predictions that are limited by race_type. So, to get GC preds, just have it train and predict on gc race_types. to get one_day preds, just have it train and predict on one_day race_types. 

# Another way to enhance the model would be to add race and tour specific average finishing places for each rider when training a population wide regression model rather than just an overall finishing place. But that won't be taking into account what kind of race is being predicted when it comes to prediction time.


#Another approach is to give it all the fine grained averages and then train on each of WT, PRO and D1 and then depending on the tour of the race call the relevant predictive model but passing in all the information. Let's try that.

#So the idea is the follwing:
    #First we initialize a dictionary of lists for each of the race type race+tour type combinations we're interested in.
    #Next we work through the races in a tour.
    #Within each race we go through the results.
        #We have the tour and race type from the race
        #We get the rider bib number from the result dictionary.
        #We get the actual finishing place bucket from the result dictionary.
        #I think it's worth creating two 
            #We generate a history for each race type and race type+tour type combination that's relevant to the particular average finishing position we're calculating.

# So really things can stay similar to the bib + full average model but we just need to add in the multiple race histories.
# To start simple, let's just do race type: gc, stage, one day. Let's ignore tour type for this round.

#Actually i think we can do this by just passing in a race_type for the training data and then having the model predict with the race_type as well. Actually the problem here is that we're not filtering out the non race_type races. So we need a slightly different race_type_filter

# What we want to pass to our regression now can be something simple like:
# team number
# bib number
# wt average finishing place
# pro average finishing place
# d1 average finishing place
# gc average finishing place
# one day average finishing place
# stage average finishing place
# stage_type (onehot encoded)
# tour_type (label encoded)