import FTPUtils
#import PresentData
import CoreUtils

browser = CoreUtils.browser

import os
import time
import datetime
import re
from io import StringIO
import pytz
import sqlite3
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
import pandas as pd
import shutil
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})
import seaborn as sns; sns.set_theme(color_codes=True)
pd.options.mode.chained_assignment = None  # default='warn'

SKILL_LEVELS_MAP = FTPUtils.SKILL_LEVELS_MAP
GLOBAL_SETTINGS = ['name', 'description', 'database_type', 'w_directory', 'archive_days', 'scrape_time', 'additional_columns']
ORDERED_SKILLS = [['ID', 'Player', 'Nationality', 'Deadline', 'Current Bid'], ['Rating', 'Exp', 'BowlType'], ['Bat', 'Bowl', 'Keep', 'Field'], ['End', 'Tech', 'Pow']]

def generate_config_file(database_settings, additional_settings):
    if database_settings['w_directory'][-1] != '/':
        database_settings['w_directory'] += '/'
    conf_file = database_settings['w_directory'] + database_settings['name'] + '.config'

    if not os.path.exists(database_settings['w_directory']):
        os.makedirs(database_settings['w_directory'])
        CoreUtils.log_event('Creating directory {}'.format(database_settings['w_directory']), logfile=['default', database_settings['w_directory'] + database_settings['name'] + '.log'])

    if os.path.isfile(conf_file):
        shutil.copy(conf_file, conf_file + '.old')
        CoreUtils.log_event('Config file {} already exisits, copying to {} and creating new file'.format(conf_file, conf_file + '.old'), logfile=['default', database_settings['w_directory'] + database_settings['name'] + '.log'])

    with open(conf_file, 'w') as f:
        for setting in GLOBAL_SETTINGS:
            try:
                f.write('{}:{}\n'.format(setting, database_settings[setting]))
            except KeyError:
                if setting in ['archive_days', 'scrape_time'] and database_settings['database_type'] == 'transfer_market_search':
                    pass
                else:
                    raise KeyError

        for setting in additional_settings.keys():
            if setting == 'teamids':
                f.write('{}:{}\n'.format(setting, ','.join([str(teamid) for teamid in additional_settings[setting]])))
            else:
                f.write('{}:{}\n'.format(setting, additional_settings[setting]))

    CoreUtils.log_event('Successfully created config file {}'.format(conf_file), logfile=['default', database_settings['w_directory'] + database_settings['name'] + '.log'])


def load_config_file(archive_name):
    archive_name = get_database_from_name(archive_name, file_extension='config')

    database_settings = {}
    additional_settings = {}
    all_file_values = {}
    with open(archive_name, 'r') as f:
        config_file_lines = [line.rstrip() for line in f.readlines()]
        for n, line in enumerate(config_file_lines):
            setting_name, value = line.split(':', 1)

            if setting_name == 'additional_columns':
                typical_column_groups = {
                    'all_visible': ['Training', 'NatSquad', 'Touring', 'Wage', 'Talents', 'Experience', 'BowlType', 'BatHand', 'Form', 'Fatigue', 'Captaincy', 'Summary'],
                    'Talents': ['Talent1', 'Talent2'],
                    'Wage': ['WageReal', 'WagePaid', 'WageDiscount'],
                    'Summary': ['SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr']
                }

                cont = 1
                while cont > 0:
                    for column_group in typical_column_groups.keys():
                        if column_group in value:
                            cont += 1
                            value = value.replace(column_group, ','.join(typical_column_groups[column_group]))

                    cont -= 1

                columns_expanded = value.split(',')
                all_file_values[setting_name] = columns_expanded

            elif setting_name in ['archive_days', 'teamids']:
                all_file_values[setting_name] = value.split(',')
            elif setting_name in ['scrape_time']:
                if ':' in value:
                    all_file_values[setting_name] = value.split(':')
                else:
                    if value in ['youthtraining', 'seniortraining', 'auto']:
                        all_file_values[setting_name] = value
            else:
                all_file_values[setting_name] = value

    for setting_name in all_file_values.keys():
        if setting_name in GLOBAL_SETTINGS:
            database_settings[setting_name] = all_file_values[setting_name]
        else:
            additional_settings[setting_name] = all_file_values[setting_name]

    return database_settings, additional_settings


def player_search(search_settings={}, to_file=False, to_database=False, search_type='transfer_market',
                  additional_columns=False, return_sort_column=False, skill_level_format='string',
                  ind_level=0, column_sort_order='standard1'):
    if search_type != 'all':
        CoreUtils.log_event('Searching {} for players with parameters {}'.format(search_type, search_settings), ind_level=ind_level)
        url = 'https://www.fromthepavilion.org/{}.htm'
        if search_type == 'transfer_market':
            url = url.format('transfer')
        elif search_type == 'nat_search':
            url = url.format('natsearch')
        else:
            CoreUtils.log_event('Invalid search_type in player_search! - {}'.format(search_type))

        browser.rbrowser.open(url)
        search_settings_form = browser.rbrowser.get_form()

        for setting in search_settings.keys():
            search_settings_form[setting] = str(search_settings[setting])

        browser.rbrowser.submit_form(search_settings_form)
        html_content = str(browser.rbrowser.parsed)
        players_df = pd.read_html(StringIO(html_content))[0]

    if search_type == 'transfer_market':
        del players_df['Nationality']
        player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', str(browser.rbrowser.parsed))][::2]
        region_ids = [x[9:] for x in re.findall('regionId=[0-9]+', str(browser.rbrowser.parsed))][9:]
        players_df.insert(loc=3, column='Nationality', value=region_ids)
        players_df.insert(loc=1, column='PlayerID', value=player_ids)
        players_df['Deadline'] = [deadline[:-5] + ' ' + deadline[-5:] for deadline in players_df['Deadline']]
        cur_bids_full = [bid for bid in players_df['Current Bid']]
        split_bids = [b.split(' ', 1) for b in cur_bids_full]
        bids = [b[0] for b in split_bids]
        team_names = pd.Series([b[1].replace(' ', '') for b in split_bids])
        bid_ints = [int(''.join([x for x in b if x.isdigit()])) for b in bids]
        players_df['Current Bid'] = pd.Series(bid_ints)
        players_df.insert(loc=3, column='Bidding Team', value=team_names)

    elif search_type == 'nat_search':
        del players_df['Unnamed: 13']
        player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', str(browser.rbrowser.parsed))][::2]
        players_df.insert(loc=1, column='PlayerID', value=player_ids)

    elif search_type == 'all':
        if 'pages' not in search_settings.keys():
            search_settings['pages'] = 1

        browser.rbrowser.open('https://www.fromthepavilion.org/playerranks.htm?regionId=1')
        search_settings_form = browser.rbrowser.get_forms()[0]

        for search_setting in ['nation', 'region', 'age', 'wagesort']:
            if search_setting in search_settings.keys():
                if search_setting == 'nation':
                    search_settings_form['country'].value = str(search_settings[search_setting])
                elif search_setting == 'region':
                    search_settings_form['region'].value = str(search_settings[search_setting])
                elif search_setting == 'wagesort':
                    search_settings_form['sortByWage'].value = str(search_settings[search_setting])
                else:
                    search_settings_form[search_setting].value = str(search_settings[search_setting])

        player_ids = []
        region_ids = []
        players_df = pd.DataFrame()

        CoreUtils.log_event('Searching for best players with parameters {}'.format(search_settings), ind_level=ind_level)
        for page in range(int(search_settings['pages'])):
            search_settings_form['page'].value = str(page)
            browser.rbrowser.submit_form(search_settings_form)

            pageplayers_df = pd.read_html(str(browser.rbrowser.parsed))[1]
            players_df = players_df.append(pageplayers_df)

            page_player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', str(browser.rbrowser.parsed))][::2]
            page_region_ids = [x[9:] for x in re.findall('regionId=[0-9]+', str(browser.rbrowser.parsed))][20:]

            player_ids += page_player_ids
            region_ids += page_region_ids

        del players_df['Nationality']
        players_df.insert(loc=3, column='Nationality', value=region_ids)
        players_df.insert(loc=1, column='PlayerID', value=player_ids)
        players_df['Wage'] = players_df['Wage'].str.replace('\D+', '')

    timestr = re.findall('Week [0-9]+, Season [0-9]+', str(browser.rbrowser.parsed))[0]
    week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]

    players_df['Age_year'] = [int(str(round(float(pl['Age']), 2)).split('.')[0]) for i, pl in players_df.iterrows()]
    players_df['Age_weeks'] = [int(str(round(float(pl['Age']), 2)).split('.')[1]) for i, pl in players_df.iterrows()]
    players_df['Age_display'] = [round(player_age, 2) for player_age in players_df['Age']]
    players_df['Age_value'] = [y + (w/15) for y, w in zip(players_df['Age_year'], players_df['Age_weeks'])]

    players_df['data_timestamp'] = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M:%S %Z')
    players_df['data_season'] = int(season)
    players_df['data_week'] = int(week)

    if additional_columns:
        players_df = add_player_columns(players_df, additional_columns, ind_level=ind_level+1)
        sorted_columns = ['Player', 'PlayerID', 'Age', 'NatSquad', 'Touring','Rating', 'BowlType', 'End', 'Bat', 'Bowl', 'Tech', 'Pow', 'Keep', 'Field', 'Exp']
        sorted_columns = sorted_columns + [c for c in list(players_df.columns) if c not in sorted_columns]
        players_df = players_df.reindex(columns=sorted_columns)

    players_df.drop(columns=[x for x in ['#', 'Unnamed: 18', 'Age'] if x in players_df.columns], inplace=True)

    if skill_level_format == 'numeric':
        skill_columns = ['End', 'Bat', 'Bowl', 'Tech', 'Pow', 'Keep', 'Field', 'Exp', 'Captaincy', 'Fatigue', 'Form', 'SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr']  # Add or modify as per your DataFrame's columns
        for col in skill_columns:
            if col in players_df.columns:
                players_df[col] = players_df[col].fillna('').astype(str).map(SKILL_LEVELS_MAP.get)

    if return_sort_column:
        players_df.sort_values(return_sort_column, inplace=True, ascending=False)

    if column_sort_order:
        if column_sort_order == 'standard1':
            standard1 = ['PlayerID', 'Player', 'Age_display', 'Nationality', 'NatSquad', 'Rating', 'WageReal', 'Deadline', 'Bidding Team', 'Current Bid', 'BatHand', 'BowlType', 'SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr', 'Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Pow', 'Exp', 'Captaincy', 'Form', 'Fatigue', 'Talent1', 'Talent2', 'Training', 'Touring', 'WageDiscount', 'WagePaid', 'Age_year', 'Age_weeks', 'Age_value', 'data_season', 'data_week', 'data_timestamp']
            players_df = players_df[standard1]
        else:
            players_df = players_df[column_sort_order]

    if to_file:
        pd.DataFrame.to_csv(players_df, to_file, index=False, float_format='%.2f')

    if to_database:
        conn = sqlite3.connect(to_database)

        players_df.to_sql('players', conn, if_exists='append', index=False)

        conn.commit()
        conn.close()

    return players_df


def download_database(archive_name, download_teams_whitelist=False, age_override=False, preserve_exisiting=False, ind_level=0):
    archive_name = get_database_from_name(archive_name)

    database_settings, additional_settings = load_config_file(archive_name)
    if 'additional_columns' not in database_settings.keys():
        database_settings['additional_columns'] = False

    if download_teams_whitelist:
        download_teams_whitelist = [str(t) for t in download_teams_whitelist]
        teams_to_download = [team for team in additional_settings['teamids'] if str(team) in download_teams_whitelist]
        CoreUtils.log_event('Downloading {}/{} entries ({}) from database {}'.format(len(download_teams_whitelist), len(additional_settings['teamids']), download_teams_whitelist, config_file_directory.split('/')[-1]), ind_level=ind_level)
    else:
        if 'teamids' in additional_settings.keys():
            teams_to_download = additional_settings['teamids']
        CoreUtils.log_event('Downloading database {}'.format(archive_name.split('/')[-1]), ind_level=ind_level)

    browser.rbrowser.open('https://www.fromthepavilion.org/club.htm?teamId=4791')

    player_df = pd.DataFrame()
    aggregate_search = []
    if database_settings['database_type'] in ['domestic_team', 'national_team']:
        for teamid in teams_to_download:
            if age_override:
                download_age = age_override
            else:
                download_age = additional_settings['age']

            search = FTPUtils.get_team_players(teamid, age_group=download_age,
                                               ind_level=ind_level + 1,
                                               additional_columns=database_settings['additional_columns'])
            search['teamid'] = teamid
            aggregate_search.append(search)

        player_df = pd.concat(aggregate_search)

    elif database_settings['database_type'] == 'best_player_search':
        aggregate_search = []
        for nationality_id in teams_to_download:
            additional_settings['nation'] = nationality_id
            search = player_search(additional_settings, search_type='all', additional_columns=database_settings['additional_columns'], ind_level=ind_level+1)
            search['nationality_id'] = nationality_id
            aggregate_search.append(search)

        player_df = pd.concat(aggregate_search)

    elif database_settings['database_type'] == 'transfer_market_search':
        player_df = player_search(search_settings=additional_settings, search_type='transfer_market', additional_columns=database_settings['additional_columns'], ind_level=ind_level+1, skill_level_format='numeric')

    db_path = f'{database_settings["w_directory"]}{database_settings["name"]}.db'
    conn = sqlite3.connect(db_path)

    try:
        player_df.to_sql('players', conn, if_exists='append', index=False)
        CoreUtils.log_event(f"Data successfully written to {db_path}", ind_level=ind_level)
    except Exception as e:
        CoreUtils.log_event(f"An error occurred while writing to the database: {e}", ind_level=ind_level)
    finally:
        conn.close()


def add_player_columns(player_df, column_types, returnsortcolumn=None, ind_level=0):
    CoreUtils.log_event('Creating additional columns ({}) for {} players'.format(column_types, len(player_df['Rating'])), ind_level=ind_level)

    all_player_data = []
    hidden_training_n = 0
    for player_id in player_df['PlayerID']:
        player_data = []
        if 'Training' in column_types:
            browser.rbrowser.open(f'https://www.fromthepavilion.org/playerpopup.htm?playerId={player_id}')
            html_content = str(browser.rbrowser.parsed)
            popup_page_info = pd.read_html(StringIO(html_content))
            try:
                training_selection = popup_page_info[0][3][9]
            except KeyError:
                training_selection = 'Hidden'
                hidden_training_n += 1

        if column_types != ['Training'] and column_types != ['SpareRating']:
            browser.rbrowser.open('https://www.fromthepavilion.org/player.htm?playerId={}'.format(player_id))
            player_page = str(browser.rbrowser.parsed)

        for column_name in column_types:
            if column_name == 'Training':
                player_data.append(training_selection)

            elif column_name == 'Experience':
                player_experience = FTPUtils.get_player_experience(player_id, player_page)
                player_data.append(player_experience)

            elif column_name == 'Form':
                player_form = FTPUtils.get_player_form(player_id, player_page)
                player_data.append(player_form)

            elif column_name == 'Fatigue':
                player_fatigue = FTPUtils.get_player_form(player_id, player_page)
                player_data.append(player_fatigue)

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
                talent1, talent2 = FTPUtils.get_player_talents(player_id, player_page)
                player_data.append(talent1)

            elif column_name == 'Talent2':
                player_data.append(talent2)

            elif column_name == 'WageReal':
                WageReal, WagePaid, WageDiscount = FTPUtils.get_player_wage(player_id, page=player_page, return_type='tuple')
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

    if hidden_training_n > 0:
        CoreUtils.log_event('Training not visible for {}/{} players - marked "Hidden" in dataframe'.format(hidden_training_n, len(player_df['PlayerID'])), ind_level=ind_level + 1)

    for n, column_name in enumerate(column_types):
        values = [v[n] for v in all_player_data]
        if column_name == 'Experience':
            player_df['Exp'] = values
        elif column_name == 'BowlType':
            player_df[column_name] = values
        else:
            if column_name in player_df.columns:
                player_df[column_name] = values
            else:
                player_df.insert(3, column_name, values)

    if returnsortcolumn in player_df.columns:
        player_df.sort_values(returnsortcolumn, inplace=True, ignore_index=True, ascending=False)

    return player_df


def next_run_time(time_tuple):
    current_datetime = datetime.datetime.now(datetime.timezone.utc)# - datetime.timedelta(days=1)
    if isinstance(time_tuple, type(None)):
        return current_datetime

    db_scrape_hour, db_scrape_minute, db_days = time_tuple

    #TEST TEST TEST TEST

    if int(db_scrape_hour) >= 12:
        db_days = [(int(n) - 1) % 7 for n in db_days]

    #TEST TEST TEST TEST

    weekly_runtimes = []
    for day in db_days:
        day = int(day)
        days_ahead = day - current_datetime.weekday()
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        next_run_datetime = current_datetime + datetime.timedelta(days_ahead)
        next_run_datetime = next_run_datetime.replace(hour=int(db_scrape_hour), minute=int(db_scrape_minute), second=0, microsecond=0, tzinfo=pytz.UTC)
        weekly_runtimes.append(next_run_datetime)

    weekly_runtimes.sort()
    for runtime in weekly_runtimes:
        if runtime > current_datetime:
            return runtime
    else:
        return weekly_runtimes[0] + datetime.timedelta(days=7)


def get_from_database_by_column(database_name, column):
    db_path = get_database_from_name(database_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT MAX({column}) FROM players")
    result = cursor.fetchone()
    conn.close()

    if result and result[0]:
        if column == 'data_timestamp':
            saved_until_time = datetime.datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S %Z')
        elif column == 'Deadline':
            saved_until_time = datetime.datetime.strptime(result[0], '%d %b. %Y %H:%M')
        return saved_until_time.replace(tzinfo=pytz.UTC) - datetime.timedelta(minutes=2)
    return None


def get_database_from_name(db_name, default_directory='data/classic-archive/', return_type='file', file_extension='db'):
    if db_name.count('/') == 0:
        db_name = f'{default_directory}{db_name}/{db_name}.{file_extension}'

    extension_start_index = db_name.rindex('.')
    if db_name[extension_start_index:] != file_extension:
        db_name = db_name[:extension_start_index+1] + file_extension

    if return_type == 'folder':
        db_name = '/'.join(db_name.split('/')[:-1])

    return db_name


def split_database_events(database_name):
    conf_data = load_config_file(database_name)
    agegroup = conf_data[1]['age']
    teamids = conf_data[1]['teamids']
    teamregions = [FTPUtils.get_team_region(teamid) for teamid in teamids]

    teams_by_region = {}
    for teamid, region_id in zip(teamids, teamregions):
        if region_id in teams_by_region.keys():
            teams_by_region[region_id].append((teamid, agegroup))
        else:
            teams_by_region[region_id] = [(teamid, agegroup)]

    split_event_list = []
    for region_id in teams_by_region.keys():
        run_time = FTPUtils.country_game_start_time(region_id)
        run_hour, run_minute = run_time.split(':')
        for teamid, agegroup in teams_by_region[region_id]:
            if agegroup in ['0', '1', 'all', 'youths']:
                day_of_week = [2]
                age_type = 1
                event_run_time_tuple = (run_hour, run_minute, day_of_week)
                runtime = next_run_time(event_run_time_tuple) + datetime.timedelta(minutes=5)
                split_event_list.append((runtime, database_name, (teamid), age_type, event_run_time_tuple))
            if agegroup in ['0', '2', 'all', 'seniors']:
                day_of_week = [0]
                age_type = 2
                event_run_time_tuple = (run_hour, run_minute, day_of_week)
                runtime = next_run_time(event_run_time_tuple) + datetime.timedelta(minutes=5)
                split_event_list.append((runtime, database_name, (teamid), age_type, event_run_time_tuple))

    return split_event_list


def watch_database_list(database_list, ind_level=0):
    if not isinstance(type(database_list), type(list)):
        database_list = [database_list]

    database_config_dic = {}
    master_database_stack = []
    CoreUtils.log_event('Generating download times for watch_database_list:')
    for database_name in database_list:
        conf_data = load_config_file(database_name)
        database_config_dic[database_name] = conf_data
        if 'archive_days' in conf_data[0].keys():
            db_scrape_hour, db_scrape_minute = conf_data[0]['scrape_time']
            db_days = conf_data[0]['archive_days']
            if not isinstance(type(db_days), type(list)):
                db_days = [int(db_days)]
            db_days = [int(d) for d in db_days]
            event_run_time_tuple = (db_scrape_hour, db_scrape_minute, db_days)
        elif conf_data[0]['database_type'] == 'transfer_market_search':
            event_run_time_tuple = None

        if conf_data[0]['database_type'] in ['domestic_team', 'national_team']:
            if conf_data[0]['scrape_time'] == 'auto':
                CoreUtils.log_event('{}: Generating from config'.format(database_name), ind_level=ind_level + 1)
                db_stack = split_database_events(database_name)
                for item in db_stack:
                    master_database_stack.append(item)
            else:
                CoreUtils.log_event('{}: Loaded from file'.format(database_name), ind_level=ind_level + 1)
                db_age_group = conf_data[1]['age']
                db_next_runtime = next_run_time(event_run_time_tuple)
                for teamid in conf_data[1]['teamids']:
                    db_event = [db_next_runtime, database_name, teamid, db_age_group, event_run_time_tuple]
                    master_database_stack.append(db_event)
        else:
            CoreUtils.log_event('{}: Loaded from file'.format(database_name), ind_level=ind_level + 1)
            if conf_data[0]['database_type'] == 'transfer_market_search':
                db_first_runtime = datetime.datetime.now(datetime.timezone.utc)
                db_event = [db_first_runtime, database_name, None, None, event_run_time_tuple]
            else:
                db_first_runtime = next_run_time(event_run_time_tuple)
                db_event = [db_first_runtime, database_name, None, conf_data[1]['age'], event_run_time_tuple]
            master_database_stack.append(db_event)

    master_database_stack.sort(key=lambda x : x[0])
    while True:
        current_datetime = datetime.datetime.now(datetime.timezone.utc)
        seconds_until_next_run = int((master_database_stack[0][0] - current_datetime).total_seconds())
        if seconds_until_next_run > 0:
            hours_until_next_run = seconds_until_next_run // (60 * 60)
            extra_minutes = (seconds_until_next_run % (60 * 60)) // 60
            CoreUtils.log_event('Pausing program for {}d{}h{}m until next event: database: {}'.format(hours_until_next_run // 24, hours_until_next_run % 24, extra_minutes, master_database_stack[0][1]))
            time.sleep(seconds_until_next_run)

        attempts_before_exiting = 10
        current_attempt = 0
        seconds_between_attempts = 60
        browser.check_login()

        while current_attempt <= attempts_before_exiting:
            try:
                download_database(master_database_stack[0][1])
                if current_attempt > 0:
                    CoreUtils.log_event('Completed successfully after {} failed attempts'.format(current_attempt), ind_level=ind_level)
                break
            except ZeroDivisionError:
                CoreUtils.log_event('Error downloading database. {}/{} attempts, {}s between attempts...'.format(current_attempt, attempts_before_exiting, seconds_between_attempts), ind_level=ind_level + 1)
                time.sleep(seconds_between_attempts)

        if current_attempt < attempts_before_exiting:
            database_settings, _ = load_config_file(master_database_stack[0][1])

            if database_settings['database_type'] == 'transfer_market_search': #Check if database type is market
                db_next_runtime = get_from_database_by_column(master_database_stack[0][1], 'Deadline')
            else:
                db_next_runtime = next_run_time(master_database_stack[0][4])
            master_database_stack[0] = [db_next_runtime] + master_database_stack[0][1:]
            master_database_stack = sorted(master_database_stack, key=lambda x:x[0])

            CoreUtils.log_event('Successfully downloaded database {}. Next download is {} at {}'.format(database_settings['name'], master_database_stack[0][1], master_database_stack[0][0]), ind_level=ind_level + 1)

