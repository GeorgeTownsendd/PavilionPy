import pandas as pd

trainingdb = pd.read_csv('data/training_db.csv')


def get_training(training_type, age='16', academy='deluxe', training_talent='None'):
    ID = f'{academy}{training_talent}{training_type}'

    relevant_row = trainingdb[trainingdb['ID'] == ID].iloc[0]
    skill_increase = {
        skill: relevant_row[f'{age}{skill}'] for skill in ['End', 'Bat', 'Bowl', 'Tech', 'Power', 'Keep', 'Field']
    }

    return skill_increase

get_training('Batting')