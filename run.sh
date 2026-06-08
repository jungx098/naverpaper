#!/usr/bin/env sh
# npaper cron/local wrapper.
#
# Usage:
#   run.sh [options] [npaper.py args...]
#
#   run.sh                         # no delay (default)
#   run.sh --random-delay          # random sleep 0..NPAPER_MAX_DELAY
#   run.sh --no-headless -v        # visible browser; -v goes to npaper.py
#
# Environment:
#   NPAPER_CREDENTIAL_FILE   accounts file path (default: accounts.json)
#   NPAPER_MAX_DELAY         max random sleep seconds (default: 1200)
#   NPAPER_AUTO_UPDATE       set to 1 to git fetch/rebase before run
#   NPAPER_SKIP_NETWORK      set to 1 to skip the connectivity probe
#   NPAPER_NETWORK_HOST      connectivity host (default: google.com)
#   NPAPER_NETWORK_PORT      connectivity port (default: 443)

set -eu

SCRIPT=npaper.py
SCRIPT_NAME=$(basename "$0")

show_help() {
    cat <<EOF
Usage: $SCRIPT_NAME [options] [npaper.py args...]

  $SCRIPT_NAME
      Run npaper.py immediately (no delay).

  $SCRIPT_NAME --random-delay
      Sleep a random 0..NPAPER_MAX_DELAY seconds, then run.

  $SCRIPT_NAME --no-headless -v
      Visible browser (default is headless); -v goes to npaper.py.

Environment:
  NPAPER_CREDENTIAL_FILE   accounts file (default: accounts.json)
  NPAPER_MAX_DELAY         max random sleep seconds (default: 1200)
  NPAPER_AUTO_UPDATE       1 = git fetch/rebase before run
  NPAPER_SKIP_NETWORK      1 = skip connectivity probe
  NPAPER_NETWORK_HOST      probe host (default: google.com)
  NPAPER_NETWORK_PORT      probe port (default: 443)

Default npaper.py invocation:
  python npaper.py --headless -cf <credential-file> -v [extra args]

Options:
  -h, --help        Show this help
  --random-delay    Random sleep 0..NPAPER_MAX_DELAY before run
  --headless        Headless browser (default)
  --no-headless     Visible browser
EOF
}

case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
esac

NPAPER_CREDENTIAL_FILE="${NPAPER_CREDENTIAL_FILE:-accounts.json}"
NPAPER_MAX_DELAY="${NPAPER_MAX_DELAY:-1200}"
NPAPER_NETWORK_HOST="${NPAPER_NETWORK_HOST:-google.com}"
NPAPER_NETWORK_PORT="${NPAPER_NETWORK_PORT:-443}"

random_duration() {
    min=$1
    max=$2
    shuf_cmd=

    if [ -n "${SHUF:-}" ] && command -v "$SHUF" >/dev/null 2>&1; then
        shuf_cmd=$SHUF
    elif command -v shuf >/dev/null 2>&1; then
        shuf_cmd=shuf
    fi

    if [ -n "$shuf_cmd" ]; then
        "$shuf_cmd" -i "${min}-${max}" -n 1
        return
    fi

    "$PYTHON" -c "import random; print(random.randint(int('$min'), int('$max')))"
}

acquire_lock() {
    LOCKFILE="${TMPDIR:-/tmp}/npaper.lock"
    LOCKDIR="${LOCKFILE}.d"

    if command -v flock >/dev/null 2>&1; then
        # shellcheck disable=SC3024
        exec 9>"$LOCKFILE"
        if ! flock -n 9; then
            return 1
        fi
        return 0
    fi

    if mkdir "$LOCKDIR" 2>/dev/null; then
        trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT INT TERM
        return 0
    fi

    return 1
}

#------------------------------------------------------------------------------
# Platform fallbacks (overridden by in-tree venv activation below)
#------------------------------------------------------------------------------

PYTHON=
SHUF=

case $(uname -s) in
    Darwin)
        echo "$SCRIPT_NAME: macOS"
        SHUF=gshuf
        PYTHON=python3
        ;;
    Linux)
        echo "$SCRIPT_NAME: Linux"
        SHUF=shuf
        PYTHON=python3
        ;;
    MINGW32_NT*)
        echo "$SCRIPT_NAME: Windows (MinGW)"
        export PYTHONIOENCODING=utf-8
        unset TZ
        SHUF=shuf
        PYTHON=/cygdrive/c/Python311/python
        ;;
    CYGWIN_NT*)
        echo "$SCRIPT_NAME: Windows (Cygwin)"
        export PYTHONIOENCODING=utf-8
        unset TZ
        SHUF=shuf

        if [ -z "${HOMEPATH:-}" ]; then
            echo "$SCRIPT_NAME: HOMEPATH not defined"
            exit 1
        fi

        if [ -n "${VIRTUAL_ENV:-}" ]; then
            if [ -x "$VIRTUAL_ENV/Scripts/python.exe" ]; then
                PYTHON="$VIRTUAL_ENV/Scripts/python.exe"
            elif [ -x "$VIRTUAL_ENV/bin/python" ]; then
                PYTHON="$VIRTUAL_ENV/bin/python"
            fi
        fi

        if [ -z "$PYTHON" ]; then
            if [ -z "${LOCALAPPDATA:-}" ]; then
                echo "$SCRIPT_NAME: LOCALAPPDATA not defined"
                exit 1
            fi
            PYTHON="$LOCALAPPDATA/Programs/Python/Python312/python"
        fi
        ;;
    *)
        echo "$SCRIPT_NAME: $(uname -s)"
        SHUF=shuf
        PYTHON=python3
        ;;
esac

#------------------------------------------------------------------------------
# Repo root + venv
#------------------------------------------------------------------------------

SCRIPT_PATH=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_PATH"

for vdir in .venv venv; do
    if [ -f "$SCRIPT_PATH/$vdir/bin/activate" ]; then
        # shellcheck disable=SC1090
        . "$SCRIPT_PATH/$vdir/bin/activate"
        PYTHON=python
        break
    elif [ -f "$SCRIPT_PATH/$vdir/Scripts/activate" ]; then
        # shellcheck disable=SC1090
        . "$SCRIPT_PATH/$vdir/Scripts/activate"
        PYTHON=python
        break
    fi
done

if [ -z "$PYTHON" ]; then
    PYTHON=python3
fi

# macOS: prefer PATH python3 over a missing MacPorts binary
if [ "$(uname -s)" = "Darwin" ] && ! command -v "$PYTHON" >/dev/null 2>&1; then
    if [ -x /opt/local/bin/python3 ]; then
        PYTHON=/opt/local/bin/python3
    fi
fi

if ! command -v "$PYTHON" >/dev/null 2>&1 && [ ! -x "$PYTHON" ]; then
    echo "$SCRIPT_NAME: Python not found: $PYTHON"
    exit 1
fi

if command -v "$PYTHON" >/dev/null 2>&1; then
    PYTHON=$(command -v "$PYTHON")
fi

echo "$SCRIPT_NAME: Using $("$PYTHON" --version 2>&1) ($PYTHON)"

#------------------------------------------------------------------------------
# Args: run.sh options, then npaper.py flags
#------------------------------------------------------------------------------

RANDOM_DELAY=0
HEADLESS_FLAG=--headless
NPAPER_EXTRA_ARGS=

while [ $# -gt 0 ]; do
    case "$1" in
        --random-delay)
            RANDOM_DELAY=1
            shift
            ;;
        --headless)
            HEADLESS_FLAG=--headless
            shift
            ;;
        --no-headless)
            HEADLESS_FLAG=--no-headless
            shift
            ;;
        *)
            NPAPER_EXTRA_ARGS="$NPAPER_EXTRA_ARGS $1"
            shift
            ;;
    esac
done

#------------------------------------------------------------------------------
# Preconditions
#------------------------------------------------------------------------------

if [ ! -f "$NPAPER_CREDENTIAL_FILE" ]; then
    echo "$SCRIPT_NAME: Missing credential file: $NPAPER_CREDENTIAL_FILE"
    exit 1
fi

if [ "$RANDOM_DELAY" = "1" ]; then
    DURATION=$(random_duration 0 "$NPAPER_MAX_DELAY")
else
    DURATION=0
fi

if [ "${NPAPER_SKIP_NETWORK:-0}" != "1" ]; then
    if command -v nc >/dev/null 2>&1; then
        nc -zw1 "$NPAPER_NETWORK_HOST" "$NPAPER_NETWORK_PORT" || {
            echo "$SCRIPT_NAME: No network ($NPAPER_NETWORK_HOST:$NPAPER_NETWORK_PORT): $(date)"
            exit 1
        }
    else
        echo "$SCRIPT_NAME: nc not found; skipping network check"
    fi
fi

if ! acquire_lock; then
    echo "$SCRIPT_NAME: Already running, skipping: $(date)"
    exit 0
fi

#------------------------------------------------------------------------------
# Run
#------------------------------------------------------------------------------

echo "$SCRIPT_NAME: Start: $(date)"

if [ "${NPAPER_AUTO_UPDATE:-0}" = "1" ]; then
    git fetch && git rebase || echo "$SCRIPT_NAME: Auto-update skipped (fetch/rebase failed)"
fi

if [ "$DURATION" -gt 0 ]; then
    echo "$SCRIPT_NAME: Sleep ${DURATION}s, then npaper.py"
    sleep "$DURATION"
fi

set +e
# shellcheck disable=SC2086
"$PYTHON" "$SCRIPT" $HEADLESS_FLAG -cf "$NPAPER_CREDENTIAL_FILE" -v $NPAPER_EXTRA_ARGS
STATUS=$?
set -e

echo "$SCRIPT_NAME: End: $(date) (exit $STATUS)"
exit "$STATUS"
