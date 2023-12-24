import CoreUtils

CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser

import PlayerDatabase

database_list = ['testing', 'market-archive']

PlayerDatabase.watch_database_list(database_list)