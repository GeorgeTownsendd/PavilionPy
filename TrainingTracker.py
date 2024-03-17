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

class SpareSkills:
    def __init__(self):
        self.skills = {skill: {'min': 0, 'max': 999} for skill in ORDERED_SKILLS}

    def update_skill(self, skill_name, points_gained, increased):
        if increased:
            self.skills[skill_name]['max'] = (points_gained-1)
            self.skills[skill_name]['min'] = 0
        else:
            self.skills[skill_name]['min'] = min(self.skills[skill_name]['min'] + points_gained, self.skills[skill_name]['max'])
            if self.skills[skill_name]['max'] != 999:
                self.skills[skill_name]['max'] = min(self.skills[skill_name]['max'] + points_gained, 999)

    def get_skill_ranges_summary(self):
        summary = f'Total Unknown: {sum(self.skills[skill]["max"] - self.skills[skill]["min"] for skill in ORDERED_SKILLS)}\n'
        for skill, r in self.skills.items():
            summary += f"{skill}: ({r['min']}, {r['max']})\n"
        return summary.strip()


class PlayerTracker:
    def __init__(self, initial_data, training_talent='None', academy_level='deluxe'):
        self.skills = np.array([initial_data[skill] for skill in ORDERED_SKILLS])
        self.rating = initial_data['Rating']
        self.age_years = initial_data['AgeYear']
        self.age_weeks = initial_data['AgeWeeks']
        self.training_talent = training_talent
        self.academy_level = academy_level
        self.spare_ratings_estimate = SpareSkills()

    def update_player(self, row, training_type):
        new_skills = np.array([row[skill] for skill in ORDERED_SKILLS])
        new_rating = row['Rating']
        skill_pops = new_skills - self.skills
        training_increase_by_skill = get_training(training_type, academy=self.academy_level, training_talent=self.training_talent, return_type='numeric', age=str(self.age_years))

        for i, increase in enumerate(skill_pops):
            if increase > 0:
                self.spare_ratings_estimate.update_skill(ORDERED_SKILLS[i], training_increase_by_skill[i], True)
            else:
                self.spare_ratings_estimate.update_skill(ORDERED_SKILLS[i], training_increase_by_skill[i], False)

        true_rating_increase = new_rating - self.rating
        self.skills = new_skills
        self.rating = new_rating
        self.age_years = row['AgeYear']
        self.age_weeks = row['AgeWeeks']

        return {
            'estimated_rating_increase': sum(training_increase_by_skill),
            'true_rating_increase': true_rating_increase,
            'skill_increases': {ORDERED_SKILLS[i]: training_increase_by_skill[i] for i, increase in enumerate(skill_pops) if increase > 0},
            'training_type': training_type  # Add training_type to the summary
        }

    def print_weekly_summary(self, week_number, update_summary):
        print(f"------ Week {week_number} Summary ------")
        print(f"Training Type: {update_summary['training_type']}")
        print(f"Estimated Rating Increase: {update_summary['estimated_rating_increase']}, True Rating Increase: {update_summary['true_rating_increase']}")
        if update_summary['skill_increases']:
            skill_increases = ', '.join([f"{skill} [+{increase}]" for skill, increase in update_summary['skill_increases'].items()])
            print(f"Skill increases: {skill_increases}")
        else:
            print("No skill increases this week.")
        print(self.spare_ratings_estimate.get_skill_ranges_summary())

    def process_weekly_training(self, player_rows):
        for idx, row in enumerate(player_rows[1:], start=1):
            expected_age_years, expected_age_weeks = self.predict_next_age()
            if (row['AgeYear'], row['AgeWeeks']) == (expected_age_years, expected_age_weeks):
                update_summary = self.update_player(row, row['Training'])
                self.print_weekly_summary(idx, update_summary)
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


def get_player_rows(player_id, db_path= 'data/archives/team_archives/team_archives.db', team_name='Meridians'):
    df = fetch_players_data(db_path, team_name)
    player_rows = prepare_player_data(df, player_id)

    return player_rows


def process_player_training(player_id):
    player_rows = get_player_rows(player_id)

    training_talent = determine_training_talent(player_rows)
    initial_data = player_rows[0]
    p = PlayerTracker(initial_data, training_talent=training_talent, academy_level='reasonable')

    p.process_weekly_training(player_rows)
