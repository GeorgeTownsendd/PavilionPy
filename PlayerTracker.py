import sqlite3
import pandas as pd
import numpy as np
from FTPUtils import calculate_player_birthweek
from TrainingTracker import SpareSkills, get_training, determine_training_talent
from CoreUtils import log_event

ORDERED_SKILLS = ['Batting', 'Bowling', 'Keeping', 'Fielding', 'Endurance', 'Technique', 'Power']

class Player:
    def __init__(self, player_id):
        player = self.load_player_database_entries(player_id, limit_n=1).iloc[0]

        self.permanent_attributes = {
            k: player[k] for k in ['Player', 'PlayerID', 'BatHand', 'BowlType', 'Talent1', 'Talent2']
        }

        self.permanent_attributes['TrainingTalent'] = determine_training_talent([player.to_dict()])
        self.permanent_attributes['BirthWeek'] = calculate_player_birthweek(player)


    @staticmethod
    def load_player_database_entries(player_id, limit_n=999):
        database_path = 'data/archives/team_archives/team_archives.db'
        conn = sqlite3.connect(database_path)
        df = pd.read_sql_query(f'SELECT * FROM players WHERE PlayerID = {player_id} LIMIT {limit_n}', conn)
        conn.close()

        return df


class PlayerTracker(Player):
    def __init__(self, player_id, academy='reasonable'):
        super().__init__(player_id)
        self.academy = academy

        self.player_states = self.load_player_database_entries(self.permanent_attributes['PlayerID']).sort_values(by='DataTimestamp', ascending=True)
        self.recorded_weeks = [(row['DataSeason'], row['DataWeek']) for i, row in self.player_states.iterrows()]
        self.n_player_states = len(self.recorded_weeks)
        self.player_states_dic = {
            week: self.player_states.iloc[i] for i, week in enumerate(self.recorded_weeks)
        }

        self.spare_skills = SpareSkills()
        self.initialise_player_state()

        for week_n in range(1, self.n_player_states):
            self.process_measurement(week_n)

        self.spare_rating = self.player_states.iloc[-1]['Rating'] - sum(self.player_states.iloc[-1][ORDERED_SKILLS] * 1000)
        self.known_sublevels = np.array([self.spare_skills.skills[skill]['min'] for skill in ORDERED_SKILLS])
        self.total_known_sublevels = sum(self.known_sublevels)
        self.known_skills = (self.player_states.iloc[-1][ORDERED_SKILLS] * 1000) + self.known_sublevels
        self.total_unknown_spare_rating = self.spare_rating - self.total_known_sublevels

        self.solved_skills = [False if self.spare_skills.skills[skill]['max'] == 999 else True for skill in self.spare_skills.skills.keys()]
        self.n_solved_skills = sum(self.solved_skills)
        estimated_spare_rating_per_unsolved_skill = self.total_unknown_spare_rating / (7-self.n_solved_skills)
        self.estimated_skills = self.known_skills + np.array([0 if skill_solved else estimated_spare_rating_per_unsolved_skill for skill_solved in self.solved_skills])

    def initialise_player_state(self):
        initial_player_state = self.player_states.iloc[0]
        initial_player_skills = initial_player_state[ORDERED_SKILLS] * 1000
        first_training_type = initial_player_state['Training']

        estimated_training_increases = get_training(first_training_type, age=initial_player_state['AgeYear'], academy=self.academy, training_talent=self.permanent_attributes['TrainingTalent'], existing_skills=initial_player_skills)
        for skill_name, points_gained in zip(ORDERED_SKILLS, estimated_training_increases):
            self.spare_skills.update_skill(skill_name, points_gained, increased=False)

    def process_measurement(self, week_n):
        previous_week = self.player_states.iloc[week_n-1]
        current_week = self.player_states.iloc[week_n]

        dt = ((current_week['DataSeason'] * 15) + current_week['DataWeek']) - ((previous_week['DataSeason'] * 15) + previous_week['DataWeek'])
        if dt > 1:
            log_event(f'WARNING: Missing {dt-1} measurements prior to {(current_week[["DataSeason", "DataWeek"]])}')

        skill_pops = current_week[ORDERED_SKILLS] - previous_week[ORDERED_SKILLS]
        estimated_training_increases = get_training(current_week['Training'], age=current_week['AgeYear'], academy=self.academy, training_talent=self.permanent_attributes['TrainingTalent'], existing_skills=previous_week[ORDERED_SKILLS])
        for skill_name, points_gained, skill_popped in zip(ORDERED_SKILLS, estimated_training_increases, skill_pops):
            self.spare_skills.update_skill(skill_name, points_gained, increased=skill_popped)


if __name__ == '__main__':
    p = PlayerTracker('2457918')

