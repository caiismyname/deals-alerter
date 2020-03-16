This is a small scraper project to read `deals.kinja.com`, The Wirecutter's deals Twitter page, and arbitrary subreddits (currently r/OutlierMarket) look for deals I've specified, and email me if found. 

It runs locally on my machine via a [chrontab job](https://www.techradar.com/how-to/computing/apple/terminal-101-creating-cron-jobs-1305651).

It's modularized so adding new deals sources should be simple, as well as changing the notification method.

To add new deals, add the keyword into the `keyword` field of the config file. (There is a blank config file in git. The populated one is local, not in VC). Each entry should be a list of keywords -- if all keywords are found, a post is considered a match.
