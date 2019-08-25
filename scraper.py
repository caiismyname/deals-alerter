import feedparser
from datetime import datetime
from datetime import timedelta
from time import mktime
import json 
import twitter # for reading deals off wirecutter's twitter, since they don't have an RSS
import os # for getting env. vas for twitter 
from dotenv import load_dotenv, find_dotenv # for env. vars for twitter

last_refresh = datetime.now() - timedelta(hours=5) #last lookup was 5 hours ago 
config = {}

class Deal:
	def __init__(self, keyword, title, link):
		self.keyword = keyword
		self.title = title
		self.link = link

	def getLink(self):
		return self.link

	def getTitle(self):
		return self.title

	def getKeyword(self):
		return self.keyword

#
#
# Helper functions
#
#

# Returns t/f for if given date is after last refresh
def isValidDate(date):
	return last_refresh < date

def timestampToDatetime(stamp):
	return datetime.fromtimestamp(mktime(stamp))

# Specific to twitter's date format: Sun Aug 25 15:23:24 +0000 2019
# Removes timezone info for compatibility with datetime.now()
def twitterStringToDatetime(given):
	return datetime.strptime(given, "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None)

# Returns list of keywords that are matches
def compareDeal(deal_text):
	matches = []
	for keyword in config["target_keywords"]:
		if keyword in deal_text.lower():
			matches.append(keyword)

	return matches

# Modularizing repeated logging code
def logFoundDeals(found_deals, provider):
	if found_deals:
		print("%s has %d matches, for " % (provider, len(found_deals.keys())), list(found_deals.keys()))	
	else:
		print("%s has no matches" % provider)
	
#
#
# Core logic
#
#

def initEnvironment():
	global config
	
	# Load env for enviornment variables for Twitter API
	load_dotenv(find_dotenv())
	
	# Load config JSON for urls, keywords
	config_json_path = "./config.json"
	with open(config_json_path) as f:
		config = json.load(f)
		
# Scrape Kinja's RSS feed for their new deals
def parseKinja():
	feed = feedparser.parse(config["urls"]["kinja"])
	new_items = list(filter(lambda x: isValidDate(timestampToDatetime(x["published_parsed"])), feed["items"]))
	print("Kinja has %d new posts" % len(new_items))

	relevant_deals = {}
	for item in new_items:
		for matched_word in compareDeal(item["title"] + item["description"]):
			relevant_deals[matched_word] = Deal(matched_word, item["title"], item["link"])

	logFoundDeals(relevant_deals, "Kinja")
	return relevant_deals

# Wirecutter doesn't have an RSS for deals, so we're gonna scrape their Twitter instead
def parseWirecutter():
	twitter_api = twitter.Api(consumer_key=os.environ.get("twitter_consumer_key"),
		consumer_secret=os.environ.get("twitter_consumer_secret"),
		access_token_key=os.environ.get("twitter_access_token_key"),
		access_token_secret=os.environ.get("twitter_access_token_secret"))	
	
	feed = twitter_api.GetUserTimeline(screen_name=config["twitter_handles"]["wirecutter"])
	posts = [item.AsDict() for item in feed]
	new_items = list(filter(lambda x: isValidDate(twitterStringToDatetime(x["created_at"])), posts))
	print("Wirecutter has %d new posts" % len(new_items))
	
	relevant_deals = {}
	for item in new_items:
		for matched_word in compareDeal(item["text"]):
			relevant_deals[matched_word] = Deal(matched_word, item["text"], item["urls"][0])

	logFoundDeals(relevant_deals, "Wirecutter")
	return relevant_deals
	

initEnvironment()
parseWirecutter()
parseKinja()
