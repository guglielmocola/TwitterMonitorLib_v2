[![SBD++](https://img.shields.io/badge/Available%20on-SoBigData%2B%2B-green)](https://sobigdata.d4science.org/group/sobigdata-gateway/explore?siteId=20371853)

Twitter Monitor Library for Twitter API v2
=========================================================
A library to ease the creation and management of social media listening campaigns using the Twitter API v2. 

The library is designed to be used interactively in a Python Jupyter Notebook. It provides methods to create and manage two kinds of real-time listening campaigns, namely "track" and "follow". The first method allows the user to listen to tweets including specified keywords, whereas the second enables the automated collection of tweets related to a list of specified Twitter accounts. .

These methods are equivalent to the "track" and "follow" endpoints offered by Twitter API v1.1, which are not natively available in Twitter API v2. Instead, the more recent version of the Twitter API requires the creation of rules made of operators connected using boolean logic. The library deals with the complexity associated with converting a list of keywords (or accounts) into one or more rules, which in turn are assigned to a bearer token with enough free rules, depending on the credential level.

Hereafter, we also use the term "crawler" to refer to a "track" or "follow" listening campaign

The class **TwitterMonitor** provides the following public methods:
* The **constructor** loads credentials from file "credentials.jsonl" and automatically determines each credential's level (i.e., essential, elevated, academic).
* **track**(str: name, list: keywords)  starts a "track" crawler on the specified keywords
* **follow**(str: name, list: accounts) stars a "follow" crawler on the specified accounts
* **pause**(str: name) the specified crawler is temporarily paused
* **resume**(str: name) the specified crawler is resumed
* **delete**(str: name) the crawler is removed from TwitterMonitor and will not be loaded again when a TwitterMonitor object is created
* **info**() prints basic info on active and paused crawlers to the standard output
* **info_crawler**(str: name) prints more detail on the specified crawler to the standard output.

In addition to the information printed on the standard output, the library produces a **log_TM.txt** log file that also includes regular updates (every ten minutes) on active crawlers and error messages.

Data are saved into the **data_TM/ folder**. More specifically, there is a dedicated subfolder for each crawler, named as the crawler itself. Each crawler's folder includes:
* One **YY-MM-DD.jsonl** file per day with the tweet objects collected on that day
* File **info.json** with the crawler's info (must not be edited manually); this configuration is used to reload the crawler automatically in case the application is restarted and a new TwitterMonitor object is created (loaded crawlers are set to the "paused" state by default).



Use example
------------------------------------------------

The library is designed for interactive use in a Python Jupyter Notebook. Here we provide an example. 

* Before being able to use the library, it is required to add valid credentials in file **credentials.jsonl**. Each line in the file should be in the format:
```
{"app_name": "paolo01","user": "PaoloMaldiniACM","bearer_token": "..."}
```

* Cell #1 -- The library is imported and a TwitterMonitor object is created:
```
from twittermonitor import TwitterMonitor

tm = TwitterMonitor()
```

Output example:
```
INFO     Loading credentials from file "credentials.jsonl"
WARNING  Skipped credential on line 2 -- missing field "app_name"
INFO     1 credential loaded from file "credentials.jsonl"
INFO     Creating TokenManager for credential "PaoloMaldini/paolo01"...
INFO     Done. Credential "PaoloMaldini/paolo01" has level: "elevated"
INFO     1 valid credential found
```

* Cell #2 -- A follow crawler named "IT_politicians" is started:
```
tm.follow('IT_politicians', ['matteosalvinimi','berlusconi', 'GiorgiaMeloni', 'CarloCalenda', '18762875'])
```

Output example:
```
INFO     OK: crawler "IT_politicians" activated to follow the specified targets
```

* Cell #3 -- A track crawler named "track1" is started:
```
tm.track('track1', ['Covid19', 'coronavirus', 'lockdown'])
```

Output example:
```
#INFO     OK: crawler "track1" activated to track the specified targets
```

* Cell #4 -- Show a summary of ongoing operations
```
tm.info()
```

Output example:
```
*** ACTIVE CRAWLERS ***
Name                       Type    Targets  Started (UTC)   Tot active  Tweets
IT_politicians             follow  5        22-10-21 17:37  3d 14h      77782
track1                     track   3        22-10-21 19:37  3d 12h      2343


*** CRDENTIALS ***
Type      Tokens    Rules used/total
elevated  1         2/25
```

* Cell #5 -- Pause crawler "track1"
```
tm.pause('track1')
```

Output example:
```
INFO     Crawler "track1" successfully paused
```

Known issues
------------------------------------------------

Sporadic errors ("connection error" or "operational disconnect") may occur and lead to losing a few seconds/minutes of tweets. This seems to be a Twitter-side issue: the library automatically attempts to reconnect and the stream is restored as soon as a new connection is accepted. In future versions of the library, we plan to introduce means to attempt to recover the tweets lost due to such issues.

The library ensures that the number of rules defined is limited according to the number and type of credentials. However, it will not check for the monthly tweet cap associated to the credentials. The user must take care of this limitation.


References
-------------------------------------------------
https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/migrate/standard-to-twitter-api-v2


License
-------------------------------------------------
Released under the terms of the MIT license (https://opensource.org/licenses/MIT).


