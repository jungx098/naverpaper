"""Stamp-campaign page handlers (Adison / campaign2.naver.com)."""

import logging
import time

from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoAlertPresentException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from page_actions.common import (
    QUICK_REWARD_LINK,
    Status,
    resolve_link,
    safe_click,
    wait_for_selector,
)
from timings import (
    CALL_TO_ACTION_WAIT,
    CONFIRM_SETTLE,
    ELEMENT_WAIT,
    MODAL_SETTLE,
    POLL_INTERVAL,
    POPUP_SETTLE,
)

logger = logging.getLogger(__name__)


@resolve_link
def process_alert(driver: WebDriver, link: str) -> Status:
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


@resolve_link
def process_dim(driver: WebDriver, link: str) -> Status:
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


@resolve_link
def process_quickreward_link(driver: WebDriver, link: str) -> Status:
    try:
        if driver.current_url == QUICK_REWARD_LINK:
            text = "Quick Reward Ignored"
            logger.info("%s: %s - %s (No Alert)", link, driver.title, text)
            return Status.UNDETERMINED

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return Status.FAIL


def process_modal(driver: WebDriver) -> None:
    try:
        modal = driver.find_element(By.CLASS_NAME, "modal")
        logger.info("modal: %s", modal.text.replace("\n", " "))

        try:
            buttons = driver.find_element(By.CLASS_NAME, "buttons")
            if not safe_click(driver, buttons):
                logger.info("modal buttons click failed")
        except NoSuchElementException:
            logger.info("No buttons Found")
    except NoSuchElementException:
        logger.info("No modal Found")


def process_popup_link(driver: WebDriver, link: str | None = None) -> Status:
    try:
        modal = driver.find_element(By.CLASS_NAME, "popup_link")
        logger.info("popup_link: %s", modal.text.replace("\n", " "))

        try:
            buttons = driver.find_element(By.CLASS_NAME, "popup_link")
            if not safe_click(driver, buttons):
                logger.info("popup_link click failed")
                return Status.FAIL
            time.sleep(POPUP_SETTLE)
        except Exception as e:
            logger.info("No buttons Found: %s", type(e).__name__)
            return Status.FAIL
    except Exception as e:
        logger.info("No popup_link Found: %s", type(e).__name__)
        return Status.FAIL

    return Status.PASS


def _click_link_text(driver: WebDriver, text: str, wait: float = ELEMENT_WAIT) -> bool:
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            elements = driver.find_elements(By.LINK_TEXT, text)
            if elements:
                if safe_click(driver, elements[0]):
                    time.sleep(CONFIRM_SETTLE)
                    return True
        except InvalidSessionIdException:
            raise
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False


def process_confirm(driver: WebDriver, link: str | None = None) -> Status:
    try:
        if not _click_link_text(driver, "확인"):
            logger.info("No Link Found: Timeout")
            return Status.FAIL
    except InvalidSessionIdException as e:
        logger.info("No Link Found: %s", type(e).__name__)
        raise
    except Exception as e:
        logger.info("No Link Found: %s", type(e).__name__)
        return Status.FAIL

    return Status.PASS


@resolve_link
def process_call_to_action(driver: WebDriver, link: str) -> Status:
    try:
        time.sleep(CALL_TO_ACTION_WAIT)
        element = driver.find_element(By.CLASS_NAME, "call_to_action")
        logger.info("Click %s", element.text)
        if not safe_click(driver, element):
            return Status.FAIL

        time.sleep(MODAL_SETTLE)
        process_modal(driver)

        time.sleep(CALL_TO_ACTION_WAIT)
        logger.info("%s: %s (call_to_action)", link, driver.title)
        return Status.UNDETERMINED

    except NoSuchElementException:
        pass

    except Exception as e:
        logger.exception("%s", type(e).__name__)

    return Status.FAIL


VISIT_HANDLERS = (
    process_alert,
    process_dim,
    process_quickreward_link,
    process_call_to_action,
    process_popup_link,
    process_confirm,
)
