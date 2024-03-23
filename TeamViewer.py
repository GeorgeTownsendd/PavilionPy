from flask import Flask, request, jsonify, render_template
import pandas as pd
import sqlite3
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
    df = pd.read_sql_query('SELECT Player, PlayerID, TeamName, AgeDisplay FROM players', conn)
    df = df.drop_duplicates(subset=['PlayerID'], keep='first')
    conn.close()

    players_list = df.values.tolist()

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

    return {
        'player_details': player_details,
        'known_skills': known_skills,
        'estimated_spare': estimate_spare,
        'estimated_max_training': estimated_max_training
    }


if __name__ == '__main__':
    app.run(debug=True)

