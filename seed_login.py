#!/usr/bin/env python3
"""One-time interactive profile seeding for naper.

Opens Chrome on the SAME per-account profile that naper.py uses (keyed by
id+pw+ua) and navigates to the Naver login page. You log in BY HAND -- typing
the ID/PW, solving any captcha, and keeping "stay signed in" (로그인 상태 유지)
checked. The tool then confirms whether a persistent NID_AUT cookie was stored,
so later `naper.py` runs reuse the session via login()'s existing-session
short-circuit instead of re-entering credentials (and tripping the captcha).

Usage:
    python seed_login.py -cf accounts.json
    python seed_login.py -c '[{"id":"...","pw":"...","ua":"..."}]'
    USERNAME=... PASSWORD=... python seed_login.py

Note on headless runs: a Naver keep-login session can be tied to the browser's
user agent. If naper.py runs headless (UA contains "HeadlessChrome") while this
seeder runs visible (UA "Chrome"), the UAs differ and Naver may invalidate the
session. To keep them consistent, set a fixed "ua" per account in accounts.json
(applied to both seeding and runs), or run naper.py with --no-headless.
"""
import argparse
import datetime
import json
import os

from driver import LOGGED_IN_TITLES, build_driver
from naper import user_dir_for


def load_accounts(args: argparse.Namespace) -> list[dict]:
    """Load credentials the same way naper.py accepts them."""

    if args.credential_file:
        with open(args.credential_file, encoding="utf-8") as file_obj:
            return json.load(file_obj)
    if args.cd:
        return json.loads(args.cd)

    naver_id = os.getenv("USERNAME")
    password = os.getenv("PASSWORD")
    if naver_id and password:
        return [{"id": naver_id, "pw": password}]
    return []


def describe_cookie(cookie: dict | None, name: str) -> bool:
    """Print a cookie's persistence state; return True if persistent."""

    if not cookie:
        print(f"  {name}: ABSENT")
        return False
    expiry = cookie.get("expiry")
    if expiry:
        when = datetime.datetime.fromtimestamp(expiry)
        print(f"  {name}: PERSISTENT (expires {when})")
        return True
    print(f"  {name}: SESSION-scoped (will NOT survive a restart)")
    return False


def seed(naver_id: str, password: str, ua: str | None) -> None:
    """Open the account's profile and wait for a manual login."""

    user_dir = user_dir_for(naver_id, password, ua)
    print(f"Profile: {user_dir}")

    driver = build_driver(ua, headless=False, user_dir=user_dir)
    try:
        driver.get("https://nid.naver.com")
        if driver.title in LOGGED_IN_TITLES:
            print("Already logged in - this profile has a valid session.")
        else:
            print("Log in MANUALLY in the browser window:")
            print("  - type the ID / PW by hand (do not let it autofill/paste)")
            print("  - solve the captcha (자동입력방지문자) if shown")
            print("  - keep 'stay signed in' (로그인 상태 유지) checked")
            print("Then return here and press Enter...")
            input()

        # Reload the login endpoint to confirm the resulting session state.
        driver.get("https://nid.naver.com")
        print(f"Page title: {driver.title!r}")
        print("Auth cookies:")
        persistent = describe_cookie(driver.get_cookie("NID_AUT"), "NID_AUT")
        describe_cookie(driver.get_cookie("NID_SES"), "NID_SES")

        if persistent:
            print("OK: naper.py should now reuse this session and skip login.")
        else:
            print(
                "WARNING: no persistent NID_AUT. Re-run and ensure 'stay signed "
                "in' is checked on the ID/PW form (QR login cannot persist)."
            )
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed naper Chrome profiles via a one-time manual login."
    )
    parser.add_argument("-cf", "--credential-file", help="credential json file")
    parser.add_argument("-c", "--cd", help="credential json string")
    args = parser.parse_args()

    accounts = load_accounts(args)
    if not accounts:
        print(
            "No credentials provided. Use -cf accounts.json, -c JSON, or set "
            "USERNAME/PASSWORD env."
        )
        return

    for index, account in enumerate(accounts, start=1):
        naver_id = account.get("id")
        password = account.get("pw")
        ua = account.get("ua")

        print(f"\n=== Account {index}/{len(accounts)} ===")
        if not naver_id or not password:
            print("Missing id/pw, skipping.")
            continue
        seed(naver_id, password, ua)


if __name__ == "__main__":
    main()
