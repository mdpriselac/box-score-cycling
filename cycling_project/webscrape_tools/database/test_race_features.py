"""
Test Suite for Race Feature Extraction

This module provides comprehensive tests for the race feature extraction system.
Run with: uv run python test_race_features.py
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import List, Dict
import os
import sys
from datetime import datetime

# Import our modules
from statistical_measures import (
    calculate_gini_coefficient,
    calculate_shannon_entropy,
    calculate_variance_and_std,
    calculate_skewness,
    calculate_kurtosis,
    calculate_percentile_gaps
)

from engineered_metrics import (
    identify_groups,
    calculate_biggest_group_metric,
    calculate_time_gap_evenness,
    calculate_clumpiness_score,
    calculate_selection_metric
)

from race_feature_extraction import (
    trim_race_results_by_percentile,
    calculate_statistical_features,
    calculate_engineered_features,
    extract_race_features
)

from race_feature_database import (
    get_competition_ids,
    create_feature_table,
    build_feature_database,
    get_feature_summary
)


class TestRaceFeatures:
    """Test class for race feature extraction."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.test_results = []
    
    def run_all_tests(self):
        """Run all tests and report results."""
        print("Starting Race Feature Extraction Tests\n")
        print("=" * 60)
        
        # Test statistical measures
        self.test_statistical_measures()
        
        # Test engineered metrics
        self.test_engineered_metrics()
        
        # Test database functions
        self.test_database_functions()
        
        # Test feature extraction
        self.test_feature_extraction()
        
        # Report results
        self.report_results()
    
    def test_statistical_measures(self):
        """Test statistical measure calculations."""
        print("\nTesting Statistical Measures...")
        
        # Test data
        test_gaps = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120]
        
        # Test Gini coefficient
        try:
            gini = calculate_gini_coefficient(test_gaps)
            assert 0 <= gini <= 1, f"Gini coefficient out of range: {gini}"
            self.test_results.append(("Gini coefficient", "PASS", f"Value: {gini:.3f}"))
        except Exception as e:
            self.test_results.append(("Gini coefficient", "FAIL", str(e)))
        
        # Test Shannon entropy
        try:
            entropy_abs, entropy_norm = calculate_shannon_entropy(test_gaps)
            assert entropy_abs >= 0, f"Absolute entropy negative: {entropy_abs}"
            assert 0 <= entropy_norm <= 1, f"Normalized entropy out of range: {entropy_norm}"
            self.test_results.append(("Shannon entropy", "PASS", 
                                    f"Abs: {entropy_abs:.3f}, Norm: {entropy_norm:.3f}"))
        except Exception as e:
            self.test_results.append(("Shannon entropy", "FAIL", str(e)))
        
        # Test variance and std
        try:
            var, std = calculate_variance_and_std(test_gaps)
            assert var >= 0, f"Variance negative: {var}"
            assert std >= 0, f"Std deviation negative: {std}"
            self.test_results.append(("Variance/Std", "PASS", f"Var: {var:.1f}, Std: {std:.1f}"))
        except Exception as e:
            self.test_results.append(("Variance/Std", "FAIL", str(e)))
        
        # Test skewness
        try:
            skew = calculate_skewness(test_gaps)
            self.test_results.append(("Skewness", "PASS", f"Value: {skew:.3f}"))
        except Exception as e:
            self.test_results.append(("Skewness", "FAIL", str(e)))
        
        # Test kurtosis
        try:
            kurt = calculate_kurtosis(test_gaps)
            self.test_results.append(("Kurtosis", "PASS", f"Value: {kurt:.3f}"))
        except Exception as e:
            self.test_results.append(("Kurtosis", "FAIL", str(e)))
        
        # Test percentile gaps
        try:
            gaps = calculate_percentile_gaps(test_gaps, [10, 25, 50, 75, 90])
            assert len(gaps) == 5, f"Wrong number of percentiles: {len(gaps)}"
            self.test_results.append(("Percentile gaps", "PASS", f"{len(gaps)} percentiles"))
        except Exception as e:
            self.test_results.append(("Percentile gaps", "FAIL", str(e)))
    
    def test_engineered_metrics(self):
        """Test engineered metric calculations."""
        print("\nTesting Engineered Metrics...")
        
        # Test data - simulating a race with groups
        test_gaps = [0, 0, 1, 1, 2, 15, 16, 16, 17, 30, 45, 60, 90, 120]
        
        # Test group identification
        try:
            groups = identify_groups(test_gaps)
            assert groups['total_groups'] >= 0, "Negative group count"
            assert groups['riders_in_groups'] <= len(test_gaps), "Too many riders in groups"
            self.test_results.append(("Group identification", "PASS", 
                                    f"{groups['total_groups']} groups found"))
        except Exception as e:
            self.test_results.append(("Group identification", "FAIL", str(e)))
        
        # Test biggest group metric
        try:
            metric = calculate_biggest_group_metric(groups, len(test_gaps))
            assert 0 <= metric <= 1, f"Biggest group metric out of range: {metric}"
            self.test_results.append(("Biggest group metric", "PASS", f"Value: {metric:.3f}"))
        except Exception as e:
            self.test_results.append(("Biggest group metric", "FAIL", str(e)))
        
        # Test evenness metric
        try:
            evenness = calculate_time_gap_evenness(test_gaps)
            assert 0 <= evenness <= 1, f"Evenness metric out of range: {evenness}"
            self.test_results.append(("Evenness metric", "PASS", f"Value: {evenness:.3f}"))
        except Exception as e:
            self.test_results.append(("Evenness metric", "FAIL", str(e)))
        
        # Test clumpiness score
        try:
            clumpiness = calculate_clumpiness_score(groups, len(test_gaps), test_gaps)
            assert 0 <= clumpiness <= 1, f"Clumpiness score out of range: {clumpiness}"
            self.test_results.append(("Clumpiness score", "PASS", f"Value: {clumpiness:.3f}"))
        except Exception as e:
            self.test_results.append(("Clumpiness score", "FAIL", str(e)))
        
        # Test selection metric
        try:
            selection = calculate_selection_metric(test_gaps, 14400)  # 4 hour race
            assert 0 <= selection <= 1, f"Selection metric out of range: {selection}"
            self.test_results.append(("Selection metric", "PASS", f"Value: {selection:.3f}"))
        except Exception as e:
            self.test_results.append(("Selection metric", "FAIL", str(e)))
    
    def test_database_functions(self):
        """Test database integration functions."""
        print("\nTesting Database Functions...")
        
        # Test getting competition IDs
        try:
            # Get some competition IDs from 2024
            comp_ids = get_competition_ids(self.db_path, year=2024, min_finishers=30)
            
            if len(comp_ids) > 0:
                self.test_results.append(("Get competition IDs", "PASS", 
                                        f"Found {len(comp_ids)} competitions"))
            else:
                self.test_results.append(("Get competition IDs", "WARN", 
                                        "No competitions found for 2024"))
        except Exception as e:
            self.test_results.append(("Get competition IDs", "FAIL", str(e)))
        
        # Test table creation
        try:
            test_table = "test_race_features"
            create_feature_table(self.db_path, test_table)
            
            # Check if table was created
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (test_table,)
            )
            exists = cursor.fetchone() is not None
            
            # Clean up
            if exists:
                cursor.execute(f"DROP TABLE {test_table}")
                conn.commit()
            conn.close()
            
            if exists:
                self.test_results.append(("Create feature table", "PASS", "Table created"))
            else:
                self.test_results.append(("Create feature table", "FAIL", "Table not created"))
        except Exception as e:
            self.test_results.append(("Create feature table", "FAIL", str(e)))
    
    def test_feature_extraction(self):
        """Test feature extraction on real data."""
        print("\nTesting Feature Extraction...")
        
        # Get a sample competition
        try:
            comp_ids = get_competition_ids(self.db_path, year=2024, min_finishers=50)
            
            if not comp_ids:
                self.test_results.append(("Feature extraction", "SKIP", 
                                        "No suitable competitions found"))
                return
            
            # Test on first competition
            comp_id = comp_ids[0]
            
            # Test trimming
            try:
                times, gaps, total, win_time = trim_race_results_by_percentile(
                    comp_id, 0.5, self.db_path
                )
                assert len(times) > 0, "No times returned"
                assert len(times) == len(gaps), "Times and gaps length mismatch"
                self.test_results.append(("Trim results", "PASS", 
                                        f"{len(times)}/{total} riders"))
            except Exception as e:
                self.test_results.append(("Trim results", "FAIL", str(e)))
                return
            
            # Test statistical features
            try:
                stat_features = calculate_statistical_features(times, gaps, win_time)
                assert len(stat_features) > 0, "No statistical features returned"
                self.test_results.append(("Statistical features", "PASS", 
                                        f"{len(stat_features)} features"))
            except Exception as e:
                self.test_results.append(("Statistical features", "FAIL", str(e)))
            
            # Test engineered features
            try:
                abandon_ratio = 1 - (len(times) / total)
                eng_features = calculate_engineered_features(
                    times, gaps, win_time, total, abandon_ratio
                )
                assert len(eng_features) > 0, "No engineered features returned"
                self.test_results.append(("Engineered features", "PASS", 
                                        f"{len(eng_features)} features"))
            except Exception as e:
                self.test_results.append(("Engineered features", "FAIL", str(e)))
            
            # Test full extraction
            try:
                features = extract_race_features(comp_id, 0.5, self.db_path)
                assert len(features) > 20, "Too few features extracted"
                self.test_results.append(("Full feature extraction", "PASS", 
                                        f"{len(features)} total features"))
            except Exception as e:
                self.test_results.append(("Full feature extraction", "FAIL", str(e)))
            
        except Exception as e:
            self.test_results.append(("Feature extraction setup", "FAIL", str(e)))
    
    def report_results(self):
        """Report test results."""
        print("\n" + "=" * 60)
        print("TEST RESULTS")
        print("=" * 60)
        
        passed = sum(1 for _, status, _ in self.test_results if status == "PASS")
        failed = sum(1 for _, status, _ in self.test_results if status == "FAIL")
        warned = sum(1 for _, status, _ in self.test_results if status == "WARN")
        skipped = sum(1 for _, status, _ in self.test_results if status == "SKIP")
        
        for test_name, status, message in self.test_results:
            status_str = f"[{status}]".ljust(8)
            print(f"{status_str} {test_name.ljust(25)} - {message}")
        
        print("\n" + "-" * 60)
        print(f"SUMMARY: {passed} passed, {failed} failed, {warned} warnings, {skipped} skipped")
        print("=" * 60)
        
        return failed == 0


def main():
    """Main test function."""
    # Get database path
    db_path = "~/Documents/Cycling Project/cycling_project/webscrape_tools/database/database/cycling_races.db"
    
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return 1
    
    # Run tests
    tester = TestRaceFeatures(db_path)
    success = tester.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())