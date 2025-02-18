#Get a list of all riders who raced in 2024.

race_db_2024 = load_year_path(year_dir_path='~/cycling_data/scraped_data/2024')
wt_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.wt.races if isinstance(race.results, list) for rider_res_dict in race.results}
pro_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.pro.races if isinstance(race.results,list) for rider_res_dict in race.results}
d1_riders = {rider_res_dict.get('rider_id', None) for race in race_db_2024.d1.races if isinstance(race.results,list) for rider_res_dict in race.results}
riders_2024 = wt_riders.union(pro_riders).union(d1_riders)

#Create the full RaceCharDB 
race_char_db = RaceCharDB(year_range=range(2010,2025))


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