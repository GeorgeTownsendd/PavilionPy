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
            self.skills[skill_name]['max'] = points_gained
            self.skills[skill_name]['min'] = 0
        else:
            self.skills[skill_name]['min'] = min(self.skills[skill_name]['min'] + points_gained, self.skills[skill_name]['max'])
            if self.skills[skill_name]['max'] != 999:
                self.skills[skill_name]['max'] = min(self.skills[skill_name]['max'] + points_gained, 999)



    def print_skill_ranges(self):
        """
        Print the current minimum and maximum spare rating for each skill.
        """

        print(
            f'Total Unknown: {sum([self.skills[skill_name]["max"] - self.skills[skill_name]["min"] for skill_name in ORDERED_SKILLS])}')
        for skill, r in self.skills.items():
            print(f"{skill}: ({r['min']}, {r['max']})")#Min = {r['min']}, Max = {r['max']}")


class PlayerTracker:
    def __init__(self, initial_data, training_talent='None', academy_level='deluxe'):
        """
        Initializes the PlayerTracker with the first week's data.
        :param initial_data: A dictionary containing the initial state of the player.
        :param training_talent: The player's training talent, if any.
        :param academy_level: The level of the academy.
        """
        self.skills = np.array([initial_data[skill] for skill in ORDERED_SKILLS])
        self.rating = initial_data['Rating']
        self.age_years = initial_data['AgeYear']
        self.age_weeks = initial_data['AgeWeeks']
        self.training_talent = training_talent
        self.academy_level = academy_level
        self.spare_ratings_estimate = SpareSkills()

    def update_player(self, row, training_type):
        """
        Updates the player's state based on the new week's data.
        :param row: A dictionary containing the week's data.
        :param training_type: The type of training undertaken during the week.
        """

        new_skills = np.array([row[skill] for skill in ORDERED_SKILLS])
        new_rating = row['Rating']
        skill_pops = new_skills - self.skills

        # Ensure training increases are correctly fetched
        training_increase_by_skill = get_training(training_type, academy=self.academy_level, training_talent=self.training_talent, return_type='numeric', age=str(self.age_years))

        skill_pop_names = []
        for i, increase in enumerate(skill_pops):
            if increase > 0:
                skill_pop_names.append(ORDERED_SKILLS[i])
                self.spare_ratings_estimate.update_skill(ORDERED_SKILLS[i], training_increase_by_skill[i], True)
            else:
                self.spare_ratings_estimate.update_skill(ORDERED_SKILLS[i], training_increase_by_skill[i], False)

        # Correctly calculate the true rating increase
        true_rating_increase = new_rating - self.rating

        self.skills = new_skills
        self.rating = new_rating  # Update the player's rating to the new value for future comparisons
        self.age_years = row['AgeYear']
        self.age_weeks = row['AgeWeeks']

        print(f'Estimated Rating Increase: {sum(training_increase_by_skill)}, True Rating Increase: {true_rating_increase}')
        if skill_pop_names:
            print(f'Skill increases: {", ".join(skill_pop_names)} with respective training increases: {[training_increase_by_skill[ORDERED_SKILLS.index(skill)] for skill in skill_pop_names]}')
        else:
            print("No skill increases this week.")

    def process_weekly_training(self, player_rows):
        """
        Processes each week's training data for the player.
        :param player_rows: A list of dictionaries, each containing a week's data.
        """
        for idx, row in enumerate(player_rows[1:], start=1):  # Skip the first row as it is used for initialization
            expected_age_years, expected_age_weeks = self.predict_next_age()
            if (row['AgeYear'], row['AgeWeeks']) == (expected_age_years, expected_age_weeks):
                self.update_player(row, row['Training'])
                print(f'------ Week {idx}:')
                self.spare_ratings_estimate.print_skill_ranges()
            else:
                print(f"Age mismatch: expected ({expected_age_years}.{expected_age_weeks}), got ({row['AgeYear']}.{row['AgeWeeks']})")

    def predict_next_age(self):
        """
        Predicts the next age of the player, handling year transitions.
        :return: A tuple (expected_next_years, expected_next_weeks)
        """
        expected_next_weeks = self.age_weeks + 1
        expected_next_years = self.age_years
        if expected_next_weeks > 14:
            expected_next_weeks = 1  # Adjust based on your dataset (1-indexed weeks)
            expected_next_years += 1
        return expected_next_years, expected_next_weeks


def fetch_players_data(db_path, team_group):
    """
    Fetches players data for a specified team group from the SQLite database.
    :param db_path: The path to the SQLite database file.
    :param team_group: The team group to filter the players by.
    :return: A DataFrame containing the fetched players data.
    """
    conn = sqlite3.connect(db_path)
    query = f"SELECT * FROM players WHERE TeamGroup = '{team_group}'"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def prepare_player_data(df, player_id):
    """
    Prepares the data for initializing PlayerTracker by extracting rows for a specific player.
    :param df: DataFrame containing players data.
    :param player_id: The ID of the player to prepare data for.
    :return: A list of dictionaries, each representing a week's data for the player.
    """
    player_rows = df[df['PlayerID'] == player_id].to_dict('records')
    return player_rows

def determine_training_talent(player_rows):
    """
    Determines the player's training talent based on their data rows.
    :param player_rows: A list of dictionaries, each representing a week's data for the player.
    :return: The training talent of the player.
    """
    for row in player_rows:
        for talent in ['Talent1', 'Talent2']:
            if row[talent] == 'Prodigy' or 'Gifted' in row[talent]:
                return row[talent]
    return 'None'

# Specify the path to your SQLite database file
db_path = 'data/archives/team_archives/team_archives.db'

# Fetch player data for the team "Meridians"
df = fetch_players_data(db_path, 'Meridians')

# Example usage for a specific player
player_id = '2583586'
player_rows = prepare_player_data(df, player_id)

# Determine training talent for the player
training_talent = determine_training_talent(player_rows)

# Assuming PlayerTracker is already defined and updated to use the new initialization parameters
initial_data = player_rows[0]
p = PlayerTracker(initial_data, training_talent=training_talent, academy_level='reasonable')

# Process training for all subsequent weeks
p.process_weekly_training(player_rows)
