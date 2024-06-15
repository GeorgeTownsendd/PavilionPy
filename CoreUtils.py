import datetime
import threading
import time
import werkzeug
import os
werkzeug.cached_property = werkzeug.utils.cached_property
import warnings
from bs4 import GuessedAtParserWarning
warnings.filterwarnings("ignore", category=GuessedAtParserWarning)
from robobrowser import RoboBrowser


class SingletonMeta(type):
    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
            return cls._instances[cls]


class FTPBrowser(metaclass=SingletonMeta):
    def __init__(self, auto_login=True):
        self.history = []
        self.override_ratelimit = False
        self.parsed = ''

        self.rbrowser = RoboBrowser()
        if auto_login:
            self.login()

    def login(self, max_attempts=3):
        credentials = self.get_credentials()
        attempts = 0
        while attempts < max_attempts:
            try:
                self._ftpopen('http://www.fromthepavilion.org/')
                form = self.get_form(action='securityCheck.htm')
                if form is None:
                    raise Exception("Login form not found")

                form['j_username'] = credentials[0]
                form['j_password'] = credentials[1]
                log_event('Attempting to login as {}'.format(credentials[0]))
                self.submit_form(form)

                if self.check_login():
                    log_event('Successfully logged in as user {}.'.format(credentials[0]))
                    return
                else:
                    log_event('Failed to log in as user {} ({}/{} attempts)'.format(credentials[0], attempts + 1, max_attempts))
            except ZeroDivisionError as e:
                log_event('Error during login: {}'.format(str(e)))

            attempts += 1
            time.sleep(10)

    def rate_limit(self):
        now = datetime.datetime.utcnow()
        max_wait_time = 0
        limit_triggered = False

        rate_limits = [
            {'duration': datetime.timedelta(minutes=2), 'limit': 100},
            {'duration': datetime.timedelta(minutes=30), 'limit': 500},
            {'duration': datetime.timedelta(hours=6), 'limit': 1000},
            {'duration': datetime.timedelta(days=1), 'limit': 2000},
            {'duration': datetime.timedelta(days=7), 'limit': 5000}
        ]

        for limit in rate_limits:
            window_start = now - limit['duration']
            requests_in_window = [req for req in self.history if req['timestamp'] > window_start]

            if len(requests_in_window) >= limit['limit']:
                wait_time = (requests_in_window[0]['timestamp'] + limit['duration'] - now).total_seconds()
                log_event(f'Rate limit exceeded for {limit["duration"]}. Calculated necessary sleep: {wait_time:.2f} seconds.')
                if wait_time > max_wait_time:
                    max_wait_time = wait_time
                    limit_triggered = True

        if limit_triggered:
            if not self.override_ratelimit:
                log_event(f'Rate limit applied, sleeping for: {max_wait_time:.2f} seconds.')
                time.sleep(max_wait_time)

    def _ftpopen(self, url):
        if 'www.fromthepavilion.org/' not in url:
            log_event('Invalid URL: {}'.format(url))
            return

        self.rate_limit()

        self.rbrowser.open(url)
        page_content = self.rbrowser.response.content
        page_size = len(page_content)
        timestamp = datetime.datetime.utcnow()
        self.history.append({'url': url, 'page_size': page_size, 'timestamp': timestamp})

        self.parsed = self.rbrowser.parsed

    def open(self, url):
        if 'www.fromthepavilion.org/' not in url:
            log_event('Invalid URL: {}'.format(url))
            return

        log_event('Opening URL: {}'.format(url))
        self._ftpopen(url)

        print(self.check_login())

        if not self.check_login():
            log_event('Session expired. Attempting to re-login.')
            self.login()
            self._ftpopen(url)

            if not self.check_login():
                log_event('Failed to load page.')

    def get_form(self, action=None):
        if isinstance(action, type(None)):
            result = self.rbrowser.get_form()
        else:
            result = self.rbrowser.get_form(action=action)
        self.parsed = self.rbrowser.parsed
        return result

    def submit_form(self, form):
        result = self.rbrowser.submit_form(form)
        self.parsed = self.rbrowser.parsed
        return result

    def check_login(self):
        content = str(self.rbrowser.parsed)
        if '<strong>completely free</strong>' in content:
            return False
        return True


    def get_credentials(self):
        with open('data/credentials.txt', 'r') as f:
            return f.readline().strip().split(',')


def initialize_browser(auto_login=True):
    return FTPBrowser(auto_login=auto_login)


def log_event(logtext, logtype='full', logfile='default', ind_level=0):
    current_time = datetime.datetime.utcnow()
    if type(logfile) == str:
        logfile = [logfile]

    for logf in logfile:
        if logf == 'default':
            log_dir = 'data/logs'
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            logf = f'{log_dir}/ftp_archiver_output_history.log'
        if logtype in ['full', 'console']:
            print('[{}] '.format(current_time.strftime('%d/%m/%Y-%H:%M:%S')) + '\t' * ind_level + logtext)
        if logtype in ['full', 'file']:
            with open(logf, 'a') as f:
                f.write('[{}] '.format(current_time.strftime('%d/%m/%Y-%H:%M:%S')) + logtext + '\n')

        logtype = 'file' # to prevent repeated console outputs when multiple logfiles are specified


