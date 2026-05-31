#!/usr/bin/env python3

import logging
import sqlite3
from pprint import pformat, pprint
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

from logging_config import init_logger

logger = logging.getLogger(__name__)


class Scrape:
    """Base scraper: discovers Naver campaign links from a community board.

    Subclasses only declare board-specific config:

    - ``base_url``: board listing page to fetch.
    - ``list_selector``: ``(tag, class)`` of the row elements holding post links.
    - ``link_source``: ``"href"`` reads the campaign link from the anchor's
      ``href``; ``"text"`` reads it from the anchor's visible text.
    - ``link_base``: base URL used to resolve relative post links; defaults to
      ``base_url`` when not set.
    """

    base_url = ""
    list_selector: tuple[str, str] = ("span", "list_subject")
    link_source = "href"
    link_base: str | None = None

    def __init__(self):
        self.headers = {"User-Agent": f"{UserAgent(platforms='pc').random}"}

    def is_campaign_link(self, link: str) -> bool:
        """Check if the link is a valid campaign link."""
        if (
            "campaign2-api.naver.com" in link
            or "campaign2.naver.com" in link
            or "ofw.adison.co" in link
        ):
            return True

        return False

    def _extract_campaign_link(self, a_tag):
        if self.link_source == "text":
            return a_tag.get_text().strip()
        return a_tag["href"]

    def _get_soup(self, url):
        response = requests.get(url, headers=self.headers, timeout=7)
        return BeautifulSoup(response.text, "html.parser")

    def find_naver_campaign_links(self, progress=None):
        soup = self._get_soup(self.base_url)

        tag, class_name = self.list_selector
        rows = soup.find_all(tag, class_=class_name)

        naver_links = []
        for row in rows:
            a_tag = row.find("a", href=True)
            if a_tag and "네이버" in a_tag.text:
                naver_links.append(a_tag["href"])

        link_base = self.link_base or self.base_url

        campaign_links = []
        for link in naver_links:
            inner_soup = self._get_soup(urljoin(link_base, link))

            for a_tag in inner_soup.find_all("a", href=True):
                campaign_link = self._extract_campaign_link(a_tag)

                if self.is_campaign_link(campaign_link):
                    campaign_links.append(campaign_link)

                    if progress:
                        progress()

        return list(set(campaign_links))


class ScrapeClien(Scrape):
    base_url = "https://www.clien.net/service/board/jirum"
    list_selector = ("span", "list_subject")


class ScrapePpompu(Scrape):
    base_url = "https://www.ppomppu.co.kr/zboard/zboard.php?id=coupon"
    list_selector = ("td", "baseList-space")
    link_source = "text"
    link_base = "https://www.ppomppu.co.kr/zboard/zboard.php?"


class ScrapeDamoang(Scrape):
    base_url = "https://damoang.net/economy"
    list_selector = ("li", "list-group-item")


class ScrapeRuliweb(Scrape):
    base_url = "https://bbs.ruliweb.com/market/board/1020"
    list_selector = ("td", "subject")


def normalize_link(link: str) -> str:
    """Normalize a scraped campaign link.

    Strips junk before the scheme, truncates at embedded CRLF, and unwraps a
    `redirect_uri` query parameter when present. Returns the cleaned link.
    """

    # Check link validness
    if not link.startswith("http"):
        logger.warning("Invalid Link: %s", link)
        pos = link.find("http")
        link = link[pos:]

    if "\r\n" in link:
        logger.warning("Invalid Link: %s", link)
        pos = link.find("\r\n")
        link = link[:pos]

    # Parse link and query params
    parsed_link = urlsplit(link)
    query_params = parse_qs(parsed_link.query)

    # Unwrap redirect_uri if present
    if "redirect_uri" in query_params:
        logger.warning("redirect_uri Found: %s", link)
        link = query_params.get("redirect_uri", [None])[0]

    return link


def scrape(progress=None) -> list[str]:
    scrapes = [ScrapeClien(), ScrapePpompu(), ScrapeDamoang(), ScrapeRuliweb()]

    campaign_links = []

    for entry in scrapes:
        try:
            links = entry.find_naver_campaign_links(progress)
        except Exception as e:
            logger.exception(
                "find_naver_campaign_links Failed for %s: %s",
                entry.base_url,
                type(e).__name__,
            )
            continue

        for i, link in enumerate(links):
            links[i] = normalize_link(link)

        campaign_links.extend(links)
        logger.info("Done for %s: %d", entry.base_url, len(links))

    campaign_links = list(set(campaign_links))
    logger.info("Campaign Link Count: %d", len(campaign_links))

    return campaign_links


class Database:
    def __init__(self, filename):
        # Connect to the database file (or create it if it does not exist).
        # A generous timeout plus WAL mode lets an overlapping run wait out an
        # active writer instead of failing immediately with "database is locked".
        self.conn = sqlite3.connect(filename, timeout=30)
        self.conn.row_factory = sqlite3.Row
        if filename != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")

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
            # Insert the record into the products table with the INSERT OR
            # IGNORE statement
            self.cur.execute("INSERT OR IGNORE INTO campaign (url) VALUES (?)", (link,))

        # Commit the changes to the database
        self.conn.commit()

    def get_campaigns(self, days=-7, newvisitonly=True):
        logger.info("Get Campaigns")

        # Assuming days is an integer representing the number of days
        sql = """SELECT url, visit
                FROM campaign
                WHERE creation >= datetime('now', ? || ' days')"""

        sqlnewvisitonly = "visit IS NULL"

        if newvisitonly:
            sql = sql + " AND " + sqlnewvisitonly

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
    pprint(campaigns)

    db = Database("campaign.db")
    db.update(campaigns)

    for c in campaigns:
        db.stamp_campaign(c)

    campaigns = db.get_campaigns(days=-7, newvisitonly=True)
    pprint(campaigns)
