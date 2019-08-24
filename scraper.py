import feedparser
from datetime import datetime
from datetime import timedelta
from time import mktime

kinja_url = "https://kinjadeals.theinventory.com/rss"
target_keywords = ["itunes", "gummy", "burrow"]
last_lookup = datetime.now() - timedelta(hours=5) #last lookup was 5 hours ago 

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

# Helper functions

# Returns t/f for if given date is after lookup
def isValidDate(date):
	diff = date - last_lookup
	return diff.seconds > 0

def timestampToDatetime(stamp):
	return datetime.fromtimestamp(mktime(stamp))

# Returns list of keywords that are matches
def compareDeal(deal_text):
	matches = []
	for keyword in target_keywords:
		if keyword in deal_text:
			matches.append(keyword)

	return matches

def parseKinja():
	feed = feedparser.parse(kinja_url)
	new_items = list(filter(lambda x: isValidDate(timestampToDatetime(x["published_parsed"])), feed["items"]))
	print("Kinja has %s new posts" % len(new_items))

	relevant_deals = {}
	for item in new_items:
		for matched_word in compareDeal(item["title"] + item["description"]):
			relevant_deals[matched_word] = Deal(matched_word, item["title"], item["link"])

	if relevant_deals:
		print("Kinja has %d matches, for " % len(relevant_deals.keys()), list(relevant_deals.keys()))	
	else:
		print("Kinja has no matches")
	
	return relevant_deals


parseKinja()
