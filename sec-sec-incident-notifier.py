#!/usr/bin/env python3
# Created by Joshua Rogers <https://joshua.hu>, <https://github.com/megamansec/sec-sec-incident-notifier>
from datetime import datetime
import json
import re
import time
import sys
import os

from bs4 import BeautifulSoup
import feedparser
import requests

OPENAI_MAX_TOKENS = 300
OPENAI_KEY = ""
SLACK_WEBHOOK=""
USER_AGENT = "Joshua Rogers Joshua@Joshua.Hu" # Format should be "(Company) Name Contact@Email.tld"

REFRESH_INTERVAL_SECONDS = 300
SEC_RSS_FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&count=100&output=atom"
SLACK_BULLETPOINT = ' \u2022   '

def check_cybersecurity_disclosure(entry):
    """
    Check if the given RSS entry contains a cybersecurity incident disclosure (Item 1.05 on 8-K).
    """

    if 'Item 1.05' in entry.summary:
        return True
    return False

def get_true_url(link):
    """
    Construct the true URL for the 1.05 filing and retrieve the content.
    Extract the text between the first occurrence of '<html' and the last occurrence of '</html>'.
    """

    # https://www.sec.gov/Archives/edgar/data/789019/000119312524011295/0001193125-24-011295-index.htm can be read by https://www.sec.gov/Archives/edgar/data/789019/000119312524011295/0001193125-24-011295.txt
    true_url = link.replace("-index.htm", ".txt")

    headers = {'User-Agent': USER_AGENT}
    response = requests.get(true_url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Unable to fetch content for {true_url}. Status code: {response.status_code}", file=sys.stderr)
        return None, None

    content = response.text
    match = re.search(r'<html[^>]*>.*</html>', content, re.DOTALL | re.IGNORECASE)

    if match:
        extracted_html = match.group(0)

        if "XBRL TAXONOMY EXTENSION SCHEMA" in extracted_html:
            # Split the string based on the substring
            extracted_html = extracted_html.split("XBRL TAXONOMY EXTENSION SCHEMA")[0]

        pattern = re.compile(r'Item(?:&#160;|\s)1\.05(.*?)(?:(?:Item(?:&#160;|\s))|(?:<\/DIV><\/Center>))', re.DOTALL | re.IGNORECASE)
        match = pattern.search(extracted_html)
        if match:
            return extracted_html, f"<p>{match.group(1)}"

        return extracted_html, None

    print(f"Error: HTML content not found in {true_url}", file=sys.stderr)
    return None, None

def summarize_text(prompt, model="gpt-3.5-turbo-1106"):
    """
    Use OpenAI to summarize the document
    """

    if OPENAI_KEY is None or len(OPENAI_KEY) == 0:
        return None

    try:
        client = OpenAI(api_key=OPENAI_KEY)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=OPENAI_MAX_TOKENS
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Error: An unexpected error occurred: {e}", file=sys.stderr)
        return None

def truncate_slack_message(message):
    """
    Truncate the largest word if the message is too large
    """

    while len(message) > 2000:
        longest_word = max(message.split(), key=len)
        message = message.replace(longest_word, "[...truncated...]")
    return message

def alert(text, summary=""):
    """
    Send a slack message with new reports, or just print.
    """

    if SLACK_WEBHOOK is None or len(SLACK_WEBHOOK) == 0:
        print(f"{text}{summary}")
        return

    current_time = datetime.now()
    formatted_time = current_time.strftime("[%d/%m/%y %H:%M:%S]")

    text = truncate_slack_message(text)
    summary = truncate_slack_message(summary)

# Ugly attachments.
#    data = {
#        "attachments": [
#            {
#                "fallback": f"*{formatted_time}*: {text}\n{summary}",
#                "pretext": f"*{formatted_time}*: {text}\n",
#                "color": "#D00000",
#                "fields": [
#                    {
#                        "title": "Summary",
#                        "value": f"{summary}",
#                        "short": False
#                    }
#                ]
#            }
#        ]
#    }


    data = { "text": f"*{formatted_time}*: {text}_{summary}_" }

    headers = {'Content-type': 'application/json'}
    requests.post(SLACK_WEBHOOK, headers=headers, data=json.dumps(data))

def get_rss_feed(feed_url):
    """
    Retrieve the entries for an rss feed.
    """

    headers = {'User-Agent': USER_AGENT}
    response = requests.get(feed_url, headers=headers)

    if response.status_code != 200:
        print(f"Error: Unable to fetch RSS feed. Status code: {response.status_code}", file=sys.stderr)
        return None

    feed = feedparser.parse(response.content)

    if 'entries' not in feed:
        print("Error: Unable to parse RSS feed.", file=sys.stderr)
        return None

    return feed.entries

def parse_sec_rss_feed(entry):
    """
    Parse an entry from the SEC's RSS feed with a custom user-agent and print information about companies with cybersecurity incident disclosures.
    """

    link = entry.link

    company = entry.title
    company = company.replace("8-K - ", "")
    company = company.replace(" (Filer)", "")

    html_content, short_html_content  = get_true_url(link)
    if not html_content:
        alert(f"_{company}_ has filed an 8-K with a section 1.05, but we cannot parse the details: {link}")
        return

    soup = BeautifulSoup(html_content, 'html5lib')
    text_content = soup.get_text(separator=' ', strip=True) # Contains the full 8-K text

    if short_html_content:
        soup = BeautifulSoup(short_html_content, 'html5lib')
        short_text_content = soup.get_text(separator=' ', strip=True) # Contains only the item 1.05 text

    if not text_content:
        alert(f"_{company}_ has filed an 8-K with a section 1.05, but we cannot parse the details: {link}")
        return

    text_content = text_content.split("TAXONOMY", 1)[0] if "TAXONOMY" in text_content else text_content
    text_content = text_content.split("provided pursuant to Section 13(a) of the Exchange Act", 1)[-1] if "provided pursuant to Section 13(a) of the Exchange Act" in text_content else text_content
    summary = summarize_text(f"Summarize the following text, making sure you include the most critical information such as the systems compromised, who they belonged to, and their overall importance: {text_content}")

    if summary:
        alert(f"_{company}_: {link}.\n\n{SLACK_BULLETPOINT}(AI): ", summary)
    else:
        alert(f"_{company}_: {link}.\n\n{SLACK_BULLETPOINT}(Manual): ", short_text_content)

if __name__ == "__main__":

    for var in ["USER_AGENT", "OPENAI_KEY", "SLACK_WEBHOOK", "OPENAI_MAX_TOKENS"]:
        e_val = os.getenv(var)
        if e_val and len(e_val) > 0:
            vars()[var] = e_val

    if OPENAI_KEY is not None and len(OPENAI_KEY) > 0:
        from openai import OpenAI

    processed_links = set()

    entries = get_rss_feed(SEC_RSS_FEED)

    if not entries:
        print("Could not start!", file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        processed_links.add(entry.link)

    while True:
        time.sleep(REFRESH_INTERVAL_SECONDS)

        entries = get_rss_feed(SEC_RSS_FEED)

        if not entries:
            continue

        for entry in entries:
            link = entry.link

            if link in processed_links:
                continue

            processed_links.add(link)

            if not check_cybersecurity_disclosure(entry):
                continue

            parse_sec_rss_feed(entry)
