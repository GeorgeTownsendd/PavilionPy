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
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
import pandas as pd
import shutil
from matplotlib import rcParams
rcParams.update({'figure.autolayout': True})
import seaborn as sns; sns.set_theme(color_codes=True)
pd.options.mode.chained_assignment = None  # default='warn'

GLOBAL_SETTINGS = ['name', 'description', 'database_type', 'w_directory', 'archive_days', 'scrape_time', 'additional_columns']
ORDERED_SKILLS = [['ID', 'Player', 'Nat', 'Deadline', 'Current Bid'], ['Rating', 'Exp', 'Talents', 'BT'], ['Bat', 'Bowl', 'Keep', 'Field'], ['End', 'Tech', 'Pow']]

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
    archive_name = FTPUtils.get_database_from_name(archive_name)

    database_settings = {}
    additional_settings = {}
    all_file_values = {}
    with open(archive_name, 'r') as f:
        config_file_lines = [line.rstrip() for line in f.readlines()]
        for n, line in enumerate(config_file_lines):
            setting_name, value = line.split(':', 1)
            if setting_name in ['additional_columns', 'archive_days', 'teamids']:
                all_file_values[setting_name]= value.split(',')
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


def player_search(search_settings={}, to_file=False, search_type='transfer_market', normalize_age=False, additional_columns=False, return_sort_column=False, ind_level=0):
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
        del players_df['Nat']
        player_ids = [x[9:] for x in re.findall('playerId=[0-9]+', str(browser.rbrowser.parsed))][::2]
        region_ids = [x[9:] for x in re.findall('regionId=[0-9]+', str(browser.rbrowser.parsed))][9:]
        players_df.insert(loc=3, column='Nat', value=region_ids)
        players_df.insert(loc=1, column='PlayerID', value=player_ids)
        players_df['Deadline'] = [deadline[:-5] + ' ' + deadline[-5:] for deadline in players_df['Deadline']]
        cur_bids_full = [bid for bid in players_df['Current Bid']]
        split_bids = [b.split(' ', 1) for b in cur_bids_full]
        bids = [b[0] for b in split_bids]
        team_names = pd.Series([b[1] for b in split_bids])
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

                # CoreUtils.log_event('Downloaded page {}/{}...'.format(page + 1, int(search_settings['pages'])), logtype='console', ind_level=1)

        del players_df['Nat']
        players_df.insert(loc=3, column='Nat', value=region_ids)
        players_df.insert(loc=1, column='PlayerID', value=player_ids)
        players_df['Wage'] = players_df['Wage'].str.replace('\D+', '')

    if normalize_age:
        players_df['Age'] = FTPUtils.normalize_age_list(players_df['Age'])

    if additional_columns:
        players_df = add_player_columns(players_df, additional_columns, ind_level=ind_level+1)
        sorted_columns = ['Player', 'PlayerID', 'Age', 'NatSquad', 'Touring', 'Wage', 'Rating','BT', 'End', 'Bat', 'Bowl', 'Tech', 'Pow', 'Keep', 'Field', 'Exp', 'Talents', 'SpareRat']
        sorted_columns = sorted_columns + [c for c in list(players_df.columns) if c not in sorted_columns]
        players_df = players_df.reindex(columns=sorted_columns)

    players_df.drop(columns=[x for x in ['#', 'Unnamed: 18'] if x in players_df.columns], inplace=True)

    if return_sort_column:
        players_df.sort_values(return_sort_column, inplace=True, ascending=False)

    if to_file:
        pd.DataFrame.to_csv(players_df, to_file, index=False, float_format='%.2f')

    return players_df


def download_database(archive_name, download_teams_whitelist=False, age_override=False, preserve_exisiting=False, ind_level=0):
    archive_name = FTPUtils.get_database_from_name(archive_name)

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
    timestr = re.findall('Week [0-9]+, Season [0-9]+', str(browser.rbrowser.parsed))[0]
    week, season = timestr.split(',')[0].split(' ')[-1], timestr.split(',')[1].split(' ')[-1]

    if database_settings['database_type'] != 'transfer_market_search':
        season_dir = database_settings['w_directory'] + 's{}/w{}/'.format(season, week)
    else:
        season_dir = database_settings['w_directory'] + '/s{}/w{}/'.format(season, week)

    if not os.path.exists(season_dir):
        os.makedirs(season_dir)
        CoreUtils.log_event('Creating directory {}'.format(season_dir.replace('//', '/')), logfile=['default', database_settings['w_directory'] + database_settings['name'] + '.log'], ind_level=ind_level)

    player_df = pd.DataFrame()
    if database_settings['database_type'] in ['domestic_team', 'national_team']:
        for teamid in teams_to_download:
            if age_override:
                download_age = age_override
            else:
                download_age = additional_settings['age']

            filename = database_settings['w_directory'] + f's{season}/w{week}/{teamid}.csv'
            player_df = FTPUtils.get_team_players(teamid, age_group=download_age,
                                                     ind_level=ind_level + 1,
                                                     additional_columns=database_settings['additional_columns'])

    elif database_settings['database_type'] == 'best_player_search':
        aggregate_search = []
        for nationality_id in teams_to_download:
            additional_settings['nation'] = nationality_id
            filename = database_settings['w_directory'] + 's{}/w{}/{}.csv'.format(season, week, nationality_id)
            search = player_search(additional_settings, search_type='all', additional_columns=database_settings['additional_columns'], ind_level=ind_level+1)
            aggregate_search.append(search)
        filename = database_settings['w_directory'] + 's{}/w{}/combined.csv'.format(season, week)
        player_df = pd.concat(aggregate_search)


    elif database_settings['database_type'] == 'transfer_market_search':
        player_df = player_search(search_settings=additional_settings, search_type='transfer_market', additional_columns=database_settings['additional_columns'], ind_level=ind_level+1)
        filename = database_settings['w_directory'] + '/s{}/w{}/{}.csv'.format(season, week, player_df['Deadline'][0] + ' - ' + player_df['Deadline'][len(player_df['Deadline'])-1])

    player_df.to_csv(filename)

def load_entry(database, season, week, groupid, normalize_age=True, ind_level=0):
    if database[-1] != '/':
        database += '/'

    predicted_log_file = database + database.split('/')[-2] + '.log' #if name of database is the name of it's working directory
    if os.path.exists(predicted_log_file):
        log_files = ['default', predicted_log_file]
    else:
        log_files = ['default']

    data_file = database + 's{}/w{}/{}.csv'.format(season, week, groupid)
    if os.path.isfile(data_file):
        players = pd.read_csv(data_file)
        players.round(2)
        if normalize_age:
            players['Age'] = pd.Series(FTPUtils.normalize_age_list((players['Age'])))
        return players
    else:
        CoreUtils.log_event('Error loading database entry (file not found): {}'.format(data_file), logtype='full', logfile=log_files, ind_level=ind_level)

def transfer_saved_until(archive_name):
    archive_name = FTPUtils.get_database_from_name(archive_name, return_type='folder')

    latest_season = [x for x in os.listdir(archive_name) if re.match('s[0-9]+', x)][-1]
    latest_week = [x for x in os.listdir(archive_name + '/' + latest_season + '/') if re.match('w[0-9]+', x)][-1]
    files_in_latest_week = [span.split(' - ') for span in os.listdir(archive_name + '/' + latest_season + '/' + latest_week + '/') if ' - ' in span]

    file_datetimes = [datetime.datetime.strptime(fnames[-1][:-4], '%d %b. %Y %H:%M') for fnames in files_in_latest_week]

    saved_until_time = max(file_datetimes)
    saved_until_time = saved_until_time.replace(tzinfo=pytz.UTC) - datetime.timedelta(minutes=2)

    return saved_until_time

def add_player_columns(player_df, column_types, normalize_wages=True, returnsortcolumn=None, ind_level=0):
    CoreUtils.log_event('Creating additional columns ({}) for {} players'.format(column_types, len(player_df['Rating'])), ind_level=ind_level)

    all_player_data = []
    hidden_training_n = 0
    for player_id in player_df['PlayerID']:
        player_data = []
        if 'Training' in column_types:
            browser.rbrowser.open(f'https://www.fromthepavilion.org/playerpopup.htm?playerId={player_id}')
            html_content = str(browser.rbrowser.parsed)
            popup_page_info = pd.read_html(StringIO(html_content))  # Wrap the HTML in StringIO
            try:
                training_selection = popup_page_info[0][3][9]
            except KeyError:  # player training not visible to manager
                training_selection = 'Hidden'
                hidden_training_n += 1

        if column_types != ['Training'] and column_types != ['SpareRat']:
            browser.rbrowser.open('https://www.fromthepavilion.org/player.htm?playerId={}'.format(player_id))
            player_page = str(browser.rbrowser.parsed)

        for column_name in column_types:
            if column_name == 'Training':
                player_data.append(training_selection)

            elif column_name == 'Wage':
                player_wage = FTPUtils.get_player_wage(player_id, player_page, normalize_wages)
                player_data.append(player_wage)

            elif column_name == 'Nat':
                player_nationality_id = FTPUtils.get_player_nationality(player_id, player_page)
                player_data.append(player_nationality_id)

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

            elif column_name == 'SpareRat':
                player_data.append(FTPUtils.get_player_spare_ratings(player_df[player_df['PlayerID'] == player_id].iloc[0]))

            elif column_name == 'SkillShift':
                skillshifts = FTPUtils.get_player_skillshifts(player_id, page=player_page)
                player_data.append('-'.join(skillshifts.keys()) if len(skillshifts.keys()) >= 1 else None)

            else:
                player_data.append('UnknownColumn')

        all_player_data.append(player_data)

    if hidden_training_n > 0:
        CoreUtils.log_event('Training not visible for {}/{} players - marked "Hidden" in dataframe'.format(hidden_training_n, len(player_df['PlayerID'])), ind_level=ind_level+1)

    for n, column_name in enumerate(column_types):
        values = [v[n] for v in all_player_data]
        player_df.insert(3, column_name, values)

    if returnsortcolumn in player_df.columns:
        player_df.sort_values(returnsortcolumn, inplace=True, ignore_index=True, ascending=False)

    return player_df


def match_pg_ids(pg1, pg2, returnsortcolumn='Player'):
    shared_ids = [x for x in pg1['PlayerID'] if x in [y for y in pg2['PlayerID']]]

    pg1_shared = pg1[(pg1['PlayerID'].isin(shared_ids))].copy()
    pg2_shared = pg2[(pg2['PlayerID'].isin(shared_ids))].copy()

    pg1_shared.sort_values('PlayerID', inplace=True, ignore_index=True, ascending=False)
    pg2_shared.sort_values('PlayerID', inplace=True, ignore_index=True, ascending=False)

    add_columns = ['Ratdif', 'Wagedif']
    #if 'Bat' in pg2_shared.columns or 'Batting' in pg2_shared.columns:
    #    add_columns.append('SkillShift')

    pg2_shared = calculate_additional_columns(pg1_shared, pg2_shared, add_columns)
    for c in add_columns:
        pg1_shared[c] = pg2_shared[c]

    pg1_shared.sort_values(returnsortcolumn, inplace=True, ignore_index=True, ascending=False)
    pg2_shared.sort_values(returnsortcolumn, inplace=True, ignore_index=True, ascending=False)

    return pg1_shared, pg2_shared


def calculate_additional_columns(pg1, pg2, columns):
    for c in columns:
        if c == 'Ratdif':
            rating_differences = pg2['Rating'] - pg1['Rating']
            pg2.insert(len(pg2.columns), 'Ratdif', rating_differences)
        elif c == 'Wagedif':
            wage_differences = pg2['Wage'] - pg1['Wage']
            pg2.insert(len(pg2.columns), 'Wagedif', wage_differences)
        elif c == 'SkillShift':
            popped_skills = [calculate_player_skillshifts(playert_1, playert_2) for playert_1, playert_2 in zip(pg1, pg2)]
            pg2.insert(len(pg2.columns), 'SkillShift', '-'.join(popped_skills))

    return pg2

def database_entries_from_directory(directory='working_directory'):
    if directory == 'working_directory':
        directory = os.getcwd()

    local_directories = os.listdir(directory)
    database_names = []
    for sub_dir in local_directories:
        path = '{}/{}'.format(directory, sub_dir)
        if os.path.isdir(path):
            sub_files = os.listdir(path)
            for file in sub_files:
                if '.config' in file:
                    dbname = file.split('.')[0]
                    config_data = load_config_file(dbname)
                    if 'teamids' in config_data[1].keys():
                        database_names.append(dbname)

    database_entries = {}

    for dbname in database_names:
        seasons = [season_folder for season_folder in os.listdir(dbname + '/') if re.match('s[0-9]+', season_folder)]
        season_weeks = {season_folder: [week_folder for week_folder in os.listdir('{}/{}/'.format(dbname, season_folder)) if re.match('w[0-9]+', week_folder)] for season_folder in seasons}
        database_entries[dbname] = season_weeks

    return database_entries


def track_player_training(playerid, database_config_file):
    database_config = load_config_file(database_config_file)
    player_data_by_season = {season : {} for season in os.listdir(database_config[0]['w_directory']) if bool(re.match('^.*s[0-9]+.*$', season))}
    lastweek = None

    for season in player_data_by_season.keys():
        season_directory = database_config[0]['w_directory'] + season + '/'
        for week in os.listdir(season_directory):
            week_directory = season_directory + week + '/'
            for teamid in [x for x in os.listdir(week_directory) if x[-4:] == '.csv']:
                team_data = load_entry(database_config[0]['w_directory'], ''.join([x for x in season if x.isdigit()]), ''.join([x for x in week if x.isdigit()]), ''.join([x for x in teamid if x.isdigit()]))
                player_data_week = team_data[team_data['PlayerID'] == playerid]
                if not player_data_week.empty:
                    player_data_week = player_data_week.iloc[0]
                    column_names = [t for t in player_data_week.axes[0].values]
                    if 'Bat' in column_names and 'Training' in column_names:
                        if not isinstance(lastweek, type(None)):# and 'SkillShift' not in column_names:
                            trained_skill_list = calculate_player_skillshifts(lastweek, player_data_week)
                            trained_skills = '-'.join(trained_skill_list)
                            if trained_skills != '':
                                player_data_week['SkillShift'] = trained_skills

                            player_data_week['Ratdif'] = player_data_week['Rating'] - lastweek['Rating']
                        else:
                            player_data_week['Ratdif'] = '???'
                        player_data_week['SpareRat'] = FTPUtils.get_player_spare_ratings(player_data_week, col_name_len='short')

                        player_data_by_season[season][week] = player_data_week
                        lastweek = player_data_week
                        break

    return player_data_by_season


def calculate_player_skillshifts(player_data1, player_data2):
    long_names = ['Batting', 'Endurance', 'Bowling', 'Technique', 'Keeping', 'Power', 'Fielding']
    short_names = ['Bat', 'End', 'Bowl', 'Tech', 'Keep', 'Power', 'Field']
    saved_columns = [t for t in player_data1.axes[0].values]
    shifts = []

    if 'Bat' in saved_columns:
        col_names = short_names
    elif 'Batting' in saved_columns:
        col_names = long_names

    for c in col_names:
        if player_data1[c] != player_data2[c]:
            skill_ind = col_names.index(c)
            shifts.append(long_names[skill_ind])

    return shifts


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
                CoreUtils.log_event('{}: Generating from config'.format(database_name), ind_level=ind_level+1)
                db_stack = split_database_events(database_name)
                for item in db_stack:
                    master_database_stack.append(item)
            else:
                CoreUtils.log_event('{}: Loaded from file'.format(database_name), ind_level=ind_level+1)
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
            CoreUtils.log_event('Pausing program for {}d{}h{}m until next event: database: {}:{}'.format(hours_until_next_run // 24, hours_until_next_run % 24, extra_minutes, master_database_stack[0][1], master_database_stack[0][2]))
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
                CoreUtils.log_event('Error downloading database. {}/{} attempts, {}s between attempts...'.format(current_attempt, attempts_before_exiting, seconds_between_attempts), ind_level=ind_level+1)
                time.sleep(seconds_between_attempts)

        if current_attempt < attempts_before_exiting:
            database_settings, _ = load_config_file(master_database_stack[0][1])

            if database_settings['database_type'] == 'transfer_market_search': #Check if database type is market
                db_next_runtime = transfer_saved_until(master_database_stack[0][1])
            else:
                db_next_runtime = next_run_time(master_database_stack[0][4])
            master_database_stack[0] = [db_next_runtime] + master_database_stack[0][1:]
            master_database_stack = sorted(master_database_stack, key=lambda x:x[0])

            CoreUtils.log_event('Successfully downloaded database {}. Next download is at {}'.format(database_settings['name'], master_database_stack[0][1], master_database_stack[0][0]), ind_level=ind_level+1)

