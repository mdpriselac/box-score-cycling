#The main thing is to skip races that have no results or no times.
#If no results -> skip

# We want to create a database for riders so that we can for any given point, create a history up to that point.

# Let's write a function to create a rider database by cycling through races.

# Get a race, if it doesn't have

from dataclasses import dataclass
from typing import Dict,List,Optional,Union
from dataclasses import field
from datetime import datetime

from dotenv import load_dotenv
import os

from cycling_project.webscrape_tools.create_race_data import Stage, Race
from cycling_project.data_loading_tools.load_scraped_data import FCCyclingTour,FCCyclingYear,load_year_path

load_dotenv(dotenv_path='../../env')
DB_PATH = os.getenv("DB_PATH")

@dataclass
class RiderResult:
    race_type: str
    race_tour: str
    race_name: str
    race_fc_id: int
    place: Union[int,str]
    time_gap: Union[float,str]
    race_year: Optional[int] = None
    team: Optional[str] = None
    team_id: Optional[int] = None
    team_number: Optional[int] = None
    personal_number: Optional[int] = None
    age: Optional[int] = None
    raw_bib_number: Optional[str] = None
    race_date: Optional[str] = None
    
    def __post_init__(self):
        if self.place == '':
            self.place = None
        if self.time_gap == '':
            self.time_gap = None
        if isinstance(self.place,str):
            try:
                self.place = int(self.place)
            except:
                pass
        if isinstance(self.time_gap,str):
            try:
                self.time_gap = float(self.time_gap)
            except:
                pass
        #make sure teh bib number is a string
        if isinstance(self.raw_bib_number,int):
            #convert to string
            self.raw_bib_number = str(self.raw_bib_number)
        #set the team and personal numbers based on the length of the raw bib number
        if isinstance(self.raw_bib_number,str):
            if len(self.raw_bib_number) == 1:
                self.team_number = 0
                self.personal_number = int(self.raw_bib_number)
            elif len(self.raw_bib_number) == 2:
                self.team_number = int(self.raw_bib_number[0])
                self.personal_number = int(self.raw_bib_number[1])
            elif len(self.raw_bib_number) == 3:
                self.team_number = int(self.raw_bib_number[0:-1])
                self.personal_number = int(self.raw_bib_number[-1])
    

@dataclass
class RiderCareer:
    fc_rider_id: int
    name: str
    team_history: Dict[int,tuple] = field(default_factory=dict)
    race_history: Dict[int,List[RiderResult]] = field(default_factory=dict)
    career_start: Optional[int] = field(default=None)
    career_end: Optional[int] = field(default=None)
    dob: Optional[str] = field(default=None)
    
    def get_age(self,year:int):
        if self.dob is not None:
            return year - int(self.dob)
        else:
            return None

    def add_race_result(self,race:Union[Race,Stage],result:dict):
        #let's use the result dict and the race information to create a RiderResult object and add it.
        
        place = result.get('place',None)
        gap = result.get('gap',None)
        team = result.get('team',None)
        team_id = result.get('team_id',None)
        raw_bib_number = result.get('bib_number',None)
        race_year = race.year
        race_date = race.date
        age = self.get_age(race_year)
        tour = race.category
        if isinstance(race,Stage):
            if 'gc' in race.name.lower():
                type = 'gc'
            else:
                type = 'stage'
            race_name = f"{race.race}, {race.name}"
            
        elif isinstance(race,Race):
            if not race.stage_race:
                type = 'one_day'
            race_name = race.name
        else:
            #We won't append just the full race object to the race history as that is either captured as a gc result or a stage for non one day races.
            return None
        #if we've got to here then we have a valid competition, let's create the result object and append it
        
        res = RiderResult(race_type=type,
                          race_tour=tour,
                          race_name=race_name,
                          race_year=race_year,
                          race_date=race_date,
                          race_fc_id=race.fc_race_id,
                          place=place,
                          time_gap=gap,
                          team=team,
                          team_id=team_id,
                          age=age,
                          raw_bib_number=raw_bib_number)
        #Check if the year has been added to the race and team history
        #If not, add the year. 
        if race_year not in self.race_history.keys():
            self.race_history[race_year] = []
        #If the team hasn't been added for the year, add the team
        if race_year not in self.team_history.keys():
            self.team_history[race_year] = (team_id, team)
        #add the race to the race history for the year.
        self.race_history[race_year].append(res)

        return None
    
    def generate_race_history(self,prior_to_year:int=None,race_type:str|list=None,tour_type:str|list=None,prior_to_date:str=None)->List[RiderResult]:
        """Create a race history for the rider up to a given year. If no year is given, will return career history with filters.
        Can filter for race_type (gc, stage, one_day) and tour_type (wt, pro, d1) as well.
        Args:
            prior_to_year (int): Year to generate history up to. If None, will return full career history length
            race_type (str|list): The type of race result to filter for. Can be 'gc', 'stage', 'one_day' or a list of these. If none, will get all.
            tour_type (str|list): The type of tour to filter for. Can be 'wt', 'pro', 'd1' or a list of these. If none, will get all.
            prior_to_date (str): Date in YYYY-MM-DD format to filter results to before this date.
        Returns:
            List[RiderResult]: List of RiderResult objects that match the filters.
        """
        
        if prior_to_year is None and prior_to_date is None and race_type is None and tour_type is None:
            return self.race_history

        race_history = []
        
        if isinstance(race_type,str):
            race_type_filter = [race_type]
        elif isinstance(race_type,list):
            race_type_filter = race_type
        else:
            race_type_filter = ['gc','stage','one_day']
            
        if isinstance(tour_type,str):
            tour_filter = [tour_type]
        elif isinstance(tour_type,list):
            tour_filter = tour_type
        else:
            tour_filter = ['wt','pro','d1']
        
        if prior_to_year is None:
            prior_to_year = max(self.race_history.keys())+1

        #implement a prior to date filter
        if isinstance(prior_to_date,str):
            #print("Filtering by prior to date")
            try:
                prior_to_dto = datetime.strptime(prior_to_date,'%Y-%m-%d')
            except:
                #print("Error converting prior_to_date to datetime object, make sure it is formatted as a string YYYY-MM-DD")
                return None
            for year in range(self.career_start,prior_to_dto.year + 1):
                raw_year_history = self.race_history.get(year,None)
                if raw_year_history is not None:
                    for result in raw_year_history:
                        #get the datetime object for the date
                        try:
                            result_race_date = datetime.strptime(result.race_date,'%Y-%m-%d')
                        except:
                            #print(f"Error converting {result.race_name} date to datetime object")
                            continue
                        if result_race_date < prior_to_dto and result.race_type in race_type_filter and result.race_tour in tour_filter:
                            race_history.append(result)
            return race_history
            
        #If there's no prior_to_date, cycle through the years up to the prior_to_year and append the results that match the filters
        for year in range(self.career_start,prior_to_year):
            #print('No prior to date filter, just getting years')
            raw_year_history = self.race_history.get(year,None)
        
            if raw_year_history is not None:
                race_history.extend([result for result in raw_year_history if result.race_type in race_type_filter and result.race_tour in tour_filter])
        
        return race_history


@dataclass
class RiderDB:
    riders: Dict[int,RiderCareer] = field(default_factory=dict)
    
    def add_rider_result(self,race:Union[Stage,Race],result_dict:dict):
        #get the int race year
        race_year = int(race.year)
        #get the rider id
        rider_id = result_dict.get('rider_id',None)
        if rider_id is None:
            #print("No rider id in result dict")
            return None
        #check for a rider object
        rider_id = int(rider_id)
        rider = self.riders.get(rider_id,None)
        #if there is no rider object, create one. After we create one we'll check all the rider information that can be added from a result but shouldn't change.
        if rider is None:
            name = result_dict.get('name',None)
            rider = RiderCareer(fc_rider_id=rider_id,name=name)
            
        #check if there's a dob in the result_dict. if there is, see if it matches the dob in the rider object. If not, update the rider object.
        res_dob = result_dict.get('dob',None)
        if res_dob is not None:
            if rider.dob is None:
                rider.dob = res_dob
            elif rider.dob != res_dob:
                #print(f"DOB mismatch for rider {rider.name}. Rider DOB: {rider.dob}, Result DOB: {res_dob}, updating rider to new DOB")
                rider.dob = res_dob
        
        #Check if there's a career_start in the rider object. If there, check the race.year. If the race.year is less than the career_start in the rider object, update the career start to the race_year
        if rider.career_start is not None:
            if race_year < int(rider.career_start):
                rider.career_start = race_year
        elif rider.career_start is None:
            rider.career_start = race_year
        
        #Check if there's a team_history in the rider object. If not, create a dictionary with the race.year as the key and (team_id, team_name) as the value
        if rider.team_history is None:
            rider.team_history = {race_year:(result_dict.get('team_id',None),result_dict.get('team',None))}
        else:
            rider.team_history[race_year] = (result_dict.get('team_id',None),result_dict.get('team',None))
        
        #Use the .add_race method to add the race result to the rider object
        rider.add_race_result(race=race,result=result_dict)
        #Update the rider object in the rider database
        self.riders[rider_id] = rider
    
    def get_rider_by_id(self,rider_id:int)->RiderCareer:
        """Get a rider by their id. If the rider is not in the database, raise a ValueError
        Args:
            rider_id (int): The rider id to get.
        Raises:
            ValueError: If the rider is not in the database.
        Returns:
            RiderCareer: The rider object.
        """
        rider = self.riders.get(rider_id,None)
        if rider is None:
            raise ValueError(f"Rider {rider_id} not found in database")
        return rider

    def add_tour(self,tour:FCCyclingTour):
        #cycle through
        for race in tour.races:
            if not race.stage_race:
                if race.results is None:
                    print(f"No results for {race.name}")
                    continue
                for result in race.results:
                    try:
                        self.add_rider_result(race=race,result_dict=result)
                    except:
                        print(f"Error adding result for {race.name}")
            else:
                for stage in race.stages:
                    if stage.results is None:
                        print(f"No results for {race.name}, {stage.name}")
                        continue
                    for result in stage.results:
                        try:
                            self.add_rider_result(race=stage,result_dict=result)
                        except:
                            print(f"Error adding result for {race.name}, {stage.name}")
    
    def add_year(self,year:FCCyclingYear):
        self.add_tour(year.wt)
        self.add_tour(year.pro)
        self.add_tour(year.d1)
    
    

def create_rider_db(db_path:str = DB_PATH)->RiderDB:
    """Create a RiderDB object from a db_path. Defaults to the environmetnal variable DB_PATH
    Args:
        db_path (str, optional): The path to the db. Defaults to DB_PATH.
    Returns:
        RiderDB: A RiderDB object
        """
    #Create a RiderDB object
    rider_db = RiderDB()
    #Get a list of the year directories in the db_path
    year_dirs = [f for f in os.listdir(db_path) if os.path.isdir(os.path.join(db_path,f)) and len(f)==4]
    #For each year directory, load the db, add it to the rider_db
    for year_dir in year_dirs:
        year_path = os.path.join(db_path,year_dir)
        year_db = load_year_path(year_path)
        rider_db.add_year(year_db)
    
    return rider_db