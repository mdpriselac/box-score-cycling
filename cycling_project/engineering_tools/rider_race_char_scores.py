# The goal of this file is to see if we can segment riders by how they perform in different kinds of races, as defined by the race characteristics of those races.
# So, let's pick a year, like 2024. Let's go through every race. Let's go through every rider who raced at least 30 times in 2024. 
# Using that list of riders, let's calculate GC, One Day, and Stage prediction models for each rider based on their entire history.
# Then let's see if they can be segmented both within and across those models based on their performance in different. We'll be using their coefficients as the means to group them.

import os
#get the race and rider dbs
from cycling_project.data_loading_tools.load_scraped_data import load_year_path,DB_PATH
from cycling_project.data_loading_tools.create_rider_data import create_rider_db
#Get the tools for a race char db 
from cycling_project.engineering_tools.race_characteristics import RaceCharDB
#Get the place bucketer function
from cycling_project.engineering_tools.place_handling import place_bucketer
#get the regression tools
from mord import LogisticAT
from sklearn.preprocessing import StandardScaler
import pandas as pd
rider_db = create_rider_db(DB_PATH)

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

#Get a list of all riders who raced in 2024.

race_db_2024 = load_year_path(year_dir_path='~/cycling_data/scraped_data/2024')
wt_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.wt.races if isinstance(race.results, list) for rider_res_dict in race.results}
pro_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.pro.races if isinstance(race.results,list) for rider_res_dict in race.results}
d1_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.d1.races if isinstance(race.results,list) for rider_res_dict in race.results}
riders_2024 = wt_riders.union(pro_riders).union(d1_riders)

#let's create sample weights for gc, one_day, and stage by getting all the results at each level
import numpy as np
def prepare_ordinal_targets(X, y):
    """
    Prepare target variable for ordinal regression ensuring all classes are represented
    
    Args:
        X: Feature matrix
        y: Original target values
    """
    all_classes = np.arange(0, 8)
    # Add dummy examples for missing classes
    unique_classes = np.unique(y)
    missing_classes = np.setdiff1d(all_classes, unique_classes)
    
    if len(missing_classes) > 0:
        # Add one dummy example for each missing class
        dummy_X = np.zeros((len(missing_classes), X.shape[1]))
        dummy_y = missing_classes
        
        X_complete = np.vstack([X, dummy_X])
        y_complete = np.concatenate([y, dummy_y])
        
        # Create sample weights to effectively ignore dummy examples
        sample_weights = np.ones(len(X_complete))
        sample_weights[-len(missing_classes):] = 1e-10
        
        return X_complete, y_complete, sample_weights
    
    return X, y, np.ones(len(y))


#Create the full RaceCharDB 
race_char_db = RaceCharDB(year_range=range(2010,2025))


#Now that we have the 2024 riders. Let's go through each rider. Get all the races they do. Regress their place bucket for each category type. So, each rider needs three regressions. GC, STAGE, ONE_DAY.

class RiderRaceCharScores:
    def __init__(self, rider_id):
        self.fc_rider_id = rider_id
        rider_object = rider_db.riders.get(rider_id, None)
        if rider_object == None:
            raise ValueError(f'Rider ID {rider_id} not found in rider_db')
        self.rider_name = rider_object.name
        result_hist_list = rider_object.generate_race_history(prior_to_year=2025)
        if result_hist_list is None:
            raise ValueError(f'Rider ID {rider_id} has no race history')

        self.result_history = [res for res in result_hist_list]
        self.gc_model = LogisticAT()
        self.one_day_model = LogisticAT()
        self.stage_model = LogisticAT()
        self.gc_coefs = None
        self.gc_thresholds = None
        self.one_day_coefs = None
        self.one_day_thresholds = None
        self.stage_coefs = None
        self.stage_thresholds = None
    
    def generate_training_data(self):
        gc_data = []
        one_day_data = []
        stage_data = []
        for race in self.result_history:
            #Check if it is in the race_char_db
            res_race_type = race.race_type
            res_race_year = race.race_year
            race_id = race.race_fc_id
            if res_race_type.lower().strip() == 'stage':
                race_stage_name = race.race_name
            else:
                race_stage_name = None
            #Check for the race
            race_chars = race_char_db.race_lookup(fc_race_id=int(race_id),race_type=res_race_type,year=int(res_race_year),stage_name=race_stage_name)
            if race_chars is None or race_chars.shape[0] == 0:
                continue
            else:
                #add an actual_place column and set the value for the first row to the rider's actual place
                race_chars['actual_place'] = place_bucketer(race.place)
            if res_race_type.lower().strip() == 'gc':
                gc_data.append(race_chars)
            elif res_race_type.lower().strip() == 'one_day':
                one_day_data.append(race_chars)
            elif res_race_type.lower().strip() == 'stage':
                stage_data.append(race_chars)
        #Let's set minimum data requirements of having done at least 10 of a race type before we can train a model for a rider.
        if len(gc_data) < 15:
            gc_data = None
        if len(one_day_data) < 50:
            one_day_data = None
        if len(stage_data) < 125:
            stage_data = None
        return gc_data, one_day_data, stage_data
    
    def train_models(self):
        #go back through and add error and sample size tracking meta data
        gc_data, one_day_data, stage_data = self.generate_training_data()
        cols_to_drop = ['actual_place'] + race_char_db._non_data_cols
        if gc_data is not None:
            gc_data = pd.concat(gc_data)
            gc_X = gc_data.drop(columns=cols_to_drop)
            scaled_X = StandardScaler().fit_transform(gc_X)
            y = gc_data['actual_place']
            try:
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.gc_model.fit(scaled_X,y, sample_weight=sample_weights)
                self.gc_coefs = list(zip(self.gc_model.coef_,gc_X.columns))
                self.gc_thresholds = self.gc_model.theta_
            except Exception as e:
                print(f'Error training GC model for rider {self.fc_rider_id}: {e}')
        if one_day_data is not None:
            one_day_data = pd.concat(one_day_data)
            one_day_X = one_day_data.drop(columns=cols_to_drop)
            scaled_X = StandardScaler().fit_transform(one_day_X)
            y = one_day_data['actual_place']
            try:
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.one_day_model.fit(scaled_X,y, sample_weight=sample_weights)
                self.one_day_coefs = list(zip(self.one_day_model.coef_,one_day_X.columns))
                self.one_day_thresholds = self.one_day_model.theta_
            except Exception as e:
                print(f'Error training One Day model for rider {self.fc_rider_id}: {e}')
        if stage_data is not None:
            stage_data = pd.concat(stage_data)
            stage_X = stage_data.drop(columns=cols_to_drop)
            scaled_X = StandardScaler().fit_transform(stage_X)
            y = stage_data['actual_place']
            try:
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.stage_model.fit(scaled_X, y, sample_weight=sample_weights)
                self.stage_coefs = list(zip(self.stage_model.coef_,stage_X.columns))
                self.stage_thresholds = self.stage_model.theta_
            except Exception as e:
                print(f'Error training Stage model for rider {self.fc_rider_id}: {e}')
        return (self.gc_coefs, self.gc_thresholds), (self.one_day_coefs,self.one_day_thresholds), (self.stage_coefs,self.stage_thresholds)
    
            
#Now we can go through each rider, train their models and collect the data.
gc_coef_data = {}
gc_threshold_data = {}
one_day_coef_data = {}
one_day_threshold_data = {}
stage_coef_data = {}
stage_threshold_data = {}
for rider_id in riders_2024:
    try:
        rider = RiderRaceCharScores(int(rider_id))
    except ValueError as e:
        print(e)
        continue
    gc_data, one_day_data, stage_data = rider.train_models()
    if gc_data[0] is not None:
        gc_coef_data[rider_id] = {c_name:c_val for c_val,c_name in gc_data[0]}
        gc_coef_data[rider_id]['name'] = rider.rider_name
        gc_threshold_data[rider_id] = {str(i):t for i,t in enumerate(gc_data[1])}
        gc_threshold_data[rider_id]['name'] = rider.rider_name
    if one_day_data[0] is not None:
        one_day_coef_data[rider_id] = {c_name:c_val for c_val,c_name in one_day_data[0]}
        one_day_coef_data[rider_id]['name'] = rider.rider_name
        one_day_threshold_data[rider_id] = {str(i):t for i,t in enumerate(one_day_data[1])}
        one_day_threshold_data[rider_id]['name'] = rider.rider_name
    if stage_data[0] is not None:
        stage_coef_data[rider_id] = {c_name:c_val for c_val,c_name in stage_data[0]}
        stage_coef_data[rider_id]['name'] = rider.rider_name
        stage_threshold_data[rider_id] = {str(i):t for i,t in enumerate(stage_data[1])}
        stage_threshold_data[rider_id]['name'] = rider.rider_name

#create a dataframe for each of the data types
gc_coef_df = pd.DataFrame.from_dict(gc_coef_data,orient='index')
gc_threshold_df = pd.DataFrame.from_dict(gc_threshold_data,orient='index')
one_day_coef_f = pd.DataFrame.from_dict(one_day_coef_data,orient='index')
one_day_threshold_df = pd.DataFrame.from_dict(one_day_threshold_data,orient='index')
stage_coef_df = pd.DataFrame.from_dict(stage_coef_data,orient='index')
stage_threshold_df = pd.DataFrame.from_dict(stage_threshold_data,orient='index')

df_package = {'gc_coef':gc_coef_df,'gc_threshold':gc_threshold_df,'one_day_coef':one_day_coef_f,'one_day_threshold':one_day_threshold_df,'stage_coef':stage_coef_df,'stage_threshold':stage_threshold_df}