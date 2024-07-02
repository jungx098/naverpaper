import argparse
import hashlib
import json
import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from run_new import grep_campaign_links
from run_new import init
from run_new import visit

logger = logging.getLogger("Naver-Paper")


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    blue = "\x1b[38;5;39m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s [%(levelname)s] %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: blue + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def init_logger(debug: bool = True):
    """Function initializing logger."""

    # create console handler with a higher log level.
    ch = logging.StreamHandler()
    ch.setFormatter(CustomFormatter())

    logger.addHandler(ch)

    # Set logger level.
    if debug is True:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.CRITICAL + 1)


def main(campaign_links, id, pwd, ua, headless, newsave):
    driver = init(id, pwd, ua, headless, newsave)
    visit(campaign_links, driver)

    # Balance Check
    try:
        driver.get("https://new-m.pay.naver.com/mydata/home")
        balance = driver.find_element(By.CLASS_NAME, "AssetCommonItem_balance__mkiEz")
        print(f"Balance: {balance.text}")
    except Exception as e:
        logging.warning("%s: Balance Not Available!", e)

    driver.quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id', type=str, required=False, help="naver id")
    parser.add_argument('-p', '--pw', type=str, required=False, help="naver password")
    parser.add_argument('-c', '--cd', type=str, required=False, help="credential json")
    parser.add_argument('--headless', type=bool, required=False,
                        default=True, action=argparse.BooleanOptionalAction,
                        help="browser headless mode (default: headless)")
    parser.add_argument('--newsave', type=bool, required=False,
                        default=False, action=argparse.BooleanOptionalAction,
                        help="new save or do not")
    parser.add_argument('-cf', '--credential-file', type=str, required=False,
                        help="credential json file")
    parser.add_argument('-d', '--debug', type=bool, required=False,
                        default=False, action=argparse.BooleanOptionalAction,
                        help="debug mode")
    args = parser.parse_args()
    cd_obj = None
    headless = args.headless
    newsave = args.newsave
    init_logger(args.debug)

    if (args.id is None and
            args.pw is None and
            args.cd is None and
            args.credential_file is None):
        id = os.getenv("USERNAME")
        pw = os.getenv("PASSWORD")
        if(pw is None and pw is None):
            print('not setting USERNAME / PASSWORD')
            exit()
        cd_obj = [{"id": id, "pw": pw}]
    elif(args.cd is not None):
        try:
            cd_obj = json.loads(args.cd)
        except:
            print('use -c or --cd argument')
            print('credential json sample [{"id":"id1","pw":"pw1"},{"id":"id2","pw":"pw2"}]')
            print('json generate site https://jsoneditoronline.org/')
            exit()
    elif args.credential_file is not None:
        file_obj = open(args.credential_file, "r", encoding="utf-8")
        cd_obj = json.load(file_obj)
    else:
        if args.id is None:
            print('use -i or --id argument')
            exit()
        if args.pw is None:
            print('use -p or --pwd argument')
            exit()
        cd_obj = [{"id": args.id, "pw": args.pw}]

    campaign_links = grep_campaign_links()
    for idx, account in enumerate(cd_obj):
        id = account.get("id")
        pw = account.get("pw")
        ua = account.get("ua")

        print(f">>> {idx+1}번째 계정")

        if id is None:
            print("ID not found!")
            continue
        if pw is None:
            print("PW not found!")
            continue

        main(campaign_links, id, pw, ua, headless, newsave)
