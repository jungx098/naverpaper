"""Shared page-action primitives and handler orchestration."""

import functools
import hashlib
import logging
import os
import time
from collections.abc import Callable, Iterable
from enum import Enum, auto

from selenium.common.exceptions import InvalidSessionIdException
from selenium.webdriver.remote.webdriver import WebDriver

from timings import ELEMENT_WAIT, POLL_INTERVAL

logger = logging.getLogger(__name__)

QUICK_REWARD_LINK = (
    "https://new-m.pay.naver.com/historybenefit/eventbenefit?category=quickreward"
)

DEBUG_DIR = "debug"

EXPECTED_QUICK_REWARD_URL_PARTS = (
    "point.pay.naver.com",
    "pay.naver.com/home",
    "new-m.pay.naver.com",
    "pincrux.com",
)


class TextToChange:
    """Expected condition: an element's text differs from a known value."""

    def __init__(self, locator: tuple[str, str], text: str):
        self.locator = locator
        self.text = text

    def __call__(self, driver: WebDriver) -> bool:
        actual_text = driver.find_element(*self.locator).text
        return actual_text != self.text


class Status(Enum):
    PASS = auto()
    FAIL = auto()
    UNDETERMINED = auto()


def resolve_link(handler: Callable) -> Callable:
    """Decorator defaulting a missing ``link`` arg to the driver's current URL."""

    @functools.wraps(handler)
    def wrapper(driver: WebDriver, link: str | None = None):
        if link is None:
            link = driver.current_url
        return handler(driver, link)

    return wrapper


def is_expected_quick_reward_url(url: str) -> bool:
    return any(part in url for part in EXPECTED_QUICK_REWARD_URL_PARTS)


def wait_for_selector(
    driver: WebDriver, selector: str, wait: float = ELEMENT_WAIT
) -> list:
    """Poll for a CSS selector within a wall-clock budget."""

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            from selenium.webdriver.common.by import By

            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements
        except InvalidSessionIdException:
            raise
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return []


def safe_click(driver: WebDriver, element) -> bool:
    """Click via JS first; native click is a fallback."""

    try:
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});"
            "arguments[0].click();",
            element,
        )
        return True
    except InvalidSessionIdException:
        raise
    except Exception as e:
        logger.info("JS click failed: %s", type(e).__name__)

    try:
        element.click()
        return True
    except InvalidSessionIdException:
        raise
    except Exception as e:
        logger.info("native click failed: %s", type(e).__name__)

    return False


def dump_page(driver: WebDriver) -> None:
    try:
        url = driver.current_url
    except Exception as e:
        logger.warning("dump_page: could not read URL: %s", type(e).__name__)
        return

    try:
        os.makedirs(DEBUG_DIR, exist_ok=True)
        page = driver.page_source
        filename = url.replace("https://", "")
        filename = filename.replace("/", "_")
        filename = filename.replace("?", "_")
        if len(filename) > 100:
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
            filename = filename[:100] + "_" + digest
        path = os.path.join(DEBUG_DIR, filename)
        with open(path + ".html", "w", encoding="utf-8") as fd:
            fd.write(page)
        driver.get_screenshot_as_file(path + ".png")
    except Exception as e:
        logger.exception("%s: %s", url, type(e).__name__)


def process_error(
    driver: WebDriver, link: str | None = None, *, quiet: bool = False
) -> None:
    if link is None:
        try:
            link = driver.current_url
        except Exception:
            link = ""

    try:
        url = driver.current_url
    except Exception:
        url = link or ""

    if quiet or is_expected_quick_reward_url(url):
        logger.info("Quick reward page (no dump): %s", url or link)
        return

    dump_page(driver)
    logger.error("Link: %s", link)
    try:
        logger.error("Current URL: %s", driver.current_url)
        logger.error("Title: %s", driver.title)
    except Exception as e:
        logger.error("Could not read page state: %s", type(e).__name__)


def run_handlers(
    driver: WebDriver,
    link: str | None,
    handlers: Iterable[Callable[..., Status]],
) -> Status:
    """Run handlers in order, stopping at the first non-FAIL result."""

    status = Status.FAIL
    for handler in handlers:
        status = handler(driver, link)
        if status is not Status.FAIL:
            break
    return status


def run_quick_reward_handlers(driver: WebDriver, link: str | None = None) -> Status:
    """Route Quick Reward pages by URL instead of trying campaign handlers."""

    from page_actions.campaign import process_alert, process_call_to_action, process_dim
    from page_actions.quick_reward import (
        process_mission_detail,
        process_pay_home_reward,
        process_point_quickreward_main,
    )

    if link is None:
        try:
            link = driver.current_url
        except Exception:
            link = ""

    for handler in (process_alert, process_dim):
        status = handler(driver, link)
        if status is not Status.FAIL:
            return status

    try:
        url = driver.current_url
    except Exception:
        url = link

    if "mission-detail" in url:
        return process_mission_detail(driver, link)
    if "point.pay.naver.com/main" in url and "quickreward" in url:
        return process_point_quickreward_main(driver, link)
    if "pay.naver.com/home" in url:
        return process_pay_home_reward(driver, link)
    if "ofw.adison.co" in url:
        return process_call_to_action(driver, link)
    if is_expected_quick_reward_url(url):
        logger.info("%s: quick reward page (no handler)", url)
        return Status.PASS

    return process_call_to_action(driver, link)
