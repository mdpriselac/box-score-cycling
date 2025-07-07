# Database Migration Plan: File System to SQLite

## Overview

This document outlines the plan for migrating the current file-based race data storage system to a SQLite database. The current system stores race data as pickled Python objects in a hierarchical directory structure. The new system will store this data in a normalized relational database for improved performance and querying capabilities.

## Current Data Structure

### File System Organization
```
~/cycling_data/scraped_data/
├── YYYY/                    # Year directories (2010-2025)
│   ├── wt/                  # World Tour races
│   │   ├── race_list.txt    # List of races with URLs
│   │   └── *.pkl            # Pickled Race objects
│   ├── pro/                 # .Pro races
│   │   ├── race_list.txt
│   │   └── *.pkl
│   └── d1/                  # .1 races
│       ├── race_list.txt
│       └── *.pkl
```

### Race Object Structure
- **Race** (from create_race_data.py):
  - name: str
  - url: str
  - year: int
  - date: datetime
  - category: str (wt/pro/d1)
  - stage_race: bool
  - results: List[Dict] (rider finishing data)
  - race_time: float (winning time in seconds)
  - stages: List[Stage]
  - fc_race_id: str

- **Stage** (from create_race_data.py):
  - name: str
  - url: str
  - fc_race_id: str
  - race: str (parent race name)
  - year: int
  - race_time: float
  - date: str
  - results: List[Dict]
  - category: str

- **Result Dictionary Structure**:
  - place: str
  - name: str
  - gap: float (seconds behind winner)
  - rider_id: str
  - team: str
  - team_id: str
  - dob: str (birth year)
  - bib_number: str (optional)

## Proposed Database Schema

### Tables

#### 1. races
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **fc_race_id**: TEXT NOT NULL
- **name**: TEXT NOT NULL
- **year**: INTEGER NOT NULL
- **date**: DATE
- **category**: TEXT NOT NULL (wt/pro/d1)
- **is_stage_race**: BOOLEAN NOT NULL
- **url**: TEXT
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **INDEX**: (fc_race_id, year) - for finding same race across years
- **INDEX**: (year, category) - for browsing races

#### 2. competitions
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **race_id**: INTEGER NOT NULL (FK to races.id)
- **name**: TEXT NOT NULL
- **stage_number**: INTEGER (NULL for one-day races)
- **competition_type**: TEXT NOT NULL ('one_day', 'stage', 'gc')
- **date**: DATE
- **winning_time**: REAL (seconds)
- **url**: TEXT
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **INDEX**: (race_id, stage_number)
- **FOREIGN KEY**: (race_id) REFERENCES races(id)

#### 3. riders
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **fc_rider_id**: TEXT UNIQUE NOT NULL
- **name**: TEXT NOT NULL
- **birth_year**: INTEGER
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **updated_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **INDEX**: (fc_rider_id)
- **INDEX**: (name)

#### 4. teams
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **fc_team_id**: TEXT UNIQUE NOT NULL
- **name**: TEXT NOT NULL
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **INDEX**: (fc_team_id)

#### 5. rider_results
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **competition_id**: INTEGER NOT NULL (FK to competitions.id)
- **rider_id**: INTEGER NOT NULL (FK to riders.id)
- **team_id**: INTEGER (FK to teams.id)
- **place**: INTEGER NOT NULL
- **time_gap**: REAL NOT NULL (seconds behind winner)
- **bib_number**: TEXT
- **rider_age**: INTEGER (calculated from competition date and birth year)
- **percentile**: REAL (calculated: 100 * (total_finishers - place + 1) / total_finishers)
- **created_at**: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
- **INDEX**: (competition_id, place)
- **INDEX**: (rider_id, competition_id)
- **UNIQUE**: (competition_id, rider_id)
- **FOREIGN KEY**: (competition_id) REFERENCES competitions(id)
- **FOREIGN KEY**: (rider_id) REFERENCES riders(id)
- **FOREIGN KEY**: (team_id) REFERENCES teams(id)

#### 6. rider_team_history (optional, for future enhancement)
- **id**: INTEGER PRIMARY KEY AUTOINCREMENT
- **rider_id**: INTEGER NOT NULL (FK to riders.id)
- **team_id**: INTEGER NOT NULL (FK to teams.id)
- **year**: INTEGER NOT NULL
- **UNIQUE**: (rider_id, team_id, year)
- **FOREIGN KEY**: (rider_id) REFERENCES riders(id)
- **FOREIGN KEY**: (team_id) REFERENCES teams(id)

## Design Decisions

### 1. Separate Riders and Results
**Decision**: Store rider results in a separate table rather than embedding in the riders table.

**Rationale**:
- **Normalization**: Follows database normalization principles
- **Flexibility**: Easier to query results by competition, team, or rider
- **Performance**: Smaller rider table for quick lookups
- **Scalability**: Can add result-specific fields without affecting rider data
- **Analytics**: Facilitates aggregations (avg finishing position, win rate, etc.)

### 2. Competition Abstraction
**Decision**: Create a competitions table to unify stages, one-day races, and GCs.

**Rationale**:
- **Consistency**: All race results stored in same format
- **Simplicity**: Single join pattern for all result queries
- **Flexibility**: Can distinguish competition types while maintaining unified structure

### 3. Race ID Strategy
**Decision**: Use auto-increment IDs internally but preserve FirstCycling IDs for reference.

**Rationale**:
- **Performance**: Integer PKs are faster than string PKs
- **Flexibility**: Not dependent on external ID scheme
- **Tracking**: Can still track races across years using fc_race_id

## Migration Process

### Phase 1: Database Setup
1. Create SQLite database file
2. Execute CREATE TABLE statements
3. Add indexes and constraints
4. Create views for common queries

### Phase 2: Data Extraction
1. Traverse the file system structure
2. Load each pickle file
3. Extract and transform data for database insertion
4. Handle missing or malformed data gracefully

### Phase 3: Data Loading
1. Insert races (handling duplicates by fc_race_id + year)
2. Insert competitions for each race
3. Insert unique riders and teams
4. Insert rider results with calculated fields

### Phase 4: Validation
1. Compare record counts between pickle files and database
2. Spot-check data integrity
3. Verify foreign key relationships
4. Test query performance

### Phase 5: Migration Tools
Create the following Python scripts:
1. `create_database.py` - Sets up the SQLite schema
2. `migrate_races.py` - Main migration script
3. `validate_migration.py` - Checks data integrity
4. `query_examples.py` - Common query patterns

## Implementation Steps

### Step 1: Create Database Schema (create_database.py)
```python
import sqlite3
from pathlib import Path

def create_database(db_path: str):
    """Create the SQLite database with all tables and indexes."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables (SQL statements here)
    # Add indexes
    # Add foreign key constraints
    
    conn.commit()
    conn.close()
```

### Step 2: Migration Script Structure (migrate_races.py)
```python
import pickle
import sqlite3
from pathlib import Path
from typing import Dict, List
import logging

class RaceMigrator:
    def __init__(self, source_dir: str, db_path: str):
        self.source_dir = Path(source_dir)
        self.conn = sqlite3.connect(db_path)
        
    def migrate_year(self, year: str):
        """Migrate all races for a given year."""
        year_dir = self.source_dir / year
        for category in ['wt', 'pro', 'd1']:
            self.migrate_category(year_dir / category, category)
            
    def migrate_category(self, category_dir: Path, category: str):
        """Migrate all races in a category directory."""
        for pkl_file in category_dir.glob('*.pkl'):
            self.migrate_race(pkl_file, category)
```

### Step 3: Data Transformation Functions
- Convert Race objects to database records
- Handle missing fields with defaults
- Calculate derived fields (age, percentile)
- Normalize rider and team names

### Step 4: Batch Processing
- Process in transactions for performance
- Add progress logging
- Handle errors gracefully
- Support resuming interrupted migrations

## Query Examples

### Find all races for a rider in a year
```sql
SELECT r.name, c.name as competition, c.date, rr.place, rr.time_gap
FROM rider_results rr
JOIN competitions c ON rr.competition_id = c.id
JOIN races r ON c.race_id = r.id
JOIN riders rid ON rr.rider_id = rid.id
WHERE rid.name = ? AND r.year = ?
ORDER BY c.date;
```

### Get race results with percentiles
```sql
SELECT rid.name, rr.place, rr.percentile, rr.time_gap, t.name as team
FROM rider_results rr
JOIN riders rid ON rr.rider_id = rid.id
JOIN teams t ON rr.team_id = t.id
WHERE rr.competition_id = ?
ORDER BY rr.place;
```

### Find dominant performances (top 10% finishes)
```sql
SELECT rid.name, COUNT(*) as top_finishes
FROM rider_results rr
JOIN riders rid ON rr.rider_id = rid.id
WHERE rr.percentile >= 90
GROUP BY rid.id
ORDER BY top_finishes DESC;
```

## Performance Considerations

1. **Indexes**: Create indexes on all foreign keys and common query fields
2. **Batch Inserts**: Use executemany() for bulk inserts
3. **Transaction Size**: Commit every 1000 records for balance
4. **Memory Usage**: Process one race at a time to avoid loading all data
5. **Connection Pooling**: Reuse database connections

## Error Handling

1. **Missing Data**: Log warnings but continue processing
2. **Duplicate Races**: Skip or update based on configuration
3. **Invalid References**: Create placeholder records for missing riders/teams
4. **Corrupted Pickles**: Log error and skip file
5. **Database Errors**: Implement retry logic with exponential backoff

## Testing Strategy

1. **Unit Tests**: Test each transformation function
2. **Integration Tests**: Test full migration of sample data
3. **Performance Tests**: Measure migration speed and query performance
4. **Data Validation**: Compare source and migrated data
5. **Edge Cases**: Test with missing fields, duplicates, etc.

## Future Enhancements

1. **Incremental Updates**: Support adding new races without full remigration
2. **Data Cleaning**: Standardize rider names, handle name changes
3. **Additional Tables**: Weather data, race profiles, etc.
4. **API Layer**: RESTful API for data access
5. **Analytics Views**: Pre-calculated statistics and aggregations

## Timeline Estimate

- **Phase 1 (Database Setup)**: 2-3 hours
- **Phase 2-3 (Migration Script)**: 4-6 hours
- **Phase 4 (Validation)**: 2-3 hours
- **Phase 5 (Documentation)**: 1-2 hours
- **Testing & Debugging**: 3-4 hours

**Total Estimate**: 12-18 hours of development time

## Next Steps

1. Review and approve this migration plan
2. Create the database schema script
3. Implement the migration script with a small test dataset
4. Run full migration on complete dataset
5. Validate results and optimize performance
6. Create documentation for using the new database