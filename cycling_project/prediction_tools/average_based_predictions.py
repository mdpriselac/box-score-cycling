from cycling_project.webscrape_tools.create_race_data import Race, Stage
from cycling_project.data_loading_tools.create_rider_data import RiderDB,create_rider_db,DB_PATH
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingYear,FCCyclingTour,load_year_path
from cycling_project.engineering_tools.place_handling import place_bucketer
from random import shuffle
from typing import Union,List,Dict,Tuple
import os
import pickle




def validate_race_for_prediction(race:Union[Race,Stage])->Union[Race,Stage]:
    """Checks a Race or Stage object to see if it has usable results. If it does, returns the object. If not, prints an error message and returns None.
    Args:
        race: Race or Stage object to check for results
    Returns:
        Race or Stage object with results or None"""

    #Check if the results are empty, if so, can't generate a rider prediction or history
    if race.results is None or race.results==[] or race.results=='' or len(race.results)<5:
        print(f"No results found for {race.name}, cannot generate a rider list")
        return None
    return race
    

def validate_race_result_dict(rider_dict:Dict)->Union[Dict,None]:
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
    
    return rider_dict

def prepare_race_data(validated_race:Union[Race,Stage],rider_db:RiderDB,tour_type:str|list=['wt','pro','d1'],race_type:str|list=['gc','stage','one_day'])->Tuple[List[Tuple[int,str,float,int]],float]:
    """Generates a list of individual rider predictions based on the average finishing place of each rider up to the prior to date of the race. If the race has no date but only a year, will use the previous year. Otherwise uses all prior race history.
    Can optionally specify a race type (gc, stage, one_day) and tour type (wt, pro, d1) to filter the rider history for calculating prior average finishing places.
    Args:
        validated_race: A race that has already been validated for having valid results.
        rider_db: A RiderDB object with rider career data.
        tour_type: A string or list of strings for the tour type(s) to filter rider history by. Defaults to ['wt','pro','d1'].
        race_type: A string or list of strings for the race type(s) to filter rider history by. Defaults to ['gc','stage','one_day'].
    Returns:
        A list of tuples. Each tuple is a rider id, rider name, average prior finishing place (bucketed), and actual finishing place (bucketed) for the race.
        For meta data, also returns the average rider history length that was used to calculate the average finishing place. This is useful for meta analysis to see if the predictions perform better with more data.
        """
    #Get the prior to date
    prior_to_date = validated_race.date
    if prior_to_date is None:
        prior_to_date = int(validated_race.year)
    if prior_to_date is None:
        print(f"No date or year found, can't generate a rider prediction or history for {validated_race.name}")
        return None
    #return a tuple of fc_rider_id, rider name, list of rider results, bucketed actual place
    prepared_results = []
    #go through the results list. If a rider is not in the db, skip them. If they have no race history, set the average finish to 6 for above top 30.
    #Let's also create some meta data in the form of the average rider history length. We'll use this to see if average place prediction gets better as it gets fed more data.
    rider_history_length_running_sum = 0
    valid_rider_history_count = 0
    #shake up the validated_race.results so that we don't pass any of that information on to later stages of full race prediction
    shuffle(validated_race.results)
    for res_dict in validated_race.results:
        #Validate the rider result dict
        validated_rider_dict = validate_race_result_dict(res_dict)
        if validated_rider_dict is None:
            continue
        #Get the rider id and rider career
        rider_id = validated_rider_dict['rider_id']
        rider_career = rider_db.riders.get(rider_id)
        if rider_career is None:
            print(f"Rider id {rider_id} not found in the rider_db, skipping")
            continue
        #Generate the rider history up to the prior to date, for the race_type and tour_type
        #if the prior_to_date is an int, use it as the year, if it is a date, use it as the date
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
        #Bucket the actual place
        actual_place = place_bucketer(validated_rider_dict['place'])
        prepared_results.append((rider_id,validated_rider_dict['name'],avg_place,actual_place))
        #Update the running sum of rider history length
        rider_history_length_running_sum += len(rider_history)
        valid_rider_history_count += 1
    #Calculate the average rider history length
    avg_rider_history_length = rider_history_length_running_sum/valid_rider_history_count
    return prepared_results,avg_rider_history_length

#Now that we have our prepared results, we can also create a race position predictor based on the average place for each rider to make a full race prediction where we rank and bucket based on average place.
def create_full_race_prediction(prepared_results:List[Tuple[int,str,float,int]],avg_rider_history_length:float)->Tuple[List[Tuple[int,str,float,int]],List[Tuple[int,str,int,int]],List[Tuple[int,str,int,int]],float]:
    """Creates a race prediction (ie finishing order) based on the average finishing place of each rider in the race up to that point. Returns versions with both a raw predicted finishing place and a bucketed predicted finishing place based on the raw predicted finishing place.
    Args:
        prepared_results: A list of tuples with rider id, rider name, predicted/average previous bucket place, and actual bucket place.
        avg_rider_history_length: The average length of rider history used to calculate the average finishing place.
    Returns:
        A tuple of three lists and the average rider history length.
        The first list is the prepared result list with individual rider predictions. Each entry in the list is an id,name,predicted place/average previous finishing bucket, and actual finishing bucket for a rider.
        The second list is the raw predicted places. Each entry in the list is an id,name,predicted place, and actual finishing bucket for a rider.
        The third list is the bucketed predicted places. Each entry in the list is an id,name,bucketed predicted place, and actual finishing bucket for a rider.
        The average rider history length is the fourth entry in the tuple, for meta data purposes. Compare with loss."""
    #Sort the prepared results by the average place. Now we have an ordering of riders by average prior finishing place.
    sorted_results = sorted(prepared_results,key=lambda x:x[2])
    #Create a list of tuples with the rider id, rider name, predicted place, and bucketed actual place.
    predicted_places = [(rider[0],rider[1],i+1,rider[3]) for i,rider in enumerate(sorted_results)]
    #Now bucket the predicted places
    bucketed_predicted_places = [(rider[0],rider[1],place_bucketer(rider[2]),rider[3]) for rider in predicted_places]
    #Prepared results: rider id, rider name, predicted/average previous bucket place, actual bucket place
    #Predicted places: rider id, rider name, predicted place/rank of average previous bucket place, actual bucketed place
    #Bucketed predicted places: rider id, rider name, bucketed predicted place/bucketed rank of average previous bucket places, actual bucketd place
    return prepared_results,predicted_places,bucketed_predicted_places,avg_rider_history_length
    

def create_race_predictions(race:Union[Race,Stage],rider_db:RiderDB,tour_type:str|list=['wt','pro','d1'],race_type:str|list=['gc','stage','one_day'])->Tuple[List[Tuple[int,str,float,int]],List[Tuple[int,str,int,int]],List[Tuple[int,str,int,int]],float]:
    """Create a full set of predictions based on a race. Individual rider predictions for bucketed place, raw predicted place finishing order, and bucketed predicted place finished order. Also returns the average rider history length used to calculate predictions to be used in seeing whether predictions improve with data.
    Args:
        race: Race or Stage object to predict.
        rider_db: A RiderDB object with rider career data.
        tour_type: A string or list of strings for the tour type(s) to filter rider history by. Defaults to ['wt','pro','d1'].
        race_type: A string or list of strings for the race type(s) to filter rider history by. Defaults to ['gc','stage','one_day'].
    Returns:
        A tuple of three lists and the average rider history length.
        The first list is the prepared result list with individual rider predictions. Each entry in the list is an id,name,predicted place/average previous finishing bucket, and actual finishing bucket for a rider.
        The second list is the raw predicted places. Each entry in the list is an id,name,predicted place, and actual finishing bucket for a rider.
        The third list is the bucketed predicted places. Each entry in the list is an id,name,bucketed predicted place, and actual finishing bucket for a rider.
        The average rider history length is the fourth entry in the tuple, for meta data purposes. Compare with loss."""
    #Validate the race
    validated_race = validate_race_for_prediction(race)
    if validated_race is None:
        print(f"{race.name} has no results")
        return None
    #Prepare the data
    prepared_results,avg_rider_history = prepare_race_data(validated_race=validated_race,rider_db=rider_db,race_type=race_type,tour_type=tour_type)
    if prepared_results is None:
        print(f"Error in preparing data for predictions for {race.name}, skipping")
    #create the predictions
    return create_full_race_prediction(prepared_results,avg_rider_history)


#Now that we can predict a single race, let's predict a tour.
def create_tour_year_prediction_data(tour:FCCyclingTour,rider_db:RiderDB,tour_type:str|list=['wt','pro','d1'],race_type:str|list=['gc','stage','one_day'],target_race_type:list=['gc','stage','one_day'])->list:
    
    #Predict each race to get the individual predictions with the actual results         
    if len(tour.races)==0:
        print(f"No races to predict for this tour")
        return None
    year_predictions = []
    for race in tour.races:
        if race.stage_race:
            if 'stage' not in target_race_type and 'gc' not in target_race_type:
                continue
            else:
                for stage in race.stages:
                    if 'stage' not in target_race_type and 'stage:' in stage.name.lower():
                        continue
                    if 'gc' not in target_race_type and 'gc' in stage.name.lower():
                        continue
                    try:
                        race_pred_tuple = create_race_predictions(stage,rider_db,race_type=race_type,tour_type=tour_type)
                        if race_pred_tuple is None:
                            print(f"Error in predicting {race.name}, {stage.name}, will not add to year predictions")
                        year_predictions.append(race_pred_tuple)
                    except:
                        print(f"Error in predicting {stage.name}, {race.name}, skipping")
                        continue
        else:
            if 'one_day' not in target_race_type:
                continue
            try:
                race_pred_tuple = create_race_predictions(race,rider_db)
                year_predictions.append(race_pred_tuple)
            except:
                print(f"Error in predicting {race.name}, skipping")
                continue

    return year_predictions

def create_year_prediction_data(year_db:FCCyclingYear,rider_db:RiderDB,race_type:str|list=['gc','stage','one_day'],tour_type:str|list=['wt','pro','d1'],target_race_type:list=['gc','stage','one_day'],target_tour_type:list=['wt','pro','d1'])->list:
    #predict year.wt
    #try:
    if 'wt' in target_tour_type:
        wt_preds = create_tour_year_prediction_data(tour=year_db.wt,rider_db=rider_db,tour_type=tour_type,race_type=race_type,target_race_type=target_race_type)
    else:
        wt_preds = []
    #    if wt_preds is None:
    #        print(f"No predictions for {year_db.year} wt")
    #        wt_preds = []
    #except:
    #    print(f"Error in predicting {year_db.year} wt, skipping")
    #    wt_preds = []
    #predict year.pro
    #try:
    if 'pro' in target_tour_type:
        pro_preds = create_tour_year_prediction_data(tour=year_db.pro,rider_db=rider_db,tour_type=tour_type,race_type=race_type,target_race_type=target_race_type)
    else:
        pro_preds = []
    #    if pro_preds is None:
    #        print(f"No predictions for {year_db.year} pro")
    #       pro_preds = []
    #except:
    #    print(f"Error in predicting {year_db.year} pro, skipping")
    #    pro_preds = []
    #predict year.d1
    #try:
    if 'd1' in target_tour_type:
        d1_preds = create_tour_year_prediction_data(tour=year_db.d1,rider_db=rider_db,tour_type=tour_type,race_type=race_type,target_race_type=target_race_type)
    else:
        d1_preds = []
    #    if d1_preds is None:
    #        print(f"No predictions for {year_db.year} d1")
    #        d1_preds = []
    #except:
    #    print(f"Error in predicting {year_db.year} dot 1, skipping")
    #   d1_preds = []
    #combine the predictions and return
    if wt_preds==[] and pro_preds==[] and d1_preds==[]:
        print(f"No predictions for {year_db.year}")
        return None
    return wt_preds+pro_preds+d1_preds
    
def full_prediction_script(years:List[int]=None):
    rider_db = create_rider_db()
    #Read the DB_Path to get a list of year directories
    year_dirs = [f for f in os.listdir(DB_PATH) if os.path.isdir(os.path.join(DB_PATH,f)) and len(f)==4]
    #Get specific with races to predict if specified
    if years is not None:
        filtered_years = [year for year in year_dirs if int(year) in years]
    else:
        filtered_years = year_dirs
    years_to_predict = []
    for year_dir in filtered_years:
        year_db = load_year_path(os.path.join(DB_PATH,year_dir))
        if len(year_db.wt.races)>0 or len(year_db.pro.races)>0 or len(year_db.d1.races)>0:
            years_to_predict.append(year_db)
        else:
            print(f"No races to load for {year_dir}")
    #Predict the year
    predicted_years = {}
    for year in years_to_predict:
        year_name = year.year
        predicted_years[year_name] = create_year_prediction_data(year,rider_db)
    #Save the predictions to a pkl file
    with open('avg_only_based_preds-all.pkl','wb') as f:
        pickle.dump(predicted_years,f)
    return predicted_years


            
    
    
    
    
    #get all the rider result dictionaries from the race.result.
    ## For each rider resutl dict, get the id, name, and place
    #get the race.date
    


#Predict a single Race
## Get rider histories
### How to treat rider history for unknown rider
## Calcluate previous history place average
## Order by previous shistory place average
## Return Rider id, rider name, predicted place, actual place

## Evaluate the prediction
### Calculate total error for the race

## Predict a tour
### Sum the error

## Predit a year
### Sum the error

## Predict all the race years.