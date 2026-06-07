#!/usr/bin/env python3
"""Page-interaction primitives for Naver campaign/quick-reward flows.

Holds the per-page handlers that inspect the current page after a navigation
and report a :class:`Status`, plus shared helpers (``Status``,
``text_to_change``, ``dump_page``) and the ordered handler chains consumed by
the orchestration code in ``naper.py``.
"""

import functools
import hashlib
import logging
import os
import time
from collections.abc import Callable, Iterable
from enum import Enum, auto

from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoAlertPresentException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)

QUICK_REWARD_LINK = (
    "https://new-m.pay.naver.com/historybenefit/eventbenefit?category=quickreward"
)

DEBUG_DIR = "debug"
ELEMENT_WAIT = 5

# Npay Point / Pay home pages opened by Quick Reward missions. These use
# ButtonBox CTAs, not Adison .call_to_action elements.
_MISSION_DETAIL_MORE = 'button[data-nlog-click="mssdetail.more"]'
_MISSION_GREEN_BTN = 'button[class*="ButtonBox-module_color-npayGreen"]'
_EXPECTED_QUICK_REWARD_URL_PARTS = (
    "point.pay.naver.com",
    "pay.naver.com/home",
    "new-m.pay.naver.com",
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


def _is_expected_quick_reward_url(url: str) -> bool:
    return any(part in url for part in _EXPECTED_QUICK_REWARD_URL_PARTS)


def _wait_for_selector(
    driver: WebDriver, selector: str, wait: float = ELEMENT_WAIT
) -> list:
    """Poll for a CSS selector within a wall-clock budget."""

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                return elements
        except InvalidSessionIdException:
            raise
        except Exception:
            pass
        time.sleep(0.25)
    return []


def _safe_click(driver: WebDriver, element) -> bool:
    """Click via JS first; native click is a fallback.

    Native ``WebElement.click()`` can block for a long time on overlays and
    stamp-campaign popups when Chrome is busy.
    """

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

    if quiet or _is_expected_quick_reward_url(url):
        logger.info("Quick reward page (no dump): %s", url or link)
        return

    dump_page(driver)
    logger.error("Link: %s", link)
    try:
        logger.error("Current URL: %s", driver.current_url)
        logger.error("Title: %s", driver.title)
    except Exception as e:
        logger.error("Could not read page state: %s", type(e).__name__)


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
            # <div class="buttons"><div class="submit-button btn-naver" onclick="CustomDialog.dismiss()">확인</div></div>
            # buttons = driver.find_element(By.CLASS_NAME, "submit-button btn-naver")
            buttons = driver.find_element(By.CLASS_NAME, "buttons")
            buttons.click()
        except NoSuchElementException:
            logger.info("No buttons Found")
    except NoSuchElementException:
        logger.info("No modal Found")


def process_popup_link(driver: WebDriver, link: str | None = None) -> Status:
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
            if not _safe_click(driver, buttons):
                logger.info("popup_link click failed")
                return Status.FAIL
            time.sleep(5)
        except Exception as e:
            logger.info("No buttons Found: %s", type(e).__name__)
            return Status.FAIL
    except Exception as e:
        logger.info("No popup_link Found: %s", type(e).__name__)
        return Status.FAIL

    return Status.PASS


def _click_link_text(driver: WebDriver, text: str, wait: float = ELEMENT_WAIT) -> bool:
    """Click the first matching link within a wall-clock budget.

    Uses find_elements polling instead of WebDriverWait so a hung Chrome tab
    cannot stack many full command-timeout round trips behind one wait.
    """

    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        try:
            elements = driver.find_elements(By.LINK_TEXT, text)
            if elements:
                if _safe_click(driver, elements[0]):
                    time.sleep(5)
                    return True
        except InvalidSessionIdException:
            raise
        except Exception:
            pass
        time.sleep(0.25)
    return False


def process_confirm(driver: WebDriver, link: str | None = None) -> Status:
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

    time.sleep(1)

    more_buttons = _wait_for_selector(driver, _MISSION_DETAIL_MORE, wait=2)
    if more_buttons and _safe_click(driver, more_buttons[0]):
        logger.info("mission_detail click: 더 알아보기")
        time.sleep(2)
        return Status.UNDETERMINED

    for button in _wait_for_selector(driver, _MISSION_GREEN_BTN, wait=2)[:3]:
        try:
            label = button.text.strip() or "ButtonBox"
        except Exception:
            label = "ButtonBox"
        if _safe_click(driver, button):
            logger.info("mission_detail click: %s", label)
            time.sleep(2)
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
    time.sleep(1)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    logger.info("%s: pay home scroll reward", link)
    return Status.PASS


@resolve_link
def process_call_to_action(driver: WebDriver, link: str) -> Status:
    try:
        # Wait for the page update.
        time.sleep(3)
        element = driver.find_element(By.CLASS_NAME, "call_to_action")
        logger.info("Click %s", element.text)
        if not _safe_click(driver, element):
            return Status.FAIL

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
    process_point_quickreward_main,
    process_mission_detail,
    process_pay_home_reward,
    process_call_to_action,
)


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
