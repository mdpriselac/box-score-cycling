Some additional things I would like to track in the gradient features:

- at which percentile, if any, do we lose all data because we fell under the minimum rider count of 10?
- how far down from 100 towards 10 do we lose monotonicity for each feature?
- at which percentile does variance hit zero (and kurtosis go null)?
- one concern i have is that some metrics will get very screwy and have some wild swings when we get down to the 20th percentile and below. We need to think through some way of evaluating where a good bottom percentile cutoff is or how to handle screwy statistics when we get to these low percentiles.
- one weird thing we're going to encounter is that since we're counting 5th through 50th percentiles for each percentile, once we're under 20th percentile we won't have enough riders for these. How can we handle that