import datetime
import time
import werkzeug
werkzeug.cached_property = werkzeug.utils.cached_property
import warnings
from bs4 import GuessedAtParserWarning
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)
from robobrowser import RoboBrowser

browser = None

class FTPBrowser:
    def __init__(self):
        self.rbrowser = RoboBrowser()
        self.login()

    def login(self, max_attempts=3, logtype='full', logfile='default'):
        with open('data/credentials.txt', 'r') as f:
            credentials = f.readline().split(',')

        attempts = 0
        while attempts < max_attempts:
            try:
                self.rbrowser.open(url='http://www.fromthepavilion.org/')
                form = self.rbrowser.get_form(action='securityCheck.htm')

                if form is None:
                    raise Exception("Login form not found")

                form['j_username'] = credentials[0]
                form['j_password'] = credentials[1]

                self.rbrowser.submit_form(form)

                if self.check_login():
                    logtext = 'Successfully logged in as user {}.'.format(credentials[0])
                    log_event(logtext, logtype=logtype, logfile=logfile)
                    return
                else:
                    logtext = 'Failed to log in as user {} ({}/{} attempts)'.format(credentials[0], attempts + 1,
                                                                                    max_attempts)
                    log_event(logtext, logtype=logtype, logfile=logfile)
            except Exception as e:
                logtext = 'Error during login: {}'.format(str(e))
                log_event(logtext, logtype=logtype, logfile=logfile)

            attempts += 1
            time.sleep(10)  # Adding a delay between attempts

        logtext = 'Login failed after {} attempts'.format(max_attempts)
        log_event(logtext, logtype=logtype, logfile=logfile)

    def check_login(self, login_on_failure=True, active_check=False):
        if active_check:
            self.rbrowser.open(url='http://www.fromthepavilion.org/profile.htm')

        if isinstance(self.rbrowser, type(None)):
            if login_on_failure:
                self.login()
            else:
                return False
        else:
            last_page_load = datetime.datetime.strptime(str(self.rbrowser.response.headers['Date'])[:-4] + '+0000', '%a, %d %b %Y %H:%M:%S%z')
            last_page = str(self.rbrowser.parsed)
            if (datetime.datetime.now(datetime.timezone.utc) - last_page_load) < datetime.timedelta(minutes=10) and 'logout.htm' in last_page:
                return True
            else:
                if login_on_failure:
                    log_event('FTP session lost... Reconnecting')
                    self.login()
                else:
                    return False


def initialize_browser():
    global browser
    browser = FTPBrowser()

    return browser


def log_event(logtext, logtype='full', logfile='default', ind_level=0):
    current_time = datetime.datetime.now()
    if type(logfile) == str:
        logfile = [logfile]

    for logf in logfile:
        if logf == 'default':
            logf = 'data/logs/ftp_archiver_output_history.log'
        if logtype in ['full', 'console']:
            print('[{}] '.format(current_time.strftime('%d/%m/%Y-%H:%M:%S')) + '\t' * ind_level + logtext)
        if logtype in ['full', 'file']:
            with open(logf, 'a') as f:
                f.write('[{}] '.format(current_time.strftime('%d/%m/%Y-%H:%M:%S')) + logtext + '\n')

        logtype = 'file' # to prevent repeated console outputs when multiple logfiles are specified


