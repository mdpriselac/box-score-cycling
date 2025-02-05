from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.data_loading_tools.create_rider_data import RiderDB
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingYear,FCCyclingTour,FCCyclingDB
from cycling_project.engineering_tools.place_handling import place_bucketer
from random import shuffle
from typing import Union,List,Dict,Tuple
import os
import pickle
import numpy as np

from sklearn.linear_model import LinearRegression

#Steps to building model
## Training the predictor
    # To predict year Y, select all years < Y to train the model.
    # Go through all races. If the race results have bib numbers,add them to the training data sources.
    # For each race that has bib numbers add it to a counter to use as meta data for evaluating performance.
    # Go through all the training data.
        # For each rider dictionary, get the personal bib number, team bib number, and generate the bucketed average place up to that date. 
        # Extract the bib number, team bib number, average bucketed place up to that date, and actual bucketed place tuple to a training data list. 
            # for meta data purposes, increment the number of histories that were used for the average bucketed place by the number of histories seen for this rider, also increment the number of riders seen by 1.
    
    # Train a Linear Regresssion model with the team, personal and bucketed average place as features and the actual bucketed place as the target.
    # Save meta data: number of histories used for the average bucketed place, number of rider results seen. Allows for average number of histories per rider to be calculated and also just allows for number of training instances.
    # Save the model, save meta data.
        
## Predicting bucketed places
    # For the year that's being predicted, go through each race.
    # Check to see if it has bib numbers in the results.
        # If it has bib numbers in the race results, go through each rider in the results.
            # Get the bib number, team bib number, and generate the bucketed average place up to that date.
            # Use the bib number, team bib number, and bucketed average place to predict the bucketed place.
            # Add the bib number, team bib number, bucketed average place and predicted place tuple to a list of predicted results.
    
# Save the predicted results with a year data as one key and meta data for the training data as another value of the key
 
# Go to the next year and repeat the process for each year.

def get_bib_nums(raw_bib_num:List[str])->Tuple[int]:
    """Converts a list of strings to a list of integers. If the string can't be converted to an int, it's skipped and not added to the list.
    Args:
        raw_bib_nums: A list of strings to convert to integers
    Returns:
        A list of integers"""
    if raw_bib_num is None:
        return None
    if isinstance(raw_bib_num,int):
            #convert to string
            raw_bib_num = str(raw_bib_num)
    #set the team and personal numbers based on the length of the raw bib number
    if isinstance(raw_bib_num,str):
        if len(raw_bib_num) == 1:
            team_number = 0
            personal_number = int(raw_bib_num)
        elif len(raw_bib_num) == 2:
            team_number = int(raw_bib_num[0])
            personal_number = int(raw_bib_num[1])
        elif len(raw_bib_num) == 3:
            team_number = int(raw_bib_num[0:-1])
            personal_number = int(raw_bib_num[-1])
    return team_number,personal_number


def validate_bib_race_result_dict(rider_dict:Dict)->Union[Dict,None]:
    """Validates a rider result dictionary to see if it has the necessary keys and values to generate a rider prediction. If it does, returns the dict. If not, prints an error message and returns None.
    Args:
        rider_dict: A dictionary with keys 'fc_rider_id', 'rider_name', and 'place'
    Returns:
        The dictionary with keys 'fc_rider_id', 'rider_name', and 'place' or None"""
    #The fc_rider_id will be an int after being validated through here.
    #Check if the rider dict has a rider name, place, and rider id. If it does, return the dict. If not, return None.
    rider_id = rider_dict.get('rider_id')
    #If the rider id is a string, try to convert it to an int
    if isinstance(rider_id,str):
        try:
            rider_id = int(rider_id.strip())
            rider_dict['rider_id'] = rider_id
        except:
            print(f"Rider id is a string that can't be converted to an int: {rider_id}")
            return None
    
    if rider_id is None:
        print(f"Rider id is None for this rider, returning None, check data")
        return None
    
    rider_name = rider_dict.get('name')
    if rider_name is None:
        print(f"Rider name is None for this rider, returning None, check data")
        return None
    
    rider_place = rider_dict.get('place')
    if rider_place is None:
        print(f"Rider place is None for this rider, returning None, check data")
        return None
    
    rider_personal_bib = rider_dict.get('bib_number')
    if rider_personal_bib is None or rider_personal_bib == '':
        print(f"Rider personal bib is None for this rider, returning None, check data")
        return None
    
    return rider_dict

def validate_race_for_bib_prediction(race:Union[Race,Stage])->Union[Race,Stage]:
    """Checks a Race or Stage object to see if it has usable results. If it does, returns the object. If not, prints an error message and returns None.
    Args:
        race: Race or Stage object to check for results
    Returns:
        Race or Stage object with results or None"""

    #Check if the results are empty, if so, can't generate a rider prediction or history
    if race.results is None or race.results==[] or race.results=='' or len(race.results)<5:
        print(f"No results found for {race.name}, cannot generate a rider list")
        return None
    
    #run through results to see if there's at least one valid rider result, if not return None
    bib_found = False
    
    for rider_res_dict in race.results:
        rider_res_dict = validate_bib_race_result_dict(rider_res_dict)
        if rider_res_dict is not None:
            bib_found = True
            break
    if not bib_found:    
        print(f"No valid bib numbers found for {race.name}, skipping")
        return None

    return race


# Extract training data from a race
def extract_bib_place_training_data_from_race(race:Union[Race,Stage],rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'])->Tuple[List[Tuple[int,str,int,int,float,int]],Dict]:
    """Extracts training data for a race that has bib number data,  prior average bucketed finishing place data, and actual bucketed finishing place data for each rider in the race if the race has bib data in its results.
    Args:
        race: the race or stage object to extract the training data from.
        rider_db: the RiderDB object to use for generating rider histories.
        race_type: select which kind of races you want to use in generating the rider history.
        tour_type: select which kind of tours you want to use in generating the rider history.
    Returns:
        A list of tuples. The first tuple is the training data. The training data is a list of tuples with a rider ide, rider name, team bib number, personal bib number, prior average finishing place, and actual finishing place. Places are bucketed. The second tuple is a dictionary with the meta data about the training data: how many total prior races were use to generate the average finishing place and how many riders from the race had the results."""
    #validate the race
    validated_race = validate_race_for_bib_prediction(race=race)
    if validated_race is None:
        print(f"{race.name} has no valid training data with bib numbers, skipping")
        return None
    #Get prior_to_date for generating average place bucket fo the rider
    prior_to_date = validated_race.date
    if prior_to_date is None:
        prior_to_date = int(validated_race.year)
    if prior_to_date is None:
        print(f"No date or year found, can't generate a rider prediction or history for {validated_race.name}")
        return None
    #Initialize the training data list
    training_data = []
    meta_data_tracking = {'num_histories':0,'num_riders':0,}
    for rider_result_dict in validated_race.results:
        #Validate the rider result dictionary
        validated_rider_result_dict = validate_bib_race_result_dict(rider_result_dict)
        if validated_rider_result_dict is None:
            continue
        #Get the rider id
        rider_id = validated_rider_result_dict['rider_id']
        #Get the bib numbers
        team_num,personal_num = get_bib_nums(validated_rider_result_dict['bib_number'])
        if team_num is None or personal_num is None:
            print(f"Team or personal bib number is None for rider id {rider_id}, skipping")
            continue
        #Get the actual bucketed place
        actual_bucketed_place = place_bucketer(validated_rider_result_dict['place'])
        #Get the average finishing place up to the date
        #To get the average finishing place, we need the RiderCareer from the RiderDB
        rider_career = rider_db.riders.get(rider_id)
        if rider_career is None:
            print(f"Rider id {rider_id} not found in the rider_db, skipping")
            continue
        if isinstance(prior_to_date,int):
            rider_history = rider_career.generate_race_history(prior_to_year=prior_to_date,race_type=race_type,tour_type=tour_type)
        else:
            rider_history = rider_career.generate_race_history(prior_to_date=prior_to_date,race_type=race_type,tour_type=tour_type)
        #Now that we have our rider history we can make our predicted finishing place by calculating the average finishing place up to this point in the rider's career.
        #If the rider history is empty, set the average finish to 6 for above top 30
        if rider_history is None or rider_history==[]:
            avg_place = 6
        else:
            #Calculate the average place
            avg_place = sum([place_bucketer(race_res.place) for race_res in rider_history])/len(rider_history)
        #return a tuple of id, name, team number, personal number, average place, and actual place
        training_data.append((rider_id,validated_rider_result_dict['name'],team_num,personal_num,avg_place,actual_bucketed_place))
        #increment the number of histories by the len of rider_history, increment the riders processed by 1
        meta_data_tracking['num_histories'] += len(rider_history)
        meta_data_tracking['num_riders'] += 1
        
    if training_data is None or training_data == []:
        print(f"{race.name} has no valid training data, skipping")
        return None
    return training_data,meta_data_tracking
    

# Extract training data from a tour
def extract_bib_place_training_data_from_tour(tour:FCCyclingTour,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'])->Tuple:
    """Extracts training data for a linear regression model to predict bucketed places for riders in a given tour. 
    Args:
        tour: The FCCyclingTour object to use for training the model.
    Returns:
        Tuple with the training data and the meta data about the training data"""
    #Initialize the training data list
    tour_training_data = []
    #Initialize the meta data dictionary
    tour_meta_data = {'num_histories':0,'num_riders':0,'num_races':0}
    #Go through through each race in the the tour and extract the training and meta data from the race.
    for race in tour.races:
        if race.stage_race:
            #If it's a stage race but neither stages nor gc are being sought out, skip the race.
            if 'stage' not in target_race_type and 'gc' not in target_race_type:
                continue
            for stage in race.stages:
                #If the stage is a stage, skip it if we're not looking for stages
                if 'stage' in stage.name.lower() and 'stage' not in target_race_type:
                    continue
                #If the stage is a gc, skip it if we're not looking for gcs
                if 'gc' not in target_race_type and stage.name.lower().strip() == 'gc':
                    continue
                try:
                    race_res_meta_d_tuple = extract_bib_place_training_data_from_race(race=stage,rider_db=rider_db,race_type=race_type,tour_type=tour_type)
                    if race_res_meta_d_tuple is None:
                        continue
                    tour_training_data.append(race_res_meta_d_tuple[0])
                    tour_meta_data['num_histories'] += race_res_meta_d_tuple[1]['num_histories']
                    tour_meta_data['num_riders'] += race_res_meta_d_tuple[1]['num_riders']
                    tour_meta_data['num_races'] += 1
                except:
                    print(f"Error extracting training data from {race.name}, {stage.name}")
                    continue
        else:
            #Skip one days if one_day not in target race type
            if 'one_day' not in target_race_type:
                continue
            try: 
                race_res_meta_d_tuple = extract_bib_place_training_data_from_race(race=race,rider_db=rider_db,race_type=race_type,tour_type=tour_type)
                if race_res_meta_d_tuple is None:
                        continue
                tour_training_data.append(race_res_meta_d_tuple[0])
                tour_meta_data['num_histories'] += race_res_meta_d_tuple[1]['num_histories']
                tour_meta_data['num_riders'] += race_res_meta_d_tuple[1]['num_riders']
                tour_meta_data['num_races'] += 1
            except:
                print(f"Error extracting training data from {race.name}")
                continue
    return tour_training_data,tour_meta_data
                

def extract_year_training_data(year_db:FCCyclingYear,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'],target_tour_type:list=['wt','pro','d1'])->Tuple:
    """Extracts training data for a linear regression model to predict bucketed places for riders in a given year. 
    Args:
        year_db: The FCCyclingYear object to use for training the model.
    Returns:
        Tuple with the training data and the meta data about the training data"""

    #Initialize the meta data dictionary
    year_meta_data = {'num_histories':0,'num_riders':0,'num_races':0}
    #Go through each tour in the year and extract the training and meta data from the tour.
    if year_db.wt.races is None or year_db.wt.races==[] or 'wt' not in target_tour_type:
        wt_training_data = []
    else:
        wt_training_data,wt_meta_data = extract_bib_place_training_data_from_tour(tour=year_db.wt,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type)
        year_meta_data['num_histories'] += wt_meta_data['num_histories']
        year_meta_data['num_riders'] += wt_meta_data['num_riders']
        year_meta_data['num_races'] += wt_meta_data['num_races']
    
    if year_db.pro.races is None or year_db.pro.races==[] or 'pro' not in target_tour_type:
        pro_training_data = []
    else:
        pro_training_data,pro_meta_data = extract_bib_place_training_data_from_tour(tour=year_db.pro,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type)
        year_meta_data['num_histories'] += pro_meta_data['num_histories']
        year_meta_data['num_riders'] += pro_meta_data['num_riders']
        year_meta_data['num_races'] += pro_meta_data['num_races']
    
    if year_db.d1.races is None or year_db.d1.races==[] or 'd1' not in target_tour_type:
        d1_training_data = []
    else:
        d1_training_data,d1_meta_data = extract_bib_place_training_data_from_tour(tour=year_db.d1,rider_db=rider_db,race_type=race_type, tour_type=tour_type,target_race_type=target_race_type)
        year_meta_data['num_histories'] += d1_meta_data['num_histories']
        year_meta_data['num_riders'] += d1_meta_data['num_riders']
        year_meta_data['num_races'] += d1_meta_data['num_races']
    if wt_training_data == [] and pro_training_data == [] and d1_training_data == []:
        print(f"No training data found for {year_db.year}, skipping")
        return None,None
    year_training_data = wt_training_data + pro_training_data + d1_training_data
    return year_training_data, year_meta_data
    
def prepare_training_data_for_bib_place_predictor(year_to_predict:int,full_db:FCCyclingDB,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'],target_tour_type:list=['wt','pro','d1'])->Tuple:
    #get the years to train.
    years_to_train = [year for year in full_db.years if int(year.year) < year_to_predict]
    if len(years_to_train) == 0:
        print(f"No years found to train the model for {year_to_predict}")
        return None,None
    full_meta_data = {'num_histories':0,'num_riders':0,'num_races':0}
    full_training_data = []
    for year in years_to_train:
        try:
            
            year_training_data,year_meta_data = extract_year_training_data(year_db=year,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type,target_tour_type=target_tour_type)
            if year_training_data is None:
                continue
            print(f"{year.year}: {year_meta_data}")
            full_training_data += year_training_data
            full_meta_data['num_histories'] += year_meta_data['num_histories']
            full_meta_data['num_riders'] += year_meta_data['num_riders']
            full_meta_data['num_races'] += year_meta_data['num_races']
        except:
            print(f"Error extracting training data for {year.year}")
            continue
    if full_training_data == []:
        print(f"No training data found for {year_to_predict}, skipping")
        return None,None
    return full_training_data,full_meta_data

def train_bib_place_predictor(prepared_training_data:List[Tuple[int,str,int,int,float,int]])->LinearRegression:
    """Trains a linear regression model to predict bucketed places for riders in a given year."""
    #Get the features and target from the training data
    X = [rider[2:5] for race in prepared_training_data for rider in race]
    y = [rider[5] for race in prepared_training_data for rider in race]
    #Train the model
    model = LinearRegression(n_jobs=-1)
    model.fit(X,y)
    return model

### Now that we have a model, we can predict the bucketed places for each rider. Then use that to predict the overall results for the whole race




def predict_race_w_bib_data(race:Union[Race,Stage],bib_model:LinearRegression,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'])->Tuple[List[Tuple[int,str,float,int]],Dict]:
    validated_race = validate_race_for_bib_prediction(race=race)
    if validated_race is None:
        print(f"{race.name} has no valid training data with bib numbers, skipping")
        return None,None
    #Get prior_to_date for generating average place bucket fo the rider
    prior_to_date = validated_race.date
    if prior_to_date is None:
        prior_to_date = int(validated_race.year)
    if prior_to_date is None:
        print(f"No date or year found, can't generate a rider prediction or history for {validated_race.name}")
        return None,None
    #Initialize predictions and race meta data
    race_predictions = []
    race_meta_data = {'num_histories':0,'num_riders':0,}
    #Predict each rider based on team bib, indidivudal bib, and previous average finishing bucketed place
    #Return rider id, rider name, predicted bucketed finishing place, actual bucketed finishing place as a tuple and add it to race_predictions
    #Validate the rider result dictionary
    for rider_result_dict in validated_race.results:
        validated_rider_result_dict = validate_bib_race_result_dict(rider_result_dict)
        if validated_rider_result_dict is None:
            continue
        #Get the rider id
        rider_id = validated_rider_result_dict['rider_id']
        #Get the bib numbers
        team_num,personal_num = get_bib_nums(validated_rider_result_dict['bib_number'])
        if team_num is None or personal_num is None:
            #print(f"Team or personal bib number is None for rider id {rider_id}, skipping")
            continue
        #Get the actual bucketed place
        actual_bucketed_place = place_bucketer(validated_rider_result_dict['place'])
        #Get the average finishing place up to the date
        #To get the average finishing place, we need the RiderCareer from the RiderDB
        rider_career = rider_db.riders.get(rider_id)
        if rider_career is None:
            #print(f"Rider id {rider_id} not found in the rider_db, skipping")
            continue
        if isinstance(prior_to_date,int):
            rider_history = rider_career.generate_race_history(prior_to_year=prior_to_date,race_type=race_type,tour_type=tour_type)
        else:
            rider_history = rider_career.generate_race_history(prior_to_date=prior_to_date,race_type=race_type,tour_type=tour_type)
        #Now that we have our rider history we can make our predicted finishing place by calculating the average finishing place up to this point in the rider's career.
        #If the rider history is empty, set the average finish to 6 for above top 30
        if rider_history is None or rider_history==[]:
            avg_place = 6
        else:
            #Calculate the average place
            avg_place = sum([place_bucketer(race_res.place) for race_res in rider_history])/len(rider_history)
        predicted_bucketed_place = bib_model.predict([[team_num,personal_num,avg_place]])[0]
        if predicted_bucketed_place is None:
            print(f"Predicted place is None for rider id {rider_id}, skipping")
        else:
        #add a tuple of id, name, predicted place, and actual place to race_predictions
            race_predictions.append((rider_id,validated_rider_result_dict['name'],predicted_bucketed_place,actual_bucketed_place))
           #increment the number of histories by the len of rider_history, increment the riders processed by 1
            race_meta_data['num_histories'] += len(rider_history)
            race_meta_data['num_riders'] += 1
    if len(race_meta_data)==0:
        print(f"No predictions found for {race.name} skipping")
        return None,None
    return race_predictions, race_meta_data
        

def predict_tour_w_bib(tour:FCCyclingTour,bib_model:LinearRegression,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'])->Tuple[List[List[Tuple[int,str,float,int]]],Dict]:
    #Initialize Tour predictions and Meta Data
    tour_predictions = []
    tour_meta_data = {'num_histories':0,'num_riders':0, 'num_races':0}
    #Work through each race in tour.results, predict it, add predictions to tour predictions, increase the tour meta data
    for race in tour.races:
        if race.stage_race:
            if "gc" not in target_race_type and "stage" not in target_race_type:
                continue
            for stage in race.stages:
                if "stage" in stage.name.lower() and "stage" not in target_race_type:
                    continue
                if "gc" not in target_race_type and stage.name.lower().strip() == "gc":
                    continue
                    
                try:
                    race_predictions,race_meta_data = predict_race_w_bib_data(race=stage,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type)
                    if race_predictions is None:
                        continue
                    else:
                        #append the list of predictions for a race to the tour_predictions
                        tour_predictions.append(race_predictions)
                        #increment the number of histories and riders
                        tour_meta_data['num_histories'] += race_meta_data['num_histories']
                        tour_meta_data['num_riders'] += race_meta_data['num_riders']
                        tour_meta_data['num_races'] += 1
                except:
                    print(f"Error predicting {race.name}, {stage.name}")
                    continue
        else:
            if 'one_day' not in target_race_type:
                continue
            try:
                race_predictions,race_meta_data = predict_race_w_bib_data(race=race,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type)
                if race_predictions is None:
                    continue
                else:
                    #append the list of predictions for a race to the tour_predictions
                    tour_predictions.append(race_predictions)
                    #increment the number of histories and riders
                    tour_meta_data['num_histories'] += race_meta_data['num_histories']
                    tour_meta_data['num_riders'] += race_meta_data['num_riders']
                    tour_meta_data['num_races'] += 1
            except:
                print(f"Error predicting {race.name}, {stage.name}")
                continue
    if len(tour_predictions)==0:
        print(f"No predictions found for {tour.name} skipping")
        return None,None
            
    return tour_predictions, tour_meta_data

def predict_year_w_bib(year_db:FCCyclingYear,bib_model:LinearRegression,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'],target_tour_type:list=['wt','pro','d1']):
    #Initialize year predictions and meta data
    year_predictions = []
    year_meta_data = {'num_histories':0,'num_riders':0,'num_races':0}
    #Go through the world tour, pro tour, and dot one tour to predict each race.
    if len(year_db.wt.races)==0 or 'wt' not in target_tour_type:
        wt_predictions = []
    else: 
        wt_predictions,wt_meta_data = predict_tour_w_bib(tour=year_db.wt,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type)
        if wt_predictions is None:
            wt_predictions = []
        #Add each race individual from the wt_predictions list, rather than the whole list
        for race in wt_predictions:
            year_predictions.append(race)
        #increment the number of histories and riders and races in the year
        year_meta_data['num_histories'] += wt_meta_data['num_histories']
        year_meta_data['num_riders'] += wt_meta_data['num_riders']
        year_meta_data['num_races'] += wt_meta_data['num_races']
    #Go through the pro tour, predict all the races
    if len(year_db.pro.races)==0 or 'pro' not in target_tour_type:
        pro_predictions = []
    else:
        pro_predictions, pro_meta_data = predict_tour_w_bib(tour=year_db.pro,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type)
        if pro_predictions is None:
            pro_predictions = []
        else:
            for race in pro_predictions:
                year_predictions.append(race)
            year_meta_data['num_histories'] += pro_meta_data['num_histories']
            year_meta_data['num_riders'] += pro_meta_data['num_riders']
            year_meta_data['num_races'] += pro_meta_data['num_races']
    #go through the dot one tour and predict all the races
    if len(year_db.d1.races)==0 or 'd1' not in target_tour_type:
        d1_predictions = []
    else:
        d1_predictions,d1_meta_data = predict_tour_w_bib(tour=year_db.d1,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type)
        if d1_predictions is None:
            d1_predictions = []
        else:
            for race in d1_predictions:
                year_predictions.append(race)
            year_meta_data['num_histories'] += d1_meta_data['num_histories']
            year_meta_data['num_riders'] += d1_meta_data['num_riders']
            year_meta_data['num_races'] += d1_meta_data['num_races']
    
    if len(year_predictions)==0:
        print(f"No predictions found for {year_db.year} skipping")
        return None, None
    
    return year_predictions, year_meta_data

def train_predict_year_w_bib(year_to_predict:int,full_db:FCCyclingDB,rider_db:RiderDB,race_type=['gc','stage','one_day'],tour_type=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'],target_tour_type:list=['wt','pro','d1']):
    #prepare the training data
    try:
        full_training_data,full_training_meta_data = prepare_training_data_for_bib_place_predictor(year_to_predict=year_to_predict,full_db=full_db,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_tour_type=target_tour_type,target_race_type=target_race_type)    
        if full_training_data is None:
            print(f"No training data found for {year_to_predict}, skipping")
            return None,None
    except:
        print(f"Error preparing training data for {year_to_predict}")
        return None,None
    #train the model
    try:
        bib_model = train_bib_place_predictor(prepared_training_data=full_training_data)
        
        if bib_model is None:
            print(f"No model found for {year_to_predict}, skipping")
            return None,None
        print(f"Model trained for {year_to_predict}, coefficients: {bib_model.coef_}")
    except:
        print(f"Error training model for {year_to_predict}")
        return None,None
    #predict the year
    target_year = None
    for year in full_db.years:
        if int(year.year) == year_to_predict:
            target_year = year
            break
    if target_year is None:
        print(f"No year found for {year_to_predict}, skipping")
        return None,None
    try:
        year_predictions,year_meta_data = predict_year_w_bib(year_db=target_year,bib_model=bib_model,rider_db=rider_db,race_type=race_type,tour_type=tour_type,target_race_type=target_race_type,target_tour_type=target_tour_type)    
        if year_predictions is None:
            print(f"No predictions found for {year_to_predict}, skipping")
            return None,None
    except:
        print(f"Error predicting year {year_to_predict}")
        return None,None
    
    return year_predictions,year_meta_data,full_training_meta_data
        

                
