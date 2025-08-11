# Overview

The basic steps for the cluster_alignment system are as follows:

For each cluster count (3-8), for each inclusion percentage (10-100, steps of 5), we create clusters.

Next, we create cluster embeddings where each cluster is represented by their feature importances across all features. 

Once we have the cluster embeddings, we can then assign each inclusion-percentage-cluster to a master cluster. 
    At this level now we can evaluate how well clusters align and are consistent across inclusion percentages. 
    

The especially useful data here are in the alingment_results folder. if you look at the heatmaps you get a good view into where clusters from different inclusion percentages are similar. For example, if you look at the no breakdown k=3 mapy ,you'll see that the master cluster 0 assigned clusters are all very similar except for when you look at the p95 and p100 levels. For those, they match each other well but the other inclusion percentage levels very poorly

You can also see, however, when there's not great separation between clusters. So, for example when you look at the m1 cluster in the no breakdown k=3 you can see that the matching pattern between m1 clusters and m2 clusters is very similar, though slightly better for m1. That is, the cluster characteristics that define m1 clusters across inclusion percentages are similar in similar ways to the way that they are similar to the clust characteristcs that define m2 clusters across inclusion percentages. By contrast if you look at the k=4 no breakdown you'll see that the m0 clusters are always very poor matches for the m1 clusters across inclusion percentages.


In general, i think we might want to focus on the cluster counts where clustering performs the best. That was in the 40ish inclusion percentage. Have a look at the cluster_quality_reports folder


In addition to the cluster alignment I also ran a meta analysis that saw how alignment looks when you vary what the reference percentile is. For the default run, we set it at 50. But if you check across different percentiles it's possible to get some different consistency and alignment scores. 

The best thing to mine further would be the heatmap/cosine similarity based on the top performing cluster levels. That's the 25-40 inclusion percentages for the with_breakdown stages at k=3-4 for cluster counts.

The meta_reference_results folder has the results of comparing different inclusion percentages as the reference for building clusters.

the aligned_feature_comparison.py file will write up a report in the meta_reference_reults of how the features for different aligned features look.


I want to next look through the alignment heat maps to see if some of the clusters seem to be better focused at different inclusion percentages since that would suggest they're doing better at those levels or worse. Also may want to exclude 95 and 100 from the alignment etc. would be interesting to see if that's throwing things off as a weird percentile.