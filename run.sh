#!/usr/bin/env sh

SCRIPT=naper.py

#==============================================================================
# Config for different platforms
#==============================================================================

if [ "$(uname)" = "Darwin" ]; then
    # Mac OS X platform
    echo Mac OS X platform
    SHUF="/opt/local/bin/gshuf"
    PYTHON=/opt/local/bin/python3
elif [ "$(expr substr $(uname -s) 1  5)" = "Linux"      ]; then
    # GNU/Linux platform
    echo GNU/Linux platform
    SHUF="shuf"
    PYTHON=python
elif [ "$(expr substr $(uname -s) 1 10)" = "MINGW32_NT" ]; then
    # Windows NT platform
    echo Windows NT platform
    export PYTHONIOENCODING=utf-8
    SHUF="shuf"
    # Clear TZ for datetime of Windows Python in Cygwin environment
    unset TZ
    PYTHON=/cygdrive/c/Python311/python
elif [ "$(expr substr $(uname -s) 1  9)" = "CYGWIN_NT"  ]; then
    # Cygwin NT platform
    echo Cygwin NT platform
    export PYTHONIOENCODING=utf-8
    SHUF="shuf"
    # Clear TZ for datetime of Windows Python in Cygwin environment
    unset TZ

    # HOMEPATH is required for the python os module. It might be missing when
    # this script is executed by cron.
    if [ -z "${HOMEPATH:-}" ]; then
        echo "HOMEPATH Not Defined"
        exit 1
    fi

    # Fallback interpreter, used only when the activation block below finds no
    # in-tree venv. Honor an already-active venv first, otherwise the
    # LOCALAPPDATA system Python.
    if [ -n "${VIRTUAL_ENV:-}" ]; then
        if [ -x "$VIRTUAL_ENV/Scripts/python.exe" ]; then
            PYTHON="$VIRTUAL_ENV/Scripts/python.exe"
        elif [ -x "$VIRTUAL_ENV/bin/python" ]; then
            PYTHON="$VIRTUAL_ENV/bin/python"
        fi
    fi

    if [ -z "$PYTHON" ]; then
        # LOCALAPPDATA is needed to locate a system-wide Python install. It
        # might be missing when this script is executed by cron.
        if [ -z "${LOCALAPPDATA:-}" ]; then
            echo "LOCALAPPDATA Not Defined"
            exit 1
        fi
        PYTHON=$LOCALAPPDATA/Programs/Python/Python312/python
    fi
else
    PYTHON=python
fi

# Resolve the script directory and switch into it. Needed for venv activation
# below, and so naper.py and any git auto-update run from the repo root.
SCRIPT_PATH=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_PATH"

# Activate an in-tree venv if present (all platforms). This is the single
# source of truth for in-tree venv preference: it overrides the platform
# fallback PYTHON set above and prepends the venv to PATH so any python
# subprocess naper.py spawns (e.g. webdriver-manager) uses it too.
for vdir in .venv venv; do
    if [ -f "$SCRIPT_PATH/$vdir/bin/activate" ]; then
        . "$SCRIPT_PATH/$vdir/bin/activate"
        PYTHON=python
        break
    elif [ -f "$SCRIPT_PATH/$vdir/Scripts/activate" ]; then
        . "$SCRIPT_PATH/$vdir/Scripts/activate"
        PYTHON=python
        break
    fi
done

# Validate the resolved interpreter (after any activation above).
if ! (command -v $PYTHON &> /dev/null); then
    echo "Command not found: $PYTHON"
    exit 1
fi

# Random sleep duration in seconds between 0 and 1200 (20 mins)
DURATION=$($SHUF -i 0-1200 -n 1)

if [ -n "$1" ]; then
    DURATION="$1"
fi

# Exit if network is not available
nc -zw1 google.com 443 || \
   { echo "$(basename $0) No network connection: $(date)"; exit; }

# Prevent overlapping cron runs. A run can take longer than the cron interval
# (random delay + multiple accounts), so skip if another instance holds the lock.
LOCKFILE="${TMPDIR:-/tmp}/naper.lock"
if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        echo "$(basename $0) Already running, skipping: $(date)"
        exit 0
    fi
fi

# Start time stamp
echo "$(basename $0) Start: $(date)"

# Optionally update src before running. Auto-rebasing a live working tree on
# every cron run is risky (it can fail on local changes or conflicts), so this
# is opt-in via NAPER_AUTO_UPDATE=1 and never aborts the run on failure.
if [ "$NAPER_AUTO_UPDATE" = "1" ]; then
    git fetch && git rebase || echo "$(basename $0) Auto-update skipped (fetch/rebase failed)"
fi

# Run main script after random delay seconds.
sleep $DURATION

#==============================================================================
# Headless
#==============================================================================
$PYTHON $SCRIPT --headless -cf accounts.json -v
# $PYTHON $SCRIPT --headless -cf accounts.json

#==============================================================================
# Non-Headless
#==============================================================================
# $PYTHON $SCRIPT --no-headless -cf accounts.json -v

# End time stamp
echo "$(basename $0) End: $(date)"
