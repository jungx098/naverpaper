#!/usr/bin/env sh

FILE=campaign.db

sqlite3 -csv -header $FILE \
    "select * from campaign WHERE creation >= datetime ((select max(creation) from campaign), '-7 days');" > temp.csv
csv2md temp.csv > campaign.md
rm temp.csv
