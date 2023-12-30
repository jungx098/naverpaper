#!/usr/bin/env sh

sqlite3 -csv -header campaign.db \
    "select * from campaign WHERE date >= datetime ((select max(date) from campaign), '-7 days');" > temp.csv
csv2md temp.csv > campaign.md
rm temp.csv
