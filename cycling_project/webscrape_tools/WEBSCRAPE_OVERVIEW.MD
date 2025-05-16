# WebScrape Tools Overview

This document provides a comprehensive overview of the web scraping tools in this project, designed for scraping cycling race data from FirstCycling.com. This guide is written to be accessible for users with limited programming experience.

## Table of Contents

1. [Module Overview](#module-overview)
2. [Key Components](#key-components)
3. [Common Workflows](#common-workflows)
4. [Logging System](#logging-system)
5. [Testing the Module](#testing-the-module)
6. [Troubleshooting](#troubleshooting)

## Module Overview

The `webscrape_tools` module is designed to:

1. Find cycling races by year and tour level (World Tour, .Pro, .1)
2. Download and parse race results
3. Extract start lists for races
4. Store the data in a structured format

The tools handle rate limiting, error recovery, and provide detailed logging to track the scraping process.

## Key Components

### WebClient (`scrape_client.py`)

The foundation of all web requests, providing:

- Automatic rate limiting to avoid being blocked
- Error handling with retries
- Session management

**Key Interface**:
```python
from cycling_project.webscrape_tools.scrape_client import WebClient

# Create a client
client = WebClient("https://firstcycling.com")

# Make a request
response = client.get("/race.php?r=17&y=2024")  # Tour de France 2024

# Always close the client when done
client.close()
```

### Finding Races (`find_races.py`)

Tools to discover races and create a database structure.

**Key Interface**:
```python
from cycling_project.webscrape_tools.find_races import create_race_year_db

# Create a database for a specific year
create_race_year_db(year="2024", race_data_dir="/path/to/database")
```

This creates a directory structure:
```
/path/to/database/
└── 2024/
    ├── wt/       # World Tour races
    ├── pro/      # .Pro races
    └── d1/       # .1 races
```

Each directory contains a text file listing races and their URLs.

### Race Results Scraping (`create_race_data.py`, `get_race_results.py`)

Tools to scrape race results, including stages for multi-stage races.

**Key Interface**:
```python
from cycling_project.webscrape_tools.create_race_data import Race

# Create a race object
race = Race(name="Tour de France", url="https://firstcycling.com/race.php?r=17&y=2024")

# Scrape the race and all its stages
race.populate_race()

# Now race contains all results
print(f"Race has {len(race.results)} riders")
if race.stage_race:
    print(f"Race has {len(race.stages)} stages")

# Save the race to a file
import pickle
with open("tour_de_france_2024.pkl", "wb") as f:
    pickle.dump(race, f)
```

### Startlist Scraping (`get_startlist.py`, `start_list_parse_tools.py`)

Tools to scrape startlists (riders and teams before a race).

**Key Interface**:
```python
from cycling_project.webscrape_tools.get_startlist import get_start_list

# Get startlist for Tour de France 2024 (race ID 17)
teams = get_start_list(race_id=17, year=2024)

# Access team and rider information
for team in teams:
    print(f"Team: {team.name} (ID: {team.team_id})")
    for rider in team.riders:
        print(f"  {rider.number}: {rider.name} (ID: {rider.rider_id})")
```

### Batch Processing (`download_race_data.py`)

Tools for downloading multiple races systematically.

**Key Interface**:
```python
from cycling_project.webscrape_tools.download_race_data import update_db

# Update the entire database (download all races)
update_db(base_db_folder="/path/to/database")

# For specific years or tours, use:
from cycling_project.webscrape_tools.download_race_data import update_year_folder, update_tour_folder

# Update just one year
update_year_folder("/path/to/database/2024")

# Update just one tour in one year
update_tour_folder("/path/to/database/2024/wt")
```

## Common Workflows

### 1. Setting Up Race Database

```python
from cycling_project.webscrape_tools.find_races import create_race_year_db

# Create directory structure and race lists for 2024
create_race_year_db(year="2024", race_data_dir="/path/to/database")
```

### 2. Downloading All Race Data

```python
from cycling_project.webscrape_tools.download_race_data import update_db

# Download all races in the database
update_db(base_db_folder="/path/to/database")
```

### 3. Getting a Specific Race

```python
from cycling_project.webscrape_tools.create_race_data import Race

# Create and populate a race object
race = Race(name="Paris-Roubaix", url="https://firstcycling.com/race.php?r=8&y=2024")
race.populate_race()

# Work with the race data
print(f"Winner: {race.results[0]['name']}")
```

### 4. Getting a Race Startlist

```python
from cycling_project.webscrape_tools.get_startlist import get_start_list

# Get startlist
teams = get_start_list(race_id=8, year=2024)  # Paris-Roubaix 2024

# Count riders per team
for team in teams:
    print(f"{team.name}: {len(team.riders)} riders")
```

## Logging System

The module uses a standardized logging system that saves detailed logs to the `webscrape_logs` directory.

### Log File Structure

- Log files are named with the format: `YYYYMMDD_module_name.log`
- Each module has its own log file
- Log entries include timestamp, module, level, and message

### Logging Levels

- **DEBUG**: Detailed information for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened
- **ERROR**: A more serious problem that prevented an operation

### Viewing Logs

Logs are saved to the `webscrape_tools/webscrape_logs` directory. You can view them with any text editor:

```bash
cat webscrape_tools/webscrape_logs/20250516_scrape_client.log
```

### Modifying Logging Configuration

To change the logging configuration, edit the `logging_config.py` file:

```python
# Change the log directory
LOG_DIR = Path("/path/to/custom/logs")

# Change the default log level
DEFAULT_LEVEL = logging.DEBUG  # More detailed logs

# Change the date format
DATE_FORMAT = "%Y-%m-%d %H:%M:%S.%f"  # Include milliseconds
```

## Testing the Module

The module includes a comprehensive test suite to verify all components work correctly.

### Test Structure

- **Unit tests**: Test individual functions in isolation
- **Integration tests**: Test multiple components working together
- **Test fixtures**: Sample HTML data for consistent testing

### Running Tests

To run the tests, use pytest from the project root:

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests for a specific module
pytest tests/unit/webscrape_tools/test_scrape_client.py

# Run a specific test
pytest tests/unit/webscrape_tools/test_scrape_client.py::test_webclient_initialization
```

### Adding New Tests

To add new tests:

1. Create a new test file in the appropriate directory:
   - `tests/unit/webscrape_tools/` for unit tests
   - `tests/integration/webscrape_tools/` for integration tests

2. Use the existing test fixtures:
   ```python
   def test_my_new_function(sample_race_detail_soup):
       # Test with the sample race detail HTML
       result = my_function(sample_race_detail_soup)
       assert result is not None
   ```

3. Use the mock client to avoid real HTTP requests:
   ```python
   def test_my_scraping_function(mock_client):
       # Test with mock HTTP responses
       result = my_function(client=mock_client)
       assert result is not None
   ```

## Troubleshooting

### Common Issues

1. **Rate Limiting**: If you see "429 Too Many Requests" errors:
   - Increase the `min_request_interval` in `WebClient`
   - Add more random sleep time between requests

2. **HTML Structure Changes**: If parsing suddenly fails:
   - Check the logs for warnings about missing tables or columns
   - Update the parsing functions to match the new structure

3. **Memory Issues**: When scraping many races:
   - Process one tour or year at a time
   - Save results frequently
   - Clear race objects after saving

### Using Logs for Debugging

1. Look for ERROR level messages first
2. Check WARNING messages for potential issues
3. Enable DEBUG level for more detailed information
4. Check the sequence of operations in the INFO messages

### Testing in Isolation

To test a specific component:

```python
from cycling_project.webscrape_tools.get_race_results import extract_race_date
from bs4 import BeautifulSoup

# Load HTML from a file
with open("sample_race.html", "r") as f:
    html = f.read()
    
# Parse the HTML
soup = BeautifulSoup(html, "html.parser")

# Test the function
race_date = extract_race_date(soup)
print(f"Race date: {race_date}")
```

This allows you to identify which component is failing without running the entire pipeline.