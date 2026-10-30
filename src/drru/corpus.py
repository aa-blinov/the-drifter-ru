#!/usr/bin/env python
"""The corpus: the game's English strings with the keys the game uses.

The game keys its text by (character, id): the same English line appears in
several places, and the translation has to be the same in all of them. The
corpus keeps those keys, the source file and the source function, because
the context of a line — who speaks, in which room, in which function — is
what makes a translation faithful.

Read from corpus/english.csv, which the extraction script writes:

    python3 src/drru/extract_corpus.py --game "<path to The Drifter>"

Written as JSONL, one line per string, so a stage can read a slice of it
without parsing a CSV.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CORPUS_CSV = os.path.join(ROOT, "corpus", "english.csv")
WORK = os.path.join(ROOT, "work")
CORPUS_JSONL = os.path.join(WORK, "corpus", "corpus.jsonl")

# The column the game reads the translation from, and the header the game
# expects in the CSV it imports.
LANG_CODE = "RU"
CSV_HEADER = ["Character", "ID", "File", "Context", "English", "Русский"]


def load_corpus(path: str = CORPUS_CSV):
    """Every line of the game, in the order the game holds them."""
    if not os.path.exists(path):
        raise SystemExit("corpus not found: %s" % path)
    rows = []
    with io.open(path, encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[:5] != ["Character", "ID", "File", "Context", "English"]:
            raise SystemExit("unexpected corpus header: %r" % (header,))
        for index, row in enumerate(reader):
            if len(row) < 5:
                raise SystemExit("short row %d: %r" % (index, row))
            rows.append({
                "index": index,
                "character": row[0],
                "id": row[1],
                "file": row[2],
                "context": row[3],
                "en": row[4],
            })
    return rows


def write_jsonl(rows, path: str = CORPUS_JSONL):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def read_jsonl(path: str):
    rows = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def key_of(row) -> str:
    """The key the game uses: character plus id."""
    return "%s|%s" % (row.get("character", ""), row.get("id", ""))


if __name__ == "__main__":
    rows = load_corpus()
    path = write_jsonl(rows)
    characters = len({r["character"] for r in rows})
    files = len({r["file"] for r in rows})
    print("corpus: %d lines, %d characters, %d source files -> %s"
          % (len(rows), characters, files, path))
