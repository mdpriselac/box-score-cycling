# for pulling race char data, we need to do the following
## 1. Validate that the current race has race time data to create race finishing charactaristics
## 2. Get the date of the current race
## 3. For each rider in the current race:
    #Let's *just* focus on finishing characteristics for now, set aside age and bib number stuff
    ### 3a. Get their actual finishing place
    ### 3b. Get the tour type of the race
    ### 3c. Get the race type of the race
    ### 3d. Get the race characteristics of the race (based on race type)
## 4. Train a mord model for each rider based on their history.
## 5. Get the coefficients of the model for each rider.
## 6. Store the coefficients in a list for each rider.
## 7. Check for any segmentation that's possible: PCA, Clustering, etc.

from typing import List,Union
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.engineering_tools.race_kinds import FiveDimDB
from cycling_project.engineering_tools.rider_race_char_scores import RiderRaceCharScores
from cycling_project.engineering_tools.race_characteristics import extract_finishing_time_distributions
from cycling_project.engineering_tools.place_handling import place_bucketer
from cycling_project.engineering_tools.race_kinds import calculate_five_race_dimensions,process_race_for_five_dimensions
from random import shuffle
import pandas as pd

#create the RaceCharDB
race_char_db = FiveDimDB(year_range=range(2010,2025))


def predict_race_on_chars(race:Union[Race,Stage]):
    #First, validate that the race has time data and finishing characteristics
    race_char = extract_finishing_time_distributions(race)
    if race_char is None:
        print(f"{race.name} does not have time data for finishing time distribution characteristics.")
        return None
    #go through each rider result and predict finishing place bucket based on their model. Set default to 6.0
    
    if race.results is None or len(race.results) < 30:
        print(f"{race.name} has too few results to predict.")
        return None
    #flatten race_char dict if not already flat
    flat_race_char = {}
    for k,v in race_char.items():
        if not isinstance(v,dict):
            flat_race_char[k] = v
        else:
            flat_race_char.update(v)
    race_char = calculate_five_race_dimensions(flat_race_char)
    #get the race year
    race_predictions = {}
    for res_dict in race.results:
        #get the id
        rider_id = res_dict.get('rider_id',None)
        if rider_id is None:
            print(f"Rider Dict does not have an id")
            continue
        #Get the actual place
        actual_place_bucketed = place_bucketer(res_dict.get('place',None))
        if actual_place_bucketed is None:
            print(f"Place for {rider.rider_name} is not valid, skipping")
            continue
        #create the RiderRaceCharScores object
        try:
            rider = RiderRaceCharScores(int(rider_id),prior_to_year=race.year)
        except ValueError as e:
            print(e)
            continue 
        #train the rider models
        gc_values, one_day_values, stage_values = rider.train_models(race_char_db=race_char_db)
        
        #get the race type, check for not enough data, set the model for prediction
        if isinstance(race,Stage) and race.name.lower() != 'gc':
            if stage_values[0] is None:
                print(f"{rider.rider_name} does not have enough stage data to predict. Setting prediction to 6.0")
                predicted_place = 6.0
                predicted_place_capped = 6.0
                predicted_place_bucketed = 6.0
                race_predictions[rider_id] = {'rider_name':rider.rider_name,'predicted_place_raw':predicted_place,'predicted_place_capped':predicted_place_capped,'predicted_place_bucketed':predicted_place_bucketed,'actual_place':actual_place_bucketed}
                continue
            else:
                model = rider.stage_model
                coef_data = stage_values[0]
                scaler = rider.stage_scaler
        #We have a GC race if it's a stage and the name has 'GC' in it
        elif isinstance(race,Stage):
            if gc_values[0] is None:
                print(f"{rider.rider_name} does not have enough GC data to predict. Setting prediction to 6.0")
                predicted_place = 6.0
                predicted_place_capped = 6.0
                predicted_place_bucketed = 6.0
                race_predictions[rider_id] = {'rider_name':rider.rider_name,'predicted_place_raw':predicted_place,'predicted_place_capped':predicted_place_capped,'predicted_place_bucketed':predicted_place_bucketed,'actual_place':actual_place_bucketed}
                continue
            else:
                model = rider.gc_model
                coef_data = gc_values[0]
                scaler = rider.gc_scaler
        #If it's not a stage, it's a one day
        elif isinstance(race,Race):
            if one_day_values[0] is None:
                print(f"{rider.rider_name} does not have enough one day data to predict. Setting prediction to 6.0")
                predicted_place = 6.0
                predicted_place_capped = 6.0
                predicted_place_bucketed = 6.0
                race_predictions[rider_id] = {'rider_name':rider.rider_name,'predicted_place_raw':predicted_place,'predicted_place_capped':predicted_place_capped,'predicted_place_bucketed':predicted_place_bucketed,'actual_place':actual_place_bucketed}
                continue
            else:
                model = rider.one_day_model
                coef_data = one_day_values[0]
                #print(coef_data)
                scaler = rider.one_day_scaler
                
        
        #Create a ddict from the coef_data
        coef_data_dict = {rider_id: {c_name:c_val for c_val,c_name in coef_data}}
        #Create a dataframe from the race_characteristics by flattening race_char dict
        feature_order = pd.DataFrame.from_dict(coef_data_dict,orient='index').columns
        #Get the threshold info
        #thresholds = model.theta_
        #thresholds_dict = {rider_id: {str(i):t for i,t in enumerate(thresholds)}}
        
        
        
        flattened_race_char = {}
        for key,val in race_char.items():
            if not isinstance(val,dict):
                flattened_race_char[key] = val
            else:
                for k,v in val.items():
                    flattened_race_char[k] = v
        
        flattened_race_char_df = pd.DataFrame.from_dict(flattened_race_char,orient='index').T
        #reorder and filter the columns in the data to be predicted  to match the model
        reordered_filtered_df = flattened_race_char_df[feature_order]
        #scale the data
        scaled_df = scaler.transform(reordered_filtered_df)
        #predict the place
        predicted_place = model.predict(scaled_df)[0]
        #if predicted place is less than 0, set to 0. If it's greater than 7, set it to 7
        if predicted_place < 0:
            predicted_place_capped = 0.0
        elif predicted_place > 7:
            predicted_place_capped = 7.0
        else:
            predicted_place_capped = predicted_place
        #create a bucketed place
        bucketed_predicted_place = int(predicted_place_capped)
        #append rider_id, rider_name, predicted place, bucketed actual place) to predictions
        race_predictions[rider_id] = {'rider_name':rider.rider_name,'predicted_place_raw':predicted_place,'predicted_place_capped':predicted_place_capped,'predicted_place_bucketed':bucketed_predicted_place,'actual_place':actual_place_bucketed}
        #race_predictions[rider_id].update(thresholds_dict[rider_id])
    
    if len(race_predictions) == 0:
        print(f"No predictions made for {race.name}")
        return None
    
    pred_df = pd.DataFrame.from_dict(race_predictions,orient='index')
    #sort pred_dict by predicted_place, add a column, 'predicted_race_place' and set the value to the order
    pred_df.sort_values(by=['predicted_place_capped', 'predicted_place_raw'], ascending=[True, True], inplace=True)
    pred_df['predicted_race_place'] = range(1,len(pred_df)+1)
    #bucket the predicted race place
    pred_df['predicted_race_bucketed'] = pred_df['predicted_race_place'].apply(place_bucketer)
    #Create a random race ordering
    possible_places = list(range(1,len(pred_df)+1))
    for i in range(20):
        shuffle(possible_places)
    pred_df['random_race_order'] = possible_places
    pred_df['bucketed_random_race_order'] = pred_df['random_race_order'].apply(place_bucketer)
    return pred_df
        
        
    