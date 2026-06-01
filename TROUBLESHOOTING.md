# Troubleshooting

Post-mortems and fixes for operational issues in naverpaper. Add new issues as
`##` sections, newest first.

- [Naver login: re-login every run / captcha](#naver-login-re-login-every-run--captcha)
- [WiFi auto-reconnect failure (Mar 20–28, 2026)](#wifi-auto-reconnect-failure-mar-2028-2026)

---

## Naver login: re-login every run / captcha

How the "stay signed in not working / captcha every run" problem was diagnosed
and fixed. Reference for future login regressions.

### Symptom

- Chrome asked for ID/PW on every run; "stay signed in" never persisted.
- Logs showed Naver's auto-input-prevention captcha:
  `message_text: "...enter the ... auto-input prevention character correctly."`

### Investigation (evidence, not guesses)

| Check | Result |
|-------|--------|
| Profile path stable across runs (`sha256(id+pw+ua)`) | Stable |
| Profile written to disk | Yes — 35 Naver cookies persisted |
| `NID_AUT` / `NID_SES` auth cookies on disk | **Absent** (only tracking cookies survived) |
| "Stay signed in" toggle (`input_keep` / `keep_text`) | Works — click flips checkbox to `true` |
| `navigator.webdriver` (headless & visible) | `false` (anti-detection flags work) |
| User agent (headless) | leaks `HeadlessChrome/148` |
| User agent (visible) | clean `Chrome/148` |
| Chrome options diff `refactor` vs `service.20240629` | **Identical** (no regression) |

#### Isolation with a bare-Chrome harness

A throwaway, configurable bare-Chrome script was used to binary-search the cause
(toggling anti-detection flags / reused profile / UA one at a time):

- Plain Chrome + manual typing → **login works**.
- Anti-detection flags only → **works** (flags are not the trigger).
- Reused profile (absolute path) → **works**.
- `build_driver` via `seed_login.py` with the account UA → **captcha fails**.

### Root cause

The account's `accounts.json` `ua` was a **mobile iPhone Safari** string applied
to a **desktop Chrome on Windows**. That UA contradicted the rest of the
fingerprint (`navigator.platform = Win32`, `window.chrome` present, desktop
WebGL, no touch) — a textbook bot signal that triggers Naver's captcha, which
the automation could never solve (it never enters the captcha characters).

Secondary issues found and fixed along the way:

- `driver.quit()` only ran on the success path, so a mid-run error skipped it
  and the login cookie was never flushed to the profile.
- `login()` called `exit()` on repeated failure, killing the whole run.
- Credentials were set via raw JS `.value` with no `input`/`change` events.
- IP security was being **enabled**, binding the session to the current IP.
- QR login was being relied on for persistence, but **QR has no "stay signed
  in" option** — it can only ever yield a session-scoped `NID_AUT`.

### Fixes implemented

- **`driver.py`**
  - Opt-in **mobile emulation**: a mobile `ua` now enables Chrome
    `mobileEmulation` (UA + viewport + touch together) instead of a bare
    `--user-agent`, so the fingerprint is internally consistent.
  - Credentials set via JS now dispatch `input`/`change` events.
  - **IP security disabled** (toggled off when on).
  - Repeated-failure path raises `RuntimeError` instead of `exit()`.
  - Post-login diagnostic logs whether `NID_AUT` is persistent / session-scoped
    / absent.
- **`naper.py`**
  - `driver.quit()` moved into a `finally` so cookies always flush.
  - Profile-path logic extracted to shared `user_dir_for()`.
- **`seed_login.py`** (new) — one-time interactive seeding tool.

### Recommended workflow

The robust approach is a **persistent session seeded once by hand**, after
which automated runs reuse it and never face the captcha:

1. Set a consistent UA in `accounts.json` (a mobile **Chrome/Android** UA works;
   avoid iPhone Safari, which claims a different engine):

   ```
   Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36
   ```

2. Seed the profile once (mobile emulation engages automatically):

   ```bash
   python seed_login.py -cf accounts.json
   ```

   Log in manually, keep "stay signed in" checked, confirm `NID_AUT: PERSISTENT`.

3. Run normally and confirm the short-circuit:

   ```bash
   python naper.py -cf accounts.json --no-headless -v
   ```

   Look for `Existing log-in session used` and `NID_AUT persistent`.

### Tools

- `seed_login.py` — one-time interactive seeding of a persistent session into
  the per-account profile (the recommended fix).
- For deeper debugging, build a small local bare-Chrome script that toggles one
  variable at a time (anti-detection flags / reused profile / UA / headless) to
  isolate which option trips the captcha.

### Caveats

- Changing `ua` changes the profile hash → a new `user_dir` → re-seed once.
- `login()` still targets the **desktop** login selectors. With a mobile UA the
  automated form path would hit Naver's mobile page; rely on the seeded session
  (short-circuit) instead, or add mobile-page selectors for full automation.
- `navigator.platform` can still read `Win32` under emulation; far more
  consistent than before, but a real device is the only perfect match.
- Headless UA: mobile emulation sets the UA explicitly, so `--headless` does not
  leak `HeadlessChrome`. The **non-mobile** path still does — for headless desktop
  runs set a desktop `ua` or run `--no-headless`.
- Naver's captcha is risk-scored (IP/frequency), so it is somewhat
  non-deterministic.

---

## WiFi auto-reconnect failure (Mar 20–28, 2026)

### Symptom

The cron job (`run_cron.sh`, every 2 hours) stopped producing logs after Mar 20 02:17.
The `nc -zw1 google.com 443` network check in `run.sh` was failing, causing the script
to exit immediately before reaching the Python execution.

### Root cause

1. **WiFi dropped** on Mar 20 ~03:11 — the router SSID became temporarily
   unreachable (`ssid-not-found`).

2. NetworkManager attempted to reconnect. During the WPA 4-way handshake, the connection
   failed again. NM interpreted this as a **wrong password** and transitioned to
   `need-auth` state, requesting new credentials from a GNOME Shell secret agent.

3. **No secret agent was available** (screen locked / no active GUI session), so NM
   failed with `no-secrets`:
   ```
   device (<wifi-iface>): no secrets: No agents were available for this request.
   device (<wifi-iface>): state change: need-auth -> failed (reason 'no-secrets')
   ```

4. After exhausting `autoconnect-retries` (default: **4 attempts**), NM gave up
   permanently. The WiFi interface went `inactive` and **never retried** — even after
   the router came back online.

5. WiFi only reconnected 8 days later (Mar 28 20:14) when a GUI login started the
   GNOME Shell NetworkAgent, which unblocked the stored credentials.

### Fix applied

#### 1. Unlimited autoconnect retries

```bash
sudo nmcli connection modify <SSID> connection.autoconnect-retries 0
```

NM will now retry indefinitely instead of giving up after 4 failures.

#### 2. Dispatcher script for forced reconnect

Created `/etc/NetworkManager/dispatcher.d/99-wifi-reconnect`:

```sh
#!/bin/sh

IFACE="$1"
ACTION="$2"

if [ "$IFACE" = "<wifi-iface>" ] && [ "$ACTION" = "down" ]; then
    sleep 10
    STATE=$(nmcli -t -f STATE general status 2>/dev/null)
    if [ "$STATE" != "connected" ]; then
        logger -t wifi-reconnect "WiFi down, attempting reconnect"
        nmcli connection up <SSID> 2>/dev/null
    fi
fi
```

When the WiFi interface goes down, this waits 10 seconds then forces a reconnect via
`nmcli connection up`, which uses the stored PSK directly — bypassing the secret agent
requirement.

#### 3. Cron output redirection (debug aid)

The crontab entry was updated to capture output for future debugging:

```
0 */2 * * * /path/to/run_cron.sh >> /tmp/naverpaper_cron_debug.log 2>&1
```

Previously, cron output was silently lost (no mail system installed).
