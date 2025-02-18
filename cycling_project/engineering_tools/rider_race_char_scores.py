# The goal of this file is to see if we can segment riders by how they perform in different kinds of races, as defined by the race characteristics of those races.
# So, let's pick a year, like 2024. Let's go through every race. Let's go through every rider who raced at least 30 times in 2024. 
# Using that list of riders, let's calculate GC, One Day, and Stage prediction models for each rider based on their entire history.
# Then let's see if they can be segmented both within and across those models based on their performance in different. We'll be using their coefficients as the means to group them.

#get the race and rider dbs
from cycling_project.data_loading_tools.create_rider_data import create_rider_db,DB_PATH
#Get the place bucketer function
from cycling_project.engineering_tools.place_handling import place_bucketer
from cycling_project.engineering_tools.race_characteristics import RaceCharDB
#get the regression tools
#from mord import LogisticAT
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import pandas as pd
import numpy as np
from sklearn.utils.class_weight import compute_sample_weight
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
    def __init__(self, rider_id,prior_to_year=2025):
        self.fc_rider_id = rider_id
        rider_object = rider_db.riders.get(rider_id, None)
        if rider_object == None:
            raise ValueError(f'Rider ID {rider_id} not found in rider_db')
        self.rider_name = rider_object.name
        result_hist_list = rider_object.generate_race_history(prior_to_year=prior_to_year)
        if result_hist_list is None:
            raise ValueError(f'Rider ID {rider_id} has no race history')

        self.result_history = [res for res in result_hist_list]
        self.gc_model = LinearRegression()
        self.one_day_model = LinearRegression()
        self.stage_model = LinearRegression()
        self.gc_coefs = None
        #self.gc_thresholds = None
        self.one_day_coefs = None
        #self.one_day_thresholds = None
        self.stage_coefs = None
        #self.stage_thresholds = None
        self.gc_scaler = None
        self.one_day_scaler = None
        self.stage_scaler = None
    
    def generate_training_data(self,ref_race_char_db:RaceCharDB):
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
        if len(gc_data) < 10:
            gc_data = None
        if len(one_day_data) < 15:
            one_day_data = None
        if len(stage_data) < 50:
            stage_data = None
        return gc_data, one_day_data, stage_data
    
    def train_models(self,race_char_db:RaceCharDB):
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
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.gc_model.fit(scaled_X,y, sample_weight=sample_weights)
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
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.one_day_model.fit(scaled_X,y, sample_weight=sample_weights)
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
                scaled_X, y, sample_weights = prepare_ordinal_targets(scaled_X, y)
                self.stage_model.fit(scaled_X, y, sample_weight=sample_weights)
                self.stage_coefs = list(zip(self.stage_model.coef_,stage_X.columns))
                #self.stage_thresholds = self.stage_model.theta_
                self.stage_scaler = stage_scaler
            except Exception as e:
                print(f'Error training Stage model for rider {self.fc_rider_id}: {e}')
        #The second in each of these pairs is where the threshold would go
        return (self.gc_coefs, None), (self.one_day_coefs,None), (self.stage_coefs,None)
    
    
    
    