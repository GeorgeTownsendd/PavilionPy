import pandas as pd
import matplotlib.pyplot as plt
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
            'training_type': training_type
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

    return p

class PlayerPredictor:
    def __init__(self, initial_state):
        self.initial_state = initial_state
        self.initial_skills = initial_state.skills
        self.initial_spares = initial_state.spare_ratings_estimate.skills

    def apply_training_regime(self, training_regime, sublevel_estimate='default'):
        training_weeks_n = len(training_regime)
        age_years = self.initial_state.age_years
        age_weeks = self.initial_state.age_weeks

        training_weeks = []
        for week_i in range(training_weeks_n):
            age_weeks += 1
            if age_weeks > 14:
                age_weeks = 0
                age_years += 1
            training_weeks.append((age_years, age_weeks, training_regime[week_i]))

        if sublevel_estimate == 'default' or sublevel_estimate == 'average_spare':
            initial_sublevels = (self.initial_skills * 1000) + [(self.initial_spares[skill]['max'] + self.initial_spares[skill]['min']) / 2 for skill in ORDERED_SKILLS]
        player_states = [initial_sublevels]
        for training_week in training_weeks:
            after_training = self.apply_training(player_states[-1], training_week[2], training_week[0], self.initial_state.academy_level, self.initial_state.training_talent)
            player_states.append(after_training)

        return player_states

    @staticmethod
    def apply_training(start_estimated_sublevels, training_type, age_years, academy_level, training_talent):
        training_increase_by_skill = get_training(training_type, academy=academy_level, training_talent=training_talent, return_type='numeric', age=age_years)
        end_estimated_sublevels = start_estimated_sublevels + training_increase_by_skill

        return end_estimated_sublevels


def plot_player_predicted_training(player_states, start_season_week, start_age):
    tick_freq = 5 # weeks
    data_transposed = np.array(player_states).T
    weeks = np.arange(data_transposed.shape[1])

    season_start, season_week_start = start_season_week
    age_years_start, age_weeks_start = start_age

    age_weeks_total = age_weeks_start + weeks
    season_weeks_total = season_week_start + weeks

    ages_years = age_years_start + age_weeks_total // 52
    ages_weeks = age_weeks_total % 52

    seasons = season_start + season_weeks_total // 15
    season_weeks = season_weeks_total % 15

    fig, ax1 = plt.subplots()

    for index, line_data in enumerate(data_transposed):
        ax1.plot(weeks, line_data, label=ORDERED_SKILLS[index])

        for i in range(1, len(line_data)):
            if (line_data[i - 1] // 1000 < line_data[i] // 1000) or (line_data[i - 1] // 1000 > line_data[i] // 1000):
                proportion = (1000 - line_data[i - 1] % 1000) / (line_data[i] - line_data[i - 1])
                crossing_week = weeks[i - 1] + proportion * (weeks[i] - weeks[i - 1])
                crossing_value = (line_data[i - 1] // 1000 + 1) * 1000

                ax1.plot(crossing_week, crossing_value, '*', c='black', markersize=10, markerfacecolor='gold')

    ax1.set_xlabel('Player Age (Years and Weeks)')
    ax1.set_ylabel('Skill Level')
    ax1.set_title('Player Predicted Training Outcomes')
    ax1.legend(loc='best')
    ax1.grid(True)

    age_labels = [f'{y}y{w}w' for y, w in zip(ages_years, ages_weeks)]
    ax1.set_xticks(weeks[::tick_freq])
    ax1.set_xticklabels(age_labels[::tick_freq])

    ax2 = ax1.twiny()
    ax2.set_xlabel('Season (Years and Weeks)')
    season_labels = [f'S{season}W{week}' for season, week in zip(seasons, season_weeks)]
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_xticks(weeks[::tick_freq])
    ax2.set_xticklabels(season_labels[::tick_freq])

    ax2.spines["top"].set_position(("axes", 1.1))
    ax2.xaxis.set_ticks_position("top")
    ax2.xaxis.set_label_position("top")

    plt.tight_layout()
    plt.show()



tracked_player = process_player_training('2587313')
predicted_player = PlayerPredictor(tracked_player)
player_states = predicted_player.apply_training_regime(['Fielding'] * 30)

plot_player_predicted_training(player_states, (57, 4), (16, 4))