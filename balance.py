#!/usr/bin/env python3
"""Naver Pay balance reading."""

import logging
import re
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from page_actions import TextToChange

logger = logging.getLogger(__name__)

# Balance sources, tried in order. The faster points-history page is preferred;
# the slower pay home is the fallback. Naver now redirects the old
# new-m.pay.naver.com URLs to these canonical domains, so request them directly.
# CSS module class hashes change per Naver build, so each xpath matches on the
# stable class-name prefix instead of the full hashed name.
BALANCE_SOURCES = (
    (
        "https://point.pay.naver.com/pointshistory/list?category=all",
        (
            "//*[contains(@class, '_area-point_')]",
            "//*[contains(@class, 'my-point_number__')]",
        ),
    ),
    (
        "https://home.pay.naver.com/",
        (
            "//*[contains(@class, 'my-point_number__')]",
            "//*[contains(@class, 'my-point_amount__')]",
        ),
    ),
)


def _find_balance_element(driver: WebDriver, xpaths: tuple[str, ...], timeout: int = 8):
    end_time = time.time() + timeout
    last_error: Exception | None = None

    while time.time() < end_time:
        for xpath in xpaths:
            try:
                return WebDriverWait(driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
            except TimeoutException as e:
                last_error = e
            except NoSuchElementException as e:
                last_error = e
        time.sleep(0.2)

    if last_error:
        raise last_error
    raise TimeoutException("Balance element not found")


def read_balance(driver: WebDriver, url: str, xpaths: tuple[str, ...]) -> int:
    """Read a Naver balance from a single page/element, or -1 on failure."""

    balance = -1

    try:
        for attempt in range(2):
            try:
                driver.get(url)
                break
            except TimeoutException as e:
                logger.warning(
                    "Balance source load timeout (%s, attempt %d/2)",
                    url,
                    attempt + 1,
                )
                if attempt == 1:
                    raise e

        element = _find_balance_element(driver, xpaths)

        old_text = element.text
        logger.info("read_balance: %s", old_text)

        def text_changed(d: WebDriver) -> bool:
            for xpath in xpaths:
                try:
                    if TextToChange((By.XPATH, xpath), old_text)(d):
                        return True
                except Exception:
                    continue
            return False

        try:
            WebDriverWait(driver, 5).until(text_changed)
            element = _find_balance_element(driver, xpaths, timeout=2)
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
