#!/usr/bin/env python3

# https://www.clien.net/service/board/lecture/18488588

from naverpaper import naverpaper
import time
import config

base_url = "https://www.clien.net/service/board/jirum"

try:
    s = naverpaper.naver_session(config.id, config.pw)
except:
    print("Session Creation Failed. Unknown ID or wrong PW?")
    exit(-1)

campaign_links = naverpaper.find_naver_campaign_links(base_url)

if(campaign_links == []):
    print("모든 링크를 방문했습니다.")
for link in campaign_links:
    response = s.get(link)
    #print(response.text) # for debugging
    #response.raise_for_status() # for debugging
    time.sleep(5)
    print("캠페인 URL : " + link)
