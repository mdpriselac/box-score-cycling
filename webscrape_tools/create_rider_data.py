#The main thing is to skip races that have no results or no times.
#If no results -> skip

# We want to create a database for riders so that we can for any given point, create a history up to that point.

# Let's write a function to create a rider database by cycling through races.

# Get a race, if it doesn't have

from dataclasses import dataclass
from typing import Dict,List,Optional,Union
from dataclasses import field

from webscrape_tools.create_race_data import Stage, Race


@dataclass
class RiderResult:
    race_type: str
    race_tour: str
    race_name: str
    race_fc_id: int
    place: Union[int,str]
    time_gap: Union[float,str]
    team: Optional[str] = None
    team_id: Optional[int] = None
    raw_number: Optional[int] = None
    team_number: Optional[int] = None
    personal_number: Optional[int] = None
    age: Optional[int] = None
    
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
        if isinstance(self.raw_number,int):
            #convert to string
            self.raw_number = str(self.raw_number)
        #set the team and personal numbers based on the length of the raw bib number
        if isinstance(self.raw_number,str):
            if len(self.raw_number) == 1:
                self.team_number = 0
                self.personal_number = int(self.raw_number)
            elif len(self.raw_number) == 2:
                self.team_number = int(self.raw_number[0])
                self.personal_number = int(self.raw_number[1])
            elif len(self.raw_number) == 3:
                self.team_number = int(self.raw_number[0:-1])
                self.personal_number = int(self.raw_number[-1])

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
        race_year = race.year
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
                          race_fc_id=race.fc_race_id,
                          place=place,
                          time_gap=gap,
                          team=team,
                          team_id=team_id,
                          age=age)
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
    
    def generate_full_history(self,prior_to_race_id:int,prior_to_race_year:int):
        #Generate a full rider history up to a year and 
        #For each race return race type (one day, stage, gc), race category (wt, pro, d1), team bib number (0-21), personal bib number(1-9), place, time gap
        return None
    
    def generate_year_history(self,year:int,prior_to_race:int):
        return None
    
    def generate_race_history(self,race_id:int,prior_to_year:int):
        return None


@dataclass
class RiderDB:
    riders: Dict[int,RiderCareer] = field(default_factory=dict)
    
    def add_rider_result(self,race:Union[Stage,Race],result_dict:dict):
        #get the int race year
        race_year = int(race.year)
        #get the rider id
        rider_id = result_dict.get('rider_id',None)
        if rider_id is None:
            print("No rider id in result dict")
            return None
        #check for a rider object
        rider_id = int(rider_id)
        rider = self.riders.get(rider_id,None)
        #if there is no rider object, create one
        if rider is None:
            name = result_dict.get('name',None)
            rider = RiderCareer(fc_rider_id=rider_id,name=name)
            
        #check if there's a dob in the result_dict. if there is, see if it matches the dob in the rider object. If not, update the rider object.
        res_dob = result_dict.get('dob',None)
        if res_dob is not None:
            if rider.dob is None:
                rider.dob = res_dob
            elif rider.dob != res_dob:
                print(f"DOB mismatch for rider {rider.name}. Rider DOB: {rider.dob}, Result DOB: {res_dob}, updating rider to new DOB")
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
        