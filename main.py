#!/usr/bin/env python3

# https://www.clien.net/service/board/lecture/18488588

from naver import session as s
from naver import find as f
import time
import config

base_url = "https://www.clien.net/service/board/jirum"

try:
    s = s.session(config.id, config.pw)
except:
    print("Session Creation Failed. Unknown ID or wrong PW?")
    exit(-1)

campaign_links = f.find(base_url)

if(campaign_links == []):
    print("모든 링크를 방문했습니다.")
for link in campaign_links:
    response = s.get(link)
    #print(response.text) # for debugging
    #response.raise_for_status() # for debugging
    time.sleep(5)
    print("캠페인 URL : " + link)
