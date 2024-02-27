import sqlite3
import os
import json
import jsonschema
import re
import time
import numpy as np
import uuid
from datetime import datetime, timedelta
import pandas as pd
from io import StringIO
from jsonschema import validate
from typing import Dict, Optional, List, Union
from bs4 import BeautifulSoup

import CoreUtils
import PavilionPy

ftpbrowser = CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser


def get_league_page(league_id):
    browser.open('https://www.fromthepavilion.org/leaguefixtures.htm?lsId={}'.format(league_id))
    page = str(browser.parsed)

    return page


def extract_game_ids(page_content):
    pattern = re.compile(r'game\.htm\?gameId=(\d+)')
    matches = pattern.findall(page_content)

    game_ids = [int(match) for match in matches]

    return game_ids


def get_league_overview_page(league_id):
    browser.open('https://www.fromthepavilion.org/leagueoverview.htm?lsId={}'.format(league_id))
    page_content = str(browser.parsed)
    return page_content


def extract_seasons_and_ids(page_content):
    pattern = re.compile(r'<option value="(\d+)">(\d+)</option>')
    matches = pattern.findall(page_content)
    seasons_dict = {int(league_id): int(season) for league_id, season in matches}

    return seasons_dict


def extract_match_ratings(game_id):
    url = f'https://www.fromthepavilion.org/ratings.htm?gameId={game_id}'
    browser.open(url)
    page = str(browser.parsed)
    soup = BeautifulSoup(page, 'html.parser')
    table = soup.find('table', class_='data stats')
    headers = table.find_all('th')
    team1 = headers[1].get_text().strip()
    team2 = headers[2].get_text().strip()
    ratings = {}
    rows = table.find_all('tr')[1:]  # Skipping the header row
    for row in rows:
        columns = row.find_all('td')
        category = columns[0].get_text().strip().replace(' - ', ' ')
        category = ''.join(word if word.islower() else ' ' + word for word in category).title().replace(' ', '').replace('/', '')
        team1_rating = int(columns[1].get_text().strip().split(' ')[0].replace(',', ''))
        team2_rating = int(columns[2].get_text().strip().split(' ')[0].replace(',', ''))
        ratings[category] = {team1: team1_rating, team2: team2_rating}
    return ratings, team1, team2


def extract_player_ids(table_html):
    player_ids = []
    player_names = []
    rows = table_html.find_all('tr')[1:-3]  # Skip the header row and summary rows
    for row in rows:
        player_cell = row.find('td')
        player_link = player_cell.find('a')
        if player_link and 'playerId=' in player_link['href']:
            player_id = player_link['href'].split('playerId=')[1].split('&')[0]
            player_ids.append(int(player_id))
            player_name = player_link['title']
            player_names.append(player_name)
        else:
            player_ids.append(None)
            player_names.append(None)
    return player_ids, player_names

def get_game_summary(game_id):
    CoreUtils.log_event(f'Downloading summary for game {game_id}')
    url = f'https://www.fromthepavilion.org/scorecard.htm?gameId={game_id}'
    browser.open(url)
    page = str(browser.parsed)
    soup = BeautifulSoup(page, 'html.parser')\

    result_text = soup.find('th', string='Result:').find_next_sibling('td').text
    winner = result_text.split(' won ')[0]

    toss_text = soup.find('th', string='Toss:').find_next_sibling('td').text
    toss_winner, toss_decision = toss_text[:-1].split(' won the toss and elected to ')

    match_ratings, team1_name, team2_name = extract_match_ratings(game_id)
    batting_team = (toss_winner if toss_decision == 'bat' else (team1_name if toss_winner == team2_name else team2_name))

    game_info = pd.read_html(StringIO(str(soup)))[5]
    weather = game_info[game_info[0] == 'Weather'][1].values[0]
    pitch = game_info[game_info[0] == 'Pitch'][1].values[0]
    league = game_info[game_info[0] == 'League'][1].values[0]
    date_str = game_info[game_info[0] == 'Date'][1].values[0]
    date_str = re.sub(r'(?<=\b\w{3})\.', '', date_str)
    match_date = datetime.strptime(date_str, "%d %b %y %H:%M")
    match_day_of_week = match_date.weekday() + 1

    match_type, division = league.rsplit(' ', 1)

    tb = pd.read_html(StringIO(str(soup)))

    first_innings_footer = tb[1].iloc[-2]
    second_innings_footer = tb[3].iloc[-2]

    first_innings_score = first_innings_footer['Runs']
    first_innings_info = re.search(r"(\d+) wickets, (\d+(?:\.\d+)?) overs", first_innings_footer[f'{team1_name if team1_name == batting_team else team2_name}.1'])
    first_innings_wickets = int(first_innings_info.group(1))
    first_innings_overs = float(first_innings_info.group(2))

    second_innings_score = int(second_innings_footer['Runs'])
    second_innings_info = re.search(r"(\d+) wickets, (\d+(?:\.\d+)?) overs", second_innings_footer[ f'{team2_name if team1_name == batting_team else team1_name}.1'])
    second_innings_wickets = int(second_innings_info.group(1))
    second_innings_overs = float(second_innings_info.group(2))

    game_summary = pd.DataFrame({
        'GameID': [int(game_id)],
        'Team1': [team1_name],
        'Team2': [team2_name],
        'Winner': [winner],
        'Weather': [weather],
        'Pitch': [pitch],
        'League': [league],
        'Match Type': [match_type],
        'Division': [division],
        'Tour Day': [match_day_of_week],
        'Toss Winner': [toss_winner],
        'Toss Decision': [toss_decision],
        'First Innings Score': [first_innings_score],
        'First Innings Length': [first_innings_overs],
        'First Innings Wickets': [first_innings_wickets],
        'Second Innings Score': [second_innings_score],
        'Second Innings Length': [second_innings_overs],
        'Second Innings Wickets': [second_innings_wickets],
        'BattingTeamWon': [winner == batting_team]
    })

    for category, ratings in match_ratings.items():
        game_summary[f'MR {category} Team1'] = ratings[team1_name]
        game_summary[f'MR {category} Team2'] = ratings[team2_name]

    return game_summary


def download_league_games(league_ids):
    game_summaries = []

    for league_id in league_ids:
        page_content = get_league_page(league_id)
        league_games = extract_game_ids(page_content)

        for game_id in league_games:
            try:
                game_summary = get_game_summary(game_id)
                game_summary['LeagueID'] = [league_id]
                game_summaries.append(game_summary)
            except Exception as e:
                CoreUtils.log_event(f'Error processing game {game_id}: {str(e)}')

    game_summary_df = pd.concat(game_summaries).reset_index(drop=True)
    column_ordering_schema = 'data/schema/col_ordering_natgamesummary.txt'

    game_summary_df = PavilionPy.apply_column_ordering(game_summary_df, column_ordering_schema)

    return game_summary_df


if __name__ == '__main__':
    league_ids = [115528]

    game_summary_df = download_league_games(league_ids)
    game_summary_df.to_csv('nat_game_summary.csv')
