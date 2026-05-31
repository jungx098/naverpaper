#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import time
from collections.abc import Callable

import apprise
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from tqdm import tqdm

from balance import get_balance
from driver import init
from logging_config import init_logger
from page_actions import (
    QUICK_REWARD_HANDLERS,
    QUICK_REWARD_LINK,
    VISIT_HANDLERS,
    Status,
    process_error,
    run_handlers,
)
from scrape import Database, scrape

logger = logging.getLogger(__name__)


def mask_username(username: str) -> str:
    """Mask a username for logging, revealing as little as possible.

    A fixed-width mask hides the true length. Short usernames are masked more
    aggressively because revealing both ends would leak most of the value:

    - length 0       -> ""
    - length 1-2     -> fully masked (no characters revealed)
    - length 3-4     -> only the first character revealed
    - length 5+      -> first and last character revealed
    """

    if not username:
        return ""

    length = len(username)
    if length <= 2:
        return "******"
    if length <= 4:
        return username[0] + "******"
    return username[0] + "******" + username[-1]


def visit(
    account: str, campaign_links: list[str], driver2: WebDriver, db: Database
) -> None:
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


def quick_reward(driver: WebDriver, progress: Callable | None = None) -> int:
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


def apprise_notify(title: str, body: str, urls: list | None = None) -> None:
    """Function sending notification to Apprise URLs."""

    if urls:
        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        apobj.notify(body=body, title=title)


def main(
    campaigns: list[str],
    naver_id: str,
    password: str,
    ua: str | None,
    headless: bool,
    newsave: bool,
    apprise_urls: list | None,
) -> None:
    time_start = time.time()

    account_hash = hashlib.sha256(
        f"{naver_id}_{password}_{ua}".encode()
    ).hexdigest()
    user_dir = os.getcwd() + "/user_dir/" + account_hash

    # If user_dir is not present then create it.
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    db = Database(user_dir + "/campaign.db")
    db.update(campaigns)
    campaigns = db.get_campaigns(days=-3, newvisitonly=True)

    driver = init(naver_id, password, ua, headless, newsave, user_dir)
    print(f"{mask_username(naver_id)}: Start Balance: ", end="")
    start_balance = get_balance(driver)
    print(f"{start_balance}")

    # Quick Reward
    quick_reward_cnt = 0
    print(f"{mask_username(naver_id)}: Quick Reward", end="", flush=True)
    quick_reward_cnt = quick_reward(driver, lambda: [print(".", end="", flush=True)])
    sys.stdout.write("\x1b[2K")
    print(
        f"\r{mask_username(naver_id)}: Quick Reward: {quick_reward_cnt} Done",
        flush=True,
    )

    # Campaign visit
    if len(campaigns) > 0:
        visit(naver_id, campaigns, driver, db)

    # Test code for balance check
    end_balance = get_balance(driver)
    logger.info("End Balance: %d Gain: %d", end_balance, end_balance - start_balance)

    gain = end_balance - start_balance

    time_end = time.time()

    duration = time_end - time_start
    logger.info("Duration: %.3f secs", duration)

    print(
        f"{mask_username(naver_id)}: Summary {{ "
        f"Balance: {end_balance:,}, "
        f"Gain: {gain:,}, "
        f"Time: {duration:.3f} secs }}"
    )

    driver.quit()

    if apprise_urls and gain != 0:
        apprise_notify(
            f"Naper {mask_username(naver_id)}",
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
        naver_id = os.getenv("USERNAME")
        password = os.getenv("PASSWORD")
        if naver_id is None or password is None:
            print("not setting USERNAME / PASSWORD")
            exit()
        cd_obj = [{"id": naver_id, "pw": password}]
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
            naver_id = account.get("id")
            password = account.get("pw")
            ua = account.get("ua")
            urls = account.get("apprise")

            if naver_id is None:
                print("ID not found!")
                continue
            if password is None:
                print("PW not found!")
                continue

            try:
                main(campaigns, naver_id, password, ua, headless, newsave, urls)
            except Exception as e:
                # Isolate per-account failures so one account (e.g. a locked DB
                # from an overlapping run) does not abort the remaining accounts.
                logger.exception(
                    "Account run failed for %s: %s",
                    mask_username(naver_id),
                    type(e).__name__,
                )
                continue

    logger.info("Bye!")
