#!/usr/bin/env python3

import argparse
import json
import logging
import os
import random
import re
import time

import apprise
from selenium.common.exceptions import NoAlertPresentException
from selenium.webdriver.common.by import By
from tqdm import tqdm

import naver_paper_clien as clien
import naver_paper_damoang as damoang
import naver_paper_ppomppu as ppomppu
from logging_config import init_logger
from run_new import init

logger = logging.getLogger(__name__)


def grep_campaign_links():
    """Function making campaign link list"""

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

    campaign_links = list(set(campaign_links))
    logger.info("Unvisited Campaign Link Count: %d", len(campaign_links))

    return campaign_links


def get_balance(driver):
    """Function checking Naver balance."""

    balance = -1

    try:
        driver.get("https://new-m.pay.naver.com/mydata/home")
        balance = driver.find_element(By.CLASS_NAME,
                                      "AssetCommonItem_balance__mkiEz")
        balance = int(re.sub(r"[^0-9]", "", balance.text))
    except Exception as e:
        logger.exception("Balance Not Available: %s", type(e).__name__)

    return balance


def mask_username(username: str):
    """Function masking username."""

    return (
        username[0]
        + "******"
        + username[-1]
    )


def visit(account, campaign_links, driver2):
    """Function visiting campaign links."""

    idx = 0
    pbar = tqdm(total=len(campaign_links), desc=mask_username(account))
    while idx < len(campaign_links):
        link = campaign_links[idx]
        driver2.get(link)

        try:
            result = driver2.switch_to.alert
            logger.info("%s: %s", link, result.text)
            result.accept()
        except NoAlertPresentException:
            logger.warning("%s: No Alert to Accept!", link)
            time.sleep(3)
        except Exception as e:
            logger.exception("%s: %s", link, type(e).__name__)
            time.sleep(3)
            # pageSource = driver2.page_source
            # print(pageSource)

        time.sleep(1)

        idx += 1
        pbar.update(1)
    pbar.close()


def apprise_notify(title, body, urls: list = []):
    """Function sending notification to Apprise URLs."""

    if urls:
        apobj = apprise.Apprise()
        for url in urls:
            apobj.add(url)
        apobj.notify(body=body, title=title)


def main(campaign_links, id, pwd, ua, headless, newsave, apprise_urls):
    time_start = time.time()

    driver = init(id, pwd, ua, headless, newsave)
    start_balance = get_balance(driver)
    logger.info("Start Balance: %d", start_balance)

    visit(id, campaign_links, driver)

    # Wait for balance update.
    wait_time = random.randint(30, 60)
    for _ in tqdm(range(wait_time),
                  desc=f"Wait for {wait_time} secs for Balance Update"):
        time.sleep(1)

    # Test code for balance check
    driver.refresh()
    end_balance = get_balance(driver)
    logger.info("End Balance: %d Gain: %d", end_balance,
                end_balance - start_balance)

    gain = end_balance - start_balance

    time_end = time.time()

    duration = time_end - time_start
    logger.info("Duration: %.3f secs", duration)

    print(f"{mask_username(id)}: Start Balance: {start_balance:,} "
          f"End Balance: {end_balance:,} "
          f"Gain: {gain:,} "
          f"Time: {duration:.3f} secs")

    driver.quit()

    if apprise_urls and (campaign_links or gain > 0):
        apprise_notify(f"Npaper {mask_username(id)}",
                       f"Link Count: {len(campaign_links)}\n"
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
                file_logging_level=LEVEL[args.verbose],
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
        campaign_links = grep_campaign_links()
        print(f"Number of Links to Visit: {len(campaign_links)}")

        if len(campaign_links) > 0:
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

                main(campaign_links, id, pw, ua, headless, newsave, urls)

    logger.info("Bye!")
