import CoreUtils
browser = CoreUtils.initialize_browser(auto_login=False)

from flask import Flask, request, jsonify, render_template
import pandas as pd
import sqlite3
from PlayerTracker import PlayerTracker
from FTPUtils import SKILL_LEVELS
from PavilionPy import get_player

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/view_player/<int:playerid>/')
def view_player(playerid):
    player_details = get_player(playerid)

    return render_template('view_player.html', player_details=player_details)


from flask import request


@app.route('/get_filtered_historical_transfer_data', methods=['POST'])
def get_filtered_historical_transfer_data():
    data = request.get_json()  # Ensure that you get JSON data correctly
    filters = data['filters']

    df = pd.read_csv('data/examples/transfer_data_13042024.csv')
    df['SimplifiedBowlType'] = [x[1:] for x in df['BowlType']]

    for filter_ in filters:
        df = df.query(filter_)

    data = df[['Player', 'PlayerID', 'WageReal', 'FinalPrice', 'SimplifiedBowlType']].to_dict(orient='records')
    return jsonify(data)


def reformat_data(training_processing_data):
    first_observation = training_processing_data['first_observation']
    last_observation = training_processing_data['last_observation']
    observation_results = training_processing_data['observation_results']

    def generate_season_weeks(start, end):
        for season in range(start[0], end[0] + 1):
            start_week = start[1] if season == start[0] else 0
            end_week = end[1] + 1 if season == end[0] else 15
            for week in range(start_week, end_week):
                yield f"{season}_{week}"

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
            reformatted_results.append({
                "season_week": season_week.replace('_', '/Week '),
                "indicated_training": '(missing)',
                "true_increase": '',
                "estimated_increase": '',
                "pass": '',
            })

    return reformatted_results[::-1]

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

    return jsonify({'players': sorted(players_list, key=lambda x:x['AgeValue'], reverse=True)})


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
    observation_results_converted = {}
    for key, value in training_processing_results['observation_results'].items():
        str_key = f'{key[0]}_{key[1]}'
        observation_results_converted[str_key] = value

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

