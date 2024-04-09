#import PlayerDatabase
#import PresentData
import CoreUtils

browser = CoreUtils.browser

import re
import os
import pandas as pd
from bs4 import BeautifulSoup
import numpy as np
import datetime
import matplotlib
import sqlite3
import json
import jsonschema
from jsonschema import validate
from typing import Dict, Optional, List, Union


from math import floor
from io import StringIO
pd.options.mode.chained_assignment = None  # default='warn'

SKILL_LEVELS = ['atrocious', 'dreadful', 'poor', 'ordinary', 'average', 'reasonable', 'capable', 'reliable', 'accomplished', 'expert', 'outstanding', 'spectacular', 'exceptional', 'world class', 'elite', 'legendary']
SKILL_LEVELS_MAP = {level: index for index, level in enumerate(SKILL_LEVELS)}

def nationality_id_to_rgba_color(natid):
    nat_colors = ['darkblue', 'red', 'forestgreen', 'black', 'mediumseagreen', 'darkkhaki', 'maroon', 'firebrick', 'darkgreen', 'firebrick', 'tomato', 'royalblue', 'brown', 'darkolivegreen', 'olivedrab', 'purple', 'lightcoral', 'darkorange']

    return matplotlib.colors.to_rgba(nat_colors[natid-1])


def nationality_id_to_name_str(natid, full_name=False):
    natid = int(natid)
    nat_name_short = ['AUS', 'ENG', 'IND', 'NZL', 'PAK', 'SA', 'WI', 'SRI', 'BAN', 'ZWE', 'CAN', 'USA', 'KEN', 'SCO', 'IRE', 'UAE', 'BER', 'NL']
    nat_name_long = ['Australia', 'England', 'India', 'New Zealand', 'Pakistan', 'South Africa', 'West Indies', 'Sri Lanka', 'Bangladesh', 'Zimbabwe', 'Canada', 'USA', 'Kenya', 'Scotland', 'Ireland', 'UAE', 'Bermuda', 'Netherlands']

    return nat_name_long[natid-1] if full_name else nat_name_short[natid-1]


def skill_word_to_index(skill_w, skill_word_type='full'):
    SKILL_LEVELS_FULL = ['atrocious', 'dreadful', 'poor', 'ordinary', 'average', 'reasonable', 'capable', 'reliable', 'accomplished', 'expert', 'outstanding', 'spectacular', 'exceptional', 'world class', 'elite', 'legendary']
    SKILL_LEVELS_SHORT = ['atroc', 'dread', 'poor', 'ordin', 'avg', 'reas', 'capab', 'reli', 'accom', 'exprt', 'outs', 'spect', 'excep', 'wclas', 'elite', 'legen']

    if str(skill_w) == 'nan':
        return -1

    if skill_word_type == 'full':
        skill_n = SKILL_LEVELS_FULL.index(skill_w)
    elif skill_word_type == 'short':
        skill_n = SKILL_LEVELS_SHORT.index(skill_w)
    else:
        skill_n = -1

    return skill_n


def get_player_page(player_id):
    browser.rbrowser.open('https://www.fromthepavilion.org/player.htm?playerId={}'.format(player_id))
    page = str(browser.rbrowser.parsed)

    return page


def get_player_spare_ratings(player_df, col_name_len='full'):
    skill_rating_sum = 0
    for skill in ['Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Pow' if 'Pow\'' in [str(x) for x in player_df.axes][0] else 'Power']:
        player_level = player_df[skill]
        if str(player_level) == 'nan':
            return 'Unknown'
        skill_n = skill_word_to_index(player_level, col_name_len)
        skill_rating_sum += 500 if skill_n == 0 else 1000 * skill_n

    return player_df['Rating'] - skill_rating_sum


def calculate_future_dates(starting_year, starting_week, weeks_n):
    age_years = starting_year
    age_weeks = starting_week
    weeks = []
    for week_i in range(weeks_n):
        age_weeks += 1
        if age_weeks > 14:
            age_weeks = 0
            age_years += 1
        weeks.append((age_years, age_weeks))

    return weeks


def cache_team(team_id: Union[int, str], db_file_path: str = 'data/PavilionPy.db') -> Optional[bool]:
    """
    Extracts team data from HTML content and adds it to the database.

    Parameters:
    - team_id (str): The unique identifier of the team.
    - html_content (str): HTML content as a string.
    - db_file_path (str): Path to the SQLite database file.

    Returns:
    - Optional[bool]: True if the operation was successful, None otherwise.
    """

    if not os.path.exists(db_file_path):
        create_table_sql = "CREATE TABLE IF NOT EXISTS teams (TeamID TEXT, TeamName TEXT, ManagerName TEXT, ManagerMembership BOOLEAN, TeamRegionID TEXT, TeamGroundName TEXT, DataSeason INTEGER, DataTimeStamp TEXT)"
        try:
            with sqlite3.connect(db_file_path) as conn:
                cursor = conn.cursor()
                cursor.execute(create_table_sql)
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")
            return None

    if int(team_id) in range(3001, 3019) or int(team_id) in range(3021, 3039):
        browser.rbrowser.open(f'https://www.fromthepavilion.org/natclub.htm?teamId={team_id}')
    else:
        browser.rbrowser.open(f'https://www.fromthepavilion.org/club.htm?teamId={team_id}')
    html_content = str(browser.rbrowser.parsed)
    soup = BeautifulSoup(html_content, 'html.parser')

    manager_name_match = soup.find('th', string="Manager").find_next_sibling('td')
    manager_name = manager_name_match.get_text(strip=True) if manager_name_match else None

    membership_title = "This manager is a Pavilion Member."
    manager_is_member_match = manager_name_match.find('img', title=membership_title) if manager_name_match else None
    manager_is_member = manager_is_member_match is not None

    team_name_match = soup.find('h1').find('a', href=re.compile(r"club\.htm\?teamId=" + re.escape(str(team_id))))
    team_name = team_name_match.get_text(strip=True) if team_name_match else None

    if int(team_id) in range(3001, 3019) or int(team_id) in range(3021, 3039):
        n = int(str(team_id)[-2:])
        if n > 20:
            n -= 20
        team_region_id = n
    else:
        country_region_link = soup.find(lambda tag: tag.name == "th" and "Country" in tag.text).find_next_sibling('td').find('a')
        team_region_id = re.search(r"regionId=(\d+)", country_region_link['href']).group(1) if country_region_link else None

    season_week_clock = soup.find('div', id='season-week-clock')
    data_season = re.findall(r"Season (\d+)", season_week_clock.get_text())[0] if season_week_clock else None

    team_ground_name_match = soup.find('th', text=re.compile(r'^Ground:?$')).find_next_sibling('td')
    team_ground_name = team_ground_name_match.get_text(strip=True) if team_ground_name_match else None

    data_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
    try:
        with sqlite3.connect(db_file_path) as conn:
            cursor = conn.cursor()
            insert_query = "INSERT INTO teams (TeamID, TeamName, ManagerName, ManagerMembership, TeamRegionID, TeamGroundName, DataSeason, DataTimeStamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(insert_query, (team_id, team_name, manager_name, manager_is_member, team_region_id, team_ground_name, data_season, data_timestamp))
            conn.commit()

            CoreUtils.log_event(f'{team_name} ({team_id}) has been added to the teams database.')

            return True
    except sqlite3.Error as e:
        CoreUtils.log_event(f"Teams database error: {e}")
        return None


def load_config(config_file_path: str, schema_file_path: str = "data/schema/archive_types.json") -> Optional[Dict]:
    """
    Loads and validates a configuration file for an archive

    Parameters:
    - config_file_path (str): Path to the JSON configuration file.
    - schema_file_path (str): Path to the JSON schema file, defaults to archive_types schema.

    Returns:
    - Optional[Dict]: The validated configuration data, or None if validation fails.
    """
    try:
        with open(schema_file_path, 'r') as schema_file:
            schema = json.load(schema_file)

        with open(config_file_path, 'r') as config_file:
            config_data = json.load(config_file)

        validate(instance=config_data, schema=schema)

        return config_data

    except (json.JSONDecodeError, jsonschema.exceptions.ValidationError, FileNotFoundError) as e:
        print(f"Error loading configuration: {e}")
        return None


def get_team_info(team_id: str, attribute: str, season: Optional[int] = None, db_file_path: str = 'data/PavilionPy.db') -> Optional[str]:
    """
    Retrieves specific attribute information for a team from a database based on the given team ID and season.
    If the team or database does not exist for the specified season, it triggers a function to download and add the team.

    Parameters:
    - team_id (str): The unique identifier of the team.
    - attribute (str): The attribute of the team to be retrieved.
    - season (Optional[int]): The season to retrieve information from, defaults to the latest season.
    - db_file_path (str): Path to the SQLite database file, defaults to 'data/PavilionPy.db'.

    Returns:
    - Optional[str]: The requested attribute's value for the specified team and season, or None if not found.
    """

    table_name = 'teams'
    columns = ["TeamID", "TeamName", "ManagerName", "TeamRegionID", "TeamGroundName", "DataSeason", "DataTimeStamp"]

    if not os.path.exists(db_file_path):
        cache_team(team_id, db_file_path=db_file_path)
        return get_team_info(team_id, attribute, season, db_file_path)

    try:
        with sqlite3.connect(db_file_path) as conn:
            cursor = conn.cursor()

            # If season is not specified, find the latest season in the database
            if season is None:
                cursor.execute(f"SELECT MAX(DataSeason) FROM {table_name}")
                season = cursor.fetchone()[0]
                # If the table has no data
                if season is None:
                    cache_team(team_id, db_file_path=db_file_path)
                    return get_team_info(team_id, attribute, None, db_file_path)

            # Now query for the team information in the specified season
            query = f"SELECT {', '.join(columns)} FROM {table_name} WHERE TeamID = ? AND DataSeason = ?"
            cursor.execute(query, (team_id, season))
            row = cursor.fetchone()

            if row is not None:
                team_info = dict(zip(columns, row))
                return team_info.get(attribute, None)
            else:
                # If team not found for the given season, download new information
                cache_team(team_id, db_file_path=db_file_path)
                return get_team_info(team_id, attribute, season, db_file_path)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None


def get_database_from_name(db_name: str, default_directory: str = 'data/archives/',
                           return_type: str = 'file', file_extension: str = 'no_extension') -> Optional[str]:
    """
    Constructs and returns a path to a database file or its containing folder.

    Parameters:
    - db_name (str): The name or path of the database.
    - default_directory (str): The default directory for the database files.
    - return_type (str): The type of return value ('file' or 'folder').
    - file_extension (str): The file extension of the database.

    Returns:
    - str: The path to the database file or folder, or None if input is invalid.
    """

    if not db_name:
        return None

    if '/' not in db_name:
        db_name = os.path.join(default_directory, db_name, f"{db_name}.{file_extension}")

    if file_extension == 'no_extension':
        db_name = f"{os.path.splitext(db_name)[0]}"
    else:
        if not db_name.endswith(f".{file_extension}"):
            db_name = f"{os.path.splitext(db_name)[0]}.{file_extension}"

    if return_type == 'folder':
        db_name = os.path.dirname(db_name)

    return db_name


def add_timestamp_info(df: pd.DataFrame, html_content: str) -> pd.DataFrame:
    """
    Extracts timestamp, season, and week information from HTML content and adds it to the DataFrame.

    Parameters:
    - df (pd.DataFrame): The DataFrame to which the extracted information will be added.
    - html_content (str): The HTML content containing timestamp, season, and week information.

    Returns:
    - pd.DataFrame: The input DataFrame with the added columns:
      'DataTimestamp' (str): Current timestamp in UTC.
      'DataSeason' (int): Extracted season number from the HTML content.
      'DataWeek' (int): Extracted week number from the HTML content.
    """

    timestr = re.findall('Week [0-9]+, Season [0-9]+', html_content)[0]
    week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]

    df['DataTimestamp'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%S')
    df['DataSeason'] = int(season)
    df['DataWeek'] = int(week)

    return df


def expand_player_ages(df: pd.DataFrame) -> pd.DataFrame:
    """
    Processes the 'Age' column in a pandas DataFrame, adding detailed age components.

    Parameters:
    - df (pd.DataFrame): DataFrame with an 'Age' column.

    Returns:
    - pd.DataFrame: The input DataFrame with additional columns:
      'AgeYear' (int): The year component of the age.
      'AgeWeeks' (int): The weeks component as a part of the year.
      'AgeDisplay' (float): The rounded age to two decimal places.
      'AgeValue' (float): Combined age in years and weeks as a single number.
    """
    df['AgeYear'] = [int(str(round(float(pl['Age']), 2)).split('.')[0]) for i, pl in df.iterrows()]
    df['AgeWeeks'] = [int(str(round(float(pl['Age']), 2)).split('.')[1]) for i, pl in df.iterrows()]
    df['AgeDisplay'] = [round(player_age, 2) for player_age in df['Age']]
    df['AgeValue'] = [y + (w / 15) for y, w in zip(df['AgeYear'], df['AgeWeeks'])]

    return df


def convert_text_to_numeric_skills(df):
    skill_columns = ['Endurance', 'Batting', 'Bowling', 'Technique', 'Power', 'Keeping', 'Fielding', 'Experience',
                     'Captaincy', 'Form',
                     'SummaryBat', 'SummaryBowl', 'SummaryKeep',
                     'SummaryAllr']
    for col in skill_columns:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str).map(SKILL_LEVELS_MAP.get)

    return df


def get_team_page(teamid):
    browser.rbrowser.open('https://www.fromthepavilion.org/club.htm?teamId={}'.format(teamid))
    page = str(browser.rbrowser.parsed)

    return page

def get_transfer_history_page(player_id):
    transfer_history_url = f'https://www.fromthepavilion.org/playertransfers.htm?playerId={player_id}'
    browser.rbrowser.open(transfer_history_url)
    page = str(browser.rbrowser.parsed)
    return page


def extract_recent_transaction_details(player_id, estimated_deadline='now', page=None):
    if page is None:
        page = get_transfer_history_page(player_id)

    transfer_history_table = pd.read_html(StringIO(page))[0]

    if estimated_deadline == 'now':
        estimated_deadline = datetime.datetime.utcnow()

    for _, transaction in transfer_history_table.iterrows():
        completion_time_raw = transaction['Date']
        final_price_raw = transaction['Price']

        for date_format in ['%d %b. %y %H:%M', '%d %b %y %H:%M']:
            try:
                completion_time = datetime.datetime.strptime(completion_time_raw, date_format)
                break
            except ValueError:
                continue

        time_difference = abs((completion_time - estimated_deadline).seconds)
        if time_difference <= 3600:  # 1 hour threshold
            table_start = page.find('<table class="data stats tablesorter">')
            table_end = page.find('</table>', table_start) + 8
            table_html = page[table_start:table_end]

            to_team_pattern = r'<a href="club\.htm\?teamId=(\d+)">([^<]+)</a>'
            to_team_matches = re.findall(to_team_pattern, table_html)
            to_team_id = int(to_team_matches[1][0]) if len(to_team_matches) > 1 else None
            to_team_name = to_team_matches[1][1] if len(to_team_matches) > 1 else None

            final_price = int(final_price_raw.replace('$', '').replace(',', '')) if final_price_raw else None
            completion_time_string = completion_time.strftime('%Y-%m-%dT%H:%M:%S')

            return to_team_name, to_team_id, final_price, completion_time_string

    # If no close match found, return did not sell placeholder
    return ['(did not sell)', -1, -1, '1970-01-01T00:00:00']



def get_team_name(teamid, page=False):
    if not page:
        page = get_team_page(teamid)

    page = page[page.index('Add this team to your bookmarks'):]
    name_start_str = str(teamid) + '">'
    name_end_str = '</a> &gt;&gt; Club'
    team_name = page[page.index(name_start_str) + len(name_start_str):page.index(name_end_str)]

    return team_name

def get_team_region(teamid, return_type='regionid', page=False):
    if not page:
        browser.rbrowser.open('https://www.fromthepavilion.org/club.htm?teamId={}'.format(teamid))
        page = str(browser.rbrowser.parsed)

    country_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 18]
    senior_country_ids = [id + 3000 for id in country_ids]
    youth_country_ids = [id + 3020 for id in country_ids]

    if teamid in senior_country_ids + youth_country_ids:
        return teamid

    truncated_page = page[page.index('<th>Country</th>'):][:200]
    country_id = int(''.join([x for x in re.findall('regionId=[0-9]+', truncated_page)[0] if x.isdigit()]))

    if return_type == 'regionid':
        return country_id
    elif return_type == 'name':
        return nationality_id_to_name_str(country_id, True)

def country_game_start_time(region_id):
    region_names = ['Australia', 'England', 'India', 'New Zealand', 'Pakistan', 'South Africa', 'West Indies', 'Sri Lanka', 'Bangladesh', 'Zimbabwe', 'Canada', 'Scotland', 'Ireland', 'Netherlands']
    country_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 15, 18]
    region_starttimes = ['00:00', '10:00', '04:30', '22:00', '05:00', '08:00', '15:00', '05:30', '02:00', '13:00', '16:00', '09:00', '11:30', '12:00']

    if isinstance(type(region_id), type(int)):
        return region_starttimes[country_ids.index(region_id)]
    elif isinstance(type(region_id), type(str)):
        return region_starttimes[region_names.index(region_id)]


def get_player_age(player_id, page=False, return_type='Age'):
    if not page:
        page = get_player_page(player_id)

    age_pattern = r'(\d+)y(\d+)w'
    age_match = re.search(age_pattern, page)

    if age_match:
        years, weeks = age_match.groups()
        years = int(years)
        weeks = int(weeks)

        if return_type == 'Age':
            return f"{years}.{str(weeks).zfill(2)}"
        elif return_type == 'AgeDisplay':
            return f"{years}.{str(weeks).zfill(2)}"
        elif return_type == 'AgeYear':
            return years
        elif return_type == 'AgeWeeks':
            return weeks
        elif return_type == 'AgeValue':
            return years + (weeks / 15.0)
    else:
        return None


def get_player_wage(player_id, page=False, normalize_wage=False, return_type='normal'):
    if not page:
        page = get_player_page(player_id)

    player_discounted_wage = int(''.join([x for x in re.findall('[0-9]+,[0-9]+ wage' if bool(re.search('[0-9]+,[0-9]+ wage', page)) else '[0-9]+ wage', page)[0] if x.isdigit()]))
    try:
        player_discount = float(re.findall('[0-9]+\% discount', page)[0][:-10]) / 100
    except: #Discount is by .5
        player_discount = float(re.findall('[0-9]+\.[0-9]+\% discount', page)[0][:-10]) / 100
    player_WageReal = int(player_discounted_wage / (1-player_discount))

    if return_type == 'normal':
        if normalize_wage:
            return player_WageReal
        else:
            return player_discounted_wage
    elif return_type == 'tuple':
        return player_WageReal, player_discounted_wage, player_discount

def get_player_talents(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    talent_pattern = r'<span class="popuphelp" title="([^"|]+)'
    talents = re.findall(talent_pattern, page)

    first_talent = talents[0] if talents else 'None'
    second_talent = talents[1] if len(talents) > 1 else 'None'

    return first_talent, second_talent


def get_player_rating(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    rating_pattern = r'(\d{1,3}(?:,\d{3})*) rating'
    rating_match = re.search(rating_pattern, page)

    if rating_match:
        rating = rating_match.group(1).replace(',', '')
        return int(rating)
    else:
        return None


def get_match_start_time_by_region(region_id):
    region_id = str(region_id)
    match_start_times = {
        "1": {'hours': 0, 'minutes': 0},
        "2": {'hours': 10, 'minutes': 0},
        "3": {'hours': 4, 'minutes': 30},
        "4": {'hours': 22, 'minutes': 0},
        "5": {'hours': 5, 'minutes': 0},
        "6": {'hours': 8, 'minutes': 0},
        "7": {'hours': 15, 'minutes': 0},
        "8": {'hours': 5, 'minutes': 30},
        "9": {'hours': 2, 'minutes': 0},
        "10": {'hours': 13, 'minutes': 0},
        "11": {'hours': 16, 'minutes': 0},
        "12": {'hours': 15, 'minutes': 30},
        "13": {'hours': 7, 'minutes': 0},
        "14": {'hours': 9, 'minutes': 0},
        "15": {'hours': 11, 'minutes': 30},
        "16": {'hours': 6, 'minutes': 0},
        "17": {'hours': 14, 'minutes': 0},
        "18": {'hours': 12, 'minutes': 0}

    }

    return match_start_times[region_id]


import datetime

def has_training_occurred(region_id, age_group):
    """
    Determine whether training has already occurred for a given region and age group.

    Args:
    region_id (str): The identifier for a specific region.
    age_group (str): The age group category. Expected values are 'youth' or 'senior'.

    Returns:
    bool: True if the training has already occurred, False otherwise.

    Training for New Zealand occurs at 22:00 on the prior day. For other regions, training occurs on the same day.
    """

    current_utc_time = datetime.datetime.utcnow()
    current_day_of_week = current_utc_time.weekday()  # Monday is 0, Sunday is 6
    training_start_time = get_match_start_time_by_region(region_id)

    # Adjust for New Zealand's schedule
    if region_id == '4':
        # Adjust the day for New Zealand's schedule
        training_day = 6 if age_group == 'youth' else 1  # Sunday (6) for 'youth', Tuesday (1) for 'senior'
        # Adjust the hour to 22:00 of the previous day
        training_start_time['hours'] = 22
    else:
        # Standard training day: Monday (0) for 'youth', Wednesday (2) for 'senior'
        training_day = 0 if age_group == 'youth' else 2

    # Check if the current day is past the training day
    if current_day_of_week > training_day:
        return True
    # Check if the current day is before the training day
    elif current_day_of_week < training_day:
        return False
    else:
        # If it's the training day, compare the current time with the training start time
        training_datetime = current_utc_time.replace(hour=training_start_time['hours'],
                                                     minute=training_start_time['minutes'],
                                                     second=0, microsecond=0)
        return current_utc_time >= training_datetime


def get_player_experience(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    exp_pattern = r'<th>(?:Exp\.|Experience)</th><td[^>]*>(?:<[^>]+>)*([^<]+)(?:<[^>]+>)*</td>'
    exp_match = re.search(exp_pattern, page)
    experience = exp_match.group(1).strip() if exp_match else None

    return experience


def get_player_form(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    form_pattern = r'<th>Form</th><td[^>]*>(.*?)</td>'
    form_match = re.search(form_pattern, page)
    form = form_match.group(1) if form_match else None

    return form


def get_player_teamname(player_id, page=None):
    if page is None:
        page = get_player_page(player_id)

    own_page = page[page.index('<h1>'):]
    team_pattern = r'<a href="club\.htm\?teamId=(\d+)">([^<]+)</a>'
    team_match = re.search(team_pattern, own_page)

    if team_match:
        team_name = team_match.group(2)
        return team_name.strip().replace('amp;', '')
    else:
        return None



def get_player_teamid(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    own_page = page[page.index('<h1>'):]
    team_pattern = r'<a href="club\.htm\?teamId=(\d+)">([^<]+)</a>'
    team_match = re.search(team_pattern, own_page)

    if team_match:
        team_id = team_match.group(1)
        team_name = team_match.group(2)
        return team_id
    else:
        return None


def get_player_fatigue(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    fatigue_pattern = r'<th>Fatigue</th><td[^>]*class="fatigue"[^>]*>(.*?)</td>'
    fatigue_match = re.search(fatigue_pattern, page)
    fatigue = fatigue_match.group(1) if fatigue_match else None

    return fatigue

def get_player_captaincy(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    captaincy_pattern = r'<th>Captaincy</th><td[^>]*>(?:<[^>]+>)?(.*?)(?:</[^>]+>)?</td>'
    captaincy_match = re.search(captaincy_pattern, page)
    captaincy = captaincy_match.group(1).strip() if captaincy_match else None

    return captaincy


def get_player_skills_summary(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    skills_patterns = {
        "Batsman": r'<th>Batsman</th><td[^>]*>.*?>(.*?)</td>',
        "Bowler": r'<th>Bowler</th><td[^>]*>.*?>(.*?)</td>',
        "Keeper": r'<th>Keeper</th><td[^>]*>.*?>(.*?)</td>',
        "Allrounder": r'<th>Allrounder</th><td[^>]*>.*?>(.*?)</td>'
    }

    skills_summary = {}
    for skill, pattern in skills_patterns.items():
        skill_match = re.search(pattern, page)
        skill_summary = skill_match.group(1) if skill_match else None
        skills_summary[skill] = skill_summary

    return skills_summary


def calculate_player_birthweek(player):
    current_season, current_week = player['DataSeason'], player['DataWeek']
    current_age_years, current_age_weeks = player['AgeYear'], player['AgeWeeks']

    weeks_since_birth = ((current_age_years - 16) * 15) + current_age_weeks
    seasons_since_birth = weeks_since_birth // 15
    extra_weeks_since_birth = weeks_since_birth % 15

    birth_season = current_season - seasons_since_birth

    if extra_weeks_since_birth > current_week:
        birth_season -= 1
    birth_week = (current_week - extra_weeks_since_birth) % 15

    return (birth_season, birth_week)


def get_player_bowling_type(player_id, page=False):
    # Retrieve the player's page if not provided
    if not page:
        page = get_player_page(player_id)

    # Define regex pattern for bowling type, case-insensitive
    bowling_pattern = r'<p>[^<]*<span class="pipe">\|</span> (Left|Right) arm (Fast medium|Fast|Medium|Finger spin|Wrist spin)</p>'

    # Extract bowling type
    bowling_match = re.search(bowling_pattern, page, re.IGNORECASE)
    if bowling_match:
        arm, style = bowling_match.groups()
        arm_code = arm[0].lower()
        style = style.lower()  # Normalize the style for easier comparison
        style_code = ''

        if 'fast medium' in style:
            style_code = 'fm'
        elif 'fast' in style:
            style_code = 'f'
        elif 'medium' in style:
            style_code = 'm'
        elif 'finger' in style:
            style_code = 'fs'
        elif 'wrist' in style:
            style_code = 'ws'

        bowling_type = arm_code + style_code
    else:
        bowling_type = None

    return bowling_type


def get_player_batting_type(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    batting_pattern = r'<p>(Left|Right) hand batsman'

    batting_match = re.search(batting_pattern, page)
    batting_type = 'L' if batting_match and batting_match.group(1) == 'Left' else 'R'

    return batting_type

def get_player_nationality(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    player_nationality_id = re.findall('regionId=[0-9]+', page)[-1][9:]

    return player_nationality_id


def get_player_skillshifts(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    skill_names = ['Experience', 'Captaincy', 'Batting', 'Endurance', 'Bowling', 'Technique', 'Keeping', 'Power', 'Fielding']
    skills = re.findall('class="skills".{0,200}', page)
    skills = skills[:2] + skills[-7:]
    skillshifts = {}
    for skill_str, skill_name in zip(skills, skill_names):
        skill_level = None
        for possible_skill in SKILL_LEVELS:
            if possible_skill in skill_str:
                skill_level = possible_skill
                break

        if 'skillup' in skill_str:
            skillshifts[skill_name] = 1
        elif 'skilldown' in skill_str:
            skillshifts[skill_name] = -1

    return skillshifts


def get_player_summary(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    summary_names = ['BattingSum', 'BowlingSum', 'KeepingSum', 'AllrounderSum']
    skills = re.findall('class="skills".{0,200}', page)
    skills = skills[2:-7]
    summary_dir = {}
    for skill_str, summary_name in zip(skills, summary_names):
        skill_level = None
        for possible_skill in SKILL_LEVELS:
            if possible_skill in skill_str:
                skill_level = possible_skill
                break

        summary_dir[summary_name] = skill_level

    return summary_dir

def get_player_skills(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    soup = BeautifulSoup(page, 'html.parser')

    skill_names = ['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power']
    skill_dir = {}

    th_elements = soup.find_all('th')

    for th in th_elements:
        if th.text in skill_names:
            td = th.find_next_sibling('td')
            if td:
                skill_level = td.text.strip()
                skill_dir[th.text] = skill_level

    return skill_dir


def get_league_teamids(leagueid, league_format='league', knockout_round=None, ind_level=0):
    if league_format == 'knockout':
        if not isinstance(knockout_round, None):
            round_n = knockout_round
        else:
            round_n = 1
    else:
        round_n = 1

    CoreUtils.log_event('Searching for teamids in leagueid {} - round {}'.format(leagueid, round_n, ind_level=ind_level))
    gameids = get_league_gameids(leagueid, round_n=round_n, league_format=league_format)
    teamids = []
    for gameid in gameids:
        team1, team2 = get_game_teamids(gameid, ind_level=ind_level+1)
        teamids.append(team1)
        teamids.append(team2)

    CoreUtils.log_event('Successfully found {} teams.'.format(len(teamids)), ind_level=ind_level)

    return teamids

def get_team_season_matches(teamid):
    browser.rbrowser.open('https://www.fromthepavilion.org/teamfixtures.htm?teamId={}#curr'.format(teamid))
    page = str(browser.rbrowser.parsed)

    data = pd.read_html(page)[1]
    date_list = [datetime.datetime.strptime(date_str, '%d %b %Y %H:%M') for date_str in data['Date']]
    print(date_list[0], type(date_list[0]))
    data['Date'] = date_list
    print(type(data['Date']))
    data['gameId'] = set([x[7:] for x in re.findall('gameId=[0-9]+', page)])

    return data

def get_league_gameids(leagueid, round_n='latest', league_format='league'):
    if round_n == 'latest':
        round_n = 1

    if league_format == 'league':
        browser.rbrowser.open('https://www.fromthepavilion.org/leaguefixtures.htm?lsId={}'.format(leagueid))
        league_page = str(browser.rbrowser.parsed)
        league_rounds = int(max([int(r[6:]) for r in re.findall('Round [0-9]+', league_page)]))
        gameids = [g[7:] for g in re.findall('gameId=[0-9]+', league_page)]

        unique_gameids = []
        for g in gameids:
            if g not in unique_gameids:
                unique_gameids.append(g)

        games_per_round = len(unique_gameids) // league_rounds

        round_start_ind = games_per_round*(round_n-1)
        round_end_ind = round_start_ind + games_per_round

        game_ids = unique_gameids[round_start_ind:round_end_ind]

    elif league_format == 'knockout':
        browser.rbrowser.open('https://www.fromthepavilion.org/cupfixtures.htm?cupId={}&currentRound=true'.format(leagueid))
        fixtures = pd.read_html(str(browser.rbrowser.parsed))[0]
        for n, roundname in enumerate(fixtures.columns):
            if roundname[:7] == 'Round {}'.format(round_n):
                round_column_name = roundname
                break

        games_on_page = re.findall('gameId=.{0,150}', str(browser.rbrowser.parsed))
        requested_games = []
        for game in fixtures[round_column_name][::2 ** (round_n - 1)]:
            team1, team2 = game.split('vs')
            if bool(re.match('.* \([0-9]+\)', team1)):
                team1 = team1[:team1.index(' (')]
            if bool(re.match('.* \([0-9]+\)', team2)):
                team2 = team2[:team2.index(' (')]

            requested_games.append([team1, team2])

        requested_game_ids = []
        for game in games_on_page:
            game = game.replace(' &amp; ', ' & ')
            for team1, team2 in requested_games:
                if team1 in game and team2 in game:
                    requested_game_ids.append(''.join([c for c in game[:game.index('>')] if c.isdigit()]))

        game_ids = requested_game_ids

    CoreUtils.log_event('Found {} games in round {} of {}'.format(len(game_ids), round_n, leagueid))

    return game_ids


def get_game_scorecard_table(gameid, ind_level=0):
    browser.rbrowser.open('https://www.fromthepavilion.org/scorecard.htm?gameId={}'.format(gameid))
    scorecard_tables = pd.read_html(str(browser.rbrowser.parsed))
    page_teamids = [''.join([c for c in x if c.isdigit()]) for x in re.findall('teamId=[0-9]+', str(browser.rbrowser.parsed))]
    home_team_id, away_team_id = page_teamids[21], page_teamids[22]
    scorecard_tables[-2].iloc[0][1] = home_team_id
    scorecard_tables[-2].iloc[1][1] = away_team_id

    CoreUtils.log_event('Downloaded scorecard for game {}'.format(gameid), ind_level=ind_level)

    return scorecard_tables


def get_game_teamids(gameid, ind_level=0):
    browser.rbrowser.open('https://www.fromthepavilion.org/gamedetails.htm?gameId={}'.format(gameid))
    page_teamids = [''.join([c for c in x if c.isdigit()]) for x in re.findall('teamId=[0-9]+', str(browser.rbrowser.parsed))]
    home_team_id, away_team_id = page_teamids[22], page_teamids[23]

    CoreUtils.log_event('Found teams for game {} - {} vs {}'.format(gameid, home_team_id, away_team_id), ind_level=ind_level)

    return (home_team_id, away_team_id)