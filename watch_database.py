import argparse
import CoreUtils

CoreUtils.initialize_browser()
browser = CoreUtils.browser.rbrowser

import PlayerDatabase

parser = argparse.ArgumentParser(description='Watch specified databases.')
parser.add_argument('--db_name', nargs='+', help='Names of the databases to watch')

args = parser.parse_args()

if args.db_name:
    PlayerDatabase.watch_database_list(args.db_name)
else:
    print("No database names provided.")
