from flask import Flask, request, jsonify, render_template
import sqlite3
from PlayerTracker import PlayerTracker

app = Flask(__name__)

@app.route('/')
def index():
    # Render a simple form for entering the playerId
    return render_template('index.html')

@app.route('/get_player_skills', methods=['POST'])
def get_player_skills():
    player_id = request.form['playerId']
    player_tracker = PlayerTracker(player_id)

    player_details = {k: str(v) for k, v in player_tracker.permanent_attributes.items()}
    known_skills = {k: int(v) for k, v in player_tracker.known_skills.items()}
    estimated_skills = {k: int(v) for k, v in player_tracker.estimated_skills.items()}

    return {
        'player_details': dict(player_details),
        'known_skills': dict(known_skills),
        'estimated_skills': dict(estimated_skills)
    }

if __name__ == '__main__':
    app.run(debug=True)
