# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Codebase Overview

This is a collection of tools for web scraping cycling race data from FirstCycling.com. The codebase allows:
- Finding races by year and tour level
- Scraping race results including stage information
- Scraping race startlists and rider information
- Downloading and storing race data in a structured format

## Key Components

### Web Scraping Client
- `scrape_client.py`: Contains the `WebClient` class, which handles HTTP requests with built-in rate limiting and error handling.

### Race Discovery
- `find_races.py`: Contains functions to identify lists of races and their URLs by year and tour level (World Tour, .Pro, and .1).
- `create_race_year_db()`: Creates a file structure for storing race data and generates text files listing races by tour level.

### Race Results Scraping
- `get_race_results.py`: Functions for extracting race data from race pages.
- `create_race_data.py`: Contains `Race` and `Stage` classes that represent races and scrape their webpages.

### Startlist Scraping
- `get_startlist.py`: Functions to extract pre-race startlist information.
- `start_list_parse_tools.py`: Classes and functions for parsing startlists, including `Team` and `Rider` objects.

### Data Management
- `download_race_data.py`: Functions for systematically downloading race data.
- `scrape_startlists.py`: Functions for scraping and adding bib numbers to race data.

## Common Operations

### Creating File Structure for Race Data
```python
from cycling_project.webscrape_tools.find_races import create_race_year_db

# Create directory structure for 2024 races 
create_race_year_db(year='2024', race_data_dir=DB_PATH)
```

### Scraping Race Results
```python
from cycling_project.webscrape_tools.create_race_data import Race

# Create Race object from race name and URL
race = Race(name="Tour de France", url="https://firstcycling.com/race.php?r=17&y=2024")

# Scrape race data
race.populate_race()

# Save race data
import pickle
with open("tour_de_france.pkl", "wb") as f:
    pickle.dump(race, f)
```

### Getting Race Startlists
```python
from cycling_project.webscrape_tools.get_startlist import get_start_list

# Get startlist for race with ID 17 (Tour de France) for year 2024
startlist = get_start_list(race_id=17, year=2024)

# Process teams and riders
for team in startlist:
    print(team.name)
    for rider in team.riders:
        print(f"  {rider.number}: {rider.name}")
```

## Development Notes

- The codebase uses Beautiful Soup for HTML parsing
- Rate limiting is built into the WebClient to avoid getting blocked
- Data is currently saved as pickle files in a directory structure
- Environment variables are used to configure the base path for data storage

## Planned Improvements

- Adding cloud storage options
- Creating proper database storage for races and riders
- Implementing tools to check scraping progress
- Consolidating scraping functions and class definitions
- Creating tools for accessing and analyzing the scraped data