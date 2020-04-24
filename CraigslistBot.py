#!/usr/bin/env python
# coding: utf-8

# ### Links

# https://deadmanssnitch.com/ <br>
# https://www.dataquest.io/blog/apartment-finding-slackbot/ <br>
# https://github.com/juliomalegria/python-craigslist <br>
# https://github.com/slackapi/python-slackclient

import os
from slack import WebClient
from slack.errors import SlackApiError
from craigslist import CraigslistForSale
import pandas as pd
from datetime import datetime
from slack import WebClient
import asyncio
import nest_asyncio
from slack_creds import creds


# ### Get Craigslist posts

# Search queries
posts_SD = CraigslistForSale(site="sandiego", filters={'query': "eurorack"})
posts_OC = CraigslistForSale(site="orangecounty", filters={'query': "eurorack"})
posts_ALL = {"SD" : posts_SD, "OC" : posts_OC}

# Get posts via python-craigslist
results = []
for location, posts in posts_ALL.items():
    for result in posts.get_results(sort_by='newest'):
        result["where"] += f" - {location}"
        results.append(result)
df = pd.DataFrame(results)

# Clean data
for i, row in df.iterrows():
    # Convert last_updated into relative time value in hours
    time_posted = pd.to_datetime(row["last_updated"], infer_datetime_format=True)  
    time_now = pd.to_datetime(datetime.now(), infer_datetime_format=True)
    time_diff = pd.Timedelta(time_now - time_posted).seconds / 3600
    df.at[i,'hrs_ago'] = round(time_diff, 1)
    
    # Convert price to float
    price = float(row["price"][1:])
    df.at[i,'price'] = price
    
# Drop unnecessary columns
df = df.drop(["datetime", "geotag", "has_image", "repost_of", "last_updated"], axis=1)

# Re-order columns
df = df[['id', 'name', 'price' , 'url', 'hrs_ago', 'where']]

# Sort by price and last update
df = df.sort_values(by=["price", "hrs_ago"]).reset_index(drop=True)

# Compile into text for bot
text = ""
for i, row in df.iterrows():
    text += f"{row['name']} | {row['price']} | {row['hrs_ago']} hrs ago | {row['where']}\n{row['url']}\n\n"


# ### Post to slack

nest_asyncio.apply()

SLACK_CHANNEL = "#synth-bot"

client = WebClient(token=creds["token"])

try:
    response = client.chat_postMessage(
        channel=SLACK_CHANNEL,
        text=text,
        username = "Synth-Bot")
except SlackApiError as e:
    # You will get a SlackApiError if "ok" is False
    assert e.response["ok"] is False
    assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
    print(f"Got an error: {e.response['error']}")

