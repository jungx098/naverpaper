#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from collections.abc import Callable

import apprise
from selenium.common.exceptions import (
    InvalidSessionIdException,
    StaleElementReferenceException,
    UnexpectedAlertPresentException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from tqdm import tqdm

from balance import get_balance
from driver import init, session_alive
from logging_config import init_logger
from page_actions import (
    QUICK_REWARD_LINK,
    VISIT_HANDLERS,
    Status,
    process_error,
    run_handlers,
    run_quick_reward_handlers,
    safe_click,
)
from timings import (
    MAX_VISIT_RETRIES,
    QUICK_REWARD_LOAD,
    dwell_after_handler,
    dwell_after_nav,
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


def _abort_on_dead_session(driver: WebDriver, context: str) -> None:
    if not session_alive(driver):
        logger.error("Browser session ended during %s", context)
        raise InvalidSessionIdException("browser session ended")


def _switch_to_new_tab(driver: WebDriver, main_handle: str) -> None:
    for window in driver.window_handles:
        if window != main_handle:
            driver.switch_to.window(window)
            return


def _close_extra_tab(driver: WebDriver, main_handle: str) -> None:
    if driver.current_window_handle != main_handle:
        driver.close()
        driver.switch_to.window(main_handle)


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
        except InvalidSessionIdException:
            raise
        except WebDriverException as e:
            logger.exception("%s (retry: %d): %s", link, retry, type(e).__name__)
            if retry < MAX_VISIT_RETRIES:
                retry += 1
                continue
            raise

        time.sleep(dwell_after_nav())

        # Reset retry.
        retry = 0

        try:
            status = run_handlers(driver2, link, VISIT_HANDLERS)
        except InvalidSessionIdException:
            raise
        except WebDriverException as e:
            logger.exception(
                "Visit handler failed for %s (retry: %d): %s",
                link,
                retry,
                type(e).__name__,
            )
            if retry < MAX_VISIT_RETRIES:
                retry += 1
                continue
            raise

        if status is Status.FAIL:
            process_error(driver2, link)
            _abort_on_dead_session(driver2, f"visit {idx}/{len(campaign_links)}")

        # The transition time to the target page can be up to 2 seconds without
        # alert, and 3 seconds may be required to stay.
        time.sleep(dwell_after_handler())

        if status is Status.PASS:
            db.stamp_campaign(campaign_links[idx])

        idx += 1
        pbar.update(1)
    pbar.close()


MISSION_XPATH = "//*[contains(@class, 'mission_item-mission__')]"


def quick_reward(driver: WebDriver, progress: Callable | None = None) -> int:
    logger.info("Process Quick Reward")

    try:
        driver.get(QUICK_REWARD_LINK)
        time.sleep(QUICK_REWARD_LOAD)
        handle = driver.current_window_handle
        # CSS module class hashes (e.g. mission_item-mission__wcILO) change per
        # Naver build, so match on the stable prefix instead of the full name.
        mission_count = len(driver.find_elements(By.XPATH, MISSION_XPATH))
        logger.info("Quick Reward Cnt: %d", mission_count)
        for i in range(mission_count):
            elements = driver.find_elements(By.XPATH, MISSION_XPATH)
            if i >= len(elements):
                break
            e = elements[i]
            try:
                label = e.text
            except StaleElementReferenceException:
                logger.info("Quick Reward: stale element at index %d, skipping", i)
                continue
            logger.info("Quick Reward: %s", label)
            if progress:
                progress()

            if not safe_click(driver, e):
                logger.info("Quick Reward: click failed at index %d", i)
                continue

            _switch_to_new_tab(driver, handle)

            status = run_quick_reward_handlers(driver)

            if status is Status.FAIL:
                process_error(driver, None, quiet=True)
                _abort_on_dead_session(driver, "quick reward")

            time.sleep(dwell_after_handler())

            _close_extra_tab(driver, handle)

        return mission_count

    except InvalidSessionIdException:
        raise
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


def user_dir_for(naver_id: str, password: str, ua: str | None) -> str:
    """Return the per-account Chrome profile directory, creating it if missing.

    The path is keyed by a hash of id+pw+ua so each account/UA gets an isolated
    profile. Both a normal run and the profile-seeding tool (seed_login.py)
    must use this helper so a manually seeded login session maps to the exact
    profile a normal run reuses.
    """

    account_hash = hashlib.sha256(
        f"{naver_id}_{password}_{ua}".encode()
    ).hexdigest()
    user_dir = os.getcwd() + "/user_dir/" + account_hash

    # If user_dir is not present then create it.
    if not os.path.exists(user_dir):
        os.makedirs(user_dir)

    return user_dir


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

    user_dir = user_dir_for(naver_id, password, ua)

    db = Database(user_dir + "/campaign.db")
    db.update(campaigns)
    campaigns = db.get_campaigns(days=-3, newvisitonly=True)

    driver = init(naver_id, password, ua, headless, newsave, user_dir)
    try:
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
        logger.info(
            "End Balance: %d Gain: %d", end_balance, end_balance - start_balance
        )

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
    finally:
        # Always close cleanly so Chrome flushes the persistent login cookie
        # (NID_AUT) to the profile. Skipping quit() on a mid-run error left the
        # session unsaved, which made "stay signed in" appear broken next run.
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
        default=True,
        action=argparse.BooleanOptionalAction,
        help="browser headless mode (default: headless)",
    )
    parser.add_argument(
        "--newsave",
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
