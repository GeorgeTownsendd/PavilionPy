import sqlite3
import os
from PavilionPy import best_player_search

# Example
# Save the top 120 waged UAE players
# 'columns_to_add' as 'all_visible' will download player skils, and requires UAE management roles in-game)

nat_potentials = best_player_search(
    search_settings={'country': '16', 'ageWeeks': '-1', 'pages': 1, 'sortByWage': 'true'},
    columns_to_add='all_visible',
    skill_level_format='numeric',
    players_to_download=1
)

#db_path = 'data/archives/uae_potentials/uae_potentials.db'
#os.makedirs(os.path.dirname(db_path), exist_ok=True)

#conn = sqlite3.connect(db_path)
#nat_potentials.to_sql('potentials', conn, if_exists='append', index=False)
#conn.close()
