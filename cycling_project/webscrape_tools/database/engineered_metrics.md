# Engineered Metrics Module

This module provides engineered metrics for characterizing race dynamics and finish patterns.

## Functions

### identify_groups(time_gaps: List[float], threshold_seconds: float = 1.0) -> Dict[str, any]
Identifies groups of riders finishing together within a time threshold.
- **Input**:
  - `time_gaps` - List of time gaps from winner (sorted by position)
  - `threshold_seconds` - Maximum gap between riders in same group (default: 1.0)
- **Output**: Dictionary containing:
  - `groups` - List of group details
  - `group_sizes` - List of group sizes
  - `group_positions` - Starting positions of each group
  - `total_groups` - Number of groups found
  - `riders_in_groups` - Total riders in groups
  - `largest_group_size` - Size of largest group
  - `largest_group_position` - Position of largest group
  - `proportion_in_groups` - Fraction of riders in groups
- **Example**: `groups = identify_groups(time_gaps, threshold_seconds=1.0)`

### calculate_biggest_group_metric(group_info: Dict, total_riders: int) -> float
Calculates a metric for the size and influence of the biggest group.
- **Input**:
  - `group_info` - Dictionary from identify_groups()
  - `total_riders` - Total number of riders in race
- **Output**: Score between 0-1 (1 = entire field in one group with winner)
- **Example**: `metric = calculate_biggest_group_metric(group_info, 150)`

### calculate_time_gap_evenness(time_gaps: List[float]) -> float
Measures how evenly distributed the time gaps are across the field.
- **Input**: `time_gaps` - List of time gaps from winner
- **Output**: Evenness score between 0-1 (1 = perfect even spacing)
- **Example**: `evenness = calculate_time_gap_evenness(time_gaps)`

### calculate_clumpiness_score(group_info: Dict, total_riders: int, time_gaps: List[float]) -> float
Measures how "clumpy" the race finish is (multiple distinct groups).
- **Input**:
  - `group_info` - Dictionary from identify_groups()
  - `total_riders` - Total number of riders
  - `time_gaps` - List of time gaps
- **Output**: Clumpiness score between 0-1 (high = multiple medium-sized groups)
- **Example**: `clumpiness = calculate_clumpiness_score(group_info, 150, time_gaps)`

### calculate_selection_metric(time_gaps: List[float], winning_time: float) -> float
Measures how selective/difficult the race was based on time spread.
- **Input**:
  - `time_gaps` - List of time gaps from winner
  - `winning_time` - Winner's total time in seconds
- **Output**: Selection metric between 0-1 (high = very selective race)
- **Example**: `selection = calculate_selection_metric(time_gaps, 14400)`