#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import random
import re
import time
from pprint import pformat

import apprise
from selenium.common.exceptions import (NoAlertPresentException,
                                        NoSuchElementException,
                                        TimeoutException,
                                        UnexpectedAlertPresentException)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm

import naver_paper_clien as clien
import naver_paper_damoang as damoang
import naver_paper_ppomppu as ppomppu
import naver_paper_ruliweb as ruliweb
from logging_config import init_logger
from run_new import init
from scrape import Database, scrape
import sys

logger = logging.getLogger(__name__)

QUICK_REWARD_LINK = "https://new-m.pay.naver.com/historybenefit/eventbenefit?category=quickreward"


class text_to_change(object):
    """Class checking element text change."""

    def __init__(self, locator, text):
        self.locator = locator
        self.text = text

    def __call__(self, driver):
        actual_text = driver.find_element(*self.locator).text
        return actual_text != self.text


def grep_campaign_links():
    """Function making campaign link list."""

    campaign_links = []

    try:
        campaign_links += clien.find_naver_campaign_links()
    except Exception as e:
        logger.exception("clien.find_naver_campaign_links Failed: %s",
                         type(e).__name__)

    try:
        campaign_links += damoang.find_naver_campaign_links()
    except Exception as e:
        logger.exception("damoang.find_naver_campaign_links Failed: %s",
                         type(e).__name__)

    try:
        campaign_links += ppomppu.find_naver_campaign_links()
    except Exception as e:
        logger.exception("ppomppu.find_naver_campaign_links Failed: %s",
                         type(e).__name__)

    try:
        campaign_links += ruliweb.find_naver_campaign_links()
    except Exception as e:
        logger.exception("ruliweb.find_naver_campaign_links Failed: %s",
                         type(e).__name__)

    campaign_links = list(set(campaign_links))
    logger.info("Unvisited Campaign Link Count: %d", len(campaign_links))

    return campaign_links


def get_balance1(driver):
    """Function checking slow Naver balance (initial value of old balance)."""

    balance = -1

    try:
        driver.get("https://new-m.pay.naver.com/mydata/home")
        class_name = "AssetCommonItem_balance__mkiEz"
        element = driver.find_element(By.CLASS_NAME, class_name)
        old_text = element.text
        logger.info("get_balance1: %s", old_text)

        try:
            WebDriverWait(driver, 5).until(text_to_change(
                (By.CLASS_NAME, class_name), old_text))
            element = driver.find_element(By.CLASS_NAME, class_name)
        except TimeoutException as e:
            logger.info("No Change in Balance Element: %s", type(e).__name__)

        logger.info("get_balance1: %s", element.text)

        balance = int(re.sub(r"[^0-9]", "", element.text))
    except Exception as e:
        logger.exception("Balance Not Available: %s", type(e).__name__)

    return balance


def get_balance2(driver):
    """Function checking fast Naver balance (initial value of 0)."""

    balance = -1

    try:
        driver.get("https://new-m.pay.naver.com/pointshistory/list?category=all")
        class_name = "PointsManage_price__w__Du"
        element = driver.find_element(By.CLASS_NAME, class_name)
        old_text = element.text
        logger.info("get_balance2: %s", old_text)

        try:
            WebDriverWait(driver, 5).until(text_to_change(
                (By.CLASS_NAME, class_name), old_text))
            element = driver.find_element(By.CLASS_NAME, class_name)
        except TimeoutException as e:
            logger.info("No Change in Balance Element: %s", type(e).__name__)

        logger.info("get_balance2: %s", element.text)

        balance = int(re.sub(r"[^0-9]", "", element.text))
    except Exception as e:
        logger.exception("Balance Not Available: %s", type(e).__name__)

    return balance


def get_balance(driver):
    """Function returning balance."""

    # Check faster balance check method
    balance = get_balance2(driver)

    if balance == -1:
        # Fall back to slower balance check method
        balance = get_balance1(driver)

    return balance


def mask_username(username: str):
    """Function masking username."""

    return (
        username[0]
        + "******"
        + username[-1]
    )


def log_html(url, page):
    filename = url.replace('https://', '')
    filename = filename.replace('/', '_')
    filename = filename.replace('?', '_')
    filename = filename + '.html'
    with open(filename, "w", encoding="utf-8") as fd:
        fd.write(page)


def process_error(driver, link):
    if link is None:
        link = driver.current_url

    log_html(driver.current_url, driver.page_source)
    logger.error("Link: %s", link)
    logger.error("Current URL: %s", driver.current_url)
    logger.error("Title: %s", driver.title)


def process_alert(driver, link):
    if link is None:
        link = driver.current_url

    try:
        result = driver.switch_to.alert
        logger.info("%s: %s", link, result.text)
        result.accept()
        return True

    except NoAlertPresentException:
        pass

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return False


def process_dim(driver, link):
    if link is None:
        link = driver.current_url

    try:
        text = driver.find_element(By.CLASS_NAME, "dim").text
        text = text.replace("\n", " ")
        logger.info("%s: %s - %s (No Alert)", link, driver.title, text)
        return True

    except NoSuchElementException as e:
        pass

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return False


def process_quickreward_link(driver, link):
    if link is None:
        link = driver.current_url

    try:
        if driver.current_url == QUICK_REWARD_LINK:
            text = "Quick Reward Ignored"
            logger.info("%s: %s - %s (No Alert)", link, driver.title, text)
            return True

    except Exception as e:
        logger.exception("%s: %s", link, type(e).__name__)

    return False


def process_modal(driver):
    try:
        modal = driver.find_element(By.CLASS_NAME, "modal")
        logger.info("modal: %s", modal.text.replace("\n", " "))

        try:
            # <div class="buttons"><div class="submit-button btn-naver" onclick="CustomDialog.dismiss()">확인</div></div>
            # buttons = driver.find_element(By.CLASS_NAME, "submit-button btn-naver")
            buttons = driver.find_element(By.CLASS_NAME, "buttons")
            buttons.click()
        except:
            logger.info("No buttons Found")
    except:
        logger.info("No modal Found")


def process_call_to_action(driver, link):
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
        return True

    except NoSuchElementException as e:
        pass

    except Exception as e:
        logger.exception("%s", type(e).__name__)

    return False


def visit(account, campaign_links, driver2, db):
    """Function visiting campaign links."""

    idx = 0
    retry = 0
    pbar = tqdm(total=len(campaign_links), desc=f"{mask_username(account)}: Visit")
    while idx < len(campaign_links):
        link = campaign_links[idx]

        try:
            driver2.get(link)
        except UnexpectedAlertPresentException:
            pass
        except Exception as e:
            logger.exception("%s (retry: %d): %s",
                             link, retry, type(e).__name__)
            if retry < 3:
                retry += 1
                continue

        time.sleep(random.uniform(1, 3))

        # Reset retry.
        retry = 0

        if process_alert(driver2, link) is True:
            pass
        elif process_dim(driver2, link) is True:
            pass
        elif process_quickreward_link(driver2, link) is True:
            pass
        elif process_call_to_action(driver2, link) is True:
            pass
        else:
            process_error(driver2, link)

        # The transition time to the target page can be up to 2 seconds without
        # alert, and 3 seconds may be required to stay.
        time.sleep(random.uniform(6, 10))

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
        elements = driver.find_elements(
            By.CLASS_NAME, "ADRewardBannerSystem_title__3f6bG")
        logger.info("Quick Reward Cnt: %d", len(elements))
        for e in elements:
            logger.info("Quick Reward: %s", e.text)
            if progress:
                progress()

            # Click element using Java Script.
            driver.execute_script("arguments[0].click();", e)

            # Switch to new handle if new tab is opened.
            multi_window = driver.window_handles
            for window in multi_window:
                if window != handle:
                    driver.switch_to.window(window)

            if process_alert(driver, None) is True:
                pass
            elif process_dim(driver, None) is True:
                pass
            elif process_call_to_action(driver, None) is True:
                pass
            else:
                process_error(driver, None)

            time.sleep(random.uniform(6, 10))

            if handle != driver.current_window_handle:
                driver.close()
                driver.switch_to.window(handle)

        return len(elements)

    except Exception as e:
        logger.exception("Quick Reward Failed: %s", type(e).__name__)

    return -1


def apprise_notify(title, body, urls: list = []):
    """Function sending notification to Apprise URLs."""

    if urls:
        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        apobj.notify(body=body, title=title)


def main(campaigns, id, pwd, ua, headless, newsave, apprise_urls):
    time_start = time.time()

    hash = hashlib.sha256(f"{id}_{pwd}_{ua}".encode('utf-8')).hexdigest()

    db = Database(os.getcwd() + "/user_dir/" + hash + "/campaign.db")
    db.update(campaigns)
    campaigns = db.get_campaigns(days=-7, newvisitonly=True)

    driver = init(id, pwd, ua, headless, newsave, hash)
    print(f"{mask_username(id)}: Start Balance: ", end="")
    start_balance = get_balance(driver)
    print(f"{start_balance}")

    # Quick Reward
    print(f"{mask_username(id)}: Quick Reward", end="", flush=True)
    cnt = quick_reward(driver, lambda: [print(".", end="", flush=True)])
    sys.stdout.write('\x1b[2K')
    print(f"\r{mask_username(id)}: Quick Reward: {cnt} Done", flush=True)

    if len(campaigns) > 0:
        visit(id, campaigns, driver, db)

    # Test code for balance check
    end_balance = get_balance(driver)
    logger.info("End Balance: %d Gain: %d",
                end_balance,
                end_balance - start_balance)

    gain = end_balance - start_balance

    time_end = time.time()

    duration = time_end - time_start
    logger.info("Duration: %.3f secs", duration)

    print(f"{mask_username(id)}: Summary {{ "
          f"Balance: {end_balance:,}, "
          f"Gain: {gain:,}, "
          f"Time: {duration:.3f} secs }}")

    driver.quit()

    if apprise_urls and gain != 0:
        apprise_notify(f"Naper {mask_username(id)}",
                       f"Link Count: {len(campaigns)}\n"
                       f"Start Balance: {start_balance:,}\n"
                       f"End Balance: {end_balance:,}\n"
                       f"Gain: {(end_balance - start_balance):,}\n"
                       f"Time: {duration:.3f} secs",
                       apprise_urls)


if __name__ == "__main__":

    print("Naper @jungx098 fork of @stateofai")

    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--id", type=str,
                        required=False, help="naver id")
    parser.add_argument("-p", "--pw", type=str,
                        required=False, help="naver password")
    parser.add_argument("-c", "--cd", type=str,
                        required=False, help="credential json")
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
    parser.add_argument("--no-verbose", dest="verbose",
                        action="store_const", const=0)

    args = parser.parse_args()
    cd_obj = None
    headless = args.headless
    newsave = args.newsave

    LEVEL = {
        5: logging.DEBUG,
        4: logging.INFO,
        3: logging.WARNING,
        2: logging.ERROR,
        1: logging.CRITICAL,
        0: logging.CRITICAL + 1,
    }

    init_logger(console_logging_level=LEVEL[args.verbose],
                file_logging_level=max(LEVEL[args.verbose], logging.INFO),
                filename="./log.txt")

    logger.info("안녕 Verbose Level: %d", args.verbose)

    if (
        args.id is None
        and args.pw is None
        and args.cd is None
        and args.credential_file is None
    ):
        id = os.getenv("USERNAME")
        pw = os.getenv("PASSWORD")
        if pw is None and pw is None:
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
        file_obj = open(args.credential_file, "r", encoding="utf-8")
        cd_obj = json.load(file_obj)
    else:
        if args.id is None:
            print("use -i or --id argument")
            exit()
        if args.pw is None:
            print("use -p or --pwd argument")
            exit()
        cd_obj = [{"id": args.id, "pw": args.pw}]

    if cd_obj is None:
        logger.warning("No Credential Provided!")
    else:
        print("Campaign Link Collection: ", end="", flush=True)
        campaigns = scrape(lambda: [print(".", end="", flush=True)])
        sys.stdout.write('\x1b[2K')
        print(f"\rCampaign Link Collection: {len(campaigns)} Links")

        for idx, account in enumerate(cd_obj):
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

            main(campaigns, id, pw, ua, headless, newsave, urls)

    logger.info("Bye!")
