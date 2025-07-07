To run a comparison, you want to try something like this: 

`uv run python database/race_kinds/find_race_kinds.py --mode evaluate --competition-type stage_one_day --use-feature-selection --feature-selection-categories wt pro --analysis-categories wt pro --eval-categories wt pro d1 --max-features 25`

That will dynamically select features, base the feature selection stage and one day races in wt or pro races, find kinds based on wt or pro stage/one days and then test against all. change argumetns as fit

From these findings it looks like we get the best clustering when looking at 30th/40th/50th percentile finishers and better. We get good silhouette scores that generalize to the d1 races perfectly fine. KMeans with min 3 clusters and Hierarchical (usually the best) seem to do well.  What we want to do is create that model and then have a way to get race values for each competition.

for stages it seems clear that we only need to consider wt and pro for selecting features and finding kinds. maybe go up to 70th percentile finishers but 50th to 60th seems to get good number of clusters populated well.


For gc, we have to look at more liek 50th percentile and above or else we start getting too small a group (ie 3 clusters with 2 of the clusters having only 1 member each). 