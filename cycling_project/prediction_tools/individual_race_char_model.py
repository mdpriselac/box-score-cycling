# for pulling race char data, we need to do the following
## 1. Validate that the current race has race time data to create race finishing charactaristics
## 2. Get the date of the current race
## 3. For each rider in the current race:
    #Let's *just* focus on finishing characteristics for now, set aside age and bib number stuff
    ### 3a. Get their actual finishing place
    ### 3b. Get the tour type of the race
    ### 3c. Get the race type of the race
    ### 3d. Get the race characteristics of the race (based on race type)
## 4. Train a mord model for each rider based on their history.
## 5. Get the coefficients of the model for each rider.
## 6. Store the coefficients in a list for each rider.
## 7. Check for any segmentation that's possible: PCA, Clustering, etc.