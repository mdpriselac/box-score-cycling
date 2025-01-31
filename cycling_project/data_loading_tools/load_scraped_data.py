import os
import pickle
import json
from typing import Optional,List
from dataclasses import dataclass,asdict
from cycling_project.webscrape_tools.create_race_data import Race, Stage
import re
from dotenv import load_dotenv

load_dotenv(dotenv_path='../env')
DB_PATH = os.getenv("DB_PATH")
TOURS = ['wt','pro','d1']

@dataclass
class FCCyclingTour:
    name:str
    races:List[Race]
    stage_races:Optional[List[Race]] = None
    one_days:Optional[List[Race]] = None
    stages:Optional[List[Stage]] = None
    
    def add_race_attrs(self, race: Race):
        for race in self.races:
            att = f"r{race.fc_race_id}"
            setattr(self, att, race)
            
    def extract_stage_races(self):
        self.stage_races = [r for r in self.races if r.stage_race == True]
        
    def extract_one_days(self):
        self.one_days = [r for r in self.races if r.stage_race == False]
        
    def extract_stages(self):
        if self.stages is None:
            self.extract_stage_races()
        self.stages = []
        for race in self.stage_races:
            for stage in race.stages:
                if stage.race is None or stage.race.strip() =='':
                    stage.race = race.name
                    stage.category = race.category
                    stage.fc_race_id = race.fc_race_id
                    if race.year is None:
                        stage.year = int(re.search(r'&y=(\d+)', race.url).group(1))
                    else:
                        stage.year = race.year
                self.stages.append(stage)
            
    def __post_init__(self):
        #extract stage races
        self.extract_stage_races()
        #extract one days
        self.extract_one_days()
        #extract stages
        self.extract_stages()
        for race in self.races:
            att = f"r{race.fc_race_id}"
            setattr(self, att, race)
    


@dataclass
class FCCyclingYear:
    year:str
    wt:FCCyclingTour
    pro:FCCyclingTour
    d1:FCCyclingTour
    
    def export_jsons(self,db_base_path:str):
        #create the year directory if it doesn't exist
        year_dir = os.path.join(db_base_path,self.year)
        if not os.path.exists(year_dir):
            os.makedirs(year_dir)
        #create the wt directory if it doesn't exist
        wt_dir = os.path.join(year_dir,'wt')
        if not os.path.exists(wt_dir):
            os.makedirs(wt_dir)
        #export each race in the wt tour to a json file with the race object name as the file_name.json
        for race in self.wt.races:
            with open(os.path.join(wt_dir,f"{race.name}.json"),'w') as f:
                #create the json string from the race object. The race object is a dataclass. use the built in 
                #asdict method to convert to a dictionary, convert to string, write to file
                json.dump(asdict(race),f,indent=4)
                
        #create the pro directory if it doesn't exist
        pro_dir = os.path.join(year_dir,'pro')
        if not os.path.exists(pro_dir):
            os.makedirs(pro_dir)
        #export each race in the pro tour
        for race in self.pro.races:
            with open(os.path.join(pro_dir,f"{race.name}.json"),'w') as f:
                json.dump(asdict(race),f,indent=4)
        #create the d1 directory if it doesn't exist
        d1_dir = os.path.join(year_dir,'d1')
        if not os.path.exists(d1_dir):
            os.makedirs(d1_dir)
        #export each race in the d1 tour
        for race in self.d1.races:
            with open(os.path.join(d1_dir,f"{race.name}.json"),'w') as f:
                json.dump(asdict(race),f,indent=4)
                
@dataclass
class FCCyclingDB:
    years:List[FCCyclingYear]

    def __post_init__(self):
        for year in self.years:
            y = f"y{year.year}"
            setattr(self, y, year)
        self._ensure_year_attributes()

    def add_year(self, year: FCCyclingYear):
        self.years.append(year)
        y = f"y{year.year}"
        setattr(self, y, year)
        self._ensure_year_attributes()

    def _ensure_year_attributes(self):
        for year in self.years:
            if not hasattr(self, year.year):
                y = f"y{year.year}"
                setattr(self, y, year)



def load_tour_path(tour_dir_path:str)->list:
    """Given a tour directory, load all races in that tour from that year.
    Args:
        tour_dir_path: the path to the tour directory
    Returns:
        list of Race objects in that tour directory from that year."""
    #load the race files in the tour directory, these will be the .pkl files
    race_files = [f for f in os.listdir(tour_dir_path) if f.endswith('.pkl')]
    race_objects = []
    #loop through race files, load objects, and append
    for file in race_files:
        with open(os.path.join(tour_dir_path,file), 'rb') as f:
            r_o = pickle.load(f)
            r_o.category = tour_dir_path.split('/')[-1]
            if r_o.stage_race:
                for stage in r_o.stages:
                    stage.category = r_o.category
            race_objects.append(r_o)
    print(f"Loaded {tour_dir_path}")
    
    return FCCyclingTour(name=tour_dir_path.split('/')[-1],races=race_objects)

def load_year_path(year_dir_path:str)->dict:
    """Given a year directory, load all tours in that year.
    Args:
        year_dir_path: the path to the year directory
    Returns:
        a dictionary of tour names each of which has a list of races in that year and tour."""
    #load the tour directories in the year directory
    
    year_db = FCCyclingYear(year=year_dir_path.split('/')[-1],wt=None,pro=None,d1=None)
    #load wt first
    wt_dir = os.path.join(year_dir_path, 'wt')
    year_db.wt = load_tour_path(wt_dir)
    #load pro next, but add check to make sure that the race is not already in the wt list
    pro_dir = os.path.join(year_dir_path, 'pro')
    year_db.pro = load_tour_path(pro_dir)
    wt_race_names = [r.name for r in year_db.wt.races]
    clean_pro_races = [r for r in year_db.pro.races if r.name not in wt_race_names]
    year_db.pro.races = clean_pro_races
    #load d1, but check to make sure that the race is not already in the wt or pro lists
    d1_dir = os.path.join(year_dir_path, 'd1')
    year_db.d1 = load_tour_path(d1_dir)
    pro_race_names = [r.name for r in year_db.pro.races]
    wt_pro_races = wt_race_names + pro_race_names
    clean_d1_races = [r for r in year_db.d1.races if r.name not in wt_pro_races]
    year_db.d1.races = clean_d1_races
    
    return year_db

def load_db(db_path:str=DB_PATH)->dict:
    """Given a db path, load all years in that db.
    Args:
        db_path: the path to the db directory
    Returns:
        a dictionary of years each of which has a dictionary of tour names each of which has a list of races in that year on that tour."""
    #load the year directories in the db directory
    year_dirs = [f for f in os.listdir(db_path) if os.path.isdir(os.path.join(db_path,f)) and len(f) == 4]
    db = FCCyclingDB(years=[])
    #load each year directory
    for year in year_dirs:
        year_path = os.path.join(db_path,year)
        db.add_year(load_year_path(year_path))
    return db
    

    
            