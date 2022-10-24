[![SBD++](https://img.shields.io/badge/Available%20on-SoBigData%2B%2B-green)](https://sobigdata.d4science.org/group/sobigdata-gateway/explore?siteId=20371853)

Twitter Monitor Library for Twitter API v2
=========================================================
A library to ease the creation and management of social media listening campaigns using the Twitter API v2. 

The library is designed to be used interactively in a Python Jupyter Notebook. It provides methods to create and manage two kinds of real-time listening campaigns, namely "track" and "follow". The first method allows the user to listen to tweets including specified keywords, whereas the second enables the automated collection of tweets related to a list of specified Twitter accounts. .

These methods are equivalent to the "track" and "follow" endpoints offered by Twitter API v1.1, which are not natively available in Twitter API v2. Instead, the more recent version of the Twitter API requires the creation of rules made of operators connected using boolean logic. The library deals with the complexity associated with converting a list of keywords (or accounts) into one or more rules, which in turn are assigned to a bearer token with enough free rules, depending on the credential level.

Hereafter, we also use the term "crawler" to refer to a "track" or "follow" listening campaign

The class TwitterMonitor provides the following methods:
* The constructor loads credentials from file "credentials.jsonl" and automatically determines each credential's level (i.e., essential, elevated, academic).
* track(str: name, list: keywords)  starts a "track" crawler on the specified keywords
* follow(str: name, list: accounts) stars a "follow" crawler on the specified accounts
* pause(str: name) the specified crawler is temporarily paused
* resume(str: name) the specified crawler is resumed
* delete(str: name) the crawler is removed from TwitterMonitor and will not be loaded again when a TwitterMonitor object is created
* info() prints basic info on active and paused crawlers to the standard output
* info_crawler(str: name) prints more detail on the specified crawler to the standard output.

Data are saved into the data_TM/ folder. More specifically, there is a dedicated subfolder for each crawler, named as the crawler itself. Each crawler's folder includes:
* One .jsonl file per day with the tweet objects collected on that day
* File info.json with the crawler's info (must not be edited manually); this configuration is used to reload the crawler automatically in case the application is restarted and a new TwitterMonitor object is created (loaded crawlers are set to the "paused" state by default).

For more information on the methods and the required parameters, please refer to source code documentation.


Use example
------------------------------------------------

File *use_example.py* provides examples on how the methods described above can be imported and used.


References
-------------------------------------------------
https://developer.twitter.com/en/docs/twitter-api/tweets/filtered-stream/migrate/standard-to-twitter-api-v2


License
-------------------------------------------------
Released under the terms of the MIT license (https://opensource.org/licenses/MIT).

