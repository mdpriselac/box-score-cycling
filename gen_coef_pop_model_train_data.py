from cycling_project.data_loading_tools.load_scraped_data import load_year_path
from cycling_project.prediction_tools.generate_race_char_pop_model_training_data import create_data_from_year
from typing import List
import sys
import pandas as pd

def create_data_from_year_range(year_range:List[int]=list(range(2013,2025))) -> pd.DataFrame:
    full_data_set = []
    for year in year_range:
        year_db = load_year_path(f'~/cycling_data/scraped_data/{year}')
        try:
            full_data_set.extend(create_data_from_year(year_db))
        except Exception as e:
            print(f"Error creating data for year {year}: {e}")
    #save the data
    df = pd.DataFrame(full_data_set)
    df.to_parquet('all_coef_pop_model_data.parquet')
    print(f"Data saved to all_coef_pop_model_data.parquet, {df.shape}")
    return df

if __name__=="__main__":
    if len(sys.argv) > 1:
        year_start = int(sys.argv[1])
        year_end = int(sys.argv[2])
        year_range = list(range(year_start, year_end + 1))
        create_data_from_year_range(year_range)
    else:
        create_data_from_year_range()