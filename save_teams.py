import sqlite3
import pandas as pd
import os

from PavilionPy import get_team_players
from FTPUtils import get_team_info

team_ids = [3941, 3016]

db_path = 'data/archives/team_archives/team_archives.db'
os.makedirs(os.path.dirname(db_path), exist_ok=True)
conn = sqlite3.connect(db_path)
for teamid in team_ids:
    team_name = get_team_info(teamid, 'TeamName')

    team_players = get_team_players(teamid,
                                    columns_to_add='all_visible',
                                    column_ordering_keyword='col_ordering_visibleplayers')
    team_players['TeamGroup'] = team_name

    trained_players = team_players[team_players['TrainedThisWeek'] == 1]
    untrained_players_count = len(team_players) - len(trained_players)
    if untrained_players_count > 0:
        print(f"{untrained_players_count} players were filtered out because they have not been trained this week.")

    trained_players.to_sql('players', conn, if_exists='append', index=False)

conn.close()
