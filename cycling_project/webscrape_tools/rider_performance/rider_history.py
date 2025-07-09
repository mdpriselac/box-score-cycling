"""
Module for creating rider history up to a certain date.
Collects all rider results and their features for training/prediction purposes.
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Union
from rider_result_features import RiderResultFeatures


class RiderHistory:
    """Creates comprehensive rider history including all features up to a specified date."""
    
    def __init__(self, db_path: str):
        """
        Initialize the rider history collector.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.feature_collector = RiderResultFeatures(db_path)
    
    def get_rider_history(self, rider_id: int, cutoff_date: str) -> pd.DataFrame:
        """
        Get all results and features for a rider up to a specific date.
        
        Args:
            rider_id: The rider ID
            cutoff_date: Date cutoff in 'YYYY-MM-DD' format
            
        Returns:
            DataFrame containing all rider results with features up to cutoff date
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Get all result IDs for this rider up to the cutoff date
            query = """
            SELECT rr.id as result_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date <= ?
            ORDER BY c.date
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, cutoff_date))
            result_ids = [row[0] for row in cursor.fetchall()]
            
            if not result_ids:
                return pd.DataFrame()
            
            # Get features for each result
            results_data = []
            for result_id in result_ids:
                features = self.feature_collector.get_features_for_result(result_id)
                if features:
                    results_data.append(features)
            
            if not results_data:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(results_data)
            
            # Sort by competition date
            df = df.sort_values('competition_date')
            
            return df
            
        finally:
            conn.close()
    
    def get_all_rider_histories(self, cutoff_date: str, 
                               min_results: int = 1) -> pd.DataFrame:
        """
        Get histories for all riders up to a specific date.
        
        Args:
            cutoff_date: Date cutoff in 'YYYY-MM-DD' format
            min_results: Minimum number of results required for a rider to be included
            
        Returns:
            DataFrame containing all rider results with features up to cutoff date
        """
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Get all riders who have results up to the cutoff date
            query = """
            SELECT DISTINCT rr.rider_id, COUNT(*) as result_count
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE c.date <= ?
            GROUP BY rr.rider_id
            HAVING COUNT(*) >= ?
            ORDER BY rr.rider_id
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_date, min_results))
            rider_info = cursor.fetchall()
            
            if not rider_info:
                return pd.DataFrame()
            
            print(f"Processing {len(rider_info)} riders with >= {min_results} results...")
            
            # Get histories for all qualifying riders
            all_results = []
            for i, (rider_id, result_count) in enumerate(rider_info):
                if i % 100 == 0:
                    print(f"Processing rider {i+1}/{len(rider_info)} (ID: {rider_id})")
                
                rider_df = self.get_rider_history(rider_id, cutoff_date)
                if not rider_df.empty:
                    all_results.append(rider_df)
            
            if not all_results:
                return pd.DataFrame()
            
            # Combine all results
            combined_df = pd.concat(all_results, ignore_index=True)
            
            # Sort by rider and then by date
            combined_df = combined_df.sort_values(['rider_id', 'competition_date'])
            
            return combined_df
            
        finally:
            conn.close()
    
    def get_rider_summary_stats(self, rider_id: int, cutoff_date: str) -> Dict:
        """
        Get summary statistics for a rider's career up to a specific date.
        
        Args:
            rider_id: The rider ID
            cutoff_date: Date cutoff in 'YYYY-MM-DD' format
            
        Returns:
            Dictionary containing rider career statistics
        """
        df = self.get_rider_history(rider_id, cutoff_date)
        
        if df.empty:
            return {
                'rider_id': rider_id,
                'total_races': 0,
                'gc_races': 0,
                'stage_races': 0,
                'one_day_races': 0,
                'wt_races': 0,
                'pro_races': 0,
                'd1_races': 0,
                'total_uci_points_actual': 0,
                'total_uci_points_proportional': 0,
                'avg_place': None,
                'best_place': None,
                'career_start_date': None,
                'career_end_date': None,
                'years_active': 0
            }
        
        # Calculate experience metrics
        total_races = len(df)
        gc_races = len(df[df['competition_type'] == 'gc'])
        stage_races = len(df[df['competition_type'] == 'stage'])
        one_day_races = len(df[df['competition_type'] == 'one_day'])
        
        wt_races = len(df[df['race_category'] == 'wt'])
        pro_races = len(df[df['race_category'] == 'pro'])
        d1_races = len(df[df['race_category'] == 'd1'])
        
        # Calculate points
        total_uci_actual = df['uci_points_actual'].sum()
        total_uci_proportional = df['uci_points_proportional'].sum()
        
        # Calculate performance metrics
        avg_place = df['place'].mean()
        best_place = df['place'].min()
        
        # Calculate career span
        career_start = df['competition_date'].min()
        career_end = df['competition_date'].max()
        
        # Calculate years active
        start_year = pd.to_datetime(career_start).year
        end_year = pd.to_datetime(career_end).year
        years_active = end_year - start_year + 1
        
        return {
            'rider_id': rider_id,
            'total_races': total_races,
            'gc_races': gc_races,
            'stage_races': stage_races,
            'one_day_races': one_day_races,
            'wt_races': wt_races,
            'pro_races': pro_races,
            'd1_races': d1_races,
            'wt_proportion': wt_races / total_races if total_races > 0 else 0,
            'total_uci_points_actual': total_uci_actual,
            'total_uci_points_proportional': total_uci_proportional,
            'avg_place': avg_place,
            'best_place': best_place,
            'career_start_date': career_start,
            'career_end_date': career_end,
            'years_active': years_active
        }
    
    def get_recent_form(self, rider_id: int, cutoff_date: str, 
                       months_back: int = 6) -> Dict:
        """
        Get rider's recent form over specified number of months.
        
        Args:
            rider_id: The rider ID
            cutoff_date: Date cutoff in 'YYYY-MM-DD' format
            months_back: Number of months to look back
            
        Returns:
            Dictionary containing recent form statistics
        """
        # Calculate the start date for recent form
        from datetime import datetime, timedelta
        import calendar
        
        cutoff_dt = datetime.strptime(cutoff_date, '%Y-%m-%d')
        
        # Approximate months back as days (30 days per month)
        days_back = months_back * 30
        form_start_date = cutoff_dt - timedelta(days=days_back)
        form_start_str = form_start_date.strftime('%Y-%m-%d')
        
        # Get all results in the period
        conn = sqlite3.connect(self.db_path)
        
        try:
            query = """
            SELECT rr.id as result_id
            FROM rider_results rr
            JOIN competitions c ON rr.competition_id = c.id
            WHERE rr.rider_id = ?
            AND c.date >= ?
            AND c.date <= ?
            ORDER BY c.date
            """
            
            cursor = conn.cursor()
            cursor.execute(query, (rider_id, form_start_str, cutoff_date))
            result_ids = [row[0] for row in cursor.fetchall()]
            
            if not result_ids:
                return {
                    'rider_id': rider_id,
                    'form_period_months': months_back,
                    'form_races': 0,
                    'form_avg_place': None,
                    'form_best_place': None,
                    'form_uci_points_actual': 0,
                    'form_uci_points_proportional': 0
                }
            
            # Get features for each result
            results_data = []
            for result_id in result_ids:
                features = self.feature_collector.get_features_for_result(result_id)
                if features:
                    results_data.append(features)
            
            if not results_data:
                return {
                    'rider_id': rider_id,
                    'form_period_months': months_back,
                    'form_races': 0,
                    'form_avg_place': None,
                    'form_best_place': None,
                    'form_uci_points_actual': 0,
                    'form_uci_points_proportional': 0
                }
            
            df = pd.DataFrame(results_data)
            
            return {
                'rider_id': rider_id,
                'form_period_months': months_back,
                'form_races': len(df),
                'form_avg_place': df['place'].mean(),
                'form_best_place': df['place'].min(),
                'form_uci_points_actual': df['uci_points_actual'].sum(),
                'form_uci_points_proportional': df['uci_points_proportional'].sum()
            }
            
        finally:
            conn.close()


if __name__ == "__main__":
    # Test the module
    db_path = "database/database/cycling_races.db"
    history = RiderHistory(db_path)
    
    # Test with a specific rider
    test_rider_id = 1000
    test_date = "2023-12-31"
    
    print(f"Testing rider history for rider {test_rider_id} up to {test_date}")
    
    # Get rider history
    rider_df = history.get_rider_history(test_rider_id, test_date)
    print(f"Found {len(rider_df)} results")
    
    if not rider_df.empty:
        print(f"Columns: {list(rider_df.columns)}")
        print(f"Date range: {rider_df['competition_date'].min()} to {rider_df['competition_date'].max()}")
        
        # Get summary stats
        stats = history.get_rider_summary_stats(test_rider_id, test_date)
        print(f"Summary: {stats['total_races']} races, {stats['total_uci_points_actual']} UCI points")
        
        # Get recent form
        recent_form = history.get_recent_form(test_rider_id, test_date, 6)
        print(f"Recent form: {recent_form['form_races']} races in last 6 months")
    
    # Test getting a small sample of all riders
    print(f"\nTesting all riders with >= 10 results up to {test_date}")
    all_riders_df = history.get_all_rider_histories(test_date, min_results=10)
    print(f"Found {len(all_riders_df)} total results from {all_riders_df['rider_id'].nunique()} riders")