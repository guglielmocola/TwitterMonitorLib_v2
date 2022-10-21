import twittermonitor._utils as tmu
import json
import os
import datetime
import pytimeparse
import threading

class Crawler:
    def __init__(self, name, is_follow=False, targets=[]):
        # global _tm_config

        self.lock = threading.Lock()
        self.tweets_to_save = []

        self.name = name
        self.path = tmu.tm_config['data_path'] + f"/{self.name}"
        self.manager = False  # Set externally by the TokenManager with a ref to itself
        self.rules = []  # Set externally by the TokenManager with the ids of the crawler's rules
        self.deleted = False

        # Thresholds, should be optional
        self.end_date = False
        #         self.end_tweet = 0  XXX in a future version

        # Tweet count.
        self.tweets = 0

        # Activity log
        self.activity_log = []  # array of {start: (str) date, end: (str) date} objects

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

        #         self.languages = [] # XXX TODO XXX

        # Prepare path.
        os.mkdir(self.path)

        # Save info into file for the first time.
        self.save()

    def load(self):
        """Load crawler info from info.json file.
        """
        #         print('DEBUG: start cr. load')
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
        for a in self.activity_log:
            if 'start' not in a or 'duration' not in a:
                err_msg = f"Error in the activity log of crawler '{self.name}'"
                raise (Exception(err_msg))

        # Find tweet count value.
        self.tweets = info['tweets']

    def save(self):
        """Save crawler info into info.json file.
        """

        # Convert activity_log into strings
        #         a_log_str = []
        #         for activity in self.activity_log:
        #             activity_str = {}
        #             for key in activity:
        #                 if key in ['start', 'end'] and activity[key] != '':
        #                     activity_str[key] = tmu.tm_date_tostr(activity[key])
        #                 elif key == 'duration':
        #                     activity_str[key] = str(activity[key]).split('.')[0]
        #                 else:
        #                     activity_str[key] = str(activity[key])
        #             a_log_str.append(activity_str)

        info = {
            'name': self.name,
            'mode': self.mode,
            'targets': self.targets,
            'deleted': self.deleted,
            'tweets': self.tweets,
            'activity_log': self.activity_log
        }
        #         if isinstance(self.start_date, datetime.datetime):
        #             info['start_date'] = tmu.tm_date_tostr(self.start_date)
        #         if isinstance(self.end_date, datetime.datetime):
        #             info['end_date'] = tmu.tm_date_tostr(self.end_date)
        #         if self.end_tweet > 0:
        #             info['end_tweet'] = self.end_tweet

        ## TODO dump INFO to JSON ###
        with open(self.path + "/info.json", "w") as write_file:
            json.dump(info, write_file, indent=4)

    def delete(self):
        """Set crawler as deleted and update info.json file.
        """
        self.deleted = True
        self.save()

        # Delete data, if required
        #         if delete_data:
        #             # XXX NOT IMPLEMENTED FOR SAFETY REASONS

        #             # Nothing else to do, everything about the crawler is gone
        #             return

        # Data not deleted, write into info.json that the crawler has been deleted
        self.save()

    def session_durations(self):
        """ How long this crawler have(or had) been running

        Return:
            list int: List of durations (in seconds) for each activity recorded
                in self.activity_log
        """
        durations = []
        for activity in self.activity_log:
            start_date = tmu.tm_date_fromstr(activity['start'])
            #         seconds = duration)
            #         time_delta = =seconds)
            duration_seconds = pytimeparse.parse(activity['duration'])
            #             if activity['end'] != '':
            #                 end_date = tmu.tm_date_fromstr(activity['end'])
            #             else:
            #                 end_date = tmu.tm_date()
            durations.append(duration_seconds)
        #             durations.append((end_date-start_date).total_seconds())
        return durations

    def __str__(self):
        # global _tm_config

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

        #         durations =

        #             last_date = self.activity_log[-1]['end']
        #         days = math.floor(tot_seconds/(3600*24))
        #         hours = math.floor(tot_seconds%(3600*24)/3600)
        #         minutes =math.floor(tot_seconds%(3600)/60)
        #         if days > 0:
        #             elapsed_str = f'{days}d {hours}h'
        #         elif hours > 0:
        #             elapsed_str = f'{hours}h {minutes}m'
        #         elif minutes > 0:
        #             elapsed_str = f'{minutes}m'
        #         else:
        #             elapsed_str = f'{tot_seconds}s'
        tot_seconds = sum(durations)
        elapsed_str = tmu.tm_duration_str(tot_seconds)

        # Remove initial '20' and seconds from last_date
        last_date = last_date[2:(last_date.rfind(':'))]

        #         mode_n_targets = f'{self.mode} ({len(self.targets)})'
        n_targets = len(self.targets)
        #         mode_n_targets = f'{self.mode}'
        name_spaces = tmu.tm_config['crawler_name_max_l'] + 2
        #         targets_csv = tmu.tm_quoted_list(self.targets)

        return (
            f'{self.name:<{name_spaces}}'
            f'{self.mode:<8}'
            f'{n_targets:<9}'
            f'{last_date:<16}'
            f'{elapsed_str:<12}'
            f'{self.tweets}'
            #              f'{targets_csv}'
        )