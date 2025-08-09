def find_stable_percentile_ranges(self, stability_metrics, threshold=0.8):
    """
    Identify contiguous percentile ranges with high stability
    """
    percentile_stability = stability_metrics['percentile_stability']
    percentiles = sorted(percentile_stability.keys(), key=int)
    
    stable_ranges = []
    current_range = []
    
    for p in percentiles:
        if percentile_stability.get(p, 0) >= threshold:
            current_range.append(p)
        else:
            if len(current_range) >= 3:  # Minimum range size
                stable_ranges.append(current_range)
            current_range = []
    
    if len(current_range) >= 3:
        stable_ranges.append(current_range)
    
    return stable_ranges