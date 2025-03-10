from cycling_project.webscrape_tools.create_race_data import Race, Stage
from typing import Union,Tuple
from mord import LogisticAT
#from cycling_project.prediction_tools.generate_race_char_pop_model_training_data import race_char_db, stage_avg_coefs,one_day_avg_coefs,gc_avg_coefs,rider_db

#this top level will allow us to get a list of dictionaries that we just then need to add a prediction to. we also need to get the race_type
from cycling_project.prediction_tools.generate_race_char_pop_model_training_data import create_data_from_race,get_race_characteristics
from train_pop_race_char_models import gc_cols_to_drop,one_day_cols_to_drop,stage_cols_to_drop,bucket_cols_to_drop
#so, we can take in any race object and get the base data. we just then need to add predictions
from sklearn.utils.class_weight import compute_sample_weight
from sklearn.metrics import mean_absolute_error, cohen_kappa_score
import pandas as pd
import joblib

#load the models
gc_model = joblib.load('./cycling_project/models/race_chars_only/gc.pkl')
one_day_model = joblib.load('./cycling_project/models/race_chars_only/one_day.pkl')
stage_model = joblib.load('./cycling_project/models/race_chars_only/stage.pkl')
model_dict = {'one_day': one_day_model,
              'stage': stage_model,
              'gc': gc_model}

drop_col_dict = {'one_day': one_day_cols_to_drop,'stage': stage_cols_to_drop,'gc': gc_cols_to_drop}

def predict_low_level_race_obj(race:Union[Race, Stage]) -> Tuple[dict,pd.DataFrame]:
    #try to get the full race data elements
    try:
        race_res_list = create_data_from_race(race)
        if len(race_res_list) == 0:
            raise Exception(f"No data found for {race.name}")
    except Exception as e:
        raise (f"Error creating data for {race.name}: {e}")
    #get the model
    race_type = get_race_characteristics(race)['race_type']
    model = model_dict[race_type]
    drop_cols = drop_col_dict[race_type]
    #loop through the race_res_list and add 'predicted_bucket' to each dictionary
    race_res_df = pd.DataFrame(race_res_list)
    #fix the age by dividing by 40
    race_res_df['rider_age'] = race_res_df['rider_age'] / 45
    pred_df = race_res_df.drop(columns=drop_cols)
    pred_df = pred_df.drop(columns=bucket_cols_to_drop).copy()
    X = pred_df.drop(columns=['actual_place_bucketed'])
    #compute sample weights
    actual_sample_weights = compute_sample_weight(class_weight='balanced',y=race_res_df['actual_place_bucketed'])
    #get the predictions
    preds = model.predict(X)
    #add the predictions to the race_res_df as 'predicted_bucket'
    race_res_df['predicted_bucket'] = preds
    #evaluate the predictions for MAE, Kappa, exact match, within 1
    # Calculate raw MAE (lower is better)
    mae = mean_absolute_error(race_res_df['actual_place_bucketed'], race_res_df['predicted_bucket'],sample_weight=actual_sample_weights)
    #print(f"Mean Absolute Error: {mae:.4f}")

    # Calculate Cohen's Kappa (measures agreement, higher is better)
    kappa = cohen_kappa_score(race_res_df['actual_place_bucketed'], race_res_df['predicted_bucket'], weights='quadratic',sample_weight=actual_sample_weights)
    #print(f"Cohen's Kappa: {kappa:.4f}")

    # Calculate accuracy (exact matches)
    accuracy = (race_res_df['predicted_bucket'] == race_res_df['actual_place_bucketed']).mean()
    #print(f"Accuracy: {accuracy:.4f}")

    # Calculate within-one accuracy (predictions within ±1 class)
    within_one = (abs(race_res_df['predicted_bucket'] - race_res_df['actual_place_bucketed']) <= 1).mean()
    #print(f"Within-One Accuracy: {within_one:.4f}")
    
    eval_dict = {
        'mae': mae,
        'kappa': kappa,
        'accuracy': accuracy,
        'within_one': within_one
    }
    
    return race_res_df, eval_dict

def predict_top_level_race_object(race:Race) -> Tuple[dict,dict]:
    #if the race is not a stage race, just return the predictions for the one day
    if not race.stage_race:
        return predict_low_level_race_obj(race)
    #if the race is a stage race, process each stage
    stage_results = {}
    eval_results = {}
    for stage in race.stages:
        name = f"{stage.race}: {stage.name}"
        stage_df, eval_dict = predict_low_level_race_obj(stage)
        stage_results[name] = stage_df
        eval_results[name] = eval_dict
    
    eval_df = pd.DataFrame.from_dict(eval_results,orient='index')
    #create a df from the eval results
    
    return stage_results, eval_df


# Next step is to play around with model confidence and other metrics besides raw bucketed place.# Get probability distributions across all classes
#probabilities = model.predict_proba(X_test)

# Example for first test sample
#sample_idx = 0
#print(f"Class probability distribution: {probabilities[sample_idx]}")

# Find most likely and second most likely classes
#top_classes = np.argsort(probabilities[sample_idx])[::-1][:2]
#print(f"Most likely class: {top_classes[0]} with {probabilities[sample_idx][top_classes[0]]:.4f} probability")
#print(f"Second most likely: {top_classes[1]} with {probabilities[sample_idx][top_classes[1]]:.4f} probability")

# Predict specifically for a class cutpoint 
# (whether sample is predicted to be in class k or higher)
#k = 3  # Example threshold
#class_predictions = model._predict_proba_lr(X_test)[:, k]

#print(f"Probability of being in class {k} or higher: {class_predictions[sample_idx]:.4f}")def compare_riders(model, X_test, rider_indices):
#    """Compare probability distributions for multiple riders"""
#    probas = model.predict_proba(X_test.iloc[rider_indices])
#    
#    comparison = {}
#    for i, rider_idx in enumerate(rider_indices):
#        comparison[f"Rider {i+1}"] = {
#            "probabilities": probas[i],
#            "most_likely_class": np.argmax(probas[i]),
#            "confidence": np.max(probas[i]),
#            "decision_value": model.decision_function(X_test.iloc[[rider_idx]])[0]
#        }
    
    # Calculate similarity between probability distributions
#    for i in range(len(rider_indices)):
#        for j in range(i+1, len(rider_indices)):
#            # KL divergence or other similarity measure
#            similarity = np.sum(np.minimum(
#                probas[i], probas[j]
#            ))
#            comparison[f"Similarity_{i+1}_{j+1}"] = similarity
#            
#    return comparison

# Compare three riders
#rider_comparison = compare_riders(model, gc_X_test, [10, 20, 30])

#def analyze_prediction_factors(model, X, sample_idx):
 #   """Analyze what factors contribute to a specific prediction"""
    # Get coefficients and individual feature values
    #coeffs = model.coef_[0]
    #features = X.iloc[sample_idx] if hasattr(X, 'iloc') else X[sample_idx]
    
    # Calculate individual contributions
    #contributions = pd.DataFrame({
    #    'feature': X.columns if hasattr(X, 'columns') else [f'feature_{i}' for i in range(X.shape[1])],
    #    'value': features,
    #    'coefficient': coeffs,
    #    'impact': features * coeffs
   # })
    
    # Sort by absolute impact
  #  contributions = contributions.sort_values('impact', key=abs, ascending=False)
    
 #   return contributions

# Get factors contributing to prediction
#factors = analyze_prediction_factors(model, gc_X_test, sample_idx)
#print("Top factors contributing to prediction:")
#print(factors.head())
#
#def prediction_confidence(proba):
#    """Calculate confidence as difference between top two probabilities"""
#    sorted_proba = np.sort(proba, axis=1)[::-1]
#    confidence = sorted_proba[0] - sorted_proba[1]
#    return confidence

# Get confidence scores for all test samples
#confidences = np.array([prediction_confidence(p) for p in probabilities])

#print(f"Average confidence: {confidences.mean():.4f}")
#print(f"Confidence for sample: {confidences[sample_idx]:.4f}")

# Find high-confidence and low-confidence predictions
#high_conf_idx = np.argmax(confidences)
#low_conf_idx = np.argmin(confidences)
#
#print(f"Highest confidence ({confidences[high_conf_idx]:.4f}) prediction: {np.argmax(probabilities[high_conf_idx])}")
#print(f"Lowest confidence ({confidences[low_conf_idx]:.4f}) prediction: {np.argmax(probabilities[low_conf_idx])}")