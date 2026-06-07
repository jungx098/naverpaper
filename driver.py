#!/usr/bin/env python3
"""Chrome driver setup and Naver login."""

import logging
import os
import re
import time

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.remote_connection import RemoteConnection
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

# Cap each chromedriver HTTP round-trip so a hung Chrome tab cannot block
# indefinitely (default socket timeout is effectively unlimited).
DRIVER_COMMAND_TIMEOUT = int(os.getenv("DRIVER_COMMAND_TIMEOUT", "30"))
PAGE_LOAD_TIMEOUT = int(os.getenv("PAGE_LOAD_TIMEOUT", "30"))

logger = logging.getLogger(__name__)

# nid.naver.com page titles that indicate a successful, logged-in session.
LOGGED_IN_TITLES = ("Naver ID", "네이버ID")

# A user agent is treated as mobile when it matches this pattern. Supplying a
# mobile UA opts the account into Chrome's mobile emulation (see build_driver).
_MOBILE_UA_RE = re.compile(r"Mobile|Android|iPhone|iPad|iPod", re.IGNORECASE)

# Generic phone viewport used for mobile emulation when a mobile UA is set.
_MOBILE_DEVICE_METRICS = {
    "width": 412,
    "height": 915,
    "pixelRatio": 3.0,
    "touch": True,
}


def session_alive(driver: WebDriver) -> bool:
    """Return False when the chromedriver session is gone."""

    try:
        _ = driver.window_handles
        return True
    except WebDriverException:
        return False


def is_mobile_ua(ua: str | None) -> bool:
    """Return True when the user agent string looks like a mobile browser."""

    return ua is not None and bool(_MOBILE_UA_RE.search(ua))


def log_messages(driver: WebDriver, level: int) -> None:
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


def build_driver(ua: str | None, headless: bool, user_dir: str) -> WebDriver:
    """Create a Chrome WebDriver bound to the per-account profile.

    Applies anti-detection options and a 30s page-load timeout. Falls back to a
    driver without an explicit Service object if ChromeDriverManager fails.
    """

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
    if is_mobile_ua(ua):
        # Opt-in mobile mode: a bare --user-agent override leaves the rest of
        # the fingerprint (navigator.platform, touch support, viewport,
        # window.chrome) looking like desktop, which contradicts a mobile UA
        # and trips Naver's bot/captcha checks. Chrome's mobile emulation sets
        # the UA together with a mobile viewport and touch so the identity is
        # internally consistent.
        logger.info("Mobile user agent detected; enabling mobile emulation")
        chrome_options.add_experimental_option(
            "mobileEmulation",
            {"deviceMetrics": _MOBILE_DEVICE_METRICS, "userAgent": ua},
        )
    elif ua is not None:
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

    RemoteConnection.set_timeout(DRIVER_COMMAND_TIMEOUT)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    driver.set_script_timeout(PAGE_LOAD_TIMEOUT)
    driver.implicitly_wait(0)
    return driver


def login(
    driver: WebDriver,
    naver_id: str,
    password: str,
    newsave: bool,
    headless: bool,
) -> WebDriver:
    """Log in to Naver, reusing an existing session when one is present."""

    driver.get("https://nid.naver.com")

    # Login page (log-in required) title for nid.naver.com
    #   <title>Naver Sign in</title>
    # ID page (successful logged-in) title for nid.naver.com
    #   <title>Naver ID</title>
    if driver.title in LOGGED_IN_TITLES:
        logger.info("Existing log-in session used")
        return driver

    # nid may open the login form in a newly created tab; switch to it if one
    # exists, otherwise stay on the current tab.
    current_window_handle = driver.current_window_handle
    for handle in driver.window_handles:
        if handle != current_window_handle:
            driver.switch_to.window(handle)
            break

    username = driver.find_element(By.NAME, "id")
    pw = driver.find_element(By.NAME, "pw")

    # Set the value via JS (clipboard paste is unreliable across OSes), then
    # dispatch input/change events so Naver's client-side validation registers
    # the value. Without these events the form may submit empty or Naver may
    # decline to issue a persistent (stay-signed-in) session cookie.
    set_value = (
        "arguments[0].value = arguments[1];"
        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));"
    )

    # ID input 클릭
    print("Input ID")
    username.click()
    driver.execute_script(set_value, username, naver_id)
    time.sleep(1)

    print("Input PW")
    pw.click()
    driver.execute_script(set_value, pw, password)
    time.sleep(1)

    # Enable Stay Signed in (keep-login) so NID_AUT is issued as a persistent
    # cookie that survives a browser restart. NOTE: this option exists only on
    # the ID/PW login form; Naver's QR login has no "stay signed in" toggle and
    # always yields a session-scoped NID_AUT, so a QR login cannot persist
    # across runs.
    if not driver.find_element(By.CLASS_NAME, "input_keep").is_selected():
        driver.find_element(By.CLASS_NAME, "keep_text").click()
        time.sleep(1)

    # Disable IP security: it binds the session to the current IP, so a
    # changing IP forces re-login and undermines "stay signed in". Toggle it
    # off when it is currently enabled.
    if driver.find_element(By.CLASS_NAME, "switch_checkbox").is_selected():
        driver.find_element(By.CLASS_NAME, "switch_btn").click()
        time.sleep(1)

    # 입력을 완료하면 로그인 버튼 클릭
    driver.find_element(By.CLASS_NAME, "btn_login").click()
    time.sleep(1)

    # new.save 등록
    # new.dontsave 등록 안함
    try:
        if newsave is True:
            driver.find_element(By.ID, "new.save").click()
        else:
            driver.find_element(By.ID, "new.dontsave").click()
        time.sleep(1)
    except Exception as e:
        # Print warning.
        logger.error(
            "new save or dontsave 오류 at %s: %s", driver.title, type(e).__name__
        )

        log_messages(driver, logging.ERROR)

        # Fallback to the login page only for headless mode, otherwise stay for
        # the user to resolve any login issues on the current page.
        if headless is True:
            driver.get("https://nid.naver.com")

    try_login_limit = int(os.getenv("TRY_LOGIN", "3"))
    try_login_count = 1
    while True:
        page_title = driver.title
        if page_title in LOGGED_IN_TITLES:
            break
        if try_login_count > try_login_limit:
            # Raise instead of exit() so the caller can close the driver
            # cleanly (flushing cookies) and continue with other accounts.
            raise RuntimeError(
                f"Login failed after {try_login_limit} attempts "
                f"(last page title: {page_title!r})"
            )
        print(f"로그인 되지 않음 #{try_login_count}")
        print(f"페이지 타이틀 : {page_title}")

        if headless is True:
            time.sleep(1)
        else:
            # Additional time for the user to address any login issues.
            time.sleep(30)
        try_login_count += 1

    # Diagnose whether "stay signed in" actually took effect. NID_AUT is the
    # auth token; with keep-login enabled it must be persistent (have an
    # expiry) to survive a browser restart. A missing or session-scoped
    # NID_AUT means the next run will prompt for credentials again.
    nid_auth = driver.get_cookie("NID_AUT")
    if nid_auth is None:
        logger.warning("NID_AUT cookie absent after login; session will not persist")
    elif not nid_auth.get("expiry"):
        logger.warning(
            "NID_AUT is session-scoped (no expiry); 'stay signed in' did not apply "
            "- re-login expected next run. QR login cannot persist (no keep-login "
            "option); use the ID/PW form to get a persistent session."
        )
    else:
        logger.info("NID_AUT persistent (keep-login active)")

    return driver


def init(
    naver_id: str,
    password: str,
    ua: str | None,
    headless: bool,
    newsave: bool,
    user_dir: str,
) -> WebDriver:
    """Build a Chrome driver and log in to Naver (six-arg entry point)."""

    driver = build_driver(ua, headless, user_dir)
    return login(driver, naver_id, password, newsave, headless)
