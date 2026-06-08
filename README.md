[![Npaper Python GitHub Actions](https://github.com/jungx098/naver-paper/actions/workflows/action.yml/badge.svg)](https://github.com/jungx098/naver-paper/actions/workflows/action.yml)

```ascii
 _  _                          
| \| |_ __  __ _ _ __  ___ _ _ 
| .` | '_ \/ _` | '_ \/ -_) '_|
|_|\_| .__/\__,_| .__/\___|_|  
     |_|        |_|   @jungx098
```

Selenium automation for Naver Pay benefit campaigns.

## What it does

Each run, per account:

1. **Scrapes** stamp-campaign links from Naver community sources (`scrape.py`).
2. **Reads** starting Naver Pay / Point balance.
3. **Completes Quick Reward** missions on the Npay Point benefit page.
4. **Visits** stamp campaigns not yet recorded in the local SQLite DB (last 3 days).
5. **Reports** balance gain and duration; optionally sends an [Apprise](https://github.com/caronc/apprise)
   notification when gain is non-zero.

Persistent Chrome profiles (`user_dir/`) let you log in once by hand and reuse the
session on later runs — see [First-time setup](#first-time-setup).

## Prerequisites

- **Python 3.12**
- **Google Chrome** — ChromeDriver is downloaded automatically at runtime by
  [`webdriver-manager`](https://github.com/SergeyPirogov/webdriver_manager); you only
  need Chrome installed.

### Linux

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get update
sudo apt-get install -y gdebi-core
sudo gdebi google-chrome-stable_current_amd64.deb
google-chrome --version
```

### macOS

```bash
brew install --cask google-chrome
# or download from https://www.google.com/chrome/
```

## Install

```bash
git clone https://github.com/jungx098/naver-paper.git
cd naver-paper
pip install -r requirements.txt
# or: pip install -e .
```

## First-time setup

Scripted ID/PW login can trigger Naver's captcha. The reliable approach is to seed
a persistent session once in a visible browser:

```bash
# 1. Create accounts.json (see below) — never commit this file.

# 2. Log in manually; keep "stay signed in" checked.
python seed_login.py -cf accounts.json

# 3. Normal runs reuse the saved profile.
python npaper.py -cf accounts.json -v
```

Set a fixed `ua` per account in `accounts.json` so seeding and headless runs share
the same browser fingerprint. See
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#naver-login-re-login-every-run--captcha)
for background.

> **GitHub Actions** runs on ephemeral VMs with no persistent `user_dir/`. It uses
> `USERNAME` / `PASSWORD` secrets and scripted login every time, so captcha risk
> remains higher than on a locally seeded profile.

## Usage

```bash
# Single account via environment variables
export USERNAME=your_naver_id
export PASSWORD=your_password
python npaper.py -v

# Multiple accounts via inline JSON
python npaper.py -c '[{"id":"ID_1","pw":"PW_1"},{"id":"ID_2","pw":"PW_2"}]' -v

# Credential file (recommended for local runs)
python npaper.py -cf accounts.json -v

# Visible browser (debugging)
python npaper.py -cf accounts.json --no-headless -v
```

### CLI flags

| Flag | Default | Description |
|------|---------|-------------|
| `-cf`, `--credential-file` | — | Path to `accounts.json` |
| `-c`, `--cd` | — | Inline credential JSON string |
| `--headless` / `--no-headless` | headless | Browser visibility |
| `-v`, `--verbose` | quiet console | Repeat for more console detail (`-vv` …) |
| `--newsave` / `--no-newsave` | off | Force the fresh-login code path |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USERNAME` | — | Naver ID (single-account mode) |
| `PASSWORD` | — | Naver password (single-account mode) |
| `TRY_LOGIN` | `3` | Login retry limit |
| `DRIVER_COMMAND_TIMEOUT` | `30` | Chromedriver HTTP timeout (seconds) |
| `PAGE_LOAD_TIMEOUT` | `30` | Page-load and script timeout (seconds) |

### Credential file format

`accounts.json` is a JSON list of account objects:

```json
[
  {
    "id": "naver_id",
    "pw": "naver_password",
    "ua": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
    "apprise": ["tgram://bottoken/chatid"]
  }
]
```

| Field | Required | Description |
|-------|----------|-------------|
| `id`, `pw` | yes | Naver credentials |
| `ua` | no | User agent; mobile UA strings enable Chrome mobile emulation |
| `apprise` | no | Apprise notification URLs; sent only when **gain ≠ 0** |

> **Never commit** `accounts.json` or `account.json` — they are git-ignored.

### Local wrapper (`run.sh`)

Optional shell script for cron or manual runs. It uses `.venv/bin/python` or
`venv/bin/python` when present, checks `accounts.json`, prevents overlapping runs,
then invokes:

```bash
python npaper.py [--headless|--no-headless] -cf accounts.json [extra args]
```

Default is `--headless` and a quiet console (same as `npaper.py`). Pass `-v` or
`-vv` via `run.sh` when you want console output (e.g. `./run.sh -v`). File log
(`log.txt`) is always INFO or higher. Use `./run.sh --no-headless` or
`python npaper.py --no-headless` for a visible browser.

```bash
./run.sh --help    # usage, env vars, and options
```

| Option | Description |
|--------|-------------|
| `--random-delay` | Sleep a random `0..NPAPER_MAX_DELAY` seconds before run (default: no delay) |
| `--headless` | Headless browser (default) |
| `--no-headless` | Visible browser |
| `-h`, `--help` | Show `run.sh` help |

`--headless` / `--no-headless` are handled by `run.sh` (only one is passed to
`npaper.py`). All other arguments are forwarded (e.g. `./run.sh -v`,
`./run.sh --no-headless -vv`).

| Environment variable | Default | Description |
|---------------------|---------|-------------|
| `NPAPER_CREDENTIAL_FILE` | `accounts.json` | Credential file path |
| `NPAPER_MAX_DELAY` | `1200` | Upper bound for `--random-delay` (seconds) |
| `NPAPER_AUTO_UPDATE` | off | `1` = `git fetch && git rebase` before run |
| `NPAPER_SKIP_NETWORK` | off | `1` = skip connectivity probe |
| `NPAPER_NETWORK_HOST` | `google.com` | Host for pre-run connectivity check |
| `NPAPER_NETWORK_PORT` | `443` | Port for pre-run connectivity check |

#### Cron examples

Edit paths for your install directory and log location.

```cron
# Every 2 hours — run immediately when cron fires
0 */2 * * * cd /path/to/naver-paper && ./run.sh >> /path/to/logs/npaper-cron.log 2>&1

# Random jitter 0–1200s before each run (spread load)
15 */2 * * * cd /path/to/naver-paper && ./run.sh --random-delay >> /path/to/logs/npaper-cron.log 2>&1

# Shorter jitter window (0–300s) + extra verbose output
30 */2 * * * cd /path/to/naver-paper && NPAPER_MAX_DELAY=300 ./run.sh --random-delay -vv >> /path/to/logs/npaper-cron.log 2>&1

# Timestamp each run in the log
0 */2 * * * cd /path/to/naver-paper && { echo "=== $(date) ==="; ./run.sh -vv; echo; } >> /path/to/logs/npaper-cron.log 2>&1

# Separate stdout and stderr
0 */2 * * * cd /path/to/naver-paper && ./run.sh -vv >> /path/to/logs/npaper.out.log 2>> /path/to/logs/npaper.err.log

# Debug: visible browser (not for routine cron)
0 9 * * * cd /path/to/naver-paper && ./run.sh --no-headless -vv >> /path/to/logs/npaper-debug.log 2>&1
```

`run.sh` logs start/end timestamps and the `npaper.py` exit code. The app also
writes `./log.txt` in the repo directory (independent of cron redirection).

## GitHub Actions

1. Fork this repo.
2. Add repository secrets: `USERNAME`, `PASSWORD` (and optionally `TRY_LOGIN`, default 3).
   (Settings → Secrets and variables → Actions → New repository secret)
3. The workflow runs every 30 minutes (`cron: '*/30 * * * *'`) and can be triggered manually.

Because CI has no persistent Chrome profile, treat Actions as a convenience for
accounts that tolerate scripted login — not a replacement for local `seed_login.py`.

## Logging and debug

| Output | Location | Notes |
|--------|----------|-------|
| Run log | `./log.txt` | Always written at INFO or higher |
| Console | stdout | Level controlled by `-v` |
| Error dumps | `./debug/` | HTML + PNG on stamp-campaign handler failures |

These paths are git-ignored along with `user_dir/` and `*.db`.

## Project layout

```
npaper.py           Main entry — balance, quick reward, campaign visits
seed_login.py      One-time interactive login to seed a Chrome profile
driver.py          Chrome setup, timeouts, Naver login
balance.py         Read Naver Pay / Point balances
scrape.py          Campaign link scraping + SQLite stamp DB
timings.py         Shared sleep and retry constants
page_actions/      Selenium page handlers (campaign + quick reward)
run.sh             Optional local cron wrapper
```

## Troubleshooting

Known issues and fixes: [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## References

- [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/) — optional manual driver pinning
- [Naver Pay benefit help (KO)](https://help.naver.com/service/5640/contents/10219?lang=ko)
- [Naver Pay point help (KO)](https://help.naver.com/service/5640/contents/8584?lang=ko)
