#!/usr/bin/env python3
"""Page-interaction primitives for Naver campaign/quick-reward flows.

Holds the per-page handlers that inspect the current page after a navigation
and report a :class:`Status`, plus shared helpers (``Status``,
``text_to_change``, ``dump_page``) and the ordered handler chains consumed by
the orchestration code in ``naper.py``.
"""

import hashlib
import logging
import os
import time
from enum import Enum

from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By

logger = logging.getLogger(__name__)

QUICK_REWARD_LINK = (
    "https://new-m.pay.naver.com/historybenefit/eventbenefit?category=quickreward"
)

DEBUG_DIR = "debug"


class text_to_change:
    """Class checking element text change."""

    def __init__(self, locator, text):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        actual_text = driver.find_element(*self.locator).text
        return actual_text != self.text


class Status(Enum):
    PASS = "1"
    FAIL = "2"
    UNDETERMINED = "3"


def dump_page(driver):
    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        url = driver.current_url
        page = driver.page_source
        filename = url.replace("https://", "")
        filename = filename.replace("/", "_")
        filename = filename.replace("?", "_")
        # Long query strings can push the name past the filesystem limit
        # (255 bytes); truncate and append a short hash to keep it unique.
        if len(filename) > 100:
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            filename = filename[:100] + "_" + digest
        path = os.path.join(DEBUG_DIR, filename)
        with open(path + ".html", "w", encoding="utf-8") as fd:
            fd.write(page)
        driver.get_screenshot_as_file(path + ".png")
    except Exception as e:
        logger.exception("%s: %s", driver.current_url, type(e).__name__)


def process_error(driver, link):
    if link is None:
        link = driver.current_url

    dump_page(driver)
    logger.error("Link: %s", link)
    logger.error("Current URL: %s", driver.current_url)
    logger.error("Title: %s", driver.title)


def process_alert(driver, link) -> Status:
    if link is None:
        link = driver.current_url

    try:
        result = driver.switch_to.alert
        logger.info("%s: %s", link, result.text)
        if "클릭적립은 캠페인당 1회만 적립됩니다." in result.text:
            return Status.PASS
        result.accept()

        return Status.UNDETERMINED

    except NoAlertPresentException:
        pass

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return Status.FAIL


def process_dim(driver, link) -> Status:
    if link is None:
        link = driver.current_url

    try:
        text = driver.find_element(By.CLASS_NAME, "dim").text
        text = text.replace("\n", " ")
        logger.info("%s: %s - %s (No Alert)", link, driver.title, text)

        if "클릭 적립은 캠페인당 1회만 적립 됩니다." in text:
            return Status.PASS

        return Status.UNDETERMINED

    except NoSuchElementException:
        pass

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return Status.FAIL


def process_quickreward_link(driver, link) -> Status:
    if link is None:
        link = driver.current_url

    try:
        if driver.current_url == QUICK_REWARD_LINK:
            text = "Quick Reward Ignored"
            logger.info("%s: %s - %s (No Alert)", link, driver.title, text)
            return Status.UNDETERMINED

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return Status.FAIL


def process_modal(driver):
    try:
        modal = driver.find_element(By.CLASS_NAME, "modal")
        logger.info("modal: %s", modal.text.replace("\n", " "))

        try:
            # <div class="buttons"><div class="submit-button btn-naver" onclick="CustomDialog.dismiss()">확인</div></div>
            # buttons = driver.find_element(By.CLASS_NAME, "submit-button btn-naver")
            buttons = driver.find_element(By.CLASS_NAME, "buttons")
            buttons.click()
        except NoSuchElementException:
            logger.info("No buttons Found")
    except NoSuchElementException:
        logger.info("No modal Found")


def process_popup_link(driver, link=None) -> Status:
    """
    Function processing popup link elements.

    Sample HTML:

    <a href="#" class="popup_link">
        <span class="text">포인트 받기</span>
    </a>
    """
    try:
        modal = driver.find_element(By.CLASS_NAME, "popup_link")
        logger.info("popup_link: %s", modal.text.replace("\n", " "))

        try:

            buttons = driver.find_element(By.CLASS_NAME, "popup_link")
            buttons.click()
            time.sleep(5)
        except Exception as e:
            logger.info("No buttons Found: %s", type(e).__name__)
            return Status.FAIL
    except Exception as e:
        logger.info("No popup_link Found: %s", type(e).__name__)
        return Status.FAIL

    return Status.PASS


def process_confirm(driver, link=None) -> Status:
    """
    Function processing popup link elements.

    Sample HTML:

    <div class="popup_box">
        <strong class="popup_tit">
            클릭 적립은 캠페인 당<br>
            1회만 적립됩니다.
        </strong>
        <div class="bg_area"></div>
        <a href="https://loan.pay.naver.com/n/credit?from=pointppopgi" class="popup_link">
            <span class="text">확인</span>
        </a>
    </div>
    """
    try:
        driver.find_element(By.LINK_TEXT, "확인").click()
        time.sleep(5)
    except Exception as e:
        logger.info("No Link Found: %s", type(e).__name__)
        return Status.FAIL

    return Status.PASS


def process_call_to_action(driver, link) -> Status:
    if link is None:
        link = driver.current_url

    try:
        # Wait for the page update.
        time.sleep(3)
        element = driver.find_element(By.CLASS_NAME, "call_to_action")
        logger.info("Click %s", element.text)
        element.click()

        # TODO: Process 알림받기
        time.sleep(1)
        process_modal(driver)

        time.sleep(3)
        logger.info("%s: %s (call_to_action)", link, driver.title)
        return Status.UNDETERMINED

    except NoSuchElementException:
        pass

    except Exception as e:
        logger.exception("%s", type(e).__name__)

    return Status.FAIL


# Ordered handler chains. Each handler returns a Status; the first non-FAIL
# result wins and the rest are skipped (see run_handlers).
VISIT_HANDLERS = (
    process_alert,
    process_dim,
    process_quickreward_link,
    process_call_to_action,
    process_popup_link,
    process_confirm,
)

QUICK_REWARD_HANDLERS = (
    process_alert,
    process_dim,
    process_call_to_action,
)


def run_handlers(driver, link, handlers) -> Status:
    """Run handlers in order, stopping at the first non-FAIL result."""

    status = Status.FAIL
    for handler in handlers:
        status = handler(driver, link)
        if status is not Status.FAIL:
            break
    return status
