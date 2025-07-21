1. Remove anything to do with the denorm table. We've dropped it and won't be using it. It was simply too unwieldy for our purposes. We're just working with the blob system.
2. The Nth_percentile_gap columns are always null.

Let's investigate this system a bit more by doing some straightforward print outs of the blobs we're generating.