from typing import Union
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingTour,FCCyclingYear
#the goal of this is to generate training data to train a population model that takes into accout:
# - rider race characteristic coefficients up to that date
# - rider age
# - tour level
# - race type finishing bucket distribution

# To do this we'll need a full, 5 char db

from cycling_project.engineering_tools.race_kinds import FiveDimDB
#Create the RaceCharDB
race_char_db = FiveDimDB(year_range=range(2010,2025))
#With the race_char_db, we can calculate the average values for each of the five dimensions
stage_mean_char_values = race_char_db.stage[['total_time','abandon_proportion','biggest_group','shattered','clumpiness']].mean()
stage_avg_coefs = (6/5)/stage_mean_char_values
#we need this to be a list of tuples where the first element is the coefficient and the second is the name of the column
stage_avg_coefs = [(coef,name) for name,coef in stage_avg_coefs.items()]
one_day_mean_char_values = race_char_db.one_day[['total_time','abandon_proportion','biggest_group','shattered','clumpiness']].mean()
one_day_avg_coefs = (6/5)/one_day_mean_char_values
one_day_avg_coefs = [(coef,name) for name,coef in one_day_avg_coefs.items()]
gc_mean_char_values = race_char_db.gc[['total_time','abandon_proportion','biggest_group','shattered','clumpiness']].mean()
gc_avg_coefs = (6/5)/gc_mean_char_values
gc_avg_coefs = [(coef,name) for name,coef in gc_mean_char_values.items()]
#Next we need to calculate the necessary coefficients so that when they're multiplied by the mean values, we get a predicted place of 6.0

# Now we need a race db
from cycling_project.data_loading_tools.create_rider_data import create_rider_db
#Create the rider db
rider_db = create_rider_db()

#From the race we need:
## Race year (to be used to get rider ages and to set the max year for the RiderRaceCharScores)
## Race type
## Tour level (label encoded)
## 5 dim race characteristics
from cycling_project.engineering_tools.race_characteristics import extract_finishing_time_distributions
from cycling_project.engineering_tools.race_kinds import calculate_five_race_dimensions

def get_race_characteristics(race:Union[Race,Stage])->dict:
    # First, validate for more than 30 finishers
    if race.results is None or len(race.results) < 30:
        raise ValueError(f"{race.name} does not have enough results to predict.")
    #Second, validate that it has race characteristics.
    try:
        race_finish_time_data = extract_finishing_time_distributions(race)
        if race_finish_time_data is None:
            raise ValueError(f"{race.name} has no finishing time data.")
    except:
        raise ValueError(f"{race.name} created an error trying to extract finishing time distribution data. No finishing time data available")

    # Third extract race characteristics
    try:
        #flatten the race_finish_time_data dict if not already flat
        flat_race_time_data = {}
        for k,v in race_finish_time_data.items():
            if not isinstance(v,dict):
                flat_race_time_data[k] = v
            else:
                flat_race_time_data.update(v)
        race_char_dict = calculate_five_race_dimensions(flat_race_time_data)
        
    except:
        raise Exception(f"Error calculating five race char dims for {race.name}")
    
    # Now that we have the race characteristics, we need to get the race tour level and encoded it
    race_tour_encoded = 0 if race.category == 'wt' else 1 if race.category == 'pro' else 2
    
    # now we need to set the race type
    if not isinstance(race,Stage):
        race_type = 'one_day'
    elif race.name.lower().replace(':','').strip() == 'gc':
        race_type = 'gc'
    else:
        race_type = 'stage'
    
    race_data = {'tour_encoded':race_tour_encoded,'race_type':race_type}
    race_data.update(race_char_dict)
    return race_data
    
    
# Now let's define a function to generate the training data for a given rider
## To create the training data for a rider:
### Get the the rider age. The rider age accessible from the rider object from the rider_db throught the .get_age() method, passing in the race year.
### Get the rider race characteristic coefficients. This is accessible from the RiderRaceCharScores objects.
#### We should save these objects in a dict by year so taht we can access without training future races for each rider every time they appear. this will help since the race is characteristics will be based on race history through the previous year to the race year.
#### The default value for all coefficients will be 6/5
from cycling_project.engineering_tools.place_handling import place_bucketer
from cycling_project.engineering_tools.rider_race_char_scores import RiderRaceCharScores
cached_RiderRaceCharScores = {y:{} for y in range(2010,2026)}

def generate_rider_data(rider_res_dict:dict,race_year:int,race_type:str)->dict:
    # First, get the rider id
    rider_id = rider_res_dict.get('rider_id',None)
    if rider_id is None:
        print(f"Rider Dict does not have an id")
        raise ValueError("Rider Dict does not have an id")
    # Second, create the RiderRaceCharScores object, which will have the rider object
    ## To do this, first check the cached_RiderRaceCharScores dict to see if the rider has been trained for this year. It will be stored with the race year as the first key and the rider id as the second key.
    try:
        rider = cached_RiderRaceCharScores.get(race_year,{}).get(int(rider_id),None)
        if rider is None:
            # If not, create the object and train it
            rider = RiderRaceCharScores(int(rider_id),prior_to_year=race_year)
            rider.train_models(race_char_db=race_char_db)
            #store the object in the cache
            cached_RiderRaceCharScores[race_year][int(rider_id)] = rider
    except ValueError as e:
        print(e)
        raise Exception(f"Failed to find or create a RiderRaceObject for rider id {rider_id} in year {race_year}")
    # Third, get the rider age
    rider_age = rider.rider_object.get_age(year=race_year)
    if rider_age is None:
        print(f"Rider {rider.rider_name} does not have an age, setting generic age of 28")
        rider_age = 28
    # Fourth, set the rider coefficients so that when combined with the mean race characteristic for races in that category, you get a predicted place of 6. Ie the 5 columns should add to 6
    # First, get the coefficients
    if rider.gc_coefs is None:
        print(f"Rider {rider.rider_name} does not have gc coefficients, setting to average")
        gc_c = gc_avg_coefs
    else:
        gc_c = rider.gc_coefs
    if rider.one_day_coefs is None:
        print(f"Rider {rider.rider_name} does not have one day coefficients, setting to average")
        one_day_c = one_day_avg_coefs
    else:
        one_day_c = rider.one_day_coefs
    if rider.stage_coefs is None:
        print(f"Rider {rider.rider_name} does not have stage coefficients, setting to average")
        stage_c = stage_avg_coefs
    else:
        stage_c = rider.stage_coefs
    # Fifth, get the distribution of finishing places for the relevant race type
    finishing_bucket_distribution_dict = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0}
    tour_distribution_dict = {'wt':0,'pro':0,'d1':0}
    if isinstance(rider.result_history,list):
        #Go through each result, get the place and update the distribution bucket
        for res in rider.result_history:
            tour_distribution_dict[res.race_tour] += 1
            if res.race_type==race_type:
                bucketed_place = place_bucketer(res.place)
                if bucketed_place is None:
                    print(f"Place for {rider.rider_name} is not valid, skipping")
                    continue
                finishing_bucket_distribution_dict[bucketed_place] += 1
        # Now normalize the distributions
        ## First, normalize the finishing bucket distribution
        finishing_bucket_total = sum(finishing_bucket_distribution_dict.values())
        finishing_bucket_prop_dict = {}
        if finishing_bucket_total > 0:
            for k,v in finishing_bucket_distribution_dict.items():
                finishing_bucket_prop_dict[f"bucket_{k}"] = v/finishing_bucket_total
        else:
            for k,v in finishing_bucket_distribution_dict.items():
                finishing_bucket_prop_dict[f"bucket_{k}"] = 0
        ## Second, normalize the tour distribution
        tour_dist_total = sum(tour_distribution_dict.values())
        tour_prop_dict = {}
        if tour_dist_total > 0:
            for k,v in tour_distribution_dict.items():
                tour_prop_dict[k+"_proportion"] = v/tour_dist_total
        else:
            for k,v in tour_distribution_dict.items():
                tour_prop_dict[k+"_proportion"] = 0
    else:
        #If there are no results set the distributions all to zero
        finishing_bucket_prop_dict = {}
        for k,v in finishing_bucket_distribution_dict.items():
            finishing_bucket_prop_dict[f"bucket_{k}"] = 0
        tour_prop_dict = {}
        for k,v in tour_distribution_dict.items():
            tour_prop_dict[k+"_proportion"] = 0
    
    # Get and bucket the actual place
    actual_place_bucketed = place_bucketer(rider_res_dict.get('place',None))
    rider_data_dict =  {'rider_id':int(rider_id),'rider_name':rider.rider_name,'rider_age':rider_age,'actual_place_bucketed':actual_place_bucketed}
    rider_data_dict.update(finishing_bucket_prop_dict)
    rider_data_dict.update(tour_prop_dict)
    #unpack the coefficients and update the rider data dict
    rider_data_dict.update({f'gc_{name}':coef for coef,name in gc_c})
    rider_data_dict.update({f'one_day_{name}':coef for coef,name in one_day_c})
    rider_data_dict.update({f'stage_{name}':coef for coef,name in stage_c})
    return rider_data_dict

def create_data_from_race(race:Union[Race,Stage])->list:
    race_training_data = []
    #First, check for race data
    try:
        race_data = get_race_characteristics(race)
    except ValueError as e:
        print(e)
        return []
    except Exception as e:
        print(e)
        return []
    #Second go through each rider result dictionary and generate the data and add the entry to the race_training_data
    for result in race.results:
        try:
            rider_data = generate_rider_data(rider_res_dict=result,race_year=int(race.year),race_type=race_data['race_type'])
        except ValueError as e:
            print(e)
            continue
        except Exception as e:
            print(e)
            continue
        rider_data.update(race_data)
        race_training_data.append(rider_data)
    return race_training_data

def create_data_from_top_level_race_obj(race:Race)->list:
    """Takes a top level race object (ie something that could be a stage race or a one day and gets all the training data out of it for each competition (GC, Stage, One Day) within it)
    Args:
        race: a Race object
    Returns:    
        A list of dictionaries with the training data for each rider in the"""
    #First, check if the race is a one_day, if so, just return the createD_data_from_race result
    if not race.stage_race:
        return create_data_from_race(race)
    #If it is a stage race, we need to get the data for each stage and the gc and add put it all into one big list.
    stage_race_results = []
    for stage in race.stages:
        try:
            stage_race_results.extend(create_data_from_race(stage))
        except ValueError as e:
            print(e)
            continue
        except Exception as e:
            print(e)
            continue
    return stage_race_results

def create_data_from_tour(tour:FCCyclingTour)->list:
    """Takes a FCCyclingTour object and generates training data for each top level race object within the tour
    Args:
        tour: a FCCyclingTour object
    Returns:
        A list of dictionaries with the training data for each rider in the tour
    """
    tour_data = []
    for race in tour.races:
        try:
            tour_data.extend(create_data_from_top_level_race_obj(race))
        except ValueError as e:
            print(f"Error creating training data from {race.name}: {e}")
            continue
        except Exception as e:
            print(f"Error creating training data from {race.name}: {e}")
            continue
    return tour_data

def create_data_from_year(year:FCCyclingYear)->list:
    """Takes a FCCyclingYear object and generates training data for each top level race within each tour for that year.
    Args:
        year: a FCCyclingYear object
    Returns:
        A list of dictionaries with the training data for each rider in the year
    """
    year_data = []
    #Try wt
    try:
        year_data.extend(create_data_from_tour(year.wt))
    except ValueError as e:
        print(f"Error creating training data from WT tour: {e}")
        pass
    except Exception as e:
        print(f"Error creating training data from WT tour: {e}")
        pass
    #Try pro
    try:
        year_data.extend(create_data_from_tour(year.pro))
    except ValueError as e:
        print(f"Error creating training data from Pro tour: {e}")
        pass
    except Exception as e:
        print(f"Error creating training data from Pro tour: {e}")
        pass
    #Try d1
    try:
        year_data.extend(create_data_from_tour(year.d1))
    except ValueError as e:
        print(f"Error creating training data from D1 tour: {e}")
        pass
    except Exception as e:
        print(f"Error creating training data from D1 tour: {e}")
        pass
    return year_data