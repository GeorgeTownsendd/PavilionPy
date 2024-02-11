import sqlite3
import pandas as pd
import os

# Assuming PavilionPy and FTPUtils are available and correctly provide team data and information
from PavilionPy import get_team_players
from FTPUtils import get_team_info

# Define the list of team IDs to process
team_ids = [3941, 3016]

# Define the database path
db_path = 'data/archives/team_archives/team_archives.db'

# Ensure the directory exists
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Initialize the database connection
conn = sqlite3.connect(db_path)

# Loop through each team ID
for teamid in team_ids:
    # Fetch team name
    team_name = get_team_info(teamid, 'TeamName')

    team_players = get_team_players(teamid)
    team_players['TeamGroup'] = team_name

    # Filter out players who have not been trained this week
    trained_players = team_players[team_players['TrainedThisWeek'] == 1]

    # Print how many players were filtered out because they have not been trained
    untrained_players_count = len(team_players) - len(trained_players)
    if untrained_players_count > 0:
        print(f"{untrained_players_count} players were filtered out because they have not been trained this week.")

    # Append only the trained players to the database
    trained_players.to_sql('players', conn, if_exists='append', index=False)

# Close the database connection
conn.close()
