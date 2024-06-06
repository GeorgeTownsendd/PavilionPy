from flask import Flask, request, jsonify, render_template
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from PlayerTracker import PlayerTracker
from FTPUtils import SKILL_LEVELS, browser
from PavilionPy import get_player

app = Flask(__name__)

@app.route('/')
def index():
    # Render a simple form for entering the playerId
    return render_template('index.html')


@app.route('/get_player_summary/<player_id>')
def get_player_summary(player_id):
    # Dummy data generation logic - replace with actual data fetching
    player_summary = [
        {"season_week": "Season 1/Week 1", "true_increase": "5", "estimated_increase": "4.5", "pass": "Yes"},
        {"season_week": "Season 1/Week 2", "true_increase": "3", "estimated_increase": "3.2", "pass": "No"},
        {"season_week": "Season 1/Week 3", "true_increase": "6", "estimated_increase": "5.8", "pass": "Yes"},
        # Add more data as needed
    ]
    return jsonify(player_summary)

@app.route('/get_players_in_database')
def get_players_in_database():
    database_path = 'data/archives/team_archives/team_archives.db'
    #database_path = 'data/archives/uae_potentials/uae_potentials.db'
    conn = sqlite3.connect(database_path)
    query = 'SELECT Player, PlayerID, TeamName, AgeDisplay, AgeValue, DataTimestamp, DataSeason, DataWeek FROM players'
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['DataTimestamp'] = pd.to_datetime(df['DataTimestamp'])
    df = df.loc[df.groupby('PlayerID')['AgeValue'].idxmax()]

    current_season = df['DataSeason'].max()
    current_week = df[df['DataSeason'] == current_season]['DataWeek'].max()

    df['currently_in_squad'] = (df['DataSeason'] == current_season) & (df['DataWeek'] == current_week)
    players_list = df.to_dict('records')

    print(players_list)

    return jsonify({'players': sorted(players_list, key=lambda x:x['AgeValue'], reverse=True)})


def reformat_data(training_processing_data):
    # Unpack the first and last observation
    first_observation = training_processing_data['first_observation']
    last_observation = training_processing_data['last_observation']
    observation_results = training_processing_data['observation_results']

    # Helper function to generate season-week pairs
    def generate_season_weeks(start, end):
        for season in range(start[0], end[0] + 1):
            start_week = start[1] if season == start[0] else 0
            end_week = end[1] + 1 if season == end[0] else 15
            for week in range(start_week, end_week):
                yield f"{season}_{week}"

    # Reformat the data
    reformatted_results = []
    for season_week in generate_season_weeks(first_observation, last_observation):
        if season_week in observation_results:
            result = observation_results[season_week]
            reformatted_results.append({
                "season_week": f'({season_week.split("_")[0]}, {season_week.split("_")[1]})',
                "indicated_training": result.get('indicated_training', ''),
                "true_increase": result.get('true_rating_increase', ''),
                "estimated_increase": result.get('estimated_rating_increase', ''),
                "pass": "Yes" if str(result.get('pass_check', '')) == 'True' else "No" if str(result.get('pass_check', '')) == 'False' else '-',
            })
        else:
            # Insert an empty row for missing weeks
            reformatted_results.append({
                "season_week": season_week.replace('_', '/Week '),
                "indicated_training": '(missing)',
                "true_increase": '',
                "estimated_increase": '',
                "pass": '',
            })

    return reformatted_results[::-1]

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
        'training_processing_results': reformat_data(training_processing_results)
    }


if __name__ == '__main__':
    app.run(debug=True)

