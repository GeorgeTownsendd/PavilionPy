#import PlayerDatabase
#import PresentData
import CoreUtils

browser = CoreUtils.browser

import re
import os
import pandas as pd
import numpy as np
import datetime
import matplotlib
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


def has_training_occured(region_id, age_group):
    current_utc_time = datetime.datetime.utcnow()
    current_day_of_week = current_utc_time.weekday()  # Monday is 0, Sunday is 6

    training_start_time = get_match_start_time_by_region(region_id)
    training_day = 0 if age_group == 'youth' else 2  # Monday for 'youth', Wednesday for 'senior'

    if current_day_of_week > training_day:
        return True
    elif current_day_of_week < training_day:
        return False
    else:
        training_datetime = current_utc_time.replace(hour=training_start_time['hours'], minute=training_start_time['minutes'], second=0, microsecond=0)
        return current_utc_time >= training_datetime


def get_player_experience(player_id, page=False):
    if not page:
        page = get_player_page(player_id)

    exp_pattern = r'<th>(?:Exp\.|Experience)</th><td[^>]*>(.*?)</td>'
    exp_match = re.search(exp_pattern, page)
    experience = exp_match.group(1) if exp_match else None

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

    captaincy_pattern = r'<th>Captaincy</th><td[^>]*>(.*?)</td>'
    captaincy_match = re.search(captaincy_pattern, page)
    captaincy = captaincy_match.group(1) if captaincy_match else None

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


def normalize_age_list(player_ages, reverse=False):
    min_year = min([int(str(age).split('.')[0]) for age in player_ages])
    max_year = max([int(str(age).split('.')[0]) for age in player_ages]) + 1
    year_list = [year for year in range(min_year, max_year)]

    nor_agelist = [] #normalized
    rea_agelist = [] #real / string / 00

    for year in year_list:
        for week in range(0, 15):
            frac_end = str(week / 15).split('.')[1]
            normalized_age = str(year) + '.' + frac_end[:5]

            if week < 10:
                if week == 0:
                    real_age = str(year) + '.00'
                else:
                    real_age = str(year) + '.0' + str(week)
            else:
                real_age = str(year) + '.' + str(week)

            nor_agelist.append(normalized_age)
            rea_agelist.append(real_age)

    new_ages = []
    for p_age in player_ages:
        if reverse:
            try:
                age_ind = nor_agelist.index(str(p_age).split('.')[0] + '.' + str(p_age).split('.')[1][:5])
                new_age = rea_agelist[age_ind]
                new_ages.append(new_age)
            except ValueError:
                new_ages.append('AgeError:Unexpected')
        else:
            if str(p_age).split('.')[1] == '1':
                p_age = str(p_age).split('.')[0] + '.10'
            if str(p_age).split('.')[1] == '0':
                p_age = str(p_age).split('.')[0] + '.00'
            new_ages.append(nor_agelist[rea_agelist.index(str(p_age))])

    return [str(age) if reverse else float(age) for age in new_ages]

def generate_db_time_pairs(database_entries='all'):
    if database_entries == 'all':
        database_entries = PlayerDatabase.database_entries_from_directory('working_directory')

    dbt_pairs = []
    for database_name in database_entries.keys():
        sequential_entries = []
        for season in database_entries[database_name].keys():
            for week in database_entries[database_name][season]:
                sequential_entries.append(season + '.' + week)

        for entry in range(len(sequential_entries)-1):
            entryminus1 = [int(''.join([n for n in x if n.isdigit()])) for x in sequential_entries[entry-1].split('.')]
            entry = [int(''.join([n for n in x if n.isdigit()])) for x in sequential_entries[entry].split('.')]
            dbt_pairs.append((database_name, entryminus1, entry))

    return dbt_pairs

def catagorise_training(db_time_pairs='all', min_data_include=5, std_highlight_limit=1, max_weeks_between_training=1):
    '''
    Catagorises a set of players from database/week pairs into a dictionary of
    lists sorted by training/age. Used to view e.g. The average ratdif of all
    22 year old players trained in Fielding

        db_time_pair_element = (db_name, dbt1, dbt2)
        dbt1 = (season, week)

        min_data_include = minimum points of data to plot for an age
        std_highlight_label = how wide the highlighted section should be for an age, by std
    '''
    if db_time_pairs == 'all':
        db_time_pairs = generate_db_time_pairs(database_entries='all')

    db_time_pairs = [dbt for dbt in db_time_pairs if (abs((dbt[2][0] * 15) + dbt[2][1]) - ((dbt[1][0] * 15) + dbt[1][1])) <= max_weeks_between_training]

    training_data_collection = []
    for dbtpair in db_time_pairs:
        training_data_week = ratdif_from_weeks(dbtpair[0], dbtpair[1], dbtpair[2])
        if 'Training' in training_data_week.columns:
            training_data_week = training_data_week[(training_data_week['Training'] != 'Rest') & (training_data_week['Ratdif'] > 0)]
            non_hidden_training = training_data_week[training_data_week['Training'] != 'Hidden']

            training_data_collection.append(non_hidden_training)

    all_training_data = pd.concat(training_data_collection)
    all_training_data.drop_duplicates(['PlayerID', 'Rating'], inplace=True)
    training_type_dict = {}
    for trainingtype in ['Batting', 'Bowling', 'Keeping', 'Keeper-Batsman', 'All-rounder', 'Fielding', 'Fitness',
                             'Batting Technique', 'Bowling Technique', 'Strength', 'Rest']:
        training_type_data = all_training_data[all_training_data['Training'] == trainingtype]
        training_type_data['Age'] = [int(floor(a)) for a in list(training_type_data['Age'])]
        training_type_age_dict = {}
        for age in range(
                int(min(np.append(training_type_data.Age, int(max(np.append(training_type_data.Age, 16)))))),
                int(max(np.append(training_type_data.Age, 16)))):
            data = training_type_data[training_type_data['Age'] == age]
            if len(data) >= min_data_include:
                data = data[np.abs(data.Ratdif - data.Ratdif.mean()) <= (
                            std_highlight_limit * training_data_week.Ratdif.std())]
                    # keep only values within +- 3 std of ratdif

                training_type_age_dict[age] = data

        training_type_dict[trainingtype] = training_type_age_dict

    return training_type_dict

def ratdif_from_weeks(db_name, dbt1, dbt2, average_ratdif=True):
    db_config = PlayerDatabase.load_config_file(db_name)
    db_team_ids = db_config[1]['teamids']
    w2p = []
    w1p = []
    for region_id in db_team_ids:
        team_w1p = PlayerDatabase.load_entry(db_name, dbt1[0], dbt1[1], region_id, normalize_age=True)  # pd.concat(w13players)
        team_w2p = PlayerDatabase.load_entry(db_name, dbt2[0], dbt2[1], region_id, normalize_age=True)  # pd.concat(w10players)
        x1, x2 = PlayerDatabase.match_pg_ids(team_w1p, team_w2p, returnsortcolumn='Ratdif')
        w1p.append(x1)
        w2p.append(x2)

    allplayers = pd.concat(w2p, ignore_index=True).T.drop_duplicates().T
    weeks_of_training = dbt2[1] - dbt1[1]

    allplayers['TrainingWeeks'] = weeks_of_training
    allplayers['DataTime'] = 's{}w{}'.format(dbt2[0], dbt2[1])
    if average_ratdif:
        if weeks_of_training > 1:
            allplayers['Ratdif'] = np.divide(allplayers['Ratdif'], weeks_of_training)

    return allplayers


