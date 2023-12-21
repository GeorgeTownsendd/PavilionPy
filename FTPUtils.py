import CoreUtils

CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser

import PlayerDatabase

database_list = ['data/classic-archive/testing/testing.config', 'data/classic-archive/market-archive/market-archive.config']

PlayerDatabase.watch_database_list(database_list)