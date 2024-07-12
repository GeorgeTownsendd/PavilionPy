from Player import *
from PavilionPy import get_player, load_player_from_database

db_path = 'data/archives/team_archives/team_archives.db'
player_id = 2456157
player = Player(player_id)

live_player_state = get_player(player_id)
db_player_state = load_player_from_database(player_id, db_path=db_path)

player.add_state(live_player_state)
player.add_state(db_player_state)