#!/usr/bin/env python3
"""Chrome driver setup and Naver login."""

import logging
import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


def log_messages(driver, level):
    error_messages = driver.find_elements(By.CLASS_NAME, "error_message")
    for i, e in enumerate(error_messages):
        if e.text:
            logger.log(
                level, "error_messages %d: %s", i, e.text.strip().replace("\n", " ")
            )

    message_text = driver.find_elements(By.CLASS_NAME, "message_text")
    for i, e in enumerate(message_text):
        if e.text:
            logger.log(
                level, "message_text %d: %s", i, e.text.strip().replace("\n", " ")
            )


def init(id, pwd, ua, headless, newsave, user_dir):
    # 크롬 드라이버 옵션 설정
    chrome_options = webdriver.ChromeOptions()

    if headless is True:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument(f"--user-data-dir={user_dir}")
    # Anti-detection: prevent sites from detecting Selenium automation,
    # which can cause session invalidation and forced re-login.
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    if ua is not None:
        chrome_options.add_argument(f"--user-agent={ua}")

    # 새로운 창 생성
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=chrome_options
        )
    except Exception as e:
        # Fall back to driver creation without service object.
        logger.exception("Driver Creation Failed: %s", type(e).__name__)
        driver = webdriver.Chrome(options=chrome_options)

    driver.set_page_load_timeout(30)
    driver.get("https://nid.naver.com")

    # Login page (log-in required) title for nid.naver.com
    #   <title>Naver Sign in</title>
    # ID page (successful logged-in) title for nid.naver.com
    #   <title>Naver ID</title>
    if driver.title == "Naver ID" or driver.title == "네이버ID":
        logger.info("Existing log-in session used")
        return driver

    # 현재 열려 있는 창 가져오기
    current_window_handle = driver.current_window_handle

    # 새롭게 생성된 탭의 핸들을 찾습니다
    # 만일 새로운 탭이 없을경우 기존 탭을 사용합니다.
    new_window_handle = None
    for handle in driver.window_handles:
        if handle != current_window_handle:
            new_window_handle = handle
            break
        else:
            new_window_handle = handle

    # 새로운 탭을 driver2로 지정합니다
    driver.switch_to.window(new_window_handle)
    driver2 = driver

    username = driver2.find_element(By.NAME, "id")
    pw = driver2.find_element(By.NAME, "pw")

    # GitHub Action을 사용하지 않을 경우, 아래와 같이 변경 해주어야 합니다.
    input_id = id
    input_pw = pwd

    # ID input 클릭
    print("Input ID")
    username.click()
    # js를 사용해서 붙여넣기 발동 <- 왜 일부러 이러냐면 pypyautogui랑 pyperclip를 사용해서 복붙 기능을 했는데 운영체제때문에 안되서 이렇게 한거다.
    driver2.execute_script("arguments[0].value = arguments[1]", username, input_id)
    time.sleep(1)

    print("Input PW")
    pw.click()
    driver2.execute_script("arguments[0].value = arguments[1]", pw, input_pw)
    time.sleep(1)

    # Enable Stay Signed in
    if not driver2.find_element(By.CLASS_NAME, "input_keep").is_selected():
        driver2.find_element(By.CLASS_NAME, "keep_text").click()
        time.sleep(1)

    # Enable IP Security
    if not driver2.find_element(By.CLASS_NAME, "switch_checkbox").is_selected():
        driver2.find_element(By.CLASS_NAME, "switch_btn").click()
        time.sleep(1)

    # 입력을 완료하면 로그인 버튼 클릭
    driver2.find_element(By.CLASS_NAME, "btn_login").click()
    time.sleep(1)

    # new.save 등록
    # new.dontsave 등록 안함
    try:
        if newsave is True:
            driver2.find_element(By.ID, "new.save").click()
        else:
            driver2.find_element(By.ID, "new.dontsave").click()
        time.sleep(1)
    except Exception as e:
        # Print warning.
        logger.error(
            "new save or dontsave 오류 at %s: %s", driver2.title, type(e).__name__
        )

        log_messages(driver2, logging.ERROR)

        # Fallback to the login page only for headless mode, otherwise stay for
        # the user to resolve any login issues on the current page.
        if headless is True:
            driver.get("https://nid.naver.com")

    try_login_limit = int(os.getenv("TRY_LOGIN", "3"))
    try_login_count = 1
    while True:
        page_title = driver2.title
        if page_title == "Naver ID" or page_title == "네이버ID":
            break
        if try_login_count > try_login_limit:
            exit()
        print(f"로그인 되지 않음 #{try_login_count}")
        print(f"페이지 타이틀 : {page_title}")

        if headless is True:
            time.sleep(1)
        else:
            # Additional time for the user to address any login issues.
            time.sleep(30)
        try_login_count += 1

    return driver2
