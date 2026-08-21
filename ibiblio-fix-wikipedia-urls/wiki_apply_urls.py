#!/usr/bin/env python
"""Write Wikipedia URLs from CSV/JSON into Gutenberg MARC 500 notes.

Reads PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD from the environment.
CSV: book_id,wikipedia_url     JSON: {"78572": "https://en.wikipedia.org/..."}

    python wiki_apply_urls.py map.csv extra.json           # preview
    python wiki_apply_urls.py map.csv extra.json --apply   # write
"""
import csv
import json
import re
import sys

import psycopg2

PREFIX = "Wikipedia page about this book: "
DROP = {
    2798: "https://en.wikipedia.org/wiki/Portal:Children",
    17503: "https://pt.wikipedia.org/wiki/Os_Meus_Amores",
    18627: "https://fr.wikipedia.org/wiki/Notre-Dame-d",
    65332: "https://hu.wikipedia.org/wiki/1913_(egy",
}
LIKE = "%.wikipedia.org/wiki/%"
URL = re.compile(r"https?://[a-z-]+\.wikipedia\.org/wiki/\S+")


def load(path):
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            return [(int(k), v) for k, v in json.load(fh).items()]
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return [(int(r["book_id"]), r["wikipedia_url"]) for r in csv.DictReader(fh)]


def lang(url):
    return re.match(r"https?://([a-z-]+)\.wikipedia\.org/", url).group(1)


write = "--apply" in sys.argv
wanted = [pair for arg in sys.argv[1:] if not arg.startswith("-") for pair in load(arg)]
report = open("wiki_apply_%s.txt" % ("applied" if write else "preview"), "w", encoding="utf-8")


def say(line):
    print(line)
    report.write(line + "\n")


db = psycopg2.connect()
cur = db.cursor()
# Record sthe target: libpq quietly defaults any PG* variable you forget to set.
say("%s %@%s:%s/%s\n" % ("APPLY to" if write else "preview of", db.info.user,
                          db.info.host, db.info.port, db.info.dbname))
changed = skipped = deleted = 0

for book, url in wanted:
    if book in DROP:
        continue
    cur.execute("SELECT pk, text FROM attributes"
                " WHERE fk_books=%s AND fk_attriblist=500 AND text LIKE %s", (book, LIKE))
    # Same-language note only, so a book with en+de URLs can't cross-write.
    hits = [r for r in cur.fetchall() if "//%s.wikipedia.org/" % lang(url) in r[1]]
    if len(hits) > 1:
        hits = [(pk, text) for pk, text in hits for m in [URL.search(text)]
                if m and url.startswith(m.group(0))]
    if len(hits) != 1:
        say("SKIP    %s  (%s matching notes)  %s" % (book, len(hits), url))
        skipped += 1
        continue
    pk, old = hits[0]
    if old == PREFIX + url:
        continue
    say("CHANGED %s\n   from %s\n   to   %s" % (book, old, PREFIX + url))
    if write:
        cur.execute("UPDATE attributes SET text=%s WHERE pk=%s", (PREFIX + url, pk))
    changed += 1

for book, url in DROP.items():
    cur.execute("SELECT pk, text FROM attributes"
                " WHERE fk_books=%s AND fk_attriblist=500 AND text LIKE %s", (book, LIKE))
    hits = [(pk, text) for pk, text in cur.fetchall() for m in [URL.search(text)]
            if m and (m.group(0).startswith(url) or url.startswith(m.group(0)))]
    if not hits:
        say("NODELETE %s  expected %s  (not present, left alone)" % (book, url))
        continue
    for pk, old in hits:
        say("DELETED %s  %s" % (book, old))
        if write:
            cur.execute("DELETE FROM attributes WHERE pk=%s", (pk,))
        deleted += 1

db.commit() if write else db.rollback()
say("\n%d changed, %d deleted, %d skipped%s"
    % (changed, deleted, skipped, "" if write else "   (preview only, nothing written)"))
report.close()
print("report written to %s" % report.name)
