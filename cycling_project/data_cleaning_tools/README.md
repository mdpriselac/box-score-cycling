# Data Cleaning Tools

Currently there is only one cleaning tool available. It is for adding dates to scraped races that didn't discover the race dates in the normal course of scraping the data. These tools are found in the clean_scraped_data module.

## Cleaning Date Data for Scraped Races

This cleaning process focuses on the Race objects that have been saved as pickle files during the scrape process. 

The process for adding race date data to races starts with a path to a tour directory that contains scraped race objects. Based on the path, the page for the year of that tour will be scraped. Those pages contain tables with race names and dates that are extracted.

Once the dates and race pairs are extracted an FCCycingTour object is loaded from the tour path. For any race that is missing a date, the date is added from the scraped tour page. 

For stage races that are missing dates or have stages with missing dates the process is as follows: 
- First, the GC date is assigned to the last date of the range of dates provided by the tour page.
- Second, the initial stage is assigned the first date of the dates provided by the tour page. A latest_date variable is initialized.
- Third, for each stage, if it has a date already, the latest date variable is set to that date. If it doesn't, the stage date is assigned to the latest date.
- Fourth, the latest date is incremented by a day.

This will lead to slight inaccuracies for dates of stages in grand tours where there are rest days but it's close enough.

Date cleaning for races can happen at tour, year, and full scraped database level through the save_date_verified_tour function (which takes a tour path), the save_year_verified function (which takes a year path), and the clean_db_dates function (which takes a base scraped database path).

Alternatively individual races can be cleaned by using the scrape_races_w_dates function, which takes a tour directory path as argument, and returns a list of date,race name tuples, and the verify_race_date function which takes a Race object and the list of date,race tuples form the scrape_races_w_dates function.