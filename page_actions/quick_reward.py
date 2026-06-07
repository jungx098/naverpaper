"""Npay Point Quick Reward page handlers."""

import logging
import time

from selenium.webdriver.remote.webdriver import WebDriver

from page_actions.common import Status, resolve_link, safe_click, wait_for_selector
from timings import MISSION_AFTER_CLICK, MISSION_HYDRATE

logger = logging.getLogger(__name__)

MISSION_DETAIL_MORE = 'button[data-nlog-click="mssdetail.more"]'
MISSION_GREEN_BTN = 'button[class*="ButtonBox-module_color-npayGreen"]'


@resolve_link
def process_point_quickreward_main(driver: WebDriver, link: str) -> Status:
    try:
        url = driver.current_url
    except Exception as e:
        logger.info("quickreward main: %s", type(e).__name__)
        return Status.FAIL

    if "point.pay.naver.com/main" not in url or "quickreward" not in url:
        return Status.FAIL

    logger.info("%s: quick reward list page", link)
    return Status.PASS


@resolve_link
def process_mission_detail(driver: WebDriver, link: str) -> Status:
    try:
        url = driver.current_url
    except Exception as e:
        logger.info("mission_detail: %s", type(e).__name__)
        return Status.FAIL

    if "mission-detail" not in url:
        return Status.FAIL

    time.sleep(MISSION_HYDRATE)

    more_buttons = wait_for_selector(driver, MISSION_DETAIL_MORE, wait=2)
    if more_buttons and safe_click(driver, more_buttons[0]):
        logger.info("mission_detail click: 더 알아보기")
        time.sleep(MISSION_AFTER_CLICK)
        return Status.UNDETERMINED

    for button in wait_for_selector(driver, MISSION_GREEN_BTN, wait=2)[:3]:
        try:
            label = button.text.strip() or "ButtonBox"
        except Exception:
            label = "ButtonBox"
        if safe_click(driver, button):
            logger.info("mission_detail click: %s", label)
            time.sleep(MISSION_AFTER_CLICK)
            return Status.UNDETERMINED

    logger.info("%s: mission detail loaded (no CTA click)", link)
    return Status.PASS


@resolve_link
def process_pay_home_reward(driver: WebDriver, link: str) -> Status:
    try:
        url = driver.current_url
    except Exception as e:
        logger.info("pay_home_reward: %s", type(e).__name__)
        return Status.FAIL

    if "pay.naver.com/home" not in url:
        return Status.FAIL

    driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
    time.sleep(MISSION_HYDRATE)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(MISSION_AFTER_CLICK)
    logger.info("%s: pay home scroll reward", link)
    return Status.PASS
