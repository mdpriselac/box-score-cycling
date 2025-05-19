# The goal of this file is to see if we can segment riders by how they perform in different kinds of races, as defined by the race characteristics of those races.
# So, let's pick a year, like 2024. Let's go through every race. Let's go through every rider who raced at least 30 times in 2024. 
# Using that list of riders, let's calculate GC, One Day, and Stage prediction models for each rider based on their entire history.
# Then let's see if they can be segmented both within and across those models based on their performance in different. We'll be using their coefficients as the means to group them.

#get the race and rider dbs
from cycling_project.data_loading_tools.create_rider_data import create_rider_db
from cycling_project.webscrape_tools.find_races import DB_PATH
#Get the place bucketer function
from cycling_project.engineering_tools.place_handling import place_bucketer
from cycling_project.engineering_tools.race_kinds import FiveDimDB
#get the regression tools
#from mord import LogisticAT
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from sklearn.utils.class_weight import compute_sample_weight
rider_db = create_rider_db(DB_PATH)
from typing import Tuple

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



#We need to make sure even limited datasets for each rider history will have all the classes represented.
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
        sample_weights = compute_sample_weight('balanced', y_complete)
        sample_weights[-len(missing_classes):] = 1e-10
        
        return X_complete, y_complete, sample_weights
    
    sample_weights = compute_sample_weight('balanced', y)
    return X, y, sample_weights

#Next we need a class for working with the rider's history to get their specific model weights.
class RiderRaceCharScores:
    """Class for working with Rider's that can get rider specific model weights for each race type across the five dimensions of race characteristics.
    Class method for generating training data to train a rider specific model for predicted bucket place against five dimensions of race characteristics.
    Class method for training rider specific modes for each race type against the five dimensions of race characteristics.
    
    Initialization requires a rider_id and a prior_to_year (int) to collect the correct races from the rider's history to use in generating data.
    """
    def __init__(self, rider_id,prior_to_year=2025):
        self.fc_rider_id = rider_id
        self.rider_object = rider_db.riders.get(rider_id, None)
        if self.rider_object == None:
            raise ValueError(f'Rider ID {rider_id} not found in rider_db')
        self.rider_name = self.rider_object.name
        result_hist_list = self.rider_object.generate_race_history(prior_to_year=prior_to_year)
        if result_hist_list is None:
            raise ValueError(f'Rider ID {rider_id} has no race history')

        self.result_history = [res for res in result_hist_list]
        self.gc_model = LinearRegression(n_jobs=-1)
        self.one_day_model = LinearRegression(n_jobs=-1)
        self.stage_model = LinearRegression(n_jobs=-1)
        self.gc_coefs = None
        #self.gc_thresholds = None
        self.one_day_coefs = None
        #self.one_day_thresholds = None
        self.stage_coefs = None
        #self.stage_thresholds = None
        self.gc_scaler = None
        self.one_day_scaler = None
        self.stage_scaler = None
    
    def generate_training_data(self,ref_race_char_db:FiveDimDB)->Tuple[list,list,list]:
        """Generate training data for a rider specific model for predicted bucket place against five dimensions of race characteristics. Minimum requirements for training data:
        gc: 5
        one_day: 5
        stage: 25
        TO ADJUST: Consider training all models on inputs from all race types. ie gc model based on gc, one_day, and stage coefficients
        Args:
            ref_race_char_db: a FiveDimDB object to draw race data for for the rider
        Returns:
            three lists, each entry of which is a dataframe with the five race characteristics, actual place, and key race id info (id, race_type, year, name) for a single race in the rider history
        """
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
            race_chars = ref_race_char_db.race_lookup(fc_race_id=int(race_id),race_type=res_race_type,year=int(res_race_year),stage_name=race_stage_name)
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
        if len(gc_data) < 5:
            gc_data = None
        if len(one_day_data) < 5:
            one_day_data = None
        if len(stage_data) < 25:
            stage_data = None
        return gc_data, one_day_data, stage_data
    
    def train_models(self,race_char_db:FiveDimDB)->Tuple[Tuple[list,list|None],Tuple[list,list|None],Tuple[list,list|None]]:
        """Train a rider specific model for predicted bucket place against five dimensions of race characteristics.
        Models are currently set to LinearRegression, but could be changed
        First generates training data using the generate_training_data method. 
        Args:
            race_char_db: a FiveDimDB object to pull race data from
        Returns:
            three tuples, each of which contains first a list of tuples of coefficient names and coefficients and second a list of thresholds for the model (or none if a simple linear regression is trained)
        """
        #go back through and add error and sample size tracking meta data
        gc_data, one_day_data, stage_data = self.generate_training_data(ref_race_char_db=race_char_db)
        cols_to_drop = ['actual_place'] + race_char_db._non_data_cols
        if gc_data is not None:
            gc_data = pd.concat(gc_data)
            gc_X = gc_data.drop(columns=cols_to_drop)
            gc_scaler = StandardScaler() 
            scaled_X = gc_scaler.fit_transform(gc_X)
            y = gc_data['actual_place']
            try:
                #scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.gc_model.fit(scaled_X,y) #, sample_weight=sample_weights
                self.gc_coefs = list(zip(self.gc_model.coef_,gc_X.columns))
                #self.gc_thresholds = self.gc_model.theta_
                self.gc_scaler = gc_scaler
            except Exception as e:
                print(f'Error training GC model for rider {self.fc_rider_id}: {e}')
        if one_day_data is not None:
            one_day_data = pd.concat(one_day_data)
            one_day_X = one_day_data.drop(columns=cols_to_drop)
            one_day_scaler = StandardScaler()
            scaled_X = one_day_scaler.fit_transform(one_day_X)
            y = one_day_data['actual_place']
            try:
                #scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.one_day_model.fit(scaled_X,y)#, sample_weight=sample_weights
                self.one_day_coefs = list(zip(self.one_day_model.coef_,one_day_X.columns))
                #self.one_day_thresholds = self.one_day_model.theta_
                self.one_day_scaler = one_day_scaler
            except Exception as e:
                print(f'Error training One Day model for rider {self.fc_rider_id}: {e}')
        if stage_data is not None:
            stage_data = pd.concat(stage_data)
            stage_X = stage_data.drop(columns=cols_to_drop)
            stage_scaler = StandardScaler()
            scaled_X = stage_scaler.fit_transform(stage_X)
            y = stage_data['actual_place']
            try:
                #scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.stage_model.fit(scaled_X, y)#, sample_weight=sample_weights
                self.stage_coefs = list(zip(self.stage_model.coef_,stage_X.columns))
                #self.stage_thresholds = self.stage_model.theta_
                self.stage_scaler = stage_scaler
            except Exception as e:
                print(f'Error training Stage model for rider {self.fc_rider_id}: {e}')
        #The second in each of these pairs is where the threshold would go
        return (self.gc_coefs, None), (self.one_day_coefs,None), (self.stage_coefs,None)
    
    
    
    