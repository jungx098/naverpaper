# TODO

## Bugs

- [x] Fix duplicate `pw` check — now `id is None or pw is None` (`naper.py`, was also in `run_new.py`)
- [x] Fix broken standalone/CI execution — `run_new.py` removed; CI now runs `naper.py`
- [x] Replace hardcoded CSS class `PointsManage_point__T67hP` in `get_balance2` with class-prefix XPATH
- [x] Fix mutable default argument `urls: list = []` in `apprise_notify` — now `None` with guard
- [x] Fix file handle leak — credential file now loaded with `with open(...)`
- [x] Fix `dependabot.yml` version from `3` to `2`
- [x] Fix `TRY_LOGIN` string/int comparison — now `int(os.getenv("TRY_LOGIN", "3"))` in `driver.py`

## Dead Code Removal

- [x] Remove `main.py` (early prototype, no longer used)
- [x] Remove `run.py` (uses broken requests-based login from `naver/session.py`)
- [x] Remove `naver/` package (`session.py`, `find.py`)
- [x] Remove `naver_paper_clien.py`, `naver_paper_damoang.py`, `naver_paper_ppomppu.py`, `naver_paper_ruliweb.py`
- [x] Remove dead `grep_campaign_links()` and stale legacy imports
- [x] Extract `init()` into `driver.py`; remove `run_new.py` (broken `visit()`/`main()`)

## Project Hygiene

- [x] Add `.gitignore` (`.venv/`, `__pycache__/`, `*.html`, `*.png`, `*.db`, `log.txt*`, `account.json`, `accounts.json`, `visited_urls_*.txt`, `debug/`, `user_dir/`)
- [x] Clean up untracked generated files from the project root (removed ~574 html/png dumps)
- [x] Replace `setup.py` with `pyproject.toml` (deps aligned with `requirements.txt`)
- [x] Remove redundant `bs4==0.0.2` from `requirements.txt`
- [x] Pin all dependency versions consistently

## Code Quality

- [x] Replace bare `except:` clauses with specific exception types (`process_modal`)
- [x] Add `ruff` config (`pyproject.toml`) and resolve all lint findings
- [x] Add unit tests (`tests/`: `is_campaign_link`, `normalize_link`, `Database`)
- [x] Rename `id` variable to avoid shadowing Python builtin `id()` (`naper.py` and `driver.py` → `naver_id`)
- [x] Remove misleading `driver2 = driver` alias in `driver.py` (`init()` split into `build_driver()` + `login()`)
- [x] Standardize parameter naming (`naper.py` and `driver.py` now use `naver_id`/`password`)
- [x] Enable `ruff` `N` (pep8-naming); rename `text_to_change` → `TextToChange`; `Status` uses `enum.auto()`
- [ ] Add type hints to function signatures (done: pure functions in `naper`/`balance`/`scrape` and all of `driver.py`; remaining: selenium-driven handlers in `page_actions.py`)

## Security

- [x] Remove `-i` / `-p` CLI credential flags; use credential files or env vars only
- [x] Remove `verify=False` SSL bypass (resolved by removing `main.py`)
- [x] Stop writing secrets to disk in GitHub Actions workflow (`~/.naver/credentials`)
- [x] Ensure `accounts.json` / `account.json` cannot be accidentally committed (`.gitignore`)
- [x] Strengthen `mask_username()` — short IDs now fully/partially masked; fixed-width hides length (`tests/test_mask.py`)

## CI / GitHub Actions

- [x] Update `actions/checkout` and `actions/setup-python` from v3 to v4
- [x] Fix CI entry point — now runs `naper.py`
- [x] Use environment variables directly instead of writing a credentials file
- [x] Align CI Python version to 3.12
- [x] Add a CI lint/test step (`ruff check .` + `pytest`) — `.github/workflows/ci.yml`

## Operational

- [x] Make `git fetch && git rebase` in `run.sh` opt-in (`NAPER_AUTO_UPDATE=1`)
- [x] Add overlap protection for cron runs (flock lock in `run.sh`)
- [x] Write screenshots and HTML dumps to a dedicated `debug/` directory
- [ ] Configure cleanup/retention for `log.txt*` files (rotation exists; backups accumulate)
