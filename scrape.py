#!/usr/bin/env python3

import logging
import sqlite3
from pprint import pformat
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from logging_config import init_logger

logger = logging.getLogger(__name__)


class Scrape:
    def __init__(self):
        pass

    def find_naver_campaign_links(self, progress=None):
        return []


class ScrapeClien(Scrape):
    def __init__(self):
        self.base_url = "https://www.clien.net/service/board/jirum"

    def find_naver_campaign_links(self, progress=None):
        # Send a request to the base URL
        response = requests.get(self.base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all span elements with class 'list_subject' and get 'a' tags
        list_subject_links = soup.find_all("span", class_="list_subject")

        naver_links = []
        for span in list_subject_links:
            a_tag = span.find("a", href=True)
            if a_tag and "네이버" in a_tag.text:
                naver_links.append(a_tag["href"])

        # Initialize a list to store campaign links
        campaign_links = []

        # Check each Naver link
        for link in naver_links:
            full_link = urljoin(self.base_url, link)

            res = requests.get(full_link)
            inner_soup = BeautifulSoup(res.text, "html.parser")

            # Find all links that start with the campaign URL
            for a_tag in inner_soup.find_all("a", href=True):
                campaign_link = a_tag["href"]

                if (
                    "campaign2-api.naver.com" in campaign_link
                    or "ofw.adison.co" in campaign_link
                ):
                    campaign_links.append(campaign_link)

                    if progress:
                        progress()

        return list(set(campaign_links))


class ScrapePpompu(Scrape):
    def __init__(self):
        self.base_url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=coupon"

    def find_naver_campaign_links(self, progress=None):
        page_url = "https://www.ppomppu.co.kr/zboard/zboard.php?"

        response = requests.get(self.base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        list_subject_links = soup.find_all("td", class_="baseList-space")

        naver_links = []
        for span in list_subject_links:
            a_tag = span.find("a", href=True)

            if a_tag and "네이버" in a_tag.text:
                naver_links.append(a_tag["href"])

        # Initialize a list to store campaign links
        campaign_links = []

        # Check each naver_links
        for link in naver_links:
            full_link = urljoin(page_url, link)

            res = requests.get(full_link)
            inner_soup = BeautifulSoup(res.text, "html.parser")

            campaign_a_tags = inner_soup.find_all("a", href=True)

            for a_tag in campaign_a_tags:
                campaign_link = a_tag.get_text().strip()

                if (
                    "campaign2-api.naver.com" in campaign_link
                    or "ofw.adison.co" in campaign_link
                ):
                    campaign_links.append(campaign_link)

                    if progress:
                        progress()

        return list(set(campaign_links))


class ScrapeDamoang(Scrape):
    def __init__(self):
        self.base_url = "https://www.damoang.net/economy"

    def find_naver_campaign_links(self, progress=None):
        # Send a request to the base URL
        request_headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(self.base_url, headers=request_headers)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all span elements with class 'list_subject' and get 'a' tags
        list_subject_links = soup.find_all("li", class_="list-group-item")

        naver_links = []
        for span in list_subject_links:
            a_tag = span.find("a", href=True)
            if a_tag and "네이버" in a_tag.text:
                naver_links.append(a_tag["href"])

        # Initialize a list to store campaign links
        campaign_links = []

        # Check each Naver link
        for link in naver_links:
            full_link = urljoin(self.base_url, link)

            res = requests.get(full_link, headers=request_headers)
            inner_soup = BeautifulSoup(res.text, "html.parser")

            # Find all links that start with the campaign URL
            for a_tag in inner_soup.find_all("a", href=True):
                campaign_link = a_tag["href"]

                if (
                    "campaign2-api.naver.com" in campaign_link or
                    "ofw.adison.co" in campaign_link
                ):
                    campaign_links.append(campaign_link)

                    if progress:
                        progress()

        return list(set(campaign_links))


class ScrapeRuliweb(Scrape):
    def __init__(self):
        self.base_url = "https://bbs.ruliweb.com/market/board/1020"

    def find_naver_campaign_links(self, progress=None):
        # Send a request to the base URL
        response = requests.get(self.base_url)
        soup = BeautifulSoup(response.text, "html.parser")

        # Find all span elements with class 'list_subject' and get 'a' tags
        list_subject_links = soup.find_all("td", class_="subject")

        naver_links = []
        for span in list_subject_links:
            a_tag = span.find("a", href=True)
            if a_tag and "네이버" in a_tag.text:
                naver_links.append(a_tag["href"])

        # Initialize a list to store campaign links
        campaign_links = []

        # Check each Naver link
        for link in naver_links:
            full_link = link

            res = requests.get(full_link)
            inner_soup = BeautifulSoup(res.text, "html.parser")

            # Find all links that start with the campaign URL
            for a_tag in inner_soup.find_all("a", href=True):
                campaign_link = a_tag["href"]

                if (
                    "campaign2-api.naver.com" in campaign_link or
                    "ofw.adison.co" in campaign_link
                ):
                    campaign_links.append(campaign_link)

                    if progress:
                        progress()

        return list(set(campaign_links))


def scrape(progress=None):
    scrapes = [ScrapeClien(), ScrapePpompu(), ScrapeDamoang(), ScrapeRuliweb()]

    campaign_links = []

    for entry in scrapes:
        links = entry.find_naver_campaign_links(progress)
        campaign_links += links
        logger.info("Done for %s: %d", entry.base_url, len(links))

    campaign_links = list(set(campaign_links))
    logger.info("Campaign Link Count: %d", len(campaign_links))

    return campaign_links


class Database:
    def __init__(self, filename):
        # Connect to the database file (or create it if it does not exist)
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row

        # Create a cursor object to execute SQL commands
        self.cur = self.conn.cursor()

        # Create the campaign table with the CREATE TABLE statement
        self.cur.execute(
            """
        CREATE TABLE IF NOT EXISTS campaign (
                    id INTEGER PRIMARY KEY,
                    creation DATE DEFAULT (datetime('now')),
                    url TEXT UNIQUE NOT NULL,
                    visit DATE,
                    status TEXT
        );
        """
        )

    def __del__(self):
        logger.info("Bye Database")
        self.conn.commit()
        self.conn.close()

    def update(self, campaign_links):
        """Update campaign db."""

        for link in campaign_links:
            # Insert the record into the products table with the INSERT OR IGNORE statement
            self.cur.execute("INSERT OR IGNORE INTO campaign (url) VALUES (?)", (link,))

        # Commit the changes to the database
        self.conn.commit()

    def get_campaigns(self, days=-7):
        logger.info("Get Campaigns")

        # Assuming days is an integer representing the number of days
        sql = """SELECT url, visit
                FROM campaign
                WHERE creation >= datetime('now', ? || ' days') AND visit IS NULL"""

        # Execute the query with parameter binding
        self.cur.execute(sql, (days,))
        rows = self.cur.fetchall()

        campaigns = []
        for r in rows:
            campaigns.append(r["url"])

        logger.info(pformat(campaigns))
        return campaigns

    def stamp_campaign(self, url):
        logger.info("Stamp Campaign: %s", url)

        sql = """UPDATE campaign SET visit = datetime('now') WHERE url = ?"""

        # Execute the update query with the provided URL
        self.cur.execute(sql, (url,))


if __name__ == "__main__":
    init_logger(
        console_logging_level=logging.DEBUG,
        file_logging_level=logging.DEBUG,
        filename=None,
    )

    campaigns = scrape()

    db = Database("campaign.db")
    db.update(campaigns)
    campaigns = db.get_campaigns()

    for c in campaigns:
        db.stamp_campaign(c)
