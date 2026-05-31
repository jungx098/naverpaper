#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from enum import Enum

import apprise
from selenium.common.exceptions import (
    NoAlertPresentException,
    NoSuchElementException,
    TimeoutException,
    UnexpectedAlertPresentException,
)
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

from driver import init
from logging_config import init_logger
from scrape import Database, scrape

logger = logging.getLogger(__name__)

QUICK_REWARD_LINK = (
    "https://new-m.pay.naver.com/historybenefit/eventbenefit?category=quickreward"
)


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


def read_balance(driver, url, xpath):
    """Read a Naver balance from a single page/element, or -1 on failure."""

    balance = -1

    try:
        driver.get(url)
        element = driver.find_element(By.XPATH, xpath)

        old_text = element.text
        logger.info("read_balance: %s", old_text)

        try:
            WebDriverWait(driver, 5).until(text_to_change((By.XPATH, xpath), old_text))
            element = driver.find_element(By.XPATH, xpath)
        except TimeoutException as e:
            logger.info("No Change in Balance Element: %s", type(e).__name__)

        logger.info("read_balance: %s", element.text)

        balance = int(re.sub(r"[^0-9]", "", element.text))
    except Exception as e:
        logger.exception(
            "Balance Not Available: %s (%s)", type(e).__name__, driver.current_url
        )

    return balance


def get_balance(driver):
    """Return the first balance readable from BALANCE_SOURCES, else -1."""

    balance = -1
    for url, xpath in BALANCE_SOURCES:
        balance = read_balance(driver, url, xpath)
        if balance != -1:
            break

    return balance


def mask_username(username: str):
    """Function masking username."""

    return username[0] + "******" + username[-1]


DEBUG_DIR = "debug"


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


def visit(account, campaign_links, driver2, db):
    """Function visiting campaign links."""

    idx = 0
    retry = 0
    pbar = tqdm(total=len(campaign_links), desc=f"{mask_username(account)}: Visit")
    while idx < len(campaign_links):
        link = campaign_links[idx]

        logger.info("Visit %d/%d: %s", idx, len(campaign_links), link)

        try:
            driver2.get(link)
        except UnexpectedAlertPresentException:
            pass
        except Exception as e:
            logger.exception("%s (retry: %d): %s", link, retry, type(e).__name__)
            if retry < 3:
                retry += 1
                continue

        time.sleep(random.uniform(1, 3))

        # Reset retry.
        retry = 0

        status = run_handlers(driver2, link, VISIT_HANDLERS)

        if status is Status.FAIL:
            process_error(driver2, link)

        # The transition time to the target page can be up to 2 seconds without
        # alert, and 3 seconds may be required to stay.
        time.sleep(random.uniform(6, 10))

        if status is Status.PASS:
            db.stamp_campaign(campaign_links[idx])

        idx += 1
        pbar.update(1)
    pbar.close()


def quick_reward(driver, progress=None):
    logger.info("Process Quick Reward")

    try:
        driver.get(QUICK_REWARD_LINK)
        time.sleep(3)
        handle = driver.current_window_handle
        # CSS module class hashes (e.g. mission_item-mission__wcILO) change per
        # Naver build, so match on the stable prefix instead of the full name.
        elements = driver.find_elements(
            By.XPATH, "//*[contains(@class, 'mission_item-mission__')]"
        )
        logger.info("Quick Reward Cnt: %d", len(elements))
        for e in elements:
            logger.info("Quick Reward: %s", e.text)
            if progress:
                progress()

            # Click element using Java Script.
            ActionChains(driver).move_to_element(e).pause(0.8).click().perform()

            # Switch to new handle if new tab is opened.
            multi_window = driver.window_handles
            for window in multi_window:
                if window != handle:
                    driver.switch_to.window(window)

            status = run_handlers(driver, None, QUICK_REWARD_HANDLERS)

            if status is Status.FAIL:
                process_error(driver, None)

            time.sleep(random.uniform(6, 10))

            if handle != driver.current_window_handle:
                driver.close()
                driver.switch_to.window(handle)

        return len(elements)

    except Exception as e:
        logger.exception("Quick Reward Failed: %s", type(e).__name__)

    return -1


def apprise_notify(title, body, urls: list | None = None):
    """Function sending notification to Apprise URLs."""

    if urls:
        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        apobj.notify(body=body, title=title)


def main(campaigns, id, pwd, ua, headless, newsave, apprise_urls):
    time_start = time.time()

    hash = hashlib.sha256(f"{id}_{pwd}_{ua}".encode()).hexdigest()
    user_dir = os.getcwd() + "/user_dir/" + hash

    # If user_dir is not present then create it.
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    db = Database(user_dir + "/campaign.db")
    db.update(campaigns)
    campaigns = db.get_campaigns(days=-3, newvisitonly=True)

    driver = init(id, pwd, ua, headless, newsave, user_dir)
    print(f"{mask_username(id)}: Start Balance: ", end="")
    start_balance = get_balance(driver)
    print(f"{start_balance}")

    # Quick Reward
    quick_reward_cnt = 0
    print(f"{mask_username(id)}: Quick Reward", end="", flush=True)
    quick_reward_cnt = quick_reward(driver, lambda: [print(".", end="", flush=True)])
    sys.stdout.write("\x1b[2K")
    print(f"\r{mask_username(id)}: Quick Reward: {quick_reward_cnt} Done", flush=True)

    # Campaign visit
    if len(campaigns) > 0:
        visit(id, campaigns, driver, db)

    # Test code for balance check
    end_balance = get_balance(driver)
    logger.info("End Balance: %d Gain: %d", end_balance, end_balance - start_balance)

    gain = end_balance - start_balance

    time_end = time.time()

    duration = time_end - time_start
    logger.info("Duration: %.3f secs", duration)

    print(
        f"{mask_username(id)}: Summary {{ "
        f"Balance: {end_balance:,}, "
        f"Gain: {gain:,}, "
        f"Time: {duration:.3f} secs }}"
    )

    driver.quit()

    if apprise_urls and gain != 0:
        apprise_notify(
            f"Naper {mask_username(id)}",
            f"- Quick Reward Count: {quick_reward_cnt}\n"
            f"- Link Count: {len(campaigns)}\n"
            f"- Gain: {(end_balance - start_balance):,} "
            f"({end_balance:,} - {start_balance:,})\n"
            f"- Time: {duration:.3f} secs",
            apprise_urls,
        )


if __name__ == "__main__":

    print("Naper @jungx098 fork of @stateofai")

    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--cd", type=str, required=False, help="credential json")
    parser.add_argument(
        "--headless",
        type=bool,
        required=False,
        default=True,
        action=argparse.BooleanOptionalAction,
        help="browser headless mode (default: headless)",
    )
    parser.add_argument(
        "--newsave",
        type=bool,
        required=False,
        default=False,
        action=argparse.BooleanOptionalAction,
        help="new save or do not",
    )
    parser.add_argument(
        "-cf",
        "--credential-file",
        type=str,
        required=False,
        help="credential json file",
    )

    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--no-verbose", dest="verbose", action="store_const", const=0)

    args = parser.parse_args()
    cd_obj = None
    headless = args.headless
    newsave = args.newsave

    LEVEL = {
        5: logging.DEBUG,
        4: logging.DEBUG,
        3: logging.DEBUG,
        2: logging.DEBUG,
        1: logging.INFO,
        0: logging.CRITICAL + 1,
    }

    init_logger(
        console_logging_level=LEVEL[args.verbose],
        file_logging_level=max(LEVEL[args.verbose], logging.INFO),
        filename="./log.txt",
    )

    logger.info("안녕 Verbose Level: %d", args.verbose)

    if args.cd is None and args.credential_file is None:
        id = os.getenv("USERNAME")
        pw = os.getenv("PASSWORD")
        if id is None or pw is None:
            print("not setting USERNAME / PASSWORD")
            exit()
        cd_obj = [{"id": id, "pw": pw}]
    elif args.cd is not None:
        try:
            cd_obj = json.loads(args.cd)
        except Exception as e:
            logger.exception("JSON Loading Error: %s", type(e).__name__)
            print("use -c or --cd argument")
            print(
                'credential json sample [{"id":"id1","pw":"pw1"},{"id":"id2","pw":"pw2"}]'
            )
            print("json generate site https://jsoneditoronline.org/")
            exit()
    elif args.credential_file is not None:
        with open(args.credential_file, encoding="utf-8") as file_obj:
            cd_obj = json.load(file_obj)

    if cd_obj is None:
        logger.warning("No Credential Provided!")
    else:
        print("Campaign Link Collection: ", end="", flush=True)
        campaigns = scrape(lambda: [print(".", end="", flush=True)])
        sys.stdout.write("\x1b[2K")
        print(f"\rCampaign Link Collection: {len(campaigns)} Links")

        for account in cd_obj:
            id = account.get("id")
            pw = account.get("pw")
            ua = account.get("ua")
            urls = account.get("apprise")

            if id is None:
                print("ID not found!")
                continue
            if pw is None:
                print("PW not found!")
                continue

            try:
                main(campaigns, id, pw, ua, headless, newsave, urls)
            except Exception as e:
                # Isolate per-account failures so one account (e.g. a locked DB
                # from an overlapping run) does not abort the remaining accounts.
                logger.exception(
                    "Account run failed for %s: %s",
                    mask_username(id),
                    type(e).__name__,
                )
                continue

    logger.info("Bye!")
