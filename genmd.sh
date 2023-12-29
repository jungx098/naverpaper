#!/usr/bin/env sh

sqlite3 -csv campaign.db "select * from campaign;" > temp.csv
csv2md temp.csv > campaign.md
rm temp.csv
