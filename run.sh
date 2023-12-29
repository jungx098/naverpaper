#!/usr/bin/env sh

# Platform specific commands
SHUF=""
NOSLEEP=""

if [ "$(uname)" = "Darwin" ]; then
    # Mac OS X platform
    echo Mac OS X platform
    SHUF="/opt/local/bin/gshuf"
    NOSLEEP="pmset noidle"
    :
elif [ "$(expr substr $(uname -s) 1 5)" = "Linux" ]; then
    # GNU/Linux platform
    echo GNU/Linux platform
    SHUF="shuf"
    :
elif [ "$(expr substr $(uname -s) 1 10)" = "MINGW32_NT" ]; then
    # Windows NT platform
    echo Windows NT platform
    SHUF="shuf"
    :
elif [ "$(expr substr $(uname -s) 1 9)" = "CYGWIN_NT" ]; then
    # Cygwin NT platform
    echo Cygwin NT platform
    SHUF="shuf"
    NOSLEEP="/opt/local/bin/nosleep.sh"
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

# Do not go to sleep.
if [ -n "$NOSLEEP" ]; then
    sh -c "$NOSLEEP" &
    NOSLEEP_PID=$!
fi

# Obtain current working directory and script directory
OLD_PATH=$(pwd)
SCRIPT_PATH=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# Change to script directory
cd $SCRIPT_PATH

# Run main script after random delay seconds.
sleep $DURATION
./main.py

# Run genmd.sh
./genmd.sh
# git add campaign.db campaign.md
# git commit -m 'Campaign DB Update'
# git push

# Change back to old working directory
cd $OLD_PATH

# Okay to go to sleep.
if [ -n "$NOSLEEP" ]; then
    kill $NOSLEEP_PID $(pgrep -P $NOSLEEP_PID)
fi

# End time stamp
echo "$(basename $0) End: $(date)"
