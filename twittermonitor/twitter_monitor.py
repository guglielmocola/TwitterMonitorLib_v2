import twittermonitor._utils as tmu
from twittermonitor._crawler import Crawler
from twittermonitor._token_manager import TokenManager

import json
import os
import datetime
import threading
import time

_tm_instance_active = False

class TwitterMonitor:
    def __init__(self, verbose=True):
        global _tm_instance_active  #, _tm_config

        self._lock = threading.Lock()

        # Ensure TwitterMonitor is a singleton, i.e. only one object can be defined.
        if _tm_instance_active is not False:
            return

        self._verbose = verbose

        self._managers = {}  # name: TokenManager
        self._managers_by_level = []  # TokenManagers ordered by credential level, from essential to academic.

        self._crawlers = {'active': {}, 'paused': {}}  # name: crawler

        self._credentials_info = {}
        self._credentials = {}  # saved as user/app_name: bearer_token

        # Try loading credentials.
        c_file_path = tmu.tm_config['credentials_file']
        try:
            self._load_credentials(c_file_path)  # fill self.credentials
        except Exception as error:
            print(f'Error: unable to load credentials from file "{c_file_path}" -- {repr(error)}')
            raise error

        n_credentials = len(self._credentials)
        if n_credentials == 0:
            print(f'Error: no credentials found in file "{c_file_path}"')
            raise (Exception(f'Error: no credentials found in file "{c_file_path}"'))

        if self._verbose:
            plural = ''
            if n_credentials > 1:
                plural = 's'
            print(f'{n_credentials} credential{plural} loaded from file "{c_file_path}"')

        # Load or create dataset folder.
        data_dir = tmu.tm_config['data_path']
        if not os.path.isdir(data_dir):
            try:
                os.mkdir(data_dir)
            except Exception as error:
                print(f'Error: unable to create dataset path "{data_dir}"')
                raise (error)
        else:
            # dataset folder already exists, check for content and load it
            list_dir = [dI for dI in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, dI))]
            # print(list_dir)
            crawlers = []
            for d in list_dir:
                #                 print(f'Existing crawler {d} found -- attempting to load...')
                #                 print(d)
                try:
                    crawler = Crawler(d)
                except Exception as error:
                    print(f'Unable to load crawler {d} -- {error}')
                else:
                    if crawler.deleted:
                        print(f'Ignored crawler {d} as it was deleted by user')
                    else:
                        self._crawlers['paused'][d] = crawler
                        print(f'Existing Crawler {d} loaded successfully (paused)')

        # Create a TokenManager for each credential
        for cn in self._credentials:
            if self._verbose:
                print(f'Creating TokenManager for credential {cn}...')
            try:
                self._managers[cn] = TokenManager(cn, self._credentials[cn])
            except Exception as error:
                print(f'Error: unable to create TokenManager for credential "{cn}" -- {repr(error)}')
                raise error
            else:
                if self._verbose:
                    print(f'Success. Credential {cn} has level: {self._managers[cn].level}')

        # Fill managers_by_level list.
        for level in tmu.tm_config['api_limits']:
            for mn in self._managers:
                manager = self._managers[mn]
                if manager.level == level:
                    self._managers_by_level.append(manager)

        # Assign current instance to the single allowed TM instance
        _tm_instance_active = self

        # Finally, launch thread to keep everything checked and updated
        self._check_thread = threading.Thread(target=self._check_status)
        self._check_thread.start()

    def __new__(cls, *args, **kwargs):
        """Ensure TwitterMonitor is a singleton, i.e. only one object can be defined.
        """
        global _tm_instance_active
        if _tm_instance_active is not False:
            print('Error: only one TwitterMonitor object can be defined. Returning the already-existing object.')
            return _tm_instance_active
        return super(TwitterMonitor, cls).__new__(cls, *args, **kwargs)

    def _check_status(self):
        # global _tm_config

        # Endless loop, check every 'check_interval' seconds.
        while (True):
            with self._lock:
                # Loop through all managers
                for m in self._managers.values():
                    # Get list of crawlers
                    m_crawlers = list(m.crawlers.values())
                    # XXX

                    for c in m_crawlers:
                        # Check end conditions
                        current_date = tmu.tm_date()
                        if isinstance(c.end_date, datetime.datetime) and c.end_date < current_date:
                            # XXX TODO
                            print(f"Crawler time has expired")

                        start_date = tmu.tm_date_fromstr(c.activity_log[-1]['start'])
                        c.activity_log[-1]['duration'] = str(current_date - start_date).split('.')[0]
                        c.save()

            time.sleep(tmu.tm_config['check_interval'])

    def _load_credentials(self, c_file_path):
        fields = ['user', 'app_name', 'bearer_token']
        error_msg = f"Error while loading credentials from file {c_file_path}"
        #         try:
        with open(c_file_path, "r") as c_file:
            line = 0
            for x in c_file:
                line += 1
                x = x.rstrip()
                if x == "":
                    continue

                c = json.loads(x)
                for f in fields:
                    if f not in c:
                        #                         print(f"{error_msg} -- Missing field '{f}' in credential on line {line}")
                        raise Exception(f"{error_msg} -- Missing field '{f}' in credential on line {line}")
                c_name = f"{c['user']}/{c['app_name']}"
                if c_name in self._credentials:
                    print(f'Warning: repeated credential {c_name} on line {line} -- ignored')
                    continue
                self._credentials[c_name] = c['bearer_token']

    #         except Exception as error:
    #             return False, f"{error_msg} -- {error}"
    #         if len(self.credentials) == 0:
    #             return False, f"{error_msg} -- No credentials found."
    #         return True, 'OK'

    def _credentials_info(self):
        """Info on credentials
        For each level, find number of tokens, max rules, and used rules.

        Returns:
            dict: level: {'tokens', 'rules_max', 'rules_used'}
        """
        credentials_info = {}
        for m in self._managers.values():
            if m.level not in credentials_info:
                credentials_info[m.level] = {
                    'tokens': 1, 'rules_max': m.max_rules, 'rules_used': len(m.rules)}
            else:
                credentials_info[m.level]['tokens'] += 1
                credentials_info[m.level]['rules_max'] += m.max_rules
                credentials_info[m.level]['rules_used'] += len(m.rules)
        return credentials_info

    def _check_crawler_name(self, name):
        # global _tm_config

        # Check whether the name is already in use.
        if name in self._crawlers['active'] or name in self._crawlers['paused']:
            return False, f'Crawler with name "{name}" already exists'

        # Check whether the name is valid
        max_len = tmu.tm_config['crawler_name_max_l']
        if len(name) > max_len:
            return False, f'Maximum name length is {max_len} characters'

        for l in name:
            if not l.isalnum() and l not in ['-', '_']:
                return False, f'Invalid char "{l}" in name. Allowed characters are: a-z A-Z 0-9 "-" "_"'

        # Check directory with same name already exists
        if os.path.isdir(tmu.tm_config['data_path'] + '/' + name):
            return False, f'A directory named "{name}" already exists'

        return True, 'OK'

    def _assign_crawler(self, crawler):
        # Prepare error msg.
        # Add crawler to TokenManager.
        # Try all token managers starting from the lowest credential level.
        rules_used = -1
        for m in self._managers_by_level:
            rules_used = m.add_crawler(crawler)
            if rules_used > 0:
                # Crawler has been regularly "accepted" by the TManager and listening has started.
                self._crawlers['active'][crawler.name] = crawler
                # Remove from paused, if present
                if crawler.name in self._crawlers['paused']:
                    del self._crawlers['paused'][crawler.name]  # remove crawler from 'paused'
                break

        if rules_used < 0:
            error_msg = 'Error: unable to find a token with enough free rules. You may want to try using multiple crawlers with a subset of the targets'
            if self._verbose:
                print(error_msg)
            return False, error_msg

        if self._verbose:
            success_msg = f'OK: crawler {crawler.name} activated to {crawler.mode} the specified targets'
        return True, success_msg

    def track(self, name, keywords):
        """Create and start a new crawler aimed at traking specified keywords

        Args:
            name (str): the new crawler's name. Must be unique and also a valid folder name, as
                crawler's data is saved into dataset_path/{crawler.name}/
            keywords (list[str]): keywords to be tracked by the crawler. Tweets containing at least
                one of the keywords are detected and saved

        Returns:
            status, msg (bool, str): status is True if succeded; msg contains the error message
                in case of error
        """
        with self._lock:
            # Prepare error msg.
            error_msg = 'Error: Unable to create track crawler -- '

            # Check crawler name
            status, error = self._check_crawler_name(name)
            if status is False:
                if self._verbose:
                    print(error_msg + error)
                return False, error_msg + error

            # Create crawler
            try:
                crawler = Crawler(name, False, keywords)
            except Exception as error:
                if self._verbose:
                    print(error_msg + repr(error))
                return False, error_msg + repr(error)

            return self._assign_crawler(crawler)

    def follow(self, name, accounts):
        """Create and start a new crawler aimed at following specified accounts

        Args:
            name (str): the new crawler's name. Must be unique and also a valid folder name, as
                crawler's data is saved into dataset_path/{crawler.name}/
            accounts (list[str]): account IDs or screen names to be tracked by the crawler.
                Tweets from, to, or retweeted from one of the specified accounts are detected and saved

        Returns:
            status, msg (bool, str): status is True if succeded; msg contains the error message
                in case of error
        """
        with self._lock:
            # Prepare error msg
            error_msg = 'Error: Unable to create follow crawler -- '

            # Check crawler name
            status, error = self._check_crawler_name(name)
            if status is False:
                if self._verbose:
                    print(error_msg + error)
                return False, error_msg + error

            # Create crawler
            try:
                crawler = Crawler(name, True, accounts)
            except Exception as error:
                if self._verbose:
                    print(error_msg + repr(error))
                return False, error_msg + repr(error)

            return self._assign_crawler(crawler)

    def pause(self, name):
        """Pause a crawler

        Args:
            name (str): name of the crawler to be paused

        Returns:
            status, msg (bool, str): status is True if succeded; msg contains the error message
                in case of error
        """
        with self._lock:
            # First check input is correct
            if name not in self._crawlers['active']:
                if name not in self._crawlers['paused']:  # and name not in self.crawlers['ended']:
                    error_msg = f'Error: crawler "{name}" does not exist'
                else:
                    error_msg = f'Error: crawler "{name}" is already paused'

                if self._verbose:
                    print(error_msg)
                return False, error_msg

            # OK, crawler is really active. Let's pause it
            crawler = self._crawlers['active'][name]
            crawler.manager.remove_crawler(crawler)

            # Update crawler info
            crawler.manager = False
            self._crawlers['paused'][crawler.name] = crawler
            del self._crawlers['active'][crawler.name]

            success_msg = f'Crawler "{name}" successfully paused'
            if self._verbose:
                print(success_msg)
            return True, success_msg

    def resume(self, name):
        """Resume a paused crawler

        Args:
            name (str): name of the crawler to be resume

        Returns:
            status, msg (bool, str): status is True if succeded; msg contains the error message
                in case of error
        """
        with self._lock:
            # First check the crawler is actually paused
            if name not in self._crawlers['paused']:
                if name not in self._crawlers['active']:
                    error_msg = f'Error: crawler "{name}" does not exist'
                else:
                    error_msg = f'Error: crawler "{name}" is already active'

                if self._verbose:
                    print(error_msg)
                return False, error_msg

            # Try resuming the crawler
            crawler = self._crawlers['paused'][name]
            return self._assign_crawler(crawler)

    def delete(self, name):
        """Delete a paused crawler from TwitterMonitor
        The crawler is set as deleted and removed from TwitterMonitor. It will not be re-loaded
        if a new TwitterMonitor object is created. However, the crawler's data on the filesystem
        is not deleted.

        Args:
            name (str): name of the crawler to be deleted

        Returns:
            status, msg (bool, str): status is True if succeded; msg contains the error message
                in case of error
        """
        with self._lock:
            # First check the crawler is actually paused
            if name not in self._crawlers['paused']:
                if name not in self._crawlers['active']:
                    error_msg = f'Error: crawler "{name}" does not exist'
                else:
                    error_msg = f'Error: crawler "{name}" is active and cannot be deleted'

                if self._verbose:
                    print(error_msg)
                return False, error_msg

            # OK, let's delete the paused crawler
            crawler = self._crawlers['paused'][name]

            # Prepare error msg
            error_msg = f'Error: Unable to delete crawler "{name}" -- '
            # Create crawler
            try:
                crawler.delete(delete_data)
            except Exception as error:
                if self._verbose:
                    print(error_msg + repr(error))
                return False, error_msg + repr(error)

            del self._crawlers['paused'][name]

            success_msg = f'Crawler "{name}" successfully deleted from TwitterMonitor'
            if self._verbose:
                print(success_msg)
            return True, success_msg

    def info(self):
        """Print a summary of the TwitterMonitor's status"""
        with self._lock:
            # global _tm_config
            name_spaces = tmu.tm_config['crawler_name_max_l'] + 2

            if len(self._crawlers['active']):
                print('*** ACTIVE CRAWLERS ***')
                print(
                    f'{"name":<{name_spaces}}'
                    #                      f'{"type (targets)":<15}'
                    f'{"type":<8}'
                    f'{"targets":<9}'
                    #                      f'{"type":<8}'                    
                    f'{"started (UTC)":<16}'
                    f'{"tot active":<12}'
                    f'{"tweets"}'
                    #                      f'{"targets"}'
                )
                for c in self._crawlers['active'].values():
                    print(c)
                print('\n')

            if len(self._crawlers['paused']):
                print('*** PAUSED CRAWLERS ***')
                print(
                    f'{"name":<{name_spaces}}'
                    f'{"type":<8}'
                    f'{"targets":<9}'
                    #                      f'{"type (targets)":<15}'
                    #                      f'{"type":<8}'
                    f'{"paused (UTC)":<16}'
                    f'{"tot active":<12}'
                    f'{"tweets"}'
                    #                      f'{"targets"}'
                )
                for c in self._crawlers['paused'].values():
                    print(c)
                print('\n')

            print('*** CRDENTIALS ***')
            # Find info on available "levels" and "rules"
            credentials_info = self._credentials_info()

            print(
                f'{"Type":<10}'
                f'{"Tokens":<10}'
                f'{"Rules used/total"}'
            )

            for level in tmu.tm_config['api_limits']:
                if level in credentials_info:
                    tokens = credentials_info[level]['tokens']
                    rules_max = credentials_info[level]['rules_max']
                    rules_used = credentials_info[level]['rules_used']
                    print(
                        f'{level:<10}'
                        f'{tokens:<10}'
                        f'{rules_used}/{rules_max}'
                    )

    def info_crawler(self, name):
        # Find crawler
        if name not in self._crawlers['paused'] and name not in self._crawlers['active']:
            print(f'Error: crawler named "{name} not found')
            return

        if name in self._crawlers['paused']:
            crawler = self._crawlers['paused'][name]
            status = 'paused'
        else:
            crawler = self._crawlers['active'][name]
            status = 'active'

        space_c1 = 14
        tot_seconds = sum(crawler.session_durations())
        print(
            f'*** CRAWLER "{name}" ***\n'
            f'{"Status":<{space_c1}}{status}\n'
            f'{"Mode":<{space_c1}}{crawler.mode}\n'
            f'{"Targets":<{space_c1}}{tmu.tm_quoted_list(crawler.targets)}\n'
            f'{"Tot active":<{space_c1}}{tmu.tm_duration_str(tot_seconds)}\n'
            f'{"Tweets":<{space_c1}}{crawler.tweets}\n\n'

            'Activity Log:'
        )
        a_count = 1
        for a in crawler.activity_log:
            print(
                f' #{a_count:<5}start UTC {a["start"][2:(a["start"].rfind(":"))]}'
                f' -- duration {a["duration"]}'
            )
            a_count += 1

