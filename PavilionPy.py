import sqlite3
import os
import json
import jsonschema
import re
import time
import uuid
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from jsonschema import validate
from typing import Dict, Optional, List, Union

import CoreUtils
ftpbrowser = CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser

import FTPUtils
from FTPUtils import SKILL_LEVELS_MAP


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


def download_and_add_team(team_id: Union[int, str], db_file_path: str = 'data/PavilionPy.db') -> Optional[bool]:
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

    browser.open(f'https://www.fromthepavilion.org/club.htm?teamId={team_id}')
    html_content = str(browser.parsed)

    soup = BeautifulSoup(html_content, 'html.parser')

    manager_name_match = soup.find('th', string="Manager").find_next_sibling('td')
    manager_name = manager_name_match.get_text(strip=True) if manager_name_match else None

    membership_title = "This manager is a Pavilion Member."
    manager_is_member_match = manager_name_match.find('img', title=membership_title) if manager_name_match else None
    manager_is_member = manager_is_member_match is not None

    team_name_match = soup.find('h1').find('a', href=re.compile(r"club\.htm\?teamId=" + re.escape(str(team_id))))
    team_name = team_name_match.get_text(strip=True) if team_name_match else None

    country_region_link = soup.find(lambda tag: tag.name == "th" and "Country" in tag.text).find_next_sibling('td').find('a')
    team_region_id = re.search(r"regionId=(\d+)", country_region_link['href']).group(1) if country_region_link else None

    season_week_clock = soup.find('div', id='season-week-clock')
    data_season = re.findall(r"Season (\d+)", season_week_clock.get_text())[0] if season_week_clock else None

    team_ground_name_match = soup.find('th', string="Ground").find_next_sibling('td')
    team_ground_name = team_ground_name_match.get_text(strip=True) if team_ground_name_match else None

    data_timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
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
        download_and_add_team(team_id, db_file_path=db_file_path)
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
                    download_and_add_team(team_id, db_file_path=db_file_path)
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
                download_and_add_team(team_id, db_file_path=db_file_path)
                return get_team_info(team_id, attribute, season, db_file_path)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None


def transfer_market_search(search_settings: Dict = {}, additional_columns: Optional[List[str]] = None,
                           skill_level_format: str = 'numeric', column_ordering_keyword: str = 'col_ordering_transfer', players_to_download: int = 20) -> Optional[pd.DataFrame]:
    """
    Searches the transfer market for players based on given search settings, processes the data,
    and returns a pandas DataFrame.

    Parameters:
    - search_settings (Dict): A dictionary of search settings for the transfer market.
    - additional_columns (Optional[List[str]]): List of additional columns to add to the DataFrame, if any.
    - skill_level_format (str): Format for skill levels, 'numeric' by default.
    - column_ordering_keyword (str): Specification file for the ordering of columns in the returned DataFrame, 'col_ordering_transfer' by default.
    - players_to_download (int): Players to return, or to download when adding additional columns, useful for testing. Defaults to 20, or one transfer market page.

    Returns:
    - Optional[pd.DataFrame]: A DataFrame containing the transfer market data, or None if the search fails.
    """
    try:
        CoreUtils.log_event(f"Searching for players on the transfer market..." + (
            f" Additional search filters: {search_settings}" if search_settings else ""))

        url = 'https://www.fromthepavilion.org/transfer.htm'
        browser.open(url)
        search_settings_form = browser.get_form()
        for setting in search_settings.keys():
            search_settings_form[setting] = str(search_settings[setting])
        browser.submit_form(search_settings_form)
        html_content = str(browser.parsed)

        players_df = pd.read_html(StringIO(html_content))[0]

        # Process transfer_market data
        del players_df['Nat']
        player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', html_content)][::2]
        region_ids = [x[9:] for x in re.findall('regionId=[0-9]+', html_content)][9:]
        bidding_team_ids = [x[7:] for x in re.findall('teamId=[0-9]+', html_content[html_content.index('Transfer Search Results'):])]

        players_df.insert(loc=3, column='Nationality', value=region_ids)
        players_df.insert(loc=1, column='PlayerID', value=player_ids)

        # Convert to ISO8601 for database
        players_df['Deadline'] = [deadline[:-5] + ' ' + deadline[-5:] for deadline in players_df['Deadline']]
        players_df['Deadline'] = pd.to_datetime(players_df['Deadline'], format='%d %b. %Y %H:%M').dt.strftime('%Y-%m-%dT%H:%M:%S')

        cur_bids_full = [bid for bid in players_df['Current Bid']]
        split_bids = [b.split(' ', 1) for b in cur_bids_full]
        bids = [b[0] for b in split_bids]

        bid_ints = [int(''.join([x for x in b if x.isdigit()])) for b in bids]
        players_df['CurrentBid'] = pd.Series(bid_ints)
        team_names = pd.Series([b[1].replace(' ', '') for b in split_bids])
        players_df.insert(loc=3, column='BiddingTeam', value=team_names)

        bidding_team_ids_filled = []
        k = 0
        for bidding_team in players_df['BiddingTeam']:
            if bidding_team == '(opening)':
                bidding_team_ids_filled.append(-1)
            else:
                bidding_team_ids_filled.append(bidding_team_ids[k])
                k += 1

        players_df.insert(loc=3, column='BiddingTeamID', value=bidding_team_ids_filled)

        # ---
        timestr = re.findall('Week [0-9]+, Season [0-9]+', str(browser.parsed))[0]
        week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]

        players_df['AgeYear'] = [int(str(round(float(pl['Age']), 2)).split('.')[0]) for i, pl in players_df.iterrows()]
        players_df['AgeWeeks'] = [int(str(round(float(pl['Age']), 2)).split('.')[1]) for i, pl in players_df.iterrows()]
        players_df['AgeDisplay'] = [round(player_age, 2) for player_age in players_df['Age']]
        players_df['AgeValue'] = [y + (w / 15) for y, w in zip(players_df['AgeYear'], players_df['AgeWeeks'])]

        players_df['DataTimestamp'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%S')
        players_df['DataSeason'] = int(season)
        players_df['DataWeek'] = int(week)
        players_df['TransactionID'] = [str(uuid.uuid4()) for x in range(len(players_df))]

        # Reduce players to reduce bandwith when testing
        players_df = players_df[:players_to_download]

        # This will iterate through each players page. There is more information, but less efficient than just fetching
        # is available from the transfer market page
        if additional_columns:
            players_df = add_player_columns(players_df, additional_columns)

        rename_dict = {
            "Bat": "Batting",
            "Bowl": "Bowling",
            "Tech": "Technique",
            "Pow": "Power",
            "Keep": "Keeping",
            "Field": "Fielding",
            "End": "Endurance"
        }

        players_df.rename(columns=rename_dict, inplace=True)

        if skill_level_format == 'numeric':
            skill_columns = ['Endurance', 'Batting', 'Bowling', 'Technique', 'Power', 'Keeping', 'Fielding', 'Experience', 'Captaincy', 'Form',
                            'SummaryBat', 'SummaryBowl', 'SummaryKeep',
                             'SummaryAllr']
            for col in skill_columns:
                if col in players_df.columns:
                    players_df[col] = players_df[col].fillna('').astype(str).map(SKILL_LEVELS_MAP.get)

        players_df.drop(columns=[x for x in ['#', 'Unnamed: 18', 'Current Bid', 'BT', 'Age'] if x in players_df.columns], inplace=True)
        ordered_df = apply_column_ordering(players_df, f'data/schema/{column_ordering_keyword}.txt')

        return ordered_df

    except Exception as e:
        CoreUtils.log_event(f"Error in transfer_market_search: {e}")
        return None


def best_player_search(search_settings: Dict = {}, players_to_download: int = 30) -> Optional[pd.DataFrame]:
    """
    Searches for the best players based on given search settings, and returns a pandas DataFrame.

    Parameters:
    - search_settings (Dict): A dictionary of search settings for the best players search.
    - players_to_download (int): Number of players to return, useful for testing. Defaults to 30.

    Returns:
    - Optional[pd.DataFrame]: A DataFrame containing the best players data, or None if the search fails.
    """
    try:
        CoreUtils.log_event("Searching for best players with parameters {}".format(search_settings))

        url = 'https://www.fromthepavilion.org/playerranks.htm?regionId=1'
        browser.open(url)
        search_settings_form = browser.get_form()

        # Set default pages if not specified
        if 'pages' not in search_settings:
            search_settings['pages'] = 1

        if search_settings['pages'] == 'all':
            search_settings['pages'] = 10 # maximum pages just in case

        # Populate search settings form
        for search_setting, value in search_settings.items():
            if search_setting in ['country', 'region', 'wagesort', 'age', 'ageWeeks']:
                search_settings_form[search_setting].value = str(value)

        browser.submit_form(search_settings_form)
        all_players = []

        for page in range(int(search_settings['pages'])):
            player_ids = []
            region_ids = []
            players_df = pd.DataFrame()

            search_settings_form['page'].value = str(page)
            browser.submit_form(search_settings_form)
            html_content = str(browser.parsed)

            pageplayers_df = pd.read_html(StringIO(html_content))[1]
            players_df = pd.concat([players_df, pageplayers_df])

            page_player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', html_content)][::2]
            page_region_ids = [x[9:] for x in re.findall('regionId=[0-9]+', html_content)][20:]

            player_ids += page_player_ids
            region_ids += page_region_ids

            # Process DataFrame
            players_df.insert(loc=3, column='Nationality', value=region_ids)
            players_df.insert(loc=1, column='PlayerID', value=player_ids)
            players_df['Wage'] = players_df['Wage'].str.replace('\D+', '')

            players_df = players_df[:players_to_download]
            players_df['Player'] = players_df['Players']
            players_df = players_df[['PlayerID', 'Player', 'Age']]

            timestr = re.findall('Week [0-9]+, Season [0-9]+', str(browser.parsed))[0]
            week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]

            players_df['AgeYear'] = [int(str(round(float(pl['Age']), 2)).split('.')[0]) for i, pl in players_df.iterrows()]
            players_df['AgeWeeks'] = [int(str(round(float(pl['Age']), 2)).split('.')[1]) for i, pl in players_df.iterrows()]
            players_df['AgeDisplay'] = [round(player_age, 2) for player_age in players_df['Age']]
            players_df['AgeValue'] = [y + (w / 15) for y, w in zip(players_df['AgeYear'], players_df['AgeWeeks'])]

            players_df['DataTimestamp'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%S')
            players_df['DataSeason'] = int(season)
            players_df['DataWeek'] = int(week)

            del players_df['Age']

            players_df = add_player_columns(players_df, column_types=['all_public'])

            column_ordering_schema = 'data/schema/col_ordering_hiddenplayers.txt'
            ordered_df = apply_column_ordering(players_df, column_ordering_schema)

            all_players.append(ordered_df)

            if len(ordered_df) < 30:
                break

        all_players_df = pd.concat(all_players)

        return all_players_df

    except Exception as e:
        CoreUtils.log_event(f"Error in best_player_search: {e}")
        return None


def apply_column_ordering(df: pd.DataFrame, column_ordering_schema_file: str) -> pd.DataFrame:
    """
    Reorders the columns of a DataFrame based on a predefined column ordering schema.

    This function reads a schema file where each line contains the name of a column. It reorders the DataFrame's columns
    to match the order specified in the schema file, appending any columns present in the DataFrame but not listed in the
    schema file at the end.

    Parameters:
    - df (pd.DataFrame): The input DataFrame whose columns are to be reordered.
    - column_ordering_schema_file (str): The file path of the column ordering schema, with one column name per line.

    Returns:
    - pd.DataFrame: A new DataFrame with columns reordered as per the schema, followed by any additional columns not specified in the schema.
    """

    with open(column_ordering_schema_file, 'r') as file:
        column_order = [line.strip() for line in file if line.strip() in df.columns]

    extra_columns = [col for col in df.columns if col not in column_order]
    final_column_order = column_order + extra_columns
    df = df[final_column_order]

    return df


def add_player_columns(player_df: pd.DataFrame, column_types: List[str]) -> pd.DataFrame:
    """
    Adds additional columns to the player DataFrame based on specified column types.

    Parameters:
    - player_df (pd.DataFrame): DataFrame containing player data.
    - column_types (List[str]): List of column types to add.

    Returns:
    - pd.DataFrame: The updated DataFrame with additional columns.
    """

    column_list = column_types
    def expand_columns(column_list):
        column_groups = {
            'all_visible': ['Training', 'NatSquad', 'Touring', 'Wage', 'Talents', 'Experience', 'BowlType', 'BatHand', 'Form',
                            'Fatigue', 'Captaincy', 'Summary', 'TeamName', 'TeamID', 'TeamPage'],
            'all_public': ['Rating', 'Nationality', 'NatSquad', 'Touring', 'Wage', 'Talents', 'Experience', 'BowlType', 'BatHand', 'Form', 'Fatigue',
                            'Captaincy', 'TeamName', 'TeamID', 'TeamPage'],
            'Talents': ['Talent1', 'Talent2'],
            'Wage': ['WageReal', 'WagePaid', 'WageDiscount'],
            'Summary': ['SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr'],
            'TeamPage': ['CountryOfResidence', 'TrainedThisWeek']
        }

        expanded_set = set()
        for item in column_list:
            if item in column_groups:
                expanded_set.update(expand_columns(column_groups[item]))
            else:
                expanded_set.add(item)

        return expanded_set

    column_types = expand_columns(column_list)

    all_player_data = []

    for player_id in player_df['PlayerID']:
        player_data = []
        player_page = None

        if any(col for col in column_types if col != 'Training'):
            browser.open(f'https://www.fromthepavilion.org/player.htm?playerId={player_id}')
            player_page = str(browser.parsed)

        for column_name in column_types:
            if 'Wage' in column_name:
                WageReal, WagePaid, WageDiscount = FTPUtils.get_player_wage(player_id, page=player_page, return_type='tuple')
                break

        for column_name in column_types:
            if 'Talent' in column_name:
                talent1, talent2 = FTPUtils.get_player_talents(player_id, player_page)
                break

        for column_name in column_types:
            if column_name == 'Training':
                browser.open(f'https://www.fromthepavilion.org/playerpopup.htm?playerId={player_id}')
                html_content = str(browser.parsed)
                popup_page_info = pd.read_html(StringIO(html_content))
                try:
                    training_selection = popup_page_info[0][3][9]
                except KeyError:
                    training_selection = 'Hidden'
                player_data.append(training_selection)

            elif column_name == 'Experience':
                player_experience = FTPUtils.get_player_experience(player_id, player_page)
                player_data.append(player_experience)

            elif column_name == 'Form':
                player_form = FTPUtils.get_player_form(player_id, player_page)
                player_data.append(player_form)

            elif column_name == 'Fatigue':
                player_fatigue = FTPUtils.get_player_fatigue(player_id, player_page)
                player_data.append(player_fatigue)

            elif column_name == 'TeamName':
                player_teamname = FTPUtils.get_player_teamname(player_id, player_page)
                player_data.append(player_teamname)

            elif column_name == 'TeamID':
                player_teamid = FTPUtils.get_player_teamid(player_id, player_page)
                player_data.append(player_teamid)

            elif column_name == 'Captaincy':
                player_captaincy = FTPUtils.get_player_captaincy(player_id, player_page)
                player_data.append(player_captaincy)

            elif column_name == 'BatHand':
                player_bathand = FTPUtils.get_player_batting_type(player_id, player_page)
                player_data.append(player_bathand)

            elif column_name == 'BowlType':
                player_BT = FTPUtils.get_player_bowling_type(player_id, player_page)
                player_data.append(player_BT)

            elif column_name == 'SummaryBat':
                player_skill_summary = FTPUtils.get_player_skills_summary(player_id, player_page)
                player_data.append(player_skill_summary['Batsman'])

            elif column_name == 'SummaryBowl':
                player_skill_summary = FTPUtils.get_player_skills_summary(player_id, player_page)
                player_data.append(player_skill_summary['Bowler'])

            elif column_name == 'SummaryKeep':
                player_skill_summary = FTPUtils.get_player_skills_summary(player_id, player_page)
                player_data.append(player_skill_summary['Keeper'])

            elif column_name == 'SummaryAllr':
                player_skill_summary = FTPUtils.get_player_skills_summary(player_id, player_page)
                player_data.append(player_skill_summary['Allrounder'])

            elif column_name == 'Nationality':
                player_nationality_id = FTPUtils.get_player_nationality(player_id, player_page)
                player_data.append(player_nationality_id)

            elif column_name == 'Rating':
                player_rating = FTPUtils.get_player_rating(player_id, player_page)
                player_data.append(player_rating)

            elif column_name == 'Talent1':
                player_data.append(talent1)

            elif column_name == 'Talent2':
                player_data.append(talent2)

            elif column_name == 'WageReal':
                player_data.append(WageReal)

            elif column_name == 'WagePaid':
                player_data.append(WagePaid)

            elif column_name == 'WageDiscount':
                player_data.append(WageDiscount)

            elif column_name == 'NatSquad':
                if 'This player is a member of the national squad' in player_page:
                    player_data.append(True)
                else:
                    player_data.append(False)

            elif column_name == 'Touring':
                if 'This player is on tour with the national team' in player_page:
                    player_data.append(True)
                else:
                    player_data.append(False)

            elif column_name == 'TeamID':
                player_teamid = FTPUtils.get_player_teamid(player_id, player_page)
                player_data.append(player_teamid)

            elif column_name == 'CountryOfResidence':
                player_teamid = FTPUtils.get_player_teamid(player_id, player_page)
                player_country_of_residence = get_team_info(player_teamid, 'TeamRegionID')
                player_data.append(player_country_of_residence)

            elif column_name == 'TrainedThisWeek':
                player_teamid = FTPUtils.get_player_teamid(player_id, player_page)
                player_country_of_residence = get_team_info(player_teamid, 'TeamRegionID')

                age_group = 'youth' if player_df[player_df['PlayerID'] == player_id].iloc[0]['AgeYear'] < 21 else 'senior'
                trained = FTPUtils.has_training_occured(player_country_of_residence, age_group)
                player_data.append(trained)

            else:
                player_data.append('UnknownColumn')

        all_player_data.append(player_data)

    for n, column_name in enumerate(column_types):
        values = [v[n] for v in all_player_data]
        if column_name in player_df.columns:
            player_df[column_name] = values
        else:
            player_df.insert(1, column_name, values)

    return player_df


def get_team_players(teamid, age_group='all', squad_type='domestic_team', ind_level=0):
    if int(teamid) in range(3001, 3019) or int(teamid) in range(3021, 3039) and squad_type == 'domestic_team':
        squad_type = 'national_team'

    if age_group == 'all':
        age_group = 0
    elif age_group == 'seniors':
        age_group = 1
    elif age_group == 'youths':
        age_group = 2

    squad_url = ('https://www.fromthepavilion.org/natsquad.htm?squadViewId=2&orderBy=15&teamId={}&playerType={}'
                 if squad_type == 'national_team' else
                 'https://www.fromthepavilion.org/seniors.htm?squadViewId=2&orderBy=&teamId={}&playerType={}')
    squad_url = squad_url.format(teamid, age_group)

    try:
        CoreUtils.log_event(f'Downloading players from teamid {teamid}', ind_level=ind_level)
        browser.open(squad_url)
        html_content = str(browser.parsed)
        team_players = pd.read_html(StringIO(html_content))[0]

        team_players['PlayerID'] = [x[9:] for x in re.findall('playerId=[0-9]+', html_content)][::2]
        team_players['WageReal'] = team_players['Wage'].str.replace('\D+', '')
        team_players['AgeDisplay'] = team_players['Age']

        if squad_type == 'domestic_team':
            team_players['Nationality'] = [x[-2:].replace('=', '') for x in re.findall('regionId=[0-9]+', html_content)][-len(team_players['PlayerID']):]

        team_players['AgeYear'] = [int(str(round(float(pl['Age']), 2)).split('.')[0]) for i, pl in team_players.iterrows()]
        team_players['AgeWeeks'] = [int(str(round(float(pl['Age']), 2)).split('.')[1]) for i, pl in team_players.iterrows()]
        team_players['AgeDisplay'] = [round(player_age, 2) for player_age in team_players['Age']]
        team_players['AgeValue'] = [y + (w / 15) for y, w in zip(team_players['AgeYear'], team_players['AgeWeeks'])]

        team_players.drop(columns=['Age', 'Nat', '#', 'BT', 'Exp', 'Fatg', 'Wage'], inplace=True)

        team_players = add_player_columns(team_players, column_types=['all_public'])
        team_players = apply_column_ordering(team_players, 'data/schema/col_ordering_hiddenplayers.txt')

        # Add timestamp and season/week information
        timestr = re.findall('Week [0-9]+, Season [0-9]+', html_content)[0]
        week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]
        team_players['DataTimestamp'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%dT%H:%M:%S')
        team_players['DataSeason'] = int(season)
        team_players['DataWeek'] = int(week)

        CoreUtils.log_event('Completed downloading team players', ind_level=ind_level)

    except Exception as e:
        CoreUtils.log_event(f'Error fetching team players: {e}', ind_level=ind_level)
        raise

    return team_players


def watch_transfer_market(db_file, retry_delay=60, max_retries=10, delay_factor=2.0, max_delay=3600, max_players_per_download=20):
    """
    Continuously monitors and updates the database with player information from the transfer market.

    Parameters:
    - db_file (str): Path to the SQLite database file.
    - retry_delay (int): Initial delay in seconds before retrying after a failure, defaults to 60.
    - max_retries (int): Maximum number of retries after consecutive failures, defaults to 10.
    - delay_factor (float): Factor by which the delay increases after each failure, defaults to 2.0.
    - max_delay (int): Maximum delay in seconds, defaults to 3600.
    - max_players_per_download (int): Maximum players to download and add to the database at once, defaults to 20 (one page on the transfer market).
    """

    if not ('.' in db_file): # db_file is not a filename, and instead a archive name
        database_file_dir = get_database_from_name(db_file)
        #database_config = load_config(f'{database_file_dir}.json')
        db_file = f'{database_file_dir}.db'

    retries = 0
    current_delay = retry_delay

    while True:
        try:
            ftpbrowser.check_login(active_check=True)
            players = transfer_market_search(additional_columns=['all_visible'], players_to_download=max_players_per_download)

            if players is not None:
                database_exists = os.path.exists(db_file)
                with sqlite3.connect(db_file) as conn:
                    # Check for 'transactions' table and create it if it doesn't exist
                    conn.execute('CREATE TABLE IF NOT EXISTS transactions (TransactionID TEXT, Player TEXT, PlayerID INTEGER, FromTeamName TEXT, FromTeamID INTEGER, ToTeamName TEXT, ToTeamID INTEGER, FinalPrice REAL, CompletionTime TEXT)')
                    conn.commit()

                    if not database_exists:
                        players.to_sql('players', conn, if_exists='append', index=False)
                        n_added_players = len(players)
                        n_filtered_players = 0
                    else:
                        # ENSURE PLAYERS ARE NOT ADDED MANY TIMES IN THE SAME WEEK BY SEQUENTIAL TRANSFER DOWNLOADS
                        # Retrieve existing players with their latest timestamp
                        recent_players_query = "SELECT PlayerID, MAX(DataTimestamp) FROM players GROUP BY PlayerID"
                        recent_players_df = pd.read_sql_query(recent_players_query, conn)
                        recent_players = {
                            row['PlayerID']: datetime.strptime(row['MAX(DataTimestamp)'], '%Y-%m-%dT%H:%M:%S')
                            for index, row in recent_players_df.iterrows()}

                        def check_recent_entry(player_id, recent_players):
                            if player_id in recent_players:
                                last_timestamp = recent_players[player_id]
                                if (datetime.now() - last_timestamp).days < 2:
                                    return True
                            return False

                        players_to_add = players[~players['PlayerID'].apply(lambda x: check_recent_entry(x, recent_players))]
                        players_to_add.to_sql('players', conn, if_exists='append', index=False)

                        n_added_players = len(players_to_add)
                        n_filtered_players = len(players) - n_added_players

                CoreUtils.log_event(f'{n_added_players} players have been added to the database.' + (
                    f' {n_filtered_players} recent duplicates were filtered out due to already existing in the database. ' if n_filtered_players > 0 else ''), ind_level=1)

                current_datetime = (datetime.now() - timedelta(minutes=60)).strftime('%Y-%m-%dT%H:%M:%S')
                query = f'''
                SELECT * FROM players 
                WHERE Deadline < '{current_datetime}' 
                  AND TransactionID NOT IN (SELECT TransactionID FROM transactions)
                ORDER BY Deadline 
                '''

                with sqlite3.connect(db_file) as conn2:
                    completed_transactions = pd.read_sql_query(query, conn2)

                CoreUtils.log_event(f'Retrieving final transfer status for {len(completed_transactions)} transactions...')

                all_transaction_data = []
                for n, player in completed_transactions.iterrows():
                    player_id = player['PlayerID']
                    page = FTPUtils.get_transfer_history_page(player_id)
                    transaction_data = FTPUtils.extract_recent_transaction_details(player_id, estimated_deadline=datetime.strptime(player['Deadline'], '%Y-%m-%dT%H:%M:%S'), page=page)
                    all_transaction_data.append(transaction_data)
                    time.sleep(1)

                transactions_df = pd.DataFrame({
                    'TransactionID': completed_transactions['TransactionID'].values,
                    'Player': completed_transactions['Player'].values,
                    'PlayerID': completed_transactions['PlayerID'].values,
                    'FromTeamName': completed_transactions['TeamName'].values,
                    'FromTeamID': completed_transactions['TeamID'].values,
                    'ToTeamName': [x[0] for x in all_transaction_data],
                    'ToTeamID': [x[1] for x in all_transaction_data],
                    'FinalPrice': [x[2] for x in all_transaction_data],
                    'CompletionTime': [x[3] for x in all_transaction_data]
                })
                transactions_df.to_sql('transactions', conn, if_exists='append', index=False)
                conn.commit()

                # Continue looping
                latest_deadline = max([datetime.strptime(player_deadline, '%Y-%m-%dT%H:%M:%S')
                                       for player_deadline in list(players['Deadline'].values)]) - timedelta(minutes=2)
                wait_time = (latest_deadline - datetime.utcnow()).total_seconds()
                wait_time = max(wait_time, retry_delay)

                CoreUtils.log_event(f'The next update is in {int(wait_time // 3600)} hours, {int((wait_time % 3600) // 60)} minutes, and {int(wait_time % 60)} seconds, at {latest_deadline.strftime("%Y-%m-%d %H:%M:%S")}.', ind_level=1)

                time.sleep(wait_time)

                retries = 0
                current_delay = retry_delay  # Reset the delay after a successful operation
            else:
                CoreUtils.log_event('Failed to retrieve data from the transfer market.')
                raise ValueError('Data retrieval failed')

        except ZeroDivisionError as e:#Exception as e:
            CoreUtils.log_event(f'Error occurred: {str(e)}. Retrying in {current_delay} seconds.')

            retries += 1
            if retries > max_retries:
                CoreUtils.log_event('Maximum retries reached. Stopping the monitoring.')
                break

            time.sleep(current_delay)
            current_delay = min(current_delay * delay_factor, max_delay)  # Increase delay and cap it at max_delay


if __name__ == "__main__":
    pass
    #from FTPUtils import get_team_players
    #download_and_add_team(1066)
    #players = best_player_search(search_settings={'country': '2', 'age': '16', 'ageWeeks': '0', 'pages': 'all'})
    #players = transfer_market_search(additional_columns=['all_visible'])

    #nationalities = list(range(1, 18))
    #players_list = []

    #for n_id in nationalities:
    #    national_players = []
    #    for age_weeks in [0, 1, 2]:
    #        players_in_age = best_player_search(search_settings={'country': f'{n_id}', 'age': '16', 'ageWeeks': f'{age_weeks}', 'pages': 'all'})
    #        national_players.append(players_in_age)
    #        #players_list.append(players)
    #    all_national_players = pd.concat(national_players)

    #    with sqlite3.connect('data/u16_players_s56w03') as conn:
    #        all_national_players.to_sql('players', conn, if_exists='append', index=False)

        #players_list.append(all_national_players)

    #players = pd.concat(players_list)



    #database_file_dir = get_database_from_name('market_archive')
    #market_archive_config = load_config(f'{database_file_dir}.json')

    #watch_transfer_market(f'{database_file_dir}.db', max_players_per_download=20)