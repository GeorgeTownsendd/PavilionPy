import argparse
import sqlite3
import os
import json
import jsonschema
import re
import pytz
import time
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from jsonschema import validate
from typing import Tuple, Dict, Optional, List

import CoreUtils
ftpbrowser = CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser

import FTPUtils
from FTPUtils import SKILL_LEVELS, SKILL_LEVELS_MAP
#SKILL_LEVELS = ['atrocious', 'dreadful', 'poor', 'ordinary', 'average', 'reasonable', 'capable', 'reliable', 'accomplished', 'expert', 'outstanding', 'spectacular', 'exceptional', 'world class', 'elite', 'legendary']
#SKILL_LEVELS_MAP = {level: index for index, level in enumerate(SKILL_LEVELS)}


def get_database_from_name(db_name: str, default_directory: str = 'data/archives/',
                           return_type: str = 'file', file_extension: str = 'db') -> Optional[str]:
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

        # Placeholder for later implementation
        players_df['CountryOfResidence'] = -1
        players_df['TrainingWeek'] = -1

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
            skill_columns = ['Endurance', 'Batting', 'Bowling', 'Technique', 'Power', 'Keeping', 'Fielding', 'Experience', 'Captaincy',
                            'SummaryBat', 'SummaryBowl', 'SummaryKeep',
                             'SummaryAllr']
            for col in skill_columns:
                if col in players_df.columns:
                    players_df[col] = players_df[col].fillna('').astype(str).map(SKILL_LEVELS_MAP.get)

        players_df.drop(columns=[x for x in ['#', 'Unnamed: 18', 'Current Bid', 'BT', 'Age'] if x in players_df.columns], inplace=True)

        # COLUMN REORDERING
        with open(f'data/schema/{column_ordering_keyword}.txt', 'r') as file:
            column_order = [line.strip() for line in file if line.strip() in players_df.columns]

        extra_columns = [col for col in players_df.columns if col not in column_order]
        final_column_order = column_order + extra_columns
        players_df = players_df[final_column_order]

        return players_df

    except Exception as e:
        CoreUtils.log_event(f"Error in transfer_market_search: {e}")
        return None


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
                            'Fatigue', 'Captaincy', 'Summary', 'TeamName', 'TeamID'],
            'Talents': ['Talent1', 'Talent2'],
            'Wage': ['WageReal', 'WagePaid', 'WageDiscount'],
            'Summary': ['SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr']
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

            elif column_name == 'SpareRating':
                player_data.append(
                    FTPUtils.get_player_spare_ratings(player_df[player_df['PlayerID'] == player_id].iloc[0]))

            elif column_name == 'SkillShift':
                skillshifts = FTPUtils.get_player_skillshifts(player_id, page=player_page)
                player_data.append('-'.join(skillshifts.keys()) if len(skillshifts.keys()) >= 1 else None)

            else:
                player_data.append('UnknownColumn')

        all_player_data.append(player_data)

    for n, column_name in enumerate(column_types):
        values = [v[n] for v in all_player_data]
        if column_name in player_df.columns:
            player_df[column_name] = values
        else:
            player_df.insert(3, column_name, values)

    return player_df


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

    retries = 0
    current_delay = retry_delay

    while True:
        try:
            ftpbrowser.check_login(active_check=True)
            players = transfer_market_search(additional_columns=['all_visible'], players_to_download=max_players_per_download)

            if players is not None:
                database_exists = os.path.exists(db_file)
                with sqlite3.connect(db_file) as conn:
                    if not database_exists:
                        players.to_sql('players', conn, if_exists='append', index=False)
                        added_players_count = len(players)
                        filtered_players_count = 0
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

                        # Filter players based on recent entry check
                        players_to_add = players[
                            ~players['PlayerID'].apply(lambda x: check_recent_entry(x, recent_players))]
                        players_to_add.to_sql('players', conn, if_exists='append', index=False)

                        added_players_count = len(players_to_add)
                        filtered_players_count = len(players) - added_players_count

                latest_deadline = max([datetime.strptime(player_deadline, '%Y-%m-%dT%H:%M:%S')
                                       for player_deadline in list(players['Deadline'].values)]) - timedelta(minutes=2)
                wait_time = (latest_deadline - datetime.utcnow()).total_seconds()
                wait_time = max(wait_time, 0)

                CoreUtils.log_event(f'{added_players_count} players have been added to the database.' + (
                    f' {filtered_players_count} recent duplicates were filtered out due to already existing in the database. ' if filtered_players_count > 0 else ''), ind_level=1)

                CoreUtils.log_event(f'The next update is in {int(wait_time // 3600)} hours, {int((wait_time % 3600) // 60)} minutes, and {int(wait_time % 60)} seconds, at {latest_deadline.strftime("%Y-%m-%d %H:%M:%S")}.', ind_level=1)

                time.sleep(wait_time)

                retries = 0
                current_delay = retry_delay  # Reset the delay after a successful operation
            else:
                CoreUtils.log_event('Failed to retrieve data from the transfer market.')
                raise ValueError('Data retrieval failed')

        except Exception as e:
            CoreUtils.log_event(f'Error occurred: {str(e)}. Retrying in {current_delay} seconds.')

            retries += 1
            if retries > max_retries:
                CoreUtils.log_event('Maximum retries reached. Stopping the monitoring.')
                break

            time.sleep(current_delay)
            current_delay = min(current_delay * delay_factor, max_delay)  # Increase delay and cap it at max_delay


if __name__ == "__main__":
    #players = transfer_market_search(additional_columns=['all_visible'])

    database_name = 'market_archive'
    database_file_dir = get_database_from_name(database_name, file_extension='')
    market_archive_config = load_config(f'{database_file_dir}json')

    watch_transfer_market(f'{database_file_dir}db', max_players_per_download=1)