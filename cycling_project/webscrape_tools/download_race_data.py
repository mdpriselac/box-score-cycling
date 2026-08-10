import os
from datetime import date, datetime, timedelta
from random import randint
from time import sleep
import pickle
from typing import List, Dict, Tuple, Optional
from dotenv import load_dotenv

from cycling_project.webscrape_tools.scrape_startlists import scrape_and_add_bib_numbers_to_race
from cycling_project.webscrape_tools.create_race_data import Race
from cycling_project.webscrape_tools.logging_config import get_logger
from cycling_project.webscrape_tools.find_races import DB_PATH

# Configure logger
logger = get_logger("download_race_data")

# Register the DB_PATH variable
logger.info(f"Database path: {DB_PATH}")

# Constants
TOURS = ['wt', 'pro', 'd1']
SLEEP_MIN = 3
SLEEP_MAX = 8

# How long after a race's last stage date missing results still mean "not
# posted yet" (keep re-scraping) rather than "never coming" (stage was
# cancelled). FirstCycling posts results same-day, so anything older than
# this without results — in a race that is otherwise over — is a cancelled
# stage, not lag. Shared by update_pipeline's incomplete-race check.
RESULTS_POSTING_GRACE_DAYS = 7


def _parse_race_date(raw_date) -> Optional[date]:
    """Normalize a race date to a date object, handling str/datetime/date."""
    if raw_date is None:
        return None
    if isinstance(raw_date, datetime):
        return raw_date.date()
    if isinstance(raw_date, date):
        return raw_date
    if isinstance(raw_date, str):
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            return None
    return None

def read_race_list(tour_folder_path: str) -> List[Tuple[str, str]]:
    """
    Reads the .txt file in a directory and returns a list of name,url tuples for races.
    
    Args:
        tour_folder_path: Path to a tour level folder within a year folder within a base race db folder
        
    Returns:
        A list of (race_name, race_url) tuples for races at that tour level in that year.
    """
    logger.debug(f"Reading race list from {tour_folder_path}")
    
    # Get the list of .txt files in the tour_folder_path
    txt_files = [f for f in os.listdir(tour_folder_path) if f.endswith('.txt')]
    if not txt_files:
        logger.warning(f"No txt files found in {tour_folder_path}")
        return []
        
    txt_file = txt_files[0]
    race_list = []
    
    # Read the txt_file line by line, splitting by comma
    file_path = os.path.join(tour_folder_path, txt_file)
    logger.debug(f"Processing race list file: {file_path}")
    
    try:
        with open(file_path, 'r') as file:
            for i, line in enumerate(file, 1):
                line_parts = line.strip().split(',')
                
                # Validate line format
                if len(line_parts) == 2:
                    name, url = line_parts
                    race_list.append((name, url))
                elif len(line_parts) < 2:
                    logger.error(f"Line {i} in {file_path} is missing either a name or a url: {line.strip()}")
                elif len(line_parts) > 2:
                    logger.error(f"Line {i} in {file_path} has extra commas: {line.strip()}")
    except Exception as e:
        logger.error(f"Error reading race list from {file_path}: {e}")
        
    logger.info(f"Found {len(race_list)} races in {tour_folder_path}")
    return race_list


def create_to_scrape_list_tour(tour_folder_path: str) -> List[Tuple[str, str]]:
    """
    Creates a list of races that still need to be scraped in a tour folder.

    Races are included if they have no .pkl file, or if they have a .pkl file
    with no results and the race date is recently past — within the
    results-posting grace (stale empty pkl). Result-less races older than the
    grace are settled/cancelled and are left alone.

    Args:
        tour_folder_path: Path to a tour level folder

    Returns:
        List of (race_name, race_url) tuples for races that need to be scraped
    """
    logger.debug(f"Creating to-scrape list for {tour_folder_path}")

    # Get all the races in the tour folder
    races_to_scrape = read_race_list(tour_folder_path)

    # Get a list of .pkl files in the tour folder
    try:
        scraped_races = [f for f in os.listdir(tour_folder_path) if f.endswith('.pkl')]
        scraped_race_names = set(f.split('.')[0] for f in scraped_races)

        # Check existing pkls for stale data (past races with no results)
        stale_names = set()
        for pkl_name in list(scraped_race_names):
            pkl_path = os.path.join(tour_folder_path, f"{pkl_name}.pkl")
            try:
                with open(pkl_path, "rb") as f:
                    race = pickle.load(f)
                is_stale = False
                if hasattr(race, 'stages') and race.stages:
                    # Stage race: stale if any stage is missing results and is
                    # not provably in the future — the in-progress shape
                    # (result-less stages either past-dated or undated;
                    # FirstCycling omits the date div on unraced stage pages),
                    # which re-scrapes every run until the race settles. A
                    # settled race never refetches: its result-less stages are
                    # legitimately empty (weather-cancelled), not pending.
                    # Settled means the final GC posted, OR every stage is
                    # dated with the last one more than the posting grace in
                    # the past — FirstCycling publishes no GC at all when a
                    # short race loses a stage (Vuelta a Murcia 2026). "Final
                    # GC" means a CLASSIFIED row — mid-race, race.results holds
                    # only the DNF board (place='DNF'), which doesn't count.
                    has_final_gc = any(
                        str(r.get('place', '')).strip().isdigit()
                        for r in (race.results or [])
                    )
                    stage_dates = [_parse_race_date(s.date) for s in race.stages]
                    concluded_past_grace = (
                        all(d is not None for d in stage_dates)
                        and max(stage_dates)
                        <= date.today() - timedelta(days=RESULTS_POSTING_GRACE_DAYS)
                    )
                    if not (has_final_gc or concluded_past_grace):
                        for stage in race.stages:
                            if getattr(stage, 'results', None):
                                continue
                            stage_date = _parse_race_date(stage.date)
                            if stage_date is None or stage_date <= date.today():
                                is_stale = True
                                break
                else:
                    # One-day race: stale if past date and no results — the
                    # "raced but results not posted yet" window, bounded by
                    # the posting grace like the stage-race arm. A result-less
                    # race further in the past was cancelled (FirstCycling
                    # never posts results for it: Duo Normand 2012–19), so
                    # marking it stale deleted + re-fetched it on every run
                    # over its folder. Keeping the pickle pins the original
                    # date — safe, because race lists carry no dates and the
                    # scraper no longer writes result-less pickles, so only
                    # legacy empties reach this arm; a rescheduled race would
                    # never have had one.
                    if not bool(race.results):
                        race_date = _parse_race_date(race.date)
                        cancelled_past_grace = race_date is not None and (
                            race_date
                            <= date.today() - timedelta(days=RESULTS_POSTING_GRACE_DAYS)
                        )
                        if (race_date and race_date <= date.today()
                                and not cancelled_past_grace):
                            is_stale = True

                if is_stale:
                    logger.info(f"Stale pkl found: {pkl_name} — will re-scrape")
                    os.remove(pkl_path)
                    stale_names.add(pkl_name)
            except Exception as e:
                logger.warning(f"Error checking pkl {pkl_name}: {e}")

        # Remove stale names from the exclusion set
        scraped_race_names -= stale_names

        # Return races that haven't been scraped yet (or were stale)
        to_scrape = [(race_name, url) for race_name, url in races_to_scrape
                     if race_name not in scraped_race_names]

        logger.info(f"{len(to_scrape)}/{len(races_to_scrape)} races need to be scraped in {tour_folder_path}")
        return to_scrape
    except Exception as e:
        logger.error(f"Error creating to-scrape list for {tour_folder_path}: {e}")
        return []


def read_year_db(year_folder_path: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Reads the year folder and returns a dictionary of tour levels with lists of races at that level in the year.
    
    Args:
        year_folder_path: Path to a year folder within a base race db folder
        
    Returns:
        A dictionary of tour levels with lists of races at that level in the year.
    """
    logger.debug(f"Reading year database from {year_folder_path}")
    
    # Create the tour paths by joining each tour name as a directory path to the year_folder_path
    tour_paths = [os.path.join(year_folder_path, tour) for tour in TOURS]
    
    # Create a dictionary to hold the tour data
    year_db = {}
    
    # Loop through tours and get a list of races for each tour
    for tour_path in tour_paths:
        if not os.path.exists(tour_path):
            logger.warning(f"Tour path does not exist: {tour_path}")
            continue
            
        tour_name = os.path.basename(tour_path)
        year_db[tour_name] = read_race_list(tour_path)
        
    logger.info(f"Read year database from {year_folder_path}, found tours: {list(year_db.keys())}")
    return year_db


def create_to_scrape_list_year(year_folder_path: str) -> Dict[str, List[Tuple[str, str]]]:
    """
    Reads the year folder and returns a dictionary of tour levels with lists of races remaining to scrape 
    in that year for each level.
    
    Args:
        year_folder_path: Path to a year folder
        
    Returns:
        A dictionary of tour levels each of which has a list of races to scrape for that tour level in that year.
    """
    logger.debug(f"Creating to-scrape list for year {year_folder_path}")
    
    # Create the tour paths by joining each tour name as a directory path to the year_folder_path
    tour_paths = [os.path.join(year_folder_path, tour) for tour in TOURS]
    
    # Create a dictionary to hold the tour data
    year_db = {}
    
    # Loop through tours and get a list of races to scrape for each tour
    for tour_path in tour_paths:
        if not os.path.exists(tour_path):
            logger.warning(f"Tour path does not exist: {tour_path}")
            continue
            
        tour_name = os.path.basename(tour_path)
        year_db[tour_name] = create_to_scrape_list_tour(tour_path)
        
    return year_db


def read_db(base_db_folder: str) -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
    """
    Reads the base db folder and returns a nested dictionary of years, tour levels, and races.
    
    Args:
        base_db_folder: Path to the base db folder
        
    Returns:
        A dictionary of years each of which has a dictionary of tour levels each of which has a list of races.
    """
    logger.info(f"Reading complete database from {base_db_folder}")
    
    # Get the list of year folders in the base_db_folder
    try:
        year_folders = [f for f in os.listdir(base_db_folder) 
                        if os.path.isdir(os.path.join(base_db_folder, f)) and len(f) == 4]
    except Exception as e:
        logger.error(f"Error listing year folders in {base_db_folder}: {e}")
        return {}
        
    # Create a dictionary to hold the year data
    db = {}
    
    # Loop through years and get a dictionary of tour levels
    for year_folder in year_folders:
        year_path = os.path.join(base_db_folder, year_folder)
        db[year_folder] = read_year_db(year_path)
        
    logger.info(f"Database read complete. Found {len(db)} years: {', '.join(sorted(db.keys()))}")
    return db


def create_to_scrape_list_db(base_db_folder: str) -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
    """
    Reads the base db folder and returns a nested dictionary of races that still need to be scraped.
    
    Args:
        base_db_folder: Path to the base db folder
        
    Returns:
        A dictionary of years each of which has a dictionary of tour levels each of which has 
        a list of races to be scraped in that year.
    """
    logger.info(f"Creating complete to-scrape list for database {base_db_folder}")
    
    # Get the list of year folders in the base_db_folder
    try:
        year_folders = [f for f in os.listdir(base_db_folder) 
                        if os.path.isdir(os.path.join(base_db_folder, f)) and len(f) == 4]
    except Exception as e:
        logger.error(f"Error listing year folders in {base_db_folder}: {e}")
        return {}
        
    # Create a dictionary to hold the year data
    db = {}
    
    # Loop through years and get a dictionary of tour levels
    for year_folder in year_folders:
        year_path = os.path.join(base_db_folder, year_folder)
        db[year_folder] = create_to_scrape_list_year(year_path)
        
    return db


def update_tour_folder(tour_folder_dir: str) -> None:
    """
    Given a tour folder directory, scrapes and saves any races that have not yet been scraped.
    
    Args:
        tour_folder_dir: Path to a tour folder within a year folder within a base race directory
        
    Returns:
        None, but will create and save race objects to a pkl file in the tour folder.
    """
    logger.info(f"Updating tour folder: {tour_folder_dir}")
    
    # Get a list of races to scrape in this tour folder
    to_scrape = create_to_scrape_list_tour(tour_folder_dir)
    
    if not to_scrape:
        logger.info(f"No races to scrape in {tour_folder_dir}")
        return None
        
    logger.info(f"Found {len(to_scrape)} races to scrape in {tour_folder_dir}")
    
    # Loop through the lists to scrape, create a race object, call populate_race on it, and save it as a pkl
    for i, (race_name, url) in enumerate(to_scrape, 1):
        logger.info(f"Scraping race {i}/{len(to_scrape)}: {race_name}")

        try:
            # Create and populate race object
            race_obj = Race(name=race_name, url=url)
            race_obj.populate_race()

            # Set the tour category for the race
            race_obj.category = os.path.basename(tour_folder_dir)
            logger.debug(f"Set race category to {race_obj.category}")

            # Skip future races — don't create empty pkls
            race_date = _parse_race_date(race_obj.date)
            if race_date and race_date > date.today():
                logger.info(f"Skipping {race_name} — race date {race_date} is in the future")
                continue

            # Skip races with no results (fallback for unparseable dates)
            has_results = bool(race_obj.results) or (
                race_obj.stages and any(getattr(s, 'results', None) for s in race_obj.stages)
            )
            if not has_results:
                logger.info(f"Skipping {race_name} — no results found")
                continue

            # Check for bib numbers
            try:
                logger.debug(f"Attempting to add bib numbers to {race_name}")
                race_obj_w_bib_check = scrape_and_add_bib_numbers_to_race(race=race_obj)
            except Exception as e:
                logger.warning(f"Error adding bib numbers to {race_name}: {e}")
                race_obj_w_bib_check = race_obj

            # Save the race_obj as a pickle in this tour folder
            output_path = os.path.join(tour_folder_dir, f"{race_name}.pkl")
            with open(output_path, 'wb') as f:
                pickle.dump(race_obj_w_bib_check, f)

            logger.info(f"Successfully saved {race_name} to {output_path}")

            # Sleep to avoid overwhelming the server
            sleep_time = randint(SLEEP_MIN, SLEEP_MAX)
            logger.debug(f"Sleeping for {sleep_time} seconds before next race")
            sleep(sleep_time)

        except Exception as e:
            logger.error(f"Error processing race {race_name}: {e}")
            
    logger.info(f"Completed updating tour folder: {tour_folder_dir}")
    return None


def remove_duplicates_across_tours(year_folder_dir: str) -> None:
    """
    Given a year folder directory, removes any duplicate races that are in multiple tours. 
    Defaults to keeping the race in a higher tour.
    
    Args:
        year_folder_dir: Path to a year folder
        
    Returns:
        None, but will remove duplicates from pro and d1 if they appear in a higher list
    """
    logger.info(f"Removing duplicate races across tours in {year_folder_dir}")
    
    try:
        # Get the wt race names from the txt file in the wt folder
        wt_dir = os.path.join(year_folder_dir, 'wt')
        if not os.path.exists(wt_dir):
            logger.warning(f"WT directory does not exist: {wt_dir}")
            return None
            
        wt_txt_files = [f for f in os.listdir(wt_dir) if f.endswith('.txt')]
        if not wt_txt_files:
            logger.warning(f"No txt files found in WT directory: {wt_dir}")
            return None
            
        wt_race_file = wt_txt_files[0]
        wt_race_names = []
        
        with open(os.path.join(wt_dir, wt_race_file), 'r') as f:
            for line in f:
                line = line.strip().split(',')
                if len(line) >= 1:
                    race_name = line[0]
                    wt_race_names.append(race_name)
        
        logger.info(f"Found {len(wt_race_names)} races in WT")
        
        # Rewrite pro text file to remove duplicates that are in the wt list
        pro_dir = os.path.join(year_folder_dir, 'pro')
        if not os.path.exists(pro_dir):
            logger.warning(f"Pro directory does not exist: {pro_dir}")
        else:
            pro_txt_files = [f for f in os.listdir(pro_dir) if f.endswith('.txt')]
            if not pro_txt_files:
                logger.warning(f"No txt files found in Pro directory: {pro_dir}")
            else:
                pro_text_file = pro_txt_files[0]
                
                # Read in the pro text file
                pro_races = []
                with open(os.path.join(pro_dir, pro_text_file), 'r') as f:
                    for line in f:
                        line_parts = line.strip().split(',')
                        if len(line_parts) >= 2:
                            pro_races.append(line_parts[:2])
                
                pro_race_names = [race_name for race_name, url in pro_races]
                clean_pro_races = [(race_name, url) for race_name, url in pro_races 
                                   if race_name not in wt_race_names]
                
                # Count duplicates removed
                duplicates_removed = len(pro_races) - len(clean_pro_races)
                logger.info(f"Removing {duplicates_removed} duplicate races from Pro list")
                
                # Rewrite the pro text file
                with open(os.path.join(pro_dir, pro_text_file), 'w') as f:
                    for race_name, url in clean_pro_races:
                        f.write(f"{race_name},{url}\n")
        
        # Rewrite d1 text file to remove duplicates that are in the wt or pro list
        d1_dir = os.path.join(year_folder_dir, 'd1')
        if not os.path.exists(d1_dir):
            logger.warning(f"D1 directory does not exist: {d1_dir}")
        else:
            d1_txt_files = [f for f in os.listdir(d1_dir) if f.endswith('.txt')]
            if not d1_txt_files:
                logger.warning(f"No txt files found in D1 directory: {d1_dir}")
            else:
                d1_text_file = d1_txt_files[0]
                
                # Read in the d1 text file
                d1_races = []
                with open(os.path.join(d1_dir, d1_text_file), 'r') as f:
                    for line in f:
                        line_parts = line.strip().split(',')
                        if len(line_parts) >= 2:
                            d1_races.append(line_parts[:2])
                
                clean_d1_races = [(race_name, url) for race_name, url in d1_races 
                                  if race_name not in wt_race_names and race_name not in pro_race_names]
                
                # Count duplicates removed
                duplicates_removed = len(d1_races) - len(clean_d1_races)
                logger.info(f"Removing {duplicates_removed} duplicate races from D1 list")
                
                # Rewrite the d1 text file
                with open(os.path.join(d1_dir, d1_text_file), 'w') as f:
                    for race_name, url in clean_d1_races:
                        f.write(f"{race_name},{url}\n")
        
        logger.info(f"Completed removing duplicates from {year_folder_dir}")
    except Exception as e:
        logger.error(f"Error removing duplicates from {year_folder_dir}: {e}")
        
    return None


def update_year_folder(year_folder_dir: str) -> None:
    """
    Given a year folder directory, scrapes and saves any races in each tour folder that have yet to be scraped.
    
    Args: 
        year_folder_dir: Path to a year folder within a base race db directory
        
    Returns:
        None but will systematically scrape all remaining races within each tour folder of the year folder.
    """
    logger.info(f"Updating year folder: {year_folder_dir}")
    
    # Remove duplicates from pro and d1
    remove_duplicates_across_tours(year_folder_dir)
    
    # Get the tour directories in the year folder
    tour_directories = []
    for tour in TOURS:
        tour_dir = os.path.join(year_folder_dir, tour)
        if os.path.exists(tour_dir):
            tour_directories.append(tour_dir)
        else:
            logger.warning(f"Tour directory does not exist: {tour_dir}")
    
    # Process each tour directory
    for tour_dir in tour_directories:
        logger.info(f"Processing tour directory: {tour_dir}")
        try:
            update_tour_folder(tour_dir)
            logger.info(f"Completed processing tour directory: {tour_dir}")
        except Exception as e:
            logger.error(f"Error updating tour directory {tour_dir}: {e}")
    
    logger.info(f"Completed updating year folder: {year_folder_dir}")
    return None


def update_db(base_db_folder: str) -> None:
    """
    Given a base db folder, scrapes and saves any races in each tour folder of each year folder 
    that have yet to be scraped.
    
    Args:
        base_db_folder: Path to a base db folder
        
    Returns:
        None but will systematically scrape all remaining races within each tour folder 
        of each year folder of the base db folder.
    """
    logger.info(f"Starting database update for {base_db_folder}")
    
    try:
        # Get list of year directories
        year_directories = [os.path.join(base_db_folder, year) 
                          for year in os.listdir(base_db_folder) 
                          if os.path.isdir(os.path.join(base_db_folder, year)) and len(year) == 4]
        
        logger.info(f"Found {len(year_directories)} year directories to process")
        
        # Process each year directory
        for year_dir in year_directories:
            logger.info(f"Processing year directory: {year_dir}")
            try:
                update_year_folder(year_dir)
                logger.info(f"Completed processing year directory: {year_dir}")
            except Exception as e:
                logger.error(f"Error updating year directory {year_dir}: {e}")
        
        logger.info(f"Database update completed for {base_db_folder}")
    except Exception as e:
        logger.error(f"Error during database update: {e}")
        
    return None


if __name__ == '__main__':
    # Update the full db
    logger.info("Starting full database update")
    update_db(base_db_folder=DB_PATH)
    logger.info("Database update complete")