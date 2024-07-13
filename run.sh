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
    PYTHON=$LOCALAPPDATA/Programs/Python/Python312/python
else
    PYTHON=python
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
$PYTHON $SCRIPT --headless -cf account.json -vvvv
# $PYTHON $SCRIPT --headless -cf account.json

#==============================================================================
# Non-Headless
#==============================================================================
# $PYTHON $SCRIPT --no-headless -cf account.json

# End time stamp
echo "$(basename $0) End: $(date)"
