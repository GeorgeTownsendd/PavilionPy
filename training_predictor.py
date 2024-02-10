import pandas as pd
import numpy as np
import sqlite3

import PavilionPy as pp
import FTPUtils

def get_player_core_skills(player_id):
    df = pd.DataFrame({'PlayerID': [player_id]})
    df = pp.add_player_columns(df, ['Skills', 'Talents', 'AgeYear'])
    df = FTPUtils.convert_text_to_numeric_skills(df)

    return df


trainingdb = pd.read_csv('data/training_db.csv')


def get_training(training_type, age='16', academy='deluxe', training_talent='None', return_type='dict'):
    ID = f'{academy}{training_talent}{training_type}'

    relevant_row = trainingdb[trainingdb['ID'] == ID].iloc[0]

    relevant_row.fillna(0, inplace=True)

    if return_type == 'dict':
        skill_increase = {
            skill: int(relevant_row[f'{age}{skill}']) for skill in ['Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Power']
        }

    elif return_type == 'numeric':
        skill_increase = [int(relevant_row[f'{age}{skill}']) for skill in ['Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Power']]

    return skill_increase


db_path = "data/archives/market_archive/market_archive.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT Batting,Bowling,Keeping,Fielding,Endurance,Technique,Power,Rating,AgeYear FROM players WHERE PLAYERID = '2338602' LIMIT 1")

rows = cur.fetchall()
player = np.array(rows[0])
training = (np.array(get_training('Strength', academy='reasonable', training_talent='Gifted (Power)', return_type='numeric', age=player[8]))) * 15
conn.close()

player[:7] *= 1000
spare = player[7] - (sum(player[:7]))
avg_spare = spare // 7

old_minimum = player[:7]
new_minimum = old_minimum + training
old_maximum = old_minimum + avg_spare
new_maximum = old_maximum + training


for i, skill in enumerate(['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power']):
    print(f'{skill}: ')
    print(f'\tOld min: \t\t{old_minimum[i]}')
    print(f'\tNew min: \t\t{new_minimum[i]} (+{training[i]})')
    print(f'\tOld est.: \t\t{old_maximum[i]}')
    print(f'\tNew est.: \t\t{new_maximum[i]} (+{training[i]})')


