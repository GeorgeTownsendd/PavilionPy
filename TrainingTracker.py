import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sqlite3
import FTPUtils
from FTPConstants import *

trainingdb = pd.read_csv('data/training_db.csv')
trainingdb['ID'] = trainingdb['ID'].str.lower()


def get_training(training_type, age='16', academy='deluxe', training_talent='None', return_type='numeric', existing_skills=None):
    try:
        ID = f'{academy}{training_talent}{training_type.replace(" Technique", "-Tech")}'.lower()
        relevant_row = trainingdb[trainingdb['ID'] == ID].iloc[0]
        relevant_row.fillna(0, inplace=True)
    except IndexError:
        #print('Training with talent not found in db...')
        ID = f'{academy}{"None"}{training_type.replace(" Technique", "-Tech")}'.lower()
        relevant_row = trainingdb[trainingdb['ID'] == ID].iloc[0]
        relevant_row.fillna(0, inplace=True)

    if not isinstance(existing_skills, type(None)):
        points_earned_multiplier = [1 if x < 10000 else 0.85 for x in existing_skills]
    else:
        points_earned_multiplier = [1] * 7

    if return_type == 'dict':
        skill_increase = {
            skill: round(relevant_row[f'{age}{skill}'] * points_earned_multiplier[i]) for i, skill in enumerate(['Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Power'])
        }

    elif return_type == 'numeric':
        skill_increase = [round(relevant_row[f'{age}{skill}'] * points_earned_multiplier[i]) for i, skill in enumerate(['Bat', 'Bowl', 'Keep', 'Field', 'End', 'Tech', 'Power'])]

    return skill_increase


def get_closest_academy(true_rating_increase, training_type, training_talent, age, existing_skills=[0] * 7):
    academy_levels = ['minimal', 'meagre', 'inadequate', 'reasonable', 'satisfactory', 'good', 'excellent', 'superior', 'lavish', 'luxurious', 'deluxe']
    possible_rating_increases = []

    for academy_level in academy_levels:
        increase = sum(get_training(training_type, training_talent=training_talent, age=age, academy=academy_level, existing_skills=existing_skills))
        possible_rating_increases.append(abs(true_rating_increase-increase))

    best_fit_index = sorted(enumerate(possible_rating_increases), key=lambda x: x[1])[0][0]
    best_fit_name = academy_levels[best_fit_index]

    return best_fit_index, best_fit_name


class SpareSkills:
    def __init__(self):
        self.skills = {skill: {'min': 0, 'max': 999} for skill in ORDERED_SKILLS}

    def update_skill(self, skill_name, points_gained, increased):
        if increased:
            self.skills[skill_name]['max'] = max([points_gained-1, 0])
            self.skills[skill_name]['min'] = 0
        else:
            self.skills[skill_name]['min'] = min(self.skills[skill_name]['min'] + points_gained, self.skills[skill_name]['max'])
            if self.skills[skill_name]['max'] != 999:
                self.skills[skill_name]['max'] = min(self.skills[skill_name]['max'] + points_gained, 999)

    def get_skill_ranges_summary(self):
        summary = f'Total Unknown: {sum(self.skills[skill]["max"] - self.skills[skill]["min"] for skill in ORDERED_SKILLS)}/7000\n'
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
        training_increase_by_skill = get_training(training_type, academy=self.academy_level, training_talent=self.training_talent, return_type='numeric', age=str(self.age_years), existing_skills=self.skills*1000)

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
                try:
                    update_summary = self.update_player(row, row['Training'])
                    self.print_weekly_summary(idx, update_summary)
                except IndexError:
                    self.age_years, self.age_weeks = expected_age_years, expected_age_weeks
                    print('Missing week! ')
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
            if row[talent] == 'Prodigy' or ('Gifted' in row[talent]):
                return row[talent]
    return 'None'


def get_player_rows(player_id, db_path= 'data/archives/team_archives/team_archives.db', team_name='Meridians'):
    df = fetch_players_data(db_path, team_name)
    player_rows = prepare_player_data(df, player_id)

    return player_rows


def process_player_training(player_id, academy_level='deluxe'):
    player_rows = get_player_rows(player_id)

    training_talent = determine_training_talent(player_rows)
    initial_data = player_rows[0]
    p = PlayerTracker(initial_data, training_talent=training_talent, academy_level=academy_level)

    p.process_weekly_training(player_rows)

    return p

class PlayerPredictor:
    def __init__(self, initial_state):
        self.initial_state = initial_state

        self.initial_skills = initial_state.skills
        self.initial_spares = initial_state.spare_ratings_estimate.skills


    def get_predicted_training_values(self):
        # This is a placeholder implementation
        return [250, 100, 100, 100, 100, 100, 100]

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

    def calculate_future_ages(self, starting_years, starting_weeks, training_weeks_n):
        age_years = starting_years
        age_weeks = starting_weeks
        training_weeks = []
        for week_i in range(training_weeks_n):
            age_weeks += 1
            if age_weeks > 14:
                age_weeks = 0
                age_years += 1
            training_weeks.append((age_years, age_weeks))

        return training_weeks

    def determine_training_regime(self, target_skills, estimate_types=['min', 'avg', 'max']):
        sublevel_estimates = []
        for estimate_name in estimate_types:
            if estimate_name == 'min':
                min_sublevels = (self.initial_skills * 1000) + np.array([self.initial_spares[skill]['min'] for skill in ORDERED_SKILLS])
                sublevel_estimates.append(min_sublevels)
            elif estimate_name == 'avg':
                avg_sublevels = (self.initial_skills * 1000) + (np.array([(self.initial_spares[skill]['min']+self.initial_spares[skill]['max'])/2 for skill in ORDERED_SKILLS]))
                sublevel_estimates.append(avg_sublevels)
            elif estimate_name == 'max':
                max_sublevels = (self.initial_skills * 1000) + np.array([self.initial_spares[skill]['max'] for skill in ORDERED_SKILLS])
                sublevel_estimates.append(max_sublevels)


        training_ages = self.calculate_future_ages(self.initial_state.age_years, self.initial_state.age_weeks, 45)
        training_regimes = {}
        for i, starting_skills in enumerate(sublevel_estimates):
            training_regime = []
            current_skills = starting_skills
            for age_year, age_week in training_ages:
                skill_deficits = target_skills - current_skills

                if max(skill_deficits) < 500:
                    break

                most_deficit_skill_index = np.argmax(skill_deficits)
                print(ORDERED_SKILLS[most_deficit_skill_index])
                print(skill_deficits)

                most_effective_training = 'None'
                most_effective_training_increases = np.zeros(len(ORDERED_SKILLS))
                for training_type in ['Batting', 'Bowling', 'Fielding', 'Keeping', 'Keeper-Batsman', 'All-Rounder', 'Bowling-Tech', 'Batting-Tech', 'Strength', 'Fitness']:
                    estimated_training_increases = get_training(training_type, academy=self.initial_state.academy_level, training_talent=self.initial_state.training_talent, return_type='numeric', age=age_year, existing_skills=current_skills)
                    if estimated_training_increases[most_deficit_skill_index] > most_effective_training_increases[most_deficit_skill_index]:
                        most_effective_training = training_type

                self.apply_training(current_skills, )
                current_skills += most_effective_training_increases.astype('int64')
                training_regime.append(most_effective_training)
            training_regimes[['min', 'avg', 'max'][i]] = training_regime

        return training_regimes

    @staticmethod
    def apply_training(start_estimated_sublevels, training_type, age_years, academy_level, training_talent):
        training_increase_by_skill = get_training(training_type, academy=academy_level, training_talent=training_talent, return_type='numeric', age=age_years, existing_skills=start_estimated_sublevels)
        end_estimated_sublevels = start_estimated_sublevels + training_increase_by_skill

        return end_estimated_sublevels


import numpy as np
import matplotlib.pyplot as plt

def plot_player_predicted_training(player_states, start_season_week, start_age, training_descriptions):
    base_width = 6.4  # Base width in inches
    base_length = 20  # Base length in data points
    data_points = len(player_states)  # Assuming all inner lists have the same length
    figure_width = max(base_width, base_width * (data_points / base_length))
    figure_height = 4.8 + 2.0  # Adjusted for additional subplot space

    # Create main plot with dynamic size
    fig, ax1 = plt.subplots(figsize=(figure_width, figure_height))
    plt.subplots_adjust(bottom=0.3, top=0.80, right=0.8)  # Adjust for subplot and secondary x-axis

    tick_freq = 5  # weeks
    data_transposed = np.array(player_states).T
    weeks = np.arange(data_transposed.shape[1])

    season_start, season_week_start = start_season_week
    age_years_start, age_weeks_start = start_age

    age_weeks_total = age_weeks_start + weeks
    season_weeks_total = season_week_start + weeks

    ages_years = age_years_start + age_weeks_total // 15
    ages_weeks = age_weeks_total % 15

    seasons = season_start + season_weeks_total // 15
    season_weeks = season_weeks_total % 15

    # Initialize lists for crossing points
    crossing_weeks = []
    crossing_values = []

    # Plot the player states data and find crossings
    for index, line_data in enumerate(data_transposed):
        ax1.plot(weeks, line_data, label=f'{ORDERED_SKILLS[index]}')  # Adjusted label

        # Check for crossing points
        for i in range(1, len(line_data)):
            if (line_data[i - 1] // 1000 < line_data[i] // 1000) or (line_data[i - 1] // 1000 > line_data[i] // 1000):
                proportion = (1000 - line_data[i - 1] % 1000) / (line_data[i] - line_data[i - 1])
                crossing_week = weeks[i - 1] + proportion * (weeks[i] - weeks[i - 1])
                crossing_value = (line_data[i - 1] // 1000 + 1) * 1000

                crossing_weeks.append(crossing_week)
                crossing_values.append(crossing_value)

    # Plot crossing points
    ax1.plot(crossing_weeks, crossing_values, '*', c='black', markersize=12, markerfacecolor='gold', label='Skill Pop')

    ax1.set_xlabel('Player Age')
    ax1.set_ylabel('Skill Level')
    ax1.legend(loc='upper left', bbox_to_anchor=(1, 0.95))
    ax1.grid(which='major', color='#DDDDDD', linewidth=1)
    ax1.grid(which='minor', color='#EEEEEE', linestyle=':', linewidth=1)
    ax1.minorticks_on()

    age_labels = [f'{y}y{w}w' for y, w in zip(ages_years, ages_weeks)]
    ax1.set_xticks(weeks[::tick_freq])
    ax1.set_xticklabels(age_labels[::tick_freq])

    # Create a second x-axis for season/week
    ax2 = ax1.twiny()
    season_labels = [f'S{season}W{week}' for season, week in zip(seasons, season_weeks)]
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_xticks(weeks[::tick_freq])
    ax2.set_xticklabels(season_labels[::tick_freq])
    ax2.spines["top"].set_position(("axes", 1.1))
    ax2.xaxis.set_ticks_position("top")
    ax2.xaxis.set_label_position("top")

    ax3 = fig.add_axes([ax1.get_position().x0, 0.015, ax1.get_position().width, 0.2], sharex=ax1)
    ax3.set_xlim(ax1.get_xlim())
    ax3.set_ylim((0, 1))
    ax3.tick_params(axis='y', which='both', left=False, labelleft=False)
    ax3.tick_params(axis='x', which='both', bottom=False, labelbottom=False)

    training_colors = {
        "Batting": "lightblue",
        "Bowling": "lightgreen",
        "Fielding": "coral",
        "Keeping": "lightpink",
        "Keeper-Batsman": "lavender",
        "All-Rounder": "wheat",
        "Bowling-Tech": "khaki",
        "Batting-Tech": "aqua",
        "Strength": "salmon",
        "Fitness": "peachpuff",
    }
    bar_width = 1
    for i, description in enumerate(training_descriptions):
        bar_color = training_colors.get(description, 'grey')
        ax3.bar(weeks[i] + 0.5, 1, width=bar_width, color=bar_color, edgecolor='black')
        ax3.text(weeks[i] + 0.5, 0.5, f'W{i+1}: {description}', ha='center', va='center', rotation=90, fontsize=8)

    plt.show()
    #plt.savefig('test2.png', dpi=300)

#tracked_player = process_player_training('2456157', academy_level='reasonable')
#predicted_player = PlayerPredictor(tracked_player)

#t1 = ['Fielding', 'Bowling'] * 11
#t2 = ['Bowling'] * 40
#t3 = t1 + t2

#player_states = predicted_player.apply_training_regime(t3)

#plot_player_predicted_training(player_states, (57, 10), (16, 12), t3)