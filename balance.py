#!/usr/bin/env python3
"""Naver Pay balance reading."""

import logging
import re

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from page_actions import TextToChange

logger = logging.getLogger(__name__)

# Balance sources, tried in order. The faster points-history page is preferred;
# the slower mydata home is the fallback. CSS module class hashes (e.g.
# PointsManage_point__T67hP) change per Naver build, so each xpath matches on the
# stable class prefix instead of the full name.
BALANCE_SOURCES = (
    (
        "https://new-m.pay.naver.com/pointshistory/list?category=all",
        "//*[contains(@class, 'PointsManage_point__')]",
    ),
    (
        "https://new-m.pay.naver.com/mydata/home",
        "//*[contains(@class, 'AssetCommonItem_balance__')]",
    ),
)


def read_balance(driver: WebDriver, url: str, xpath: str) -> int:
    """Read a Naver balance from a single page/element, or -1 on failure."""

    balance = -1

    try:
        driver.get(url)
        element = driver.find_element(By.XPATH, xpath)

        old_text = element.text
        logger.info("read_balance: %s", old_text)

        try:
            WebDriverWait(driver, 5).until(TextToChange((By.XPATH, xpath), old_text))
            element = driver.find_element(By.XPATH, xpath)
        except TimeoutException as e:
            logger.info("No Change in Balance Element: %s", type(e).__name__)

        logger.info("read_balance: %s", element.text)

        balance = int(re.sub(r"[^0-9]", "", element.text))
    except Exception as e:
        try:
            current_url = driver.current_url
        except Exception:
            current_url = "<unknown>"
        logger.exception(
            "Balance Not Available: %s (%s)", type(e).__name__, current_url
        )

    return balance


def get_balance(driver: WebDriver) -> int:
    """Return the first balance readable from BALANCE_SOURCES, else -1."""

    balance = -1
    for url, xpath in BALANCE_SOURCES:
        balance = read_balance(driver, url, xpath)
        if balance != -1:
            break

    return balance
