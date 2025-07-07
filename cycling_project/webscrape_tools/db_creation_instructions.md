# Overview

Currently we're scraping data and saving it to a file structure that encodes some of the information about a race. It saves race data a YYYY/MM/DD/tour_type folder structure and then the race specific information in a file. 

Our goal is to convert this file structure into a local sqlite database. The goal of this move is to speed up the loading and processing of data when we get to the analytics phase of this project.

To accomplish this migration, you'll need to understand the structure of the data that has been saved as it is saved in a pkl format that stores Race objects, as defined by the `create_race_data.py` file in this folder.

Right now, we're thinking that the database should represent the following information.

- Top level Race objects
    - a top level race object can either be a one day race or a stage race.
    - Top level race objects should contain basic information like:
        - race date
        - race level
        - name
        - race id 
    - race ids should not be unique, we should track the same race over different years by the same id.


- Competitions
    - competitions fall into three categories: a stage of a stage race, a one day race, or the general classification of a stage race. Top level race objects that are stage races contain both their stages and their general classification. Top level race objects that are one day races just are their competition. 
    - competitions should have:
        - name
        - stage number (if a stage race)
        - race type (gc, stage, one day)
        - race results (ie finishing order of riders with their gaps from the winning time)
        - total/winning time time
        - race date
        - unique competition id. these can be unique.
        - competitions should be connected to race ids for top level races

- Riders
    - id
    - Birth date 
    - Team list (if possible) by year. Ie what team are they on for each year of their career.
    

- Rider Results
    - A rider result represents a rider outcome for a competition. It should include: 
        - competition id (this gives access to competition info)
        - rider age at date of competition
        - rider place (absolute)
        - rider place (percentile where winner is 100th percentile)
        - absolute rider time from winner
        - relative rider time from winner


An alternative way we might want to represent the data is to have each rider result stored inside the rider table. We're not sure which way is best to store the data and would appreciate advice you might have about what kinds of considerations might move us one way rather than another.  Our overarching goal is to build a predictive analytics system in which races can be characterized by the distribution of rider finishing times, riders can be characterized by how well they perform in different kinds of races, and race fields can be characterized by the strength of the riders, so that race outcomes and rider quality can be predicted based on these features.

# What to read

To understand how the current system works, especially in terms of how the data for each race is stored you'll want to start with the `create_race_data.py` file. The race data is saved as pickled Race objects. Date information and tour level information is stored in the file system, however.

To understand more of how the file system and scraping systems are working together, read the WEBSCRAPE_OVERVIEW.MD file. You'll get directed to the relevant python files for how race data has been scraped and saved.

# How to run python scripts and access pkl files

We want to use UV to run python scripts and manage our packages and environment. The pkl files were created using a conda environment. The packages in that environment have been exported to the requirements.txt file. You can build a UV venv using that requirements file and then use that with the uv run functionality to explore some of the race data. 

# What to do now

Read through everything you need to run through and create a plan for migrating from the file structure system we have now to a sqlite database that we can use going forward. Feel free to ask any clarifying questions in the process. Once we have our plan in place, let's save it as a markdown file, db_migration_plan.md. The plan should be crystal clear so that an engineer in the future can pick it up, look at our current project and see right where to pick up and what needs to be done.