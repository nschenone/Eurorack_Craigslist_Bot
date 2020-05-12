#!/usr/bin/env python

# Links
# https://www.dataquest.io/blog/apartment-finding-slackbot
# https://github.com/juliomalegria/python-craigslist
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
from flask import Flask
app = Flask(__name__)

def get_posts(posts_ALL):
    # Get posts via python-craigslist
    results = []
    for location, posts in posts_ALL.items():
        for result in posts.get_results(sort_by='newest', include_details=True):
            loc = result["where"] if result["where"] != None else ""
            loc += f" - {location}"
            result["where"] = loc
            results.append(result)
    df = pd.DataFrame(results)

    # Clean data
    for i, row in df.iterrows():
        # Convert last_updated into relative time value in hours
        time_posted = pd.to_datetime(row["last_updated"], infer_datetime_format=True)  
        time_now = pd.to_datetime(datetime.now(), infer_datetime_format=True)
        time_diff = pd.Timedelta(time_now - time_posted).total_seconds() / 3600 / 24
        df.at[i,'updated'] = round(time_diff, 1)

        # Convert created into relative time value in hours
        time_posted = pd.to_datetime(row["created"], infer_datetime_format=True)  
        time_now = pd.to_datetime(datetime.now(), infer_datetime_format=True)
        time_diff = pd.Timedelta(time_now - time_posted).total_seconds() / 3600 / 24
        df.at[i,'created'] = round(time_diff, 1)

        # Convert price to float
        price = float(row["price"][1:])
        df.at[i,'price'] = price

    # Drop unnecessary columns
    df = df.drop(["datetime", "geotag", "has_image", "repost_of", "last_updated"], axis=1)

    # Re-order columns
    df = df[['id', 'name', 'price' , 'url', 'updated', 'created','where']]

    # Sort by price and last update
    df = df.sort_values(by=["updated", "price"]).reset_index(drop=True)
    
    return df

def compile_blacklist(SLACK_CHANNEL_ID, client):
    # Get blacklist urls from Slack via reactions
    response = client.conversations_history(channel=SLACK_CHANNEL_ID)
    seen_urls = []
    for message in response["messages"]:
        if message["subtype"] == 'bot_message':
            try:
                if message["reactions"]:
                    text = message["text"]
                    url = "https://" + text.split(".html")[-2].split("https://")[-1] + ".html"
                    seen_urls.append(url)
            except:
                pass
    # Write to file
    open('seen_urls.txt', 'w').close()
    with open("seen_urls.txt", "w+") as f:
        for url in seen_urls:
            f.write(url + '\n')
            
    # Compile list of urls not to send into list
    blacklist_urls = []
    with open("seen_urls.txt") as f:
        for url in f:
            blacklist_urls.append(url.split("\n")[0])
            
    return blacklist_urls

def send_messages(SLACK_CHANNEL, text_posts, client):
    for text in text_posts:
        try:
            response = client.chat_postMessage(
                channel=SLACK_CHANNEL,
                text=text,
                username = "Synth-Bot",
                icon_emoji=':robot_face:')
        except SlackApiError as e:
            # You will get a SlackApiError if "ok" is False
            assert e.response["ok"] is False
            assert e.response["error"]  # str like 'invalid_auth', 'channel_not_found'
            print(f"Got an error: {e.response['error']}")
            
def main():
    # Initialize bot
    SLACK_CHANNEL = "#synth-bot"
    SLACK_CHANNEL_ID = "C012FHZE1NW"

    client = WebClient(token=creds["token"])

    # Create search queries
    posts_SD = CraigslistForSale(site="sandiego", filters={'query': "eurorack"})
    posts_OC = CraigslistForSale(site="orangecounty", filters={'query': "eurorack"})
    posts_ALL = {"SD" : posts_SD, "OC" : posts_OC}

    # Get posts via python-craigslist
    df = get_posts(posts_ALL)

    # Get blacklist urls from Slack via reactions
    blacklist_urls = compile_blacklist(SLACK_CHANNEL_ID, client)

    # Compile into text for bot
    text_posts = []
    for i, row in df.iterrows():
        if row['url'] not in blacklist_urls:
            text_posts.append(f"{row['name']} | ${row['price']} | {row['where']}\nUpdated {row['updated']} days ago | Created {row['created']} days ago\n{row['url']}\n\n")

    # Check if there are any new messages
    if len(text_posts) == 0:
        text_posts.append("No new synths today!")
            
    # Send messages
    send_messages(SLACK_CHANNEL, text_posts, client)

@app.route('/synth_bot')
def run():
    main()
    return "Done"
