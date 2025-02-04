import os
import pickle
from cycling_project.prediction_tools.bib_avg_place_predictions import train_predict_year_w_bib
from cycling_project.data_loading_tools.load_scraped_data import load_db
from cycling_project.data_loading_tools.create_rider_data import create_rider_db

rider_db = create_rider_db()
race_db = load_db()


    
prediction_dict = {}
for year in range(2011,2017):
    prediction_tuple = train_predict_year_w_bib(year_to_predict=year,full_db=race_db,rider_db=rider_db)
    prediction_dict[year] = prediction_tuple

with open(f'bib_place_predictor_predictions-all.pkl','wb') as f:
    pickle.dump(prediction_dict,f)