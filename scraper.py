import feedparser
from datetime import timezone
from datetime import datetime
from datetime import timedelta
from time import mktime
import json 
import twitter # for reading deals off wirecutter's twitter, since they don't have an RSS
import os # for getting env. vars for twitter 
from dotenv import load_dotenv, find_dotenv # for env. vars for twitter
import smtplib # for sending emails
from collections import defaultdict

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

def log(message):
	date_format = "%d-%m-%Y %H:%M:%S"
	timestamp = "[" + datetime.now().strftime(date_format) + "] "
	with open("deals_alerter_log.log", "a+") as f:
		message = timestamp + message + "\n"
		f.write(message)
		f.close()	
		if config["verbose"]:
			print(message)		


# Returns t/f for if given date is after last refresh
def isValidDate(date):
	# 'interval' is how many hours are between each refresh
	last_refresh = datetime.now(timezone.utc) - timedelta(hours=config["schedule"]["interval"]) 
	return last_refresh < date

def utcTimestampToDatetime(stamp):
	# Second half is to offset for DST since DST info is lost in mktime conversion
	# timetuple().tm_isdst returns 0 if not DST, 1 if it is DST for the given timezone associated with datetime.now()
	return datetime.fromtimestamp(mktime(stamp)).replace(tzinfo=timezone.utc) + timedelta(hours = datetime.now().timetuple().tm_isdst)

# Specific to twitter's date format: Sun Aug 25 15:23:24 +0000 2019
# Removes timezone info for compatibility with datetime.now()
def twitterStringToDatetime(given):
	# Twitter time is in UTC already
	return datetime.strptime(given, "%a %b %d %H:%M:%S %z %Y")

def removePunctuation(text):
	# Removing : and ; b/c of canoncial post formatting in r/OutlierMarket
	punctuation = [".", ",", "!", "?", "-", "_", "@", "#", "$", "%", "&", ":", ";"] 
	for mark in punctuation:
		text = text.replace(mark, "")	
	return text

# Returns list of keywords that are matches
def compareDeal(deal_text):
	# split given text into list of words so substrings don't trigger matches (e.g. keyword: oven --> text: woven)
	split_text = list(map(lambda word: word.lower(), map(removePunctuation, deal_text.split(" ")))) # cast to list so you can do "foo in bar" lookups
	matches = []
	for keyword_group in config["target_keywords"]:
		if type(keyword_group) is not list:
			raise TypeError("target_keywords should be lists of keywords")

		all_match = True
		for keyword in keyword_group:
			if keyword not in split_text:
				all_match = False
		
		if all_match:
			matches.append("-".join(keyword_group))
	return matches

# Modularizing repeated logging code
def logFoundDeals(found_deals, provider):
	if found_deals:
		log("%s has %d matches, for %s" % (provider, len(found_deals.keys()), list(found_deals.keys())))	
	else:
		log("%s has no matches" % provider)
	
def mergeDictionaries(dicts):
	merged = defaultdict(list)
	for d in dicts:
		for k, v in d.items():
			merged[k] += v
	return merged

def removeNonASCII(given):
	return "".join(filter(lambda char: ord(char) >= 0 and ord(char) <= 127, given))

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
# Return format: dictionary of {keyword: [Deal_objects]}
def parseKinja():
	feed = feedparser.parse(config["urls"]["kinja"])
	new_items = list(filter(lambda x: isValidDate(utcTimestampToDatetime(x["published_parsed"])), feed["items"]))
	log("Kinja has %d new posts" % len(new_items))

	relevant_deals = defaultdict(list)
	for item in new_items:
		for matched_word in compareDeal(item["title"] + item["description"]):
			relevant_deals[matched_word].append(Deal(matched_word, item["title"], item["link"]))

	logFoundDeals(relevant_deals, "Kinja")
	return relevant_deals

# Scrape a subreddit's RSS feed for new posts
# Return format: dictionary of {keyword: [Deal_objects]}
def parseSubreddit(url, sub_name):
	feed = feedparser.parse(url)
	
	new_items = list(filter(lambda x: isValidDate(utcTimestampToDatetime(x["updated_parsed"])), feed["entries"]))
	log("r/" + sub_name + " has %d new posts" % len(new_items))

	relevant_deals = defaultdict(list)
	for item in new_items:
		for matched_word in compareDeal(item["title"]):
			relevant_deals[matched_word].append(Deal(matched_word, item["title"], item["link"]))

	logFoundDeals(relevant_deals, "r/" + sub_name)
	return relevant_deals


# Wirecutter doesn't have an RSS for deals, so we're gonna scrape their Twitter instead
# Return format: dictionary of {keyword: [Deal_objects]}
def parseWirecutter():
	twitter_api = twitter.Api(consumer_key=os.environ.get("twitter_consumer_key"),
		consumer_secret=os.environ.get("twitter_consumer_secret"),
		access_token_key=os.environ.get("twitter_access_token_key"),
		access_token_secret=os.environ.get("twitter_access_token_secret"))	
	
	feed = twitter_api.GetUserTimeline(screen_name=config["twitter_handles"]["wirecutter"])
	posts = [item.AsDict() for item in feed]
	new_items = list(filter(lambda x: isValidDate(twitterStringToDatetime(x["created_at"])), posts))
	log("Wirecutter has %d new posts" % len(new_items))
	
	relevant_deals = defaultdict(list)
	for item in new_items:
		for matched_word in compareDeal(item["text"]):
			# The twitter lib. returns urls as a list of dicts, hence the [0]["url"]
			relevant_deals[matched_word].append(Deal(matched_word, item["text"], item["urls"][0]["url"]))

	logFoundDeals(relevant_deals, "Wirecutter")
	return relevant_deals

# input deals: dict of {keyword: [deals]}
def createEmail(deals):
	sent_from = config["email"]["sender"] 
	to = ", ".join(config["email"]["recipients"])
	# content type header so email is HTML so I can embed links
	content_type = "text/html"
	subject = "Deals Alerter Found %d Deals For You!" % (len(deals))
	body = ""
	body_template = "\t- <a href=\"%s\">%s</a>\n"

	for keyword, deal_list in deals.items():
		body += "Deals found for [%s]:<br>" % keyword
		for deal in deal_list:
			body += body_template % (deal.getLink(), deal.getTitle())
		body += "<br><br>"
	body = "<p>" + body + "</p>"
	# smtplib requires the whole email encoded into one string
	message = """From: %s\r\nTo: %s\r\nContent-Type: %s\r\nSubject: %s\r\n\r\n%s""" % (sent_from, to, content_type, subject, body)
	message = removeNonASCII(message)
	return message

def notify(deals):
	if deals:
		try:
			email_server = smtplib.SMTP("smtp.gmail.com:587")
			email_server.ehlo()
			email_server.starttls()	
			email_server.login(config["email"]["sender"], os.environ.get("gmail_app_password"))
			message = createEmail(deals)
			email_status = email_server.sendmail(config["email"]["sender"], config["email"]["recipients"], message)	

			if email_status:
				log("Email Status: %s" % email_status)
			else:
				log("Email with %d deals sent succesfully to %s" % (len(deals.keys()), config["email"]["recipients"]))
			email_server.quit()
		except Exception as e:
			log("Email server error: %s" % e)		
	else:
		log("No matches, so not sending email")

def main():
	initEnvironment()
	
	kinja_results = parseKinja()
	# wirecutter_results = parseWirecutter()
	outliermarket_results = parseSubreddit(config["urls"]["outliermarket"], "OutlierMarket")
	all_deals = mergeDictionaries([kinja_results, wirecutter_results, outliermarket_results]) 
	notify(all_deals)	

main()