import pandas as pd
import numpy as np
import sqlite3

#import PavilionPy as pp
import FTPUtils

ORDERED_SKILLS = ['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power']
trainingdb = pd.read_csv('data/training_db.csv')

def get_training(training_type, age='16', academy='deluxe', training_talent='None', return_type='numeric'):
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


def get_player_core_skills(player_id):
    df = pd.DataFrame({'PlayerID': [player_id]})
    df = pp.add_player_columns(df, ['Skills', 'Talents', 'AgeYear', 'Rating', 'AgeWeeks'])
    df = FTPUtils.convert_text_to_numeric_skills(df)

    return df.iloc[0][['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power', 'Rating', 'AgeYear', 'AgeWeeks', 'Talent1', 'Talent2']]


#db_path = "data/archives/market_archive/market_archive.db"
#conn = sqlite3.connect(db_path)
#cur = conn.cursor()
#cur.execute("SELECT Batting,Bowling,Keeping,Fielding,Endurance,Technique,Power,Rating,AgeYear FROM players WHERE PLAYERID = '2338602' LIMIT 1")

#rows = cur.fetchall()
#player = np.array(rows[0])
#training = (np.array(get_training('Strength', academy='reasonable', training_talent='Gifted (Power)', return_type='numeric', age=player[8]))) * 15
#conn.close()

# Define a class to represent each player
class SpareSkills:
    def __init__(self,):
        self.skills = {
            'Batting': {'min': 0, 'max': 999},
            'Bowling': {'min': 0, 'max': 999},
            'Keeping': {'min': 0, 'max': 999},
            'Fielding': {'min': 0, 'max': 999},
            'Endurance': {'min': 0, 'max': 999},
            'Technique': {'min': 0, 'max': 999},
            'Power': {'min': 0, 'max': 999}
        }

    def update_skill(self, skill_name, points_gained, increased):
        """
        Update the minimum and maximum spare rating for a skill after training.
        Adjusts based on whether the skill has increased, and refines the min and max ratings more accurately.
        :param skill_name: The name of the skill to update.
        :param points_gained: The number of rating points gained from the training session.
        :param increased: Boolean indicating if the skill level has increased.
        """
        if increased:
            # If the skill has increased, set the new maximum to the points gained,
            # and reset the minimum to 0.
            self.skills[skill_name]['max'] = points_gained
            self.skills[skill_name]['min'] = 0
        else:
            # If the skill hasn't increased, adjust both the minimum and maximum spare rating
            # by adding the points gained to both, to keep the estimate refined.
            # This ensures that the range reflects a more accurate distribution of spare points.
            # Update the max only if it's not at the initial max setting to ensure
            # it reflects an actual range of possible spare points after an increase.
            if self.skills[skill_name]['max'] != 999:
                self.skills[skill_name]['max'] = min(self.skills[skill_name]['max'] + points_gained, 999)
            self.skills[skill_name]['min'] = min(self.skills[skill_name]['min'] + points_gained,
                                                 self.skills[skill_name]['max'])

    def print_skill_ranges(self):
        """
        Print the current minimum and maximum spare rating for each skill.
        """

        print(
            f'Total Unknown: {sum([self.skills[skill_name]["max"] - self.skills[skill_name]["min"] for skill_name in ORDERED_SKILLS])}')
        for skill, r in self.skills.items():
            print(f"{skill}: ({r['min']}, {r['max']})")#Min = {r['min']}, Max = {r['max']}")
            
class PlayerTracker:
    def __init__(self, skills, rating, age_years, age_weeks, training_talent='None', academy_level='deluxe'):
        self.skills = skills
        self.rating = rating
        self.age_years = age_years
        self.age_weeks = age_weeks
        self.training_talent = training_talent
        self.academy_level = academy_level

        self.spare_ratings_estimate = SpareSkills()

    def update_player(self, new_skills, new_rating, training_type):
        if self.age_weeks == 14:
            self.age_years += 1
            self.age_weeks = 0
        else:
            self.age_weeks += 1

        skill_pops = new_skills - self.skills
        training_increase_by_skill = get_training(training_type, academy=self.academy_level, training_talent=self.training_talent, return_type='numeric', age=self.age_years)
        estimated_rating_increase = sum(training_increase_by_skill)

        print(f'Estimated Rating Increase: {estimated_rating_increase}\nTrue Rating Increase: {new_rating-self.rating}')

        for i, SKILL in enumerate(ORDERED_SKILLS):
            self.spare_ratings_estimate.update_skill(SKILL, training_increase_by_skill[i], increased=skill_pops[i])


# Specify the path to your SQLite database file
db_path = 'data/archives/team_archives/team_archives.db'

# Connect to the SQLite database
conn = sqlite3.connect(db_path)

# SQL query to select all rows with "TeamGroup" = 'Meridians'
query = "SELECT * FROM players WHERE TeamGroup = 'Meridians'"

# Load the query results into a pandas DataFrame
df = pd.read_sql(query, conn)

# Close the database connection
conn.close()

players_dict = {
    player_id: [row[1] for row in group.iterrows()]
    for player_id, group in df.groupby('PlayerID')
}


#df = pd.read_csv('data/trained_players.csv')

#player_id = 2462784
#player_rows = df[df['PlayerID'] == player_id]

player_id = '2583586'
player_rows = players_dict[player_id]

training_talent = 'None'
for talent in [player_rows[0]['Talent1'], player_rows[0]['Talent2']]:
    if talent == 'Prodigy' or 'Gifted' in talent:
        training_talent = talent
        break

player_week1 = player_rows[0]
player_week2 = player_rows[1]

week1_skills = np.array(player_week1[ORDERED_SKILLS].values)
week2_skills = np.array(player_week2[ORDERED_SKILLS].values)

week1_rating = player_week1['Rating']
week2_rating = player_week2['Rating']

week2_training = player_week2['Training']
print(f'Training: {week2_training}')

p = PlayerTracker(week1_skills, week1_rating, player_week1['AgeYear'], player_week1['AgeWeeks'], academy_level='reasonable', training_talent=training_talent)

p.update_player(week2_skills, week2_rating, week2_training)
print('------')
p.spare_ratings_estimate.print_skill_ranges()

player_week3 = player_rows[2]

week2_skills = np.array(player_week3[ORDERED_SKILLS].values)
week3_rating = player_week3['Rating']
week3_training = player_week3['Training']

p.update_player(week2_skills, week3_rating, week3_training)
print('------ 2:')
print(f'Training: {week3_training}')
p.spare_ratings_estimate.print_skill_ranges()



#player_id = 2592591
#player = get_player_core_skills(player_id)

#training_talent = 'None'
#for talent in [player['Talent1'], player['Talent2']]:
#    if talent == 'Prodigy' or 'Gifted' in talent:
#        training_talent = talent
#        break


#player_skills = np.array(player[ORDERED_SKILLS])
#x = PlayerTrainer(player_skills, player['AgeYear'], player['AgeWeeks'], player['Rating'], training_talent, 'reasonable')

#x.apply_training('Fielding')
#x.print_player_status()

#training = (np.array(get_training('Fielding', academy='reasonable', training_talent=training_talent, return_type='numeric', age=player['AgeYear']))) * (15 - player['AgeWeeks'])
#

#player_skills *= 1000
#spare = player['Rating'] - (sum(player_skills[:7]))
#avg_spare = spare // 7

#old_minimum = player_skills
#new_minimum = old_minimum + training
#old_maximum = old_minimum + avg_spare
#new_maximum = old_maximum + training

#print(f'Training talent: {training_talent}')
#print(f"{15 - player['AgeWeeks']} weeks of training")
#for i, skill in enumerate(['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power']):
#    print(f'{skill}: ')
#    print(f'\tOld min: \t\t{old_minimum[i]}')
#    print(f'\tNew min: \t\t{new_minimum[i]} (+{training[i]})')
#    print(f'\tOld est.: \t\t{old_maximum[i]}')
#    print(f'\tNew est.: \t\t{new_maximum[i]} (+{training[i]})')


