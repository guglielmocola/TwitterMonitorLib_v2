import tweepy
import json
import datetime
from tweepy import StreamingClient
import threading
import twittermonitor._utils as tmu

class TokenManager(StreamingClient):
    def __init__(self, name, bearer_token, **kwargs):
        super().__init__(bearer_token, return_type=dict, wait_on_rate_limit=True)
        # global _tm_config

        self.lock = threading.Lock()

        api_limits = tmu.tm_config['api_limits']
        self.name = name
        self.token = bearer_token
        self.crawlers = {}  # name: crawler object
        self._delete_all_rules()
        self.disconnect()
        self.level = self._check_credential()

        self.sessions = []
        #         print(self.level)
        #         return

        self.rules = {}  # rule_id: crawler_name

        self.max_rules = api_limits[self.level]['rules']
        self.max_rule_len = api_limits[self.level]['len']

        # Setup and start the stream
        self.tweet_fields = [
            'attachments',
            'author_id',
            'context_annotations',
            'conversation_id',
            'created_at',
            'entities',
            'geo',
            'in_reply_to_user_id',
            'lang',
            'non_public_metrics',
            'organic_metrics',
            'possibly_sensitive',
            'promoted_metrics',
            'public_metrics',
            'referenced_tweets',
            'reply_settings',
            'source',
            'withheld'
        ]

    def _check_credential(self):
        """Check credentials level (essential, elevated, academic) based on a simple test"""

        # Prepare dummy rules.
        string_element = 'bb'
        rules = []
        for i in range(26):
            rules.append(tweepy.StreamRule(string_element))
            string_element += 'b'

        level = False
        attempts = [26, 25, 5]
        for a in attempts:
            try:
                self.add_rules(rules[:a], dry_run=True)
            except BaseException as err:
                continue
            else:
                if a == 26:
                    level = 'academic'
                elif a == 25:
                    level = 'elevated'
                else:
                    level = 'essential'
                break

        if not level:
            raise (Exception('Error: unable to determine credential level'))
        return level

    def _delete_all_rules(self):
        rules = self.get_rules()
        n_rules = rules['meta']['result_count']
        if n_rules > 0:
            rids = []
            for r in rules['data']:
                rids.append(r['id'])
            self.delete_rules(rids)

    def on_response(self, status):
        #         print('on RESP')
        #         print(status)
        with self.lock:
            tweet = status.data.data
            date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
            print(tweet)
            for r in status.matching_rules:
                # Only process response if rules still exists (it might have been just removed)
                if r.id in self.rules:
                    crawler_name = self.rules[r.id]
                    crawler = self.crawlers[crawler_name]

                    # Save tweet for crawler.
                    file_path = crawler.path + f"/{date_str}.jsonl"

                    with open(file_path, "a") as write_file:
                        json.dump(tweet, write_file)
                        write_file.write('\n')

                    crawler.tweets += 1

    def on_errors(self, errors):
        print(f'{self.name} error -- {errors}')
        return False
        # if status_code == 420:  # end of monthly limit rate (500k)
        #     return False

    def on_connect(self):
        print(f'{self.name} connected')
        self.sessions.append(self.session)

    def on_disconnect(self):
        print(f'{self.name} disconnected')

    def on_disconnect_message(self, message):
        print(f'{self.name} disconnected -- {message}')

    def on_closed(self, response):
        print(f'{self.name} closed -- {response}')

    def on_connection_error(self):
        print(f'{self.name} connection error')

    #         self.disconnect()

    # def on_keep_alive(self):
    #     print(f'{self.name} keep alive')

    def on_request_error(self, status_code):
        print(f'{self.name} request error -- {status_code}')

    def on_exception(self, exception):
        print(f'{self.name} unhandled exception -- {repr(exception)}')

    def add_crawler(self, crawler):
        """Add a new crawler to the TokenManager

        Args:
            crawler (_Crawler): The crawler to be added with all the related info.

        Returns:
            int: Number of rules used for the crawler. Return -1 if add_crawler failed because there are
                not enough free rules available to serve the crawler.
        """
        with self.lock:
            rule = ''
            new_rules = []
            nt = len(crawler.targets)

            i = 0
            while i < nt:
                t = crawler.targets[i]
                if rule == '':
                    # Add first element to a new rule.
                    if crawler.mode == 'follow':
                        rule = f'to:{t} OR from:{t} OR retweets_of:{t}'
                    else:
                        if t.isalnum():
                            rule = t
                        else:
                            rule = f'"{t}"'
                    i += 1
                    if i == nt:
                        new_rules.append(rule)
                    continue

                # Rule already initialized.
                if crawler.mode == 'follow':
                    add_str = f' OR to:{t} OR from:{t} OR retweets_of:{t}'
                else:
                    if t.isalnum():
                        add_str = f' OR {t}'
                    else:
                        add_str = f' OR "{t}"'

                if len(rule) + len(add_str) > self.max_rule_len:
                    new_rules.append(rule)
                    rule = ''
                    continue

                rule += add_str
                i += 1
                if i == nt:
                    new_rules.append(rule)

            # Check if enough rules are available
            available_rules = self.max_rules - len(self.rules)
            if len(new_rules) > available_rules:
                # Unable to add rules.
                return -1

                # Crawler (with its new rules) can be added.
            tweepy_rules = []
            for r in new_rules:
                tweepy_rules.append(tweepy.StreamRule(r))
            resp = self.add_rules(tweepy_rules)
            start_date = tmu.tm_date()
            if 'data' not in resp:
                # Unexpected error while adding rules -- raise an exception!
                err_msg = f'Unexpected error while adding rules to the stream: {resp["errors"]}'
                raise (Exception(err_msg))

            # Manage added rules XXX THIS SHOULD BE ATOMIC with ADD RULE and UNINTERRUPTED by ON RESPONSE XXX
            for r in resp['data']:
                r_id = r['id']
                r_val = r['value']
                self.rules[r_id] = crawler.name
                crawler.rules.append(r_id)
            crawler.manager = self
            # save date
            crawler.activity_log.append({'start': tmu.tm_date_tostr(start_date), 'duration': ''})
            crawler.save()
            self.crawlers[crawler.name] = crawler

            if not self.running:
                self.filter(tweet_fields=self.tweet_fields, threaded=True)

            return len(new_rules)

    def remove_crawler(self, crawler):
        """Remove a crawler from the TokenManager

        Args:
            crawler (Crawler): The crawler to be removed.
        """
        with self.lock:
            # Remove rules in crawler.rules from stream, self.rules
            self.delete_rules(crawler.rules)

            end_date = tmu.tm_date()
            start_date = tmu.tm_date_fromstr(crawler.activity_log[-1]['start'])
            #             crawler.activity_log[-1]['end']      = tmu.tm_date_tostr(end_date)
            crawler.activity_log[-1]['duration'] = str(end_date - start_date).split('.')[0]
            crawler.save()

            for r in crawler.rules:
                del self.rules[r]

            # Reset crawler.rules
            crawler.rules = []

            # Remove crawler from self.crawlers
            del self.crawlers[crawler.name]

            # Disconnect if there are no rules left
            if len(self.rules) == 0:
                self.disconnect()