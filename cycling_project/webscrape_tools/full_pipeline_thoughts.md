# Overall Pipeline Thoughts

Current status

- Write/Create Statistics and Engineered Features generation based on the distribution of rider finishing times.

Decision Point
- Which percentile of riders in a race do we want to use for the cutoff for calculating the rider finishing times.
    - each of these generates a race_feature_N tables for each N where N is a percentile cutoff

Once we have a set of race features we can then get rider embeddings based on performance.
- Decision Points: 
    - how do we want to measure rider performance?
        - actual uci points?
        - proportional uci points (decision point: how to discount from top level point assignments?)
        - Should we apply one_day or gc point schemes to stages to reduce the pressures of zero inflation? It gives points 60 riders down instead of 20 riders down.
    - how do we want to connect rider performance and race features?
        - Mathematical relation question: correlation between each race feature and rider performance metric?
        - Domain question: should we create race (or tour level) specific correlations. That is, when looking at a rider's prior races shoudl we limit the history to only previous races that are the same race type (or tour level)
    - how should we optimize feature selection?
        - one approach: not at all, just get all the race features, all the race_result info, and all the rider embedding features, and use that to predict outcomes. This is done via the 'full' embedding approach currently.
            - for this method we need to have some way of picking the best feature percentile
        - a second approach is to pre select features before model training. I've currently set up the optimized pipeline to work as follows for each race type:
            - First, select high quality feauters; second, eliminate redundant featuers. Third, see how well the resulting features support rider clusters. Do this process for all of the N percentiles for which we're considering race_features, then pick the best percententile with the best features. The result is a pairing of slimmed down feature set + percentile from which those data are used.
            - this is implemented as the optimized feature set approach.
        - a third approach would be a model training loop where we train a model, see what it uses most through feature importance and then retrain with a more limited set (and maybe randomly inject eliminated features to see if they help). This is not implemented
        - Another option here would be to try to characterize races by treating the different percentiles for finishers as a matrix of race features x percentiels. Then we coudl have race features that were a matrix of correlations with each race_feature x percentile
            - then we could try to do feature selection from there.
            - let's make this our next target.
            - we would represent the race features as a percentiles x feature matrix and the rider embedding as correlating the rider performance across each location.
            - i wonder if this could be an input setup that would reward a neural network? What if we thought of passing a rider embedding through race features to get a classification and or regression. Or we could combine them through something like a dot product or other method as an interaction and then running that through our model?
                - how could we incorporate the other key competition statistics?
                    - tour level
                    - rider database history in terms of points earned and count of races?
            Another thing to look at would be race kinds by seeing how they change in their feature values as you move across the percentiles. We almost progressively go through the things to see if we get a characerization of change through percentiles.
    
Model Architecture and Design
    - Dual stage, classifier first (points or no), then regressor for predicting points
    - What are the losl targets
        - accuracy?
        - f1?
        - others, etc.