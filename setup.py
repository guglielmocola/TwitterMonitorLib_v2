from setuptools import setup

setup(
    name='twittermonitor',
    description='Library to ease the use of the Twitter API v2 on Jupyter Notebooks',
    version='0.1.0',
    packages=[
        "twittermonitor",
    ],
    install_requires=[
        'tweepy>=4.10.1',
        'pytimeparse>=1.1.8',
    ],
    author='Guglielmo Cola',
    author_email='guglielmo.cola@iit.cnr.it',
    license='MIT',
    url='https://github.com/guglielmocola/TwitterMonitorLib_v2'
)