import twittermonitor._utils as tmu
import json
import os
import datetime
import pytimeparse
import threading

class Crawler:
    """Class to manage the information associated to a crawler (track or follow).
    """
    
    def __init__(self, name, is_follow=False, targets=[]):
        self.lock = threading.Lock()
        self.tweets_to_save = []

        self.name = name
        self.path = tmu.tm_config['data_path'] + f"/{self.name}"
        self.manager = False  # Set externally by the TokenManager with a ref to itself
        self.rules = []  # Set externally by the TokenManager with the ids of the crawler's rules
        self.deleted = False

        # Date-based threshold
        # self.end_date = False  # for a future version, not enabled yet

        # Tweet language filter
        # self.languages = [] # for a future version, not enabled yet

        # Tweet count.
        self.tweets = 0

        # Activity log
        self.activity_log = []  # array of {'start': (str) date, 'duration': (str) timedelta} objects

        # Try loading the crawler from filesystem.
        if os.path.isdir(self.path):
            self.load()
            return

        if len(targets) == 0:
            raise (Exception(f'Targets not provided and unable to load crawler from path {self.path}'))

        # Use arguments to initialize crawler.
        self.targets = targets
        if is_follow:
            self.mode = 'follow'
        else:
            self.mode = 'track'

        # Prepare path.
        os.mkdir(self.path)

        # Save info into file for the first time.
        self.save()

    def load(self):
        """Load crawler info from info.json file.
        """
        with open(self.path + "/info.json", "r") as read_file:
            info = json.load(read_file)

        # Check required fields are there
        fields = ['name', 'deleted', 'mode', 'targets', 'tweets', 'activity_log']
        for f in fields:
            if f not in info:
                err_msg = f"Field '{f}' is not defined in the info.json file of Crawler '{self.name}'"
                raise (Exception(err_msg))

        self.deleted = info['deleted']
        if self.deleted:
            # Crawler has been deleted, nothing else to do, it will be ignored
            return

        if info['name'] != self.name:
            err_msg = f"Name field '{info['name']}'in info.json different from crawler '{self.name}'"
            raise (Exception(err_msg))
        self.mode = info['mode']
        self.targets = info['targets']
        self.activity_log = info['activity_log']

        # Check activity log is well-defined
        if type(self.activity_log) != list or len(self.activity_log) <= 0:
            err_msg = f"Error in the activity log of crawler '{self.name}'"
            raise (Exception(err_msg))
        for a in self.activity_log:
            if 'start' not in a or 'duration' not in a:
                err_msg = f"Error in the activity log of crawler '{self.name}'"
                raise (Exception(err_msg))

        # Find tweet count value.
        self.tweets = info['tweets']

    def save(self):
        """Save crawler info into info.json file.
        """
        info = {
            'name': self.name,
            'mode': self.mode,
            'targets': self.targets,
            'deleted': self.deleted,
            'tweets': self.tweets,
            'activity_log': self.activity_log
        }

        with open(self.path + "/info.json", "w") as write_file:
            json.dump(info, write_file, indent=4)

    def delete(self):
        """Set crawler as deleted and update info.json file.
        Crawler will not be loaded again.
        """
        self.deleted = True
        self.save()

    def session_durations(self):
        """ How long this crawler have (or had) been running

        Returns:
            list int: List of durations (in seconds) for each activity recorded in self.activity_log
        """
        durations = []
        for activity in self.activity_log:
            duration_seconds = pytimeparse.parse(activity['duration'])
            durations.append(duration_seconds)
        return durations

    def __str__(self):
        """Str representation of the Crawler
        """
        durations = self.session_durations()

        if len(self.rules) > 0:
            # Active crawler. Report last session's start date
            #             tot_seconds = durations[-1]
            last_date = self.activity_log[-1]['start']
        else:
            # Paused crawler. Report last end date
            #             tot_seconds = sum(durations)
            last_date = tmu.tm_date_tostr(
                tmu.tm_date_fromstr(self.activity_log[-1]['start']) + datetime.timedelta(seconds=durations[-1]))

        tot_seconds = sum(durations)
        elapsed_str = tmu.tm_duration_str(tot_seconds)

        # Remove initial '20' and seconds from last_date
        last_date = last_date[2:(last_date.rfind(':'))]

        n_targets = len(self.targets)
        name_spaces = tmu.tm_config['crawler_name_max_l'] + 2

        return (
            f'{self.name:<{name_spaces}}'
            f'{self.mode:<8}'
            f'{n_targets:<9}'
            f'{last_date:<16}'
            f'{elapsed_str:<12}'
            f'{self.tweets}'
        )