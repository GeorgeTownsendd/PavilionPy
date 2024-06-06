import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture
import matplotlib.ticker as ticker
from itertools import cycle


market_data_file_path = 'data/examples/transfer_data_13042024.csv'

raw_data = pd.read_csv(market_data_file_path)
raw_data['SimplifiedBowlType'] = [x[1:] for x in raw_data['BowlType']]

df = raw_data[raw_data['AgeYear'] >= 20]

summary_data = df[['SummaryBat', 'SummaryBowl', 'SummaryAllr', 'SummaryKeep']]

# Scaling the data
scaler = StandardScaler()
scaled_data = scaler.fit_transform(summary_data)

# Fitting a Gaussian Mixture Model with 4 components
gmm = GaussianMixture(n_components=4, random_state=0)
gmm.fit(scaled_data)

# Predicting the clusters
clusters = gmm.predict(scaled_data)

# Adding the cluster labels to the original dataframe
df['Cluster'] = clusters

# Checking the distribution of players in each cluster
#cluster_counts = df['Cluster'].value_counts()
#print(cluster_counts)

cluster_summaries = df.groupby(['Cluster'])[['SummaryBat', 'SummaryBowl', 'SummaryKeep', 'SummaryAllr']].mean()
#print(cluster_summaries)

cluster_ids = {
    'Batsmen': cluster_summaries['SummaryBat'].idxmax(),
    'Bowler': cluster_summaries['SummaryBowl'].idxmax(),
    'Keeper': cluster_summaries['SummaryKeep'].idxmax(),
    'AllRounder': cluster_summaries['SummaryAllr'].idxmax()
}


def plot_data_seaborn(df, filters, attribute_column):
    # Apply filters to the dataframe
    filtered_df = df.copy()
    for condition in filters:
        filtered_df = filtered_df.query(condition)

    # Retrieve unique attribute values
    unique_attributes = filtered_df[attribute_column].unique()

    # Predefined extended list of markers
    markers = ['o', 's', '^', 'X', 'P', 'D', 'H', '*', 'p', 'v', '>', '<', 'd']  # Extend or adjust markers as needed

    # Cycle markers if there are not enough
    marker_cycle = cycle(markers)

    # Map attributes to markers using cycling
    attribute_marker = {attr: next(marker_cycle) for attr in unique_attributes}

    sns.set(style="darkgrid")
    plt.figure(figsize=(12, 8))
    ax = sns.scatterplot(x='WageReal', y='FinalPrice', hue=attribute_column,
                         style=attribute_column, data=filtered_df,
                         markers=attribute_marker, s=100)  # s is the size of the markers

    handles, labels = ax.get_legend_handles_labels()
    counts = filtered_df[attribute_column].value_counts().reindex(labels)
    new_labels = [f'{label} ({count})' for label, count in zip(labels, counts)]
    ax.legend(handles, new_labels, title=attribute_column, loc='upper left')

    title = f'Wage vs Final Price by {attribute_column}'
    plt.title(title)
    plt.xlabel('Wage')
    plt.ylabel('Final Price')

    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda y, _: f'{y:,.0f}'))

    for _, row in filtered_df.iterrows():
        if row['FinalPrice'] >= 50000:
            ax.text(row['WageReal']-100, row['FinalPrice']+5000, str(row['PlayerID']),
                    fontsize=7, color='black', ha='right')

    # Displaying filters on the plot
    filter_text = "\n".join(filters)
    plt.figtext(0.99, 0.01, 'Filters:\n' + filter_text.replace('Cluster == 0', 'PlayerType == Bowler').replace('6','Capable'), horizontalalignment='right', fontsize=10, color='gray')

    plt.show()

# Example Usage
filters = [
    "AgeYear == 23",
    "FinalPrice >= 2000",
    f"Cluster == {cluster_ids['Bowler']}",
    'Fielding >= 6'
    #'(Talent1 == "Gifted (Fielding)") | (Talent2 == "Gifted (Fielding)")'
]

filters2 = [
    'AgeYear == 16',
    'FinalPrice >= 2000',
    'SummaryBowl >= 4'
]

plot_data_seaborn(df, filters2, 'SimplifiedBowlType')