from flask import Flask, request, jsonify, render_template
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from PlayerTracker import PlayerTracker
from FTPUtils import SKILL_LEVELS

app = Flask(__name__)

@app.route('/')
def index():
    # Render a simple form for entering the playerId
    return render_template('index.html')


@app.route('/get_players_in_database')
def get_players_in_database():
    database_path = 'data/archives/team_archives/team_archives.db'
    conn = sqlite3.connect(database_path)
    query = 'SELECT Player, PlayerID, TeamName, AgeDisplay, DataTimestamp FROM players'
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Convert "DataTimestamp" from string to datetime
    df['DataTimestamp'] = pd.to_datetime(df['DataTimestamp'])

    # Calculate the start and end of the previous week
    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday(), weeks=1)
    end_of_week = start_of_week + timedelta(days=6)

    # Determine if each player's latest data timestamp falls within the previous week
    df['currently_in_squad'] = df['DataTimestamp'].between(start_of_week, end_of_week)

    players_list = df.to_dict('records')  # Convert dataframe to list of dicts

    return jsonify({'players': players_list})


@app.route('/get_player_skills', methods=['POST'])
def get_player_skills():
    player_id = request.form['playerId']
    player_tracker = PlayerTracker(player_id)

    player_details = {k: str(v) for k, v in player_tracker.permanent_attributes.items()}

    player_details['AgeDisplay'] = str(player_tracker.player_states.iloc[-1]['AgeDisplay'])
    player_details['Rating'] = str(player_tracker.player_states.iloc[-1]['Rating'])
    player_details['SpareRating'] = str(player_tracker.spare_rating)
    player_details['UnknownSpareRating'] = str(player_tracker.total_unknown_spare_rating)
    player_details['WageReal'] = str(player_tracker.player_states.iloc[-1]['WageReal'])
    player_details['Experience'] = SKILL_LEVELS[int(player_tracker.player_states.iloc[-1]['Experience'])]
    player_details['Captaincy'] = SKILL_LEVELS[int(player_tracker.player_states.iloc[-1]['Captaincy'])]
    player_details['LatestData'] = str(player_tracker.recorded_weeks[-1])

    known_skills = list([int(x) for x in player_tracker.known_skills])
    estimate_spare = list([int(x) for x in player_tracker.estimate_spare])
    estimated_max_training = list([int(x) for x in player_tracker.estimate_max_training])

    training_processing_results = player_tracker.training_processing_results
    # Convert tuple keys to strings
    observation_results_converted = {}
    for key, value in training_processing_results['observation_results'].items():
        # Convert the tuple key to a string or another serializable format
        str_key = f'{key[0]}_{key[1]}'  # Example format: '57_5'
        observation_results_converted[str_key] = value

    # Replace the original 'observation_results' with the converted one
    training_processing_results['observation_results'] = observation_results_converted

    return {
        'player_details': player_details,
        'known_skills': known_skills,
        'estimated_spare': estimate_spare,
        'estimated_max_training': estimated_max_training,
        'training_processing_results': training_processing_results
    }


if __name__ == '__main__':
    app.run(debug=True)

