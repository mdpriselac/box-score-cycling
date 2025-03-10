from mord import LogisticAT
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_sample_weight
import tqdm
import joblib
from sklearn.utils import gen_batches
from scipy.optimize import minimize
import numpy as np
from sklearn.metrics import mean_absolute_error, cohen_kappa_score
import sys

gc_cols_to_drop = ['one_day_total_time', 'one_day_abandon_proportion','one_day_biggest_group', 'one_day_shattered', 'one_day_clumpiness','rider_id', 'rider_name','race_type']
one_day_cols_to_drop = ['gc_total_time', 'gc_abandon_proportion','gc_biggest_group', 'gc_shattered', 'gc_clumpiness','rider_id', 'rider_name','race_type']
stage_cols_to_drop = ['gc_total_time', 'gc_abandon_proportion','gc_biggest_group', 'gc_shattered', 'gc_clumpiness','rider_id', 'rider_name','race_type']
bucket_cols_to_drop = ['bucket_0', 'bucket_1', 'bucket_2', 'bucket_3', 'bucket_4', 'bucket_5','bucket_6', 'bucket_7']



# Define batch training function
def train_model_with_batches(model, X, y, sample_weight=None, batch_size=512, max_iter=100, pbar=None):
    """
    Train LogisticAT model in batches with progress bar updates
    """
    n_samples = X.shape[0]
    n_batches = int(np.ceil(n_samples / batch_size))
    
    # Initialize model parameters if not already initialized
    if not hasattr(model, 'coef_'):
        model.coef_ = np.zeros((1, X.shape[1]))
        model.theta_ = np.zeros(int(y.max()))
    
    # Setup progress tracking
    total_steps = max_iter * n_batches
    completed_steps = 0
    
    for epoch in range(max_iter):
        # Shuffle data for each epoch
        indices = np.random.permutation(n_samples)
        X_shuffled = X.iloc[indices] if hasattr(X, 'iloc') else X[indices]
        y_shuffled = y.iloc[indices] if hasattr(y, 'iloc') else y[indices]
        
        if sample_weight is not None:
            sw_shuffled = sample_weight[indices]
        else:
            sw_shuffled = None
        
        # Process each batch
        for batch_idx in gen_batches(n_samples, batch_size):
            X_batch = X_shuffled.iloc[batch_idx] if hasattr(X_shuffled, 'iloc') else X_shuffled[batch_idx]
            y_batch = y_shuffled.iloc[batch_idx] if hasattr(y_shuffled, 'iloc') else y_shuffled[batch_idx]
            
            if sw_shuffled is not None:
                sw_batch = sw_shuffled[batch_idx]
            else:
                sw_batch = None
            
            # Update model on this batch
            try:
                model.fit(X_batch, y_batch, sample_weight=sw_batch)
            except Exception as e:
                print(f"Error in batch training: {e}")
                continue
                
            # Update progress
            completed_steps += 1
            if pbar:
                progress = int((completed_steps / total_steps) * 100)
                pbar.update(progress - pbar.n)  # Update to current progress
    
    return model



#load the full dataset
df = pd.read_parquet('all_coef_pop_model_data.parquet')

full_column_list = ['rider_id', 'rider_name', 'rider_age', 'actual_place_bucketed',
       'bucket_0', 'bucket_1', 'bucket_2', 'bucket_3', 'bucket_4', 'bucket_5',
       'bucket_6', 'bucket_7', 'wt_proportion', 'pro_proportion',
       'd1_proportion', 'gc_total_time', 'gc_abandon_proportion',
       'gc_biggest_group', 'gc_shattered', 'gc_clumpiness',
       'one_day_total_time', 'one_day_abandon_proportion',
       'one_day_biggest_group', 'one_day_shattered', 'one_day_clumpiness',
       'stage_total_time', 'stage_abandon_proportion', 'stage_biggest_group',
       'stage_shattered', 'stage_clumpiness', 'tour_encoded', 'race_type',
       'total_time', 'abandon_proportion', 'biggest_group', 'shattered',
       'clumpiness']

def train_gc_model():
       #Let's train a GC prediction model.
       # We only want to train on races where the race_type is 'gc'
       gc_df = df[df['race_type']=='gc'].copy()
       #Next, let's drop one day columns
       gc_df = gc_df.drop(columns=['one_day_total_time', 'one_day_abandon_proportion','one_day_biggest_group', 'one_day_shattered', 'one_day_clumpiness','bucket_0', 'bucket_1', 'bucket_2', 'bucket_3', 'bucket_4', 'bucket_5','bucket_6', 'bucket_7']).copy()
       #Let's try by keeping the stage columns in since stage performance (ie better on shattered) is likely to be relevant
       #next let's normalize the age column by dividing by 40
       gc_df['rider_age'] = gc_df['rider_age'] / 45
       #Next let's drop the rider_id, rider_name columns, and the race_type column
       gc_df = gc_df.drop(columns=['rider_id', 'rider_name','race_type']).copy()
       #Now we have a full X and y set up. y = 'actual_place_bucketed' and X = all other columns
       gc_X = gc_df.drop(columns=['actual_place_bucketed'])
       gc_y = gc_df['actual_place_bucketed']
       #Next let's split the data into a train and test set
       gc_X_train, gc_X_test, gc_y_train, gc_y_test = train_test_split(gc_X, gc_y, test_size=0.15, random_state=173, stratify=gc_y)
       #Next let's compute the sample weights
       gc_weights_train = compute_sample_weight('balanced', gc_y_train)
       gc_weights_test = compute_sample_weight('balanced', gc_y_test)
       #Next let's train the model
       print("Training GC Model...")
       with tqdm.tqdm(total=100, desc="Training Progress") as pbar:
              model = LogisticAT()
              train_model_with_batches(
                     model, 
                     gc_X_train, 
                     gc_y_train, 
                     sample_weight=gc_weights_train, 
                     batch_size=2048,  # Adjust batch size as needed
                     max_iter=10,     # Adjust number of epochs as needed
                     pbar=pbar
              )
       #save the model with joblib
       joblib.dump(model, './cycling_project/models/race_chars_only/gc.pkl')
       #test the model 
       # Get predictions
       y_pred = model.predict(gc_X_test)

       # Calculate raw MAE (lower is better)
       mae = mean_absolute_error(gc_y_test, y_pred,sample_weight=gc_weights_test)
       print(f"Mean Absolute Error: {mae:.4f}")

       # Calculate Cohen's Kappa (measures agreement, higher is better)
       kappa = cohen_kappa_score(gc_y_test, y_pred, weights='quadratic',sample_weight=gc_weights_test)
       print(f"Quadratic Weighted Kappa: {kappa:.4f}")

       # Calculate accuracy (exact matches)
       accuracy = (y_pred == gc_y_test).mean()
       print(f"Accuracy: {accuracy:.4f}")

       # Calculate within-one accuracy (predictions within ±1 class)
       within_one = (abs(y_pred - gc_y_test) <= 1).mean()
       print(f"Within-One Accuracy: {within_one:.4f}")


def train_one_day_model():
       #Next let's train a one_day model
       one_day_df = df[df['race_type']=='one_day'].copy()
       #Next, let's drop one day columns
       one_day_df = one_day_df.drop(columns=['gc_total_time', 'gc_abandon_proportion','gc_biggest_group', 'gc_shattered', 'gc_clumpiness','bucket_0', 'bucket_1', 'bucket_2', 'bucket_3', 'bucket_4', 'bucket_5','bucket_6', 'bucket_7']).copy()
       #Let's try by keeping the stage columns in since stage performance (ie better on shattered) is likely to be relevant
       #next let's normalize the age column by dividing by 40
       one_day_df['rider_age'] = one_day_df['rider_age'] / 45
       #Next let's drop the rider_id, rider_name columns, and the race_type column
       one_day_df = one_day_df.drop(columns=['rider_id', 'rider_name','race_type']).copy()
       #Now we have a full X and y set up. y = 'actual_place_bucketed' and X = all other columns
       one_day_X = one_day_df.drop(columns=['actual_place_bucketed'])
       one_day_y = one_day_df['actual_place_bucketed']
       #Next let's split the data into a train and test set
       one_day_X_train, one_day_X_test, one_day_y_train, one_day_y_test = train_test_split(one_day_X, one_day_y, test_size=0.15, random_state=173, stratify=one_day_y)
       #Next let's compute the sample weights
       one_day_weights_train = compute_sample_weight('balanced', one_day_y_train)
       one_day_weights_test = compute_sample_weight('balanced', one_day_y_test)
       #Next let's train the model
       print("Training one_day Model...")
       with tqdm.tqdm(total=100, desc="Training Progress") as pbar:
              model = LogisticAT()
              train_model_with_batches(
                     model, 
                     one_day_X_train, 
                     one_day_y_train, 
                     sample_weight=one_day_weights_train, 
                     batch_size=2048,  # Adjust batch size as needed
                     max_iter=10,     # Adjust number of epochs as needed
                     pbar=pbar
              )
              #save the model with joblib
       joblib.dump(model, './cycling_project/models/race_chars_only/one_day.pkl')
       #test the model 
       # Get predictions
       y_pred = model.predict(one_day_X_test)

       # Calculate raw MAE (lower is better)
       mae = mean_absolute_error(one_day_y_test, y_pred,sample_weight=one_day_weights_test)
       print(f"Mean Absolute Error: {mae:.4f}")

       # Calculate Cohen's Kappa (measures agreement, higher is better)
       kappa = cohen_kappa_score(one_day_y_test, y_pred, weights='quadratic',sample_weight=one_day_weights_test)
       print(f"Quadratic Weighted Kappa: {kappa:.4f}")

       # Calculate accuracy (exact matches)
       accuracy = (y_pred == one_day_y_test).mean()
       print(f"Accuracy: {accuracy:.4f}")

       # Calculate within-one accuracy (predictions within ±1 class)
       within_one = (abs(y_pred - one_day_y_test) <= 1).mean()
       print(f"Within-One Accuracy: {within_one:.4f}")

def train_stage_model():
       #Next let's train a stage model
       stage_df = df[df['race_type']=='stage'].copy()
       #Next, let's drop one day columns
       stage_df = stage_df.drop(columns=['gc_total_time', 'gc_abandon_proportion','gc_biggest_group', 'gc_shattered', 'gc_clumpiness','bucket_0', 'bucket_1', 'bucket_2', 'bucket_3', 'bucket_4', 'bucket_5','bucket_6', 'bucket_7']).copy()
       #Let's try by keeping the stage columns in since stage performance (ie better on shattered) is likely to be relevant
       #next let's normalize the age column by dividing by 45
       stage_df['rider_age'] = stage_df['rider_age'] / 45
       #Next let's drop the rider_id, rider_name columns, and the race_type column
       stage_df = stage_df.drop(columns=['rider_id', 'rider_name','race_type']).copy()
       #Now we have a full X and y set up. y = 'actual_place_bucketed' and X = all other columns
       stage_X = stage_df.drop(columns=['actual_place_bucketed'])
       stage_y = stage_df['actual_place_bucketed']
       #Next let's split the data into a train and test set
       stage_X_train, stage_X_test, stage_y_train, stage_y_test = train_test_split(stage_X, stage_y, test_size=0.15, random_state=173, stratify=stage_y)
       #Next let's compute the sample weights
       stage_weights_train = compute_sample_weight('balanced', stage_y_train)
       stage_weights_test = compute_sample_weight('balanced', stage_y_test)
       #Next let's train the model
       print("Training stage Model...")
       with tqdm.tqdm(total=100, desc="Training Progress") as pbar:
              model = LogisticAT()
              train_model_with_batches(
                     model, 
                     stage_X_train, 
                     stage_y_train, 
                     sample_weight=stage_weights_train, 
                     batch_size=2048,  # Adjust batch size as needed
                     max_iter=10,     # Adjust number of epochs as needed
                     pbar=pbar
              )
              #save the model with joblib
       joblib.dump(model, './cycling_project/models/race_chars_only/stage.pkl')
       #test the model 
       # Get predictions
       y_pred = model.predict(stage_X_test)

       # Calculate raw MAE (lower is better)
       mae = mean_absolute_error(stage_y_test, y_pred,sample_weight=stage_weights_test)
       print(f"Mean Absolute Error: {mae:.4f}")

       # Calculate Cohen's Kappa (measures agreement, higher is better)
       kappa = cohen_kappa_score(stage_y_test, y_pred, weights='quadratic',sample_weight=stage_weights_test)
       print(f"Quadratic Weighted Kappa: {kappa:.4f}")

       # Calculate accuracy (exact matches)
       accuracy = (y_pred == stage_y_test).mean()
       print(f"Accuracy: {accuracy:.4f}")

       # Calculate within-one accuracy (predictions within ±1 class)
       within_one = (abs(y_pred - stage_y_test) <= 1).mean()
       print(f"Within-One Accuracy: {within_one:.4f}")

if __name__ == "__main__":
       if len(sys.argv) < 2:
              print("Trainign all three models...")
              train_gc_model()
              train_one_day_model()
              train_stage_model()
       elif sys.argv[1] == 'gc':
              train_gc_model()
       elif sys.argv[1] == 'one_day':
              train_one_day_model()
       elif sys.argv[1] == 'stage':
              train_stage_model()
       