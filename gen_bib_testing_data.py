from cycling_project.prediction_tools.bib_avg_place_predictions import prepare_training_data_for_bib_place_predictor
from cycling_project.data_loading_tools.load_scraped_data import load_db
from cycling_project.data_loading_tools.create_rider_data import create_rider_db

import pickle

racedb = load_db()
riderdb = create_rider_db()

#create training data for bib place predictor
full_training_data,full_meta_data = prepare_training_data_for_bib_place_predictor(year_to_predict=2016,full_db=racedb,rider_db=riderdb)

#save training data
with open('bib_place_predictor_training_data.pkl','wb') as f:
    pickle.dump(full_training_data,f)

print(full_meta_data)