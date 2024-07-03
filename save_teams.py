import CoreUtils
browser = CoreUtils.initialize_browser()

import sqlite3
import pandas as pd
import os
from PavilionPy import get_team_players
from FTPUtils import get_team_info, get_current_game_week

team_ids = [3941, 3016]
db_path = 'data/archives/team_archives/team_archives.db'
age_group = 'all'
#age_group = 'youths'

conn = sqlite3.connect(db_path)
def get_existing_combinations(conn):
    query = "SELECT PlayerID, DataSeason, DataWeek FROM players"
    existing_df = pd.read_sql(query, conn)
    return set(existing_df.itertuples(index=False, name=None))

current_season, current_week = get_current_game_week()
existing_combinations = get_existing_combinations(conn)
players_already_downloaded = [player_id for player_id, data_season, data_week in existing_combinations if data_season == current_season and data_week == current_week]

for teamid in team_ids:
    team_name = get_team_info(teamid, 'TeamName')
    new_players = get_team_players(teamid, columns_to_add='all_visible', column_ordering_keyword='col_ordering_visibleplayers', age_group=age_group, ignore_players=players_already_downloaded)
    if len(new_players) > 0:
        new_players['TeamGroup'] = team_name
        trained_players = new_players[new_players['TrainedThisWeek'] == 1]

        untrained_players_count = len(new_players) - len(trained_players)
        if untrained_players_count > 0:
            CoreUtils.log_event(f"{untrained_players_count} players were filtered out because they have not been trained this week.")

        trained_players.to_sql('players', conn, if_exists='append', index=False)
        CoreUtils.log_event(f'{len(trained_players)} players saved to the database for TeamID {teamid}.')

conn.close()
