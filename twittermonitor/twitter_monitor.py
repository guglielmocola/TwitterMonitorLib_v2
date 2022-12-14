import twittermonitor._utils as tmu
from twittermonitor._crawler import Crawler
from twittermonitor._token_manager import TokenManager
import json
import os
import threading
import time

_tm_instance_active = False

class TwitterMonitor:
    """A class to ease real-time track/follow of tweets using the Twitter API v2

    Designed for interactive use in a Python Jupyter Notebook.

    Provides the following main functionalities:
     * Manage one or more credentials, which are automatically loaded by the constructor from file credentials.jsonl
     * Start/pause track/follow real-time tweet collection campaigns ("crawlers")
     * Show information on ongoing and paused crawlers
     * Save collected tweets into daily .jsonl files
     * Crawlers' information is automatically reloaded from disk if the application is restarted
    """

    def __init__(self):
        """Initialize TwitterMonitor object

        Only one object can be instantiated, to avoid conflicts on the same credentials.

        Performs the following operations:
         * credentials are automatically loaded from credentials.jsonl and an exception is raised if no valid
            credentials are found;
         * The path for the dataset is created; if already existing, it attempts to load information on existing
            crawlers, which are set into the "paused" state
         * Finally, two threads are launched: one to dump collected tweets from ongoing crawlers into the dataset;
            another to check ongoing operations, update crawlers' information files, and report the overall status
            in the log file.
        """
        global _tm_instance_active

        self._lock = threading.Lock()

        # Ensure TwitterMonitor is a singleton, i.e. only one object can be defined.
        if _tm_instance_active is not False:
            return

        self._managers = {}  # name: TokenManager
        self._managers_by_level = []  # TokenManagers ordered by credential level, from essential to academic.

        self._crawlers = {'active': {}, 'paused': {}}  # name: crawler

        self._credentials = {}  # saved as user/app_name: bearer_token

        # Try loading credentials.
        c_file_path = tmu.tm_config['credentials_file']
        tmu.tm_log.info(f'Loading credentials from file "{c_file_path}"')
        try:
            self._load_credentials(c_file_path)  # fill self.credentials
        except Exception as error:
            tmu.tm_log.error(f'Unable to load credentials -- {repr(error)}')
            raise error

        n_credentials = len(self._credentials)
        if n_credentials == 0:
            tmu.tm_log.error(f'No credentials found in file "{c_file_path}"')
            raise (Exception(f'No credentials found in file "{c_file_path}"'))

        plural = ''
        if n_credentials > 1:
            plural = 's'
        tmu.tm_log.info(f'{n_credentials} credential{plural} loaded from file "{c_file_path}"')

        # Load or create dataset folder.
        data_dir = tmu.tm_config['data_path']
        if not os.path.isdir(data_dir):
            try:
                os.mkdir(data_dir)
            except Exception as error:
                tmu.tm_log.error(f'Unable to create dataset path "{data_dir}"')
                raise error
        else:
            # dataset folder already exists, check for content and load it
            list_dir = [dI for dI in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, dI))]
            # print(list_dir)
            # crawlers = []
            for d in list_dir:
                try:
                    crawler = Crawler(d)
                except Exception as error:
                    tmu.tm_log.error(f'Unable to load crawler {d} -- {error}')
                else:
                    if crawler.deleted:
                        tmu.tm_log.error(f'Ignored crawler {d} as it was deleted by user')
                    else:
                        self._crawlers['paused'][d] = crawler
                        tmu.tm_log.info(f'Existing Crawler {d} loaded successfully (paused)')

        # Create a TokenManager for each credential
        invalid_credentials = []
        for cn in self._credentials:
            tmu.tm_log.info(f'Creating TokenManager for credential "{cn}"...')
            try:
                self._managers[cn] = TokenManager(cn, self._credentials[cn])
            except Exception as error:
                tmu.tm_log.error(f'Unable to create TokenManager for credential "{cn}" -- {repr(error)}')
                invalid_credentials.append(cn)
                continue
            else:
                tmu.tm_log.info(f'Done. Credential "{cn}" has level: "{self._managers[cn].level}"')

        # Check at least one credential was valid
        if len(invalid_credentials) == len(self._credentials):
            tmu.tm_log.error(f'No valid credential found in file "{c_file_path}"')
            raise (Exception(f'No valid credential found in file "{c_file_path}"'))
        # Remove invalid credentials from self._credentials

        for invalid in invalid_credentials:
            del self._credentials[invalid]

        n_credentials = len(self._credentials)
        plural = 's' if n_credentials > 1 else ''
        tmu.tm_log.info(f'{len(self._credentials)} valid credential{plural} found')

        # Fill managers_by_level list.
        for level in tmu.tm_config['api_limits']:
            for mn in self._managers:
                manager = self._managers[mn]
                if manager.level == level:
                    self._managers_by_level.append(manager)

        # Assign current instance to the single allowed TM instance
        _tm_instance_active = self

        # Launch thread to dump tweet jsons into files
        self.tweet_saver_thread = threading.Thread(target=self._tweet_saver)
        self.tweet_saver_thread.start()

        # Finally, launch thread to keep everything checked and updated
        self._check_thread = threading.Thread(target=self._check_status)
        self._check_thread.start()

    def __new__(cls, *args, **kwargs):
        """Ensure TwitterMonitor is a singleton

        Only one object can be defined (instantiated) to avoid conflicts on the use of the same credentials.
        """
        global _tm_instance_active
        if _tm_instance_active is not False:
            tmu.tm_log.error('Only one TwitterMonitor object can be defined. Returning the already-existing object.')
            return _tm_instance_active
        return super(TwitterMonitor, cls).__new__(cls, *args, **kwargs)

    def _tweet_saver(self):
        """Thread to dump collected tweets into the dataset
        """
        while True:
            saved_one = False
            for c in self._crawlers['active'].values():
                if len(c.tweets_to_save) > 0:
                    saved_one = True
                    tweets_to_save = []
                    with c.lock:
                        tweets_to_save = c.tweets_to_save
                        c.tweets_to_save = []
                        c.tweets += len(tweets_to_save)
                    for t in tweets_to_save:
                        with open(t['path'], "a") as write_file:
                            json.dump(t['tweet'], write_file)
                            write_file.write('\n')

            for c in self._crawlers['paused'].values():
                if len(c.tweets_to_save) > 0:
                    saved_one = True
                    tweets_to_save = []
                    with c.lock:
                        tweets_to_save = c.tweets_to_save
                        c.tweets_to_save = []
                        c.tweets += len(tweets_to_save)
                    for t in tweets_to_save:
                        with open(t['path'], "a") as write_file:
                            json.dump(t['tweet'], write_file)
                            write_file.write('\n')

            if not saved_one:
                time.sleep(10)

    def _check_status(self):
        """Thread to check ongoing operations

        Updates crawlers' information in the dataset; reports overall status into the log file.
        """
        last_log_time = time.time()

        # Endless loop, check every 'check_interval' seconds.
        while True:
            with self._lock:
                # Loop through all managers
                for m in self._managers.values():
                    # Get list of crawlers
                    m_crawlers = list(m.crawlers.values())

                    write_log = False
                    current_time = time.time()
                    if current_time-last_log_time > tmu.tm_config['log_interval']:
                        write_log = True
                        last_log_time = current_time

                    log_str = []

                    for c in m_crawlers:
                        current_date = tmu.tm_date()
                        # Check end conditions XXX TODO for NEXT version
                        # if isinstance(c.end_date, datetime.datetime) and c.end_date < current_date:
                        #     tmu.tm_log.warning(f"Crawler time has expired")

                        # Update duration and save crawler
                        start_date = tmu.tm_date_fromstr(c.activity_log[-1]['start'])
                        c.activity_log[-1]['duration'] = str(current_date - start_date).split('.')[0]
                        c.save()
                        log_str.append(f'{c.name}({c.tweets})')

                    if write_log:
                        tmu.tm_log.info(f'Active:{";".join(log_str)}')

            time.sleep(tmu.tm_config['check_interval'])

    def _load_credentials(self, c_file_path):
        """Load credentials from file credentials.jsonl
        """
        fields = ['user', 'app_name', 'bearer_token']
        with open(c_file_path, "r") as c_file:
            line = 0
            for x in c_file:
                line += 1
                x = x.rstrip()
                if x == "":
                    continue

                try:
                    c = json.loads(x)
                except Exception as error:
                    tmu.tm_log.warning(f'Skipped line {line}, not a valid json -- {error}')
                    continue

                field_error = False
                for f in fields:
                    if f not in c:
                        tmu.tm_log.warning(f'Skipped credential on line {line} -- missing field "{f}"')
                        field_error = True
                        break
                        # raise Exception(f"{error_msg} -- Missing field '{f}' in credential on line {line}")
                if field_error:
                    continue
                c_name = f"{c['user']}/{c['app_name']}"
                if c_name in self._credentials:
                    tmu.tm_log.warning(f'Ignored repeated credential {c_name} on line {line}')
                    continue
                self._credentials[c_name] = c['bearer_token']

    def _credentials_info(self):
        """Info on credentials
        For each level, find number of tokens, max rules, and used rules.

        Returns:
            dict: level: {'tokens', 'rules_max', 'rules_used'}
        """
        c_info = {}
        for m in self._managers.values():
            if m.level not in c_info:
                c_info[m.level] = {
                    'tokens': 1, 'rules_max': m.max_rules, 'rules_used': len(m.rules)}
            else:
                c_info[m.level]['tokens'] += 1
                c_info[m.level]['rules_max'] += m.max_rules
                c_info[m.level]['rules_used'] += len(m.rules)
        return c_info

    def _check_crawler_targets(self, targets, mode):
        """Check crawler's targets are defined properly
        """
        mode_verb = 'tracks' if mode == 'track' else 'follows'
        mode_obj = 'keywords' if mode == 'track' else 'accounts'
        if type(targets) != list:
            return False, f'{mode_obj} must be a list of strings'

        targets = set(targets)

        all_crawlers = self._crawlers['active']
        for c in self._crawlers['paused']:
            all_crawlers[c] = self._crawlers['paused'][c]

        # all_crawlers = self._crawlers['active'] | self._crawlers['paused'] XXX merge introduced in python 3.9
        for c in all_crawlers.values():
            if c.mode == mode and targets == set(c.targets):
                return False, f'Crawler with name "{c.name}" already {mode_verb} the same {mode_obj}'

        return True, 'OK'

    def _check_crawler_name(self, name):
        """Check crawler's name is defined properly
        """
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
        """Assign the crawler to a TokenManager
        """
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
            error_msg = 'Unable to find a token with enough free rules. You may want to try using multiple ' \
                        'crawlers with a subset of the targets'
            tmu.tm_log.error(error_msg)
            return False

        success_msg = f'Crawler "{crawler.name}" activated to {crawler.mode} the specified targets'

        tmu.tm_log.info(success_msg)
        return True

    def track(self, name, keywords):
        """Create and start a new crawler aimed at tracking specified keywords

        Args:
            name (str): the new crawler's name. Must be unique and also a valid folder name, as
                crawler's data is saved into dataset_path/{crawler.name}/
            keywords (list[str]): keywords to be tracked by the crawler. Tweets containing at least
                one of the keywords are detected and saved

        Returns:
            bool: True for success, False otherwise.
        """
        with self._lock:
            # Prepare error msg.
            error_msg = 'Unable to create track crawler -- '

            # Check crawler name
            status, error = self._check_crawler_name(name)
            if status is False:
                tmu.tm_log.error(error_msg + error)
                return False

            # Check keywords
            status, error = self._check_crawler_targets(keywords, 'track')
            if status is False:
                tmu.tm_log.error(error_msg + error)
                return False

            # Create crawler
            try:
                crawler = Crawler(name, False, keywords)
            except Exception as error:
                tmu.tm_log.error(error_msg + repr(error))
                return False

            return self._assign_crawler(crawler)

    def follow(self, name, accounts):
        """Create and start a new crawler aimed at following specified accounts

        Args:
            name (str): the new crawler's name. Must be unique and also a valid folder name, as
                crawler's data is saved into dataset_path/{crawler.name}/
            accounts (list[str]): account IDs or screen names to be tracked by the crawler.
                Tweets from, to, or retweeted from one of the specified accounts are detected and saved

        Returns:
            bool: True for success, False otherwise.
        """
        with self._lock:
            # Prepare error msg
            error_msg = 'Unable to create follow crawler -- '

            # Check crawler name
            status, error = self._check_crawler_name(name)
            if status is False:
                tmu.tm_log.error(error_msg + error)
                return False

            # Check accounts
            status, error = self._check_crawler_targets(accounts, 'follow')
            if status is False:
                tmu.tm_log.error(error_msg + error)
                return False

            # Create crawler
            try:
                crawler = Crawler(name, True, accounts)
            except Exception as error:
                tmu.tm_log.error(error_msg + repr(error))
                return False

            return self._assign_crawler(crawler)

    def pause(self, name):
        """Pause a crawler

        Args:
            name (str): name of the crawler to be paused

        Returns:
            bool: True for success, False otherwise.
        """
        with self._lock:
            # First check input is correct
            if name not in self._crawlers['active']:
                if name not in self._crawlers['paused']:  # and name not in self.crawlers['ended']:
                    error_msg = f'Crawler "{name}" does not exist'
                else:
                    error_msg = f'Crawler "{name}" is already paused'

                tmu.tm_log.error(error_msg)
                return False

            # OK, crawler is really active. Let's pause it
            crawler = self._crawlers['active'][name]
            crawler.manager.remove_crawler(crawler)

            # Update crawler info
            crawler.manager = False
            self._crawlers['paused'][crawler.name] = crawler
            del self._crawlers['active'][crawler.name]

            success_msg = f'Crawler "{name}" successfully paused'
            tmu.tm_log.info(success_msg)
            return True

    def resume(self, name):
        """Resume a paused crawler

        Args:
            name (str): name of the crawler to be resume

        Returns:
            bool: True for success, False otherwise.
        """
        with self._lock:
            # First check the crawler is actually paused
            if name not in self._crawlers['paused']:
                if name not in self._crawlers['active']:
                    error_msg = f'Crawler "{name}" does not exist'
                else:
                    error_msg = f'Crawler "{name}" is already active'

                tmu.tm_log.error(error_msg)
                return False

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
            bool: True for success, False otherwise.
        """
        with self._lock:
            # First check the crawler is actually paused
            if name not in self._crawlers['paused']:
                if name not in self._crawlers['active']:
                    error_msg = f'Crawler "{name}" does not exist'
                else:
                    error_msg = f'Crawler "{name}" is active and cannot be deleted'

                tmu.tm_log.error(error_msg)
                return False

            # OK, let's delete the paused crawler
            crawler = self._crawlers['paused'][name]

            # Prepare error msg
            error_msg = f'Unable to delete crawler "{name}" -- '
            # Create crawler
            try:
                crawler.delete()
            except Exception as error:
                tmu.tm_log.error(error_msg + repr(error))
                return False

            del self._crawlers['paused'][name]

            success_msg = f'Crawler "{name}" successfully deleted from TwitterMonitor'
            tmu.tm_log.info(success_msg)
            return True

    def info(self):
        """Print a summary of ongoing operations

        Shows the main information on active crawlers, paused crawlers, and credentials (available rules)
        """
        with self._lock:
            # global _tm_config
            name_spaces = tmu.tm_config['crawler_name_max_l'] + 2

            if len(self._crawlers['active']):
                print('*** ACTIVE CRAWLERS ***')
                print(
                    f'{"Name":<{name_spaces}}'
                    #                      f'{"type (targets)":<15}'
                    f'{"Type":<8}'
                    f'{"Targets":<9}'
                    #                      f'{"type":<8}'                    
                    f'{"Started (UTC)":<16}'
                    f'{"Tot active":<12}'
                    f'{"Tweets"}'
                    #                      f'{"targets"}'
                )
                for c in self._crawlers['active'].values():
                    print(c)
                print('\n')

            if len(self._crawlers['paused']):
                print('*** PAUSED CRAWLERS ***')
                print(
                    f'{"Name":<{name_spaces}}'
                    f'{"Type":<8}'
                    f'{"Targets":<9}'
                    #                      f'{"type (targets)":<15}'
                    #                      f'{"type":<8}'
                    f'{"Paused (UTC)":<16}'
                    f'{"Tot active":<12}'
                    f'{"Tweets"}'
                    #                      f'{"targets"}'
                )
                for c in self._crawlers['paused'].values():
                    print(c)
                print('\n')

            print('*** CRDENTIALS ***')
            # Find info on available "levels" and "rules"
            c_info = self._credentials_info()

            print(
                f'{"Type":<10}'
                f'{"Tokens":<10}'
                f'{"Rules used/total"}'
            )

            for level in tmu.tm_config['api_limits']:
                if level in c_info:
                    tokens = c_info[level]['tokens']
                    rules_max = c_info[level]['rules_max']
                    rules_used = c_info[level]['rules_used']
                    print(
                        f'{level:<10}'
                        f'{tokens:<10}'
                        f'{rules_used}/{rules_max}'
                    )

    def info_crawler(self, name):
        """Print detailed information on a specific crawler

        Args:
            name (str): name of the crawler
        """
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
