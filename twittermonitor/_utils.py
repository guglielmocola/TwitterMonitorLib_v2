import tweepy
import json
import sys
import os
import datetime # import pandas as pd
from tweepy import StreamingClient
import traceback
import math
import threading
import time
import pytimeparse

# Global variable describing the limits of different types of credentials.
tm_config = {
    'api_limits':
        {'essential': {'rules': 5,    'len': 512},
         'elevated':  {'rules': 25,   'len': 512},
         'academic':  {'rules': 1000, 'len': 1024}},
    'credentials_file': 'credentials.jsonl',
    'data_path': 'data_TM',
    'crawler_name_max_l': 25,
    'check_interval': 10
}

def tm_date():
    return datetime.datetime.now(datetime.timezone.utc)


def tm_date_str():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")


def tm_date_tostr(date_dt):
    return date_dt.strftime("%Y-%m-%d %H:%M:%S %Z")


def tm_date_fromstr(date_str):
    date_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %Z")
    return date_dt.replace(tzinfo=datetime.timezone.utc)


def tm_timedelta_fromstr(delta_str):
    return datetime.timedelta(pytimeparse.parse(delta_str))


def tm_quoted_list(values):
    """Converts a list into quoted comma separated values.
        Example: (list) [elem1,elem2,elem3] => (str) 'elem1','elem2','elem3' """
    return ','.join(f"'{x}'" for x in values)


def tm_duration_str(tot_seconds):
    days = math.floor(tot_seconds / (3600 * 24))
    hours = math.floor(tot_seconds % (3600 * 24) / 3600)
    minutes = math.floor(tot_seconds % (3600) / 60)
    if days > 0:
        elapsed_str = f'{days}d {hours}h'
    elif hours > 0:
        elapsed_str = f'{hours}h {minutes}m'
    elif minutes > 0:
        elapsed_str = f'{minutes}m'
    else:
        elapsed_str = f'{tot_seconds}s'
    return elapsed_str
