#We can access top level tours by using the t input variable to the url
#y=year
#t=tour
#you can always but in t=1 and get redirected to the top level tour of that year
#t21 is the second level, currently the .Pro level

import json
import os
import re
from datetime import date
from bs4 import BeautifulSoup
from time import sleep
from random import randint
from typing import Any, Dict, List, Tuple, Optional
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from cycling_project.webscrape_tools.scrape_client import WebClient
from cycling_project.webscrape_tools.logging_config import get_logger
from dotenv import load_dotenv

# Configure logger
logger = get_logger("find_races")

# Set a default path for DB_PATH if environment variable is not set
DEFAULT_DB_PATH = os.path.join(str(Path.home()), "cycling_data/scraped_data")

# Load environment variables - using absolute path resolution
module_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(module_dir))
env_path = os.path.join(project_root, ".env")

# Try to load from .env file if it exists
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    logger.warning(f"No .env file found at {env_path}")

# Get DB_PATH with a fallback to DEFAULT_DB_PATH
DB_PATH = os.getenv("DB_PATH", DEFAULT_DB_PATH)

# Ensure DB_PATH exists
if not DB_PATH:
    logger.warning("DB_PATH environment variable not set, using default path")
    DB_PATH = DEFAULT_DB_PATH

logger.info(f"Database path: {DB_PATH}")

# Create the directory if it doesn't exist
if not os.path.exists(DB_PATH):
    os.makedirs(DB_PATH)
    logger.info(f"Created database directory: {DB_PATH}")

# Constants
BASE_URL = "https://firstcycling.com"
# Tour level IDs
WORLD_TOUR_ID = 1  # World Tour level, division 1, top level
PRO_TOUR_ID = 21   # .Pro level, division 2, second level
DOT_ONE_TOUR_ID = 22  # .1 level, division 3, third level

def find_race_list_table(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Finds the table from a soup object that contains race information for a year and tour level.

    FirstCycling pages have two matching tables: a small "Results" table showing
    only recently completed races, and the full calendar table. We return the
    largest matching table to get the complete race list.

    Args:
        soup: BeautifulSoup object of a page

    Returns:
        BeautifulSoup table tag or None if not found
    """
    tables = soup.find_all('table')
    matching_tables = []
    for table in tables:
        thead = table.find('thead')
        if thead:
            ths = thead.find_all('th')
            date_found = False
            cat_found = False
            race_found = False
            for th in ths:
                if 'date' in th.text.lower():
                    date_found = True
                if 'cat' in th.text.lower():
                    cat_found = True
                if 'race' in th.text.lower():
                    race_found = True
            if date_found and cat_found and race_found:
                tbody = table.find('tbody')
                row_count = len(tbody.find_all('tr')) if tbody else 0
                matching_tables.append((row_count, table))

    if matching_tables:
        # Return the table with the most rows (full calendar, not just results)
        matching_tables.sort(key=lambda x: x[0], reverse=True)
        return matching_tables[0][1]

    logger.warning("No Race table found for this page")
    return None

def find_race_data_column(table_tag: BeautifulSoup) -> Optional[int]:
    """
    Finds the index of the race data column in a table that has already been identified as listing races.
    
    Args:
        table_tag: BeautifulSoup table tag
        
    Returns:
        int the index of Race column in the table that has the race name and url, or None if not found
    """
    #In the thead tag, get the tr, and then find the th tag that has 'Race' in it, return its index
    thead = table_tag.find('thead')
    if not thead:
        logger.warning("No thead tag found in this table, can't find winner column")
        return None
        
    tr = thead.find('tr')
    ths = tr.find_all('th')
    for i, th in enumerate(ths):
        if 'race' in th.text.lower():
            return i
            
    logger.warning("No Race Column found in this table")
    return None


def _find_column(table_tag: BeautifulSoup, name: str) -> Optional[int]:
    """Return the index of a named calendar column, case-insensitively."""
    thead = table_tag.find("thead")
    row = thead.find("tr") if thead else None
    if row:
        for index, th in enumerate(row.find_all("th")):
            if name in th.get_text(" ", strip=True).lower():
                return index
    return None


_MONTHS = {
    name.lower(): number
    for number, name in enumerate(
        ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    )
    if name
}


def parse_calendar_dates(value: str, year: int) -> Tuple[Optional[str], Optional[str]]:
    """Parse FirstCycling's single-day or date-range calendar notation.

    FirstCycling has used both numeric ``dd.mm`` values and abbreviated month
    names in fixtures.  A range that rolls from December into January is
    assigned to the following year at its end.
    """
    text = " ".join(value.replace("\xa0", " ").split())
    text = re.sub(r"\s*(?:–|—|-)\s*", "-", text)
    numeric = re.fullmatch(
        r"(?P<d1>\d{1,2})[./](?P<m1>\d{1,2})(?:-(?P<d2>\d{1,2})[./](?P<m2>\d{1,2}))?",
        text,
    )
    named = re.fullmatch(
        r"(?P<d1>\d{1,2})\s+(?P<m1>[A-Za-z]{3})(?:-(?P<d2>\d{1,2})\s+(?P<m2>[A-Za-z]{3}))?",
        text,
    )
    match = numeric or named
    if not match:
        return None, None

    def month(raw: str) -> int:
        return int(raw) if raw.isdigit() else _MONTHS[raw.lower()]

    try:
        start_month = month(match.group("m1"))
        start = date(year, start_month, int(match.group("d1")))
        if match.group("d2"):
            end_month = month(match.group("m2"))
            end_year = year + int(end_month < start_month)
            end = date(end_year, end_month, int(match.group("d2")))
        else:
            end = start
    except (KeyError, ValueError):
        return None, None
    return start.isoformat(), end.isoformat()


def _race_id(url: str) -> Optional[str]:
    values = parse_qs(urlparse(url).query).get("r")
    return values[0] if values else None


def _row_country(row: BeautifulSoup) -> Optional[str]:
    """Best-effort country text from FC flag markup (title/alt/data-code)."""
    for tag in row.find_all(["span", "img"]):
        classes = " ".join(tag.get("class") or []).lower()
        if "flag" not in classes and tag.name != "img":
            continue
        for attr in ("title", "alt", "data-country", "data-code"):
            value = tag.get(attr)
            if value and str(value).strip():
                return str(value).strip()
    return None


def extract_calendar_rows(soup: BeautifulSoup, year: int) -> List[Dict[str, Any]]:
    """Extract dated race records while leaving the legacy ``.txt`` shape alone."""
    table = find_race_list_table(soup)
    if table is None:
        return []
    race_index = find_race_data_column(table)
    date_index = _find_column(table, "date")
    category_index = _find_column(table, "cat")
    if race_index is None or date_index is None:
        return []

    records: List[Dict[str, Any]] = []
    body = table.find("tbody")
    for row in body.find_all("tr") if body else []:
        cols = row.find_all("td")
        if max(race_index, date_index) >= len(cols):
            continue
        link = cols[race_index].find("a")
        if not link or not link.get("href"):
            continue
        url = f"{BASE_URL}/{link.get('href').lstrip('/')}"
        start_date, end_date = parse_calendar_dates(
            cols[date_index].get_text(" ", strip=True), year
        )
        calendar_category = (
            cols[category_index].get_text(" ", strip=True)
            if category_index is not None and category_index < len(cols)
            else None
        )
        records.append({
            "fc_race_id": _race_id(url),
            "name": link.get("title") or link.get_text(" ", strip=True),
            "url": url,
            "start_date": start_date,
            "end_date": end_date,
            "calendar_category": calendar_category or None,
            "is_stage_race": bool(
                (calendar_category or "").strip().startswith("2.")
                or (start_date and end_date and start_date != end_date)
            ),
            "country": _row_country(row),
        })
    return records


def _write_calendar_sidecar(path: Path, records: List[Dict[str, Any]]) -> None:
    """Merge a partial-month scrape into the durable, deterministic sidecar."""
    existing: List[Dict[str, Any]] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            existing = loaded if isinstance(loaded, list) else loaded.get("races", [])
        except (OSError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable calendar sidecar %s", path)
    by_url = {row.get("url"): row for row in existing if row.get("url")}
    for row in records:
        old = by_url.get(row.get("url"), {})
        by_url[row["url"]] = {**old, **{k: v for k, v in row.items() if v is not None}}
    ordered = sorted(
        by_url.values(),
        key=lambda row: (row.get("start_date") or "9999-12-31", row.get("name") or "", row.get("url") or ""),
    )
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False) + "\n")

def extract_races(soup: BeautifulSoup) -> Optional[List[Tuple[str, str]]]:
    """
    Extracts a list of race names and urls from a soup object that contains a table of race information for a given year and tour level.
    
    Args:
        soup: BeautifulSoup object of a page
        
    Returns:
        List of tuples. The first element is a race name, the second element is the race webpage url.
        Returns None if race table or column not found.
    """
    #Find the key table
    race_table = find_race_list_table(soup)
    if race_table is None:
        logger.warning("No Race table found")
        return None
        
    #Get the race column index
    race_col_index = find_race_data_column(race_table)
    if race_col_index is None:
        logger.warning("No Race column found in the race table")
        return None
        
    #Get the rows of the table
    race_rows = race_table.find('tbody').find_all('tr')
    #Extract the data from the rows. We want race Name and URL. Both are in the a tag inside the td tag. The name is the title attribute, the url is the href
    races = []
    for row in race_rows:
        cols = row.find_all('td')
        race_col = cols[race_col_index]
        try:
            a_tag = race_col.find('a')
            race_name = a_tag.get('title')
            race_url = f"{BASE_URL}/{a_tag.get('href')}"
            races.append((race_name, race_url))
        except Exception as e:
            logger.error(f"Error extracting race name and url: {e}")
            continue
            
    return races

def create_race_year_db(year: str, race_data_dir: str = None, months: Optional[List[int]] = None) -> None:
    """
    Creates a directory structure for a given year and saves a list of races and their webpage urls
    for all three tour levels in that year. Optionally filter by month(s) to only get races from
    specific months (useful for scraping an in-progress season).

    Args:
        year: four digit year as a string
        race_data_dir: base directory where the year directory will be created. Default is DB_PATH.
        months: list of month numbers (1-12) to scrape. If None, scrapes the full calendar.
                When specified, each month generates a separate page request and results are
                combined into the single tour-level txt file.
    """
    # If no race_data_dir is provided, use the global DB_PATH
    if race_data_dir is None:
        race_data_dir = DB_PATH

    month_desc = f" months {months}" if months else ""
    logger.info(f"Creating race database for {year}{month_desc} in {race_data_dir}")

    #Check if there's a directory for the year, create it if not
    year_dir = os.path.join(race_data_dir, year)
    logger.debug(f"Year directory: {year_dir}")

    if not os.path.exists(year_dir):
        os.makedirs(year_dir)
        logger.info(f"Created directory for year {year}")

    #Check if there are directories for wt, pro, and d1 divisions, create them if not
    wt_dir = os.path.join(year_dir, 'wt')
    pro_dir = os.path.join(year_dir, 'pro')
    d1_dir = os.path.join(year_dir, 'd1')

    for dir_path, tour_name in [(wt_dir, 'World Tour'), (pro_dir, '.Pro'), (d1_dir, '.1')]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"Created directory for {tour_name} races")

    tour_configs = [
        (WORLD_TOUR_ID, "World Tour", wt_dir, 'wt.txt'),
        (PRO_TOUR_ID, ".Pro", pro_dir, 'pro.txt'),
        (DOT_ONE_TOUR_ID, ".1", d1_dir, 'd1.txt'),
    ]

    client = WebClient(BASE_URL)

    try:
        for tour_id, tour_name, tour_dir, filename in tour_configs:
            if months:
                # Scrape each month separately and combine results
                _process_tour_level_by_months(client, year, tour_name, tour_id, tour_dir, filename, months)
            else:
                # Scrape the full calendar page
                tour_url = f"{BASE_URL}/race.php?y={year}&t={tour_id}"
                _process_tour_level(client, year, tour_name, tour_url, tour_dir, filename)
            sleep(randint(1, 3))

        logger.info(f"Finished getting all race lists for {year}")
    finally:
        client.close()

def _process_tour_level_by_months(client: WebClient, year: str, tour_name: str,
                                  tour_id: int, tour_dir: str, filename: str,
                                  months: List[int]) -> None:
    """
    Process a tour level month by month, combining results into a single file.
    Uses the FirstCycling &m= parameter to fetch per-month race lists.

    Args:
        client: WebClient instance
        year: Year to process
        tour_name: Name of the tour level for logging
        tour_id: FirstCycling tour level ID
        tour_dir: Directory to save the file
        filename: Name of the file to save the races
        months: List of month numbers (1-12) to process
    """
    logger.info(f"Getting {tour_name} Race List for {year} months {months}")

    all_races = []
    all_calendar_rows: List[Dict[str, Any]] = []
    seen_urls = set()

    for month in months:
        month_url = f"{BASE_URL}/race.php?y={year}&t={tour_id}&m={month}"
        try:
            response = client.get(month_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            races = extract_races(soup)
            calendar_rows = extract_calendar_rows(soup, int(year))
            all_calendar_rows.extend(calendar_rows)

            if races:
                for race_name, race_url in races:
                    if race_url not in seen_urls:
                        all_races.append((race_name, race_url))
                        seen_urls.add(race_url)
                logger.info(f"Found {len(races)} {tour_name} race(s) for {year} month {month}")
            else:
                logger.info(f"No {tour_name} races found for {year} month {month}")

            sleep(randint(1, 3))

        except Exception as e:
            logger.error(f"Error processing {tour_name} month {month} for {year}: {e}")

    # Merge with existing race list entries (from previous months)
    filepath = os.path.join(tour_dir, filename)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                for line in f:
                    parts = line.strip().split(',', 1)
                    if len(parts) == 2 and parts[1] not in seen_urls:
                        all_races.append((parts[0], parts[1]))
                        seen_urls.add(parts[1])
        except Exception as e:
            logger.warning(f"Error reading existing race list {filepath}: {e}")

    if not all_races:
        logger.warning(f"No {tour_name} Races found for {year} months {months}")
        return

    with open(filepath, 'w') as tour_file:
        for race, url in all_races:
            tour_file.write(f"{race},{url}\n")

    logger.info(f"Saved {len(all_races)} {tour_name} Race(s) for {year} months {months}")
    _write_calendar_sidecar(
        Path(tour_dir) / f"{Path(filename).stem}.calendar.json",
        all_calendar_rows,
    )


def _process_tour_level(client: WebClient, year: str, tour_name: str, tour_url: str,
                        tour_dir: str, filename: str) -> None:
    """
    Process a specific tour level, extract races and save to file.
    
    Args:
        client: WebClient instance
        year: Year to process
        tour_name: Name of the tour level for logging
        tour_url: URL to fetch the tour data
        tour_dir: Directory to save the file
        filename: Name of the file to save the races
    """
    logger.info(f"Getting {tour_name} Race List for {year}")
    
    try:
        response = client.get(tour_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        races = extract_races(soup)
        calendar_rows = extract_calendar_rows(soup, int(year))
        
        if not races or len(races) == 0:
            logger.warning(f"No {tour_name} Races found for {year}")
            return
            
        with open(os.path.join(tour_dir, filename), 'w') as tour_file:
            for race, url in races:
                tour_file.write(f"{race},{url}\n")
                
        logger.info(f"Saved {len(races)} {tour_name} Race(s) for {year}")
        _write_calendar_sidecar(
            Path(tour_dir) / f"{Path(filename).stem}.calendar.json",
            calendar_rows,
        )
        
    except Exception as e:
        logger.error(f"Error processing {tour_name} races for {year}: {e}")
    
if __name__ == "__main__":
    create_race_year_db(year='2025')
