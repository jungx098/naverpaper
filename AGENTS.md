# AGENTS.md

Instructions for AI coding agents working in this repository. Applies to the repo root unless a closer `AGENTS.md` exists (none today).

## Project overview

**naverpaper** automates Naver Pay benefit campaigns: it scrapes Naver campaign links from Korean community boards, logs into Naver via Selenium/Chrome, visits campaigns and quick-reward flows, tracks visits in SQLite, and optionally notifies via Apprise. Python 3.12, Selenium 4, BeautifulSoup/requests for scraping. Human-oriented setup and usage live in [README.md](README.md).

## Architecture

| Path | Role |
|------|------|
| `naper.py` | **Primary entry point** — CLI, campaign visit logic, balance checks, notifications |
| `scrape.py` | `Scrape*` classes + `scrape()` link discovery, `normalize_link()`; `Database` (SQLite per account under `user_dir/`) |
| `driver.py` | `init()` — Chrome driver setup and Naver login (imported by `naper.py`) |
| `logging_config.py` | `init_logger()` — console + rotating `log.txt` |
| `run.sh` | Cron/local wrapper: network check, flock lock, optional venv, opt-in update, runs `naper.py` |
| `tests/` | Pytest unit tests (`is_campaign_link`, `normalize_link`, `Database`) |

**Flow:** `scrape()` → per-account `main()` → `init()` → quick rewards → `visit()` → balance summary → optional Apprise.

**Per-account state:** `user_dir/<sha256(id+pw+ua)>/` (Chrome profile + `campaign.db`). Do not delete or commit `user_dir/`.

## Build, Test & Validation Commands

```bash
cd /path/to/naverpaper
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

```bash
# Dry run: scrape only (no browser)
python scrape.py
```

```bash
# Main run (credentials file or USERNAME/PASSWORD env; headless default)
python naper.py -cf accounts.json -v
```

```bash
# Visible browser
python naper.py -cf accounts.json --no-headless -v
```

```bash
# Cron-style wrapper (random 0–1200s delay unless arg given; flock-guarded)
./run.sh
./run.sh 0
```

**Prerequisites:** Google Chrome installed; `webdriver-manager` resolves ChromeDriver at runtime. Network required for Naver and board scraping.

**Tests / lint (dev deps in `pyproject.toml` `[project.optional-dependencies].dev`):**

```bash
pip install -e ".[dev]"   # or: pip install pytest ruff
python -m pytest -q       # unit tests (no network/browser needed)
ruff check .              # lint; ruff config lives in pyproject.toml
```

Also run `python scrape.py` and a single-account `naper.py --no-headless` smoke run when debugging UI selectors.

**Style:** 4-space indent, `logging` over `print` for new code, minimal diffs. `ruff` enforces pyflakes/pycodestyle/import-order/bugbear/pyupgrade.

## Code conventions

- Prefer **XPath or stable attributes** over brittle CSS module class names (e.g. `PointsManage_point__*` breaks when Naver ships new builds).
- Use **`with open(...)`** for file I/O; avoid bare `except:` — catch specific Selenium/request exceptions.
- Do not use **`id` as a variable name** (shadows builtin); prefer `account_id` / `naver_id` in new code.
- **Link discovery uses `scrape()`** (from `scrape.py`), called once in `naper.py`'s `__main__`. Add new boards as `Scrape*` subclasses there.
- **`init()`** lives in `driver.py` and requires six arguments including `user_dir`; callers must pass all six.
- Campaign links: validate via `Scrape.is_campaign_link()`; clean via `normalize_link()` (`redirect_uri` unwrap, CRLF/junk-prefix stripping).

## Security and secrets

- **Never commit** `account.json`, `accounts.json`, `user_dir/`, or credential-bearing env in logs.
- Credentials come from **`-cf accounts.json`**, **`-c` JSON**, or **`USERNAME`/`PASSWORD` env** only; the `-i`/`-p` flags were removed.
- Do not add real credentials to code, docs, or commit messages.
- GitHub Actions runs `naper.py --headless -v` with `USERNAME` / `PASSWORD` (and optional `TRY_LOGIN`) secrets passed as env — no credentials written to disk.

## Boundaries

**Do not edit or commit** (all covered by `.gitignore`)

- `.venv/`, `user_dir/`
- `debug/` and any `*.html` / `*.png` (debug page dumps/screenshots from `dump_page()`)
- `log.txt`, `log.txt.*`, `*.log`
- `*.db`, `visited_urls_*.txt`
- `account.json`, `accounts.json`

> `.gitignore` now covers these, but still stage files explicitly — avoid `git add -A` so a stray credential file is never committed.

**Do not run without user approval**

- `git push`, especially force push
- `run.sh` auto-update is now opt-in via `NAPER_AUTO_UPDATE=1`; do not enable it on a live tree without asking
- Bulk deletion of `user_dir/` or SQLite DBs

**Avoid unless asked**

- Expanding scope to unrelated refactors; fix the task at hand
- Creating new markdown docs beyond what the user requests

## Known issues (check `TODO.md`)

- `mask_username()` reveals first/last char; short IDs leak. Consider a stronger mask.
- UI flows depend on Naver's DOM; selectors use stable class-prefix XPath but can still break on redesigns. Use `--no-headless` and `debug/` dumps to diagnose.
- No CI smoke/lint step yet — `ruff check .` and `pytest` are run manually.

## Branch and upstream

Default working branch in this fork: `service.20240629` (tracks `origin/service.20240629`). Do not assume `main` is the integration branch. Remote: `git@github.com:jungx098/naverpaper.git`. See README for upstream/fork context.
