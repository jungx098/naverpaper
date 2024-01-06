#!/usr/bin/env python3

import sqlite3

src_conn = sqlite3.connect("campaign.db")
src_cur = src_conn.cursor()

src_cur.execute("SELECT * FROM campaign")

rows = src_cur.fetchall()

dst_conn = sqlite3.connect("foo.db")
dst_cur = dst_conn.cursor()
dst_cur.execute("""
CREATE TABLE IF NOT EXISTS campaign (
            id INTEGER PRIMARY KEY,
            creation DATE DEFAULT (datetime('now', 'localtime')),
            url TEXT UNIQ NOT NULL,
            visit DATE
);
""")


for row in rows:
    print(row[1])
    print(row[2])
    dst_cur.execute("INSERT OR IGNORE INTO campaign (creation, url) VALUES (?, ?)", (row[1], row[2]))

dst_conn.commit()
dst_conn.close()
