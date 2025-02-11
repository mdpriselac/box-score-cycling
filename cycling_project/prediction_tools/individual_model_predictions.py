from cycling_project.prediction_tools.bib_avg_place_predictions import validate_bib_race_result_dict,validate_race_for_bib_prediction,get_bib_nums,get_rider_hist_w_unknown_date_min_req
from cycling_project.data_loading_tools.load_scraped_data import load_db,FCCyclingTour,FCCyclingYear,FCCyclingDB
from cycling_project.data_loading_tools.create_rider_data import create_rider_db,RiderResult,RiderCareer,RiderDB
from cycling_project.webscrape_tools.create_race_data import Race,Stage
from cycling_project.engineering_tools.place_handling import place_bucketer

import pandas as pd
import numpy as np

#import RandomForestRegressor
from mord import LogisticAT
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error,mean_absolute_error,confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight

from dataclasses import asdict
from typing import List,Dict,Union,Optional
import json
import os

class RiderModel(RiderCareer):
    rider_model = Optional[LogisticAT]
    def __init__(self, fc_rider_id: int, name: str):
        super().__init__(fc_rider_id, name)
        self.rider_model = None
    
    # add a create from RiderCareer class method
    @classmethod
    def create_from_rider_career(cls, rider_career: RiderCareer):
        copied_obj = cls(rider_career.fc_rider_id, rider_career.name)
        #set all the attributes of the rider career to the new rider model
        copied_obj.race_history = rider_career.race_history 
        copied_obj.dob = rider_career.dob
        copied_obj.team_history = rider_career.team_history
        copied_obj.career_start = rider_career.career_start
        copied_obj.career_end = rider_career.career_end
        return copied_obj
 
    
    def generate_historical_training_data(self,race_date:int|str):
        if isinstance(race_date,int):
            history = self.generate_race_history(prior_to_year=race_date)
        elif isinstance(race_date,str):
            history = self.generate_race_history(prior_to_date=race_date)
        else:
            print(f"Invalid Date for generating a rider history: {race_date}")
            return None
        if len(history) == 0:
            #print(f"No history for rider {self.name} on {race_date}")
            return None,None
        history_df = pd.DataFrame.from_dict([asdict(r) for r in history if isinstance(r,RiderResult)])
        history_df['place_bucketed'] = history_df['place'].apply(place_bucketer)
        #filter out rows where personal_number and team_number are not integers
        history_df = history_df[history_df['personal_number'].apply(lambda x: isinstance(x,float)) & history_df['team_number'].apply(lambda x: isinstance(x,float))]
        #If no rows are left, return None, None
        if history_df.shape[0] == 0:
            #print(f"No training data with bib numbers for {self.name} on date {race_date}")
            return None, None
        #filter out rows where age is not an integer
        history_df = history_df[history_df['age'].apply(lambda x: isinstance(x,int))]
        #If no rows are left, return None, None
        if history_df.shape[0] == 0:
            #print(f"No training data with age for rider {self.name} on date {race_date}")
            return None,None
        #Drop any rows with NaN values
        history_df = history_df.dropna()
        #If the history at this point is less than 5 rows, return None, None
        if history_df.shape[0] < 5:
            #print(f"Not enough training data for rider {self.name} on {race_date}")
            return None,None
        #training_data_columns: age, personal_number, team_number, tour_type, race_type
        #tour_type can be lable encoded wt is the highest level, pro is second leve, d1 is lowest level.
        history_df['tour_type_encoded'] = history_df['race_tour'].apply(lambda x: 0 if x == 'wt' else 1 if x == 'pro' else 2)
        #race_type needs to be one hot encoded
        history_df = pd.get_dummies(history_df, columns=['race_type'], prefix='race_type')
        training_cols = ['age','personal_number','team_number','tour_type_encoded']
        training_cols.extend([c for c in history_df.columns if c.startswith('race_type_')])
        training_data = history_df[training_cols]
        #target column: place_bucketed
        target_data = history_df['place_bucketed']
        if training_data.shape[0] == 0:
            #print(f"No training data for rider {self.name} on date {race_date}")
            return None,None
        return training_data, target_data
    

    def create_model(self,training_data:pd.DataFrame,target_data:pd.Series):
        #create training data
        #Get sample weights for unbalanced distribution
        sample_weights = compute_sample_weight(class_weight='balanced', y=target_data)
        model = LogisticAT()
        model.fit(training_data, target_data,sample_weight=sample_weights)
        #pair each coefficient with the column name
        #coefficients = model.coef_
        #feature_names = training_data.columns
        #coeff_dict = dict(zip(feature_names, coefficients))
        coeff_dict = {}
        #Get the intercept
        #intercept = model.intercept_
        #add it to the coeff_dict
        #coeff_dict['intercept'] = intercept
        #Get the number of training examples
        train_count = training_data.shape[0]
        #Get the training error as mse
        train_error = mean_absolute_error(target_data,model.predict(training_data))
        return model, train_error, train_count, coeff_dict
    
    def predict_place(self,race:Union[Race,Stage],result_dict:Dict):
        #the key data we need from a race: date,type, tour_type (category)
        #we'll get bib number info from the rider, age from the rider
        race_data = {}
        if race.date is not None:
                race_data['date'] = race.date
        else:
            race_data['date'] = int(race.year)
        race_data['tour_type'] = race.category
        if isinstance(race,Race):
            race_data['race_type'] = 'one_day'
        elif isinstance(race,Stage):
            if race.name.replace(':','').strip() == "GC":
                race_data['race_type'] = 'gc'
            else:
                race_data['race_type'] = 'stage'

        #get the rider's age from the race.year
        race_data['age'] = self.get_age(race.year)
        
        #get the bib number for the results_dict
        bib_number = result_dict.get('bib_number', None)
        
        if bib_number is not None:
            #get the team and personal bib numbers from the 
            team_number,personal_number = get_bib_nums(bib_number)
            race_data['team_number'] = team_number
            race_data['personal_number'] = personal_number
            
        else:
            print(f"No bib number found for rider {self.name}")
            return None,None
        

        #label encode the tour_type:
        race_data['tour_type_encoded'] = 0 if race_data['tour_type'] == 'wt' else 1 if race_data['tour_type'] == 'pro' else 2
        
        #create a dataframe
        race_data_df = pd.DataFrame([race_data])
        #one hot encode the race_type
        race_data_df = pd.get_dummies(race_data_df, columns=['race_type'], prefix='race_type')
        #get the columns in the correct order
        input_data = race_data_df[['age','personal_number','team_number','tour_type_encoded'] + [col for col in race_data_df.columns if col.startswith('race_type_')]].copy()
        
        
        #create the training data
        training_data, target_data = self.generate_historical_training_data(race_data['date'])
        if training_data is None or target_data is None:
            #print(f"No training data for rider {self.name} on date {race_data['date']}, returning default prediction of 6.0")
            prediction = 6.0
            training_meta_data = {'train_count':0,'train_error':0,'coefficients':{}}
            return prediction, training_meta_data
        
        #Scale the training data
        scaler = MinMaxScaler()
        scaler.fit(training_data)
        scaled_training_data = scaler.transform(training_data)
        #add column names back to scaled_training_data
        scaled_training_data = pd.DataFrame(scaled_training_data, columns=training_data.columns)
        
        #Train the model
        model, train_error, train_count, coeff_dict = self.create_model(scaled_training_data, target_data)
        
        #make sure the input data columns are teh same order as the training data columns
        #make sure that the input data columns have all the race_type_encoded columns, and the missing ones are set to zero
        #race_type columns are race_type_gc, race_type_stage, and race_type_one_day. If any of those are missing in the input data, create them and set to 0
        row_ind = input_data.index[0]
        for col in ['race_type_gc', 'race_type_stage', 'race_type_one_day']:
            if col not in input_data.columns:
                input_data.loc[row_ind,col] = 0
        #reorder the columns
        input_data = input_data[training_data.columns]
        #Scale the input data
        input_data_scaled = scaler.transform(input_data)
        #Add feature names back to the input data
        input_data_scaled = pd.DataFrame(input_data_scaled, columns=input_data.columns)
        prediction = model.predict(input_data_scaled)[0]
        training_meta_data = {'train_count':train_count,'train_error':train_error,'coefficients':coeff_dict}
        return prediction, training_meta_data
        
        
    
def predict_race_results(race:Union[Race,Stage],rider_db:RiderDB):
    #validate the race
    validated_race = validate_race_for_bib_prediction(race)
    if validated_race is None:
        print(f"Race validation failed for {race.name}.")
        return None,None  # early return if the race is not valid
    
    predictions = []
    for result_dict in validated_race.results:
        #get the rider id from the result dict
        
        rider_id = result_dict.get('rider_id',None)
        if rider_id is None:
            print(f"No rider id found for result dict: {result_dict}")
            continue
        rider_career = rider_db.riders.get(int(rider_id),None)
        if rider_career is None:
            print(f"No rider career found for rider id {rider_id}")
            continue 
        #Get the name
        rider_name = result_dict.get('name',None)
        if rider_name is None:
            rider_name = rider_career.name
        #print(f"Predicting result for {rider_id}, {rider_name}")
        #Get the actual place and create a bucketed place
        actual_place = result_dict.get('place',None)
        bucketed_actual_place = place_bucketer(actual_place)
        if bucketed_actual_place is None:
            #print(f"Invalid actual place {actual_place} for rider {rider_name}")
            continue
        #crete a rider model object
        rider_model = RiderModel.create_from_rider_career(rider_career)
        rider_model.dob = rider_career.dob
        #predict the place
        prediction, meta_data = rider_model.predict_place(race, result_dict)
        if prediction is None:
            #print(f"No prediction for rider {rider_name}")
            continue
        predictions.append((rider_id,rider_name,prediction,bucketed_actual_place,meta_data))
    return predictions

def predict_tour(tour:FCCyclingTour,rider_db:RiderDB):
    tour_predictions = []
    for race in tour.races:
        if not race.stage_race:
            race_preds = predict_race_results(race, rider_db)
            if race_preds is not None:
                tour_predictions.append(race_preds)
        elif race.stage_race:
            for stage in race.stages:
                stage_preds = predict_race_results(stage, rider_db)
                if stage_preds is not None:
                    tour_predictions.append(stage_preds)
    return tour_predictions

def predict_year(year:FCCyclingYear,rider_db:RiderDB):
    year_predictions = []
    #predict the wt races
    try:
        wt_preds = predict_tour(year.wt, rider_db)
        if wt_preds is not None:
            year_predictions.extend(wt_preds)
        else:
            print(f'No wt predictions for {year.year}')
    except:
        print(f'Error predicting wt for {year.year}')
        
    #predict the pro races
    try:
        pro_preds = predict_tour(year.pro, rider_db)
        if pro_preds is not None:
            year_predictions.extend(pro_preds)
        else:
            print(f'No pro predictions for {year.year}')
    except:
        print(f'Error predicting pro for {year.year}')
    
    #predict the dot1 races
    try:
        d1_preds = predict_tour(year.d1, rider_db)
        if d1_preds is not None:
            year_predictions.extend(d1_preds)
        else:
            print(f'No d1 predictions for {year.year}')
    except:
        print(f'Error predicting d1 for {year.year}')
    return year_predictions

def ordinal_metrics(y_true, y_pred):
    """Calculate multiple metrics for ordinal classification"""
    # Basic error metrics
    mae = mean_absolute_error(y_true, y_pred)
    
    # Calculate how often we're off by N steps
    diff = np.abs(y_true - y_pred)
    exact = np.mean(diff == 0)
    off_by_1 = np.mean(diff <= 1)
    off_by_2 = np.mean(diff <= 2)
    
    # Quadratic weighted kappa
    # Penalizes errors quadratically based on distance
    rounded_y_pred = np.round(y_pred).astype(int)
    conf_mat = confusion_matrix(y_true, rounded_y_pred)
    n_classes = conf_mat.shape[0]
    w_mat = np.zeros((n_classes, n_classes))
    for i in range(n_classes):
        for j in range(n_classes):
            w_mat[i, j] = (i - j) ** 2
    
    # Normalize confusion matrix
    conf_mat = conf_mat.astype(float)
    n_obs = float(conf_mat.sum())
    conf_mat = conf_mat / n_obs
    
    # Expected frequencies under independence
    r_sum = conf_mat.sum(axis=1)
    c_sum = conf_mat.sum(axis=0)
    exp_mat = np.outer(r_sum, c_sum)
    
    # Calculate kappa
    num = np.sum(w_mat * conf_mat)
    den = np.sum(w_mat * exp_mat)
    kappa = 1 - (num / den)
    
    return {
        'MAE': mae,
        'Exact_Match': exact,
        'Within_1': off_by_1,
        'Within_2': off_by_2,
        'Quadratic_Kappa': kappa
    }