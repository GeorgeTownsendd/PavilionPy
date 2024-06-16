# PavilionPy
## Overview

PavilionPy automates data retrieval functions for managers of the fantasy cricket game 'From the Pavilion'.

https://www.fromthepavilion.org/

## Setup
Requires a file "data/credentials.txt" to exist with a username on the first line and a password on the second line.

## Usage
### Transfer Market Monitoring
The "monitor_transfer_market" script will continuously download players passing through the transfer market. They are saved to the sqlite file "data/archives/market_archive/market_archive.db"

### Data Collection
An example of how to use the player search functionality to collect information on the quality of youth recruits by country:

```
    nationalities = list(range(1, 18))
    players_list = []

    for n_id in nationalities:
        national_players = []
        for age_weeks in [0, 1, 2]:
            players_in_age = best_player_search(search_settings={'country': f'{n_id}', 'age': '16', 'ageWeeks': f'{age_weeks}', 'pages': 'all'})
            national_players.append(players_in_age)
        all_national_players = pd.concat(national_players)

        with sqlite3.connect('data/u16_players_s56w03') as conn:
            all_national_players.to_sql('players', conn, if_exists='append', index=False)
```

A plot generated from the collected data: 
![member_v_nonmember](https://github.com/GeorgeTownsendd/PavilionPy/assets/7286540/cbe32969-e32f-4ebb-95e3-1d8810d94167)

### Team Name Caching
Team names are cached in a separate sqlite file "data/PavilionPy.db". 

### Player Viewer + Transfer History Search
<img src="https://github.com/GeorgeTownsendd/PavilionPy/assets/7286540/e98ad11d-937f-4552-9864-8aee3c476642" width="720">
