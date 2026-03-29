# TODO

## Bugs

- [ ] Fix duplicate `pw` check — `pw is None and pw is None` should be `id is None or pw is None` (`naper.py:611`, `run_new.py:220`)
- [ ] Fix broken `run_new.py` standalone execution — `main()` calls `init()` with 5 args but it requires 6 (missing `user_dir`); this also breaks the GitHub Actions workflow
- [ ] Replace hardcoded CSS class `PointsManage_point__T67hP` in `get_balance2` with a resilient XPATH selector (`naper.py:134`)
- [ ] Fix mutable default argument `urls: list = []` in `apprise_notify` — use `None` with a guard (`naper.py:474`)
- [ ] Fix file handle leak — use `with open(...)` for credential file loading (`naper.py:627`)
- [ ] Fix `dependabot.yml` version from `3` to `2`

## Dead Code Removal

- [ ] Remove `main.py` (early prototype, no longer used)
- [ ] Remove `run.py` (uses broken requests-based login from `naver/session.py`)
- [ ] Remove `naver/` package (`session.py`, `find.py`) — legacy requests-based login that no longer works
- [ ] Remove `naver_paper_clien.py`, `naver_paper_damoang.py`, `naver_paper_ppomppu.py`, `naver_paper_ruliweb.py` — superseded by class hierarchy in `scrape.py`
- [ ] Remove stale imports of the above modules in `run_new.py`
- [ ] Extract `init()` from `run_new.py` into a dedicated module (e.g. `driver.py`) and remove the unused `visit()`/`main()` in `run_new.py`

## Project Hygiene

- [ ] Add `.gitignore` (`.venv/`, `__pycache__/`, `*.html`, `*.png`, `*.db`, `log.txt*`, `account.json`, `accounts.json`, `visited_urls_*.txt`)
- [ ] Clean up 100+ untracked generated files from the project root
- [ ] Sync `setup.py` dependencies with `requirements.txt`, or replace `setup.py` with `pyproject.toml`
- [ ] Remove redundant `bs4==0.0.2` from `requirements.txt` (`beautifulsoup4` already listed)
- [ ] Pin all dependency versions consistently (some are pinned, others float)

## Code Quality

- [ ] Replace bare `except:` clauses with specific exception types (`run_new.py:182`, `naper.py:272-274`)
- [ ] Rename `id` variable to avoid shadowing Python builtin `id()`
- [ ] Remove misleading `driver2 = driver` aliases (`run_new.py:97`, `main.py:136`)
- [ ] Standardize parameter naming (`id`/`pw` vs `id`/`pwd` vs `id`/`passwd`)
- [ ] Add type hints to function signatures

## Security

- [ ] Remove `-i` / `-p` CLI credential flags (credentials visible in process listing); use credential files or env vars only
- [ ] Remove `verify=False` SSL bypass in `main.py`
- [ ] Stop writing secrets to disk in GitHub Actions workflow (`~/.naver/credentials`)
- [ ] Ensure `accounts.json` / `account.json` cannot be accidentally committed

## CI / GitHub Actions

- [ ] Update `actions/checkout` and `actions/setup-python` from v3 to v4
- [ ] Fix CI entry point — `run_new.py` standalone execution is broken (see Bugs)
- [ ] Consider using environment variables directly instead of writing a credentials file

## Operational

- [ ] Remove `git fetch && git rebase` from `run.sh` — auto-updating before execution is risky
- [ ] Add overlap protection for cron runs (e.g. flock/lockfile)
- [ ] Write screenshots and HTML dumps to a dedicated output directory instead of project root
- [ ] Configure log rotation or cleanup for `log.txt*` files
