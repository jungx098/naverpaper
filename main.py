#!/usr/bin/env python3

# https://www.clien.net/service/board/lecture/18488588

from naver import session as s
from naver import find as f
import time
import config
import sqlite3

search_urls = ['https://www.clien.net/service/search?q=%EB%84%A4%EC%9D%B4%EB%B2%84',
               'https://www.clien.net/service/search?q=%EB%84%A4%EC%9D%B4%EB%B2%84&sort=recency&boardCd=jirum&isBoard=true']

try:
    s = s.session(config.id, config.pw)
except:
    print("Session Creation Failed. Unknown ID or wrong PW?")
    exit(-1)

# Connect to the database file (or create it if it does not exist)
conn = sqlite3.connect("campaign.db")

# Create a cursor object to execute SQL commands
cur = conn.cursor()

# Create the campaign table with the CREATE TABLE statement
cur.execute("""
CREATE TABLE IF NOT EXISTS campaign (
  id INTEGER PRIMARY KEY,
  date TEXT DEFAULT (datetime('now', 'localtime')),
  url TEXT UNIQ NOT NULL
);
""")

campaign_links = []

for url in search_urls:
    campaign_links.extend(f.find(url))

if(campaign_links == []):
    print("모든 링크를 방문했습니다.")
for link in campaign_links:

    # Execute a SELECT query to find a record with the name 'Laptop'
    cur.execute("SELECT * FROM campaign WHERE url = ?", (link,))

    # Fetch one result from the query
    result = cur.fetchone()

    # Check if the result is None or not
    if result is not None:
        continue

    response = s.get(link)
    #print(response.text) # for debugging
    #response.raise_for_status() # for debugging
    time.sleep(5)
    print("캠페인 URL : " + link)

    # Insert the record into the products table with the INSERT OR IGNORE statement
    cur.execute("INSERT OR IGNORE INTO campaign (url) VALUES (?)", (link,))

# Commit the changes to the database
conn.commit()

# Close the connection
conn.close()
