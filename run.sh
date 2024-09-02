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

    # HOMEPATH is required for the python os module, and LOCALAPPDATA is needed
    # for the Python executable path. These variables might be missing when
    # this script is executed by cron.
    for var in HOMEPATH LOCALAPPDATA; do
        if [ -z "${!var}" ]; then
            echo "$var Not Defined"
            exit 1
        fi
    done

    PYTHON=$LOCALAPPDATA/Programs/Python/Python312/python
else
    PYTHON=python
fi

if ! command -v $PYTHON &> /dev/null; then
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

# Start time stamp
echo "$(basename $0) Start: $(date)"

# Obtain current working directory and script directory
OLD_PATH=$(pwd)
SCRIPT_PATH=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Change to script directory
cd $SCRIPT_PATH

# Update src.
git fetch
git rebase

# Run main script after random delay seconds.
sleep $DURATION

#==============================================================================
# Headless
#==============================================================================
$PYTHON $SCRIPT --headless -cf account.json -v
# $PYTHON $SCRIPT --headless -cf account.json

#==============================================================================
# Non-Headless
#==============================================================================
# $PYTHON $SCRIPT --no-headless -cf account.json

# End time stamp
echo "$(basename $0) End: $(date)"
