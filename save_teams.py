import sqlite3
import pandas as pd
import os

import CoreUtils
from PavilionPy import get_team_players
from FTPUtils import get_team_info

team_ids = [3941]#, 3016]
db_path = 'data/archives/team_archives/team_archives.db'
age_group = 'all'
#age_group = 'youths'

conn = sqlite3.connect(db_path)
def get_existing_combinations(conn):
    query = "SELECT PlayerID, DataSeason, DataWeek FROM players"
    existing_df = pd.read_sql(query, conn)
    return set(existing_df.itertuples(index=False, name=None))


existing_combinations = get_existing_combinations(conn)

for teamid in team_ids:
    team_name = get_team_info(teamid, 'TeamName')
    new_players = get_team_players(teamid, columns_to_add='all_visible', column_ordering_keyword='col_ordering_visibleplayers', age_group=age_group)
    new_players['TeamGroup'] = team_name

    trained_players = new_players[new_players['TrainedThisWeek'] == 1]

    untrained_players_count = len(new_players) - len(trained_players)
    if untrained_players_count > 0:
        CoreUtils.log_event(f"{untrained_players_count} players were filtered out because they have not been trained this week.")

    is_new_record = trained_players.apply(lambda row: (row['PlayerID'], row['DataSeason'], row['DataWeek']) not in existing_combinations, axis=1)
    unique_new_players = trained_players[is_new_record]
    n_filtered_players = len(trained_players) - len(unique_new_players)

    if n_filtered_players > 0:
        CoreUtils.log_event(f'{n_filtered_players} players were filtered out because they already exist in the database for this week.')

    if not unique_new_players.empty:
        unique_new_players.to_sql('players', conn, if_exists='append', index=False)
        CoreUtils.log_event(f'{len(unique_new_players)} players saved to the database for TeamID {teamid}.')

conn.close()
