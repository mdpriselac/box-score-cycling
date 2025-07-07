#!/usr/bin/env python3

import pickle
import sys
import os
from pprint import pprint

# Add parent directories to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def explore_race_pkl(pkl_path):
    """Load and explore a race pickle file"""
    with open(pkl_path, 'rb') as f:
        race = pickle.load(f)
    
    print(f"Race Name: {race.name}")
    print(f"Race URL: {race.url}")
    print(f"Race Year: {race.year}")
    print(f"Race Date: {race.date}")
    print(f"Race Category: {race.category}")
    print(f"Stage Race: {race.stage_race}")
    print(f"Race Time: {race.race_time}")
    print(f"FC Race ID: {race.fc_race_id}")
    print(f"Number of Results: {len(race.results) if race.results else 0}")
    
    if race.results and len(race.results) > 0:
        print("\nFirst 3 results:")
        for i, result in enumerate(race.results[:3]):
            print(f"  {i+1}. {result}")
    
    if race.stage_race:
        print(f"\nNumber of Stages: {len(race.stages)}")
        if race.stages:
            print("Stages:")
            for stage in race.stages[:3]:
                print(f"  - {stage.name}")
                print(f"    URL: {stage.url}")
                print(f"    Date: {stage.date}")
                print(f"    Time: {stage.race_time}")
                print(f"    Results: {len(stage.results) if stage.results else 0}")

if __name__ == "__main__":
    pkl_path = sys.argv[1] if len(sys.argv) > 1 else "~/cycling_data/scraped_data/2024/wt/Amstel Gold Race.pkl"
    explore_race_pkl(pkl_path)