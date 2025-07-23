"""
Selectivity Point Analysis Implementation

This module implements the selectivity point detection and analysis
for race classification based on where competitive racing ends.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import sqlite3


@dataclass
class SelectivityAnalysis:
    """Container for selectivity point analysis results."""
    selectivity_point: Optional[int]
    selectivity_sharpness: float
    pre_selectivity_slope: float
    post_selectivity_slope: float
    post_sp_spread: float
    post_sp_group_count: int
    post_sp_isolation_ratio: float
    post_sp_largest_group: float
    racing_intensity_score: float
    attrition_pattern: str
    selectivity_type: str


class SelectivityAnalyzer:
    """Analyze where races transition from racing to riding."""
    
    def __init__(self, db_path: str, variance_threshold: float = 0.05):
        self.db_path = db_path
        self.variance_threshold = variance_threshold
        self.percentiles = list(range(10, 101, 5))
    
    def find_selectivity_point(
        self, 
        variance_values: List[float], 
        percentiles: List[int]
    ) -> Optional[int]:
        """
        Find the percentile where normalized variance drops below threshold.
        
        Args:
            variance_values: Normalized variance at each percentile
            percentiles: Corresponding percentile values
            
        Returns:
            Percentile where selectivity occurs, or None if always competitive
        """
        for i, (percentile, variance) in enumerate(zip(percentiles, variance_values)):
            if variance is not None and variance < self.variance_threshold:
                # Check if it stays low (not just a temporary dip)
                remaining_values = variance_values[i:]
                if all(v < self.variance_threshold for v in remaining_values if v is not None):
                    return percentile
        return None
    
    def analyze_selectivity_profile(
        self, 
        variance_values: List[float], 
        percentiles: List[int],
        sp: int
    ) -> Dict:
        """Analyze how variance changes around the selectivity point."""
        sp_index = percentiles.index(sp)
        
        # Calculate sharpness (rate of drop)
        window = 3  # Look at 3 points before and after
        pre_start = max(0, sp_index - window)
        post_end = min(len(variance_values), sp_index + window)
        
        pre_values = [v for v in variance_values[pre_start:sp_index] if v is not None]
        post_values = [v for v in variance_values[sp_index:post_end] if v is not None]
        
        if len(pre_values) >= 2 and len(post_values) >= 2:
            pre_slope = np.polyfit(range(len(pre_values)), pre_values, 1)[0]
            post_slope = np.polyfit(range(len(post_values)), post_values, 1)[0]
            
            # Sharpness: ratio of change at SP to average change
            if sp_index > 0 and variance_values[sp_index-1] is not None:
                drop = variance_values[sp_index-1] - variance_values[sp_index]
                avg_drop = np.mean(np.abs(np.diff([v for v in variance_values if v is not None])))
                sharpness = min(1.0, drop / avg_drop if avg_drop > 0 else 0)
            else:
                sharpness = 0.0
        else:
            pre_slope = post_slope = sharpness = 0.0
        
        return {
            'sharpness': sharpness,
            'pre_slope': pre_slope,
            'post_slope': post_slope
        }
    
    def analyze_post_selectivity_distribution(
        self, 
        competition_id: int, 
        selectivity_percentile: int
    ) -> Dict:
        """Analyze rider distribution after the selectivity point."""
        conn = sqlite3.connect(self.db_path)
        
        # Get time gaps for riders beyond selectivity point
        total_riders_query = """
        SELECT COUNT(*) FROM rider_results 
        WHERE competition_id = ? AND time_gap IS NOT NULL
        """
        total_riders = pd.read_sql_query(
            total_riders_query, conn, params=(competition_id,)
        ).iloc[0, 0]
        
        cutoff_position = int(total_riders * selectivity_percentile / 100)
        
        # Get gaps for riders after cutoff
        gaps_query = """
        SELECT time_gap 
        FROM rider_results 
        WHERE competition_id = ? AND time_gap IS NOT NULL
        ORDER BY place
        LIMIT -1 OFFSET ?
        """
        gaps_df = pd.read_sql_query(
            gaps_query, conn, params=(competition_id, cutoff_position)
        )
        conn.close()
        
        if gaps_df.empty:
            return {
                'spread': 0.0,
                'groups': 0,
                'isolation_ratio': 0.0,
                'largest_group_size': 0.0
            }
        
        gaps = gaps_df['time_gap'].values
        
        # Calculate metrics
        spread = np.std(gaps)
        groups = self._count_groups(gaps)
        isolation_ratio = self._calculate_isolation_ratio(gaps)
        largest_group_size = self._find_largest_group_proportion(gaps)
        
        return {
            'spread': spread,
            'groups': groups,
            'isolation_ratio': isolation_ratio,
            'largest_group_size': largest_group_size
        }
    
    def _count_groups(self, gaps: np.ndarray, threshold: float = 3.0) -> int:
        """Count distinct groups based on gap threshold."""
        if len(gaps) < 2:
            return 1
        
        groups = 1
        for i in range(1, len(gaps)):
            if gaps[i] - gaps[i-1] > threshold:
                groups += 1
        return groups
    
    def _calculate_isolation_ratio(self, gaps: np.ndarray, threshold: float = 10.0) -> float:
        """Calculate proportion of isolated riders."""
        if len(gaps) < 2:
            return 0.0
        
        isolated = 0
        for i in range(len(gaps)):
            # Check distance to neighbors
            isolated_from_prev = i == 0 or (gaps[i] - gaps[i-1] > threshold)
            isolated_from_next = i == len(gaps)-1 or (gaps[i+1] - gaps[i] > threshold)
            
            if isolated_from_prev and isolated_from_next:
                isolated += 1
        
        return isolated / len(gaps)
    
    def _find_largest_group_proportion(self, gaps: np.ndarray, threshold: float = 3.0) -> float:
        """Find the proportion of riders in the largest group."""
        if len(gaps) == 0:
            return 0.0
        if len(gaps) == 1:
            return 1.0
        
        # Group riders
        groups = []
        current_group = [gaps[0]]
        
        for i in range(1, len(gaps)):
            if gaps[i] - gaps[i-1] <= threshold:
                current_group.append(gaps[i])
            else:
                groups.append(current_group)
                current_group = [gaps[i]]
        groups.append(current_group)
        
        largest_group_size = max(len(g) for g in groups)
        return largest_group_size / len(gaps)
    
    def classify_selectivity_type(self, sp: Optional[int], profile: Dict) -> str:
        """Classify the type of selectivity."""
        if sp is None:
            return "NONE"
        elif sp <= 30:
            return "EARLY"
        elif sp >= 70:
            return "LATE"
        elif profile['sharpness'] > 0.7:
            return "SUDDEN"
        else:
            return "PROGRESSIVE"
    
    def classify_attrition_pattern(self, post_sp_data: Dict) -> str:
        """Classify the pattern of riders after selectivity point."""
        if post_sp_data['largest_group_size'] > 0.7:
            return "GROUPED"
        elif post_sp_data['isolation_ratio'] > 0.5:
            return "SCATTERED"
        elif post_sp_data['groups'] > 3:
            return "MULTI_GROUP"
        else:
            return "GRADUAL"
    
    def analyze_competition(
        self, 
        competition_id: int,
        variance_gradient: Dict
    ) -> SelectivityAnalysis:
        """Complete selectivity analysis for a competition."""
        
        # Extract variance values and percentiles
        variance_values = variance_gradient.get('values', [])
        valid_percentiles = [p for p, v in zip(self.percentiles, variance_values) 
                           if v is not None]
        
        # Find selectivity point
        sp = self.find_selectivity_point(variance_values, self.percentiles)
        
        if sp is None:
            # No clear selectivity point - fully competitive race
            return SelectivityAnalysis(
                selectivity_point=None,
                selectivity_sharpness=0.0,
                pre_selectivity_slope=0.0,
                post_selectivity_slope=0.0,
                post_sp_spread=0.0,
                post_sp_group_count=0,
                post_sp_isolation_ratio=0.0,
                post_sp_largest_group=0.0,
                racing_intensity_score=1.0,
                attrition_pattern="COMPETITIVE",
                selectivity_type="NONE"
            )
        
        # Analyze selectivity profile
        profile = self.analyze_selectivity_profile(variance_values, self.percentiles, sp)
        
        # Analyze post-selectivity distribution
        post_sp_data = self.analyze_post_selectivity_distribution(competition_id, sp)
        
        # Classify patterns
        selectivity_type = self.classify_selectivity_type(sp, profile)
        attrition_pattern = self.classify_attrition_pattern(post_sp_data)
        
        return SelectivityAnalysis(
            selectivity_point=sp,
            selectivity_sharpness=profile['sharpness'],
            pre_selectivity_slope=profile['pre_slope'],
            post_selectivity_slope=profile['post_slope'],
            post_sp_spread=post_sp_data['spread'],
            post_sp_group_count=post_sp_data['groups'],
            post_sp_isolation_ratio=post_sp_data['isolation_ratio'],
            post_sp_largest_group=post_sp_data['largest_group_size'],
            racing_intensity_score=sp / 100.0,
            attrition_pattern=attrition_pattern,
            selectivity_type=selectivity_type
        )


def classify_race_by_selectivity(analysis: SelectivityAnalysis) -> str:
    """Classify race type based on selectivity analysis."""
    
    # No selectivity point = Time Trial or very competitive race
    if analysis.selectivity_point is None:
        return "TIME_TRIAL_OR_COMPETITIVE"
    
    # Early selectivity + grouped finish = Sprint
    if (analysis.selectivity_point <= 30 and 
        analysis.attrition_pattern == "GROUPED" and
        analysis.post_sp_largest_group > 0.7):
        return "SPRINT_STAGE"
    
    # Late selectivity + scattered = Mountain
    if (analysis.selectivity_point >= 60 and
        analysis.attrition_pattern == "SCATTERED" and
        analysis.post_sp_isolation_ratio > 0.4):
        return "MOUNTAIN_STAGE"
    
    # Mid selectivity + multiple groups = Echelon/Crosswind
    if (40 <= analysis.selectivity_point <= 60 and
        analysis.attrition_pattern == "MULTI_GROUP"):
        return "CROSSWIND_STAGE"
    
    # Early selectivity + small groups = Breakaway
    if (analysis.selectivity_point <= 40 and
        analysis.post_sp_group_count <= 2 and
        analysis.selectivity_sharpness > 0.6):
        return "BREAKAWAY_STAGE"
    
    # Progressive selectivity = Classic/Endurance
    if (analysis.selectivity_type == "PROGRESSIVE" and
        analysis.pre_selectivity_slope < -0.01):
        return "CLASSIC_ENDURANCE"
    
    return "MIXED_TERRAIN"


# Example usage
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = SelectivityAnalyzer(
        db_path="/path/to/database.db",
        variance_threshold=0.05
    )
    
    # Example variance gradient data
    variance_gradient = {
        'values': [0.8, 0.75, 0.7, 0.65, 0.55, 0.4, 0.2, 0.04, 0.02, 0.01],
        'percentiles': list(range(10, 101, 10))
    }
    
    # Analyze competition
    competition_id = 1234
    analysis = analyzer.analyze_competition(competition_id, variance_gradient)
    
    # Classify race
    race_type = classify_race_by_selectivity(analysis)
    
    print(f"Competition {competition_id} Analysis:")
    print(f"Selectivity Point: {analysis.selectivity_point}%")
    print(f"Racing Intensity: {analysis.racing_intensity_score:.2%}")
    print(f"Attrition Pattern: {analysis.attrition_pattern}")
    print(f"Race Classification: {race_type}")