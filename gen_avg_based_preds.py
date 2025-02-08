from cycling_project.prediction_tools.average_based_predictions import create_year_prediction_data
from cycling_project.data_loading_tools.load_scraped_data import load_db
from cycling_project.data_loading_tools.create_rider_data import create_rider_db
import pickle

race_db = load_db()
rider_db = create_rider_db()


years = [2018,2019]
#get the yeardb that is 2019

pred_dict = {}
for year in years:
    yeardb = None
    for db in race_db.years:
        if db.year == str(year):
            yeardb = db
            print(f'{year} db foud')
            break
    if yeardb is None:
        raise ValueError(f'No db found for year {year}')
    pred_data = create_year_prediction_data(year_db=yeardb,rider_db=rider_db)
    pred_dict[year] = pred_data
    
with open(f'avg_only_preds-{"-".join([str(y) for y in years])}.pkl','wb') as f:
    pickle.dump(pred_dict,f)
